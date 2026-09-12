"""Tests del esquema LeadDoc — `from_dict` blando + `to_dict` round-trip."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.lead_schema import (
    LeadDoc, Ubicacion, Contacto, Interaccion, Compromiso, PoliticaReintentos,
    mapear_legacy_a_pipeline, SCHEMA_VERSION,
)


# ── Validaciones duras (las dos únicas) ──────────────────────────────────────
def test_falla_sin_id():
    with pytest.raises(ValueError, match="id"):
        LeadDoc.from_dict({"company": "laboratorio"})


def test_falla_sin_company():
    with pytest.raises(ValueError, match="company"):
        LeadDoc.from_dict({"id": "x"})


# ── from_dict con un lead mínimo ─────────────────────────────────────────────
def test_lead_minimo_rellena_defaults():
    doc = LeadDoc.from_dict({"id": "x", "company": "laboratorio"})
    assert doc.id == "x"
    assert doc.company == "laboratorio"
    assert doc.nombre == ""
    assert doc.categoria_icp == ""
    assert doc.anillo == 99
    assert doc.estado == "identificado"
    assert doc.estado_pipeline == "cold"        # mapeado del legacy
    assert isinstance(doc.ubicacion, Ubicacion)
    assert isinstance(doc.contacto, Contacto)
    assert isinstance(doc.reintentos, PoliticaReintentos)
    assert doc.interacciones == []
    assert doc.compromisos == []
    assert doc.do_not_call is False
    assert doc._schema_version == SCHEMA_VERSION


# ── from_dict con un lead legacy real ────────────────────────────────────────
def test_lead_legacy_real_no_pierde_campos():
    """Caso parecido a un lead real del piloto (restaurante_la_cabana). Todos los
    campos del JSON se preservan; los del schema están tipados."""
    raw = {
        "id": "restaurante_la_cabana",
        "company": "laboratorio",
        "nombre": "Restaurante La Cabaña",
        "tipo_detectado": "restaurant",
        "categoria_icp": "cafeteria_especialidad",
        "prioridad_icp": "ALTA",
        "anillo": 0,
        "ubicacion": {"lat": 38.24, "lon": -1.42, "direccion": "Cieza"},
        "distancia_minutos": 11.0,
        "distancia_provider": "google_routes",
        "fuentes": [{"nombre": "google_places", "id_externo": "ChIJxx"}],
        "contacto": {"telefono": "+34968000000", "web": "https://example.com"},
        "metadatos_fuente": {"rating": 4.3, "ratings_count": 1090},
        "descripcion": "Restaurante en Cieza",
        "tamano_estimado": "grande",
        "actualidad_signal": {"ratings_count": 1090, "rating": 4.3},
        "checklists": {"enrichment": {"ok": True}},
        "estado": "enriquecido",
        "creado_en": "2026-05-26T00:00:00+00:00",
        "actualizado_en": "2026-05-26T00:10:00+00:00",
        "historial": [{"ts": "2026-05-26T00:00:00+00:00", "desde": None, "a": "identificado", "razon": "seed"}],
    }
    doc = LeadDoc.from_dict(raw)
    assert doc.id == "restaurante_la_cabana"
    assert doc.categoria_icp == "cafeteria_especialidad"
    assert doc.anillo == 0
    assert doc.contacto.telefono == "+34968000000"
    assert doc.metadatos_fuente["rating"] == 4.3
    assert doc.estado == "enriquecido"
    assert doc.estado_pipeline == "cold"        # enriquecido → cold
    assert doc.historial[0]["a"] == "identificado"


def test_round_trip_dict_a_dict_es_idempotente():
    """from_dict → to_dict produce dict equivalente, sin perder ni inventar campos."""
    raw = {
        "id": "x", "company": "laboratorio",
        "nombre": "X", "anillo": 1,
        "campo_extra_que_no_modelamos": "valor_libre",   # debe sobrevivir vía metadatos_extra
        "fuentes": [{"nombre": "x", "id_externo": "y"}],
    }
    doc = LeadDoc.from_dict(raw)
    out = doc.to_dict()
    # Campos modelados presentes
    assert out["id"] == "x" and out["company"] == "laboratorio"
    assert out["nombre"] == "X" and out["anillo"] == 1
    # Campo extra preservado al desempaquetar metadatos_extra
    assert out["campo_extra_que_no_modelamos"] == "valor_libre"
    # Y como ya lo desempaquetamos al nivel raíz, no debe quedar también dentro de
    # metadatos_extra duplicado: ese sub-dict no aparece en el dict de salida.
    assert "metadatos_extra" not in out
    # Round-trip una segunda vez no cambia nada
    doc2 = LeadDoc.from_dict(out)
    out2 = doc2.to_dict()
    assert out2 == out


def test_metadatos_extra_no_pisan_modelado():
    """Si un lead trae un campo que existe en el schema, gana el schema, no extras."""
    raw = {"id": "x", "company": "laboratorio", "nombre": "Modelado", "extra_libre": "ok"}
    doc = LeadDoc.from_dict(raw)
    out = doc.to_dict()
    assert out["nombre"] == "Modelado"
    assert out["extra_libre"] == "ok"


# ── Subdocumentos ────────────────────────────────────────────────────────────
def test_interaccion_desde_dict():
    raw = {
        "id": "x", "company": "laboratorio",
        "interacciones": [
            {"ts": "2026-05-26T18:16:00+00:00", "tipo": "llamada",
             "direccion": "outbound", "resultado": "contestado",
             "canal_id": "CA469a", "transcript_id": "conv_3201",
             "resumen_llm": "Lidia, callback mañana 10-11h.", "duracion_s": 89.0},
        ],
    }
    doc = LeadDoc.from_dict(raw)
    assert len(doc.interacciones) == 1
    i = doc.interacciones[0]
    assert i.tipo == "llamada" and i.resultado == "contestado"
    assert i.canal_id == "CA469a" and i.duracion_s == 89.0


def test_compromiso_desde_dict():
    raw = {
        "id": "x", "company": "laboratorio",
        "compromisos": [
            {"id": "compr1", "tipo": "callback",
             "fecha_objetivo": "2026-05-28T10:00:00+00:00",
             "tolerancia_min": 30,
             "contexto": "Llamar al encargado entre las 10 y las 11.",
             "origen_interaccion_id": "CA469a"},
        ],
    }
    doc = LeadDoc.from_dict(raw)
    c = doc.compromisos[0]
    assert c.tipo == "callback"
    assert c.fecha_objetivo == "2026-05-28T10:00:00+00:00"
    assert c.tolerancia_min == 30
    assert c.cumplido is False


def test_reintentos_desde_dict():
    raw = {
        "id": "x", "company": "laboratorio",
        "reintentos": {
            "proxima_accion_ts": "2026-05-28T10:00:00+00:00",
            "proxima_accion_tipo": "llamar",
            "intentos_realizados": 1,
            "max_intentos": 3,
            "ultima_razon_reintento": "callback pactado con Lidia",
        },
    }
    doc = LeadDoc.from_dict(raw)
    r = doc.reintentos
    assert r.intentos_realizados == 1
    assert r.max_intentos == 3
    assert r.proxima_accion_tipo == "llamar"


def test_do_not_call_marca_y_persiste():
    raw = {"id": "x", "company": "laboratorio", "do_not_call": True}
    doc = LeadDoc.from_dict(raw)
    assert doc.do_not_call is True
    out = doc.to_dict()
    assert out["do_not_call"] is True


# ── Mapeo legacy → pipeline ─────────────────────────────────────────────────
def test_mapear_legacy_a_pipeline_estados_conocidos():
    assert mapear_legacy_a_pipeline("identificado") == "cold"
    assert mapear_legacy_a_pipeline("cualificado") == "cold"
    assert mapear_legacy_a_pipeline("enriquecido") == "cold"
    assert mapear_legacy_a_pipeline("en_contacto") == "contacting"
    assert mapear_legacy_a_pipeline("compromiso_reciproco") == "engaged"
    assert mapear_legacy_a_pipeline("muestra_enviada") == "sample_sent"
    assert mapear_legacy_a_pipeline("cliente_activo") == "customer"
    assert mapear_legacy_a_pipeline("en_riesgo") == "customer"
    assert mapear_legacy_a_pipeline("perdido") == "lost"


def test_mapear_legacy_a_pipeline_estado_desconocido_default_cold():
    assert mapear_legacy_a_pipeline("zombi") == "cold"
    assert mapear_legacy_a_pipeline("") == "cold"


def test_estado_pipeline_explicito_no_se_sobrescribe():
    """Si el dict ya trae estado_pipeline, no se vuelve a derivar del legacy."""
    raw = {"id": "x", "company": "laboratorio", "estado": "enriquecido",
           "estado_pipeline": "engaged"}
    doc = LeadDoc.from_dict(raw)
    assert doc.estado_pipeline == "engaged"


# ── Compatibilidad con campos legacy específicos del knowledge ──────────────
def test_campos_legacy_se_preservan():
    """Los campos que ya existían en el knowledge sobreviven al round-trip."""
    raw = {
        "id": "x", "company": "laboratorio",
        "distancia_minutos": 33.0,
        "distancia_provider": "google_routes",
        "fuentes": [{"nombre": "google_places", "id_externo": "ChIJxx"}],
        "checklists": {"enrichment": {"ok": True, "criterios": ["a", "b"]}},
        "email_discovery": {"email": "info@x.com", "fuente": "web", "metodo": "regex"},
        "actualidad_signal": {"ratings_count": 50, "rating": 4.5,
                              "business_status": "OPERATIONAL", "metodo": "google_places"},
        "problemas_enrichment": [],
    }
    doc = LeadDoc.from_dict(raw)
    out = doc.to_dict()
    for k in raw:
        if k in ("id", "company"):
            continue
        assert out[k] == raw[k], f"campo legacy '{k}' no preservado: {out[k]} vs {raw[k]}"


def test_schema_version_se_eleva_al_cargar_legacy():
    """Lead sin _schema_version (legacy) → al cargar queda con SCHEMA_VERSION."""
    raw = {"id": "x", "company": "laboratorio"}
    doc = LeadDoc.from_dict(raw)
    assert doc._schema_version == SCHEMA_VERSION
