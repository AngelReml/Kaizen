"""Tests de la migración del knowledge — no destructiva, idempotente."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge_migration import migrar, ResultadoMigracion, TIPO_LEAD
from core.lead_schema import SCHEMA_VERSION


def _knowledge_con_leads(tmp_path: Path, leads: dict, company: str = "laboratorio") -> Path:
    """Crea un knowledge.json en tmp_path con los leads dados."""
    raw = {company: {TIPO_LEAD: leads}}
    p = tmp_path / "knowledge.json"
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ── Casos base ──────────────────────────────────────────────────────────────
def test_knowledge_inexistente_no_falla_solo_reporta(tmp_path):
    p = tmp_path / "noexiste.json"
    res = migrar(knowledge_path=p, hacer_backup=False)
    assert res.leads_total == 0
    assert any("no existe" in e for e in res.errores)


def test_knowledge_vacio_no_hace_nada(tmp_path):
    p = _knowledge_con_leads(tmp_path, {})
    res = migrar(knowledge_path=p, hacer_backup=False)
    assert res.leads_total == 0
    assert res.leads_migrados == 0


def test_migra_lead_legacy_y_rellena_defaults(tmp_path):
    leads = {
        "restaurante_la_cabana": {
            "nombre": "Restaurante La Cabaña",
            "categoria_icp": "cafeteria_especialidad",
            "prioridad_icp": "ALTA",
            "anillo": 0,
            "estado": "enriquecido",
            "contacto": {"telefono": "+34968000000"},
            "metadatos_fuente": {"rating": 4.3, "ratings_count": 1090},
        }
    }
    p = _knowledge_con_leads(tmp_path, leads)
    res = migrar(knowledge_path=p, hacer_backup=False)
    assert res.leads_total == 1
    assert res.leads_migrados == 1
    assert res.leads_con_error == 0
    # Re-cargar y verificar
    raw = json.loads(p.read_text(encoding="utf-8"))
    lead = raw["laboratorio"][TIPO_LEAD]["restaurante_la_cabana"]
    # Defaults nuevos rellenados
    assert lead["_schema_version"] == SCHEMA_VERSION
    assert lead["do_not_call"] is False
    assert lead["interacciones"] == []
    assert lead["compromisos"] == []
    assert lead["memoria_conversacional"] == ""
    assert lead["reintentos"]["intentos_realizados"] == 0
    # Estado pipeline derivado del legacy
    assert lead["estado"] == "enriquecido"      # legacy preservado
    assert lead["estado_pipeline"] == "cold"     # derivado
    # Legacy preservado
    assert lead["metadatos_fuente"]["rating"] == 4.3


# ── Idempotencia ────────────────────────────────────────────────────────────
def test_migrar_dos_veces_es_idempotente(tmp_path):
    leads = {
        "lead_legacy": {
            "id": "lead_legacy", "company": "laboratorio",
            "nombre": "Legacy", "estado": "enriquecido",
        },
    }
    p = _knowledge_con_leads(tmp_path, leads)
    res1 = migrar(knowledge_path=p, hacer_backup=False)
    raw1 = json.loads(p.read_text(encoding="utf-8"))
    res2 = migrar(knowledge_path=p, hacer_backup=False)
    raw2 = json.loads(p.read_text(encoding="utf-8"))
    # Misma estructura tras 2ª migración (sin re-cambiar nada)
    assert raw1 == raw2
    # La 2ª vez los leads cuentan como "ya_al_dia"
    assert res2.leads_total == 1
    assert res2.leads_ya_al_dia == 1
    assert res2.leads_migrados == 0


# ── Backup ──────────────────────────────────────────────────────────────────
def test_backup_se_crea_antes_de_escribir(tmp_path):
    leads = {"x": {"id": "x", "company": "laboratorio", "estado": "enriquecido"}}
    p = _knowledge_con_leads(tmp_path, leads)
    res = migrar(knowledge_path=p, hacer_backup=True)
    assert res.backup_path is not None
    assert res.backup_path.exists()
    # El backup tiene el contenido original (sin _schema_version aún)
    bak = json.loads(res.backup_path.read_text(encoding="utf-8"))
    lead_bak = bak["laboratorio"][TIPO_LEAD]["x"]
    assert "_schema_version" not in lead_bak


def test_dry_run_no_escribe_ni_hace_backup(tmp_path):
    leads = {"x": {"id": "x", "company": "laboratorio", "estado": "enriquecido"}}
    p = _knowledge_con_leads(tmp_path, leads)
    md5_antes = p.read_bytes()
    res = migrar(knowledge_path=p, hacer_backup=True, dry_run=True)
    md5_despues = p.read_bytes()
    assert md5_antes == md5_despues
    assert res.backup_path is None
    # Pero el dry_run sí cuenta lo que migraría
    assert res.leads_total == 1
    assert res.leads_migrados == 1


# ── No destructiva: campos extras se preservan ──────────────────────────────
def test_no_destructiva_preserva_campos_extra(tmp_path):
    leads = {
        "x": {
            "id": "x", "company": "laboratorio", "estado": "enriquecido",
            "campo_libre_inventado": {"clave": "valor"},
            "lista_libre": [1, 2, 3],
            "fuentes": [{"nombre": "google_places", "id_externo": "ChIJxx"}],
            "checklists": {"enrichment": {"ok": True}},
        }
    }
    p = _knowledge_con_leads(tmp_path, leads)
    migrar(knowledge_path=p, hacer_backup=False)
    raw = json.loads(p.read_text(encoding="utf-8"))
    lead = raw["laboratorio"][TIPO_LEAD]["x"]
    assert lead["campo_libre_inventado"] == {"clave": "valor"}
    assert lead["lista_libre"] == [1, 2, 3]
    assert lead["fuentes"][0]["id_externo"] == "ChIJxx"
    assert lead["checklists"]["enrichment"]["ok"] is True


# ── Lead corrupto NO bloquea la migración del resto ─────────────────────────
def test_lead_corrupto_se_aisla(tmp_path):
    leads = {
        "ok1": {"id": "ok1", "company": "laboratorio", "estado": "enriquecido"},
        "roto": "esto-no-es-un-dict",                          # un string sin sentido
        "ok2": {"id": "ok2", "company": "laboratorio", "estado": "enriquecido"},
    }
    p = _knowledge_con_leads(tmp_path, leads)
    res = migrar(knowledge_path=p, hacer_backup=False)
    assert res.leads_total == 3
    assert res.leads_con_error == 1
    # Los OK se migraron
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["laboratorio"][TIPO_LEAD]["ok1"]["_schema_version"] == SCHEMA_VERSION
    assert raw["laboratorio"][TIPO_LEAD]["ok2"]["_schema_version"] == SCHEMA_VERSION
    # El roto se quedó como estaba (no destructiva)
    assert raw["laboratorio"][TIPO_LEAD]["roto"] == "esto-no-es-un-dict"


# ── No toca otros tipos del knowledge ───────────────────────────────────────
def test_no_modifica_otros_tipos(tmp_path):
    raw_inicial = {
        "laboratorio": {
            "lead": {"x": {"id": "x", "company": "laboratorio", "estado": "enriquecido"}},
            "llamada": {"CA1": {"id": "CA1", "estado": "completada"}},
            "email_pendiente_aprobacion": {"p1": {"id": "p1", "estado": "aprobado"}},
        }
    }
    p = tmp_path / "knowledge.json"
    p.write_text(json.dumps(raw_inicial, indent=2), encoding="utf-8")
    migrar(knowledge_path=p, hacer_backup=False)
    raw = json.loads(p.read_text(encoding="utf-8"))
    # Otros tipos intactos
    assert raw["laboratorio"]["llamada"]["CA1"]["estado"] == "completada"
    assert raw["laboratorio"]["email_pendiente_aprobacion"]["p1"]["estado"] == "aprobado"
