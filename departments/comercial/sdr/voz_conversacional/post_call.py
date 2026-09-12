"""Orquestador post-call.

Cuando los 3 webhooks asíncronos (status_completed, recording, transcript) han llegado
para un call_sid, se ejecuta:

  1. Verificación de conformidad (R1: recording presente; R5: aviso legal registrado).
  2. Transición ENRIQUECIDO → EN_CONTACTO (si el lead estaba en ENRIQUECIDO).
  3. Análisis de calidad (4 criterios: compromiso + tono + objeciones + mejoras).
  4. Persistencia del dictamen como nodo `analisis_llamada`.
  5. Si compromiso detectado con confianza ≥0.6 → Account Executive escala.

Idempotente: si el análisis ya se hizo, no se repite.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from core.knowledge import KnowledgeStore
from departments.comercial.account_executive import AccountExecutive
from departments.comercial.lifecycle import EstadoLead, LeadStore, TransicionInvalida
from departments.comercial.sdr.voz_conversacional import transcripts as _t
from departments.comercial.sdr.voz_conversacional.analisis_calidad import (
    AnalisisCalidadLlamada, DictamenCalidad,
)

TIPO_ANALISIS = "analisis_llamada"
EVENTOS_REQUERIDOS = frozenset({"status_completed", "recording", "transcript"})


@dataclass
class ResultadoPostCall:
    analizado: bool
    dictamen: DictamenCalidad | None = None
    analisis_id: str | None = None
    no_conforme_motivos: list[str] = field(default_factory=list)
    razon_no_analizado: str = ""


class PostCallOrchestrator:
    def __init__(self, *, lead_store: LeadStore, knowledge: KnowledgeStore | None = None,
                 company: str = "laboratorio",
                 analisis: AnalisisCalidadLlamada | None = None,
                 account_executive: AccountExecutive | None = None) -> None:
        self.lead_store = lead_store
        self.knowledge = knowledge or lead_store.k
        self.company = company
        self.analisis = analisis or AnalisisCalidadLlamada()
        self.ae = account_executive or AccountExecutive(lead_store=lead_store)

    def tal_vez_disparar_analisis(self, call_sid: str) -> ResultadoPostCall:
        """Llamar tras cada webhook recibido. Si los 3 eventos están listos, analiza."""
        llamada = _t.get_llamada(self.knowledge, self.company, call_sid)
        if llamada is None:
            return ResultadoPostCall(False, razon_no_analizado="llamada no existe")
        if llamada.get("analisis_id"):
            return ResultadoPostCall(False, razon_no_analizado="ya analizado")
        eventos = set(llamada.get("eventos_completados") or [])
        if not EVENTOS_REQUERIDOS.issubset(eventos):
            faltan = sorted(EVENTOS_REQUERIDOS - eventos)
            return ResultadoPostCall(False,
                                      razon_no_analizado=f"faltan eventos: {','.join(faltan)}")

        # ── 1. Conformidad ──────────────────────────────────────────────────
        motivos_nc = self._motivos_no_conforme(llamada)
        if motivos_nc:
            for m in motivos_nc:
                _t.marcar_no_conforme(self.knowledge, self.company, call_sid, m)
            return ResultadoPostCall(False, no_conforme_motivos=motivos_nc,
                                      razon_no_analizado="no_conforme")

        # ── 2. Transición ENRIQUECIDO → EN_CONTACTO (si procede) ────────────
        lead = self.lead_store.get(llamada["lead_id"])
        if lead and lead.get("estado") == EstadoLead.ENRIQUECIDO.value:
            try:
                self.lead_store.transicionar(
                    llamada["lead_id"], EstadoLead.EN_CONTACTO,
                    razon="Llamada voz completada",
                    detalle={"call_sid": call_sid,
                             "duracion_s": llamada.get("duracion_s", 0)},
                )
                lead = self.lead_store.get(llamada["lead_id"])
            except TransicionInvalida:
                pass     # otro path ya transicionó; seguimos

        # ── 3. Análisis ─────────────────────────────────────────────────────
        dictamen = self.analisis.analizar(
            transcript=llamada.get("transcript") or [],
            call_sid=call_sid,
            lead=lead,
            duracion_s=float(llamada.get("duracion_s", 0)),
            agente_config_version=llamada.get("agente_config_version", "v1"),
            company=self.company,
        )

        # ── 4. Persistir dictamen ───────────────────────────────────────────
        analisis_id = f"an_{call_sid}_{uuid.uuid4().hex[:6]}"
        nodo_an = dictamen.to_dict()
        nodo_an["id"] = analisis_id
        self.knowledge.add(self.company, TIPO_ANALISIS, analisis_id, nodo_an)
        _t.actualizar_llamada(self.knowledge, self.company, call_sid,
                              analisis_id=analisis_id, estado="completada")

        # ── 5. Escalada al Account Executive si hay compromiso ──────────────
        if dictamen.compromiso.es_compromiso and dictamen.compromiso.confianza >= 0.6:
            texto_cliente = "\n".join(
                t.get("texto", "") for t in (llamada.get("transcript") or [])
                if t.get("hablante") == "cliente"
            )
            self.ae.gestionar_compromiso(
                llamada["lead_id"], dictamen.compromiso, respuesta_texto=texto_cliente,
            )

        return ResultadoPostCall(True, dictamen=dictamen, analisis_id=analisis_id)

    # ── Conformidad (R1, R5, R2) ───────────────────────────────────────────
    @staticmethod
    def _motivos_no_conforme(llamada: dict) -> list[str]:
        motivos = []
        if not llamada.get("recording_path"):
            motivos.append("recording_no_descargado")    # R1
        if not llamada.get("transcript"):
            motivos.append("transcript_vacio")           # R2
        elif len(llamada.get("transcript") or []) < 2:
            motivos.append("transcript_solo_un_turno")
        if not llamada.get("aviso_legal_version"):
            motivos.append("aviso_legal_no_registrado")  # R5
        return motivos
