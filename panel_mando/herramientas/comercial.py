# -*- coding: utf-8 -*-
"""Herramientas REALES del director de Comercial (Fase 4 — plenipotenciarios).

Cada ToolSpec envuelve una operacion REAL verificada contra el codigo del
departamento (departments/comercial/cubo_serie_d.py, .../lifecycle.py,
.../metricas.py, .../sdr/compromiso.py, cubos/comercial/adaptador.py,
cubos/comercial/p8_bucle.py, sustrato/registro.py). Ninguna funcion aqui
atrapa excepciones salvo para traducir un objeto no serializable a dict —
si algo falla, la excepcion sube y la capa de invocacion la reporta.

Las operaciones de sustrato/registro.py (P9) trabajan sobre una conexion
SQLite propia, no sobre `k` (KnowledgeStore, capa 2). Cada fn que las usa
abre su propia conexion con `sustrato.bus.conexion()` — EXACTAMENTE como
hace `cubos.comercial.adaptador.CuboComercial` cuando no se le pasa una
conexion explicita — y la cierra al terminar; el esquema se instala de
forma idempotente antes de operar (CREATE TABLE IF NOT EXISTS).

Deliberadamente NO wireadas (ver INFORME de la sesion Fase 4):
- enviar_email: IRREVERSIBLE-EXTERNA — nunca se wirea (frontera R2).
- llamada_ia: los tres flags de gate (robinson_consultado,
  disclosure_test_verde, cuota_dia_usada) los declara el propio llamante
  sin forma de verificarlos — el director podria autoafirmar su propio
  control de cumplimiento.
- alta_lead: sobrescribe silenciosamente un lead existente si el id ya
  esta en uso (k.add sin comprobacion de duplicado) y su argumento
  principal es un dict anidado no aplanable a str/int/float/bool.
- registrar_pedido (P9): registra importes de dinero sin exigir ninguna
  evidencia — vetada explicitamente por el criterio de auditoria.
"""
from __future__ import annotations

from dataclasses import asdict

from cubos.comercial import p8_bucle
from cubos.comercial.adaptador import CuboComercial
from departments.comercial import metricas as metricas_mod
from departments.comercial.cubo_serie_d import (Atribuidor, PipelineCanonico,
                                                asiento_p8,
                                                bloques_obligatorios_ausentes,
                                                ranking_argumentos)
from departments.comercial.lifecycle import LeadStore
from departments.comercial.sdr.compromiso import CompromisoDetector
from panel_mando.herramientas.base import Argumento, ToolSpec
from sustrato import bus as sbus
from sustrato import registro as p9


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_salud_cubo(*, k, tenant, bitacora=None, **kw) -> dict:
    cubo = CuboComercial(cliente_id=tenant)
    cubo.instalar()
    return cubo.salud()


def _fn_lead_canonico(*, k, tenant, bitacora=None, lead_id: str, **kw) -> dict:
    p = PipelineCanonico(k, tenant, bitacora=bitacora)
    return p.lead(lead_id)


def _fn_en_lista_exclusion(*, k, tenant, bitacora=None, email_o_id: str, **kw) -> dict:
    p = PipelineCanonico(k, tenant, bitacora=bitacora)
    return {"email_o_id": email_o_id, "en_exclusion": p.en_lista_exclusion(email_o_id)}


def _fn_bloques_obligatorios_ausentes(*, k, tenant, bitacora=None, cuerpo: str, **kw) -> dict:
    return {"bloques_ausentes": bloques_obligatorios_ausentes(cuerpo)}


def _fn_ranking_argumentos(*, k, tenant, bitacora=None, segmento: str, **kw) -> dict:
    return {"ranking": ranking_argumentos(k, tenant, segmento)}


def _fn_conteo_por_estado(*, k, tenant, bitacora=None, **kw) -> dict:
    store = LeadStore(k, tenant)
    return store.contar_por_estado()


