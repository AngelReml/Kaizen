"""Configuración global de la suite de tests.

Forzamos:
  - `KAIZEN_KNOWLEDGE_INMEMORY=1`: ningún test toca el `state/knowledge.json` del repo.
    Los tests que quieren validar `JsonKnowledge` lo instancian explícitamente con un
    `tmp_path`.
  - Reset del singleton de Knowledge entre tests (evita fugas de estado).
  - Aislamiento de variables .env-cargadas entre tests (ver fixture de abajo).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Set ANTES de cualquier import que pueda llamar get_knowledge().
os.environ.setdefault("KAIZEN_KNOWLEDGE_INMEMORY", "1")

import pytest
from core.knowledge import reset_knowledge_singleton


@pytest.fixture(autouse=True)
def _reset_knowledge_between_tests():
    reset_knowledge_singleton()
    yield
    reset_knowledge_singleton()


@pytest.fixture(autouse=True)
def _sin_dotenv_filtrado(monkeypatch):
    """`claude_client.py` llama `load_dotenv()` incondicionalmente en tiempo de
    IMPORTACION (no solo en el main() de arranque, pese a la regla del proyecto
    de cargar .env solo alli). La primera vez que CUALQUIER test importa ese
    modulo (directo, o transitivamente via panel_mando.colmena, que lo importa
    dentro de crear_app()), python-dotenv escribe en el os.environ REAL del
    proceso de pytest — y ese proceso ejecuta TODOS los tests. Sin este
    aislamiento, un KAIZEN_TOKEN real del .env del operador se filtraba a
    tests que esperaban 'sin token = uso local abierto' (crear_app() sin
    `token=` explicito cae a os.getenv('KAIZEN_TOKEN')), rompiendolos SOLO
    cuando corrian despues de cualquier test que tocase claude_client/colmena
    — un fallo de orden de ejecucion, no del propio codigo bajo prueba.
    Se limpia ANTES de cada test (no solo una vez): el import es cacheado por
    Python, pero el .env pudo haberse cargado en un test anterior."""
    for var in ("KAIZEN_TOKEN", "ANTHROPIC_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
        monkeypatch.delenv(var, raising=False)
