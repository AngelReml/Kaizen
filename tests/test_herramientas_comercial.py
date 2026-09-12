# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del director de Comercial (panel_mando/herramientas/
comercial.py). Cada ToolSpec se prueba construyendo el objeto real del departamento
(PipelineCanonico, Atribuidor, LeadStore, CuboComercial, sustrato.registro sobre una
BD SQLite temporal) e invocando fn/validar de verdad — nada de fakes salvo la llamada
LLM del detector de compromiso, que se sustituye por una funcion fija (coste real cero
en tests). R-TENANT: tenant sintetico 'laboratorio', jamas un tenant real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.comercial import cubo_serie_d as C
from departments.comercial.lifecycle import LeadStore
from departments.comercial.sdr import compromiso as compromiso_mod
from panel_mando.herramientas import comercial as M
from panel_mando.herramientas.base import ArgumentosInvalidos
from sustrato import bus as sbus
from sustrato import registro as p9

TENANT = "laboratorio"

LEAD_OK = {"id": "l1", "nombre_ref": "lead_sintetico_1",
           "fuentes": [{"url": "https://negocio.example", "fecha": "2026-07-01"}],
           "contacto": {"publicado_por_el_negocio": True}}


@pytest.fixture()
def k():
    return InMemoryKnowledge()


@pytest.fixture()
def b(k):
    return Bitacora(k, TENANT, fecha_alta="2026-07-10")


@pytest.fixture(autouse=True)
def _db_temporal(tmp_path, monkeypatch):
    """Todas las herramientas P9/P8 abren su propia conexion via sbus.conexion(),
    que respeta KAIZEN_DB_PATH — la redirigimos a una BD temporal SIEMPRE."""
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen_test.db"))
    return tmp_path


def _conn():
    return sbus.conexion()


# ── helpers de contrato: nombre coincide, clase valida ──────────────────────

def test_registro_interno_bien_formado():
    for nombre, spec in M.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert callable(spec.fn)


def test_nunca_wireadas_ausentes():
    """enviar_email, llamada_ia, alta_lead y registrar_pedido NO deben estar
    registradas — frontera deliberada (ver docstring del modulo)."""
    for prohibida in ("enviar_email", "llamada_ia", "alta_lead", "registrar_pedido_p9",
                      "registrar_pedido"):
        assert prohibida not in M.HERRAMIENTAS


def test_ninguna_irreversible_externa_registrada():
    assert not [s for s in M.HERRAMIENTAS.values() if s.clase == "IRREVERSIBLE-EXTERNA"]


# ── LECTURA ──────────────────────────────────────────────────────────────

def test_salud_cubo(k):
    spec = M.HERRAMIENTAS["salud_cubo"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["cubo"] == "comercial"
    assert r["estado"] in ("OK", "DEGRADADO", "ERROR")
    assert set(r["contadores"]) == {"leads", "compromisos_pendientes", "eventos_publicados_24h"}


def test_lead_canonico(k, b):
    C.PipelineCanonico(k, TENANT, bitacora=b).alta_lead(LEAD_OK)
    spec = M.HERRAMIENTAS["lead_canonico"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"lead_id": "l1"}))
    assert r["id"] == "l1" and r["estado"] == "COLD"


def test_lead_canonico_inexistente_sube_la_excepcion(k, b):
    spec = M.HERRAMIENTAS["lead_canonico"]
    with pytest.raises(KeyError):
        spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"lead_id": "no-existe"}))


def test_en_lista_exclusion(k, b):
    p = C.PipelineCanonico(k, TENANT, bitacora=b)
    p.alta_lead(LEAD_OK)
    k.add(TENANT, "lead_pii", "l1", {"email": "optout@sintetico.example"})
    p.opt_out("l1")
    spec = M.HERRAMIENTAS["en_lista_exclusion"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"email_o_id": "optout@sintetico.example"}))
    assert r["en_exclusion"] is True
    r2 = spec.fn(k=k, tenant=TENANT, bitacora=b,
                **spec.validar({"email_o_id": "nadie@sintetico.example"}))
    assert r2["en_exclusion"] is False


def test_bloques_obligatorios_ausentes():
    spec = M.HERRAMIENTAS["bloques_obligatorios_ausentes"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None, **spec.validar({"cuerpo": "hola, compra pan"}))
    assert set(r["bloques_ausentes"]) == {"identificacion", "baja", "derechos"}
    cuerpo_legal = ("Buenos dias, le escribe el equipo comercial. "
                    "Si no desea recibir mas mensajes, responda BAJA. "
                    "Puede ejercer sus derechos de acceso segun RGPD.")
    r2 = spec.fn(k=None, tenant=TENANT, bitacora=None, **spec.validar({"cuerpo": cuerpo_legal}))
    assert r2["bloques_ausentes"] == []


