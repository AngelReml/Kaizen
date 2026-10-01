# -*- coding: utf-8 -*-
"""Mundo — /mundo, /api/mundo/estado y /api/mundo/rio (panel_mando/mundo.py).

Solo lectura: proyeccion del sustrato para el juego isometrico. Datos SOLO
sinteticos (tenant `laboratorio`, BD del bus en tmp via KAIZEN_DB_PATH); sin
red y sin modelo. Contrato: docs/CONTRATO_MUNDO.md."""
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core.aprobaciones import ColaSustrato
from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora, Sobre
from panel_mando import colmena as CLM
from panel_mando import mundo as MND
from panel_mando.app import crear_app
from sustrato import bus

EMPRESA = "laboratorio"
XSS = "x';alert(1)//"
RARO = 'comillas "dobles" \'simples\' <script>alert(1)</script>\nsalto\tTAB   ñ'


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)
    return tmp_path


def _montaje(mecha_s=0, token=None):
    k = InMemoryKnowledge()
    app = crear_app(k, token=token, mecha_s=mecha_s)
    b = Bitacora(k, EMPRESA, fecha_alta="2026-07-10")
    app.state.bitacoras[EMPRESA] = b
    app.state.colas[EMPRESA] = ColaSustrato(k, EMPRESA, bitacora=b)
    return app, TestClient(app, raise_server_exceptions=False), b


def _rue(b, tipo, payload=None):
    b.publicar(Sobre(tenant_id=EMPRESA, tipo=tipo, payload=payload or {}, origen="test"))


def _bus(topic, payload=None):
    conn = bus.conexion()
    bus.instalar(conn)
    try:
        return bus.publicar(conn, topic, "test", payload or {})
    finally:
        conn.close()


def _estado(c, empresa=EMPRESA):
    r = c.get("/api/mundo/estado", params={"empresa": empresa})
    assert r.status_code == 200, r.text
    return r.json()


def _sse(c, **params):
    params.setdefault("empresa", EMPRESA)
    params.setdefault("ciclos", 1)
    r = c.get("/api/mundo/rio", params=params)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]
    return evs, r.text


def _filas_agentes():
    conn = sqlite3.connect(os.environ["KAIZEN_DB_PATH"])
    try:
        hay = conn.execute("SELECT 1 FROM sqlite_master WHERE name='colmena_agentes'").fetchone()
        return None if hay is None else conn.execute(
            "SELECT COUNT(*) FROM colmena_agentes").fetchone()[0]
    finally:
        conn.close()


CLAVES_EVENTO = {"canal", "id", "tipo", "cubo", "frase", "ts", "aprobacion"}


# ── /mundo: pagina, auth, validacion ─────────────────────────────────────────

def test_mundo_sirve_el_fichero_sin_cache(entorno, monkeypatch):
    (entorno / "mundo").mkdir()
    (entorno / "mundo" / "index.html").write_text("<html>hola mundo</html>", encoding="utf-8")
    monkeypatch.setattr(MND, "RAIZ", entorno)
    _, c, _ = _montaje()
    r = c.get("/mundo")
    assert r.status_code == 200 and "hola mundo" in r.text
    assert r.headers["cache-control"] == "no-store"
    # se lee en cada peticion: un cambio en disco se ve sin reiniciar
    (entorno / "mundo" / "index.html").write_text("<html>otra version</html>", encoding="utf-8")
    assert "otra version" in c.get("/mundo").text


def test_mundo_sin_fichero_da_404_claro(entorno, monkeypatch):
    monkeypatch.setattr(MND, "RAIZ", entorno)          # tmp sin mundo/
    _, c, _ = _montaje()
    r = c.get("/mundo")
    assert r.status_code == 404 and "mundo/index.html" in r.text


