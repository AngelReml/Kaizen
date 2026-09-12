"""Tests del reporte del viernes — sección 'Calidad de llamadas' (R4)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone

from core.knowledge import InMemoryKnowledge
from departments.comercial.cola_aprobacion import ColaAprobacion
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.rituales import weekly_report


def _ts(delta_dias=0):
    return (datetime.now(timezone.utc) - timedelta(days=delta_dias)).isoformat()


def _sembrar(n_llamadas_semana=3, n_compromiso=1, n_tono_ok=2, n_no_conforme=0,
              puntuacion_baja=False):
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    cola = ColaAprobacion(k, "laboratorio")
    store.crear("lead_x", {"nombre": "Test"})
    for st in (EstadoLead.CUALIFICADO, EstadoLead.ENRIQUECIDO):
        store.transicionar("lead_x", st, razon="seed")
    for i in range(n_llamadas_semana):
        call_sid = f"CA_test_{i}"
        # llamada de esta semana
        k.add("laboratorio", "llamada", call_sid, {
            "id": call_sid, "lead_id": "lead_x", "estado": "completada" if i >= n_no_conforme else "no_conforme",
            "inicio_ts": _ts(delta_dias=2),
            "duracion_s": 120 + i * 10,
            "transcript": [{"hablante":"agente","ts":0,"texto":"hola"},
                           {"hablante":"cliente","ts":3,"texto":"buenas"}],
        })
        # analisis
        k.add("laboratorio", "analisis_llamada", f"an_{i}", {
            "id": f"an_{i}", "call_sid": call_sid, "lead_id": "lead_x",
            "compromiso": {"es_compromiso": i < n_compromiso, "confianza": 0.8,
                           "senales_detectadas": [], "motivo": "", "recomendacion": ""},
            "tono": {"ok": i < n_tono_ok, "problemas": [] if i < n_tono_ok else ["IA"],
                     "sugerencias": ["dar más pausas"], "dictamen_llm": ""},
            "objeciones": [] if i < n_compromiso else [
                {"frase_cliente": "tengo proveedor", "abordada": False,
                 "motivo": "no respondió", "sugerencia": "ofrecer comparativa"}
            ],
            "mejoras": ["preguntar más por el negocio"],
            "puntuacion_global": 3 if puntuacion_baja else 8,
            "duracion_s": 120, "turnos_agente": 2, "turnos_cliente": 2,
        })
    return store, cola


def test_reporte_incluye_seccion_calidad_llamadas():
    store, cola = _sembrar()
    with tempfile.TemporaryDirectory() as d:
        ruta = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "w.md")
        md = ruta.read_text(encoding="utf-8")
    assert "## 6. Calidad de llamadas" in md
    assert "Llamadas totales" in md
    assert "Compromisos Recíprocos detectados" in md
    assert "Tono de marca OK" in md
    assert "Puntuación media" in md


def test_reporte_lista_objeciones_no_abordadas():
    store, cola = _sembrar(n_llamadas_semana=3, n_compromiso=0)  # ninguna en compromiso → todas tienen objeción
    with tempfile.TemporaryDirectory() as d:
        ruta = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "w.md")
        md = ruta.read_text(encoding="utf-8")
    assert "Objeciones no abordadas más frecuentes" in md
    assert "tengo proveedor" in md


def test_reporte_lista_sugerencias_de_mejora():
    store, cola = _sembrar()
    with tempfile.TemporaryDirectory() as d:
        md = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "w.md").read_text(encoding="utf-8")
    assert "Sugerencias de mejora más repetidas" in md
    assert "preguntar más por el negocio" in md


def test_reporte_marca_llamadas_de_baja_puntuacion():
    store, cola = _sembrar(n_llamadas_semana=2, puntuacion_baja=True)
    with tempfile.TemporaryDirectory() as d:
        md = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "w.md").read_text(encoding="utf-8")
    assert "Llamadas con puntuación <5" in md
    assert "CA_test_0" in md or "CA_test_1" in md


def test_reporte_sin_llamadas_muestra_nota():
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    cola = ColaAprobacion(k, "laboratorio")
    with tempfile.TemporaryDirectory() as d:
        md = weekly_report(lead_store=store, cola=cola, salida=Path(d) / "w.md").read_text(encoding="utf-8")
    assert "## 6. Calidad de llamadas" in md
    assert "Sin llamadas registradas" in md
