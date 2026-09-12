"""Tests de resiliencia: arranque sin dependencia, degradación, cola persistente, bus SQLite
y umbral de migración (§7.1, §7.2, §7.4)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.bus_sqlite import SQLitePersistentBus
from core.events import Event, EventType
from core.resiliencia.arranque import Cubo, Orquestador, verificar_combinaciones, CUBOS_CATALOGO
from core.resiliencia.degradacion import (
    ColaPersistente, ClaseEvento, marcar_degradado, es_degradado, DegradedReason,
    TTL_POR_CLASE,
)
from core.migracion_bus import MonitorMigracion, percentil, UMBRALES


# ── §7.1 Sin dependencia de arranque ─────────────────────────────────────────
class _Stub(Cubo):
    def __init__(self, name, bus, company):
        super().__init__(bus, company)
        self.name = name


def test_cubo_arranca_solo_y_publica_cube_started():
    bus = InMemoryBus()
    started = []
    bus.subscribe(started.append, types=[EventType.CUBE_STARTED])
    _Stub("legal", bus, "laboratorio").arrancar()
    assert started and started[0].payload["cube"] == "legal"


def test_arranque_idempotente():
    bus = InMemoryBus()
    started = []
    bus.subscribe(started.append, types=[EventType.CUBE_STARTED])
    c = _Stub("legal", bus, "laboratorio")
    c.arrancar(); c.arrancar()
    assert len(started) == 1


def test_matriz_combinaciones_todas_arrancan():
    # Toda combinación no vacía de 6 cubos debe arrancar (63 combinaciones).
    fabricas = {n: (lambda b, c, n=n: _Stub(n, b, c)) for n in CUBOS_CATALOGO[:6]}
    fallidas = verificar_combinaciones(fabricas, lambda: InMemoryBus())
    assert fallidas == []


def test_orquestador_arranca_combinacion():
    bus = InMemoryBus()
    orq = Orquestador(bus)
    for n in ("legal", "brand"):
        orq.registrar_fabrica(n, lambda b, c, n=n: _Stub(n, b, c))
    orq.arrancar("laboratorio", ["legal", "brand"])
    assert set(orq.activos("laboratorio")) == {"legal", "brand"}


# ── §7.2 Degradación elegante ─────────────────────────────────────────────────
def test_metadatos_degradados_obligatorios():
    p = marcar_degradado({"x": 1}, DegradedReason.CONSUMER_OFF, "evt-1",
                         valor_degradado={"aprobado": True})
    assert es_degradado(p)
    assert p["degraded_reason"] == "consumer_off" and p["degraded_event_ref"] == "evt-1"
    assert p["aprobado"] is True


def test_cola_persistente_idempotente():
    tmp = Path(tempfile.mkdtemp())
    cola = ColaPersistente(db_path=tmp / "c.db")
    ev = Event(EventType.OPENGRAVITY_REVIEW_REQUESTED, source="comercial",
               company="laboratorio", correlation_id="c1")
    assert cola.encolar(ev, "opengravity", ClaseEvento.REQ_RESP_OBLIGATORIA) is True
    assert cola.encolar(ev, "opengravity", ClaseEvento.REQ_RESP_OBLIGATORIA) is False
    assert len(cola.pendientes("opengravity", "laboratorio")) == 1
    cola.marcar_procesado("opengravity", "c1")
    assert cola.pendientes("opengravity", "laboratorio") == []
    cola.cerrar()


def test_cola_aislada_por_empresa():
    tmp = Path(tempfile.mkdtemp())
    cola = ColaPersistente(db_path=tmp / "c.db")
    for emp in ("laboratorio", "otra"):
        cola.encolar(Event(EventType.CUBE_STARTED, source="x", company=emp,
                           correlation_id=f"{emp}-1"), "brand", ClaseEvento.BROADCAST)
    assert len(cola.pendientes("brand", "laboratorio")) == 1
    assert len(cola.pendientes("brand", "otra")) == 1
    cola.cerrar()


def test_ttl_obligatoria_no_expira():
    assert TTL_POR_CLASE[ClaseEvento.REQ_RESP_OBLIGATORIA] is None
    assert TTL_POR_CLASE[ClaseEvento.BROADCAST].days == 7


# ── Bus SQLite persistente ────────────────────────────────────────────────────
def test_bus_sqlite_persiste_y_replay():
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "sn.db"
    bus = SQLitePersistentBus(db_path=db)
    bus.publish(Event(EventType.SYSTEM_STARTED, source="x", company="laboratorio"))
    bus.cerrar()
    # Reabre: el evento sobrevive al reinicio.
    bus2 = SQLitePersistentBus(db_path=db)
    assert len(bus2.history("laboratorio")) == 1
    bus2.cerrar()


def test_bus_sqlite_dispatch_sincrono():
    tmp = Path(tempfile.mkdtemp())
    bus = SQLitePersistentBus(db_path=tmp / "sn.db")
    got = []
    bus.subscribe(got.append, types=[EventType.CUBE_STARTED])
    bus.publish(Event(EventType.CUBE_STARTED, source="x", company="laboratorio"))
    assert len(got) == 1
    assert len(bus.latencias_escritura()) == 1
    bus.cerrar()


# ── §7.4 Umbral de migración ──────────────────────────────────────────────────
def test_percentil():
    assert percentil(list(range(1, 101))) == 95.05


def test_migracion_abre_tras_3_dias():
    tmp = Path(tempfile.mkdtemp())
    m = MonitorMigracion(base_dir=tmp)
    alto = {"events_per_minute_p95": 300, "db_write_latency_ms_p95": 40,
            "concurrent_subscribers": 6, "consumer_lag_seconds_p95": 1}
    m.registrar_dia(alto, dia="2026-05-27")
    m.registrar_dia(alto, dia="2026-05-28")
    assert not m.decision_abierta()
    m.registrar_dia(alto, dia="2026-05-29")
    assert m.decision_abierta()


def test_migracion_necesita_2_de_4():
    tmp = Path(tempfile.mkdtemp())
    m = MonitorMigracion(base_dir=tmp)
    # Solo 1 métrica cruza → no cuenta.
    una = {"events_per_minute_p95": 300, "db_write_latency_ms_p95": 1,
           "concurrent_subscribers": 1, "consumer_lag_seconds_p95": 1}
    for d in ("2026-05-27", "2026-05-28", "2026-05-29"):
        m.registrar_dia(una, dia=d)
    assert not m.decision_abierta()


def test_cifras_son_estimacion():
    from core.migracion_bus import ES_ESTIMACION
    assert ES_ESTIMACION is True


def test_disparador_cualitativo_y_razones_invalidas():
    assert MonitorMigracion.disparador_cualitativo(3, True)
    assert not MonitorMigracion.disparador_cualitativo(2, True)
    assert not MonitorMigracion.razon_valida("sería más profesional")
    assert MonitorMigracion.razon_valida("latencia real medida cruzó el umbral")


def test_emite_evento_cuando_abre():
    tmp = Path(tempfile.mkdtemp())
    bus = InMemoryBus()
    eventos = []
    bus.subscribe(eventos.append, types=[EventType.BUS_MIGRATION_THRESHOLD_OPEN])
    m = MonitorMigracion(base_dir=tmp)
    alto = {k: v * 2 for k, v in UMBRALES.items()}
    for d in ("2026-05-27", "2026-05-28", "2026-05-29"):
        m.registrar_dia(alto, dia=d)
    assert m.emitir_si_abierta(bus, "laboratorio")
    assert len(eventos) == 1
