# -*- coding: utf-8 -*-
"""Herramientas REALES del director de Legal (Fase 4 — plenipotenciarios).

El manifest de Legal dictamina riesgos Y CUMPLIMIENTO: este cubo absorbe
tambien el cubo Cumplimiento (departments/cumplimiento/cubo_serie_d.py).
Cada ToolSpec envuelve una operacion REAL verificada contra el codigo:
  - departments/legal/agente.py, departments/legal/herramientas.py
  - departments/cumplimiento/cubo_serie_d.py (CuboCumplimiento)
Ninguna funcion aqui atrapa excepciones salvo para traducir un objeto no
serializable a dict — si algo falla, la excepcion sube y la capa de
invocacion la reporta.

Fuera de alcance de este fichero (el mapa de capacidades mezclaba legal con
qa/rrhh): las entradas cuya firma empieza por departments.qa. o
departments.rrhh. NO se tocan aqui — pertenecen a otros cubos.

Deliberadamente NO wireadas de departments.cumplimiento.cubo_serie_d:
  - aportar_evidencia y auditar: no aparecen en el mapa de capacidades
    auditado (ni en 'operaciones' ni en 'lecturas') — no se wirean sin
    auditoria explicita, aunque el metodo exista en el codigo real.
  - barrer_plazos no expone `ahora` (datetime, no aplanable a
    str/int/float/bool): se llama siempre con `ahora=None` (usa el reloj
    real), que es el uso normal del metodo.

Guardas anadidas (no estan en el metodo real, evitan un AttributeError/
TypeError feo cuando el id no existe — no ocultan fallos, solo dan un
ValueError legible ANTES de la llamada real; ver auditoria de 'asignar'):
  - asignar_obligacion, cumplir_obligacion, validar_expediente: comprueban
    que la obligacion existe.
  - verificar_evidencia: comprueba que la evidencia existe.

`cumplir_obligacion` pasa siempre `por=tenant` (el agente autenticado real),
NUNCA un valor libre que el LLM pudiera inventar (ver riesgos del auditor)."""
from __future__ import annotations

from core.bus import InMemoryBus
from departments.base import Task
from departments.cumplimiento.cubo_serie_d import CuboCumplimiento
from departments.legal import herramientas as h
from departments.legal.agente import LegalDepartment

from panel_mando.herramientas.base import Argumento, ToolSpec


def _requiere_obligacion(k, tenant: str, ob_id: str) -> None:
    if k.get(tenant, "obligacion", ob_id) is None:
        raise ValueError(f"obligacion {ob_id!r} no existe para el tenant {tenant!r}")


def _requiere_evidencia(k, tenant: str, ev_id: str) -> None:
    if k.get(tenant, "evidencia", ev_id) is None:
        raise ValueError(f"evidencia {ev_id!r} no existe para el tenant {tenant!r}")


# ── LECTURA: legal ───────────────────────────────────────────────────────

def _fn_handle(*, k, tenant, bitacora=None, contrato: str = "", clausula: str = "",
              texto: str = "", intent: str = "analiza", **kw) -> dict:
    dept = LegalDepartment(InMemoryBus(), knowledge=k)
    payload: dict = {}
    if contrato:
        payload["contrato"] = contrato
    if clausula:
        payload["clausula"] = clausula
    if texto:
        payload["texto"] = texto
    task = Task(intent=intent, payload=payload, company=tenant)
    result = dept.handle(task)
    return {"ok": result.ok, "summary": result.summary, "data": result.data}


def _fn_consultar_clausula_problematica(*, k, tenant, bitacora=None, texto: str, **kw) -> dict:
    return h.consultar_clausula_problematica(texto)


def _fn_analizar_contrato(*, k, tenant, bitacora=None, texto: str, **kw) -> dict:
    return h.analizar_contrato(texto)


def _fn_comparar_con_plantilla(*, k, tenant, bitacora=None, contrato: str, requeridos: str,
                               **kw) -> dict:
    lista_requeridos = [r.strip() for r in requeridos.split(",") if r.strip()]
    return h.comparar_con_plantilla(contrato, lista_requeridos)


# ── LECTURA: cumplimiento ────────────────────────────────────────────────

def _fn_verificar_evidencia(*, k, tenant, bitacora=None, ev_id: str,
                            contenido_actual_texto: str, **kw) -> dict:
    _requiere_evidencia(k, tenant, ev_id)
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return c.verificar_evidencia(ev_id, contenido_actual_texto.encode("utf-8"))


def _fn_validar_expediente(*, k, tenant, bitacora=None, ob_id: str, **kw) -> dict:
    _requiere_obligacion(k, tenant, ob_id)
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return c.validar_expediente(ob_id)


