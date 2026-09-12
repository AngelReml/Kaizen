"""Cubo Operaciones (D05): saturacion bloquea (13.2), claim atomico R-09 (13.9),
fail-safe pender R-08, rechazo con propuesta (13.7), secuencia (13.4), hitos (13.5),
SLA GAP-02, aislamiento (13.1)."""
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.ops.cubo_serie_d import CuboOps


def _pedido(i, fecha="2026-07-15", **kw):
    return {"id": f"p{i}", "cliente_ref": f"c{i}", "producto": "lote surtido",
            "cantidad": 1, "fecha": fecha, **kw}


@pytest.fixture()
def ops():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    return CuboOps(k, "t1", bitacora=b), k, b


def test_saturacion_bloquea_con_propuesta(ops):
    o, k, _ = ops
    o.declarar_capacidad("2026-07-15", 2)
    o.declarar_capacidad("2026-07-16", 5)
    for i in range(3):
        o.recibir_pedido(_pedido(i))
    assert o.confirmar("p0")["estado"] == "CONFIRMADO"
    assert o.confirmar("p1")["estado"] == "CONFIRMADO"
    r = o.confirmar("p2")                                   # 3o: puerta cerrada
    assert r["estado"] == "RECHAZADO"
    assert r["propuesta_alternativa_fecha"] == "2026-07-16"  # 13.7: siempre con propuesta
    tipos = [e["tipo"] for e in k.all("t1", "evento").values()]
    assert "operacion.capacidad.saturada" in tipos


def test_fail_safe_sin_capacidad_pende_jamas_rechaza(ops):
    o, _, _ = ops
    o.recibir_pedido(_pedido(9, fecha="2026-08-01"))        # sin capacidad declarada
    r = o.confirmar("p9")
    assert r["estado"] == "PENDIENTE_CONFIRMACION"           # R-08: NO ACTUAR
    assert r["pendiente_por"] == "capacidad_no_declarada"


def test_claim_atomico_ultima_unidad_r09(ops):
    o, _, _ = ops
    o.declarar_capacidad("2026-07-15", 1)                    # UNA unidad
    o.recibir_pedido(_pedido(1)); o.recibir_pedido(_pedido(2))
    resultados = {}

    def confirmar(pid):
        resultados[pid] = o.confirmar(pid)["estado"]

    h1 = threading.Thread(target=confirmar, args=("p1",))
    h2 = threading.Thread(target=confirmar, args=("p2",))
    h1.start(); h2.start(); h1.join(); h2.join()
    assert sorted(resultados.values()) == ["CONFIRMADO", "RECHAZADO"]   # exactamente una gana


def test_secuencia_loyal_y_urgente_primero(ops):
    o, _, _ = ops
    o.declarar_capacidad("2026-07-15", 10)
    o.recibir_pedido(_pedido(1)); o.confirmar("p1")
    o.recibir_pedido(_pedido(2, urgente=True)); o.confirmar("p2")
    o.recibir_pedido(_pedido(3, cliente_loyal=True)); o.confirmar("p3")
    assert o.proponer_secuencia("2026-07-15") == ["p2", "p3", "p1"]     # 13.4


def test_hitos_recuperables_y_gate_logistica(ops):
    o, k, b = ops
    o.declarar_capacidad("2026-07-15", 5)
    o.recibir_pedido(_pedido(1)); o.confirmar("p1")
    with pytest.raises(ValueError):
        o.entregar_a_logistica("p1", albaran_ref="alb1")     # sin LISTO no sale
    o.registrar_hito("p1", "LOTE_COMPLETO")
    o.registrar_hito("p1", "EMPAQUETADO", foto_ref="foto_1")
    o.registrar_hito("p1", "LISTO_LOGISTICA")
    p = k.get("t1", "pedido_ops", "p1")
    assert p["estado"] == "COMPLETADO" and len(p["hitos"]) == 3
    assert all(h["ts"] for h in p["hitos"])                  # 13.5: recuperables con ts
    o.entregar_a_logistica("p1", albaran_ref="alb1")
    assert k.get("t1", "pedido_ops", "p1")["estado"] == "ENTREGADO_A_LOGISTICA"
    assert b.verificar()["integra"] is True


def test_sla_gap02_alerta_y_escalado(ops):
    o, _, _ = ops
    o.recibir_pedido(_pedido(1, fecha="2026-08-01"))
    o.recibir_pedido(_pedido(2, fecha="2026-08-01"))
    ahora = datetime.now(timezone.utc)
    p1 = o.k.get("t1", "pedido_ops", "p1")
    p1["recibido_en"] = (ahora - timedelta(hours=30)).isoformat(); o.k.add("t1", "pedido_ops", "p1", p1)
    p2 = o.k.get("t1", "pedido_ops", "p2")
    p2["recibido_en"] = (ahora - timedelta(hours=80)).isoformat(); o.k.add("t1", "pedido_ops", "p2", p2)
    avisos = o.barrer_pendientes(ahora=ahora)
    assert {a["pedido"]: a["sla"] for a in avisos} == {"p1": "24h→operador", "p2": "72h→D01"}


def test_aislamiento_por_tenant_13_1():
    k = InMemoryKnowledge()
    a = CuboOps(k, "tenant_a"); b = CuboOps(k, "tenant_b")
    a.declarar_capacidad("2026-07-15", 1)
    b.declarar_capacidad("2026-07-15", 1)
    a.recibir_pedido(_pedido(1)); a.confirmar("p1")
    b.recibir_pedido(_pedido(1)); r = b.confirmar("p1")
    assert r["estado"] == "CONFIRMADO"                       # la capacidad de A no contamina B
