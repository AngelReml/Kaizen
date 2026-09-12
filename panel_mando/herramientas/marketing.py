# -*- coding: utf-8 -*-
"""Herramientas REALES del cubo Marketing para el director plenipotenciario
(Fase 4). Envuelve `departments.marketing.cubo_serie_d.CuboMarketing`,
`departments.marketing.agente.MarketingDepartment` y
`departments.marketing.herramientas` — SIN reimplementar nada, solo
adaptando la firma real al contrato `ToolSpec` (ver panel_mando/herramientas/base.py).

Wireadas:
  LECTURA: roi, plan, piezas, metricas_alcance — solo lectura, riesgo bajo,
    le dan al director ojos reales sobre su cubo.
  REVERSIBLE: crear_campana, crear_contenido, validar_con_brand — escritura
    acotada y auditable; validar_con_brand es ademas el gate Brand real
    (regla de oro D06: sin VALIDADO_POR_BRAND no hay lanzamiento).
  IRREVERSIBLE-INTERNA: lanzar (SIEMPRE dry-run — cambio de estado interno,
    NO hay envio real a ningun canal, GR-08), registrar_metrica (reporting,
    impacto bajo). Ambas se PROPONEN via [PROPUESTA] y solo se disparan de
    verdad tras aprobacion humana (invocar_aprobada) — nunca desde un turno
    de chat directo.

    lanzar en concreto SOLO se alcanza aqui despues de que invocar_aprobada
    ya certifico la aprobacion humana de la tarjeta [PROPUESTA] real. Por eso,
    si la campaña sigue en BORRADOR (el estado que deja crear_campana), el
    wrapper fuerza en SERVIDOR `m.aprobar_campana(c_id, por="operador")`
    justo antes de `m.lanzar(...)` — la aprobacion humana YA ocurrio, solo
    faltaba reflejarla en el estado de CuboMarketing (patron "servidor fuerza
    el actor" de legal.py::_fn_cumplir_obligacion). Para cualquier OTRO
    estado (PAUSADA, CANCELADA, COMPLETADA, ya ACTIVA...) NO se fuerza nada:
    lanzar() lanza su propio GateMarketing tal cual, para no reabrir/relanzar
    una campaña que no deberia.

NO wireadas (a proposito):
  aprobar_campana — sigue sin existir como herramienta INDEPENDIENTE: el
    propio metodo exige `por == "operador"`, un gate de humano que el
    llamador podria autoafirmar pasando por="operador" en el argumento
    (patron (a) del auditor); el director no puede autoautorizarse. El UNICO
    camino que lo dispara es el forzado interno de `lanzar` arriba, nunca una
    invocacion directa.
  pausar — atestigua una decision de pausa manual "explicita e incondicional"
    que en el flujo real la dispara el operador (`por` describe quien pide la
    pausa, no una verificacion que el director pueda hacer por si mismo);
    fuera de esto no hay ningun endpoint que la exponga como accion del
    director en el mapa auditado, así que se deja fuera por prudencia.
  reconciliar_gasto — es dinero/gasto de campaña sin gate de evidencia real
    (nadie exige prueba del gasto reportado antes de sumarlo): patron (c).
"""
from __future__ import annotations

from core.bus import InMemoryBus
from core import verificacion as V
from departments.marketing import herramientas as h
from departments.marketing.agente import MarketingDepartment
from departments.marketing.cubo_serie_d import CuboMarketing

from panel_mando.herramientas.base import Argumento, ToolSpec


def _cubo(k, tenant, bitacora) -> CuboMarketing:
    """Construye el CuboMarketing real (mismo patron que
    tests/test_d6_d7_marketing_inteligencia.py). El servicio de verificacion
    se construye siempre — barato, y sin el `validar_con_brand` no podria
    validar nada (regla de oro)."""
    return CuboMarketing(k, tenant, bitacora=bitacora,
                         servicio_verificacion=V.ServicioVerificacion(k))


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_roi(*, k, tenant, bitacora=None, **kwargs) -> dict:
    m = _cubo(k, tenant, bitacora)
    return m.roi(kwargs["c_id"])