def _fn_compilar_defensa(*, k, tenant, bitacora=None, **kw) -> dict:
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return c.compilar_defensa()


def _fn_listar_obligaciones(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"obligaciones": k.all(tenant, "obligacion")}


def _fn_listar_evidencias(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"evidencias": k.all(tenant, "evidencia")}


def _fn_listar_auditorias(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"auditorias": k.all(tenant, "auditoria_cumplimiento")}


def _fn_verificar_cadena_bitacora(*, k, tenant, bitacora=None, **kw) -> dict:
    if bitacora is None:
        raise ValueError(f"no hay bitacora activa para el tenant {tenant!r}")
    return bitacora.verificar()


# ── REVERSIBLE: cumplimiento ─────────────────────────────────────────────

def _fn_registrar_obligacion(*, k, tenant, bitacora=None, nombre: str, tipo: str,
                             fecha_limite: str, area: str, fuente_validada_por: str = "",
                             **kw) -> dict:
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return c.registrar(nombre=nombre, tipo=tipo, fecha_limite=fecha_limite, area=area,
                       fuente_validada_por=fuente_validada_por)


def _fn_asignar_obligacion(*, k, tenant, bitacora=None, ob_id: str, responsable: str,
                           **kw) -> dict:
    _requiere_obligacion(k, tenant, ob_id)
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return c.asignar(ob_id, responsable)


# ── IRREVERSIBLE-INTERNA: cumplimiento ───────────────────────────────────

def _fn_cumplir_obligacion(*, k, tenant, bitacora=None, ob_id: str, **kw) -> dict:
    _requiere_obligacion(k, tenant, ob_id)
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return c.cumplir(ob_id, por=tenant)


def _fn_barrer_plazos(*, k, tenant, bitacora=None, **kw) -> dict:
    c = CuboCumplimiento(k, tenant, bitacora=bitacora)
    return {"avisos": c.barrer_plazos()}


