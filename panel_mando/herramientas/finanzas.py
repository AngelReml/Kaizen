# -*- coding: utf-8 -*-
"""Herramientas reales del cubo Finanzas para el director plenipotenciario (Fase 4).

Wireadas contra el codigo real de `departments/finanzas/` (verificado leyendo cada
fichero, no el mapa de auditoria a ciegas):

- LECTURA: `FinanzasDepartment.handle` (orquesta el selector determinista de
  herramienta + responde con datos reales, sin persistir nada mas alla de
  eventos efimeros en un bus en memoria propio de la llamada) y las cinco
  lecturas deterministas de `departments/finanzas/herramientas.py`
  (consultar_gasto, proyectar_quema, comparar_periodos, top_acciones_caras,
  detectar_anomalia), mas las lecturas de Pista A/B de `cubo_serie_d.py`:
  `Conciliador.proponer` (matching propuesto, no ejecuta nada), `Conciliador.aging`
  y `MotorSIF.verificar_cadena` (recomputo puro de la cadena SHA-256), y la
  funcion pura `nif_valido`.
- REVERSIBLE: `Liquidador.calcular` (numeros reproducibles: recalcular da el
  mismo hash; PENDIENTE_VALIDACION queda fuera con informe) y
  `Conciliador.importar_csv` (import manual de extracto, R-19: jamas
  credenciales bancarias; no deduplica pero es auditable/reversible despues).

Deliberadamente NO wireadas (ver INFORME de la sesion Fase 4):
- `Conciliador.confirmar`: el gate de humano es `por != "operador"` —
  exactamente el patron (a) del auditor: el propio llamador puede autoafirmar
  "operador" en el argumento y saltarse su propio control. No esta en el mapa.
- `MotorSIF.emitir`: IRREVERSIBLE-EXTERNA (remite a la AEAT real via
  `remitir()` dentro del mismo metodo) — nunca se wirea, frontera R2. Tampoco
  esta en el mapa de capacidades.
- `MotorSIF.anular`: mismo patron (a) que `confirmar` (`por != "operador"`
  autoafirmable) ademas de ser un acto legal que D04 §6 exige que sea siempre
  humano. No esta en el mapa.
- `MotorSIF.remitir`: dispara la remision real a la AEAT (simulador hoy, real
  manana) — IRREVERSIBLE-EXTERNA por naturaleza. No esta en el mapa.
- `costes_directos` de `Liquidador.calcular`: es un dict libre no aplanable a
  str/int/float/bool; se expone como argumento `str` opcional con JSON
  serializado (mismo patron que `veredictos`/`lead` en brand.py), vacio por
  defecto si no se indica — tal como pedia el criterio de auditoria.
"""
from __future__ import annotations

import json

from core.bus import InMemoryBus
from departments.base import Task
from departments.finanzas import cubo_serie_d as F
from departments.finanzas import herramientas as dfh
from departments.finanzas.agente import FinanzasDepartment
from panel_mando.herramientas.base import Argumento, ToolSpec


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_department_handle(*, k, tenant, bitacora=None, intent: str, **kw) -> dict:
    presupuesto_mensual = kw.get("presupuesto_mensual")
    dept = FinanzasDepartment(InMemoryBus(), k, presupuesto_mensual=presupuesto_mensual)
    r = dept.handle(Task(intent=intent, company=tenant))
    return {"ok": r.ok, "summary": r.summary, "data": r.data}


def _fn_consultar_gasto(*, k, tenant, bitacora=None, **kw) -> dict:
    periodo = kw.get("periodo", "mes")
    categoria = kw.get("categoria")
    return dfh.consultar_gasto(k, tenant, periodo, categoria)


def _fn_proyectar_quema(*, k, tenant, bitacora=None, **kw) -> dict:
    dias = kw.get("dias", 30)
    presupuesto_mensual = kw.get("presupuesto_mensual")
    return dfh.proyectar_quema(k, tenant, dias, presupuesto_mensual)


def _fn_comparar_periodos(*, k, tenant, bitacora=None, p1: str, p2: str, **kw) -> dict:
    return dfh.comparar_periodos(k, tenant, p1, p2)


def _fn_top_acciones_caras(*, k, tenant, bitacora=None, **kw) -> dict:
    n = kw.get("n", 5)
    periodo = kw.get("periodo", "semana")
    return {"top": dfh.top_acciones_caras(k, tenant, n, periodo)}


