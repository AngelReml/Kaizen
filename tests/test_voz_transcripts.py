"""Tests de persistencia de llamadas (transcripts.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.sdr.voz_conversacional import transcripts as t


def _k():
    return InMemoryKnowledge()


def test_crear_llamada_persiste_estado_inicial():
    k = _k()
    nodo = t.crear_llamada(k, "laboratorio",
                            call_sid="CA123", lead_id="lead_x", pendiente_id="pid1",
                            agente_config_version="v1", telefono_destino="+34600000000")
    assert nodo["estado"] == "iniciada"
    assert nodo["lead_id"] == "lead_x"
    assert nodo["telefono_destino"] == "+34600000000"
    assert nodo["agente_config_version"] == "v1"
    assert nodo["eventos_completados"] == []
    # Lo persistido coincide.
    assert t.get_llamada(k, "laboratorio", "CA123") == nodo


def test_actualizar_llamada_lanza_si_no_existe():
    k = _k()
    with pytest.raises(KeyError):
        t.actualizar_llamada(k, "laboratorio", "CA_inexistente", estado="completada")


def test_marcar_evento_completado_dedup():
    k = _k()
    t.crear_llamada(k, "laboratorio", call_sid="CA1", lead_id="l", pendiente_id="p",
                    agente_config_version="v1")
    t.marcar_evento_completado(k, "laboratorio", "CA1", "recording")
    t.marcar_evento_completado(k, "laboratorio", "CA1", "recording")     # duplicado
    t.marcar_evento_completado(k, "laboratorio", "CA1", "transcript")
    nodo = t.get_llamada(k, "laboratorio", "CA1")
    assert nodo["eventos_completados"] == ["recording", "transcript"]


def test_marcar_evento_crea_huerfana_si_no_existia():
    """Si el webhook llega antes de que persistiéramos initiated → crea shell."""
    k = _k()
    t.marcar_evento_completado(k, "laboratorio", "CA_huerfana", "recording")
    nodo = t.get_llamada(k, "laboratorio", "CA_huerfana")
    assert nodo["estado"] == "huerfana"
    assert "webhook_antes_de_initiated" in nodo["no_conforme_motivos"]


def test_persistir_transcript_marca_evento():
    k = _k()
    t.crear_llamada(k, "laboratorio", call_sid="CA1", lead_id="l", pendiente_id="p",
                    agente_config_version="v1")
    transcript = [
        {"hablante": "agente", "ts": 0.0, "texto": "Hola, le habla Iván..."},
        {"hablante": "cliente", "ts": 4.0, "texto": "Sí dígame."},
    ]
    t.persistir_transcript(k, "laboratorio", "CA1", transcript)
    nodo = t.get_llamada(k, "laboratorio", "CA1")
    assert nodo["transcript"] == transcript
    assert "transcript" in nodo["eventos_completados"]
    assert nodo["transcript_ts"]


def test_marcar_no_conforme_acumula_motivos():
    k = _k()
    t.crear_llamada(k, "laboratorio", call_sid="CA1", lead_id="l", pendiente_id="p",
                    agente_config_version="v1")
    t.marcar_no_conforme(k, "laboratorio", "CA1", "recording_faltante")
    t.marcar_no_conforme(k, "laboratorio", "CA1", "transcript_corrupto")
    nodo = t.get_llamada(k, "laboratorio", "CA1")
    assert nodo["estado"] == "no_conforme"
    assert nodo["no_conforme_motivos"] == ["recording_faltante", "transcript_corrupto"]


def test_todas_las_llamadas_filtra_por_estado():
    k = _k()
    for i, est in enumerate(["iniciada", "completada", "no_conforme"]):
        t.crear_llamada(k, "laboratorio", call_sid=f"CA{i}", lead_id="l", pendiente_id="p",
                        agente_config_version="v1")
        t.actualizar_llamada(k, "laboratorio", f"CA{i}", estado=est)
    completadas = t.todas_las_llamadas(k, "laboratorio", estados=["completada"])
    assert len(completadas) == 1 and completadas[0]["estado"] == "completada"
