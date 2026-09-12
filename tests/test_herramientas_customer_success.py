# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del director de Customer Success
(panel_mando/herramientas/customer_success.py). Cada ToolSpec se prueba
construyendo el estado real en InMemoryKnowledge e invocando fn/validar de
verdad, igual que hace CustomerSuccessDepartment/departments.customer_success.
herramientas por debajo. R-TENANT: tenant sintetico 'laboratorio', jamas un
tenant real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from departments.customer_success import herramientas as cs_herramientas
from panel_mando.herramientas import customer_success as M
from panel_mando.herramientas.base import ArgumentosInvalidos

TENANT = "laboratorio"


@pytest.fixture()
def k():
    return InMemoryKnowledge()


def _cliente(k, nombre="Panaderia Ana", valor_mensual=100.0, **extra):
    ficha = cs_herramientas.alta_cliente(k, TENANT, nombre=nombre, valor_mensual=valor_mensual)
    if extra:
        ficha.update(extra)
        k.add(TENANT, "cliente_cs", ficha["id"], ficha)
    return ficha


# ── helpers de contrato: nombre coincide, clase valida ──────────────────────

def test_registro_interno_bien_formado():
    for nombre, spec in M.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert callable(spec.fn)


def test_nunca_wireadas_ausentes():
    """alta_cliente, registrar_contacto y abrir_ticket NO deben estar
    registradas — fuera del mapa de capacidades auditado para este cubo (ver
    docstring del modulo)."""
    for prohibida in ("alta_cliente", "registrar_contacto", "abrir_ticket"):
        assert prohibida not in M.HERRAMIENTAS


def test_ninguna_irreversible_externa_registrada():
    assert not [s for s in M.HERRAMIENTAS.values() if s.clase == "IRREVERSIBLE-EXTERNA"]


# ── LECTURA ──────────────────────────────────────────────────────────────

def test_detectar_churn_sin_riesgo(k):
    _cliente(k)
    spec = M.HERRAMIENTAS["detectar_churn"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["riesgo"] == []


def test_detectar_churn_por_nps_detractor(k):
    ficha = _cliente(k, nombre="Panaderia Roja", valor_mensual=250.0, nps=3)
    spec = M.HERRAMIENTAS["detectar_churn"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert len(r["riesgo"]) == 1
    assert r["riesgo"][0]["cliente_id"] == ficha["id"]
    assert "NPS 3 (detractor)" in r["riesgo"][0]["motivos"]


def test_detectar_upsell_por_nps_alto(k):
    ficha = _cliente(k, nombre="Panaderia Feliz", nps=9)
    spec = M.HERRAMIENTAS["detectar_upsell"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert len(r["oportunidades"]) == 1
    assert r["oportunidades"][0]["cliente_id"] == ficha["id"]


def test_detectar_upsell_vacio_sin_promotores(k):
    _cliente(k, nps=5)
    spec = M.HERRAMIENTAS["detectar_upsell"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["oportunidades"] == []


def test_salud_cartera(k):
    _cliente(k, nombre="A", nps=9)
    _cliente(k, nombre="B", nps=3, valor_mensual=50.0)
    spec = M.HERRAMIENTAS["salud_cartera"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["clientes_activos"] == 2
    assert r["en_riesgo"] == 1
    assert r["valor_en_riesgo"] == 50.0
    assert r["nps_medio"] == 6.0


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def test_barrido_churn_ejecuta_de_verdad_y_devuelve_el_resultado_real(k):
    ficha = _cliente(k, nombre="Panaderia Roja", valor_mensual=250.0, nps=2)
    spec = M.HERRAMIENTAS["barrido_churn"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert len(r["alertas"]) == 1
    assert r["alertas"][0]["cliente_id"] == ficha["id"]


def test_barrido_churn_vacio_sin_clientes_en_riesgo(k):
    _cliente(k)
    spec = M.HERRAMIENTAS["barrido_churn"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["alertas"] == []


def test_barrido_upsell_ejecuta_de_verdad_y_devuelve_el_resultado_real(k):
    ficha = _cliente(k, nombre="Panaderia Feliz", nps=10)
    spec = M.HERRAMIENTAS["barrido_upsell"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert len(r["oportunidades"]) == 1
    assert r["oportunidades"][0]["cliente_id"] == ficha["id"]


# ── IRREVERSIBLE-INTERNA (invocadas directo aqui: la frontera de invocar()
#    vive en base.py/colmena.py, no en el fn en si — se prueba en su propio
#    test) ──────────────────────────────────────────────────────────────────

def test_renovar_cliente_existente(k):
    ficha = _cliente(k)
    spec = M.HERRAMIENTAS["renovar"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"cliente_id": ficha["id"]}))
    assert r["renovado"] is True
    assert r["cliente_id"] == ficha["id"]
    assert r["ficha"]["renovaciones"] == 1
    # segunda renovacion incrementa de nuevo, sobre el estado persistido real
    r2 = spec.fn(k=k, tenant=TENANT, bitacora=None,
                **spec.validar({"cliente_id": ficha["id"]}))
    assert r2["ficha"]["renovaciones"] == 2


def test_renovar_cliente_inexistente_es_honesto_no_none_ni_excepcion(k):
    spec = M.HERRAMIENTAS["renovar"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"cliente_id": "no-existe"}))
    assert r is not None
    assert r["renovado"] is False
    assert r["cliente_id"] == "no-existe"
    assert "motivo" in r


# ── validacion de argumentos ─────────────────────────────────────────────

def test_argumento_no_declarado_rechazado():
    spec = M.HERRAMIENTAS["detectar_churn"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"intruso": "x"})


def test_argumento_obligatorio_ausente_rechazado():
    spec = M.HERRAMIENTAS["renovar"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({})     # falta 'cliente_id'


def test_tipo_incorrecto_no_aplica_str_acepta_cualquier_valor_coercible():
    """renovar solo declara cliente_id: str — un valor no-str se coacciona a
    str explicitamente (no hay coercion silenciosa a OTRO tipo, es el
    comportamiento declarado del validador para 'str')."""
    spec = M.HERRAMIENTAS["renovar"]
    limpios = spec.validar({"cliente_id": 123})
    assert limpios["cliente_id"] == "123"