def _fn_plan(*, k, tenant, bitacora=None, **kwargs) -> dict:
    dept = MarketingDepartment(InMemoryBus(), tenant, knowledge=k)
    return {"plan": dept.plan(n=kwargs.get("n", 5))}


def _fn_piezas(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"piezas": h.piezas(k, tenant, estado=kwargs.get("estado"))}


def _fn_metricas_alcance(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return h.metricas_alcance(k, tenant)


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def _fn_crear_campana(*, k, tenant, bitacora=None, **kwargs) -> dict:
    m = _cubo(k, tenant, bitacora)
    lista_canales = [c.strip() for c in kwargs["canales"].split(",") if c.strip()]
    return m.crear_campana(nombre=kwargs["nombre"], segmento=kwargs["segmento"],
                           canales=lista_canales, presupuesto_eur=kwargs["presupuesto_eur"],
                           duracion_dias=kwargs["duracion_dias"])


def _fn_crear_contenido(*, k, tenant, bitacora=None, **kwargs) -> dict:
    m = _cubo(k, tenant, bitacora)
    return m.crear_contenido(kwargs["c_id"], tipo=kwargs["tipo"], texto=kwargs["texto"])


def _fn_validar_con_brand(*, k, tenant, bitacora=None, **kwargs) -> dict:
    m = _cubo(k, tenant, bitacora)
    return m.validar_con_brand(kwargs["cont_id"])


# ── IRREVERSIBLE-INTERNA (solo via [PROPUESTA] + invocar_aprobada) ─────────

def _fn_lanzar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    """Fuerza el actor en SERVIDOR (patron legal.py::_fn_cumplir_obligacion):
    invocar_aprobada() solo llega aqui tras aprobacion humana real de la
    tarjeta [PROPUESTA] de lanzar. Si la campaña sigue en BORRADOR (estado
    inicial de crear_campana), esa aprobacion humana YA ocurrio pero nunca
    paso por CuboMarketing.aprobar_campana — se fuerza aqui con por="operador"
    (NUNCA un valor libre del LLM) antes de lanzar. Para cualquier otro
    estado no se toca nada: lanzar() decide con su propio GateMarketing."""
    m = _cubo(k, tenant, bitacora)
    c_id = kwargs["c_id"]
    campana = k.get(tenant, "campana", c_id)
    if campana is not None and campana.get("estado") == "BORRADOR":
        m.aprobar_campana(c_id, por="operador")
    return m.lanzar(c_id, kwargs["cont_id"])


def _fn_registrar_metrica(*, k, tenant, bitacora=None, **kwargs) -> dict:
    m = _cubo(k, tenant, bitacora)
    return m.registrar_metrica(kwargs["c_id"], fecha=kwargs["fecha"],
                               impresiones=kwargs["impresiones"], clicks=kwargs["clicks"],
                               coste_eur=kwargs["coste_eur"])


HERRAMIENTAS: dict[str, ToolSpec] = {
    "roi": ToolSpec(
        nombre="roi", clase="LECTURA",
        descripcion="ROI verificable de una campaña: leads generados y conversiones "
                    "reales via lead.fuentes tipo CAMPANA -> pedido_atribuido (R-15).",
        argumentos=(Argumento("c_id", "str", "id de la campaña"),),
        fn=_fn_roi),
    "plan": ToolSpec(
        nombre="plan", clase="LECTURA",
        descripcion="Plan editorial heuristico (ideas de contenido a partir del "
                    "posicionamiento de Brand y las objeciones reales de Comercial).",
        argumentos=(Argumento("n", "int", "numero de ideas a generar", obligatorio=False),),
        fn=_fn_plan),
    "piezas": ToolSpec(
        nombre="piezas", clase="LECTURA",
        descripcion="Lista las piezas de contenido publicadas/planificadas, "
                    "opcionalmente filtradas por estado.",
        argumentos=(Argumento("estado", "str", "filtro de estado (p. ej. 'publicada')",
                              obligatorio=False),),
        fn=_fn_piezas),
    "metricas_alcance": ToolSpec(
        nombre="metricas_alcance", clase="LECTURA",
        descripcion="Metricas agregadas de alcance: piezas publicadas, leads inbound, "
                    "distribucion por canal y tasa de conversion pieza->lead.",
        argumentos=(),
        fn=_fn_metricas_alcance),
    "crear_campana": ToolSpec(
        nombre="crear_campana", clase="REVERSIBLE",
        descripcion="Crea una campaña nueva en estado BORRADOR (aun no lanzable: "
                    "requiere aprobacion del operador y contenido VALIDADO_POR_BRAND).",
        argumentos=(
            Argumento("nombre", "str", "nombre de la campaña"),
            Argumento("segmento", "str", "segmento objetivo"),
            Argumento("canales", "str", "canales separados por comas, p. ej. 'email,blog'"),
            Argumento("presupuesto_eur", "float", "presupuesto total en euros"),
            Argumento("duracion_dias", "int", "duracion de la campaña en dias"),
        ),
        fn=_fn_crear_campana),
    "crear_contenido": ToolSpec(
        nombre="crear_contenido", clase="REVERSIBLE",
        descripcion="Crea una pieza de contenido en estado GENERADO, asociada a una "
                    "campaña existente. Debe pasar por validar_con_brand antes de poder "
                    "lanzarse (regla de oro: sin VALIDADO_POR_BRAND no avanza).",
        argumentos=(
            Argumento("c_id", "str", "id de la campaña a la que se asocia el contenido"),
            Argumento("tipo", "str", "tipo de contenido, p. ej. 'COPY'"),
            Argumento("texto", "str", "texto del contenido"),
        ),
        fn=_fn_crear_contenido),
    "validar_con_brand": ToolSpec(
        nombre="validar_con_brand", clase="REVERSIBLE",
        descripcion="Pasa un contenido por el gate bloqueante de Brand (servicio de "
                    "verificacion del sustrato). Deja el contenido en VALIDADO_POR_BRAND "
                    "o RECHAZADO segun el veredicto real.",
        argumentos=(Argumento("cont_id", "str", "id del contenido a validar"),),
        fn=_fn_validar_con_brand),
    "lanzar": ToolSpec(
        nombre="lanzar", clase="IRREVERSIBLE-INTERNA",
        descripcion="Lanza una campaña con un contenido ya VALIDADO_POR_BRAND. SIEMPRE "
                    "dry-run hoy (GR-08): es un cambio de estado interno (campaña -> "
                    "ACTIVA, contenido -> LANZADO), NO un envio real a ningun canal "
                    "externo. Bloqueado por el kill-switch del 90% del presupuesto (R-10). "
                    "Si la campaña esta en BORRADOR, el servidor aprueba primero en su "
                    "nombre (por='operador', nunca del LLM): la aprobacion humana ya "
                    "ocurrio para llegar a invocar_aprobada().",
        argumentos=(
            Argumento("c_id", "str", "id de la campaña"),
            Argumento("cont_id", "str", "id del contenido VALIDADO_POR_BRAND"),
        ),
        fn=_fn_lanzar),
    "registrar_metrica": ToolSpec(
        nombre="registrar_metrica", clase="IRREVERSIBLE-INTERNA",
        descripcion="Registra una medicion diaria de una campaña (impresiones, clicks, "
                    "coste). Impacto bajo: es reporting, no mueve dinero ni gasto real.",
        argumentos=(
            Argumento("c_id", "str", "id de la campaña"),
            Argumento("fecha", "str", "fecha de la medicion, formato ISO"),
            Argumento("impresiones", "int", "impresiones del dia"),
            Argumento("clicks", "int", "clicks del dia"),
            Argumento("coste_eur", "float", "coste del dia en euros"),
        ),
        fn=_fn_registrar_metrica),
}

__all__ = ["HERRAMIENTAS"]
