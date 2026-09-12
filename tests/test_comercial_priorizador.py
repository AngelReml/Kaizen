"""Tests del Priorizador — ordenación determinista por anillo, prioridad y reseñas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.priorizador import Priorizador


def _seed_lead(store: LeadStore, lead_id: str, *, anillo: int, prioridad: str,
               ratings: int = 0, rating: float = 0.0, estado: EstadoLead = EstadoLead.ENRIQUECIDO):
    store.crear(lead_id, {
        "nombre": lead_id, "anillo": anillo, "prioridad_icp": prioridad,
        "metadatos_fuente": {"ratings_count": ratings, "rating": rating},
    })
    store.transicionar(lead_id, EstadoLead.CUALIFICADO, razon="seed")
    if estado != EstadoLead.CUALIFICADO:
        store.transicionar(lead_id, EstadoLead.ENRIQUECIDO, razon="seed")


def _store():
    return LeadStore(InMemoryKnowledge(), "laboratorio")


def test_orden_anillo_prioridad_reseñas():
    s = _store()
    _seed_lead(s, "h_a1_alta", anillo=1, prioridad="ALTA", ratings=10)
    _seed_lead(s, "h_a0_alta", anillo=0, prioridad="ALTA", ratings=10)
    _seed_lead(s, "h_a0_baja", anillo=0, prioridad="BAJA", ratings=10)
    _seed_lead(s, "h_a0_media", anillo=0, prioridad="MEDIA", ratings=10)
    cola = Priorizador(s).cola()
    ids = [l["id"] for l in cola]
    # Anillo 0 antes que 1; dentro de anillo 0: ALTA > MEDIA > BAJA.
    assert ids == ["h_a0_alta", "h_a0_media", "h_a0_baja", "h_a1_alta"]


def test_desempate_por_ratings_count():
    s = _store()
    _seed_lead(s, "b", anillo=0, prioridad="ALTA", ratings=100)
    _seed_lead(s, "a", anillo=0, prioridad="ALTA", ratings=500)
    _seed_lead(s, "c", anillo=0, prioridad="ALTA", ratings=10)
    ids = [l["id"] for l in Priorizador(s).cola()]
    # Mismo anillo + prioridad → más reseñas primero.
    assert ids == ["a", "b", "c"]


def test_limite_y_filtro_prioridades():
    s = _store()
    for i, prio in enumerate(["ALTA", "MEDIA", "BAJA", "ALTA"]):
        _seed_lead(s, f"l{i}", anillo=0, prioridad=prio, ratings=100 - i)
    cola = Priorizador(s).cola(prioridades=("ALTA",), limite=2)
    assert len(cola) == 2
    assert all(l["prioridad_icp"] == "ALTA" for l in cola)


def test_solo_devuelve_estado_pedido():
    s = _store()
    _seed_lead(s, "enr", anillo=0, prioridad="ALTA", ratings=10, estado=EstadoLead.ENRIQUECIDO)
    _seed_lead(s, "cua", anillo=0, prioridad="ALTA", ratings=10, estado=EstadoLead.CUALIFICADO)
    assert {l["id"] for l in Priorizador(s).cola(estado=EstadoLead.ENRIQUECIDO)} == {"enr"}
    assert {l["id"] for l in Priorizador(s).cola(estado=EstadoLead.CUALIFICADO)} == {"cua"}


def test_excluir_ids():
    s = _store()
    _seed_lead(s, "a", anillo=0, prioridad="ALTA", ratings=10)
    _seed_lead(s, "b", anillo=0, prioridad="ALTA", ratings=10)
    cola = Priorizador(s).cola(excluir_lead_ids={"a"})
    assert [l["id"] for l in cola] == ["b"]
