# -*- coding: utf-8 -*-
"""Herramientas REALES del director de Customer Success (Fase 4 — plenipotenciarios).

Cada ToolSpec envuelve una operacion REAL verificada contra el codigo del
departamento (departments/customer_success/agente.py,
.../herramientas.py). Ninguna funcion aqui atrapa excepciones salvo para
traducir un valor no serializable (o `None`) a dict — si algo falla de
verdad, la excepcion sube y la capa de invocacion la reporta.

`barrido_churn`, `barrido_upsell` y `renovar` son metodos de
`CustomerSuccessDepartment`, que hereda de `Department`/`CuboDepartamento` y
por tanto exige un `MessageBus` real en su constructor (publica CUBE_STARTED
al arrancar y los eventos del contrato al operar). Cada fn crea un
`InMemoryBus()` propio y desechable — exactamente lo que hace el patron de
"cubo ligero" en otros directores (p.ej. `CuboComercial`/`CuboOps` en
comercial.py/ops.py) cuando la operacion no necesita persistir el bus entre
llamadas; los eventos que produce el director (CS_CHURN_ALERT, CS_RENEWAL,
CS_UPSELL_OPPORTUNITY) quedan en el log de ese bus efimero, no se pierden
por excepcion pero tampoco se propagan a otros suscriptores del proceso real
(igual que sucede con cualquier operacion sin bus persistente inyectado).

Deliberadamente NO wireadas (fuera del mapa de capacidades auditado para
este cubo — el auditor solo evaluo `barrido_churn`, `renovar`,
`barrido_upsell` como operaciones y `detectar_churn`, `detectar_upsell`,
`salud_cartera` como lecturas; el resto de `departments/customer_success/
herramientas.py` no tiene veredicto de riesgo y no se wirea sin el):
- alta_cliente: no es una accion de director — la dispara el propio cubo
  como reaccion automatica a `DEPT_TASK_COMPLETED` de Comercial
  (`CustomerSuccessDepartment._on_comercial`); exponerla dejaria que el
  director cree clientes de la nada, sin evento de venta real detras.
- registrar_contacto / abrir_ticket: escritura directa sobre la ficha del
  cliente (NPS, notas) o alta de incidencia sin ningun gate descrito en el
  mapa auditado — no hay veredicto de riesgo que las respalde, se dejan
  fuera hasta que el auditor las revise explicitamente.
"""
from __future__ import annotations

from core.bus import InMemoryBus
from departments.customer_success import herramientas as cs_herramientas
from departments.customer_success.agente import CustomerSuccessDepartment
from panel_mando.herramientas.base import Argumento, ToolSpec


def _dept(k, tenant) -> CustomerSuccessDepartment:
    return CustomerSuccessDepartment(InMemoryBus(), tenant, knowledge=k)


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_detectar_churn(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"riesgo": cs_herramientas.detectar_churn(k, tenant)}


def _fn_detectar_upsell(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"oportunidades": cs_herramientas.detectar_upsell(k, tenant)}


def _fn_salud_cartera(*, k, tenant, bitacora=None, **kw) -> dict:
    return cs_herramientas.salud_cartera(k, tenant)


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def _fn_barrido_churn(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"alertas": _dept(k, tenant).barrido_churn()}


def _fn_barrido_upsell(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"oportunidades": _dept(k, tenant).barrido_upsell()}


# ── IRREVERSIBLE-INTERNA ─────────────────────────────────────────────────

def _fn_renovar(*, k, tenant, bitacora=None, cliente_id: str, **kw) -> dict:
    """`CustomerSuccessDepartment.renovar` devuelve `None` en silencio si el
    cliente no existe (riesgo documentado por el auditor). El contrato de
    ToolSpec.fn exige devolver SIEMPRE un dict, nunca None — se traduce aqui
    a un resultado honesto (`renovado: False` + motivo), no a una excepcion
    inventada ni a un `None` silencioso."""
    ficha = _dept(k, tenant).renovar(cliente_id)
    if ficha is None:
        return {"cliente_id": cliente_id, "renovado": False,
                "motivo": "cliente_id no encontrado en cliente_cs"}
    return {"cliente_id": cliente_id, "renovado": True, "ficha": ficha}


HERRAMIENTAS: dict[str, ToolSpec] = {
    "detectar_churn": ToolSpec(
        nombre="detectar_churn", clase="LECTURA",
        descripcion="Clientes activos en riesgo de churn por inactividad prolongada "
                    "(>=45 dias sin contacto) o NPS de detractor (<=6), ordenados por "
                    "valor mensual (departments.customer_success.herramientas.detectar_churn).",
        argumentos=(), fn=_fn_detectar_churn),
    "detectar_upsell": ToolSpec(
        nombre="detectar_upsell", clase="LECTURA",
        descripcion="Clientes activos con NPS>=9 (promotores): oportunidades de "
                    "crecimiento/upsell (departments.customer_success.herramientas.detectar_upsell).",
        argumentos=(), fn=_fn_detectar_upsell),
    "salud_cartera": ToolSpec(
        nombre="salud_cartera", clase="LECTURA",
        descripcion="Cuadro de salud de la cartera: clientes activos, en riesgo, NPS "
                    "medio y valor mensual en riesgo "
                    "(departments.customer_success.herramientas.salud_cartera).",
        argumentos=(), fn=_fn_salud_cartera),

    "barrido_churn": ToolSpec(
        nombre="barrido_churn", clase="REVERSIBLE",
        descripcion="Detecta clientes en riesgo y emite una alerta CS_CHURN_ALERT por "
                    "cada uno (CustomerSuccessDepartment.barrido_churn). No deduplica "
                    "entre barridos sucesivos; bajo impacto.",
        argumentos=(), fn=_fn_barrido_churn),
    "barrido_upsell": ToolSpec(
        nombre="barrido_upsell", clase="REVERSIBLE",
        descripcion="Detecta oportunidades de upsell y emite CS_UPSELL_OPPORTUNITY por "
                    "cada una (CustomerSuccessDepartment.barrido_upsell). Mismo aviso de "
                    "no-deduplicacion que barrido_churn.",
        argumentos=(), fn=_fn_barrido_upsell),

    "renovar": ToolSpec(
        nombre="renovar", clase="IRREVERSIBLE-INTERNA",
        descripcion="Registra una renovacion para un cliente existente (incrementa su "
                    "contador de renovaciones y actualiza el ultimo contacto) y emite "
                    "CS_RENEWAL (CustomerSuccessDepartment.renovar). Verifica que el "
                    "cliente_id existe antes de invocarla: si no existe, el resultado "
                    "es honesto (renovado: False), no una excepcion.",
        argumentos=(Argumento("cliente_id", "str", "id del cliente en cliente_cs"),),
        fn=_fn_renovar),
}

__all__ = ["HERRAMIENTAS"]
