"""D10 P5 — delicia (parte automatizable): temas Hiru/Yoru, marca del manual en el
CSS servido, sello de tinta, animaciones acotadas, una columna movil-lista.
La otra mitad de la puerta P5 es HUMANA (R9 + test de los 90 segundos) y queda
PENDIENTE del operador en su maquina — por diseño, innegociable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from panel_mando import nucleo as N
from panel_mando.app import crear_app


def _c():
    return TestClient(crear_app(InMemoryKnowledge(), mecha_s=0))


def test_temas_hiru_defecto_y_yoru_a_un_clic():
    c = _c()
    assert N.TEMA_DEFECTO == "hiru"                      # §11.1, facil de cambiar
    assert 'data-tema="hiru"' in c.get("/").text
    assert 'data-tema="yoru"' in c.get("/?tema=yoru").text


def test_css_ancla_la_marca_del_manual():
    c = _c()
    css = c.get("/assets/panel.css").text
    assert "#7A8B5A" in css                               # bambu, unico acento
    assert 'data-tema="hiru"' in css and 'data-tema="yoru"' in css
    assert "Cormorant Garamond" in css and "Inter" in css and "JetBrains Mono" in css
    assert "sello-tinta" in css and "consumirse 60s" in css   # hanko + mecha
    assert ".15s" in css                                  # microanimaciones ≤150ms
    for chillon in ("#ff0000", "#00ff00", "#ffff00"):     # nada de casino
        assert chillon not in css.lower()


def test_una_columna_movil_lista():
    c = _c()
    assert "max-width: 720px" in c.get("/assets/panel.css").text
    assert 'name="viewport"' in c.get("/").text


def test_puerta_humana_documentada_pendiente():
    """La aceptacion final NO es de esta suite: R9 + 90 segundos son del operador."""
    doc = Path(__file__).read_text(encoding="utf-8")
    assert "90 segundos" in doc and "R9" in doc