def _fn_detectar_anomalia(*, k, tenant, bitacora=None, **kw) -> dict:
    sensibilidad = kw.get("sensibilidad", 3.0)
    return {"anomalias": dfh.detectar_anomalia(k, tenant, sensibilidad)}


def _fn_conciliador_proponer(*, k, tenant, bitacora=None, **kw) -> dict:
    con = F.Conciliador(k, tenant)
    return {"propuestas": con.proponer()}


def _fn_conciliador_aging(*, k, tenant, bitacora=None, **kw) -> dict:
    con = F.Conciliador(k, tenant)
    return {"aging": con.aging()}


def _fn_verificar_cadena_sif(*, k, tenant, bitacora=None, nif: str, **kw) -> dict:
    sif = F.MotorSIF(k, tenant, bitacora=bitacora)
    return sif.verificar_cadena(nif)


def _fn_nif_valido(*, k, tenant, bitacora=None, nif: str, **kw) -> dict:
    return {"nif": nif, "valido": F.nif_valido(nif)}


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def _fn_liquidador_calcular(*, k, tenant, bitacora=None, periodo: str, **kw) -> dict:
    costes_raw = kw.get("costes_directos")
    costes_directos = json.loads(costes_raw) if costes_raw else {}
    comision_pct = kw.get("comision_pct", 0.5)
    version_anexo = kw.get("version_anexo", "anexo-I-v1")
    liq = F.Liquidador(k, tenant, bitacora=bitacora)
    return liq.calcular(periodo, costes_directos=costes_directos,
                        comision_pct=comision_pct, version_anexo=version_anexo)


def _fn_conciliador_importar_csv(*, k, tenant, bitacora=None, contenido_csv: str, **kw) -> dict:
    con = F.Conciliador(k, tenant)
    return {"movimientos": con.importar_csv(contenido_csv)}


