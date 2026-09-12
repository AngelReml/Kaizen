"""Tests contra los backends REALES (Redis/Neo4j/Postgres).

Se ejecutan solo si las variables de entorno apuntan a backends reales y responden;
si no, se saltan. Validan la Fase 0.1 del roadmap tras `docker compose up -d`.

Ejecutar:  REDIS_URL=... NEO4J_URI=... DATABASE_URL=... python tests/test_persistencia_real.py
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# _Skip hereda de la excepción de skip de pytest si está disponible (así pytest lo
# trata como "saltado"); si no, es una excepción normal que captura el runner manual.
try:
    from _pytest.outcomes import Skipped as _SkipBase
except Exception:
    _SkipBase = Exception


class _Skip(_SkipBase):
    pass


def _need(env: str) -> None:
    if not os.getenv(env):
        raise _Skip(f"sin {env}: requiere backend real")


def test_redis_real_roundtrip():
    _need("REDIS_URL")
    from core.bus import RedisStreamsBus
    from core.events import Event, EventType
    bus = RedisStreamsBus()
    marker = uuid.uuid4().hex
    bus.publish(Event(EventType.SYSTEM_STARTED, source="test", payload={"m": marker}, company="t_redis"))
    hist = bus.history(company="t_redis")
    assert any(e.payload.get("m") == marker for e in hist)


def test_neo4j_real_aislamiento():
    _need("NEO4J_URI")
    from core.knowledge import Neo4jKnowledge
    k = Neo4jKnowledge()
    key = uuid.uuid4().hex
    k.add("t_laboratorio", "lead", key, {"fit": "alta"})
    assert k.get("t_laboratorio", "lead", key) == {"fit": "alta"}
    assert k.get("t_otra", "lead", key) is None          # no cruza entre empresas
    k.close()


def test_postgres_real_companies():
    _need("DATABASE_URL")
    from core.config_store import PostgresConfig
    slug = "t_" + uuid.uuid4().hex[:8]
    c1 = PostgresConfig()
    c1.add_company(slug, "Empresa Test", "Test")
    c2 = PostgresConfig()                                  # nueva conexión: persiste
    assert any(e["slug"] == slug for e in c2.list_companies())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = skip = fail = 0
    for fn in fns:
        try:
            fn()
            ok += 1
            print(f"  PASS  {fn.__name__}")
        except _Skip as e:
            skip += 1
            print(f"  SKIP  {fn.__name__} ({e})")
        except AssertionError as e:
            fail += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{ok} OK · {skip} saltados · {fail} fallidos")
    sys.exit(1 if fail else 0)
