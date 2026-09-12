# -*- coding: utf-8 -*-
"""Herramientas REALES del director de Ops (Fase 4 — plenipotenciarios).

Cada ToolSpec envuelve una operacion REAL verificada contra el codigo del
departamento (departments/ops/cubo_serie_d.py, .../herramientas.py,
.../reglas.py). Ninguna funcion aqui atrapa excepciones salvo para traducir
un objeto no serializable a dict — si algo falla, la excepcion sube y la
capa de invocacion la reporta.

Deliberadamente NO wireadas (ver criterio del auditor, patron b — atestacion
de un hecho fisico que el director no puede saber por si mismo):
- registrar_hito (CuboOps.registrar_hito): exige `foto_ref` como evidencia de
  un hito fisico de obrador (LOTE_COMPLETO/EMPAQUETADO/LISTO_LOGISTICA); el
  director no puede verificar por si mismo que la foto existe o es real.
- entregar_a_logistica (CuboOps.entregar_a_logistica): certifica un traspaso
  fisico real a logistica via `albaran_ref`; misma atestacion no verificable.

No hay operaciones IRREVERSIBLE-EXTERNA ni apto=false en el mapa de Ops.
"""
from __future__ import annotations

from datetime import datetime, timezone

from departments.ops import herramientas as ops_herramientas
from departments.ops import reglas as ops_reglas
from departments.ops.cubo_serie_d import CuboOps
from panel_mando.herramientas.base import Argumento, ToolSpec


def _cubo(k, tenant, bitacora):
    return CuboOps(k, tenant, bitacora=bitacora)


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_consultar_capacidad(*, k, tenant, bitacora=None, fecha: str, **kw) -> dict:
    return _cubo(k, tenant, bitacora).consultar_capacidad(fecha)


def _fn_proponer_secuencia(*, k, tenant, bitacora=None, fecha: str, **kw) -> dict:
    return {"fecha": fecha, "secuencia": _cubo(k, tenant, bitacora).proponer_secuencia(fecha)}


def _fn_alerta_stock(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"alertas": ops_herramientas.alerta_stock(k, tenant)}


def _fn_capacidad_supera_umbral(*, k, tenant, bitacora=None, ocupada_pct: float,
                                umbral: float = 0.9, **kw) -> dict:
    pasa, motivo = ops_reglas.capacidad_supera_umbral(ocupada_pct, umbral)
    return {"pasa": pasa, "motivo": motivo}


def _fn_stock_bajo_seguridad(*, k, tenant, bitacora=None, stock: float, seguridad: float,
                             **kw) -> dict:
    pasa, motivo = ops_reglas.stock_bajo_seguridad(stock, seguridad)
    return {"pasa": pasa, "motivo": motivo}


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def _fn_declarar_capacidad(*, k, tenant, bitacora=None, fecha: str, lotes: int,
                           por: str = "operador", version_motivo: str = "", **kw) -> dict:
    return _cubo(k, tenant, bitacora).declarar_capacidad(fecha, lotes, por=por,
                                                         version_motivo=version_motivo)


def _fn_declarar_stock(*, k, tenant, bitacora=None, material: str, cantidad: float,
                       seguridad: float, por: str = "operador", **kw) -> dict:
    """Simetrico a declarar_capacidad: un dato operativo que declara el operador del
    obrador (no un sensor automatico), sin logica de negocio compleja detras — se
    escribe directo en el knowledge store con el esquema exacto que
    departments.ops.herramientas.alerta_stock espera leer (material/stock/
    stock_seguridad). Cada declaracion sobrescribe la anterior del mismo material
    (mismo patron de "ultima version gana" que declarar_capacidad por fecha)."""
    nodo = {"material": material, "stock": float(cantidad), "stock_seguridad": float(seguridad),
           "declarado_por": por, "ts": datetime.now(timezone.utc).isoformat()}
    k.add(tenant, "inventario", material, nodo)
    return nodo


def _fn_recibir_pedido(*, k, tenant, bitacora=None, id: str, cliente_ref: str, producto: str,
                       cantidad: int, fecha: str, **kw) -> dict:
    pedido = {"id": id, "cliente_ref": cliente_ref, "producto": producto,
             "cantidad": cantidad, "fecha": fecha}
    if "urgente" in kw:
        pedido["urgente"] = kw["urgente"]
    if "cliente_loyal" in kw:
        pedido["cliente_loyal"] = kw["cliente_loyal"]
    return _cubo(k, tenant, bitacora).recibir_pedido(pedido)


# ── IRREVERSIBLE-INTERNA ─────────────────────────────────────────────────

def _fn_confirmar(*, k, tenant, bitacora=None, pedido_id: str, **kw) -> dict:
    return _cubo(k, tenant, bitacora).confirmar(pedido_id)


def _fn_barrer_pendientes(*, k, tenant, bitacora=None, **kw) -> dict:
    return {"avisos": _cubo(k, tenant, bitacora).barrer_pendientes()}


