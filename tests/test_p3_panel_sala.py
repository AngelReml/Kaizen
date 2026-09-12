"""D10 P3 — Sala: Historias por hilo narradas, sello verificable con ruptura en
cristiano, dinero humano + export CSV.
Puerta P3: una historia real completa legible de punta a punta; ruptura señalada."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora, Sobre
from panel_mando.app import crear_app


def _montaje():
    k = InMemoryKnowledge()
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    corr = "hilo-lead-1"
    for tipo, payload in (("comercial.lead.descubierto", {"lead_ref": "l1"}),
                          ("plataforma.aprobacion.solicitada", {"accion": "enviar email"}),
                          ("plataforma.aprobacion.concedida", {}),
                          ("comercial.contacto.enviado", {"secuencia": "INICIAL"})):
        b.publicar(Sobre(tenant_id="laboratorio", tipo=tipo, payload=payload,
                         origen="test", correlacion_id=corr))
    app = crear_app(k, mecha_s=0)
    app.state.bitacoras["laboratorio"] = b
    return app, k, b


def test_historia_narrada_de_punta_a_punta():
    app, _, _ = _montaje()
    c = TestClient(app)
    hs = c.get("/api/historias/laboratorio").json()["historias"]
    h = next(x for x in hs if x["hilo"] == "hilo-lead-1")
    assert h["pasos"] == 4
    assert "se envio un mensaje (inicial)" in h["ultimo"]
    assert any("encontre un negocio candidato" in f for f in h["frases"])
    assert any("recibi tu SI" in f for f in h["frases"])
    pagina = c.get("/sala").text
    assert "se envio un mensaje" in pagina and "ver detalle tecnico" in pagina


def test_sello_integro_y_ruptura_en_cristiano():
    app, k, _ = _montaje()
    c = TestClient(app)
    j = c.get("/api/sello/laboratorio").json()
    assert j["integra"] is True and "intacto" in j["mensaje"]
    ev = k.get("laboratorio", "evento", "000000000001")
    ev["payload"] = {"manipulado": True}
    k.add("laboratorio", "evento", "000000000001", ev)
    j2 = c.get("/api/sello/laboratorio").json()
    assert j2["integra"] is False
    assert "se rompe en el paso 1" in j2["mensaje"]        # cristiano, no hex


def test_dinero_frase_y_export_csv():
    app, k, _ = _montaje()
    from core.techos import LibroCoste
    LibroCoste(k, mandatos={"laboratorio": {"techo_coste_diario_eur": 10}}).asiento(
        "laboratorio", cubo="comercial", rol="detector", clase="ESTANDAR", coste_eur=0.12)
    c = TestClient(app)
    j = c.get("/api/dinero/laboratorio").json()
    assert "12 centimos" in j["frase"] and j["modo_ahorro"] is False
    csv_ = c.get("/api/dinero/laboratorio/export.csv").text
    assert "coste_eur" in csv_ and "comercial" in csv_
