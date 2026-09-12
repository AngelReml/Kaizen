"""Tests del argumentario por empresa (`empresas/<company>/argumentario.json`)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.argumentario import (
    argumentos_funcionan,
    cargar_argumentario,
    competidores,
    distribuidores_logistica,
    patrones_argumentos_prohibidos,
    precios_competencia,
    segmentos_diana,
)


# ─── Carga del argumentario del tenant SINTÉTICO ─────────────────────────────
#
# R-TENANT: estos tests apuntaban al argumentario de un cliente real y afirmaban
# hechos suyos (sus competidores, sus distribuidores, sus precios). Eso no probaba
# el producto: probaba la cartera. Ahora ejercitan el MISMO código contra el tenant
# sintético `laboratorio`, cuyo contenido emite el generador determinista.

TENANT = "laboratorio"


def test_cargar_argumentario_tiene_secciones_clave():
    arg = cargar_argumentario(TENANT)
    assert arg["empresa"] == TENANT
    assert "argumentos_funcionan" in arg
    assert "argumentos_prohibidos" in arg
    assert "segmentos_diana" in arg
    assert "competencia" in arg
    assert "precios_competencia_uso_interno" in arg
    assert "distribuidores_logistica_fase1" in arg


def test_cargar_argumentario_inexistente_devuelve_dict_vacio():
    assert cargar_argumentario("empresa_que_no_existe") == {}
    assert cargar_argumentario("") == {}


def test_argumentos_funcionan_ordenados_por_prioridad():
    """Lo que se prueba es el ORDEN que aplica el loader, no qué dice el argumento."""
    args = argumentos_funcionan(TENANT)
    prioridades = [a["prioridad"] for a in args]
    assert prioridades == sorted(prioridades)
    assert prioridades[0] == 1
    assert all(a.get("id") and a.get("texto") for a in args)


def test_patrones_argumentos_prohibidos_solo_substring():
    """Los argumentos `deteccion: semantica_llm` no aparecen en la lista de
    patrones — esos los gestiona el LLM, no la regla dura."""
    patrones = patrones_argumentos_prohibidos(TENANT)
    ids = {p["id"] for p in patrones}
    assert "superlativo_absoluto" in ids
    assert "promesa_de_resultado" in ids
    assert "comparacion_precio_competencia" not in ids        # semántico, fuera


def test_patrones_estan_en_minusculas():
    """BrandGuardian compara contra cuerpo.lower(); el loader debe garantizarlo."""
    for p in patrones_argumentos_prohibidos(TENANT):
        assert p["patron"] == p["patron"].lower()
        assert p["patron"].strip() == p["patron"]


def test_segmentos_diana_priorizados_y_completos():
    segs = segmentos_diana(TENANT)
    assert len(segs) == 4
    assert [s["prioridad"] for s in segs] == [1, 2, 3, 4]
    assert all(s.get("id") and s.get("nombre") and s.get("razon") for s in segs)


def test_competidores_tienen_la_forma_esperada():
    comps = competidores(TENANT)
    assert len(comps) == 4
    for c in comps:
        assert {"id", "nombre", "ubicacion", "rol", "fortaleza", "amenaza"} <= set(c)


def test_precios_competencia_marcados_como_uso_interno():
    """El aviso es la salvaguarda: estas cifras JAMÁS salen al transcript ni al
    email. Se comprueba el aviso y la forma, no el precio de nadie."""
    precios = precios_competencia(TENANT)
    aviso = precios.get("_aviso", "").upper()
    assert "USO INTERNO" in aviso
    assert "NUNCA" in aviso
    refs = precios.get("referencias", [])
    assert len(refs) >= 4
    for r in refs:
        assert {"id", "producto", "precio_eur", "iva_incluido", "nota"} <= set(r)
        assert isinstance(r["precio_eur"], (int, float))


def test_distribuidores_fase1_tienen_la_forma_esperada():
    dists = distribuidores_logistica(TENANT)
    assert len(dists) == 3
    for d in dists:
        assert {"id", "nombre", "ubicacion", "antiguedad_anos"} <= set(d)


# ─── Aislamiento por empresa con `base_dir` ──────────────────────────────────


def test_base_dir_aisla_busqueda(tmp_path):
    """`base_dir` permite cargar argumentarios alternativos en tests sin tocar
    el repo real."""
    (tmp_path / "empresas" / "test_co").mkdir(parents=True)
    payload = {
        "empresa": "test_co",
        "argumentos_funcionan": [{"prioridad": 1, "id": "x", "texto": "T"}],
    }
    (tmp_path / "empresas" / "test_co" / "argumentario.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    arg = cargar_argumentario("test_co", base_dir=tmp_path)
    assert arg["empresa"] == "test_co"
    assert argumentos_funcionan("test_co", base_dir=tmp_path)[0]["id"] == "x"