def test_ranking_argumentos(k, b):
    C.asiento_p8(k, TENANT, bitacora=b, segmento="gourmet", argumento_id="arg_cercania",
                canal="EMAIL", secuencia="INICIAL", resultado="PEDIDO")
    C.asiento_p8(k, TENANT, bitacora=b, segmento="gourmet", argumento_id="arg_precio",
                canal="EMAIL", secuencia="INICIAL", resultado="NEGATIVA")
    spec = M.HERRAMIENTAS["ranking_argumentos"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"segmento": "gourmet"}))
    assert r["ranking"][0]["argumento_id"] == "arg_cercania"


def test_conteo_por_estado(k):
    store = LeadStore(k, TENANT)
    store.crear("l1", {"nombre": "Cafe Uno"})
    store.crear("l2", {"nombre": "Cafe Dos"})
    spec = M.HERRAMIENTAS["conteo_por_estado"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["identificado"] == 2


def test_cuadro_metricas_fase0(k):
    store = LeadStore(k, TENANT)
    store.crear("l1", {"nombre": "Cafe Uno"})
    spec = M.HERRAMIENTAS["cuadro_metricas_fase0"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert "metricas" in r and "gates_fase0" in r
    assert "__superados__" in r["gates_fase0"]


def test_agregados_y_ranking_p8():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    from cubos.comercial import p8_bucle
    p8_bucle.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    for _ in range(3):
        p9.insertar_interaccion(conn, "l1", "email", "interes", cliente_id=TENANT,
                                argumento_id="arg_x")
    conn.close()

    spec_a = M.HERRAMIENTAS["agregados_p8"]
    ra = spec_a.fn(k=None, tenant=TENANT, bitacora=None, **spec_a.validar({}))
    assert any(f["argumento_id"] == "arg_x" and f["avanza"] == 3 for f in ra["agregados"])

    spec_r = M.HERRAMIENTAS["ranking_p8"]
    rr = spec_r.fn(k=None, tenant=TENANT, bitacora=None, **spec_r.validar({"segmento": "otro"}))
    assert any(f["argumento_id"] == "arg_x" for f in rr["ranking"])


def test_evaluar_compromiso_reciproco(monkeypatch):
    monkeypatch.setattr(compromiso_mod.ai, "chat", lambda *a, **kw: (
        '{"es_compromiso": true, "confianza": 0.9, "senales_detectadas": ["puedo tomar una muestra"], '
        '"motivo": "pide muestra", "recomendacion": "escalar_account_executive"}'))
    spec = M.HERRAMIENTAS["evaluar_compromiso_reciproco"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"texto_respuesta": "puedo tomar una muestra?"}))
    assert r["es_compromiso"] is True and r["confianza"] == 0.9


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def test_cerrar_compromiso_p9():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    cid = p9.crear_compromiso(conn, "l1", "callback", "llamar de nuevo", "2026-09-01")
    conn.close()

    spec = M.HERRAMIENTAS["cerrar_compromiso_p9"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"compromiso_id": cid, "estado": "cumplido"}))
    assert r == {"compromiso_id": cid, "estado": "cumplido"}
    conn2 = _conn()
    fila = conn2.execute("SELECT estado FROM compromisos WHERE id=?", (cid,)).fetchone()
    conn2.close()
    assert fila[0] == "cumplido"


def test_cerrar_compromiso_p9_estado_invalido_sube_la_excepcion():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    cid = p9.crear_compromiso(conn, "l1", "callback", "llamar de nuevo", "2026-09-01")
    conn.close()
    spec = M.HERRAMIENTAS["cerrar_compromiso_p9"]
    with pytest.raises(ValueError):
        spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"compromiso_id": cid, "estado": "en_el_limbo"}))


# ── IRREVERSIBLE-INTERNA ─────────────────────────────────────────────────

def test_transicionar_pipeline_canonico(k, b):
    C.PipelineCanonico(k, TENANT, bitacora=b).alta_lead(LEAD_OK)
    spec = M.HERRAMIENTAS["transicionar_pipeline_canonico"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"lead_id": "l1", "a": "CONTACTADO", "disparador": "SISTEMA"}))
    assert r["estado"] == "CONTACTADO"