HERRAMIENTAS: dict[str, ToolSpec] = {
    "handle": ToolSpec(
        nombre="handle", clase="LECTURA",
        descripcion="Ejecuta el flujo real del departamento Legal (LegalDepartment.handle) "
                    "sobre un contrato/clausula/texto; emite el ciclo de vida al bus y "
                    "devuelve ok/summary/data.",
        argumentos=(
            Argumento("contrato", "str", "texto completo del contrato", obligatorio=False),
            Argumento("clausula", "str", "texto de una unica clausula (sin 'contrato')",
                     obligatorio=False),
            Argumento("texto", "str", "texto generico si no aplica contrato/clausula",
                     obligatorio=False),
            Argumento("intent", "str", "intent de la tarea (informativo)", obligatorio=False),
        ),
        fn=_fn_handle),
    "consultar_clausula_problematica": ToolSpec(
        nombre="consultar_clausula_problematica", clase="LECTURA",
        descripcion="Comprueba si un texto de clausula contiene un patron problematico "
                    "conocido en la base curada. Devuelve {es_problematica, motivo, "
                    "gravedad, referencia}.",
        argumentos=(Argumento("texto", "str", "texto de la clausula a comprobar"),),
        fn=_fn_consultar_clausula_problematica),
    "analizar_contrato": ToolSpec(
        nombre="analizar_contrato", clase="LECTURA",
        descripcion="Trocea el texto en clausulas y evalua cada una contra la base curada. "
                    "Devuelve {clausulas[], riesgos[], puntos_atencion[]}.",
        argumentos=(Argumento("texto", "str", "texto completo del contrato"),),
        fn=_fn_analizar_contrato),
    "comparar_con_plantilla": ToolSpec(
        nombre="comparar_con_plantilla", clase="LECTURA",
        descripcion="Detecta que clausulas requeridas por la plantilla faltan en el "
                    "contrato. Devuelve {diferencias[], coincide}.",
        argumentos=(
            Argumento("contrato", "str", "texto del contrato"),
            Argumento("requeridos", "str",
                     "clausulas requeridas separadas por comas, p. ej. 'objeto,duracion'"),
        ),
        fn=_fn_comparar_con_plantilla),

    "verificar_evidencia": ToolSpec(
        nombre="verificar_evidencia", clase="LECTURA",
        descripcion="Verifica la integridad de una evidencia por hash sha256: compara el "
                    "hash guardado contra el del contenido actual (edicion posterior = "
                    "CORRUPTA). El contenido se pasa como texto y se codifica UTF-8 antes "
                    "de comparar (CuboCumplimiento.verificar_evidencia).",
        argumentos=(
            Argumento("ev_id", "str", "id de la evidencia"),
            Argumento("contenido_actual_texto", "str",
                     "contenido actual a verificar, como texto (se codifica UTF-8)"),
        ),
        fn=_fn_verificar_evidencia),
    "validar_expediente": ToolSpec(
        nombre="validar_expediente", clase="LECTURA",
        descripcion="Checklist de completitud de una obligacion (fecha_limite, responsable, "
                    "evidencias, cumplida_en). Devuelve {checklist, veredicto: COMPLETO|"
                    "INCOMPLETO} (CuboCumplimiento.validar_expediente).",
        argumentos=(Argumento("ob_id", "str", "id de la obligacion"),),
        fn=_fn_validar_expediente),
    "compilar_defensa": ToolSpec(
        nombre="compilar_defensa", clase="LECTURA",
        descripcion="Compila el expediente de defensa documental: manifest integro con "
                    "hashes de todas las evidencias de todas las obligaciones "
                    "(CuboCumplimiento.compilar_defensa).",
        argumentos=(), fn=_fn_compilar_defensa),
    "listar_obligaciones": ToolSpec(
        nombre="listar_obligaciones", clase="LECTURA",
        descripcion="Lista todas las obligaciones registradas del tenant (cubo.k.all(tenant, "
                    "'obligacion')).",
        argumentos=(), fn=_fn_listar_obligaciones),
    "listar_evidencias": ToolSpec(
        nombre="listar_evidencias", clase="LECTURA",
        descripcion="Lista todas las evidencias registradas del tenant (cubo.k.all(tenant, "
                    "'evidencia')).",
        argumentos=(), fn=_fn_listar_evidencias),
    "listar_auditorias": ToolSpec(
        nombre="listar_auditorias", clase="LECTURA",
        descripcion="Lista todas las actas de auditoria de cumplimiento del tenant "
                    "(cubo.k.all(tenant, 'auditoria_cumplimiento')).",
        argumentos=(), fn=_fn_listar_auditorias),
    "verificar_cadena_bitacora": ToolSpec(
        nombre="verificar_cadena_bitacora", clase="LECTURA",
        descripcion="Recomputa la cadena de hashes de la bitacora del tenant y nombra el "
                    "punto exacto de ruptura si no esta integra (Bitacora.verificar).",
        argumentos=(), fn=_fn_verificar_cadena_bitacora),

    "registrar_obligacion": ToolSpec(
        nombre="registrar_obligacion", clase="REVERSIBLE",
        descripcion="Registra una nueva obligacion de cumplimiento (estado REGISTRADA). Las "
                    "obligaciones REGULATORIA exigen 'fuente_validada_por' no vacio (GL-05): "
                    "sin gestoria detras, una fecha legal no entra "
                    "(CuboCumplimiento.registrar).",
        argumentos=(
            Argumento("nombre", "str", "nombre de la obligacion"),
            Argumento("tipo", "str", "REGULATORIA | CONTRACTUAL | INTERNA"),
            Argumento("fecha_limite", "str", "fecha limite ISO8601"),
            Argumento("area", "str", "area responsable"),
            Argumento("fuente_validada_por", "str",
                     "gestoria/fuente que valido la fecha (obligatorio si tipo=REGULATORIA)",
                     obligatorio=False),
        ),
        fn=_fn_registrar_obligacion),
    "asignar_obligacion": ToolSpec(
        nombre="asignar_obligacion", clase="REVERSIBLE",
        descripcion="Asigna un responsable a una obligacion ya registrada (estado ASIGNADA). "
                    "Bajo riesgo, reversible (CuboCumplimiento.asignar).",
        argumentos=(
            Argumento("ob_id", "str", "id de la obligacion"),
            Argumento("responsable", "str", "responsable asignado"),
        ),
        fn=_fn_asignar_obligacion),

    "cumplir_obligacion": ToolSpec(
        nombre="cumplir_obligacion", clase="IRREVERSIBLE-INTERNA",
        descripcion="Marca una obligacion como CUMPLIDA. Exige evidencia previa aportada "
                    "(regla de oro: sin evidencia no hay cumplimiento documentado). El "
                    "'por' es siempre el tenant autenticado, nunca un valor libre "
                    "(CuboCumplimiento.cumplir).",
        argumentos=(Argumento("ob_id", "str", "id de la obligacion"),),
        fn=_fn_cumplir_obligacion),
    "barrer_plazos": ToolSpec(
        nombre="barrer_plazos", clase="IRREVERSIBLE-INTERNA",
        descripcion="Barre todas las obligaciones vivas del tenant: emite alertas 30/7/1 "
                    "dias y marca INCUMPLIDA por timeout (gate determinista, siempre con "
                    "el reloj real). Es el trabajo normal del director vigilar plazos "
                    "(CuboCumplimiento.barrer_plazos).",
        argumentos=(), fn=_fn_barrer_plazos),
}

__all__ = ["HERRAMIENTAS"]
