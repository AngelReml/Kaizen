# -*- coding: utf-8 -*-
"""Herramientas REALES del cubo Inteligencia para el director plenipotenciario
(Fase 4). Envuelve `departments.inteligencia.cubo_serie_d.CuboInteligencia`,
`departments.inteligencia.agente.InteligenciaDepartment` y
`departments.inteligencia.herramientas` — SIN reimplementar nada, solo
adaptando la firma real al contrato `ToolSpec` (ver panel_mando/herramientas/base.py).

Wireadas:
  LECTURA: patron, tasa_falsos_positivos, correlacionar, reporte_ejecutivo,
    briefing, listar_senales, listar_tendencias — solo lectura, riesgo bajo,
    le dan al director ojos reales sobre su cubo (mercado + alertas).
  REVERSIBLE: detectar (clasifica un valor contra el umbral YA versionado por
    el operador y emite alerta si corresponde — determinista, auditable,
    acotado), resolver_alerta (transiciona una alerta existente segun un
    veredicto cerrado; el metodo real ya guarda contra alerta_id inexistente
    con ValueError, no hace falta guard adicional en el wrapper), observar
    (registra una señal interna de mercado, sin efecto externo).
  IRREVERSIBLE-INTERNA: definir_umbral_alerta — sin esto, `detectar` SIEMPRE
    devolvia None (ningun umbral que romper: no era solo un problema de
    autonomia, era un flujo de negocio incompleto). El propio metodo real
    (CuboInteligencia.definir_umbral) exige `por == "operador"`: es un gate
    de humano que el LLM podria autoafirmar pasando por="operador" en el
    argumento (patron (a) del auditor), asi que el wrapper fuerza `por`
    en SERVIDOR (patron legal.py::_fn_cumplir_obligacion) y solo se dispara
    tras aprobacion humana real via [PROPUESTA] + invocar_aprobada, igual
    que el resto de IRREVERSIBLE-INTERNA de los demas cubos.

NO wireadas (a proposito):
  agregar_p8 — no aparece en el mapa auditado (ni como operacion ni como
    lectura) para este cubo; se deja fuera por prudencia hasta que el
    auditor la revise explicitamente.
"""
from __future__ import annotations

from core.bus import InMemoryBus
from departments.inteligencia import herramientas as h
from departments.inteligencia.agente import InteligenciaDepartment
from departments.inteligencia.cubo_serie_d import CuboInteligencia

from panel_mando.herramientas.base import Argumento, ToolSpec


def _cubo(k, tenant, bitacora) -> CuboInteligencia:
    """Construye el CuboInteligencia real (mismo patron que
    tests/test_d6_d7_marketing_inteligencia.py)."""
    return CuboInteligencia(k, tenant, bitacora=bitacora)


def _dept(k, tenant) -> InteligenciaDepartment:
    """Construye el InteligenciaDepartment real (mismo patron que
    _fn_plan en panel_mando/herramientas/marketing.py)."""
    return InteligenciaDepartment(InMemoryBus(), tenant, knowledge=k)


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_patron(*, k, tenant, bitacora=None, **kwargs) -> dict:
    i = _cubo(k, tenant, bitacora)
    crudo = kwargs.get("valores", "") or ""
    valores = [float(v.strip()) for v in crudo.split(",") if v.strip()]
    return i.patron(kwargs["metrica"], valores)


def _fn_tasa_falsos_positivos(*, k, tenant, bitacora=None, **kwargs) -> dict:
    i = _cubo(k, tenant, bitacora)
    return i.tasa_falsos_positivos()


def _fn_correlacionar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    i = _cubo(k, tenant, bitacora)
    r = i.correlacionar(kwargs["alerta_id"], ventana_horas=kwargs.get("ventana_horas", 48))
    return r if r is not None else {"alerta_id": kwargs["alerta_id"], "correlacion": None}