def test_mundo_sin_sesion_redirige_a_login(entorno):
    _, c, _ = _montaje(token="secreto-sintetico")
    r = c.get("/mundo", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_mundo_con_token_pasa(entorno, monkeypatch):
    (entorno / "mundo").mkdir()
    (entorno / "mundo" / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    monkeypatch.setattr(MND, "RAIZ", entorno)
    _, c, _ = _montaje(token="secreto-sintetico")
    assert c.get("/mundo", headers={"X-Token": "secreto-sintetico"}).status_code == 200


def test_mundo_empresa_invalida_400(entorno, monkeypatch):
    (entorno / "mundo").mkdir()
    (entorno / "mundo" / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    monkeypatch.setattr(MND, "RAIZ", entorno)
    _, c, _ = _montaje()
    r = c.get("/mundo", params={"empresa": XSS})
    assert r.status_code == 400 and "alert(1)" not in r.text


def test_api_exige_auth(entorno):
    _, c, _ = _montaje(token="secreto-sintetico")
    assert c.get("/api/mundo/estado").status_code == 401
    assert c.get("/api/mundo/rio?ciclos=1").status_code == 401
    h = {"X-Token": "secreto-sintetico"}
    assert c.get("/api/mundo/estado", headers=h).status_code == 200
    assert c.get("/api/mundo/rio?ciclos=1", headers=h).status_code == 200


def test_estado_y_rio_empresa_invalida_400(entorno):
    _, c, _ = _montaje()
    assert c.get("/api/mundo/estado", params={"empresa": XSS}).status_code == 400
    assert c.get("/api/mundo/rio", params={"empresa": XSS, "ciclos": 1}).status_code == 400


# ── /api/mundo/estado ────────────────────────────────────────────────────────

def test_estado_tenant_vacio(entorno):
    _, c, _ = _montaje()
    j = _estado(c)
    assert j["empresa"] == EMPRESA and EMPRESA in j["empresas"]
    assert j["ahora"].endswith("Z") and j["parado"] is False
    assert j["tenant"]["estado"] in ("activo", "pausado", "baja", "desconocido")
    assert j["cubos"] and all(x["alta"] is False and x["uid"] is None for x in j["cubos"])
    assert j["sello"]["integra"] is True and j["sello"]["pasos"] == 0
    assert j["tarjetas"] == {"pendientes": 0, "en_manos": 0, "mechas": []}
    assert j["cursores"] == {"rue": -1, "bus": 0, "chat": 0} and j["recientes"] == []


def test_estado_defecto_es_la_primera_empresa(entorno):
    _, c, _ = _montaje()
    assert c.get("/api/mundo/estado").json()["empresa"] == EMPRESA


def test_cubos_uno_por_manifest_en_orden_de_colmena(entorno):
    _, c, _ = _montaje()
    nombres = [x["cubo"] for x in _estado(c)["cubos"]]
    instalados = set(CLM._manifiestos())
    assert set(nombres) == instalados
    esperado = [x for x in CLM.CUBOS_ORDEN if x in instalados] + \
        sorted(instalados - set(CLM.CUBOS_ORDEN))
    assert nombres == esperado
    x = _estado(c)["cubos"][0]
    assert x["nombre"] == CLM.NOMBRES.get(x["cubo"], x["cubo"])
    assert set(x) >= {"cubo", "nombre", "mision", "autonomia", "irreversibles",
                      "nota_estado", "alta", "uid", "role_id", "ts_alta", "salud", "ultimo"}
    assert set(x["salud"]) == {"estado", "detalle", "eventos_24h"}


def test_estado_no_crea_tablas_ni_agentes(entorno):
    _, c, _ = _montaje()
    assert _filas_agentes() is None
    _estado(c)
    _estado(c)
    assert _filas_agentes() is None            # ni siquiera la tabla


def test_estado_tras_alta_de_directores(entorno):
    _, c, _ = _montaje()
    assert c.get(f"/api/colmena/agentes?empresa={EMPRESA}").status_code == 200   # UNA vez
    antes = _filas_agentes()
    assert antes == len(CLM.CUBOS_ORDEN)
    j = _estado(c)
    assert _estado(c) is not None
    assert _filas_agentes() == antes           # leer el estado NO da de alta nada
    for x in j["cubos"]:
        if x["cubo"] in CLM.CUBOS_ORDEN:
            assert x["alta"] is True and x["uid"].startswith("KZ-")
            assert x["role_id"] == f"director_{x['cubo']}" and x["ts_alta"]


def test_estado_otra_empresa_no_ve_altas_ajenas(entorno):
    _, c, _ = _montaje()
    c.get(f"/api/colmena/agentes?empresa={EMPRESA}")
    assert all(x["alta"] is False for x in _estado(c, "otra_sintetica")["cubos"])


def test_ultimo_mensaje_del_director(entorno):
    _, c, _ = _montaje()
    c.get(f"/api/colmena/agentes?empresa={EMPRESA}")
    conn = CLM._conn()
    try:
        sid = conn.execute("SELECT id FROM colmena_sesiones WHERE empresa=? AND tipo='individual' "
                           "AND cubo='brand'", (EMPRESA,)).fetchone()[0]
        CLM._insertar_mensaje(conn, sid, "director", "director_brand", "Listo el informe")
    finally:
        conn.close()
    por = {x["cubo"]: x for x in _estado(c)["cubos"]}
    assert por["brand"]["ultimo"]["texto"] == "Listo el informe" and por["brand"]["ultimo"]["ts"]
    assert por["comercial"]["ultimo"] is None


def test_salud_reflejada(entorno, monkeypatch):
    _, c, _ = _montaje()
    monkeypatch.setattr(CLM, "_salud_cubo", lambda conn, cubo, **kw: {
        "cubo": cubo, "estado": "DEGRADADO", "detalle": "prueba <b>", "contadores": {
            "eventos_publicados_24h": 7}})
    x = _estado(c)["cubos"][0]
    assert x["salud"] == {"estado": "DEGRADADO", "detalle": "prueba <b>", "eventos_24h": 7}


def test_salud_real_cuenta_eventos_del_bus(entorno):
    _, c, _ = _montaje()
    _bus("kaizen.brand.revision_emitida.v1", {"x": 1})
    por = {x["cubo"]: x for x in _estado(c)["cubos"]}
    assert por["brand"]["salud"]["eventos_24h"] >= 1
    assert por["brand"]["salud"]["estado"] in ("OK", "DEGRADADO", "ERROR", "SIN DATOS")


def test_dinero_coherente_con_api_dinero(entorno):
    _, c, _ = _montaje()
    assert _estado(c)["dinero"] == c.get(f"/api/dinero/{EMPRESA}").json()


def test_tarjetas_pendientes_y_en_mecha(entorno):
    app, c, _ = _montaje(mecha_s=3600)
    cola = app.state.colas[EMPRESA]
    n = cola.solicitar(cubo="comercial", accion="enviar email inicial a candidato",
                       clase="IRREVERSIBLE-EXTERNA", contenido_ref="borrador_x")
    assert _estado(c)["tarjetas"] == {"pendientes": 1, "en_manos": 0, "mechas": []}
    r = c.post("/cmd/aprobar", json={"empresa": EMPRESA, "id": n["id"], "quien": "operador"})
    assert r.json()["estado"] == "EN_MECHA"
    t = _estado(c)["tarjetas"]
    assert t["pendientes"] == 0 and len(t["mechas"]) == 1
    assert t["mechas"][0] == {"aprobacion": n["id"], "dispara": r.json()["dispara"],
                              "accion": "enviar email inicial a candidato", "cubo": "comercial"}
    c.post("/cmd/deshacer", json={"empresa": EMPRESA, "id": n["id"], "quien": "operador"})
    assert _estado(c)["tarjetas"] == {"pendientes": 0, "en_manos": 0, "mechas": []}


def test_parado_tras_parar_todo_y_reanudar(entorno):
    _, c, _ = _montaje()
    c.post("/cmd/parar_todo", json={"quien": "operador", "motivo": "prueba"})
    assert _estado(c)["parado"] is True
    c.post("/cmd/reanudar", json={"quien": "operador"})
    assert _estado(c)["parado"] is False


def test_sello_integro_con_eventos_y_roto_si_se_manipula(entorno):
    app, c, b = _montaje()
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    _rue(b, "operacion.pedido.confirmado")
    assert _estado(c)["sello"]["integra"] is True and _estado(c)["sello"]["pasos"] == 2
    ev = app.state.k.get(EMPRESA, "evento", "000000000001")
    ev["payload"] = {"manipulado": True}
    app.state.k.add(EMPRESA, "evento", "000000000001", ev)
    s = _estado(c)["sello"]
    assert s["integra"] is False and "paso 1" in s["mensaje"]


def test_cursores_y_recientes_ordenados_y_acotados(entorno):
    _, c, b = _montaje()
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    _rue(b, "operacion.pedido.confirmado")
    ultimo_bus = _bus("kaizen.brand.revision_emitida.v1")
    j = _estado(c)
    assert j["cursores"] == {"rue": 1, "bus": ultimo_bus, "chat": 0}
    assert len(j["recientes"]) == 3
    assert {e["canal"] for e in j["recientes"]} == {"rue", "bus"}
    assert all(set(e) == CLAVES_EVENTO for e in j["recientes"])
    ts = [MND._clave_ts(e)[0] for e in j["recientes"]]
    assert ts == sorted(ts)
    for i in range(50):
        _bus("kaizen.finanzas.cierre_registrado.v1", {"i": i})
    assert len(_estado(c)["recientes"]) == MND.LIMITE_RECIENTES


# ── /api/mundo/rio (SSE) ─────────────────────────────────────────────────────

def test_rio_une_rue_y_bus_con_formato_unificado(entorno):
    _, c, b = _montaje()
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    idb = _bus("kaizen.brand.revision_emitida.v1")
    evs, texto = _sse(c)
    assert ": latido" in texto
    assert all(set(e) == CLAVES_EVENTO for e in evs)
    rue = next(e for e in evs if e["canal"] == "rue")
    bus_ev = next(e for e in evs if e["canal"] == "bus")
    assert rue["id"] == 0 and rue["tipo"] == "comercial.lead.descubierto" and rue["cubo"] == "comercial"
    assert "encontre un negocio candidato" in rue["frase"] and rue["aprobacion"] is None
    assert bus_ev["id"] == idb and bus_ev["tipo"] == "kaizen.brand.revision_emitida.v1"
    assert bus_ev["cubo"] == "brand" and bus_ev["frase"] == "Marca: revision emitida"


def test_rio_cursores_independientes_y_sin_repetir(entorno):
    _, c, b = _montaje()
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    _rue(b, "operacion.pedido.confirmado")
    id1 = _bus("kaizen.brand.revision_emitida.v1")
    id2 = _bus("kaizen.finanzas.cierre_registrado.v1")
    evs, _ = _sse(c)
    assert len(evs) == 4
    # solo avanza el cursor de RUE: el bus sigue entero
    solo_bus, _ = _sse(c, desde_rue=1)
    assert [e["canal"] for e in solo_bus] == ["bus", "bus"]
    solo_rue, _ = _sse(c, desde_bus=id2)
    assert [e["canal"] for e in solo_rue] == ["rue", "rue"]
    # con ambos cursores al dia no hay nada
    assert _sse(c, desde_rue=1, desde_bus=id2)[0] == []
    # y un evento posterior aparece una sola vez
    id3 = _bus("kaizen.ops.plan_emitido.v1")
    nuevo, _ = _sse(c, desde_rue=1, desde_bus=id2)
    assert [(e["canal"], e["id"]) for e in nuevo] == [("bus", id3)] and id1 < id2 < id3


def test_rio_cursores_de_estado_no_repiten(entorno):
    _, c, b = _montaje()
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    _bus("kaizen.brand.revision_emitida.v1")
    cur = _estado(c)["cursores"]
    assert _sse(c, desde_rue=cur["rue"], desde_bus=cur["bus"])[0] == []


def test_rio_ciclos_sucesivos_no_repiten_dentro_de_un_stream(entorno):
    _, c, b = _montaje()
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    _bus("kaizen.brand.revision_emitida.v1")
    evs, texto = _sse(c, ciclos=3)
    assert len(evs) == 2 and texto.count(": latido") == 3


def test_rio_bus_ajeno_no_aparece(entorno):
    _, c, _ = _montaje()
    _bus("kaizen.finanzas.cierre_registrado.v1", {"empresa": "otra_sintetica", "secreto": "S3CR3T"})
    _bus("kaizen.finanzas.cierre_registrado.v1", {"empresa": EMPRESA})
    _bus("kaizen.finanzas.cierre_registrado.v1", {"sin_empresa": True})
    evs, texto = _sse(c)
    assert len(evs) == 2 and "S3CR3T" not in texto and "otra_sintetica" not in texto
    assert [e["id"] for e in evs] == [2, 3]
    assert [e["id"] for e in _estado(c)["recientes"]] == [2, 3]
    # pedir la otra empresa: ve la suya y las globales, no la de laboratorio
    otra, _ = _sse(c, empresa="otra_sintetica")
    assert [e["id"] for e in otra] == [1, 3]


def test_rio_cubo_por_prefijo_rue(entorno):
    _, c, b = _montaje()
    _rue(b, "operacion.pedido.confirmado")
    _rue(b, "cumplimiento.alerta.plazo", {"dias_restantes": 3})
    _rue(b, "brand.directriz.actualizada")
    _rue(b, "plataforma.panico.activado")
    _rue(b, "inteligencia.alerta.emitida", {"severidad": "ALTA", "metrica": "m"})
    por = {e["tipo"]: e["cubo"] for e in _sse(c)[0]}
    assert por == {"operacion.pedido.confirmado": "ops", "cumplimiento.alerta.plazo": "legal",
                   "brand.directriz.actualizada": "brand", "plataforma.panico.activado": None,
                   "inteligencia.alerta.emitida": "inteligencia"}


def test_rio_cubo_del_payload_gana_si_es_conocido(entorno):
    app, c, b = _montaje()
    cola = app.state.colas[EMPRESA]
    n = cola.solicitar(cubo="brand", accion="publicar guia", clase="IRREVERSIBLE-INTERNA")
    cola.aprobar(n["id"], por="operador")
    _rue(b, "plataforma.aprobacion.solicitada", {"cubo": "cubo_inventado", "accion": "x"})
    evs = _sse(c)[0]
    sol = [e for e in evs if e["tipo"] == "plataforma.aprobacion.solicitada"]
    assert sol[0]["cubo"] == "brand" and sol[0]["aprobacion"] == n["id"]
    assert sol[1]["cubo"] is None and sol[1]["aprobacion"] is None    # desconocido: ignorado
    conc = next(e for e in evs if e["tipo"] == "plataforma.aprobacion.concedida")
    assert conc["aprobacion"] == n["id"] and conc["cubo"] is None


def test_rio_topic_del_bus_colmena_y_cubos(entorno):
    _, c, _ = _montaje()
    _bus("kaizen.colmena.mensaje_registrado.v1")
    _bus("kaizen.legal.dictamen_emitido.v1")
    _bus("kaizen.cumplimiento.plazo_vencido.v1")
    evs = _sse(c)[0]
    assert [(e["cubo"], e["frase"]) for e in evs] == [
        (None, "Colmena: mensaje registrado"),
        ("legal", "Legal y Cumplimiento: dictamen emitido"),
        ("legal", "Legal y Cumplimiento: plazo vencido")]


def test_rio_tope_de_200_por_ciclo(entorno):
    _, c, _ = _montaje()
    conn = bus.conexion()
    bus.instalar(conn)
    for i in range(205):
        bus.publicar(conn, "kaizen.finanzas.cierre_registrado.v1", "test", {"i": i})
    conn.close()
    assert len(_sse(c, ciclos=1)[0]) == MND.LIMITE_POR_CICLO
    assert len(_sse(c, ciclos=2)[0]) == 205


def test_rio_quema_mechas_vencidas(entorno):
    app, c, b = _montaje(mecha_s=3600)
    cola = app.state.colas[EMPRESA]
    n = cola.solicitar(cubo="comercial", accion="enviar email", clase="IRREVERSIBLE-EXTERNA")
    c.post("/cmd/aprobar", json={"empresa": EMPRESA, "id": n["id"], "quien": "operador"})
    app.state.mechas.segundos = 0
    app.state.mechas.armar(n["id"], EMPRESA)               # vence al instante
    assert len(_estado(c)["tarjetas"]["mechas"]) == 1
    _sse(c)
    assert _estado(c)["tarjetas"]["mechas"] == []
    assert cola._get(n["id"])["estado"] != "APROBADA"


def test_json_parseable_con_caracteres_raros(entorno):
    _, c, b = _montaje()
    _rue(b, "plataforma.aprobacion.solicitada", {"accion": RARO})
    evs, texto = _sse(c)
    assert evs[0]["frase"] == f"pedi permiso para: {RARO}"
    # el salto de linea del texto no rompe el framing SSE: una sola linea `data:`
    assert sum(1 for l in texto.splitlines() if l.startswith("data: ")) == 1
    rec = _estado(c)["recientes"]
    assert rec[0]["frase"] == evs[0]["frase"]


def test_primer_evento_tras_estado_vacio_no_se_pierde(entorno):
    """Regresion: la cadena RUE empieza en n=0; con el cursor de un tenant vacio en 0 el primer
    evento (id 0) quedaba «ya visto» y el Mundo se lo perdia."""
    _, c, b = _montaje()
    cur = _estado(c)["cursores"]
    _rue(b, "comercial.lead.descubierto", {"lead_ref": "l1"})
    r = c.get(f"/api/mundo/rio?empresa=laboratorio&desde_rue={cur['rue']}&desde_bus={cur['bus']}&ciclos=1")
    datos = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]
    assert [d["id"] for d in datos if d["canal"] == "rue"] == [0]


# ── RRHH: el juego cuenta lo mismo que el cubo RRHH ──────────────────────────

def test_estado_incluye_el_mapa_y_las_propuestas_de_rrhh(entorno):
    _, c, _ = _montaje()
    j = _estado(c)
    m = j["rrhh"]["mapa"]
    assert len(m["faltantes"]) == len(j["cubos"]) and m["presentes"] == [] and m["cobertura"] == 0.0
    assert j["rrhh"]["propuestas"][0].startswith("Dar de alta el director de")
    c.get("/api/colmena/agentes", params={"empresa": EMPRESA})           # alta real de los directores
    j2 = _estado(c)
    m2 = j2["rrhh"]["mapa"]
    assert m2["faltantes"] == [] and m2["cobertura"] == 1.0
    assert "Sin huecos" in j2["rrhh"]["propuestas"][0]
    # mismo resultado que la funcion pura de la herramienta de RRHH (no una copia)
    from panel_mando.herramientas import rrhh as RRHH
    assert m2 == RRHH.mapa_desde([x["cubo"] for x in j2["cubos"]], [x["cubo"] for x in j2["cubos"] if x["alta"]])


# ── chat de la Colmena: los directores hablan en el juego ────────────────────

def _sesion(cubo):
    conn = CLM._conn()
    try:
        tipo, c = ("sala", "") if cubo is None else ("individual", cubo)
        return conn.execute("SELECT id FROM colmena_sesiones WHERE empresa=? AND tipo=? AND cubo=?",
                            (EMPRESA, tipo, c)).fetchone()[0]
    finally:
        conn.close()


def _mensaje(cubo, autor_tipo, autor_id, texto):
    conn = CLM._conn()
    try:
        return CLM._insertar_mensaje(conn, _sesion(cubo), autor_tipo, autor_id, texto)
    finally:
        conn.close()


def test_rio_emite_el_chat_de_directores_y_operador_sin_notas_de_sistema(entorno):
    _, c, _ = _montaje()
    c.get("/api/colmena/agentes", params={"empresa": EMPRESA})
    _mensaje("comercial", "operador", "operador", "como va el pipeline?")
    m2 = _mensaje("comercial", "director", "director_comercial", "Hay 12 leads en frio.")
    _mensaje("comercial", "sistema", "colmena", "nota interna")                       # no debe salir
    m4 = _mensaje(None, "director", "director_marketing", "Propongo pausar la campana.")   # sala
    evs, _ = _sse(c, desde_chat=-1)
    chat = [e for e in evs if e["canal"] == "chat"]
    assert [(e["tipo"], e["cubo"]) for e in chat] == [
        ("colmena.individual.operador", None),
        ("colmena.individual.director", "comercial"),
        ("colmena.sala.director", "marketing")]
    assert chat[0]["frase"] == "Tú: como va el pipeline?" and chat[1]["frase"] == "Hay 12 leads en frio."
    assert all(set(e) == CLAVES_EVENTO for e in chat)
    # el cursor de chat no repite y el de estado empalma sin huecos
    assert not [e for e in _sse(c, desde_chat=m4)[0] if e["canal"] == "chat"]
    assert _estado(c)["cursores"]["chat"] == m4
    assert [e["id"] for e in _sse(c, desde_chat=m2)[0] if e["canal"] == "chat"] == [m4]


def test_chat_sin_tablas_de_colmena_no_emite_ni_crea_nada(entorno):
    _, c, _ = _montaje()
    evs, _ = _sse(c)
    assert not [e for e in evs if e["canal"] == "chat"]
    assert _estado(c)["cursores"]["chat"] == 0 and _filas_agentes() is None


def test_estado_trae_rendimiento_por_cubo_y_nadie_tiene_grado_sin_datos(entorno):
    app, c, b = _montaje()
    j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
    assert j["cubos"] and all("rendimiento" in x for x in j["cubos"])
    assert all(x["rendimiento"]["rango"] is None for x in j["cubos"])        # tenant vacio: no se inventa ningun grado
    assert all(x["rendimiento"]["motivo"] for x in j["cubos"])


def test_comercial_trae_el_embudo_solo_con_numeros(entorno):
    app, c, b = _montaje()
    j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
    com = next(x for x in j["cubos"] if x["cubo"] == "comercial")
    assert com["pipeline"]["leads"]["COLD"] == 0 and com["pipeline"]["pedidos"] == {"atribuidos": 0, "pendientes_validacion": 0}
    assert all("pipeline" not in x for x in j["cubos"] if x["cubo"] != "comercial")
    k = b.k if hasattr(b, "k") else None
    if k is not None:
        for i in range(3):
            k.add(EMPRESA, "lead_canon", f"l{i}", {"id": f"l{i}", "estado": "COLD" if i < 2 else "CONVERSACION", "contacto": {"email": "secreto@x.es"}})
        j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
        com = next(x for x in j["cubos"] if x["cubo"] == "comercial")
        assert com["pipeline"]["leads"]["COLD"] == 2 and com["pipeline"]["leads"]["CONVERSACION"] == 1
        assert "secreto" not in json.dumps(j)                      # solo numeros: ningun dato de personas


def test_marketing_trae_campanas_y_contenidos_solo_como_numeros(entorno):
    app, c, b = _montaje()
    k = b.k
    k.add(EMPRESA, "campana", "c1", {"id": "c1", "nombre": "SECRETO-NOMBRE", "estado": "ACTIVA", "presupuesto_eur": 100.0, "gasto_reportado_eur": 50.0, "metricas": []})
    k.add(EMPRESA, "contenido_mkt", "t1", {"id": "t1", "estado": "VALIDADO_POR_BRAND", "texto": "SECRETO-TEXTO"})
    j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
    mk = next(x for x in j["cubos"] if x["cubo"] == "marketing")["marketing"]
    assert mk["campanas"]["ACTIVA"] == 1 and mk["contenidos"]["VALIDADO_POR_BRAND"] == 1
    assert mk["gasto"] == [{"estado": "ACTIVA", "pct": 0.5}] and mk["kill_switch_pct"] == 0.9
    assert "SECRETO" not in json.dumps(j)


def test_marca_trae_veredictos_y_directrices_solo_como_numeros(entorno):
    app, c, b = _montaje()
    for v in ("APTO", "APTO", "NO_APTO"):
        _rue(b, "plataforma.verificacion.emitida", {"veredicto": v, "hash": "h", "contenido_ref": "SECRETO-REF"})
    b.k.add(EMPRESA, "directriz", "d1", {"id": "d1", "regla": "SECRETO-REGLA", "estado": "ACTIVA"})
    j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
    m = next(x for x in j["cubos"] if x["cubo"] == "brand")["marca"]
    assert m["veredictos"] == {"APTO": 2, "NO_APTO": 1, "AMBIGUO": 0} and m["directrices"] == {"ACTIVA": 1}
    assert "SECRETO" not in json.dumps(j)
    ev = [e for e in j["recientes"] if e["tipo"] == "plataforma.verificacion.emitida"]
    assert ev and ev[-1]["veredicto"] == "NO_APTO" and "SECRETO" not in json.dumps(ev)


def test_legal_trae_plazos_y_archivo_solo_como_numeros(entorno):
    from datetime import datetime, timedelta, timezone
    app, c, b = _montaje()
    k = b.k; ahora = datetime.now(timezone.utc)
    for i, (est, dias) in enumerate([("ASIGNADA", 5), ("REGISTRADA", 40), ("CUMPLIDA", -3), ("INCUMPLIDA", -10)]):
        k.add(EMPRESA, "obligacion", f"o{i}", {"id": f"o{i}", "nombre": "SECRETO-NOMBRE", "area": "SECRETO-AREA", "tipo": "REGULATORIA", "estado": est,
                                               "fecha_limite": (ahora + timedelta(days=dias, hours=1)).isoformat(), "evidencias": []})
    k.add(EMPRESA, "evidencia", "e1", {"id": "e1", "nombre_fichero": "SECRETO.pdf"})
    j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
    lg = next(x for x in j["cubos"] if x["cubo"] == "legal")["legal"]
    assert lg["obligaciones"]["ASIGNADA"] == 1 and lg["obligaciones"]["CUMPLIDA"] == 1 and lg["evidencias"] == 1
    assert [p["dias"] for p in lg["plazos"]] == [-99, 5, 40]                      # la incumplida primero, luego por cercania; la cumplida no es un plazo
    assert "SECRETO" not in json.dumps(j)


def test_pulso_ops_e_inteligencia_solo_numeros(entorno):
    app, c, b = _montaje()
    k = b.k
    _bus("kaizen.qa.validacion_emitida.v1")
    _rue(b, "operacion.pedido.confirmado", {})
    k.add(EMPRESA, "pedido_ops", "p1", {"id": "p1", "estado": "CONFIRMADO", "cliente": "SECRETO-CLIENTE"})
    k.add(EMPRESA, "capacidad", "2026-10-02", {"fecha": "2026-10-02"})
    k.add(EMPRESA, "alerta", "a1", {"alerta_id": "a1", "estado": "EMITIDA", "metrica": "SECRETO-METRICA", "valor": 123456})
    k.add(EMPRESA, "umbral", "m", {"version": 1})
    j = c.get(f"/api/mundo/estado?empresa={EMPRESA}").json()
    por = {x["cubo"]: x for x in j["cubos"]}
    assert por["ops"]["ops"] == {"pedidos": {"PENDIENTE_CONFIRMACION": 0, "CONFIRMADO": 1, "EN_PRODUCCION": 0, "RETENIDO": 0, "COMPLETADO": 0, "ENTREGADO_A_LOGISTICA": 0, "RECHAZADO": 0}, "dias_con_capacidad": 1}
    assert por["inteligencia"]["inteligencia"] == {"alertas": {"EMITIDA": 1}, "umbrales": 1}
    assert por["qa"]["pulso"]["total"] == 1 and por["qa"]["pulso"]["dias"][-1] == 1 and len(por["qa"]["pulso"]["dias"]) == 14
    assert por["ops"]["pulso"]["total"] == 1
    assert por["rrhh"]["pulso"] == {"dias": [0] * 14, "total": 0}
    assert "SECRETO" not in json.dumps(j) and "123456" not in json.dumps(j["cubos"])


def test_autonomia_efectiva_se_refleja_en_el_mundo(entorno):
    """El nivel que muestra el mundo es el VIGENTE de la empresa (core/autonomia), no solo el
    defecto del manifest: tras endurecer, baja; otra empresa sigue con el defecto."""
    from core.autonomia import AutonomiaCubos
    app, c, b = _montaje()

    def nivel(cubo):
        return {x["cubo"]: x["autonomia"] for x in _estado(c)["cubos"]}[cubo]

    assert nivel("comercial") == "BAJA"
    AutonomiaCubos(b.k, EMPRESA, bitacora=b).endurecer(
        "comercial", "BAJA", causa="prueba", incidente="i1")
    assert nivel("comercial") == "CERO"
    assert nivel("legal") == "BAJA"                      # solo ese cubo
    assert b.verificar()["integra"] is True


def test_tarjetas_en_manos_se_cuentan_como_numero(entorno):
    """C1: una IRREVERSIBLE-EXTERNA aprobada y entregada al operador sale en la foto como
    numero, y la EVIDENCIA con que se confirma no viaja nunca al mundo (solo su huella, sellada)."""
    _, c, b = _montaje()
    cola = ColaSustrato(b.k, EMPRESA, bitacora=b)
    n = cola.solicitar(cubo="marketing", accion="publicar landing", clase="IRREVERSIBLE-EXTERNA")
    cola.aprobar(n["id"], por="angel")
    cola.entregar_a_humano(n["id"], por="angel")
    t = _estado(c)["tarjetas"]
    assert t["en_manos"] == 1 and t["pendientes"] == 0
    cola.confirmar_hecha(n["id"], por="angel", evidencia="evidencia privada")
    assert _estado(c)["tarjetas"]["en_manos"] == 0
    assert "privada" not in json.dumps(_estado(c))
