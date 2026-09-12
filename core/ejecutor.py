"""Ejecutor real tras la aprobacion — R-16 (roadmap F3).

Auditoria 2026-07-20: aprobar una tarjeta en el panel marcaba `EJECUTADA` sin ejecutar
nada (panel_mando/app.py). Esto convierte la aprobacion en una ejecucion REAL con TODAS
las barreras DELANTE y en orden, sin ningun camino dry fantasma ni camino que las salte:

    AI Act (E4) → freno de coste (R-05) → panico (R-08) → envio del cubo Comercial

Diseño:
  - El envio real es INYECTABLE (`enviar`): en produccion es el canal Comercial; en pruebas,
    un doble. Por defecto, si no se pasa, el ejecutor es sandbox-seguro: NO inventa un envio.
  - Cada barrera que falla LANZA su excepcion (fail-closed). El panel las traduce con su
    escudo. Nada se marca "ejecutado" si una barrera corta: el estado del pendiente lo
    gobierna la cola (aprobado/enviando/enviado), no este ejecutor.
  - Sandbox global (KAIZEN_ENVIO_HABILITADO=false) => el ejecutor NO envia al mundo: hace un
    ensayo en seco EXPLICITO (marcado dry=True), jamas un "EJECUTADA" que miente.
"""
from __future__ import annotations

import os

from core import aiact_gate
from core.panico import Panico
from core.techos import LibroCoste, TechoAlcanzado


def envio_habilitado() -> bool:
    return os.environ.get("KAIZEN_ENVIO_HABILITADO", "false").lower() == "true"


class EjecutorComercial:
    """Compone las barreras en orden y, solo si todas pasan, delega el envio real."""

    def __init__(self, *, panico: Panico | None = None, libro: LibroCoste | None = None,
                 comite=None, enviar=None) -> None:
        self.panico = panico
        self.libro = libro
        self.comite = comite            # opcional: callable(artefacto, company)->outcome con .mediacion
        self.enviar = enviar            # callable(**envio)->dict ; None => sandbox dry

    def ejecutar(self, *, tenant: str, canal: str, texto: str, coste_previsto_eur: float = 0.0,
                 clase: str = "IRREVERSIBLE-EXTERNA", ahora=None, **envio) -> dict:
        pasos = []

        # 1 · AI Act art. 50 por fecha (E4) — DELANTE de todo lo demas.
        gate = aiact_gate.exigir_transparencia(texto, ahora=ahora, canal=canal)
        pasos.append({"barrera": "aiact", **gate})

        # 2 · Comite endurecido (R-03/R-14) si esta cableado. Un PASS del comite NUNCA es
        #     la unica autorizacion: es ADEMAS de la aprobacion humana que ya ocurrio.
        if self.comite is not None:
            outcome = self.comite(texto, tenant)
            verdict = getattr(getattr(outcome, "mediacion", None), "verdict", None)
            v = getattr(verdict, "value", str(verdict))
            pasos.append({"barrera": "comite", "verdict": v})
            if v != "PASS":
                raise ComiteNoAutoriza(f"el comite no autoriza ({v}); la accion no sale")

        # 3 · Freno de coste DELANTE (R-05): si rebasa techo, no se ejecuta.
        if self.libro is not None:
            self.libro.hard_stop_delante(tenant, coste_previsto_eur)
            pasos.append({"barrera": "coste", "previsto_eur": coste_previsto_eur})

        # 4 · Panico (R-08): corta toda IRR-EXT en <=1 ciclo, conserva la cola.
        if self.panico is not None:
            self.panico.gate_irrext(tenant, clase)
            pasos.append({"barrera": "panico", "ok": True})

        # 5 · Envio real — o ensayo en seco EXPLICITO si el sandbox global esta cerrado.
        if not envio_habilitado() or self.enviar is None:
            return {"estado": "ENSAYO_SECO", "dry": True, "enviado": False, "pasos": pasos,
                    "motivo": ("sandbox global cerrado (KAIZEN_ENVIO_HABILITADO=false): "
                               "ensayo en seco; ningun envio real (R4)")}
        resultado = self.enviar(tenant=tenant, canal=canal, texto=texto, **envio)
        return {"estado": "EJECUTADA", "dry": False, "enviado": True, "pasos": pasos,
                "resultado": resultado}


class ComiteNoAutoriza(RuntimeError):
    """R-16: el comite endurecido no dio PASS; la accion irreversible no sale."""
