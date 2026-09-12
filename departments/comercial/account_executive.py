"""Account Executive básico (v0.2 §2.4 Equipo Agricultor).

Recibe leads que el SDR marcó como en Compromiso Recíproco. En Fase 1 valida la señal
y registra la `operacion_muestra_preparada` para que el Jefe de Cuentas (o humano) decida
qué productos enviar y a través de qué transportista — la ejecución del envío de muestra
es Fase 2 (requiere catálogo del tenant estructurado + acuerdo con empresa de transporte).

En Fase 1 ejerce de gate de validación: comprueba la decisión del detector, transiciona
el lead, anota la operación y emite el evento para que el operador la vea en el panel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.events import Event, EventType
from departments.comercial.lifecycle import EstadoLead, LeadStore, TransicionInvalida
from departments.comercial.sdr.compromiso import DecisionCompromiso

TIPO_OPERACION = "operacion_muestra"


@dataclass
class ResultadoEscalado:
    ok: bool
    lead_id: str
    motivo: str = ""
    operacion_id: str | None = None


class AccountExecutive:
    """Punto de entrada cuando el SDR detecta compromiso recíproco.

    `gestionar_compromiso` requiere que la señal venga del detector (no acepta señales
    inventadas) y que el lead esté en estado EN_CONTACTO. Cualquier otra cosa se rechaza
    para mantener disciplina del pipeline."""

    def __init__(self, *, lead_store: LeadStore, knowledge=None, bus=None,
                 confianza_minima: float = 0.6) -> None:
        self.lead_store = lead_store
        self.knowledge = knowledge or lead_store.k
        self.bus = bus
        self.confianza_minima = confianza_minima

    def gestionar_compromiso(self, lead_id: str, decision: DecisionCompromiso, *,
                             respuesta_texto: str = "") -> ResultadoEscalado:
        if not decision.es_compromiso:
            return ResultadoEscalado(False, lead_id, motivo="decisión: no es compromiso")
        if decision.confianza < self.confianza_minima:
            return ResultadoEscalado(False, lead_id,
                                     motivo=f"confianza {decision.confianza:.2f} bajo "
                                            f"el mínimo {self.confianza_minima:.2f}; mantenerse en nurturing")

        lead = self.lead_store.get(lead_id)
        if lead is None:
            return ResultadoEscalado(False, lead_id, motivo=f"lead '{lead_id}' no existe")

        try:
            self.lead_store.transicionar(
                lead_id, EstadoLead.COMPROMISO_RECIPROCO,
                razon="SDR detectó Compromiso Recíproco",
                detalle={"senales": decision.senales_detectadas,
                         "confianza": decision.confianza,
                         "motivo": decision.motivo},
            )
        except TransicionInvalida as e:
            return ResultadoEscalado(False, lead_id, motivo=f"transición inválida: {e}")

        # Registramos una "operación de muestra" en estado PREPARADA. La ejecución
        # física la decide el operador o el AE en Fase 2.
        ahora = datetime.now(timezone.utc).isoformat()
        operacion_id = f"op_muestra_{lead_id}_{int(datetime.now().timestamp())}"
        operacion = {
            "id": operacion_id,
            "lead_id": lead_id,
            "estado": "preparada",
            "creada_en": ahora,
            "decision_compromiso": {
                "senales": decision.senales_detectadas,
                "confianza": decision.confianza,
                "motivo": decision.motivo,
            },
            "respuesta_cliente": respuesta_texto[:2000],
            "siguiente_paso": "Definir productos a enviar (rollicos + cabello de ángel "
                              "por defecto §6.1) y empresa de transporte.",
        }
        self.knowledge.add(self.lead_store.company, TIPO_OPERACION, operacion_id, operacion)

        if self.bus is not None:
            self.bus.publish(Event(
                EventType.APPROVAL_REQUESTED, source="account_executive",
                payload={"lead": lead_id, "operacion": operacion_id,
                         "siguiente_paso": operacion["siguiente_paso"],
                         "confianza": decision.confianza},
                company=self.lead_store.company,
            ))

        return ResultadoEscalado(True, lead_id, operacion_id=operacion_id,
                                 motivo="lead escalado, operación de muestra preparada")

    def listar_operaciones(self, estado: str | None = None) -> list[dict]:
        ops = list(self.knowledge.all(self.lead_store.company, TIPO_OPERACION).values())
        if estado:
            ops = [o for o in ops if o.get("estado") == estado]
        return sorted(ops, key=lambda x: x.get("creada_en", ""), reverse=True)
