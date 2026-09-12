# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del director de Ops (panel_mando/herramientas/
ops.py). Cada ToolSpec se prueba construyendo el objeto real del departamento
(CuboOps con InMemoryKnowledge) e invocando fn/validar de verdad. R-TENANT:
tenant sintetico 'laboratorio', jamas un tenant real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.ops.cubo_serie_d import CuboOps
from panel_mando.herramientas import ops as M
from panel_mando.herramientas.base import ArgumentosInvalidos

TENANT = "laboratorio"


@pytest.fixture()
def k():
    return InMemoryKnowledge()


@pytest.fixture()
def b(k):
    return Bitacora(k, TENANT, fecha_alta="2026-07-10")


def _pedido(i, fecha="2026-07-15", **kw):
    return {"id": f"p{i}", "cliente_ref": f"c{i}", "producto": "lote surtido",
            "cantidad": 1, "fecha": fecha, **kw}


# ── helpers de contrato: nombre coincide, clase valida ──────────────────────

def test_registro_interno_bien_formado():
    for nombre, spec in M.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert callable(spec.fn)


def test_nunca_wireadas_ausentes():
    """registrar_hito y entregar_a_logistica NO deben estar registradas —
    atestacion de un hecho fisico que el director no puede verificar (ver
    docstring del modulo)."""
    for prohibida in ("registrar_hito", "entregar_a_logistica"):
        assert prohibida not in M.HERRAMIENTAS


def test_ninguna_irreversible_externa_registrada():
    assert not [s for s in M.HERRAMIENTAS.values() if s.clase == "IRREVERSIBLE-EXTERNA"]


# ── LECTURA ──────────────────────────────────────────────────────────────

def test_consultar_capacidad_sin_declarar(k, b):
    spec = M.HERRAMIENTAS["consultar_capacidad"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"fecha": "2026-07-15"}))
    assert r["declarada"] is False
    assert r["lotes"] is None
    assert r["disponible"] is None


def test_consultar_capacidad_tras_declarar(k, b):
    CuboOps(k, TENANT, bitacora=b).declarar_capacidad("2026-07-15", 5)
    spec = M.HERRAMIENTAS["consultar_capacidad"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"fecha": "2026-07-15"}))
    assert r["declarada"] is True
    assert r["lotes"] == 5
    assert r["disponible"] == 5


def test_proponer_secuencia(k, b):
    o = CuboOps(k, TENANT, bitacora=b)
    o.declarar_capacidad("2026-07-15", 10)
    o.recibir_pedido(_pedido(1)); o.confirmar("p1")
    o.recibir_pedido(_pedido(2, urgente=True)); o.confirmar("p2")
    spec = M.HERRAMIENTAS["proponer_secuencia"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"fecha": "2026-07-15"}))
    assert r["fecha"] == "2026-07-15"
    assert r["secuencia"] == ["p2", "p1"]        # urgente primero


def test_alerta_stock_bajo_seguridad(k, b):
    k.add(TENANT, "inventario", "harina", {"material": "harina", "stock": 2,
                                           "stock_seguridad": 10})
    k.add(TENANT, "inventario", "azucar", {"material": "azucar", "stock": 20,
                                           "stock_seguridad": 5})
    spec = M.HERRAMIENTAS["alerta_stock"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({}))
    assert r["alertas"] == [{"material": "harina", "stock": 2, "seguridad": 10}]


def test_capacidad_supera_umbral_por_defecto():
    spec = M.HERRAMIENTAS["capacidad_supera_umbral"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"ocupada_pct": 0.95}))
    assert r["pasa"] is False
    assert "90%" in r["motivo"]


def test_capacidad_supera_umbral_con_umbral_explicito():
    spec = M.HERRAMIENTAS["capacidad_supera_umbral"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"ocupada_pct": 0.5, "umbral": 0.4}))
    assert r["pasa"] is False
    r2 = spec.fn(k=None, tenant=TENANT, bitacora=None,
                **spec.validar({"ocupada_pct": 0.3, "umbral": 0.4}))
    assert r2["pasa"] is True


