"""Cubo Comercial segun KAIZEN-D01 — bloques C1 (pipeline canonico + Atribuidor),
C2 (cumplimiento como codigo: los 10 controles de §7) y C3 (bucle P8).

Convive con el pipeline real (lifecycle/pipeline_state_machine) sin sustituirlo:
la migracion del historial es reversible y esta mapeada (AUDITORIA_D01 C0.1).
Nada de este modulo envia nada real: el envio es un sobre dry-run que exige
aprobacion, gates deterministas y bitacora (GR-08; las 3 barreras del sandbox
siguen mandando en el canal real).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from core.rue import Sobre, nuevo_id

# ── C1: maquina de estados canonica (D01 §4.1) ───────────────────────────────

ESTADOS = ("COLD", "CONTACTADO", "CONVERSACION", "COMPROMETIDO", "PEDIDO",
           "CUSTOMER", "DORMIDO", "DESCARTADO", "EXCLUIDO")

TRANSICIONES = {
    "COLD":         {"CONTACTADO", "DORMIDO", "DESCARTADO", "CONVERSACION"},  # inbound directo
    "CONTACTADO":   {"CONVERSACION", "DORMIDO"},
    "CONVERSACION": {"COMPROMETIDO", "DORMIDO", "DESCARTADO"},
    "COMPROMETIDO": {"PEDIDO", "CONVERSACION"},
    "PEDIDO":       {"CUSTOMER"},
    "CUSTOMER":     set(),
    "DORMIDO":      {"COLD", "CONVERSACION"},
    "DESCARTADO":   {"COLD"},                      # reversible por operador
    "EXCLUIDO":     set(),                          # absorbente (V1)
}
DISPARADORES = ("SISTEMA", "OPERADOR", "EVIDENCIA", "OPTOUT")

MAPEO_REAL_A_CANON = {   # equivalencia C0.1 (EstadoPipeline M2 → canon)
    "cold": "COLD", "queued": "COLD", "contacting": "CONTACTADO",
    "no_answer": "CONTACTADO", "contacted": "CONTACTADO", "engaged": "CONVERSACION",
    "sample_requested": "COMPROMETIDO", "sample_sent": "COMPROMETIDO",
    "trial": "COMPROMETIDO", "customer": "CUSTOMER", "lost": "DESCARTADO",
    "do_not_call": "EXCLUIDO",
    # legacy EstadoLead
    "identificado": "COLD", "cualificado": "COLD", "enriquecido": "COLD",
    "en_contacto": "CONTACTADO", "compromiso_reciproco": "COMPROMETIDO",
    "muestra_enviada": "COMPROMETIDO", "cliente_activo": "CUSTOMER",
    "en_riesgo": "CUSTOMER", "perdido": "DESCARTADO",
}


class TransicionRechazada(ValueError):
    pass


class GateLegal(RuntimeError):
    """Un control de D01 §7 ha cerrado la puerta. No hay bypass."""


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineCanonico:
    def __init__(self, knowledge, tenant: str, *, bitacora=None, mandato: dict | None = None,
                 bus=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora
        self.mandato = mandato or {}
        # Bus real (core.bus.MessageBus) para el puente hacia otros cubos (p. ej.
        # Customer Success escucha DEPT_TASK_COMPLETED con source="comercial" al
        # cerrarse una venta). Inyectado, igual que researcher.py; None = sin emitir,
        # nunca get_bus() aqui (evitaria escrituras de estado inesperadas en quien
        # construye PipelineCanonico sin pasar bus explicitamente).
        self.bus = bus

    def _emitir(self, tipo: str, payload: dict, correlacion: str = "") -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="comercial.pipeline", correlacion_id=correlacion))

    def lead(self, lead_id: str) -> dict:
        n = self.k.get(self.tenant, "lead_canon", lead_id)
        if n is None:
            raise KeyError(f"lead inexistente: {lead_id}")
        return n

    # C2 control 1: procedencia obligatoria (LIA S1)
    def alta_lead(self, lead: dict) -> dict:
        fuentes = lead.get("fuentes") or []
        if not any(f.get("url") and f.get("fecha") for f in fuentes):
            raise GateLegal("S1: sin procedencia (fuente+fecha) el dato NO entra")
        contacto = lead.get("contacto") or {}
        # C2 control 2: solo contacto que el negocio publica (LIA S2)
        if contacto and not contacto.get("publicado_por_el_negocio"):
            raise GateLegal("S2: contacto no publicado por el negocio → rechazado")
        lead = dict(lead)
        lead.setdefault("estado", "COLD")
        lead.setdefault("contactos_enviados", 0)
        lead["correlacion_id"] = lead.get("correlacion_id") or nuevo_id()
        self.k.add(self.tenant, "lead_canon", lead["id"], lead)
        self._emitir("comercial.lead.descubierto",
                     {"lead_ref": lead["id"], "fuentes": [{"url": f["url"], "fecha": f["fecha"], "tipo": f.get("tipo", "WEB")} for f in fuentes]},
                     lead["correlacion_id"])
        return lead

    def transicionar(self, lead_id: str, a: str, *, disparador: str, causa_ref: str = "") -> dict:
        """V1-V6. Fuera del grafo: RECHAZADA y registrada (V5), jamas silenciosa."""
        assert disparador in DISPARADORES, f"V6: disparador invalido {disparador!r}"
        lead = self.lead(lead_id)
        de = lead["estado"]
        # V1: →EXCLUIDO desde cualquier estado; ante OPTOUT es automatica e inmediata
        permitida = (a == "EXCLUIDO") or (a in TRANSICIONES.get(de, set()))
        if a == "EXCLUIDO" and disparador not in ("OPTOUT", "OPERADOR", "EVIDENCIA"):
            permitida = False                      # V1 cierra, no abre: SISTEMA no excluye por su cuenta
        # V3: COMPROMETIDO exige compromiso vigente
        if a == "COMPROMETIDO" and not causa_ref:
            permitida = False
        # V4: PEDIDO exige atribucion; CUSTOMER exige señal de cobro o confirmacion
        if a == "PEDIDO" and not self.k.get(self.tenant, "pedido_atribuido", causa_ref):
            permitida = False
        if a == "CUSTOMER" and disparador not in ("EVIDENCIA", "OPERADOR"):
            permitida = False
        veredicto = "APLICADA" if permitida else "RECHAZADA"
        self._emitir("comercial.pipeline.transicion",
                     {"lead_ref": lead_id, "de": de, "a": a, "disparador": disparador,
                      "causa_ref": causa_ref, "veredicto": veredicto},
                     lead.get("correlacion_id", ""))
        if not permitida:
            raise TransicionRechazada(f"{de} → {a} ({disparador}) RECHAZADA y registrada (V5)")
        lead["estado"] = a
        if a == "EXCLUIDO":
            lead["do_not_call"] = True
        self.k.add(self.tenant, "lead_canon", lead_id, lead)
        # Puente real hacia Customer Success (departments/customer_success/agente.py
        # ::_on_comercial espera exactamente este source+payload). Una venta cerrada
        # (→CUSTOMER) es el unico disparador; el mecanismo replica el de researcher.py
        # (bus.publish(Event(...))). Un fallo al emitir NUNCA tumba la transicion ya
        # aplicada arriba: el try/except cubre solo esto.
        if a == "CUSTOMER" and self.bus is not None:
            try:
                from core.events import Event, EventType
                valor_mensual = 0.0
                pedido = self.k.get(self.tenant, "pedido_atribuido", causa_ref) if causa_ref else None
                if pedido and pedido.get("importe_bruto") is not None:
                    valor_mensual = pedido["importe_bruto"]
                self.bus.publish(Event(
                    EventType.DEPT_TASK_COMPLETED, source="comercial",
                    payload={"cliente_nuevo": {"nombre": lead.get("nombre", lead_id),
                                                "valor_mensual": valor_mensual}},
                    company=self.tenant))
            except Exception:
                pass
        return lead

    def opt_out(self, lead_id: str, *, evidencia_ref: str = "") -> dict:
        """C2 control 4 (LIA S4): oposicion = EXCLUIDO inmediato + lista de plataforma."""
        lead = self.transicionar(lead_id, "EXCLUIDO", disparador="OPTOUT",
                                 causa_ref=evidencia_ref)
        email = ((self.k.get(self.tenant, "lead_pii", lead_id) or {}).get("email", ""))
        huella = hashlib.sha256((email or lead_id).lower().encode()).hexdigest()
        self.k.add("plataforma", "exclusion", huella,
                   {"huella": huella, "ts": _ts(), "origen_tenant": self.tenant})
        return lead

    def en_lista_exclusion(self, email_o_id: str) -> bool:
        huella = hashlib.sha256(email_o_id.lower().encode()).hexdigest()
        return self.k.get("plataforma", "exclusion", huella) is not None

    # ── envio con gates (C2 controles 3, 4, 5) ──
    def enviar_email(self, lead_id: str, cuerpo: str, *, secuencia: str,
                     aprobacion_ref: str, email_destino: str = "") -> dict:
        lead = self.lead(lead_id)
        if lead["estado"] in ("EXCLUIDO", "DORMIDO"):
            raise GateLegal(f"V2: contacto a lead en {lead['estado']} es imposible")
        if email_destino and self.en_lista_exclusion(email_destino):
            raise GateLegal("S4: destinatario en lista de exclusion de plataforma")
        faltan = bloques_obligatorios_ausentes(cuerpo)
        if faltan:
            raise GateLegal(f"S3: envio imposible sin bloques obligatorios: {faltan}")
        if not aprobacion_ref:
            raise GateLegal("sin aprobacion no hay envio (nivel BAJA)")
        n = int(lead.get("contactos_enviados", 0))
        if secuencia == "INICIAL" and n != 0:
            raise GateLegal("S5: INICIAL solo puede ser el primero")
        if secuencia == "RECORDATORIO" and n != 1:
            raise GateLegal("S5: el tercer contacto NO EXISTE como ruta (1+1 duro)")
        if secuencia not in ("INICIAL", "RECORDATORIO"):
            raise GateLegal(f"secuencia desconocida: {secuencia}")
        lead["contactos_enviados"] = n + 1
        self.k.add(self.tenant, "lead_canon", lead_id, lead)
        caja: list = []
        self._emitir_outbox("comercial.contacto.enviado",
                            {"lead_ref": lead_id, "secuencia": secuencia,
                             "aprobacion_ref": aprobacion_ref}, lead, caja)
        if lead["estado"] == "COLD":
            self.transicionar(lead_id, "CONTACTADO", disparador="SISTEMA",
                              causa_ref=aprobacion_ref)
        return {"dry_run": True, "secuencia": secuencia, "outbox": caja}

    def _emitir_outbox(self, tipo: str, payload: dict, lead: dict, caja: list) -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="comercial.ejecutor",
                                  correlacion_id=lead.get("correlacion_id", "")), outbox=caja)

    # C2 controles 6 y 7 (voz): sin Robinson/disclosure/cuota/horario, no hay llamada
    def llamada_ia(self, lead_id: str, *, robinson_consultado: bool = False,
                   disclosure_test_verde: bool = False, cuota_dia_usada: int = 0) -> dict:
        mandato_max = int(self.mandato.get("max_llamadas_dia", 25))
        if not disclosure_test_verde:
            raise GateLegal("art.50: la palanca de voz NO abre sin test de disclosure en verde")
        if not robinson_consultado:
            raise GateLegal("S6: sin consulta Robinson registrada no hay marcacion")
        if cuota_dia_usada >= mandato_max:
            raise GateLegal(f"cuota de voz agotada ({cuota_dia_usada}/{mandato_max})")
        lead = self.lead(lead_id)
        if lead["estado"] in ("EXCLUIDO", "DORMIDO"):
            raise GateLegal("V2: no se llama a EXCLUIDO/DORMIDO")
        return {"dry_run": True, "permitida": True}


BLOQUES = {"identificacion": re.compile(r"(le escribe|soy|somos)\s", re.I),
           "baja": re.compile(r"(darse de baja|no desea recibir|responda BAJA|baja de esta lista)", re.I),
           "derechos": re.compile(r"(protecci[oó]n de datos|derechos de acceso|RGPD)", re.I)}


def bloques_obligatorios_ausentes(cuerpo: str) -> list[str]:
    """C2 control 3 (LIA S3/S7): comprobacion ESTRUCTURAL, no LLM."""
    return [nombre for nombre, rx in BLOQUES.items() if not rx.search(cuerpo)]


# ── C1: Atribuidor (D01 §4.4) ────────────────────────────────────────────────

class Atribuidor:
    def __init__(self, knowledge, tenant: str, *, bitacora=None, ventana_meses: int = 12) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora
        self.ventana_meses = ventana_meses

    def _cadena(self, correlacion_id: str) -> list[str]:
        evs = sorted(self.k.all(self.tenant, "evento").items())
        return [e["event_id"] for _, e in evs if e.get("correlacion_id") == correlacion_id]

    def atribuir(self, *, pedido_id: str, lead_id: str, via: str,
                 correlacion_id: str = "", fecha_primer_pedido: str = "",
                 importe_bruto: float | None = None) -> dict:
        if self.k.get(self.tenant, "pedido_atribuido", pedido_id):
            raise ValueError(f"doble atribucion prohibida: {pedido_id} ya atribuido")
        estado = "ATRIBUIDO"
        cadena: list[str] = []
        if via == "DIRECTA":
            if self.b is None or not self.b.verificar().get("integra"):
                raise ValueError("DIRECTA exige bitacora integra")
            cadena = self._cadena(correlacion_id)
            if not cadena:
                raise ValueError("DIRECTA sin cadena causal: no hay atribucion")
        elif via == "REPETICION":
            if not fecha_primer_pedido:
                raise ValueError("REPETICION exige primer pedido atribuible previo")
        elif via == "REGISTRO_EXTERNO":
            if self.k.get(self.tenant, "lead_canon", lead_id) is None:
                raise ValueError("REGISTRO_EXTERNO con lead inexistente: rechazado")
            estado = "PENDIENTE_VALIDACION"        # jamas se auto-atribuye (control 10)
        else:
            raise ValueError(f"via desconocida: {via}")
        nodo = {"pedido_id": pedido_id, "lead_ref": lead_id, "via": via, "estado": estado,
                "cadena": cadena, "importe_bruto": importe_bruto, "ts": _ts()}
        self.k.add(self.tenant, "pedido_atribuido", pedido_id, nodo)
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo="comercial.pedido.atribuido",
                                  payload={"pedido_ref": pedido_id, "lead_ref": lead_id,
                                           "via": via, "estado": estado,
                                           "cadena": cadena},
                                  origen="comercial.atribuidor",
                                  correlacion_id=correlacion_id))
        return nodo

    def validar_externo(self, pedido_id: str, *, por: str) -> dict:
        n = self.k.get(self.tenant, "pedido_atribuido", pedido_id)
        if n is None or n["estado"] != "PENDIENTE_VALIDACION":
            raise ValueError("solo se valida un REGISTRO_EXTERNO pendiente")
        if por != "operador":
            raise PermissionError("la validacion externa es humana SIEMPRE (no sube con el nivel)")
        n.update(estado="ATRIBUIDO", validado_por=por)
        self.k.add(self.tenant, "pedido_atribuido", pedido_id, n)
        return n


# ── C3: bucle P8 (D01 §8.2, R-05) ────────────────────────────────────────────

def asiento_p8(knowledge, tenant: str, *, bitacora=None, segmento: str, argumento_id: str,
               canal: str, secuencia: str, resultado: str, t_respuesta_h: float | None = None,
               cliente_ref: str = "") -> dict:
    asiento = {"id": nuevo_id(), "segmento": segmento, "argumento_id": argumento_id,
               "canal": canal, "secuencia": secuencia, "resultado": resultado,
               "t_respuesta_h": t_respuesta_h, "cliente_ref": cliente_ref, "ts": _ts()}
    knowledge.add(tenant, "p8_asiento", asiento["id"], asiento)
    if bitacora is not None:
        bitacora.publicar(Sobre(tenant_id=tenant, tipo="comercial.p8.asiento",
                                payload={k: v for k, v in asiento.items() if k != "cliente_ref"} |
                                        {"cliente_ref": cliente_ref},
                                origen="comercial.p8"))
    return asiento


RESULTADOS_P8 = ("SIN_RESPUESTA", "NEGATIVA", "POSITIVA", "COMPROMISO", "PEDIDO")
_PESOS = {"SIN_RESPUESTA": 0.0, "NEGATIVA": 0.0, "POSITIVA": 1.0, "COMPROMISO": 2.0, "PEDIDO": 4.0}


def ranking_argumentos(knowledge, tenant: str, segmento: str) -> list[dict]:
    """Determinista: puntua argumentos por resultados en el segmento."""
    marcador: dict[str, dict] = {}
    for a in knowledge.all(tenant, "p8_asiento").values():
        if a["segmento"] != segmento:
            continue
        m = marcador.setdefault(a["argumento_id"], {"argumento_id": a["argumento_id"],
                                                    "usos": 0, "puntos": 0.0})
        m["usos"] += 1
        m["puntos"] += _PESOS.get(a["resultado"], 0.0)
    for m in marcador.values():
        m["tasa"] = round(m["puntos"] / m["usos"], 4) if m["usos"] else 0.0
    return sorted(marcador.values(), key=lambda x: (-x["tasa"], -x["usos"], x["argumento_id"]))


def p8_agregado_disociado(knowledge, tenant: str) -> list[dict]:
    """Frontera D00 §9.2: el agregado cross-tenant sale SIN identificadores."""
    out = []
    for a in knowledge.all(tenant, "p8_asiento").values():
        out.append({k: v for k, v in a.items() if k not in ("cliente_ref", "id")})
    return out
