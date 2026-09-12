"""D10 P2 — La Mañana: resumen determinista clicable, diccionario L4 (cero siglas
del canon en nivel 1), estados vacios, dinero humano en el resumen.
Puerta P2: test de palabras prohibidas sobre el HTML de "/" y cada frase con fuente."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core.aprobaciones import ColaSustrato
from panel_mando import nucleo as N
from panel_mando.app import crear_app


def _montaje():
    k = InMemoryKnowledge()
    k.add("laboratorio", "obligacion", "o1", {"nombre": "variantes del reglamento de IA",
                                          "fecha_limite": "2026-08-02", "estado": "ASIGNADA"})
    k.add("laboratorio", "alerta", "a1", {"severidad": "CRITICA", "estado": "EMITIDA",
                                      "metrica": "conversion"})
    app = crear_app(k, mecha_s=0)
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    cola = ColaSustrato(k, "laboratorio", bitacora=b)
    app.state.colas["laboratorio"] = cola
    app.state.bitacoras["laboratorio"] = b
    cola.solicitar(cubo="comercial", accion="enviar email inicial",
                   clase="IRREVERSIBLE-EXTERNA")
    return app, k


def test_manana_sin_siglas_del_canon_l4():
    app, _ = _montaje()
    c = TestClient(app)
    pagina = c.get("/").text
    visible = re.sub(r"<script>.*?</script>", "", pagina, flags=re.S)
    for palabra in N.PROHIBIDAS_NIVEL1:
        assert palabra not in visible, f"L4 violada: {palabra!r} en La Mañana"


def test_resumen_frases_clicables_y_contenido():
    app, _ = _montaje()
    c = TestClient(app)
    pagina = c.get("/").text
    assert "esperando tu SI" in pagina                   # pendientes
    assert "Plazo cerca: variantes del reglamento" in pagina
    assert "aviso(s) importantes" in pagina              # CRITICA
    assert pagina.count('class="frase"') >= 3
    assert 'href="#tarjetas"' in pagina                  # cada frase con fuente


def test_estados_vacios_disenados():
    app = crear_app(InMemoryKnowledge(), mecha_s=0)
    c = TestClient(app)
    pagina = c.get("/").text
    assert "Nada que aprobar. Kaizen sigue trabajando" in pagina
    assert "Nada espera tu decision" in pagina


def test_dinero_humano_formatos():
    assert N.dinero_humano(0.0) == "0 €"
    assert N.dinero_humano(0.12) == "12 centimos"
    assert N.dinero_humano(0.01) == "1 centimo"
    assert N.dinero_humano(10.0) == "10,00 €"
