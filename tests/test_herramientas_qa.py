# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del cubo QA: cada ToolSpec invoca el codigo
real de departments/qa/ (QADepartment, departments.qa.herramientas), no un
doble de prueba. R-TENANT: tenant sintetico 'laboratorio', jamas uno real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from panel_mando.herramientas import base as B
from panel_mando.herramientas import qa as QA

TENANT = "laboratorio"

BORRADOR_OK = ("Presentación de Repostería Laboratorio",
               "Buenos días, le escribo desde Repostería Laboratorio, obrador artesano de Cieza "
               "con más de un siglo de historia, por si encajamos como proveedor de su negocio. "
               "Quedo a su disposición. Un saludo, Iván Carbonell.")


@pytest.fixture()
def k():
    return InMemoryKnowledge()


def _invocar(nombre, argumentos, *, k):
    return B.invocar({"qa": QA.HERRAMIENTAS}, "qa", nombre, argumentos,
                     k=k, tenant=TENANT, bitacora=None)


# ── handle (QADepartment.handle real) ────────────────────────────────────

def test_handle_valida_borrador_ok(k):
    r = _invocar("handle", {"asunto": BORRADOR_OK[0], "cuerpo": BORRADOR_OK[1]}, k=k)
    assert r["ok"] is True
    assert r["data"]["ok"] is True


def test_handle_reporta_problemas_reales(k):
    r = _invocar("handle", {"asunto": "", "cuerpo": "corto [nombre]"}, k=k)
    assert r["ok"] is False
    assert r["data"]["problemas"]


def test_handle_payload_vacio_no_se_confunde_con_validacion_superada(k):
    """Con asunto/cuerpo en blanco (defaults de la herramienta), las reglas reales
    de QA fallan (correo_sin_asunto, cuerpo_demasiado_corto) -> ok=False explicito,
    nunca un OK vacio."""
    r = _invocar("handle", {}, k=k)
    assert r["ok"] is False
    assert r["data"]["problemas"]


