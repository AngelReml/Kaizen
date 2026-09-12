# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del director de Legal (panel_mando/herramientas/
legal.py), que absorbe tambien Cumplimiento. Cada ToolSpec se prueba construyendo el
objeto real (LegalDepartment, CuboCumplimiento) con InMemoryKnowledge/Bitacora reales
e invocando fn/validar de verdad — nada de fakes. R-TENANT: tenant sintetico
'laboratorio', jamas un tenant real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.cumplimiento.cubo_serie_d import CuboCumplimiento
from panel_mando.herramientas import legal as M
from panel_mando.herramientas.base import ArgumentosInvalidos

TENANT = "laboratorio"


@pytest.fixture()
def k():
    return InMemoryKnowledge()


@pytest.fixture()
def b(k):
    return Bitacora(k, TENANT, fecha_alta="2026-07-10")


# ── contrato: nombre coincide, clase valida ──────────────────────────────

def test_registro_interno_bien_formado():
    for nombre, spec in M.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert callable(spec.fn)


def test_ninguna_irreversible_externa_registrada():
    assert not [s for s in M.HERRAMIENTAS.values() if s.clase == "IRREVERSIBLE-EXTERNA"]


def test_nunca_wireadas_ausentes():
    """auditar/aportar_evidencia no estan en el mapa auditado; qa./rrhh. no son de
    este cubo — ninguna debe colarse en el registro de legal."""
    for prohibida in ("auditar", "aportar_evidencia", "validar_borrador",
                      "detectar_contradicciones", "mapa_capacidades", "roles_comite",
                      "rendimiento", "propuestas"):
        assert prohibida not in M.HERRAMIENTAS


# ── LECTURA: legal ────────────────────────────────────────────────────────

def test_handle_analiza_contrato_con_riesgo(k):
    spec = M.HERRAMIENTAS["handle"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"contrato": "El proveedor asume responsabilidad ilimitada."}))
    assert r["ok"] is False           # hay riesgo alto => TaskResult(ok=False, ...)
    assert r["data"]["riesgos"]


def test_handle_sin_insumo_pide_texto(k):
    spec = M.HERRAMIENTAS["handle"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))
    assert r["ok"] is False
    assert "texto" in r["summary"].lower() or "pásame" in r["summary"].lower() \
        or "pasame" in r["summary"].lower()


def test_consultar_clausula_problematica():
    spec = M.HERRAMIENTAS["consultar_clausula_problematica"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"texto": "Se pacta exclusividad indefinida con el distribuidor."}))
    assert r["es_problematica"] is True and r["gravedad"] == "alta"
    r2 = spec.fn(k=None, tenant=TENANT, bitacora=None,
                **spec.validar({"texto": "El precio es 100 euros."}))
    assert r2["es_problematica"] is False


def test_analizar_contrato():
    spec = M.HERRAMIENTAS["analizar_contrato"]
    contrato = ("Primera. El precio es 1000 euros.\n"
                "Segunda. El proveedor asume responsabilidad ilimitada.\n"
                "Tercera. Renovacion automatica anual.\n")
    r = spec.fn(k=None, tenant=TENANT, bitacora=None, **spec.validar({"texto": contrato}))
    assert len(r["clausulas"]) == 3
    assert len(r["riesgos"]) == 1
    assert len(r["puntos_atencion"]) == 1


def test_comparar_con_plantilla():
    spec = M.HERRAMIENTAS["comparar_con_plantilla"]
    r = spec.fn(k=None, tenant=TENANT, bitacora=None,
               **spec.validar({"contrato": "Objeto del contrato. Precio.",
                               "requeridos": "objeto, duracion, jurisdiccion"}))
    assert "duracion" in r["diferencias"] and r["coincide"] is False


# ── LECTURA: cumplimiento ────────────────────────────────────────────────

def test_listar_obligaciones_evidencias_auditorias_vacio(k):
    assert M.HERRAMIENTAS["listar_obligaciones"].fn(
        k=k, tenant=TENANT, bitacora=None, **M.HERRAMIENTAS["listar_obligaciones"].validar({})
    ) == {"obligaciones": {}}
    assert M.HERRAMIENTAS["listar_evidencias"].fn(
        k=k, tenant=TENANT, bitacora=None, **M.HERRAMIENTAS["listar_evidencias"].validar({})
    ) == {"evidencias": {}}
    assert M.HERRAMIENTAS["listar_auditorias"].fn(
        k=k, tenant=TENANT, bitacora=None, **M.HERRAMIENTAS["listar_auditorias"].validar({})
    ) == {"auditorias": {}}


def test_listar_obligaciones_tras_registrar(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    c.registrar(nombre="obl 1", tipo="INTERNA", fecha_limite="2026-08-01", area="ops")
    r = M.HERRAMIENTAS["listar_obligaciones"].fn(k=k, tenant=TENANT, bitacora=b,
                                                  **M.HERRAMIENTAS["listar_obligaciones"].validar({}))
    assert len(r["obligaciones"]) == 1


def test_verificar_evidencia_integra_y_corrupta(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    o = c.registrar(nombre="acta", tipo="INTERNA", fecha_limite="2026-08-01", area="direccion")
    ev = c.aportar_evidencia(o["id"], nombre_fichero="acta.pdf",
                             contenido=b"contenido original", firmante="operador")
    spec = M.HERRAMIENTAS["verificar_evidencia"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"ev_id": ev["id"], "contenido_actual_texto": "contenido original"}))
    assert r["integra"] is True
    r2 = spec.fn(k=k, tenant=TENANT, bitacora=b,
                **spec.validar({"ev_id": ev["id"], "contenido_actual_texto": "EDITADO"}))
    assert r2["integra"] is False and "CORRUPTA" in r2["veredicto"]


