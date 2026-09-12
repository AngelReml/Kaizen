"""Director Brand — orquesta los cuatro sub-agentes y atiende el contrato (tesis §6.4).

El Brand es el segundo cubo del catálogo y el PRIMERO que levanta comités de verificación
(para validar campañas). Atiende `brand.review_requested`, aplica el Brand Guardian, y para
artefactos de campaña (preventivos) levanta un comité de OpenGravity —SIN importar el cubo
OpenGravity: lo invoca publicando `opengravity.review_requested` y leyendo el
`opengravity.review_completed` correlacionado (regla de §7.1, comunicación solo por eventos).

Si OpenGravity está apagado, el comité no llega: el Director degrada con el veredicto del
Guardian y marca el resultado para auditoría posterior (cierra con §7.2).
"""
from __future__ import annotations

import uuid

from core.bus import MessageBus
from core.events import Event, EventType, Criticality
from departments.brand.brand_guardian import BrandGuardian
from departments.brand.brand_strategist import BrandStrategist
from departments.brand.asset_manager import AssetManager
from departments.brand.voice_auditor import VoiceAuditor

# Tipos de artefacto Brand que se tratan como campaña → comité preventivo.
TIPOS_CAMPANA = {"campana", "campaign", "lanzamiento", "comunicado_publico", "anuncio", "landing"}


class DirectorBrand:
    name = "brand"

    def __init__(self, bus: MessageBus, empresa: str = "laboratorio", *,
                 guardian: BrandGuardian | None = None, suscribir: bool = True) -> None:
        self.bus = bus
        self.empresa = empresa
        self.guardian = guardian or BrandGuardian(empresa)
        self.strategist = BrandStrategist(empresa)
        self.assets = AssetManager(empresa)
        self.voice = VoiceAuditor(empresa)
        self._veredictos_comite: dict[str, dict] = {}   # decision_id → payload de review_completed
        if suscribir:
            bus.subscribe(self._on_review_requested, types=[EventType.BRAND_REVIEW_REQUESTED])
            bus.subscribe(self._capturar_comite, types=[EventType.OPENGRAVITY_REVIEW_COMPLETED])
        # Cubo sin dependencia de arranque: se marca listo sin preguntar por nadie (§7.1).
        bus.publish(Event(EventType.CUBE_STARTED, source=self.name,
                          payload={"cube": self.name, "empresa": empresa}, company=empresa))

    # ── Contrato: revisión de un artefacto de marca ──────────────────────────
    def revisar(self, *, asunto: str, cuerpo: str, artifact_type: str | None = None,
                lead: dict | None = None, correlation_id: str | None = None,
                usar_llm: bool = True) -> dict:
        review = self.guardian.revisar(asunto, cuerpo, lead=lead, usar_llm=usar_llm)
        resultado = {
            "aprobado": review.aprobado,
            "problemas": review.problemas,
            "sugerencias": review.sugerencias,
            "detalle_llm": review.detalle_llm,
            "comite": None,
            "degradado": False,
        }

        es_campana = (artifact_type or "").lower() in TIPOS_CAMPANA
        if es_campana and review.aprobado:
            payload = self._levantar_comite(asunto, cuerpo, correlation_id)
            if payload is None:
                # OpenGravity apagado: degradación elegante (§7.2). Sale con bandera.
                resultado["degradado"] = True
                resultado["degraded_reason"] = "consumer_off"
            else:
                resultado["comite"] = payload
                if payload.get("verdict") != "PASS" or payload.get("escalate"):
                    resultado["aprobado"] = False
                    resultado["problemas"].append(
                        f"Comité OpenGravity: {payload.get('verdict')} "
                        f"(consenso {payload.get('consensus')}, confianza {payload.get('confidence')}).")
        return resultado

    def _levantar_comite(self, asunto: str, cuerpo: str,
                         correlation_id: str | None) -> dict | None:
        """Publica review_requested (preventivo, dominio brand) y recoge el veredicto
        correlacionado. Devuelve None si OpenGravity no respondió (apagado)."""
        decision_id = uuid.uuid4().hex
        artifact = f"Asunto: {asunto}\n\n{cuerpo}"
        self.bus.publish(Event(
            EventType.OPENGRAVITY_REVIEW_REQUESTED, source=self.name,
            payload={"decision_id": decision_id, "mode": "preventive", "domain": "brand",
                     "artifact": artifact, "artifact_type": "campana", "context": ""},
            company=self.empresa, correlation_id=correlation_id, criticality=Criticality.HIGH,
        ))
        # En bus síncrono el review_completed ya llegó vía _capturar_comite.
        return self._veredictos_comite.pop(decision_id, None)

    # ── Handlers del bus ─────────────────────────────────────────────────────
    def _on_review_requested(self, event: Event) -> None:
        p = event.payload or {}
        resultado = self.revisar(
            asunto=p.get("asunto", ""), cuerpo=p.get("cuerpo", ""),
            artifact_type=p.get("artifact_type"), lead=p.get("lead"),
            correlation_id=event.correlation_id, usar_llm=p.get("usar_llm", True),
        )
        self.bus.publish(Event(
            EventType.BRAND_REVIEW_COMPLETED, source=self.name,
            payload={**resultado, "decision_id": p.get("decision_id")},
            company=event.company, correlation_id=event.correlation_id,
            criticality=Criticality.MEDIUM,
        ))

    def _capturar_comite(self, event: Event) -> None:
        did = (event.payload or {}).get("decision_id")
        if did:
            self._veredictos_comite[did] = event.payload