HERRAMIENTAS: dict[str, ToolSpec] = {
    "department_handle": ToolSpec(
        nombre="department_handle", clase="LECTURA",
        descripcion="Ejecuta el ciclo completo del departamento de Finanzas para una "
                    "pregunta en lenguaje natural: elige la herramienta determinista "
                    "adecuada (por palabras clave) y responde con datos reales "
                    "(FinanzasDepartment.handle).",
        argumentos=(
            Argumento("intent", "str", "pregunta/intencion en lenguaje natural"),
            Argumento("presupuesto_mensual", "float",
                      "presupuesto mensual para calcular runway (opcional)",
                      obligatorio=False),
        ),
        fn=_fn_department_handle),

    "consultar_gasto": ToolSpec(
        nombre="consultar_gasto", clase="LECTURA",
        descripcion="Gasto total y desglose por modelo en un periodo, opcionalmente "
                    "filtrado por categoria (departments.finanzas.herramientas.consultar_gasto).",
        argumentos=(
            Argumento("periodo", "str",
                      "todo | hoy | semana | semana_anterior | mes (por defecto 'mes')",
                      obligatorio=False),
            Argumento("categoria", "str", "categoria a filtrar (opcional)", obligatorio=False),
        ),
        fn=_fn_consultar_gasto),

    "proyectar_quema": ToolSpec(
        nombre="proyectar_quema", clase="LECTURA",
        descripcion="Gasto diario medio y proyeccion a N dias; con presupuesto_mensual "
                    "calcula el runway estimado (departments.finanzas.herramientas.proyectar_quema).",
        argumentos=(
            Argumento("dias", "int", "dias a proyectar (por defecto 30)", obligatorio=False),
            Argumento("presupuesto_mensual", "float",
                      "presupuesto mensual para calcular runway (opcional)",
                      obligatorio=False),
        ),
        fn=_fn_proyectar_quema),

    "comparar_periodos": ToolSpec(
        nombre="comparar_periodos", clase="LECTURA",
        descripcion="Compara el gasto total entre dos periodos y la variacion porcentual "
                    "(departments.finanzas.herramientas.comparar_periodos).",
        argumentos=(
            Argumento("p1", "str", "primer periodo (todo|hoy|semana|semana_anterior|mes)"),
            Argumento("p2", "str", "segundo periodo (todo|hoy|semana|semana_anterior|mes)"),
        ),
        fn=_fn_comparar_periodos),

    "top_acciones_caras": ToolSpec(
        nombre="top_acciones_caras", clase="LECTURA",
        descripcion="Las N acciones mas caras de un periodo, ordenadas de mayor a menor "
                    "coste (departments.finanzas.herramientas.top_acciones_caras).",
        argumentos=(
            Argumento("n", "int", "numero de acciones a listar (por defecto 5)",
                      obligatorio=False),
            Argumento("periodo", "str",
                      "todo | hoy | semana | semana_anterior | mes (por defecto 'semana')",
                      obligatorio=False),
        ),
        fn=_fn_top_acciones_caras),

    "detectar_anomalia": ToolSpec(
        nombre="detectar_anomalia", clase="LECTURA",
        descripcion="Detecta gastos atipicos (por encima de media + sensibilidad * "
                    "desviacion estandar) en el historico "
                    "(departments.finanzas.herramientas.detectar_anomalia).",
        argumentos=(
            Argumento("sensibilidad", "float",
                      "multiplicador de desviacion estandar para el umbral (por defecto 3.0)",
                      obligatorio=False),
        ),
        fn=_fn_detectar_anomalia),

    "conciliador_proponer": ToolSpec(
        nombre="conciliador_proponer", clase="LECTURA",
        descripcion="Propone emparejamientos deterministas (por importe dentro de "
                    "tolerancia) entre movimientos bancarios sin conciliar y facturas "
                    "pendientes de cobro; no confirma nada (Conciliador.proponer).",
        argumentos=(), fn=_fn_conciliador_proponer),

    "conciliador_aging": ToolSpec(
        nombre="conciliador_aging", clase="LECTURA",
        descripcion="Antiguedad (dias pendientes) de las facturas aun no cobradas, "
                    "ordenadas de mas a menos antigua (Conciliador.aging).",
        argumentos=(), fn=_fn_conciliador_aging),

    "verificar_cadena_sif": ToolSpec(
        nombre="verificar_cadena_sif", clase="LECTURA",
        descripcion="Recomputo puro e independiente de la cadena SHA-256 de registros SIF "
                    "de un NIF obligado: confirma integridad o el punto exacto de ruptura "
                    "(MotorSIF.verificar_cadena).",
        argumentos=(Argumento("nif", "str", "NIF obligado a verificar"),),
        fn=_fn_verificar_cadena_sif),

    "nif_valido": ToolSpec(
        nombre="nif_valido", clase="LECTURA",
        descripcion="Validacion algoritmica (digito de control) de un DNI/NIE, sin datos "
                    "legales externos (departments.finanzas.cubo_serie_d.nif_valido).",
        argumentos=(Argumento("nif", "str", "NIF/DNI/NIE a validar"),),
        fn=_fn_nif_valido),

    "liquidador_calcular": ToolSpec(
        nombre="liquidador_calcular", clase="REVERSIBLE",
        descripcion="Calcula la liquidacion de un periodo agregando pedidos ATRIBUIDOS "
                    "(los PENDIENTE_VALIDACION quedan fuera con informe); reproducible: "
                    "recalcular con los mismos datos da el mismo hash (Liquidador.calcular). "
                    "No emite factura ni mueve dinero real.",
        argumentos=(
            Argumento("periodo", "str", "periodo a liquidar, p.ej. '2026-07'"),
            Argumento("costes_directos", "str",
                      "costes directos por pedido como JSON, p.ej. "
                      '{"ped1": 40.0, "ped2": 10.0} (opcional, vacio si no se indica)',
                      obligatorio=False),
            Argumento("comision_pct", "float", "porcentaje de comision (por defecto 0.5)",
                      obligatorio=False),
            Argumento("version_anexo", "str",
                      "version del anexo aplicado (por defecto 'anexo-I-v1')",
                      obligatorio=False),
        ),
        fn=_fn_liquidador_calcular),

    "conciliador_importar_csv": ToolSpec(
        nombre="conciliador_importar_csv", clase="REVERSIBLE",
        descripcion="Importa manualmente un extracto bancario en CSV (columnas "
                    "fecha,concepto,importe) como movimientos SIN_CONCILIAR (R-19: jamas "
                    "credenciales bancarias, solo import manual) (Conciliador.importar_csv).",
        argumentos=(
            Argumento("contenido_csv", "str",
                      "contenido CSV completo con cabecera fecha,concepto,importe"),
        ),
        fn=_fn_conciliador_importar_csv),
}

__all__ = ["HERRAMIENTAS"]
