# -*- coding: utf-8 -*-
"""Herramientas REALES del director de QA (Fase 4 — plenipotenciarios).

Cada ToolSpec envuelve una operacion REAL verificada contra el codigo del
departamento (departments/qa/agente.py, departments/qa/herramientas.py).
Ninguna funcion aqui atrapa excepciones salvo para traducir un objeto no
serializable a dict — si algo falla, la excepcion sube y la capa de
invocacion la reporta.

Wireadas (todas LECTURA, 100% deterministas, sin LLM):
  - handle: ejecuta el flujo real del departamento (QADepartment.handle),
    que en la practica delega en validar_borrador cuando el payload trae
    asunto/cuerpo.
  - validar_borrador: aplica todas las reglas de QA a un borrador.
  - detectar_contradicciones: heuristica de choque texto vs contexto.
  - comparar_con_plantilla: comprueba elementos requeridos en un texto.
  - calificar_calidad (pase de excelencia): pipeline REAL de especialistas
    (departments/qa/agente.py::QADepartment con usar_pipeline=True —
    ValidadorDeEstructura, DetectorDeContradicciones, CalificadorDeCalidad,
    ver departments/qa/especialistas.py) que puntua 0-10 con desglose y
    recomendaciones. Investigado antes de activarlo: ninguno de los tres
    especialistas llama a self._chat/self._get_llm ni a claude_client — son
    deterministas, cero coste oculto de LLM (ver docstring de QADepartment).
    Se le pasa 'artefacto' (no 'asunto'/'cuerpo') porque QADepartment.run()
    bifurca por esa clave exacta: con 'artefacto' usa el pipeline, sin ella
    usa las reglas duras legacy — asi 'handle'/'validar_borrador' siguen
    funcionando exactamente igual que antes.
  - historial_validaciones (pase de excelencia): lee el historial YA
    persistido por core/subscriptors/qa_validador.py (nodos tipo
    "validacion" en el knowledge store, uno por cada borrador que Redaccion
    completa) via k.all(tenant, "validacion") — dato real ya existente, no
    un contador nuevo.

Fuera de alcance de este fichero (mapa de capacidades mezclaba legal/rrhh):
  las entradas de departments.legal.* y departments.rrhh.* no se tocan aqui
  — pertenecen a otros cubos, no a QA."""
from __future__ import annotations

from core.bus import InMemoryBus
from departments.base import Task
from departments.qa import herramientas as h
from departments.qa.agente import QADepartment

from panel_mando.herramientas.base import Argumento, ToolSpec


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_handle(*, k, tenant, bitacora=None, asunto: str = "", cuerpo: str = "",
              contexto: str = "", intent: str = "validar_borrador", **kw) -> dict:
    dept = QADepartment(InMemoryBus(), knowledge=k)
    task = Task(intent=intent, payload={"asunto": asunto, "cuerpo": cuerpo,
                                        "contexto": contexto}, company=tenant)
    result = dept.handle(task)
    return {"ok": result.ok, "summary": result.summary, "data": result.data}


def _fn_validar_borrador(*, k, tenant, bitacora=None, asunto: str, cuerpo: str,
                         contexto: str = "", **kw) -> dict:
    return h.validar_borrador(asunto, cuerpo, contexto)


def _fn_detectar_contradicciones(*, k, tenant, bitacora=None, texto: str,
                                 contexto_empresa: str, **kw) -> dict:
    return h.detectar_contradicciones(texto, contexto_empresa)


def _fn_comparar_con_plantilla(*, k, tenant, bitacora=None, texto: str, requeridos: str,
                               **kw) -> dict:
    lista_requeridos = [r.strip() for r in requeridos.split(",") if r.strip()]
    return h.comparar_con_plantilla(texto, lista_requeridos)


def _fn_calificar_calidad(*, k, tenant, bitacora=None, texto: str,
                          secciones_requeridas: str = "", contexto_empresa: str = "",
                          **kw) -> dict:
    dept = QADepartment(InMemoryBus(), knowledge=k)
    lista_secciones = [s.strip() for s in secciones_requeridas.split(",") if s.strip()]
    task = Task(intent="calificar_calidad",
               payload={"artefacto": texto, "secciones_requeridas": lista_secciones,
                        "contexto_empresa": contexto_empresa},
               company=tenant)
    result = dept.handle(task)
    return {"ok": result.ok, "summary": result.summary, "data": result.data}