def _fn_cuadro_metricas_fase0(*, k, tenant, bitacora=None, **kw) -> dict:
    store = LeadStore(k, tenant)
    cuadro = metricas_mod.calcular(store)
    return {"metricas": [asdict(m) for m in cuadro.metricas],
            "gates_fase0": cuadro.gates_fase0,
            "cualificados_total": cuadro.cualificados_total,
            "enriquecidos_total": cuadro.enriquecidos_total}


def _fn_agregados_p8(*, k, tenant, bitacora=None, **kw) -> dict:
    conn = sbus.conexion()
    try:
        sbus.instalar(conn)
        p9.instalar(conn)
        p8_bucle.instalar(conn)
        return {"agregados": p8_bucle.agregados(conn, kw.get("segmento"))}
    finally:
        conn.close()


def _fn_ranking_p8(*, k, tenant, bitacora=None, **kw) -> dict:
    conn = sbus.conexion()
    try:
        sbus.instalar(conn)
        p9.instalar(conn)
        p8_bucle.instalar(conn)
        return {"ranking": p8_bucle.ranking(conn, kw.get("segmento"))}
    finally:
        conn.close()


def _fn_evaluar_compromiso_reciproco(*, k, tenant, bitacora=None, texto_respuesta: str,
                                     **kw) -> dict:
    detector = CompromisoDetector()
    decision = detector.evaluar(texto_respuesta, company=tenant)
    return asdict(decision)


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def _fn_cerrar_compromiso_p9(*, k, tenant, bitacora=None, compromiso_id: int, estado: str,
                             **kw) -> dict:
    conn = sbus.conexion()
    try:
        sbus.instalar(conn)
        p9.instalar(conn)
        p9.cerrar_compromiso(conn, compromiso_id, estado)
        return {"compromiso_id": compromiso_id, "estado": estado}
    finally:
        conn.close()


# ── IRREVERSIBLE-INTERNA ─────────────────────────────────────────────────

def _fn_transicionar_pipeline_canonico(*, k, tenant, bitacora=None, lead_id: str, a: str,
                                       disparador: str, **kw) -> dict:
    p = PipelineCanonico(k, tenant, bitacora=bitacora)
    return p.transicionar(lead_id, a, disparador=disparador,
                          causa_ref=kw.get("causa_ref", ""))


def _fn_opt_out_lead(*, k, tenant, bitacora=None, lead_id: str, **kw) -> dict:
    p = PipelineCanonico(k, tenant, bitacora=bitacora)
    return p.opt_out(lead_id, evidencia_ref=kw.get("evidencia_ref", ""))


def _fn_atribuir_pedido(*, k, tenant, bitacora=None, pedido_id: str, lead_id: str, via: str,
                        **kw) -> dict:
    a = Atribuidor(k, tenant, bitacora=bitacora)
    return a.atribuir(pedido_id=pedido_id, lead_id=lead_id, via=via,
                      correlacion_id=kw.get("correlacion_id", ""),
                      fecha_primer_pedido=kw.get("fecha_primer_pedido", ""),
                      importe_bruto=kw.get("importe_bruto"))


def _fn_asiento_p8_telemetria(*, k, tenant, bitacora=None, segmento: str, argumento_id: str,
                              canal: str, secuencia: str, resultado: str, **kw) -> dict:
    return asiento_p8(k, tenant, bitacora=bitacora, segmento=segmento,
                      argumento_id=argumento_id, canal=canal, secuencia=secuencia,
                      resultado=resultado, t_respuesta_h=kw.get("t_respuesta_h"),
                      cliente_ref=kw.get("cliente_ref", ""))


def _fn_transicionar_lead_p9(*, k, tenant, bitacora=None, lead_id: str, a: str, **kw) -> dict:
    conn = sbus.conexion()
    try:
        sbus.instalar(conn)
        p9.instalar(conn)
        p9.transicionar(conn, lead_id, a, kw.get("motivo"), _forzar_operador=False)
        fila = conn.execute("SELECT estado FROM leads WHERE id=?", (lead_id,)).fetchone()
        return {"lead_id": lead_id, "a": a, "estado_actual": fila[0] if fila else None}
    finally:
        conn.close()


