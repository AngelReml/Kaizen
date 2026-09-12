"""Tests de Enrichment con leads sembrados directamente en CUALIFICADO."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.enrichment import Enrichment
from departments.comercial.lifecycle import EstadoLead, LeadStore


def _store_con_leads(leads):
    """Crea un LeadStore y siembra cada lead en estado CUALIFICADO con metadatos."""
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    for lid, datos in leads.items():
        store.crear(lid, datos, razon="seed")
        store.transicionar(lid, EstadoLead.CUALIFICADO, razon="seed", detalle={})
    return store


def test_enriquece_lead_operativo_con_contacto():
    store = _store_con_leads({
        "hotel_x": {
            "nombre": "Hotel X",
            "metadatos_fuente": {"business_status": "OPERATIONAL", "ratings_count": 25, "rating": 4.5},
            "contacto": {"telefono": "968111111", "web": "https://x.test"},
        }
    })
    res = Enrichment(lead_store=store).procesar_todos(verbose=False)
    assert res.enriquecidos == 1
    lead = store.get("hotel_x")
    assert lead["estado"] == EstadoLead.ENRIQUECIDO.value
    assert lead["tamano_estimado"] == "pequeno"     # 25 reseñas → pequeño (5-49)
    assert "actualidad_signal" in lead
    assert lead["actualidad_signal"]["ratings_count"] == 25


def test_descarta_a_perdido_si_no_operativo():
    store = _store_con_leads({
        "hotel_cerrado": {
            "nombre": "Hotel Cerrado",
            "metadatos_fuente": {"business_status": "CLOSED_PERMANENTLY", "ratings_count": 100},
            "contacto": {"telefono": "968111111"},
        }
    })
    Enrichment(lead_store=store).procesar_todos(verbose=False)
    assert store.get("hotel_cerrado")["estado"] == EstadoLead.PERDIDO.value


def test_se_queda_en_cualificado_sin_canales_de_contacto():
    store = _store_con_leads({
        "lead_sin_contacto": {
            "nombre": "Lead Sin Contacto",
            "metadatos_fuente": {"business_status": "OPERATIONAL", "ratings_count": 10},
            "contacto": {"telefono": None, "web": None},
        }
    })
    res = Enrichment(lead_store=store).procesar_todos(verbose=False)
    assert res.enriquecidos == 0
    lead = store.get("lead_sin_contacto")
    assert lead["estado"] == EstadoLead.CUALIFICADO.value
    assert "sin_canales" in lead.get("problemas_enrichment", [])


def test_se_queda_en_cualificado_sin_resenas():
    store = _store_con_leads({
        "lead_sin_resenas": {
            "nombre": "Lead Sin Reseñas",
            "metadatos_fuente": {"business_status": "OPERATIONAL", "ratings_count": 0},
            "contacto": {"telefono": "968111111"},
        }
    })
    Enrichment(lead_store=store).procesar_todos(verbose=False)
    lead = store.get("lead_sin_resenas")
    assert lead["estado"] == EstadoLead.CUALIFICADO.value
    assert "sin_reseñas" in lead.get("problemas_enrichment", [])


def test_tamano_estimado_por_ratings_count():
    casos = [(1, "minimo"), (10, "pequeno"), (60, "medio"), (300, "grande")]
    for n, esperado in casos:
        store = _store_con_leads({
            f"l_{n}": {"nombre": f"L{n}",
                       "metadatos_fuente": {"business_status": "OPERATIONAL", "ratings_count": n},
                       "contacto": {"telefono": "x", "web": "y"}}
        })
        Enrichment(lead_store=store).procesar_todos(verbose=False)
        assert store.get(f"l_{n}")["tamano_estimado"] == esperado, f"n={n}"
