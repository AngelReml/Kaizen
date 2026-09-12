"""F1 — panel honesto y abrible (auditoria 2026-07-20: R-01 auth, R-07 dinero, R-08 panico).

Puerta F1, mitad maquina: con token definido, el navegador entra por /login y
navega con cookie de sesion (jamas un 401 con HTML delante del navegador);
PARAR TODO deja evento sellado en la bitacora y SOBREVIVE a un reinicio del
proceso; el dinero del panel refleja el gasto real (ledger persistente) y el
gasto legado sin atribuir se muestra, no se oculta. La mitad humana (R9) es de
Ivan: abrir CENTRO DE MANDO.cmd en su maquina.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from core.ledger import LedgerCoste
from core.panico import PanicoActivo
from core.rue import Bitacora
from core.techos import LibroCoste, TechoAlcanzado

from panel_mando.app import crear_app

CLAVE = "clave-de-prueba-f1"


def _montaje(tmp_path, *, token=CLAVE, con_solicitud=False):
    k = InMemoryKnowledge()
    app = crear_app(k, token=token, mecha_s=0,
                    ruta_panico=tmp_path / "panico" / "estado.json",
                    ruta_ledger=tmp_path / "coste" / "ledger.jsonl",
                    ruta_legacy_coste=tmp_path / "legacy.json")
    c = TestClient(app, raise_server_exceptions=False)
    n = None
    if con_solicitud:
        from core.aprobaciones import ColaSustrato
        b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
        cola = ColaSustrato(k, "laboratorio", bitacora=b)
        app.state.colas["laboratorio"] = cola
        app.state.bitacoras["laboratorio"] = b
        n = cola.solicitar(cubo="comercial", accion="enviar email inicial a candidato",
                           clase="IRREVERSIBLE-EXTERNA", contenido_ref="borrador_x")
    return app, c, k, n


def _entrar(c, clave=CLAVE):
    r = c.post("/login", data={"token": clave}, follow_redirects=False)
    # El CSRF esta ACTIVO por defecto desde la auditoria 2026-08-02 (G-05): una
    # sesion de navegador que hace POST debe mandar el token, igual que hace ya
    # el JS del panel. Se fija en el cliente para todas las peticiones que sigan.
    csrf = c.cookies.get("kz_csrf")
    if csrf:
        c.headers.update({"X-CSRF": csrf})
    return r


# ── R-01 · auth de navegador ──────────────────────────────────────────────────

def test_pagina_sin_credencial_redirige_a_login(tmp_path):
    _, c, _, _ = _montaje(tmp_path)
    for ruta in ("/", "/sala", "/sala/tecnico"):
        r = c.get(ruta, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
        assert "401" not in r.text                # jamas HTML tras cabecera imposible


def test_login_con_clave_entra_y_navega(tmp_path):
    _, c, _, _ = _montaje(tmp_path)
    r = _entrar(c)
    assert r.status_code == 303 and "kz_sesion" in r.headers.get("set-cookie", "")
    for ruta in ("/", "/sala", "/sala/tecnico"):
        assert c.get(ruta).status_code == 200     # la cookie navega sola
    assert c.get("/api/tarjetas/laboratorio").status_code == 200


def test_login_clave_mala_no_entra(tmp_path):
    _, c, _, _ = _montaje(tmp_path)
    r = _entrar(c, "clave-mala")
    assert r.status_code == 200 and "no es" in r.text     # re-formulario amable, sin sesion
    assert c.get("/", follow_redirects=False).status_code == 303


def test_login_un_toque_por_url(tmp_path):
    """El lanzador .cmd abre /login?token=... : un toque y dentro (R8)."""
    _, c, _, _ = _montaje(tmp_path)
    r = c.get(f"/login?token={CLAVE}", follow_redirects=False)
    assert r.status_code == 303 and "kz_sesion" in r.headers.get("set-cookie", "")
    assert c.get("/").status_code == 200


def test_api_json_sin_credencial_da_401_json(tmp_path):
    _, c, _, _ = _montaje(tmp_path)
    r = c.get("/api/tarjetas/laboratorio")
    assert r.status_code == 401 and "<html" not in r.text.lower()


def test_x_token_sigue_valiendo_para_api_y_tests(tmp_path):
    _, c, _, _ = _montaje(tmp_path)
    r = c.get("/api/tarjetas/laboratorio", headers={"X-Token": CLAVE})
    assert r.status_code == 200


def test_sin_token_definido_uso_local_abierto_como_siempre(tmp_path):
    _, c, _, _ = _montaje(tmp_path, token=None)
    assert c.get("/").status_code == 200
    r = c.get("/login", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"


# ── R-08 · PARAR TODO con rastro y persistente ───────────────────────────────

def test_parar_todo_deja_evento_sellado_y_reanudar_tambien(tmp_path):
    app, c, k, _ = _montaje(tmp_path, con_solicitud=True)
    _entrar(c)
    r = c.post("/cmd/parar_todo", json={"quien": "operador", "motivo": "prueba F1"})
    assert r.status_code == 200
    tipos = [e["tipo"] for _, e in sorted(k.all("laboratorio", "evento").items())]
    assert "plataforma.panico.activado" in tipos
    b = app.state.bitacoras["laboratorio"]
    assert b.verificar()["integra"] is True       # el rastro queda SELLADO en la cadena
    c.post("/cmd/reanudar", json={"quien": "operador"})
    tipos = [e["tipo"] for _, e in sorted(k.all("laboratorio", "evento").items())]
    assert "plataforma.panico.desactivado" in tipos


def test_panico_sobrevive_a_un_reinicio(tmp_path):
    app1, c1, _, _ = _montaje(tmp_path)
    _entrar(c1)
    c1.post("/cmd/parar_todo", json={"quien": "operador", "motivo": "apagon"})
    assert c1.get("/latido").json()["parado"] is True
    # "reinicio": proceso nuevo, mismo fichero de estado
    app2, c2, _, n2 = _montaje(tmp_path, con_solicitud=True)
    assert c2.get("/latido").json()["parado"] is True
    with pytest.raises(PanicoActivo):
        app2.state.panico.gate_irrext("laboratorio")
    _entrar(c2)
    r = c2.post("/cmd/aprobar", json={"empresa": "laboratorio", "id": n2["id"], "quien": "operador"})
    assert r.status_code == 409                   # nada sale con el panico heredado
    c2.post("/cmd/reanudar", json={"quien": "operador"})
    app3, c3, _, _ = _montaje(tmp_path)
    assert c3.get("/latido").json()["parado"] is False


def test_panico_estado_ilegible_degrada_cerrando(tmp_path):
    ruta = tmp_path / "panico" / "estado.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{basura", encoding="utf-8")
    app, c, _, _ = _montaje(tmp_path)
    assert c.get("/latido").json()["parado"] is True      # GR-04: en duda, cerrado


# ── R-07 · dinero real en pantalla ───────────────────────────────────────────

def test_dinero_refleja_gasto_real_del_ledger(tmp_path):
    app, c, _, _ = _montaje(tmp_path)
    _entrar(c)
    led = LedgerCoste(tmp_path / "coste" / "ledger.jsonl")
    led.asentar("laboratorio", cubo="comercial", rol="redactor", clase="ESTANDAR",
                proveedor="anthropic", modelo="claude-haiku-4-5", coste_eur=0.42)
    j = c.get("/api/dinero/laboratorio").json()
    assert j["gasto_eur"] >= 0.42 and "42" in j["frase"]  # deja de ser 0 fantasma


def test_dinero_muestra_legado_sin_atribuir(tmp_path):
    from core.ledger import _hoy
    app, c, _, _ = _montaje(tmp_path)
    _entrar(c)
    (tmp_path / "legacy.json").write_text(
        json.dumps({"date": _hoy(), "usd": 1.0}), encoding="utf-8")
    j = c.get("/api/dinero/laboratorio").json()
    assert j["sin_atribuir_eur"] == 0.92 and "sin atribuir" in j["frase"]


def test_ledger_suma_por_tenant_dia_y_verifica_e1(tmp_path):
    led = LedgerCoste(tmp_path / "l.jsonl", legacy_json=tmp_path / "legacy.json")
    led.asentar("laboratorio", cubo="comercial", rol="a", clase="ESTANDAR", coste_eur=0.10)
    led.asentar("laboratorio", cubo="brand", rol="b", clase="TRIVIAL", coste_eur=0.05)
    led.asentar("laboratorio_dos", cubo="comercial", rol="a", clase="ESTANDAR", coste_eur=0.30)
    assert led.gasto_dia("laboratorio") == 0.15
    assert led.gasto_dia("laboratorio_dos") == 0.30
    from core.ledger import _hoy
    (tmp_path / "legacy.json").write_text(json.dumps({"date": _hoy(), "usd": 0.5}),
                                          encoding="utf-8")
    assert led.gasto_global_dia() == round(0.45 + 0.46, 6)
    mes = _hoy()[:7]
    assert len(led.asientos_mes("laboratorio", mes)) == 2
    assert led.lineas_corruptas() == 0


def test_ledger_alimenta_el_hard_stop_delante(tmp_path):
    """El techo B4 ve el gasto persistido: freno DELANTE con dinero real (R-05/R-07)."""
    k = InMemoryKnowledge()
    led = LedgerCoste(tmp_path / "l.jsonl")
    led.asentar("laboratorio", cubo="comercial", rol="a", clase="ESTANDAR", coste_eur=0.42)
    lb = LibroCoste(k, mandatos={"laboratorio": {"techo_coste_diario_eur": 0.5}}, ledger=led)
    assert lb.gasto_dia("laboratorio") == 0.42
    with pytest.raises(TechoAlcanzado):
        lb.hard_stop_delante("laboratorio", 0.20)
    assert lb.hard_stop_delante("laboratorio", 0.05)["permitido"] is True


def test_csv_del_panel_incluye_el_ledger(tmp_path):
    app, c, _, _ = _montaje(tmp_path)
    _entrar(c)
    LedgerCoste(tmp_path / "coste" / "ledger.jsonl").asentar(
        "laboratorio", cubo="comercial", rol="redactor", clase="ESTANDAR",
        modelo="claude-haiku-4-5", coste_eur=0.07)
    csv_texto = c.get("/api/dinero/laboratorio/export.csv").text
    assert "claude-haiku-4-5" in csv_texto and "0.07" in csv_texto