HERRAMIENTAS: dict[str, ToolSpec] = {
    "consultar_capacidad": ToolSpec(
        nombre="consultar_capacidad", clase="LECTURA",
        descripcion="Capacidad declarada, consumida y disponible para una fecha "
                    "(CuboOps.consultar_capacidad).",
        argumentos=(Argumento("fecha", "str", "fecha ISO a consultar"),),
        fn=_fn_consultar_capacidad),

    "proponer_secuencia": ToolSpec(
        nombre="proponer_secuencia", clase="LECTURA",
        descripcion="Secuencia de produccion determinista para una fecha: LOYAL y "
                    "URGENTE primero (CuboOps.proponer_secuencia).",
        argumentos=(Argumento("fecha", "str", "fecha ISO a secuenciar"),),
        fn=_fn_proponer_secuencia),

    "alerta_stock": ToolSpec(
        nombre="alerta_stock", clase="LECTURA",
        descripcion="Materiales con stock por debajo del stock de seguridad "
                    "(departments.ops.herramientas.alerta_stock).",
        argumentos=(),
        fn=_fn_alerta_stock),

    "capacidad_supera_umbral": ToolSpec(
        nombre="capacidad_supera_umbral", clase="LECTURA",
        descripcion="Regla dura: si un porcentaje de ocupacion supera el umbral de "
                    "alerta antes de aceptar mas pedidos (departments.ops.reglas."
                    "capacidad_supera_umbral).",
        argumentos=(Argumento("ocupada_pct", "float", "porcentaje ocupado, 0.0-1.0"),
                   Argumento("umbral", "float", "umbral de alerta (por defecto 0.9)",
                             obligatorio=False)),
        fn=_fn_capacidad_supera_umbral),

    "stock_bajo_seguridad": ToolSpec(
        nombre="stock_bajo_seguridad", clase="LECTURA",
        descripcion="Regla dura: si un nivel de stock esta por debajo del minimo de "
                    "seguridad (departments.ops.reglas.stock_bajo_seguridad).",
        argumentos=(Argumento("stock", "float", "stock actual del material"),
                   Argumento("seguridad", "float", "stock minimo de seguridad")),
        fn=_fn_stock_bajo_seguridad),

    "declarar_capacidad": ToolSpec(
        nombre="declarar_capacidad", clase="REVERSIBLE",
        descripcion="Declara la capacidad (lotes) de una fecha, versionada "
                    "(CuboOps.declarar_capacidad). Afirmacion sobre capacidad fisica "
                    "real: basala en lo que te reporte el operador del obrador.",
        argumentos=(Argumento("fecha", "str", "fecha ISO a declarar"),
                   Argumento("lotes", "int", "lotes de capacidad para esa fecha"),
                   Argumento("por", "str", "quien declara (por defecto 'operador')",
                             obligatorio=False),
                   Argumento("version_motivo", "str", "motivo del cambio de version",
                             obligatorio=False)),
        fn=_fn_declarar_capacidad),

    "declarar_stock": ToolSpec(
        nombre="declarar_stock", clase="REVERSIBLE",
        descripcion="Declara el stock actual y el stock de seguridad de un material "
                    "(dato operativo que reporta el operador del obrador, no un sensor "
                    "automatico). Alimenta directamente alerta_stock: sin esto ningun "
                    "material puede aparecer en alerta_stock (nadie mas escribe nodos "
                    "tipo 'inventario'). Cada declaracion sobrescribe la anterior del "
                    "mismo material.",
        argumentos=(Argumento("material", "str", "nombre del material"),
                   Argumento("cantidad", "float", "stock actual del material"),
                   Argumento("seguridad", "float", "stock minimo de seguridad"),
                   Argumento("por", "str", "quien declara (por defecto 'operador')",
                             obligatorio=False)),
        fn=_fn_declarar_stock),

    "recibir_pedido": ToolSpec(
        nombre="recibir_pedido", clase="REVERSIBLE",
        descripcion="Da de alta un pedido interno en PENDIENTE_CONFIRMACION "
                    "(CuboOps.recibir_pedido).",
        argumentos=(Argumento("id", "str", "id del pedido"),
                   Argumento("cliente_ref", "str", "referencia del cliente"),
                   Argumento("producto", "str", "producto pedido"),
                   Argumento("cantidad", "int", "cantidad pedida"),
                   Argumento("fecha", "str", "fecha ISO del pedido"),
                   Argumento("urgente", "bool", "si el pedido es urgente",
                             obligatorio=False),
                   Argumento("cliente_loyal", "bool", "si el cliente es loyal",
                             obligatorio=False)),
        fn=_fn_recibir_pedido),

    "confirmar": ToolSpec(
        nombre="confirmar", clase="IRREVERSIBLE-INTERNA",
        descripcion="Claim atomico sobre la capacidad de la fecha del pedido: "
                    "CONFIRMADO, RECHAZADO con propuesta de fecha alternativa, o "
                    "PENDIENTE si la capacidad no esta declarada (CuboOps.confirmar).",
        argumentos=(Argumento("pedido_id", "str", "id del pedido a confirmar"),),
        fn=_fn_confirmar),

    "barrer_pendientes": ToolSpec(
        nombre="barrer_pendientes", clase="IRREVERSIBLE-INTERNA",
        descripcion="Barrido de SLA sobre pedidos PENDIENTE_CONFIRMACION: alerta a "
                    "las 24h, escala/rechaza a las 72h (CuboOps.barrer_pendientes).",
        argumentos=(),
        fn=_fn_barrer_pendientes),
}

__all__ = ["HERRAMIENTAS"]