def test_transicionar_pipeline_canonico_fuera_de_grafo_sube_la_excepcion(k, b):
    C.PipelineCanonico(k, TENANT, bitacora=b).alta_lead(LEAD_OK)
    spec = M.HERRAMIENTAS["transicionar_pipeline_canonico"]
    with pytest.raises(C.TransicionRechazada):
        spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"lead_id": "l1", "a": "CUSTOMER", "disparador": "SISTEMA"}))


def test_opt_out_lead(k, b):
    C.PipelineCanonico(k, TENANT, bitacora=b).alta_lead(LEAD_OK)
    spec = M.HERRAMIENTAS["opt_out_lead"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"lead_id": "l1"}))
    assert r["estado"] == "EXCLUIDO"
    assert C.PipelineCanonico(k, TENANT, bitacora=b).en_lista_exclusion("l1") is True


def test_atribuir_pedido_registro_externo_queda_pendiente(k, b):
    C.PipelineCanonico(k, TENANT, bitacora=b).alta_lead(LEAD_OK)
    spec = M.HERRAMIENTAS["atribuir_pedido"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"pedido_id": "ped1", "lead_id": "l1", "via": "REGISTRO_EXTERNO"}))
    assert r["estado"] == "PENDIENTE_VALIDACION"


def test_atribuir_pedido_lead_inexistente_sube_la_excepcion(k, b):
    spec = M.HERRAMIENTAS["atribuir_pedido"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"pedido_id": "ped1", "lead_id": "no-existe",
                               "via": "REGISTRO_EXTERNO"}))


def test_asiento_p8_telemetria(k, b):
    spec = M.HERRAMIENTAS["asiento_p8_telemetria"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"segmento": "gourmet", "argumento_id": "arg_x",
                               "canal": "EMAIL", "secuencia": "INICIAL",
                               "resultado": "POSITIVA"}))
    assert r["resultado"] == "POSITIVA" and r["argumento_id"] == "arg_x"


def test_transicionar_lead_p9():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    conn.close()
    spec = M.HERRAMIENTAS["transicionar_lead_p9"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"lead_id": "l1", "a": "CONTACTADO", "motivo": "primer intento"}))
    assert r["estado_actual"] == "CONTACTADO"


def test_transicionar_lead_p9_forzar_operador_nunca_expuesto():
    """El argumento _forzar_operador NO esta declarado: si el LLM intenta colarlo,
    ArgumentosInvalidos lo rechaza antes de llegar a fn."""
    spec = M.HERRAMIENTAS["transicionar_lead_p9"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"lead_id": "l1", "a": "COLD", "_forzar_operador": True})


def test_transicionar_lead_p9_ilegal_sube_la_excepcion():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    conn.close()
    spec = M.HERRAMIENTAS["transicionar_lead_p9"]
    with pytest.raises(p9.TransicionIlegal):
        spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"lead_id": "l1", "a": "CLIENTE"}))


def test_insertar_interaccion_p9():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    conn.close()
    spec = M.HERRAMIENTAS["insertar_interaccion_p9"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"lead_id": "l1", "canal": "llamada_manual", "resultado": "interes"}))
    assert r["interaccion_id"] > 0


def test_crear_compromiso_p9():
    conn = _conn()
    sbus.instalar(conn)
    p9.instalar(conn)
    p9.insertar_lead(conn, id="l1", nombre="Cafe Uno", segmento="otro", prioridad="ALTA",
                     cliente_id=TENANT)
    conn.close()
    spec = M.HERRAMIENTAS["crear_compromiso_p9"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"lead_id": "l1", "tipo": "callback",
                               "descripcion": "llamar de nuevo", "fecha_limite": "2026-09-01"}))
    assert r["compromiso_id"] > 0


# ── validacion de argumentos: rechazo honesto, no coercion silenciosa ──────

@pytest.mark.parametrize("nombre_herramienta", list(M.HERRAMIENTAS))
def test_argumento_desconocido_rechazado_en_todas(nombre_herramienta):
    spec = M.HERRAMIENTAS[nombre_herramienta]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"intruso_no_declarado": "x"})


@pytest.mark.parametrize("nombre_herramienta", [n for n, s in M.HERRAMIENTAS.items()
                                                if any(a.obligatorio for a in s.argumentos)])
def test_argumento_obligatorio_ausente_rechazado(nombre_herramienta):
    spec = M.HERRAMIENTAS[nombre_herramienta]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({})
