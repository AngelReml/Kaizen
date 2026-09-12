"""Tests de los rituales (daily + weekly) — generación de Markdown sobre estado real."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.cola_aprobacion import ColaAprobacion
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.rituales import daily_report, weekly_report


def _setup_pipeline(n_enriquecidos=10, n_compromiso=0, n_pendientes_cola=0, n_aprobados_cola=0):
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    for i in range(n_enriquecidos):
        store.crear(f"e{i}", {"nombre": f"E{i}"})
        store.transicionar(f"e{i}", EstadoLead.CUALIFICADO, razon="seed")
        store.transicionar(f"e{i}", EstadoLead.ENRIQUECIDO, razon="seed")
    for i in range(n_compromiso):
        store.crear(f"c{i}", {"nombre": f"C{i}"})
        for st in (EstadoLead.CUALIFICADO, EstadoLead.ENRIQUECIDO,
                   EstadoLead.EN_CONTACTO, EstadoLead.COMPROMISO_RECIPROCO):
            store.transicionar(f"c{i}", st, razon="seed")
    cola = ColaAprobacion(k, "laboratorio")
    for i in range(n_pendientes_cola):
        cola.encolar(lead_id=f"p{i}", canal="email", destino="x@y.com",
                     asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp")
    for i in range(n_aprobados_cola):
        p = cola.encolar(lead_id=f"ap{i}", canal="email", destino="x@y.com",
                         asunto="A", cuerpo="B", brand_review={}, campaign_id="cmp")
        cola.aprobar(p.id)
    return store, cola


def test_daily_report_genera_md_con_secciones():
    store, cola = _setup_pipeline(n_enriquecidos=5, n_pendientes_cola=2)
    with tempfile.TemporaryDirectory() as d:
        ruta = daily_report(lead_store=store, cola=cola, salida=Path(d) / "daily.md")
        md = ruta.read_text(encoding="utf-8")
    assert "Daily stand-up" in md
    assert "Estado del pipeline" in md
    assert "Atascos" in md
    # 5 leads enriquecidos deben aparecer en la tabla.
    assert "| enriquecido | 5 |" in md
    assert "Pendientes en cola de aprobación: 2" in md


def test_weekly_report_marca_gate_no_alcanzado_si_pocos_compromisos():
    store, cola = _setup_pipeline(n_enriquecidos=10, n_compromiso=2)
    with tempfile.TemporaryDirectory() as d:
        ruta = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "weekly.md")
        md = ruta.read_text(encoding="utf-8")
    assert "Reporte ejecutivo del viernes" in md
    assert "Embudo" in md
    assert "Gate semanal Fase 1" in md
    # 2 compromisos < gate 5 → debe marcar como no superado.
    assert "actual: **2**" in md
    assert "Por debajo del gate" in md or "Ningún compromiso" in md


def test_weekly_report_gate_cumplido_si_5_o_mas_compromisos():
    store, cola = _setup_pipeline(n_enriquecidos=20, n_compromiso=6)
    with tempfile.TemporaryDirectory() as d:
        ruta = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "weekly.md")
        md = ruta.read_text(encoding="utf-8")
    assert "Gate cumplido" in md


def test_weekly_report_5_secciones_v0_2():
    store, cola = _setup_pipeline(n_enriquecidos=5)
    with tempfile.TemporaryDirectory() as d:
        ruta = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "weekly.md")
        md = ruta.read_text(encoding="utf-8")
    for titulo in ("## 1. Resultados", "## 2. Embudo", "## 3. Desviaciones",
                   "## 4. Riesgos", "## 5. Próxima semana"):
        assert titulo in md
