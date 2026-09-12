# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del director de RRHH (panel_mando/herramientas/
rrhh.py). RRHH esta pospuesto (manifest): SOLO LECTURA, ninguna escritura de
negocio. Cada ToolSpec se prueba construyendo el objeto real (RRHHDepartment)
e invocando fn/validar de verdad — nada de fakes. R-TENANT: tenant sintetico
'laboratorio', jamas un tenant real."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from cubos.base import manifiestos_instalados
from panel_mando.herramientas import rrhh as M
from panel_mando.herramientas.base import ArgumentosInvalidos

TENANT = "laboratorio"
CATALOGO_REAL = sorted(manifiestos_instalados())   # los 10 cubos reales en disco


@pytest.fixture()
def k():
    return InMemoryKnowledge()


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Aisla la BD del sustrato (colmena_agentes) por test — mismo patron que
    tests/test_colmena_herramientas.py::entorno."""
    ruta = tmp_path / "kaizen.db"
    monkeypatch.setenv("KAIZEN_DB_PATH", str(ruta))
    return ruta


def _dar_de_alta(db_path: Path, tenant: str, cubo: str) -> None:
    """Siembra un alta REAL en colmena_agentes (mismo esquema que
    panel_mando/colmena.py — ver panel_mando/herramientas/rrhh.py::_DDL_COLMENA_AGENTES),
    sin pasar por el endpoint HTTP de colmena.py (fuera de ambito de este grupo)."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(M._DDL_COLMENA_AGENTES)
        conn.execute(
            "INSERT INTO colmena_agentes (empresa, cubo, role_id, uid, ts_alta) "
            "VALUES (?, ?, ?, ?, ?)",
            (tenant, cubo, f"director_{cubo}", f"KZ-{cubo.upper()}-TEST",
             "2026-01-01T00:00:00Z"))
        conn.commit()
    finally:
        conn.close()


# ── contrato: nombre coincide, clase valida, TODO es LECTURA ────────────────

def test_registro_interno_bien_formado():
    for nombre, spec in M.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert callable(spec.fn)


def test_todo_es_lectura_rrhh_pospuesto():
    """RRHH esta pospuesto: solo lectura/consulta, ninguna escritura de negocio,
    ni siquiera REVERSIBLE."""
    for spec in M.HERRAMIENTAS.values():
        assert spec.clase == "LECTURA"


def test_nunca_wireadas_ausentes():
    """Las entradas de legal./qa. del mapa mezclado no son de este cubo — no deben
    colarse en el registro de rrhh."""
    for prohibida in ("consultar_clausula_problematica", "analizar_contrato",
                      "comparar_con_plantilla", "validar_borrador",
                      "detectar_contradicciones"):
        assert prohibida not in M.HERRAMIENTAS


# ── LECTURA: RRHHDepartment.handle ───────────────────────────────────────

def test_handle_estado_general_por_defecto(k):
    spec = M.HERRAMIENTAS["handle"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["ok"] is True
    assert "RRHH operativo" in r["summary"]
    assert r["data"]["activos"] == []


def test_handle_mapa_de_capacidades(k):
    spec = M.HERRAMIENTAS["handle"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"intent": "dame el mapa de capacidades"}))
    assert r["ok"] is True
    assert "Cobertura" in r["summary"]
    assert r["data"]["mapa"]["presentes"] == ["rrhh"]
    assert "rrhh" not in r["data"]["mapa"]["faltantes"]


def test_handle_rendimiento(k):
    spec = M.HERRAMIENTAS["handle"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"intent": "como va el rendimiento"}))
    assert r["ok"] is True
    assert r["data"]["alertas"] == []


def test_handle_propuestas(k):
    spec = M.HERRAMIENTAS["handle"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"intent": "dame propuestas de mejora"}))
    assert r["ok"] is True
    assert len(r["data"]["propuestas"]) == 1
    assert "comercial" in r["data"]["propuestas"][0]


# ── LECTURA: mapa / rendimiento / propuestas directos ───────────────────────
#
# Estos tres tests probaban EXACTAMENTE el bug de la auditoria (presentes ==
# ["rrhh"] siempre, alertas == [] siempre, la misma propuesta siempre) porque
# la implementacion vieja reconstruia un RRHHDepartment sobre un bus
# desechable en cada llamada. R6: se actualizan para verificar el
# comportamiento honesto nuevo (datos reales y persistentes via
# cubos.base.manifiestos_instalados() + la tabla colmena_agentes).

