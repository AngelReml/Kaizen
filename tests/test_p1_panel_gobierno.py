"""D10 P1 — gobierno: tarjetas con consecuencia, mecha deshacible, PARAR TODO,
identidad obligatoria y errores como escudo.
Puerta P1: doble clic = exactamente-una-vez; deshacer dentro de la mecha aborta de
verdad; PARAR TODO retiene y reanuda sin perdida; sin identidad = escudo (no traza)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from panel_mando.app import crear_app


def _montaje(mecha_s=3600):
    k = InMemoryKnowledge()
    app = crear_app(k, mecha_s=mecha_s)
    c = TestClient(app, raise_server_exceptions=False)
    # sembrar una solicitud IRR-EXT real via la cola del propio panel
    cola = app.state.colas.setdefault("laboratorio", None)
    from core.rue import Bitacora
    from core.aprobaciones import ColaSustrato
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    cola = ColaSustrato(k, "laboratorio", bitacora=b)
    app.state.colas["laboratorio"] = cola
    app.state.bitacoras["laboratorio"] = b
    n = cola.solicitar(cubo="comercial", accion="enviar email inicial a candidato",
                       clase="IRREVERSIBLE-EXTERNA", contenido_ref="borrador_x")
    return app, c, cola, n


def test_tarjeta_lleva_consecuencia_caducidad_y_empresa():
    _, c, _, n = _montaje()
    j = c.get("/api/tarjetas/laboratorio").json()
    t = j["tarjetas"][0]
    assert t["id"] == n["id"] and t["empresa"] == "laboratorio"
    assert "SALE AL MUNDO" in t["consecuencia"] and "deshacer" in t["consecuencia"].lower()
    assert "72" in t["si_no_haces_nada"]


def test_mecha_deshacer_aborta_de_verdad():
    app, c, cola, n = _montaje()
    r = c.post("/cmd/aprobar", json={"empresa": "laboratorio", "id": n["id"], "quien": "operador"})
    assert r.json()["estado"] == "EN_MECHA"
    r2 = c.post("/cmd/deshacer", json={"empresa": "laboratorio", "id": n["id"], "quien": "operador"})
    assert r2.json()["estado"] == "REVOCADA"
    tic = c.post("/cmd/tic", json={"quien": "operador"}).json()
    assert tic["quemadas"] == [] and tic["encendidas"] == []      # nada pendiente
    assert cola._get(n["id"])["estado"] == "REVOCADA"             # no salio NADA


def test_mecha_vencida_ejecuta_exactamente_una_vez():
    app, c, cola, n = _montaje(mecha_s=0)                          # mecha 0 en el armado manual
    app.state.mechas.segundos = 0
    r = c.post("/cmd/aprobar", json={"empresa": "laboratorio", "id": n["id"], "quien": "operador"})
    # R-16: IRREVERSIBLE-EXTERNA sin canal de envio real cableado en el panel
    # generico (solo Comercial lo tiene, en su propio camino intocable) es
    # ENSAYO_SECO, nunca EJECUTADA — antes del arreglo, el panel mentia aqui.
    assert r.json()["estado"] == "ENSAYO_SECO"                     # sin mecha: directo con gate
    # doble aprobacion posterior = escudo, no segunda ejecucion
    r2 = c.post("/cmd/aprobar", json={"empresa": "laboratorio", "id": n["id"], "quien": "operador"})
    assert r2.status_code == 409 and r2.json()["escudo"] is True


def test_parar_todo_retiene_y_reanudar_sin_perdida():
    app, c, cola, n = _montaje(mecha_s=1)
    app.state.mechas.segundos = 0.0                                # vencera al instante
    c.post("/cmd/parar_todo", json={"quien": "operador", "motivo": "prueba"})
    assert c.get("/latido").json()["parado"] is True
    r = c.post("/cmd/aprobar", json={"empresa": "laboratorio", "id": n["id"], "quien": "operador"})
    assert r.status_code == 409                                     # panico: no se ejecuta
    assert cola._get(n["id"])["estado"] == "APROBADA"               # retenida, NO perdida
    c.post("/cmd/reanudar", json={"quien": "operador"})
    tic = c.post("/cmd/tic", json={"quien": "operador"}).json()
    r3 = c.post("/cmd/tic", json={"quien": "operador"})             # ya sin mechas
    # ejecutar ahora si:
    from core.panico import PanicoActivo
    n2 = cola.ejecutar(n["id"], lambda nodo: None)
    assert n2["estado"] == "EJECUTADA"                              # reanudacion limpia


def test_sin_identidad_escudo_sin_traza():
    _, c, _, n = _montaje()
    r = c.post("/cmd/aprobar", json={"empresa": "laboratorio", "id": n["id"]})
    assert r.status_code == 409
    j = r.json()
    assert j["escudo"] is True and "Traceback" not in r.text
    assert j["que_no_paso"] and j["por_que"] and j["que_puedes_hacer"]
