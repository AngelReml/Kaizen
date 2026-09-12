"""Tests del departamento Legal (Fase 5.3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.guardian import Guardian, Action, Decision
from departments.legal import reglas, herramientas as h
from departments.legal.agente import LegalDepartment


# ── reglas ──────────────────────────────────────────────────────────────────
def test_contrato_supera_tope():
    assert reglas.contrato_supera_tope(15000)[0] is False
    assert reglas.contrato_supera_tope(5000)[0] is True


def test_responsabilidad_ilimitada():
    assert reglas.responsabilidad_ilimitada("El proveedor asume responsabilidad ilimitada.")[0] is False
    assert reglas.responsabilidad_ilimitada("Responsabilidad limitada al importe del contrato.")[0] is True


def test_no_competencia_larga():
    assert reglas.no_competencia_larga(36)[0] is False
    assert reglas.no_competencia_larga(12)[0] is True


# ── herramientas ────────────────────────────────────────────────────────────
def test_consultar_clausula_problematica():
    r = h.consultar_clausula_problematica("Se pacta exclusividad indefinida con el distribuidor.")
    assert r["es_problematica"] is True and r["gravedad"] == "alta"
    assert h.consultar_clausula_problematica("El precio es 100€.")["es_problematica"] is False


def test_analizar_contrato():
    contrato = ("Primera. El precio es 1000€.\n"
                "Segunda. El proveedor asume responsabilidad ilimitada.\n"
                "Tercera. Renovacion automatica anual.\n")
    an = h.analizar_contrato(contrato)
    assert len(an["clausulas"]) == 3
    assert len(an["riesgos"]) == 1            # responsabilidad ilimitada (alta)
    assert len(an["puntos_atencion"]) == 1    # renovacion automatica (media)


def test_comparar_con_plantilla():
    r = h.comparar_con_plantilla("Objeto del contrato. Precio.", ["objeto", "duracion", "jurisdiccion"])
    assert "duracion" in r["diferencias"] and r["coincide"] is False


# ── reglas en el Guardián ────────────────────────────────────────────────────
def test_guardian_bloquea_responsabilidad_ilimitada():
    g = Guardian(reglas_extra=[reglas.como_regla_guardian])
    v = g.evaluate(Action("revisar_clausula", payload={"clausula_texto": "responsabilidad ilimitada del proveedor"}))
    assert v.decision is Decision.BLOCKED


def test_guardian_escala_contrato_caro():
    g = Guardian(reglas_extra=[reglas.como_regla_guardian])
    v = g.evaluate(Action("firmar_contrato", payload={"contrato_importe_eur": 50000}))
    assert v.decision is Decision.ESCALATED


# ── agente ──────────────────────────────────────────────────────────────────
def test_agente_analiza_contrato():
    from departments.base import Task
    d = LegalDepartment(InMemoryBus())
    res = d.handle(Task(intent="analiza", payload={"contrato": "El proveedor asume responsabilidad ilimitada."}))
    assert res.data["riesgos"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1; print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