def _fn_reporte_ejecutivo(*, k, tenant, bitacora=None, **kwargs) -> dict:
    i = _cubo(k, tenant, bitacora)
    return i.reporte_ejecutivo(kwargs["periodo"])


def _fn_briefing(*, k, tenant, bitacora=None, **kwargs) -> dict:
    dept = _dept(k, tenant)
    return dept.briefing()


def _fn_listar_senales(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"senales": h.senales(k, tenant, tipo=kwargs.get("tipo"))}


def _fn_listar_tendencias(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"tendencias": h.detectar_tendencias(k, tenant)}


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def _fn_detectar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    i = _cubo(k, tenant, bitacora)
    r = i.detectar(kwargs["metrica"], kwargs["valor"])
    if r is not None:
        return r
    return {"alerta": None, "metrica": kwargs["metrica"], "valor": kwargs["valor"]}


def _fn_resolver_alerta(*, k, tenant, bitacora=None, **kwargs) -> dict:
    i = _cubo(k, tenant, bitacora)
    return i.resolver_alerta(kwargs["alerta_id"], veredicto=kwargs["veredicto"],
                             por=kwargs["por"])


def _fn_observar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    dept = _dept(k, tenant)
    return dept.observar(tipo=kwargs["tipo"], tema=kwargs["tema"],
                         fuente=kwargs.get("fuente", ""),
                         relevancia=kwargs.get("relevancia", 3),
                         detalle=kwargs.get("detalle", ""))


# ── IRREVERSIBLE-INTERNA (solo via [PROPUESTA] + invocar_aprobada) ─────────

def _fn_definir_umbral_alerta(*, k, tenant, bitacora=None, **kwargs) -> dict:
    """Fuerza el actor en SERVIDOR (patron legal.py::_fn_cumplir_obligacion):
    CuboInteligencia.definir_umbral exige por=='operador' y NUNCA se acepta
    ese valor libre del LLM. Sin esta herramienta wireada, `detectar` no
    tenia forma de alcanzar un umbral real y siempre devolvia None."""
    i = _cubo(k, tenant, bitacora)
    return i.definir_umbral(kwargs["metrica"], kwargs["minimo"], kwargs["maximo"],
                            por="operador")