def test_handle_rechaza_argumento_no_declarado(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("handle", {"asunto": "x", "cuerpo": "y", "intruso": "no"}, k=k)


# ── validar_borrador ──────────────────────────────────────────────────────

def test_validar_borrador_ok(k):
    r = _invocar("validar_borrador", {"asunto": BORRADOR_OK[0], "cuerpo": BORRADOR_OK[1]}, k=k)
    assert r["ok"] is True and r["problemas"] == []


def test_validar_borrador_con_problemas(k):
    r = _invocar("validar_borrador", {"asunto": "", "cuerpo": "corto [nombre]"}, k=k)
    assert r["ok"] is False and len(r["problemas"]) >= 2


def test_validar_borrador_detecta_contradiccion_via_contexto(k):
    r = _invocar("validar_borrador", {
        "asunto": "Presentación",
        "cuerpo": "Somos un fabricante industrial a gran escala, con mucha experiencia.",
        "contexto": "obrador artesano local",
    }, k=k)
    assert r["ok"] is False
    assert any("industrial" in p for p in r["problemas"])


def test_validar_borrador_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("validar_borrador", {"asunto": "x"}, k=k)


def test_validar_borrador_rechaza_argumento_no_declarado(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("validar_borrador", {"asunto": "x", "cuerpo": "y", "intruso": "no"}, k=k)


# ── detectar_contradicciones ─────────────────────────────────────────────

def test_detectar_contradicciones_real(k):
    r = _invocar("detectar_contradicciones", {
        "texto": "Producto industrial a gran escala",
        "contexto_empresa": "obrador artesano local",
    }, k=k)
    assert r["ok"] is False and r["contradicciones"]


def test_detectar_contradicciones_sin_choque(k):
    r = _invocar("detectar_contradicciones", {
        "texto": "Un saludo cordial",
        "contexto_empresa": "obrador artesano local",
    }, k=k)
    assert r["ok"] is True and r["contradicciones"] == []


def test_detectar_contradicciones_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("detectar_contradicciones", {"texto": "x"}, k=k)


# ── comparar_con_plantilla ────────────────────────────────────────────────

def test_comparar_con_plantilla_real(k):
    r = _invocar("comparar_con_plantilla", {
        "texto": "Buenos días. Un saludo.",
        "requeridos": "buenos días, firma",
    }, k=k)
    assert r["coincide_estructura"] is False and "firma" in r["diferencias"]


def test_comparar_con_plantilla_coincide(k):
    r = _invocar("comparar_con_plantilla", {
        "texto": "Buenos días. Firma: Iván.",
        "requeridos": "buenos días, firma",
    }, k=k)
    assert r["coincide_estructura"] is True and r["diferencias"] == []


def test_comparar_con_plantilla_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("comparar_con_plantilla", {"texto": "x"}, k=k)


# ── calificar_calidad (pipeline REAL de especialistas, pase de excelencia) ─

def test_calificar_calidad_puntua_0_10(k):
    r = _invocar("calificar_calidad", {"texto": "Un saludo cordial."}, k=k)
    assert r["ok"] is True
    assert 0 <= r["data"]["puntuacion"] <= 10
    assert "desglose" in r["data"] and "recomendaciones" in r["data"]


def test_calificar_calidad_sin_problemas_puntua_diez(k):
    r = _invocar("calificar_calidad", {"texto": "Un saludo cordial."}, k=k)
    assert r["data"]["puntuacion"] == 10


def test_calificar_calidad_detecta_contradiccion(k, monkeypatch):
    """Igual que en tests/test_qa.py: el tenant 'laboratorio' ya tiene
    contexto real en disco que no contiene los rasgos de
    PARES_CONTRADICTORIOS, asi que se vacia con monkeypatch para probar el
    fallback a 'contexto_empresa' que pasa esta herramienta."""
    import diario_ops
    monkeypatch.setattr(diario_ops, "read", lambda *a, **kw: "")
    r = _invocar("calificar_calidad", {
        "texto": "Somos un fabricante industrial a gran escala.",
        "contexto_empresa": "obrador artesano local",
    }, k=k)
    assert r["data"]["contradicciones"]
    assert r["data"]["puntuacion"] < 10


def test_calificar_calidad_secciones_requeridas_ausentes_corta_el_pipeline(k):
    """Igual que en departments/qa: si faltan secciones requeridas,
    ValidadorDeEstructura corta la cadena antes de puntuar (comportamiento
    real del PipelineDepartamento compartido, no un bug de esta tool)."""
    r = _invocar("calificar_calidad", {
        "texto": "Buenos días. Un saludo.",
        "secciones_requeridas": "buenos días,firma",
    }, k=k)
    assert r["ok"] is False
    assert "firma" in r["data"]["secciones_faltantes"]


def test_calificar_calidad_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("calificar_calidad", {}, k=k)


def test_calificar_calidad_rechaza_argumento_no_declarado(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("calificar_calidad", {"texto": "x", "intruso": "no"}, k=k)


def test_calificar_calidad_no_afecta_handle_legacy(k):
    """La activacion del pipeline no debe filtrarse a 'handle': con
    asunto/cuerpo (sin 'artefacto'), 'handle' sigue siendo las reglas duras
    de siempre."""
    r = _invocar("handle", {"asunto": BORRADOR_OK[0], "cuerpo": BORRADOR_OK[1]}, k=k)
    assert r["ok"] is True
    assert r["data"]["ok"] is True
    assert "puntuacion" not in r["data"]


# ── historial_validaciones (dato ya persistido, pase de excelencia) ────────

def test_historial_validaciones_vacio_sin_validaciones(k):
    r = _invocar("historial_validaciones", {}, k=k)
    assert r == {"total": 0, "aceptados": 0, "rechazados": 0, "detalle": []}


def test_historial_validaciones_cuenta_aceptados_y_rechazados_reales(k):
    """Siembra el knowledge store exactamente como lo hace
    core/subscriptors/qa_validador.py (tipo de nodo 'validacion', mismos
    campos) — dato REAL ya existente, no un contador inventado aqui."""
    k.add(TENANT, "validacion", "ev-1", {"target": "ev-1", "ok": True, "problemas": [],
                                         "ts": "2026-01-01T00:00:00Z"})
    k.add(TENANT, "validacion", "ev-2", {"target": "ev-2", "ok": False,
                                         "problemas": ["cuerpo demasiado corto"],
                                         "ts": "2026-01-01T00:01:00Z"})
    k.add(TENANT, "validacion", "ev-3", {"target": "ev-3", "ok": False,
                                         "problemas": ["asunto vacío"],
                                         "ts": "2026-01-01T00:02:00Z"})
    r = _invocar("historial_validaciones", {}, k=k)
    assert r["total"] == 3
    assert r["aceptados"] == 1
    assert r["rechazados"] == 2
    assert len(r["detalle"]) == 3


def test_historial_validaciones_via_qa_validador_real(k):
    """Extremo a extremo: dispara el subscriptor real (no siembra a mano) y
    comprueba que la herramienta lee lo que este persistio de verdad."""
    from core.bus import InMemoryBus
    from core.events import Event, EventType
    from core.subscriptors.qa_validador import QAValidador
    bus = InMemoryBus()
    QAValidador(bus, k)
    bus.publish(Event(EventType.DEPT_TASK_COMPLETED, source="redaccion",
                      payload={"lead": "x", "asunto": "", "cuerpo": "corto"},
                      company=TENANT))
    r = _invocar("historial_validaciones", {}, k=k)
    assert r["total"] == 1
    assert r["rechazados"] == 1


def test_historial_validaciones_rechaza_argumento_no_declarado(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("historial_validaciones", {"intruso": "no"}, k=k)


# ── aislamiento de cubo (sanity contra el registro real de este cubo) ────

def test_todas_las_specs_son_lectura_y_declaran_su_propio_nombre(k):
    for nombre, spec in QA.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase == "LECTURA"


def test_qa_no_ve_herramientas_de_otro_cubo(k):
    with pytest.raises(B.NoExisteHerramienta):
        _invocar("crear_campana", {}, k=k)
