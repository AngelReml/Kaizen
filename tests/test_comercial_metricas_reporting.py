"""Tests de métricas (verde/ámbar/rojo) y del reporte ejecutivo."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.enrichment import ResultadoEnrichment
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.metricas import calcular
from departments.comercial.reporting import generar_reporte
from departments.comercial.researcher import ResultadoPasada


def _seed(store, n_cualificados=0, n_enriquecidos=0, n_perdidos=0):
    for i in range(n_cualificados):
        store.crear(f"c{i}", {"nombre": f"C{i}"})
        store.transicionar(f"c{i}", EstadoLead.CUALIFICADO, razon="seed")
    for i in range(n_enriquecidos):
        store.crear(f"e{i}", {"nombre": f"E{i}"})
        store.transicionar(f"e{i}", EstadoLead.CUALIFICADO, razon="seed")
        store.transicionar(f"e{i}", EstadoLead.ENRIQUECIDO, razon="seed")
    for i in range(n_perdidos):
        store.crear(f"p{i}", {"nombre": f"P{i}"})
        store.transicionar(f"p{i}", EstadoLead.PERDIDO, razon="seed")


def test_metrica_pct_pasan_icp_verde_si_supera_60():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    res = ResultadoPasada(candidatos_unicos=100, descartes_icp=30, cualificados_nuevos=70)
    cuadro = calcular(store, ultima_pasada=res)
    m = cuadro.metrica("pct_pasan_icp")
    assert m.valor == 70.0
    assert m.banda == "VERDE"


def test_metrica_pct_pasan_icp_rojo_si_baja_de_40():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    res = ResultadoPasada(candidatos_unicos=100, descartes_icp=70)
    cuadro = calcular(store, ultima_pasada=res)
    assert cuadro.metrica("pct_pasan_icp").banda == "ROJO"


def test_metrica_contacto_verificado_verde_si_supera_85_pct():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed(store, n_cualificados=1, n_enriquecidos=9)
    cuadro = calcular(store, ultima_pasada=ResultadoPasada(candidatos_unicos=10, descartes_icp=0))
    m = cuadro.metrica("pct_contacto_verificado")
    assert m.valor == 90.0
    assert m.banda == "VERDE"


def test_gates_fase0_se_cumplen():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed(store, n_enriquecidos=100)
    res = ResultadoPasada(candidatos_unicos=200, descartes_icp=60)   # 30% descarte < 40%
    cuadro = calcular(store, ultima_pasada=res)
    g = cuadro.gates_fase0
    assert g["cualificados_100"]["ok"] is True
    assert g["descarte_icp_menos_40"]["ok"] is True
    assert g["contacto_verificado_85"]["ok"] is True
    assert g["__superados__"] is True


def test_gates_fase0_no_se_cumplen_si_pocos_leads():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed(store, n_enriquecidos=10)
    res = ResultadoPasada(candidatos_unicos=20, descartes_icp=8)
    cuadro = calcular(store, ultima_pasada=res)
    assert cuadro.gates_fase0["__superados__"] is False
    assert cuadro.gates_fase0["cualificados_100"]["ok"] is False


def test_reporte_genera_markdown_con_5_secciones():
    store = LeadStore(InMemoryKnowledge(), "laboratorio")
    _seed(store, n_enriquecidos=120)
    res = ResultadoPasada(candidatos_unicos=200, descartes_icp=50)
    cuadro = calcular(store, ultima_pasada=res)
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "reporte.md"
        ruta = generar_reporte(lead_store=store, cuadro=cuadro, salida=salida)
        contenido = ruta.read_text(encoding="utf-8")
    # Las 5 secciones del §7.4 deben estar.
    for titulo in ("## 1. Resultados", "## 2. Embudo", "## 3. Desviaciones",
                   "## 4. Riesgos", "## 5. Próxima semana"):
        assert titulo in contenido, f"Falta sección: {titulo}"
    assert "SUPERADA" in contenido