def test_stock_bajo_seguridad(k):
    spec = M.HERRAMIENTAS["stock_bajo_seguridad"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"stock": 2, "seguridad": 10}))
    assert r["pasa"] is False
    r2 = spec.fn(k=None, tenant=TENANT, bitacora=None,
                **spec.validar({"stock": 20, "seguridad": 10}))
    assert r2["pasa"] is True


# ── REVERSIBLE ───────────────────────────────────────────────────────────

def test_declarar_capacidad(k, b):
    spec = M.HERRAMIENTAS["declarar_capacidad"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"fecha": "2026-07-15", "lotes": 8}))
    assert r["fecha"] == "2026-07-15" and r["lotes"] == 8 and r["version"] == 1
    assert r["declarada_por"] == "operador"
    r2 = spec.fn(k=k, tenant=TENANT, bitacora=b,
                **spec.validar({"fecha": "2026-07-15", "lotes": 9, "por": "gerente",
                                "version_motivo": "ajuste"}))
    assert r2["version"] == 2 and r2["declarada_por"] == "gerente"


# ── G4: declarar_stock — nada mas escribia nodos tipo 'inventario' ─────────

def test_declarar_stock_escribe_el_esquema_que_alerta_stock_espera(k, b):
    spec = M.HERRAMIENTAS["declarar_stock"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"material": "harina", "cantidad": 2, "seguridad": 10}))
    assert r["material"] == "harina" and r["stock"] == 2.0 and r["stock_seguridad"] == 10.0
    assert r["declarado_por"] == "operador"
    guardado = k.get(TENANT, "inventario", "harina")
    assert guardado == r


def test_declarar_stock_flujo_completo_escribir_leer_via_alerta_stock(k, b):
    """AUDITORIA G4: antes de este fix nada escribia nodos tipo 'inventario' —
    alerta_stock estaba cableada a una fuente que ningun escritor real llenaba."""
    declarar = M.HERRAMIENTAS["declarar_stock"]
    declarar.fn(k=k, tenant=TENANT, bitacora=b,
               **declarar.validar({"material": "harina", "cantidad": 2, "seguridad": 10}))
    declarar.fn(k=k, tenant=TENANT, bitacora=b,
               **declarar.validar({"material": "azucar", "cantidad": 20, "seguridad": 5}))
    alerta = M.HERRAMIENTAS["alerta_stock"]
    r = alerta.fn(k=k, tenant=TENANT, bitacora=b, **alerta.validar({}))
    assert r["alertas"] == [{"material": "harina", "stock": 2.0, "seguridad": 10.0}]


def test_declarar_stock_redeclarar_mismo_material_sobrescribe(k, b):
    spec = M.HERRAMIENTAS["declarar_stock"]
    spec.fn(k=k, tenant=TENANT, bitacora=b,
           **spec.validar({"material": "harina", "cantidad": 2, "seguridad": 10}))
    spec.fn(k=k, tenant=TENANT, bitacora=b,
           **spec.validar({"material": "harina", "cantidad": 50, "seguridad": 10,
                           "por": "gerente"}))
    guardado = k.get(TENANT, "inventario", "harina")
    assert guardado["stock"] == 50.0 and guardado["declarado_por"] == "gerente"
    alerta = M.HERRAMIENTAS["alerta_stock"]
    r = alerta.fn(k=k, tenant=TENANT, bitacora=b, **alerta.validar({}))
    assert r["alertas"] == []                          # 50 >= 10: ya no alerta


def test_recibir_pedido(k, b):
    spec = M.HERRAMIENTAS["recibir_pedido"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({
        "id": "p1", "cliente_ref": "c1", "producto": "lote surtido",
        "cantidad": 3, "fecha": "2026-07-15"}))
    assert r["estado"] == "PENDIENTE_CONFIRMACION"
    assert k.get(TENANT, "pedido_ops", "p1")["cliente_ref"] == "c1"


