"""Tests del puente aditivo Researcher -> lead_canon (departments/comercial/puente_canonico.py).

R-TENANT: usa el tenant sintetico 'laboratorio'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.anillos import ResultadoAnillo
from departments.comercial.cubo_serie_d import PipelineCanonico
from departments.comercial.fuentes.base import CandidatoCrudo
from departments.comercial.icp import DecisionICP
from departments.comercial.puente_canonico import construir_lead_canonico, dar_alta_canonico

TS_FIJO = "2026-08-06T10:00:00+00:00"


def _cand(*, id_externo="ChIJ_fake_place_id", telefono="968 000 000", web="https://x.test"):
    return CandidatoCrudo(
        fuente="google_places", id_externo=id_externo,
        nombre="Hotel La Parra", direccion="Hotel La Parra, Murcia",
        ubicacion={"lat": 38.24, "lon": -1.42},
        tipo_principal="lodging", place_types=["lodging"],
        descripcion="Hotel boutique",
        metadatos={"telefono": telefono, "web": web},
    )


def _decision():
    return DecisionICP(True, ["Encaja en hoteles (ALTA): place_type"],
                       categoria="hoteles", prioridad="ALTA",
                       senal="place_type", peso=2)


def _anillo():
    return ResultadoAnillo(anillo=0, distancia_minutos=12.0, distancia_metros=8000.0,
                           proveedor="haversine", activo=True)


# ── construir_lead_canonico ──────────────────────────────────────────────────

def test_construir_lead_canonico_pasa_gates_s1_s2_de_alta_lead():
    lead = construir_lead_canonico(_cand(), _decision(), _anillo(), ts=TS_FIJO)

    k = InMemoryKnowledge()
    pipeline = PipelineCanonico(k, "laboratorio")
    alta = pipeline.alta_lead(lead)   # no debe lanzar GateLegal

    assert alta["estado"] == "COLD"
    assert alta["contacto"]["publicado_por_el_negocio"] is True
    assert "ChIJ_fake_place_id" in alta["fuentes"][0]["url"]
    assert alta["fuentes"][0]["fecha"] == TS_FIJO


def test_construir_lead_canonico_sin_telefono_ni_web_no_bloquea_s2():
    lead = construir_lead_canonico(_cand(telefono="", web=""), _decision(), _anillo(), ts=TS_FIJO)
    assert lead["contacto"] == {}   # contacto vacio: S2 no lo exige (no es truthy)

    k = InMemoryKnowledge()
    pipeline = PipelineCanonico(k, "laboratorio")
    alta = pipeline.alta_lead(lead)   # tampoco debe lanzar GateLegal
    assert alta["contacto"] == {}


def test_construir_lead_canonico_id_externo_vacio_no_revienta():
    lead = construir_lead_canonico(_cand(id_externo=""), _decision(), _anillo(), ts=TS_FIJO)
    # No debe reventar con KeyError al construir ni al emitir el sobre en alta_lead.
    assert lead["fuentes"][0]["url"]
    assert lead["fuentes"][0]["fecha"] == TS_FIJO

    k = InMemoryKnowledge()
    pipeline = PipelineCanonico(k, "laboratorio")
    pipeline.alta_lead(lead)   # no debe lanzar KeyError


# ── dar_alta_canonico ─────────────────────────────────────────────────────────

def test_dar_alta_canonico_segunda_llamada_mismo_lead_devuelve_none():
    k = InMemoryKnowledge()
    pipeline = PipelineCanonico(k, "laboratorio")
    lead = construir_lead_canonico(_cand(), _decision(), _anillo(), ts=TS_FIJO)

    primera = dar_alta_canonico(pipeline, lead)
    assert primera is not None
    assert k.get("laboratorio", "lead_canon", lead["id"]) is not None

    segunda = dar_alta_canonico(pipeline, dict(lead))
    assert segunda is None   # no sobrescribe


def test_dar_alta_canonico_degrada_gate_legal_a_none():
    k = InMemoryKnowledge()
    pipeline = PipelineCanonico(k, "laboratorio")
    lead = construir_lead_canonico(_cand(), _decision(), _anillo(), ts=TS_FIJO)
    lead["fuentes"] = []   # fuerza S1: sin procedencia

    resultado = dar_alta_canonico(pipeline, lead)   # no debe propagar GateLegal
    assert resultado is None
    assert k.get("laboratorio", "lead_canon", lead["id"]) is None
