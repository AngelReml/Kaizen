"""Tests de la Cola de Aprobación: CRUD, máquina de estados, hash determinista, token."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.cola_aprobacion import ColaAprobacion, hash_mensaje


def _cola() -> ColaAprobacion:
    return ColaAprobacion(InMemoryKnowledge(), "laboratorio")


def test_hash_mensaje_determinista_y_sensible():
    h1 = hash_mensaje("email", "a@x.com", "Asunto", "Cuerpo")
    h2 = hash_mensaje("email", "a@x.com", "Asunto", "Cuerpo")
    h3 = hash_mensaje("email", "a@x.com", "Asunto", "Cuerpo modificado")
    assert h1 == h2
    assert h1 != h3


def test_encolar_y_listar():
    c = _cola()
    p1 = c.encolar(lead_id="l1", canal="email", destino="a@x.com",
                   asunto="A", cuerpo="B", brand_review={"aprobado": True},
                   campaign_id="cmp1")
    p2 = c.encolar(lead_id="l2", canal="email", destino="b@x.com",
                   asunto="C", cuerpo="D", brand_review={"aprobado": True},
                   campaign_id="cmp1")
    assert len(c.listar()) == 2
    assert len(c.listar(estado="pendiente")) == 2
    assert len(c.listar(estado="aprobado")) == 0
    assert {p["lead_id"] for p in c.listar()} == {"l1", "l2"}


def test_aprobar_genera_token_y_cambia_estado():
    c = _cola()
    p = c.encolar(lead_id="l", canal="email", destino="x@y.com",
                  asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp")
    nodo = c.aprobar(p.id, aprobado_por="test")
    assert nodo["estado"] == "aprobado"
    assert nodo["token_aprobacion"]                    # generado
    assert nodo["aprobado_por"] == "test"
    assert nodo["aprobado_en"]


def test_aprobar_idempotente_falla():
    c = _cola()
    p = c.encolar(lead_id="l", canal="email", destino="x@y.com",
                  asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp")
    c.aprobar(p.id)
    with pytest.raises(ValueError):
        c.aprobar(p.id)


def test_rechazar_cambia_estado_y_motivo():
    c = _cola()
    p = c.encolar(lead_id="l", canal="email", destino="x@y.com",
                  asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp")
    c.rechazar(p.id, motivo="No suena a Iván")
    nodo = c.get(p.id)
    assert nodo["estado"] == "rechazado"
    assert nodo["motivo_rechazo"] == "No suena a Iván"


def test_aprobar_campania_aprueba_todos_los_pendientes():
    c = _cola()
    ids = []
    for i in range(3):
        p = c.encolar(lead_id=f"l{i}", canal="email", destino=f"a{i}@x.com",
                      asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp_x")
        ids.append(p.id)
    # Aparte, uno de otra campaña que NO debe tocarse.
    p_otro = c.encolar(lead_id="otro", canal="email", destino="z@x.com",
                       asunto="A", cuerpo="B", brand_review={}, campaign_id="otra")
    aprobados = c.aprobar_campania("cmp_x")
    assert len(aprobados) == 3
    assert all(c.get(i)["estado"] == "aprobado" for i in ids)
    assert c.get(p_otro.id)["estado"] == "pendiente"


def test_marcar_enviado_requiere_estado_aprobado():
    c = _cola()
    p = c.encolar(lead_id="l", canal="email", destino="x@y.com",
                  asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp")
    with pytest.raises(ValueError):
        c.marcar_enviado(p.id)
    c.aprobar(p.id)
    nodo = c.marcar_enviado(p.id, referencia_externa="smtp:test")
    assert nodo["estado"] == "enviado"
    assert nodo["enviado_en"]
    assert nodo["referencia_externa"] == "smtp:test"