def _fn_historial_validaciones(*, k, tenant, bitacora=None, **kw) -> dict:
    validaciones = k.all(tenant, "validacion")
    detalle = list(validaciones.values())
    aceptados = sum(1 for v in detalle if v.get("ok"))
    return {"total": len(detalle), "aceptados": aceptados,
            "rechazados": len(detalle) - aceptados, "detalle": detalle}


HERRAMIENTAS: dict[str, ToolSpec] = {
    "handle": ToolSpec(
        nombre="handle", clase="LECTURA",
        descripcion="Ejecuta el flujo real del departamento de QA (QADepartment.handle) "
                    "sobre un borrador (asunto/cuerpo/contexto opcional); emite el ciclo "
                    "de vida al bus y devuelve ok/summary/data.",
        argumentos=(
            Argumento("asunto", "str", "asunto del borrador", obligatorio=False),
            Argumento("cuerpo", "str", "cuerpo del borrador", obligatorio=False),
            Argumento("contexto", "str", "contexto de empresa para detectar contradicciones",
                     obligatorio=False),
            Argumento("intent", "str", "intent de la tarea (informativo)", obligatorio=False),
        ),
        fn=_fn_handle),
    "validar_borrador": ToolSpec(
        nombre="validar_borrador", clase="LECTURA",
        descripcion="Aplica todas las reglas de QA a un borrador (asunto vacio, cuerpo "
                    "demasiado corto, placeholders, contradicciones con el contexto). "
                    "Devuelve {ok, problemas[]}.",
        argumentos=(
            Argumento("asunto", "str", "asunto del correo"),
            Argumento("cuerpo", "str", "cuerpo del correo"),
            Argumento("contexto", "str", "contexto de empresa para detectar contradicciones",
                     obligatorio=False),
        ),
        fn=_fn_validar_borrador),
    "detectar_contradicciones": ToolSpec(
        nombre="detectar_contradicciones", clase="LECTURA",
        descripcion="Heuristica por keywords: detecta si el texto afirma algo que choca "
                    "con el contexto de la empresa (p. ej. contexto 'artesano' vs texto "
                    "'industrial'). Devuelve {ok, contradicciones[]}.",
        argumentos=(
            Argumento("texto", "str", "texto a comprobar"),
            Argumento("contexto_empresa", "str", "contexto real de la empresa"),
        ),
        fn=_fn_detectar_contradicciones),
    "comparar_con_plantilla": ToolSpec(
        nombre="comparar_con_plantilla", clase="LECTURA",
        descripcion="Comprueba que el texto contiene los elementos requeridos por una "
                    "plantilla. Devuelve {coincide_estructura, diferencias[]}.",
        argumentos=(
            Argumento("texto", "str", "texto a comprobar"),
            Argumento("requeridos", "str",
                     "elementos requeridos separados por comas, p. ej. 'buenos dias,firma'"),
        ),
        fn=_fn_comparar_con_plantilla),
    "calificar_calidad": ToolSpec(
        nombre="calificar_calidad", clase="LECTURA",
        descripcion="Puntua un artefacto 0-10 con el pipeline REAL de especialistas de QA "
                    "(QADepartment con usar_pipeline=True: ValidadorDeEstructura, "
                    "DetectorDeContradicciones, CalificadorDeCalidad — 100% deterministas, "
                    "sin LLM). Devuelve {ok, summary, data} con data.puntuacion (0-10), "
                    "data.desglose y data.recomendaciones.",
        argumentos=(
            Argumento("texto", "str", "artefacto a puntuar (borrador, contenido, etc.)"),
            Argumento("secciones_requeridas", "str",
                     "secciones/elementos requeridos separados por comas para el chequeo "
                     "estructural, p. ej. 'buenos dias,firma' (opcional)", obligatorio=False),
            Argumento("contexto_empresa", "str",
                     "contexto real de la empresa para detectar contradicciones (opcional)",
                     obligatorio=False),
        ),
        fn=_fn_calificar_calidad),
    "historial_validaciones": ToolSpec(
        nombre="historial_validaciones", clase="LECTURA",
        descripcion="Historial REAL ya persistido de validaciones automaticas de borradores "
                    "(core/subscriptors/qa_validador.py, nodos tipo 'validacion' en el "
                    "knowledge store, uno por cada borrador que Redaccion completa). "
                    "Devuelve {total, aceptados, rechazados, detalle[]}.",
        argumentos=(), fn=_fn_historial_validaciones),
}

__all__ = ["HERRAMIENTAS"]
