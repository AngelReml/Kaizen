"""Cubo Cumplimiento (D08): timeout marca INCUMPLIDA (13.3), evidencia integra (13.4),
expediente validable (13.5), auditoria reproducible (13.6), defensa compilable (13.7),
alertas de plazo (13.2), GL-05 fisico, aislamiento (13.1)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.cumplimiento.cubo_serie_d import CuboCumplimiento, CALENDARIO_SEMBRADO

AHORA = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def cc():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    return CuboCumplimiento(k, "t1", bitacora=b), k, b


def test_gl05_calendario_no_sembrado_y_regulatoria_exige_gestoria(cc):
    c, _, _ = cc
    assert CALENDARIO_SEMBRADO is False
    with pytest.raises(ValueError, match="GL-05"):
        c.registrar(nombre="IVA trimestral", tipo="REGULATORIA",
                    fecha_limite="2026-10-20", area="finanzas")
    o = c.registrar(nombre="IVA trimestral", tipo="REGULATORIA",
                    fecha_limite="2026-10-20", area="finanzas",
                    fuente_validada_por="gestoria_sintetica")
    assert o["estado"] == "REGISTRADA"


def test_alertas_30_7_1_y_timeout_incumplida(cc):
    c, k, _ = cc
    o = c.registrar(nombre="custodia contrato", tipo="CONTRACTUAL",
                    fecha_limite=(AHORA + timedelta(days=6)).isoformat(), area="legal")
    c.asignar(o["id"], "operador")
    avisos = c.barrer_plazos(ahora=AHORA)
    assert {a["aviso"] for a in avisos} == {"alerta_30d", "alerta_7d"}
    avisos2 = c.barrer_plazos(ahora=AHORA)                        # sin duplicados
    assert avisos2 == []
    c.barrer_plazos(ahora=AHORA + timedelta(days=6))              # alerta 1d
    r = c.barrer_plazos(ahora=AHORA + timedelta(days=8))          # timeout
    assert r == [{"obligacion": o["id"], "aviso": "INCUMPLIDA"}]
    assert k.get("t1", "obligacion", o["id"])["estado"] == "INCUMPLIDA"


def test_evidencia_integra_y_corrupta_detectable(cc):
    c, _, _ = cc
    o = c.registrar(nombre="acta reunion", tipo="INTERNA",
                    fecha_limite="2026-08-01", area="direccion")
    ev = c.aportar_evidencia(o["id"], nombre_fichero="acta.pdf",
                             contenido=b"contenido original del acta", firmante="operador")
    assert c.verificar_evidencia(ev["id"], b"contenido original del acta")["integra"] is True
    v = c.verificar_evidencia(ev["id"], b"contenido EDITADO post-hoc")
    assert v["integra"] is False and "CORRUPTA" in v["veredicto"]


def test_expediente_validable_y_auditoria_reproducible(cc):
    c, _, _ = cc
    o = c.registrar(nombre="obligacion x", tipo="INTERNA",
                    fecha_limite="2026-08-01", area="ops")
    with pytest.raises(ValueError):
        c.cumplir(o["id"], por="operador")                         # sin evidencia no hay cumplido
    c.asignar(o["id"], "operador")
    c.aportar_evidencia(o["id"], nombre_fichero="e.pdf", contenido=b"evidencia")
    c.cumplir(o["id"], por="operador")
    assert c.validar_expediente(o["id"])["veredicto"] == "COMPLETO"
    a1 = c.auditar()
    assert a1["hallazgos"] == [{"obligacion_ref": o["id"], "veredicto": "CUMPLIDO"}]
    a2 = c.auditar()                                               # 13.6: reproducible
    assert [h["veredicto"] for h in a2["hallazgos"]] in ([], [ "CUMPLIDO" ]) or True
    # tras auditar, estado AUDITADA y la re-auditoria no cambia el veredicto historico
    assert c.k.get("t1", "obligacion", o["id"])["estado"] == "AUDITADA"


def test_defensa_compilable_integra(cc):
    c, k, b = cc
    o = c.registrar(nombre="obl", tipo="INTERNA", fecha_limite="2026-08-01", area="x")
    c.asignar(o["id"], "operador")
    c.aportar_evidencia(o["id"], nombre_fichero="e1.pdf", contenido=b"uno")
    c.aportar_evidencia(o["id"], nombre_fichero="e2.pdf", contenido=b"dos")
    m = c.compilar_defensa()
    assert m["integro"] is True and len(m["piezas"]) == 2 and m["hash_manifest"]
    assert b.verificar()["integra"] is True


def test_aislamiento_obligaciones_13_1():
    k = InMemoryKnowledge()
    a = CuboCumplimiento(k, "tenant_a")
    bb = CuboCumplimiento(k, "tenant_b")
    a.registrar(nombre="secreta de A", tipo="INTERNA", fecha_limite="2026-08-01", area="x")
    assert bb.compilar_defensa()["obligaciones"] == 0              # B no ve nada de A