HERRAMIENTAS: dict[str, ToolSpec] = {
    "patron": ToolSpec(
        nombre="patron", clase="LECTURA",
        descripcion="Media y desviacion estandar de una serie de valores para una "
                    "metrica (determinista: mismos datos, mismo resultado).",
        argumentos=(
            Argumento("metrica", "str", "nombre de la metrica"),
            Argumento("valores", "str",
                     "valores numericos separados por comas, p. ej. '0.1,0.2,0.3'"),
        ),
        fn=_fn_patron),
    "tasa_falsos_positivos": ToolSpec(
        nombre="tasa_falsos_positivos", clase="LECTURA",
        descripcion="Tasa de alertas descartadas sobre el total. Con n<15 es "
                    "INFORMATIVA (R-17); el umbral bloqueante es 0 falsos CRITICA.",
        argumentos=(),
        fn=_fn_tasa_falsos_positivos),
    "correlacionar": ToolSpec(
        nombre="correlacionar", clase="LECTURA",
        descripcion="Busca el evento mas cercano en el tiempo a una alerta dentro de "
                    "una ventana de horas. Documenta correlacion CON confianza, nunca "
                    "causalidad probada.",
        argumentos=(
            Argumento("alerta_id", "str", "id de la alerta"),
            Argumento("ventana_horas", "int", "ventana de busqueda en horas (default 48)",
                     obligatorio=False),
        ),
        fn=_fn_correlacionar),
    "reporte_ejecutivo": ToolSpec(
        nombre="reporte_ejecutivo", clase="LECTURA",
        descripcion="Resumen de alertas del periodo por severidad. Propone, no decide "
                    "(las decisiones son del operador).",
        argumentos=(Argumento("periodo", "str", "periodo del reporte, p. ej. '2026-07'"),),
        fn=_fn_reporte_ejecutivo),
    "briefing": ToolSpec(
        nombre="briefing", clase="LECTURA",
        descripcion="Briefing de mercado: alertas de competencia y tendencias "
                    "detectadas a partir de las señales observadas.",
        argumentos=(),
        fn=_fn_briefing),
    "listar_senales": ToolSpec(
        nombre="listar_senales", clase="LECTURA",
        descripcion="Lista las señales de mercado observadas, opcionalmente filtradas "
                    "por tipo (competidor, precio, tendencia, conversacion, regulatorio).",
        argumentos=(Argumento("tipo", "str", "filtro de tipo de señal", obligatorio=False),),
        fn=_fn_listar_senales),
    "listar_tendencias": ToolSpec(
        nombre="listar_tendencias", clase="LECTURA",
        descripcion="Señales debiles: temas que se repiten en la ventana reciente "
                    "(30 dias) antes de ser obvios.",
        argumentos=(),
        fn=_fn_listar_tendencias),
    "detectar": ToolSpec(
        nombre="detectar", clase="REVERSIBLE",
        descripcion="Clasifica un valor de una metrica contra el umbral YA definido "
                    "por el operador; si esta fuera de rango, emite y guarda una "
                    "alerta (CRITICA/ADVERTENCIA/INFO segun el exceso). Sin umbral "
                    "definido no hay alerta (no genera ruido).",
        argumentos=(
            Argumento("metrica", "str", "nombre de la metrica"),
            Argumento("valor", "float", "valor observado de la metrica"),
        ),
        fn=_fn_detectar),
    "resolver_alerta": ToolSpec(
        nombre="resolver_alerta", clase="REVERSIBLE",
        descripcion="Transiciona una alerta existente a RECONOCIDA, DESCARTADA o "
                    "RESUELTA. Alerta inexistente: error real, no se inventa.",
        argumentos=(
            Argumento("alerta_id", "str", "id de la alerta a resolver"),
            Argumento("veredicto", "str",
                     "uno de: RECONOCIDA, DESCARTADA, RESUELTA"),
            Argumento("por", "str", "quien resuelve la alerta"),
        ),
        fn=_fn_resolver_alerta),
    "observar": ToolSpec(
        nombre="observar", clase="REVERSIBLE",
        descripcion="Registra una señal de mercado observada (competidor, precio, "
                    "tendencia, conversacion, regulatorio). Si es de tipo 'competidor' "
                    "y su relevancia es alta, produce ademas una alerta de competencia.",
        argumentos=(
            Argumento("tipo", "str",
                     "tipo de señal: competidor, precio, tendencia, conversacion, regulatorio"),
            Argumento("tema", "str", "tema de la señal"),
            Argumento("fuente", "str", "fuente de la señal", obligatorio=False),
            Argumento("relevancia", "int", "relevancia de 1 a 5 (default 3)",
                     obligatorio=False),
            Argumento("detalle", "str", "detalle adicional de la señal", obligatorio=False),
        ),
        fn=_fn_observar),
    "definir_umbral_alerta": ToolSpec(
        nombre="definir_umbral_alerta", clase="IRREVERSIBLE-INTERNA",
        descripcion="Define/versiona el umbral [minimo, maximo] de una metrica que "
                    "`detectar` usa para emitir alertas. El 'por' lo fuerza el servidor "
                    "a 'operador' (nunca el LLM); solo se dispara tras aprobacion humana "
                    "real via [PROPUESTA] + invocar_aprobada "
                    "(CuboInteligencia.definir_umbral).",
        argumentos=(
            Argumento("metrica", "str", "nombre de la metrica"),
            Argumento("minimo", "float", "valor minimo del rango aceptable"),
            Argumento("maximo", "float", "valor maximo del rango aceptable"),
        ),
        fn=_fn_definir_umbral_alerta),
}

__all__ = ["HERRAMIENTAS"]
