"""SDR Multicanal — orquestador de Fase 1.

`preparar(limite)`: toma los N leads top del Priorizador, compone con `EmailComposer`,
revisa con el Brand Guardian y **encola** los mensajes en la `ColaAprobacion`. NO envía.

`enviar(lista_pendientes | "todos_aprobados")`: solo procesa los aprobados; el
`EmailChannel` aplica las tres barreras del guard (flag global + token + hash) antes de
hacer SMTP. Si el envío es exitoso, transiciona el lead a `EN_CONTACTO` y registra.

Fase 1 sólo activa el canal email. Voz y WhatsApp quedan apagados por flag (ver
sdr/canales/voz.py y whatsapp.py).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from core.events import Event, EventType
from departments.comercial.cola_aprobacion import (
    ColaAprobacion, EnvioSinAprobacion,
)
from departments.comercial.email_composer import EmailComposer
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.priorizador import Priorizador
from departments.comercial.sdr.canales.base import Canal, CanalDeshabilitado, ResultadoContacto
from departments.comercial.sdr.canales.email import EmailChannel


@dataclass
class ResultadoPreparacion:
    campaign_id: str
    preparados: int = 0
    sin_destino: int = 0
    pendientes_ids: list[str] = field(default_factory=list)
    fallos: list[str] = field(default_factory=list)


@dataclass
class ResultadoEnvio:
    enviados: int = 0
    bloqueados_sin_aprobacion: int = 0
    canal_deshabilitado: int = 0
    fallos_smtp: int = 0
    detalle: list[dict] = field(default_factory=list)


class SDRMulticanal:
    def __init__(self, *, lead_store: LeadStore, cola: ColaAprobacion,
                 composer: EmailComposer | None = None,
                 canales: dict[str, Canal] | None = None,
                 bus=None) -> None:
        self.lead_store = lead_store
        self.cola = cola
        self.composer = composer or EmailComposer(empresa=lead_store.company)
        self.canales: dict[str, Canal] = canales or {"email": EmailChannel()}
        self.bus = bus

    # ── Preparación: componer y encolar (NUNCA envía) ───────────────────────
    def preparar(self, *, limite: int = 10, canal: str = "email",
                 prioridades: tuple[str, ...] | None = None,
                 lead_id: str | None = None,
                 verbose: bool = True) -> ResultadoPreparacion:
        if canal != "email":
            raise NotImplementedError(
                f"Canal '{canal}' no activo en Fase 1. Email es el único habilitado."
            )
        campaign_id = f"camp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        res = ResultadoPreparacion(campaign_id=campaign_id)

        # Selección de leads.
        if lead_id:
            lead = self.lead_store.get(lead_id)
            if lead is None:
                res.fallos.append(f"Lead '{lead_id}' no existe.")
                return res
            leads = [lead]
        else:
            ya_preparados = {p["lead_id"] for p in self.cola.listar()
                             if p["estado"] in ("pendiente", "aprobado", "enviado")}
            leads = Priorizador(self.lead_store).cola(
                limite=limite, prioridades=prioridades, excluir_lead_ids=ya_preparados,
            )

        if verbose:
            print(f"[SDR] campaña {campaign_id}: preparando {len(leads)} mensaje(s)")

        for lead in leads:
            destino = self._destino_email(lead)
            if not destino:
                res.sin_destino += 1
                continue
            try:
                borrador = self.composer.componer(lead)
            except Exception as e:
                res.fallos.append(f"{lead.get('nombre','')}: composer falló: {e}")
                continue
            pendiente = self.cola.encolar(
                lead_id=lead["id"], canal="email", destino=destino,
                asunto=borrador.asunto, cuerpo=borrador.cuerpo,
                brand_review=asdict(borrador.review),
                campaign_id=campaign_id,
                razones_personalizacion=borrador.razones_de_personalizacion,
                intentos_composer=borrador.intentos,
            )
            res.preparados += 1
            res.pendientes_ids.append(pendiente.id)
            if self.bus is not None:
                self.bus.publish(Event(
                    EventType.DEPT_TASK_COMPLETED, source="sdr",
                    payload={"accion": "preparado", "lead": lead["id"],
                             "pendiente": pendiente.id, "brand_ok": borrador.aprobado_por_brand},
                    company=self.lead_store.company,
                ))

        if verbose:
            print(f"[SDR] campaña {campaign_id}: {res.preparados} encolados · "
                  f"{res.sin_destino} sin destino · {len(res.fallos)} fallos")
        return res

    # ── Envío: solo aprobados; el canal aplica el guard ─────────────────────
    def enviar(self, *, pendientes_ids: list[str] | None = None,
               canal: str = "email", verbose: bool = True) -> ResultadoEnvio:
        canal_obj = self.canales[canal]
        if pendientes_ids is None:
            pendientes_ids = [p["id"] for p in self.cola.listar(estado="aprobado")]
        res = ResultadoEnvio()

        for pid in pendientes_ids:
            try:
                if not isinstance(canal_obj, EmailChannel):
                    raise NotImplementedError("Solo email implementado para enviar() en Fase 1.")
                resultado: ResultadoContacto = canal_obj.enviar_pendiente(self.cola, pid)
            except EnvioSinAprobacion as e:
                res.bloqueados_sin_aprobacion += 1
                res.detalle.append({"pendiente": pid, "estado": "bloqueado", "motivo": str(e)})
                if verbose:
                    print(f"[SDR] {pid}: BLOQUEADO — {e}")
                continue
            except CanalDeshabilitado as e:
                res.canal_deshabilitado += 1
                res.detalle.append({"pendiente": pid, "estado": "canal_off", "motivo": str(e)})
                continue
            except Exception as e:
                res.fallos_smtp += 1
                res.detalle.append({"pendiente": pid, "estado": "fallo", "motivo": str(e)})
                continue

            if resultado.estado == "enviado":
                res.enviados += 1
                nodo = self.cola.get(pid)
                # Transición del lead: ENRIQUECIDO → EN_CONTACTO.
                try:
                    self.lead_store.transicionar(
                        nodo["lead_id"], EstadoLead.EN_CONTACTO,
                        razon=f"Email enviado via {canal}",
                        detalle={"pendiente_id": pid, "destino": resultado.destino},
                    )
                except Exception:
                    pass    # ya estaba en EN_CONTACTO o más allá
                if self.bus is not None:
                    self.bus.publish(Event(
                        EventType.DEPT_TASK_COMPLETED, source="sdr",
                        payload={"accion": "enviado", "lead": nodo["lead_id"],
                                 "destino": resultado.destino, "pendiente": pid},
                        company=self.lead_store.company,
                    ))
                res.detalle.append({"pendiente": pid, "estado": "enviado",
                                    "destino": resultado.destino})
            else:
                res.fallos_smtp += 1
                res.detalle.append({"pendiente": pid, "estado": "fallo",
                                    "motivo": resultado.detalle})

        if verbose:
            print(f"[SDR] envío: {res.enviados} enviados · "
                  f"{res.bloqueados_sin_aprobacion} bloqueados · "
                  f"{res.canal_deshabilitado} canal_off · "
                  f"{res.fallos_smtp} fallos")
        return res

    # ── Helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _destino_email(lead: dict) -> str | None:
        """Lee el email del lead. En Fase 0 el Enrichment NO obtuvo email del decisor
        (eso requiere LLM sobre web del lead — Fase 1.5). De momento, si la ficha lleva
        un email en `contacto.email`, lo usamos; si no, devolvemos None y se cuenta como
        sin_destino. La obtención de email es follow-up del Enrichment."""
        contacto = lead.get("contacto") or {}
        return contacto.get("email")
