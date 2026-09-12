"""Tests del lifecycle del lead. Persistencia + máquina de estados sobre InMemoryKnowledge."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.lifecycle import (
    LeadStore, EstadoLead, TRANSICIONES_VALIDAS, TransicionInvalida,
)


def _store() -> LeadStore:
    return LeadStore(InMemoryKnowledge(), "laboratorio")


def test_crear_y_recuperar():
    s = _store()
    nodo = s.crear("hotel_la_parra", {"nombre": "Hotel La Parra", "anillo": 1})
    assert nodo["estado"] == EstadoLead.IDENTIFICADO.value
    assert len(nodo["historial"]) == 1
    assert nodo["historial"][0]["a"] == "identificado"
    assert s.get("hotel_la_parra")["nombre"] == "Hotel La Parra"


def test_crear_duplicado_falla():
    s = _store()
    s.crear("x", {"nombre": "X"})
    with pytest.raises(ValueError):
        s.crear("x", {"nombre": "X duplicado"})


def test_transicion_valida_persiste_historial():
    s = _store()
    s.crear("h", {"nombre": "H"})
    s.transicionar("h", EstadoLead.CUALIFICADO, razon="pasa ICP",
                   detalle={"categoria": "hotel_boutique_con_desayuno"})
    n = s.get("h")
    assert n["estado"] == "cualificado"
    assert len(n["historial"]) == 2
    assert n["historial"][-1]["desde"] == "identificado"
    assert n["historial"][-1]["a"] == "cualificado"
    assert n["historial"][-1]["detalle"]["categoria"] == "hotel_boutique_con_desayuno"


def test_transicion_invalida_lanza():
    s = _store()
    s.crear("h", {"nombre": "H"})
    # No se puede saltar de identificado directamente a cliente_activo.
    with pytest.raises(TransicionInvalida):
        s.transicionar("h", EstadoLead.CLIENTE_ACTIVO, razon="atajo ilegal")
    # El estado no debe haber cambiado.
    assert s.get("h")["estado"] == "identificado"


def test_perdido_es_terminal():
    s = _store()
    s.crear("h", {"nombre": "H"})
    s.transicionar("h", EstadoLead.PERDIDO, razon="sin respuesta")
    # Desde PERDIDO no hay transición saliente.
    assert TRANSICIONES_VALIDAS[EstadoLead.PERDIDO] == set()
    with pytest.raises(TransicionInvalida):
        s.transicionar("h", EstadoLead.CUALIFICADO, razon="resucitar")


def test_parches_actualizan_otros_campos():
    s = _store()
    s.crear("h", {"nombre": "H", "scoring_inicial": 0.5})
    s.transicionar("h", EstadoLead.CUALIFICADO, razon="ok",
                   parches={"scoring_inicial": 0.85, "anillo": 1})
    n = s.get("h")
    assert n["scoring_inicial"] == 0.85
    assert n["anillo"] == 1


def test_contar_por_estado():
    s = _store()
    for i in range(3):
        s.crear(f"l{i}", {"nombre": f"L{i}"})
    s.transicionar("l0", EstadoLead.CUALIFICADO, razon="ok")
    s.transicionar("l1", EstadoLead.PERDIDO, razon="ko")
    c = s.contar_por_estado()
    assert c["identificado"] == 1
    assert c["cualificado"] == 1
    assert c["perdido"] == 1


def test_listar_por_estado():
    s = _store()
    s.crear("a", {"nombre": "A"})
    s.crear("b", {"nombre": "B"})
    s.transicionar("a", EstadoLead.CUALIFICADO, razon="ok")
    cualificados = s.listar(EstadoLead.CUALIFICADO)
    assert len(cualificados) == 1 and cualificados[0]["id"] == "a"
    assert len(s.listar()) == 2
