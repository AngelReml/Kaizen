"""Tests del descubrimiento de email — fetcher inyectado, sin red."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.email_discovery import (
    descubrir_email_de_web, descubrir_emails, _filtrar_y_rankear, _es_social,
)
from departments.comercial.lifecycle import EstadoLead, LeadStore


# ── Helpers de fetch fake ────────────────────────────────────────────────────
def _fetcher_factory(mapa: dict[str, str]):
    """Factory de fetchers para tests: devuelve la respuesta del mapa para URLs dadas."""
    def f(url, timeout=8): return mapa.get(url, "")
    return f


# ── _es_social ───────────────────────────────────────────────────────────────
def test_detecta_redes_sociales():
    assert _es_social("https://www.facebook.com/lacabana/") is True
    assert _es_social("https://www.instagram.com/x") is True
    assert _es_social("https://www.lacabana.es/") is False


# ── _filtrar_y_rankear ───────────────────────────────────────────────────────
def test_descarta_emails_tecnicos():
    assert _filtrar_y_rankear(["noreply@x.com", "info@x.com"]) == "info@x.com"
    assert _filtrar_y_rankear(["postmaster@x.com"]) is None


def test_prefiere_contacto_sobre_otros():
    elegido = _filtrar_y_rankear(["pepe@x.com", "contacto@x.com", "marketing@x.com"])
    assert elegido == "contacto@x.com"


def test_prefiere_info_si_no_hay_contacto():
    elegido = _filtrar_y_rankear(["pepe@x.com", "info@x.com", "marketing@x.com"])
    assert elegido == "info@x.com"


def test_cae_al_primero_si_no_hay_preferidos():
    elegido = _filtrar_y_rankear(["pepe@x.com", "ana@x.com"])
    assert elegido == "pepe@x.com"


# ── descubrir_email_de_web ───────────────────────────────────────────────────
def test_devuelve_none_para_red_social():
    email, motivo = descubrir_email_de_web("https://www.facebook.com/x/", fetcher=lambda *a, **k: "")
    assert email is None and motivo == "web_solo_social"


def test_devuelve_none_si_url_no_es_http():
    email, motivo = descubrir_email_de_web("", fetcher=lambda *a, **k: "")
    assert email is None and motivo == "sin_web"


def test_encuentra_email_en_pagina_principal():
    f = _fetcher_factory({"https://www.cafe.es/": "Contáctanos: hola@cafe.es"})
    email, motivo = descubrir_email_de_web("https://www.cafe.es/", fetcher=f)
    assert email == "hola@cafe.es"
    assert "web" in motivo


def test_intenta_subpagina_contacto_si_principal_no_tiene_email():
    f = _fetcher_factory({
        "https://www.cafe.es/": "Bienvenido al café",
        "https://www.cafe.es/contacto": "Escríbenos a info@cafe.es",
    })
    email, _ = descubrir_email_de_web("https://www.cafe.es/", fetcher=f)
    assert email == "info@cafe.es"


def test_devuelve_no_encontrado_si_nada_tiene_email():
    f = _fetcher_factory({"https://www.cafe.es/": "Bienvenido"})
    email, motivo = descubrir_email_de_web("https://www.cafe.es/", fetcher=f)
    assert email is None and motivo == "no_encontrado"


# ── descubrir_emails (integración con LeadStore) ─────────────────────────────
def _seed_lead(store, lid, web=None, email_previo=None):
    contacto = {}
    if web: contacto["web"] = web
    if email_previo: contacto["email"] = email_previo
    store.crear(lid, {"nombre": lid, "contacto": contacto})
    store.transicionar(lid, EstadoLead.CUALIFICADO, razon="seed")
    store.transicionar(lid, EstadoLead.ENRIQUECIDO, razon="seed")


def test_descubre_y_persiste_email():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed_lead(store, "cafe_x", web="https://www.cafex.es/")
    f = _fetcher_factory({"https://www.cafex.es/": "Email: contacto@cafex.es"})
    res = descubrir_emails(store, fetcher=f, verbose=False)
    assert res.descubiertos == 1
    actualizado = store.get("cafe_x")
    assert actualizado["contacto"]["email"] == "contacto@cafex.es"
    assert "email_discovery" in actualizado


def test_no_pisa_email_existente():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed_lead(store, "cafe_y", web="https://x.es", email_previo="ya@y.com")
    f = _fetcher_factory({"https://x.es": "info@x.es aparece aqui"})
    res = descubrir_emails(store, fetcher=f, verbose=False)
    assert res.descubiertos == 0
    assert res.con_email_previo == 1
    assert store.get("cafe_y")["contacto"]["email"] == "ya@y.com"


def test_cuenta_categorias_correctamente():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed_lead(store, "con_email",  web="https://x.es", email_previo="ya@x.com")
    _seed_lead(store, "sin_web",                          # ningún contacto
              web=None)
    _seed_lead(store, "solo_social", web="https://www.facebook.com/cafe/")
    _seed_lead(store, "no_encuentra", web="https://noemail.es")
    _seed_lead(store, "encontrado", web="https://si.es")
    f = _fetcher_factory({
        "https://noemail.es": "una web sin mail",
        "https://si.es": "info@si.es nuestro email",
    })
    res = descubrir_emails(store, fetcher=f, verbose=False)
    assert res.descubiertos == 1
    assert res.con_email_previo == 1
    assert res.sin_web == 1
    assert res.web_solo_social == 1
    assert res.no_encontrado == 1
