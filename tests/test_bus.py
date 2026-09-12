"""Tests del bus de mensajes (Capa 1). Runnable con `python tests/test_bus.py` o pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import Event, EventType, Criticality


def test_publish_y_entrega():
    bus = InMemoryBus()
    recibidos = []
    bus.subscribe(recibidos.append)
    bus.publish(Event(EventType.SYSTEM_STARTED, source="test"))
    assert len(recibidos) == 1
    assert recibidos[0].type is EventType.SYSTEM_STARTED


def test_filtro_por_tipo():
    bus = InMemoryBus()
    solo_coste = []
    bus.subscribe(solo_coste.append, types=[EventType.COST_ALERT])
    bus.publish(Event(EventType.DEPT_TASK_STARTED, source="prospeccion"))
    bus.publish(Event(EventType.COST_ALERT, source="contabilidad"))
    assert len(solo_coste) == 1
    assert solo_coste[0].type is EventType.COST_ALERT


def test_replay_historial():
    bus = InMemoryBus()
    bus.publish(Event(EventType.DEPT_TASK_STARTED, source="a"))
    bus.publish(Event(EventType.DEPT_TASK_COMPLETED, source="a"))
    hist = bus.history()
    assert [e.type for e in hist] == [EventType.DEPT_TASK_STARTED, EventType.DEPT_TASK_COMPLETED]


def test_aislamiento_por_empresa():
    bus = InMemoryBus()
    bus.publish(Event(EventType.DEPT_TASK_STARTED, source="a", company="laboratorio"))
    bus.publish(Event(EventType.DEPT_TASK_STARTED, source="a", company="otra"))
    assert len(bus.history(company="laboratorio")) == 1
    assert len(bus.history(company="otra")) == 1
    assert len(bus.history()) == 2


def test_serializacion_roundtrip():
    ev = Event(
        EventType.GUARDIAN_BLOCKED,
        source="guardian",
        payload={"motivo": "presupuesto"},
        company="laboratorio",
        criticality=Criticality.CRITICAL,
        correlation_id="abc",
    )
    clon = Event.from_json(ev.to_json())
    assert clon.type is EventType.GUARDIAN_BLOCKED
    assert clon.criticality is Criticality.CRITICAL
    assert clon.payload == {"motivo": "presupuesto"}
    assert clon.company == "laboratorio"
    assert clon.correlation_id == "abc"
    assert clon.id == ev.id


# -----------------------------------------------------------------------------
#  Bus del SUSTRATO (KAIZEN_ARQUITECTURA_CANONICA_v1_0 seccion 4) - Bloque 1.
#  Seccion aditiva: no toca los tests del bus de core/ de arriba.
#  BD temporal siempre; JAMAS data/kaizen.db real.
# -----------------------------------------------------------------------------
import tempfile  # noqa: E402

from sustrato import bus as sbus  # noqa: E402


def _bus_tmp(tmp_path=None):
    base = Path(tmp_path) if tmp_path is not None else Path(tempfile.mkdtemp())
    conn = sbus.conexion(base / "bus_test.db")
    sbus.instalar(conn)
    return conn


def test_publicar_y_consumir(tmp_path=None):
    conn = _bus_tmp(tmp_path)
    sbus.publicar(conn, "kaizen.comercial.lead_actualizado.v1", "test", {"lead_id": "l1"})
    sbus.publicar(conn, "kaizen.comercial.pedido_registrado.v1", "test", {"lead_id": "l1"})
    sbus.publicar(conn, "kaizen.comercial.lead_actualizado.v1", "test", {"lead_id": "l2"})
    vistos = []
    ok, err = sbus.consumir(conn, "consumidor_a",
                            ["kaizen.comercial.lead_actualizado.v1"], vistos.append)
    assert (ok, err) == (2, 0)
    assert [e["payload"]["lead_id"] for e in vistos] == ["l1", "l2"]  # orden por id
    # segundo poll: nada nuevo
    ok2, _ = sbus.consumir(conn, "consumidor_a",
                           ["kaizen.comercial.lead_actualizado.v1"], vistos.append)
    assert ok2 == 0 and len(vistos) == 2


def test_reentrega_idempotente(tmp_path=None):
    conn = _bus_tmp(tmp_path)
    eid = sbus.publicar(conn, "kaizen.comercial.compromiso_creado.v1", "test", {"c": 1})
    estado: set = set()
    llamadas = []

    def handler(evento):  # idempotente: estado en set
        llamadas.append(evento["id"])
        estado.add(evento["payload"]["c"])

    sbus.consumir(conn, "consumidor_b", ["kaizen.comercial.compromiso_creado.v1"], handler)
    # reentrega explicita del MISMO evento (at-least-once)
    assert sbus.reintentar(conn, eid, "consumidor_b", handler) in ("OK", "YA_OK")
    if llamadas.count(eid) < 2:  # YA_OK no reentrega; forzamos la segunda entrega
        conn.execute("DELETE FROM bus_consumos WHERE evento_id=? AND consumidor=?",
                     (eid, "consumidor_b"))
        conn.commit()
        sbus.consumir(conn, "consumidor_b", ["kaizen.comercial.compromiso_creado.v1"], handler)
    assert llamadas.count(eid) == 2      # recibido dos veces
    assert estado == {1}                 # sin corromper estado
    fila = conn.execute("SELECT COUNT(*) FROM bus_consumos WHERE evento_id=?",
                        (eid,)).fetchone()
    assert fila[0] == 1                  # un solo registro de consumo (PK)


def test_evento_envenenado_no_bloquea(tmp_path=None):
    conn = _bus_tmp(tmp_path)
    for i in range(3):
        sbus.publicar(conn, "kaizen.comercial.interaccion_registrada.v1", "test", {"n": i})
    procesados = []

    def handler(evento):
        if evento["payload"]["n"] == 1:
            raise RuntimeError("veneno")
        procesados.append(evento["payload"]["n"])

    ok, err = sbus.consumir(conn, "consumidor_c",
                            ["kaizen.comercial.interaccion_registrada.v1"], handler)
    assert (ok, err) == (2, 1)
    assert procesados == [0, 2]          # el envenenado no bloqueo el poll
    fila = conn.execute(
        "SELECT resultado FROM bus_consumos WHERE consumidor='consumidor_c' "
        "AND evento_id=(SELECT id FROM bus_eventos WHERE payload LIKE '%\"n\":1%')").fetchone()
    assert fila[0] == "ERROR"


def test_cadena_detecta_manipulacion(tmp_path=None):
    conn = _bus_tmp(tmp_path)
    for i in range(3):
        sbus.publicar(conn, "kaizen.comercial.lead_actualizado.v1", "test", {"i": i})
    assert sbus.verificar_cadena(conn) == "CADENA INTACTA (3 eventos)"
    conn.execute("UPDATE bus_eventos SET payload='{\"i\":99}' WHERE id=2")  # manipulacion
    conn.commit()
    veredicto = sbus.verificar_cadena(conn)
    assert veredicto.startswith("CADENA CORRUPTA")
    assert "primer id corrupto = 2" in veredicto


def test_topic_invalido_rechazado(tmp_path=None):
    conn = _bus_tmp(tmp_path)
    import pytest as _pytest
    with _pytest.raises(sbus.TopicInvalido):
        sbus.publicar(conn, "actualizar_lead", "test", {})


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