def _fn_insertar_interaccion_p9(*, k, tenant, bitacora=None, lead_id: str, canal: str,
                                resultado: str, **kw) -> dict:
    conn = sbus.conexion()
    try:
        sbus.instalar(conn)
        p9.instalar(conn)
        iid = p9.insertar_interaccion(
            conn, lead_id, canal, resultado,
            cliente_id=kw.get("cliente_id", "laboratorio"),
            duracion_s=kw.get("duracion_s"), transcript_ref=kw.get("transcript_ref"),
            argumento_id=kw.get("argumento_id"), notas=kw.get("notas"))
        return {"interaccion_id": iid}
    finally:
        conn.close()


def _fn_crear_compromiso_p9(*, k, tenant, bitacora=None, lead_id: str, tipo: str,
                            descripcion: str, fecha_limite: str, **kw) -> dict:
    conn = sbus.conexion()
    try:
        sbus.instalar(conn)
        p9.instalar(conn)
        cid = p9.crear_compromiso(conn, lead_id, tipo, descripcion, fecha_limite,
                                  interaccion_origen=kw.get("interaccion_origen"))
        return {"compromiso_id": cid}
    finally:
        conn.close()


HERRAMIENTAS: dict[str, ToolSpec] = {
    "salud_cubo": ToolSpec(
        nombre="salud_cubo", clase="LECTURA",
        descripcion="Salud real del cubo comercial: leads, compromisos pendientes, "
                    "eventos publicados en 24h (CuboComercial.salud).",
        argumentos=(), fn=_fn_salud_cubo),
    "lead_canonico": ToolSpec(
        nombre="lead_canonico", clase="LECTURA",
        descripcion="Lee el estado canonico completo de un lead (PipelineCanonico.lead).",
        argumentos=(Argumento("lead_id", "str", "id del lead"),),
        fn=_fn_lead_canonico),
    "en_lista_exclusion": ToolSpec(
        nombre="en_lista_exclusion", clase="LECTURA",
        descripcion="Comprueba si un email/id esta en la lista de exclusion de plataforma "
                    "(PipelineCanonico.en_lista_exclusion).",
        argumentos=(Argumento("email_o_id", "str", "email o id a comprobar"),),
        fn=_fn_en_lista_exclusion),
    "bloques_obligatorios_ausentes": ToolSpec(
        nombre="bloques_obligatorios_ausentes", clase="LECTURA",
        descripcion="Comprobacion estructural (no LLM) de que bloques legales obligatorios "
                    "faltan en un cuerpo de mensaje (S3/S7).",
        argumentos=(Argumento("cuerpo", "str", "texto del mensaje a comprobar"),),
        fn=_fn_bloques_obligatorios_ausentes),
    "ranking_argumentos": ToolSpec(
        nombre="ranking_argumentos", clase="LECTURA",
        descripcion="Ranking determinista de argumentos comerciales por segmento, segun "
                    "resultados P8 acumulados (ranking_argumentos).",
        argumentos=(Argumento("segmento", "str", "segmento ICP a consultar"),),
        fn=_fn_ranking_argumentos),
    "conteo_por_estado": ToolSpec(
        nombre="conteo_por_estado", clase="LECTURA",
        descripcion="Conteo de leads por estado del ciclo de vida (LeadStore.contar_por_estado).",
        argumentos=(), fn=_fn_conteo_por_estado),
    "cuadro_metricas_fase0": ToolSpec(
        nombre="cuadro_metricas_fase0", clase="LECTURA",
        descripcion="Cuadro de metricas Fase 0 con bandas verde/ambar/rojo y gates de "
                    "transicion a Fase 1 (departments.comercial.metricas.calcular).",
        argumentos=(), fn=_fn_cuadro_metricas_fase0),
    "agregados_p8": ToolSpec(
        nombre="agregados_p8", clase="LECTURA",
        descripcion="Agregados del bucle P8 (avanza/rechaza/neutro por argumento y segmento), "
                    "leidos del registro SQLite (cubos.comercial.p8_bucle.agregados).",
        argumentos=(Argumento("segmento", "str", "segmento a filtrar", obligatorio=False),),
        fn=_fn_agregados_p8),
    "ranking_p8": ToolSpec(
        nombre="ranking_p8", clase="LECTURA",
        descripcion="Ranking P8 con muestra suficiente (n>=10), leido del registro SQLite "
                    "(cubos.comercial.p8_bucle.ranking).",
        argumentos=(Argumento("segmento", "str", "segmento a filtrar", obligatorio=False),),
        fn=_fn_ranking_p8),
    "evaluar_compromiso_reciproco": ToolSpec(
        nombre="evaluar_compromiso_reciproco", clase="LECTURA",
        descripcion="Analiza con el detector real (LLM) si una respuesta de cliente expresa "
                    "Compromiso Reciproco (CompromisoDetector.evaluar). Coste LLM por llamada; "
                    "salida no determinista.",
        argumentos=(Argumento("texto_respuesta", "str", "texto literal de la respuesta del cliente"),),
        fn=_fn_evaluar_compromiso_reciproco),

    "cerrar_compromiso_p9": ToolSpec(
        nombre="cerrar_compromiso_p9", clase="REVERSIBLE",
        descripcion="Cierra un compromiso ya existente del registro P9 con un estado final "
                    "(sustrato.registro.cerrar_compromiso). Bajo riesgo, reversible.",
        argumentos=(Argumento("compromiso_id", "int", "id del compromiso"),
                   Argumento("estado", "str", "cumplido | incumplido | cancelado")),
        fn=_fn_cerrar_compromiso_p9),

    "transicionar_pipeline_canonico": ToolSpec(
        nombre="transicionar_pipeline_canonico", clase="IRREVERSIBLE-INTERNA",
        descripcion="Transiciona un lead en la maquina de estados canonica D01, validada "
                    "internamente (PipelineCanonico.transicionar). EXCLUIDO es absorbente; "
                    "SISTEMA no puede excluir por su cuenta.",
        argumentos=(Argumento("lead_id", "str", "id del lead"),
                   Argumento("a", "str", "estado destino"),
                   Argumento("disparador", "str", "SISTEMA | OPERADOR | EVIDENCIA | OPTOUT"),
                   Argumento("causa_ref", "str", "referencia de la causa (compromiso/pedido)",
                             obligatorio=False)),
        fn=_fn_transicionar_pipeline_canonico),
    "opt_out_lead": ToolSpec(
        nombre="opt_out_lead", clase="IRREVERSIBLE-INTERNA",
        descripcion="Oposicion/baja inmediata de un lead: EXCLUIDO absorbente + alta en la "
                    "lista de exclusion de plataforma (PipelineCanonico.opt_out). Direccion "
                    "de fallo segura.",
        argumentos=(Argumento("lead_id", "str", "id del lead"),
                   Argumento("evidencia_ref", "str", "referencia de la evidencia de oposicion",
                             obligatorio=False)),
        fn=_fn_opt_out_lead),
    "atribuir_pedido": ToolSpec(
        nombre="atribuir_pedido", clase="IRREVERSIBLE-INTERNA",
        descripcion="Atribuye un pedido a un lead por una via verificable (DIRECTA exige "
                    "cadena causal en bitacora integra; REPETICION exige pedido previo; "
                    "REGISTRO_EXTERNO queda PENDIENTE_VALIDACION, nunca se auto-atribuye). "
                    "Afecta a dinero/comisiones (Atribuidor.atribuir).",
        argumentos=(Argumento("pedido_id", "str", "id del pedido"),
                   Argumento("lead_id", "str", "id del lead"),
                   Argumento("via", "str", "DIRECTA | REPETICION | REGISTRO_EXTERNO"),
                   Argumento("correlacion_id", "str", "id de correlacion (via DIRECTA)",
                             obligatorio=False),
                   Argumento("fecha_primer_pedido", "str", "fecha del primer pedido (via REPETICION)",
                             obligatorio=False),
                   Argumento("importe_bruto", "float", "importe bruto del pedido", obligatorio=False)),
        fn=_fn_atribuir_pedido),
    "asiento_p8_telemetria": ToolSpec(
        nombre="asiento_p8_telemetria", clase="IRREVERSIBLE-INTERNA",
        descripcion="Registra un asiento de telemetria P8 (resultado real de un contacto) "
                    "para que el argumentario aprenda (asiento_p8). No valida el resultado: "
                    "telemetria falsa sesga el ranking.",
        argumentos=(Argumento("segmento", "str", "segmento ICP"),
                   Argumento("argumento_id", "str", "id del argumento usado"),
                   Argumento("canal", "str", "canal usado"),
                   Argumento("secuencia", "str", "secuencia usada"),
                   Argumento("resultado", "str",
                             "SIN_RESPUESTA | NEGATIVA | POSITIVA | COMPROMISO | PEDIDO"),
                   Argumento("t_respuesta_h", "float", "horas hasta la respuesta",
                             obligatorio=False),
                   Argumento("cliente_ref", "str", "referencia del cliente", obligatorio=False)),
        fn=_fn_asiento_p8_telemetria),
    "transicionar_lead_p9": ToolSpec(
        nombre="transicionar_lead_p9", clase="IRREVERSIBLE-INTERNA",
        descripcion="Transiciona un lead en el registro P9 (SQLite) por la matriz cerrada "
                    "de transiciones legales (sustrato.registro.transicionar). Las excepciones "
                    "reservadas al operador jamas se habilitan desde aqui.",
        argumentos=(Argumento("lead_id", "str", "id del lead"),
                   Argumento("a", "str", "estado destino"),
                   Argumento("motivo", "str", "motivo de la transicion", obligatorio=False)),
        fn=_fn_transicionar_lead_p9),
    "insertar_interaccion_p9": ToolSpec(
        nombre="insertar_interaccion_p9", clase="IRREVERSIBLE-INTERNA",
        descripcion="Registra una interaccion real con un lead en el registro P9 "
                    "(sustrato.registro.insertar_interaccion). Interacciones ficticias "
                    "alimentan P8 con datos falsos.",
        argumentos=(Argumento("lead_id", "str", "id del lead"),
                   Argumento("canal", "str",
                             "llamada_manual | llamada_ia | email | whatsapp | visita | otro"),
                   Argumento("resultado", "str",
                             "no_contesta | ocupado | numero_invalido | rechazo | neutro | "
                             "interes | compromiso | pedido"),
                   Argumento("cliente_id", "str", "id de cliente/tenant del registro P9",
                             obligatorio=False),
                   Argumento("duracion_s", "int", "duracion en segundos", obligatorio=False),
                   Argumento("transcript_ref", "str", "referencia a la transcripcion",
                             obligatorio=False),
                   Argumento("argumento_id", "str", "id del argumento usado", obligatorio=False),
                   Argumento("notas", "str", "notas libres", obligatorio=False)),
        fn=_fn_insertar_interaccion_p9),
    "crear_compromiso_p9": ToolSpec(
        nombre="crear_compromiso_p9", clase="IRREVERSIBLE-INTERNA",
        descripcion="Crea un compromiso (promesa al cliente) en el registro P9 "
                    "(sustrato.registro.crear_compromiso).",
        argumentos=(Argumento("lead_id", "str", "id del lead"),
                   Argumento("tipo", "str",
                             "callback | envio_muestras | reunion | pedido_pendiente | otro"),
                   Argumento("descripcion", "str", "descripcion del compromiso"),
                   Argumento("fecha_limite", "str", "fecha limite ISO8601"),
                   Argumento("interaccion_origen", "int", "id de la interaccion que lo origino",
                             obligatorio=False)),
        fn=_fn_crear_compromiso_p9),
}
