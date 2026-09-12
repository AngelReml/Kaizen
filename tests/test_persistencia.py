"""Tests de las fábricas de persistencia y el backend en memoria (Block A).

Los adaptadores reales (Redis/Neo4j/Postgres) se validan con `docker compose up`; aquí
se comprueba el contrato en memoria y que sin variables de entorno se cae a memoria.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import get_bus, InMemoryBus
from core.bus_sqlite import SQLitePersistentBus
from core.knowledge import get_knowledge, InMemoryKnowledge, JsonKnowledge, reset_knowledge_singleton
from core.config_store import get_config, InMemoryConfig


def _sin(*nombres):
    return {n: os.environ.pop(n, None) for n in nombres}


def _restaurar(saved):
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


def test_bus_cae_a_sqlite_sin_redis(tmp_path):
    """Sin REDIS_URL, la cascada ofrece SQLitePersistentBus (persiste entre reinicios)
    antes de degradar a memoria — mismo patrón que get_knowledge() (Neo4j->Json->Memoria)."""
    saved = _sin("REDIS_URL")
    os.environ["KAIZEN_DATOS"] = str(tmp_path)
    try:
        assert isinstance(get_bus(), SQLitePersistentBus)
    finally:
        os.environ.pop("KAIZEN_DATOS", None)
        _restaurar(saved)


def test_bus_cae_a_memoria_si_sqlite_falla(tmp_path, monkeypatch):
    """Si SQLitePersistentBus no puede abrirse (disco/permisos), el último recurso
    sigue siendo InMemoryBus — nunca un crash silencioso del bus."""
    saved = _sin("REDIS_URL")
    os.environ["KAIZEN_DATOS"] = str(tmp_path)

    def _revienta(*a, **kw):
        raise RuntimeError("disco no disponible")

    monkeypatch.setattr("core.bus_sqlite.SQLitePersistentBus.__init__", _revienta)
    try:
        assert isinstance(get_bus(), InMemoryBus)
    finally:
        os.environ.pop("KAIZEN_DATOS", None)
        _restaurar(saved)


def test_knowledge_inmemory_si_opt_in():
    """conftest fuerza KAIZEN_KNOWLEDGE_INMEMORY=1 → InMemoryKnowledge."""
    saved = _sin("NEO4J_URI")
    try:
        assert isinstance(get_knowledge(), InMemoryKnowledge)
    finally:
        _restaurar(saved)


def test_knowledge_json_persiste_entre_instancias(tmp_path):
    """Sin Neo4j y sin opt-in InMemory, el default es JsonKnowledge en KAIZEN_KNOWLEDGE_PATH.
    El estado sobrevive entre instanciaciones (regla v0.2 §3.4 'NO SE PIERDE NADA')."""
    saved = _sin("NEO4J_URI", "KAIZEN_KNOWLEDGE_INMEMORY")
    ruta = tmp_path / "knowledge.json"
    os.environ["KAIZEN_KNOWLEDGE_PATH"] = str(ruta)
    try:
        reset_knowledge_singleton()
        k1 = get_knowledge()
        assert isinstance(k1, JsonKnowledge)
        k1.add("laboratorio", "lead", "hotel_x", {"nombre": "Hotel X", "anillo": 1})

        # Nueva instancia desde el mismo archivo → mismo estado.
        reset_knowledge_singleton()
        k2 = get_knowledge()
        assert isinstance(k2, JsonKnowledge)
        assert k2.get("laboratorio", "lead", "hotel_x")["nombre"] == "Hotel X"
    finally:
        os.environ.pop("KAIZEN_KNOWLEDGE_PATH", None)
        _restaurar(saved)
        reset_knowledge_singleton()


def test_json_knowledge_escritura_atomica(tmp_path):
    """Tras un add, no debe quedar el .tmp residual; el JSON debe estar bien formado."""
    ruta = tmp_path / "knowledge.json"
    k = JsonKnowledge(ruta)
    k.add("laboratorio", "lead", "x", {"v": 1})
    import json as _json
    assert not (ruta.parent / "knowledge.json.tmp").exists()
    assert _json.loads(ruta.read_text(encoding="utf-8"))["laboratorio"]["lead"]["x"] == {"v": 1}


def test_json_knowledge_delete(tmp_path):
    k = JsonKnowledge(tmp_path / "k.json")
    k.add("laboratorio", "lead", "a", {"v": 1})
    assert k.delete("laboratorio", "lead", "a") is True
    assert k.get("laboratorio", "lead", "a") is None
    assert k.delete("laboratorio", "lead", "a") is False    # ya no existe


def test_json_knowledge_corrupto_falla_explicito(tmp_path):
    """Un JSON corrupto NO debe degradar a 0; debe lanzar para no perder datos en silencio."""
    import pytest
    ruta = tmp_path / "k.json"
    ruta.write_text("{ esto no es JSON válido", encoding="utf-8")
    with pytest.raises(RuntimeError):
        JsonKnowledge(ruta)


def test_config_cae_a_memoria_sin_postgres():
    saved = _sin("DATABASE_URL")
    try:
        assert isinstance(get_config(), InMemoryConfig)
    finally:
        _restaurar(saved)


def test_config_memoria_empresas_y_settings():
    c = InMemoryConfig()
    c.add_company("laboratorio", "Repostería Laboratorio", "Alimentación")
    c.add_company("demo-soft", "Demo Software", "Software")
    assert [e["slug"] for e in c.list_companies()] == ["demo-soft", "laboratorio"]
    assert c.get_setting("autonomia", "cero") == "cero"     # default
    c.set_setting("autonomia", "media")
    assert c.get_setting("autonomia") == "media"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