def test_mapa_directo_catalogo_es_el_real_instalado(k, db):
    """Sin ningun alta: catalogo = los 10 cubos reales en disco, cero presentes,
    cobertura 0.0 — nada de '["rrhh"]' inventado desde un bus vacio."""
    spec = M.HERRAMIENTAS["mapa"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["catalogo"] == CATALOGO_REAL
    assert r["presentes"] == []
    assert r["faltantes"] == CATALOGO_REAL
    assert r["fuera_de_catalogo"] == []
    assert r["cobertura"] == 0.0


def test_mapa_directo_presentes_refleja_altas_reales(k, db):
    """Dar de alta 'qa' y 'rrhh' de verdad (colmena_agentes) SI cambia la
    cobertura calculada — la prueba de que ya no es un numero fijo."""
    _dar_de_alta(db, TENANT, "qa")
    _dar_de_alta(db, TENANT, "rrhh")
    spec = M.HERRAMIENTAS["mapa"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["presentes"] == ["qa", "rrhh"]
    assert "qa" not in r["faltantes"] and "rrhh" not in r["faltantes"]
    assert r["cobertura"] == round(2 / len(CATALOGO_REAL), 3)


def test_mapa_directo_altas_de_otro_tenant_no_cuentan(k, db):
    """R-TENANT: un alta sembrada para otra empresa no debe filtrarse a
    'laboratorio' — aislamiento real por tenant, no solo documentado."""
    _dar_de_alta(db, "otra_empresa_sintetica", "qa")
    spec = M.HERRAMIENTAS["mapa"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["presentes"] == []
    assert r["cobertura"] == 0.0


def test_mapa_directo_alta_fuera_del_catalogo_real(k, db):
    """Un cubo dado de alta que no tiene manifest instalado en disco (p. ej.
    un residuo o un alias) aparece en fuera_de_catalogo, no infla cobertura."""
    _dar_de_alta(db, TENANT, "cubo_legado_sin_manifest")
    spec = M.HERRAMIENTAS["mapa"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["fuera_de_catalogo"] == ["cubo_legado_sin_manifest"]
    assert r["presentes"] == []
    assert r["cobertura"] == 0.0


def test_rendimiento_directo_es_honesto_sobre_falta_de_datos(k, db):
    """Ya no finge 'sin alertas' como si hubiera comprobado: declara
    explicitamente que no hay fuente persistente fuera del proceso vivo."""
    spec = M.HERRAMIENTAS["rendimiento"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["alertas"] == []
    assert r["datos_disponibles"] is False
    assert r["motivo"]   # motivo no vacio, explica el porque


def test_propuestas_directo_sugiere_el_cubo_realmente_faltante(k, db):
    """Con 9 de los 10 cubos reales dados de alta, la propuesta debe nombrar
    EXACTAMENTE el que falta de verdad — no 'comercial' porque sea el primero
    de un catalogo fijo."""
    presentes = [c for c in CATALOGO_REAL if c != "qa"]
    for cubo in presentes:
        _dar_de_alta(db, TENANT, cubo)
    spec = M.HERRAMIENTAS["propuestas"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert any("qa" in p for p in r["propuestas"])
    assert not any("comercial" in p and "qa" not in p for p in r["propuestas"])


def test_propuestas_directo_catalogo_completo_no_sugiere_activar_nada(k, db):
    for cubo in CATALOGO_REAL:
        _dar_de_alta(db, TENANT, cubo)
    spec = M.HERRAMIENTAS["propuestas"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert not any("Dar de alta" in p for p in r["propuestas"])


def test_propuestas_directo_no_inventa_alertas_de_rendimiento(k, db):
    """Coherente con 'rendimiento': si no hay datos persistentes, las
    propuestas tampoco pueden fingir que los revisaron."""
    spec = M.HERRAMIENTAS["propuestas"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert any("rendimiento" in p for p in r["propuestas"])


# ── LECTURA: mapa_capacidades (funcion determinista, activos libre) ────────

def test_mapa_capacidades_con_activos_del_llamador(k):
    spec = M.HERRAMIENTAS["mapa_capacidades"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"activos": "comercial, brand, rrhh"}))
    assert r["presentes"] == ["brand", "comercial", "rrhh"]
    assert "marketing" in r["faltantes"]
    assert r["fuera_de_catalogo"] == []
    assert r["cobertura"] == round(3 / 10, 3)


def test_mapa_capacidades_cubo_fuera_de_catalogo(k):
    spec = M.HERRAMIENTAS["mapa_capacidades"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"activos": "comercial,cubo_inventado"}))
    assert r["presentes"] == ["comercial"]
    assert r["fuera_de_catalogo"] == ["cubo_inventado"]


def test_mapa_capacidades_vacio(k):
    spec = M.HERRAMIENTAS["mapa_capacidades"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({"activos": ""}))
    assert r["presentes"] == []
    assert r["cobertura"] == 0.0


# ── LECTURA: roles_comite (sin argumentos) ──────────────────────────────────

def test_roles_comite(k):
    spec = M.HERRAMIENTAS["roles_comite"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["roles_negocio"] > 0
    assert isinstance(r["transversales"], list)
    assert r["dominios"] == ["legal", "finanzas", "brand", "comercial", "operaciones"]


# ── validacion de argumentos: rechazo honesto, no coercion silenciosa ──────

@pytest.mark.parametrize("nombre_herramienta", list(M.HERRAMIENTAS))
def test_argumento_desconocido_rechazado_en_todas(nombre_herramienta):
    spec = M.HERRAMIENTAS[nombre_herramienta]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"intruso_no_declarado": "x"})


@pytest.mark.parametrize("nombre_herramienta", [n for n, s in M.HERRAMIENTAS.items()
                                                if any(a.obligatorio for a in s.argumentos)])
def test_argumento_obligatorio_ausente_rechazado(nombre_herramienta):
    spec = M.HERRAMIENTAS[nombre_herramienta]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({})


def test_intent_es_opcional_en_handle():
    spec = M.HERRAMIENTAS["handle"]
    limpio = spec.validar({})
    assert "intent" not in limpio