def test_verificar_evidencia_inexistente_sube_valueerror(k):
    spec = M.HERRAMIENTAS["verificar_evidencia"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"ev_id": "no-existe", "contenido_actual_texto": "x"}))


def test_validar_expediente_incompleto_y_completo(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    o = c.registrar(nombre="obl", tipo="INTERNA", fecha_limite="2026-08-01", area="ops")
    spec = M.HERRAMIENTAS["validar_expediente"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"ob_id": o["id"]}))
    assert r["veredicto"] == "INCOMPLETO"
    c.asignar(o["id"], "operador")
    c.aportar_evidencia(o["id"], nombre_fichero="e.pdf", contenido=b"ev")
    c.cumplir(o["id"], por="operador")
    r2 = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"ob_id": o["id"]}))
    assert r2["veredicto"] == "COMPLETO"


def test_validar_expediente_inexistente_sube_valueerror(k):
    spec = M.HERRAMIENTAS["validar_expediente"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({"ob_id": "no-existe"}))


def test_compilar_defensa(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    o = c.registrar(nombre="obl", tipo="INTERNA", fecha_limite="2026-08-01", area="x")
    c.asignar(o["id"], "operador")
    c.aportar_evidencia(o["id"], nombre_fichero="e1.pdf", contenido=b"uno")
    spec = M.HERRAMIENTAS["compilar_defensa"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({}))
    assert r["integro"] is True and len(r["piezas"]) == 1 and r["hash_manifest"]


def test_verificar_cadena_bitacora_integra(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    c.registrar(nombre="obl", tipo="INTERNA", fecha_limite="2026-08-01", area="x")
    spec = M.HERRAMIENTAS["verificar_cadena_bitacora"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({}))
    assert r["integra"] is True


def test_verificar_cadena_bitacora_sin_bitacora_sube_valueerror(k):
    spec = M.HERRAMIENTAS["verificar_cadena_bitacora"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({}))


# ── REVERSIBLE: cumplimiento ─────────────────────────────────────────────

def test_registrar_obligacion_interna(k, b):
    spec = M.HERRAMIENTAS["registrar_obligacion"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"nombre": "custodia contrato", "tipo": "CONTRACTUAL",
                               "fecha_limite": "2026-10-20", "area": "legal"}))
    assert r["estado"] == "REGISTRADA"
    assert k.get(TENANT, "obligacion", r["id"]) is not None


def test_registrar_obligacion_regulatoria_exige_gl05(k, b):
    spec = M.HERRAMIENTAS["registrar_obligacion"]
    with pytest.raises(ValueError, match="GL-05"):
        spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"nombre": "IVA trimestral", "tipo": "REGULATORIA",
                               "fecha_limite": "2026-10-20", "area": "finanzas"}))
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"nombre": "IVA trimestral", "tipo": "REGULATORIA",
                               "fecha_limite": "2026-10-20", "area": "finanzas",
                               "fuente_validada_por": "gestoria_sintetica"}))
    assert r["estado"] == "REGISTRADA"


def test_asignar_obligacion(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    o = c.registrar(nombre="obl", tipo="INTERNA", fecha_limite="2026-08-01", area="ops")
    spec = M.HERRAMIENTAS["asignar_obligacion"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b,
               **spec.validar({"ob_id": o["id"], "responsable": "operador"}))
    assert r["estado"] == "ASIGNADA" and r["responsable"] == "operador"


def test_asignar_obligacion_inexistente_sube_valueerror(k):
    spec = M.HERRAMIENTAS["asignar_obligacion"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=None,
               **spec.validar({"ob_id": "no-existe", "responsable": "operador"}))


# ── IRREVERSIBLE-INTERNA: cumplimiento ───────────────────────────────────

def test_cumplir_obligacion_exige_evidencia_y_usa_tenant_como_por(k, b):
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    o = c.registrar(nombre="obl", tipo="INTERNA", fecha_limite="2026-08-01", area="ops")
    spec = M.HERRAMIENTAS["cumplir_obligacion"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"ob_id": o["id"]}))
    c.aportar_evidencia(o["id"], nombre_fichero="e.pdf", contenido=b"ev")
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({"ob_id": o["id"]}))
    assert r["estado"] == "CUMPLIDA" and r["cumplida_por"] == TENANT


def test_cumplir_obligacion_no_expone_por_libre():
    """'por' NO esta declarado como argumento: si el LLM intenta colarlo, se rechaza
    antes de llegar a fn — siempre se usa el tenant autenticado real."""
    spec = M.HERRAMIENTAS["cumplir_obligacion"]
    with pytest.raises(ArgumentosInvalidos):
        spec.validar({"ob_id": "x", "por": "quien-sea"})


def test_cumplir_obligacion_inexistente_sube_valueerror(k):
    spec = M.HERRAMIENTAS["cumplir_obligacion"]
    with pytest.raises(ValueError):
        spec.fn(k=k, tenant=TENANT, bitacora=None, **spec.validar({"ob_id": "no-existe"}))


def test_barrer_plazos_alertas_y_timeout(k, b):
    from datetime import datetime, timedelta, timezone
    c = CuboCumplimiento(k, TENANT, bitacora=b)
    o = c.registrar(nombre="obl", tipo="INTERNA",
                    fecha_limite=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                    area="ops")
    spec = M.HERRAMIENTAS["barrer_plazos"]
    r = spec.fn(k=k, tenant=TENANT, bitacora=b, **spec.validar({}))
    assert {"obligacion": o["id"], "aviso": "INCUMPLIDA"} in r["avisos"]
    assert k.get(TENANT, "obligacion", o["id"])["estado"] == "INCUMPLIDA"


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