def test_recibir_pedido_con_urgente_y_loyal(k, b):
    spec = M.HERRAMIENTAS["recibir_pedido"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({
        "id": "p1", "cliente_ref": "c1", "producto": "lote surtido",
        "cantidad": 3, "fecha": "2026-07-15", "urgente": True, "cliente_loyal": True}))
    assert r["urgente"] is True and r["cliente_loyal"] is True


def test_recibir_pedido_mal_formado_sube_la_excepcion(k, b):
    """recibir_pedido no atrapa excepciones: si el pedido real subyacente
    fallara la validacion (aqui forzado con cantidad=0, que 'not 0' es True),
    la excepcion del departamento sube intacta."""
    spec = M.HERRAMIENTAS["recibir_pedido"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({
            "id": "p1", "cliente_ref": "c1", "producto": "lote surtido",
            "cantidad": 0, "fecha": "2026-07-15"}))


# ── IRREVERSIBLE-INTERNA (invocadas directo aqui: la frontera de invocar()
#    vive en base.py/colmena.py, no en el fn en si — se prueba en su propio
#    test) ──────────────────────────────────────────────────────────────────

def test_confirmar_ejecuta_el_claim_real(k, b):
    o = CuboOps(k, TENANT, bitacora=b)
    o.declarar_capacidad("2026-07-15", 1)
    o.recibir_pedido(_pedido(1))
    spec = M.HERRAMIENTAS["confirmar"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"pedido_id": "p1"}))
    assert r["estado"] == "CONFIRMADO"


def test_confirmar_sin_capacidad_pende(k, b):
    o = CuboOps(k, TENANT, bitacora=b)
    o.recibir_pedido(_pedido(9, fecha="2026-08-01"))
    spec = M.HERRAMIENTAS["confirmar"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"pedido_id": "p9"}))
    assert r["estado"] == "PENDIENTE_CONFIRMACION"
    assert r["pendiente_por"] == "capacidad_no_declarada"


def test_confirmar_pedido_inexistente_sube_la_excepcion(k, b):
    spec = M.HERRAMIENTAS["confirmar"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"pedido_id": "no-existe"}))


def test_barrer_pendientes(k, b):
    from datetime import datetime, timedelta, timezone
    o = CuboOps(k, TENANT, bitacora=b)
    o.recibir_pedido(_pedido(1, fecha="2026-07-15"))
    ahora = datetime.now(timezone.utc) + timedelta(hours=25)
    # barrer_pendientes no expone `ahora` como argumento de la herramienta
    # (no aplanable a los tipos declarados) — se prueba directamente sobre
    # el objeto real que el mismo cubo usaria internamente para el aviso de
    # 24h, y la herramienta (sin argumentos) se prueba sobre el caso base.
    assert o.barrer_pendientes(ahora=ahora) == [{"pedido": "p1", "sla": "24h→operador"}]
    spec = M.HERRAMIENTAS["barrer_pendientes"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({}))
    assert r == {"avisos": []}                  # recien recibido: aun no pasan las 24h


# ── validacion de argumentos ─────────────────────────────────────────────

def test_argumento_no_declarado_rechazado():
    spec = M.HERRAMIENTAS["consultar_capacidad"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"fecha": "2026-07-15", "intruso": "x"})


def test_argumento_obligatorio_ausente_rechazado():
    spec = M.HERRAMIENTAS["declarar_capacidad"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"fecha": "2026-07-15"})     # falta 'lotes'


def test_tipo_incorrecto_rechazado_no_coercion_silenciosa():
    spec = M.HERRAMIENTAS["declarar_capacidad"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"fecha": "2026-07-15", "lotes": "no-es-numero"})


def test_argumento_opcional_ausente_no_rompe():
    spec = M.HERRAMIENTAS["capacidad_supera_umbral"]
    limpios = spec.validar({"ocupada_pct": 0.5})
    assert "umbral" not in limpios
