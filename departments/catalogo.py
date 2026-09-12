"""Catálogo de los diez cubos de una empresa completa (tesis §3, §3.11, §7.1).

Fuente única de qué cubos existen, en qué orden de construcción van (por dependencia de
valor, no por calendario) y cómo se instancian. El Orquestador (core/resiliencia) lee de
aquí qué cubos activar por empresa; el cubo individual no conoce esta lista (§7.1).

Cada fábrica tiene la firma uniforme `(bus, company) -> objeto` y garantiza que el cubo
publica `cube.started` al arrancar, de modo que cualquier combinación encaja en la matriz
de §7.1 y RRHH (§3.9) puede mapear capacidades por introspección del bus.
"""
from __future__ import annotations

from core.bus import MessageBus
from core.events import Event, EventType, Criticality


def _emitir_started(bus: MessageBus, name: str, company: str) -> None:
    bus.publish(Event(EventType.CUBE_STARTED, source=name,
                      payload={"cube": name, "empresa": company},
                      company=company, criticality=Criticality.LOW))


# ── Fábricas por cubo (import perezoso para no acoplar el catálogo a todo) ────
def _comercial(bus, company):
    from departments.comercial.director import DirectorComercial
    d = DirectorComercial(empresa=company)
    _emitir_started(bus, "comercial", company)
    return d

def _brand(bus, company):
    from departments.brand.director import DirectorBrand
    return DirectorBrand(bus, company)           # ya emite cube.started

def _marketing(bus, company):
    from departments.marketing.agente import MarketingDepartment
    return MarketingDepartment(bus, company)     # CuboDepartamento: auto-emite

def _customer_success(bus, company):
    from departments.customer_success.agente import CustomerSuccessDepartment
    return CustomerSuccessDepartment(bus, company)

def _finanzas(bus, company):
    from departments.finanzas.agente import FinanzasDepartment
    d = FinanzasDepartment(bus)
    _emitir_started(bus, "finanzas", company)
    return d

def _legal(bus, company):
    from departments.legal.agente import LegalDepartment
    d = LegalDepartment(bus)
    _emitir_started(bus, "legal", company)
    return d

def _operaciones(bus, company):
    from departments.ops.agente import OpsDepartment
    d = OpsDepartment(bus)
    _emitir_started(bus, "operaciones", company)
    return d

def _inteligencia(bus, company):
    from departments.inteligencia.agente import InteligenciaDepartment
    return InteligenciaDepartment(bus, company)

def _rrhh(bus, company):
    from departments.rrhh.agente import RRHHDepartment
    return RRHHDepartment(bus, company)

def _opengravity(bus, company):
    from core.opengravity.department import OpenGravity
    og = OpenGravity(bus)
    _emitir_started(bus, "opengravity", company)
    return og


# ── El catálogo: orden, nombre, estado y fábrica (tesis §3.11) ────────────────
CATALOGO = [
    {"orden": 1,  "name": "comercial",          "titulo": "Comercial / Ventas",            "estado": "construido", "fabrica": _comercial},
    {"orden": 2,  "name": "brand",              "titulo": "Brand / Identidad",             "estado": "construido", "fabrica": _brand},
    {"orden": 3,  "name": "marketing",          "titulo": "Marketing / Contenido",         "estado": "construido", "fabrica": _marketing},
    {"orden": 4,  "name": "customer_success",   "titulo": "Atención al Cliente / CS",      "estado": "construido", "fabrica": _customer_success},
    {"orden": 5,  "name": "finanzas",           "titulo": "Finanzas",                      "estado": "construido", "fabrica": _finanzas},
    {"orden": 6,  "name": "legal",              "titulo": "Legal",                         "estado": "construido", "fabrica": _legal},
    {"orden": 7,  "name": "operaciones",        "titulo": "Operaciones",                   "estado": "construido", "fabrica": _operaciones},
    {"orden": 8,  "name": "inteligencia_mercado","titulo": "Inteligencia de Mercado",      "estado": "construido", "fabrica": _inteligencia},
    {"orden": 9,  "name": "rrhh",               "titulo": "RRHH / gestión de agentes",     "estado": "construido", "fabrica": _rrhh},
    {"orden": 10, "name": "opengravity",        "titulo": "QA / Verificación (OpenGravity)","estado": "construido", "fabrica": _opengravity},
]

FABRICAS = {c["name"]: c["fabrica"] for c in CATALOGO}
ORDEN_CONSTRUCCION = [c["name"] for c in CATALOGO]

# El cuadrado mínimo viable de una empresa (tesis §3.11).
CUADRADO_MINIMO = ("comercial", "brand", "marketing", "customer_success")


def registrar_en_orquestador(orquestador, *, solo: list[str] | None = None) -> None:
    """Registra las fábricas del catálogo en un Orquestador (core/resiliencia.arranque)."""
    for name, fabrica in FABRICAS.items():
        if solo is None or name in solo:
            orquestador.registrar_fabrica(name, fabrica)


def info() -> list[dict]:
    """Vista del catálogo sin las fábricas (para dashboard/CLI)."""
    return [{k: v for k, v in c.items() if k != "fabrica"} for c in CATALOGO]
