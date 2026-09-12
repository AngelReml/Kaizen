"""Tests del detector de compromisos (Módulo 4)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.compromisos import DetectorCompromisos, _formatear_transcript, TIPOS_VALIDOS


FIXTURES = Path(__file__).parent / "fixtures"


def _stub_chat(salida: str):
    """Crea un chat fake que devuelve la salida dada (independiente de la API real)."""
    def _chat(messages, *, system=None, model=None, max_tokens=None, company="default"):
        return salida
    return _chat


def _stub_chat_que_explota(exc=RuntimeError("LLM caído")):
    def _chat(messages, **kwargs):
        raise exc
    return _chat


# --- Parser puro (sin LLM) -----------------------------------------------

def test_parsear_json_limpio():
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T08:00:00+00:00",
         "tolerancia_min": 60, "contexto": "callback Lidia"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1
    assert comps[0].tipo == "callback"
    assert comps[0].tolerancia_min == 60
    # Ya estaba en UTC: queda igual
    assert comps[0].fecha_objetivo == "2026-05-28T08:00:00+00:00"
    assert comps[0].cumplido is False
    assert comps[0].id.startswith("comp_")


def test_parsear_normaliza_offset_madrid_a_utc():
    """LLM devuelve hora local Madrid con offset +02:00; parser normaliza a UTC."""
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T10:00:00+02:00",
         "tolerancia_min": 60, "contexto": "callback Lidia"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1
    # 10:00 Madrid = 08:00 UTC
    assert comps[0].fecha_objetivo == "2026-05-28T08:00:00+00:00"


def test_parsear_naive_asume_madrid():
    """Si el LLM devuelve sin offset, parser asume hora Madrid."""
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-12-15T10:00:00",
         "tolerancia_min": 15, "contexto": "x"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1
    # Diciembre = invierno = +01:00, 10:00 Madrid = 09:00 UTC
    assert comps[0].fecha_objetivo == "2026-12-15T09:00:00+00:00"


def test_parsear_lista_vacia():
    assert DetectorCompromisos._parsear('{"compromisos": []}') == []


def test_parsear_tolera_markdown():
    salida = """Aquí tienes el JSON:
```json
{"compromisos": [{"tipo": "muestra", "fecha_objetivo": "", "tolerancia_min": 15,
                   "contexto": "mandar caja"}]}
```
Fin."""
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1
    assert comps[0].tipo == "muestra"


def test_parsear_tipo_invalido_se_descarta():
    salida = json.dumps({"compromisos": [
        {"tipo": "cosa_inventada", "fecha_objetivo": "2026-05-28T08:00:00+00:00"},
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T08:00:00+00:00"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1
    assert comps[0].tipo == "callback"


def test_parsear_fecha_invalida_se_descarta():
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "mañana a las 10"}]})
    assert DetectorCompromisos._parsear(salida) == []


def test_parsear_acepta_fecha_vacia_no_aplica():
    """Algunos tipos (referido) pueden no tener fecha concreta."""
    salida = json.dumps({"compromisos": [
        {"tipo": "referido", "fecha_objetivo": "", "tolerancia_min": 0,
         "contexto": "hablar con su mujer"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1
    assert comps[0].fecha_objetivo == ""


def test_parsear_basura_devuelve_vacio():
    assert DetectorCompromisos._parsear("lorem ipsum sin JSON") == []
    assert DetectorCompromisos._parsear("") == []
    assert DetectorCompromisos._parsear("{esto no es json}") == []


def test_parsear_acepta_Z_como_utc():
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T08:00:00Z",
         "tolerancia_min": 60, "contexto": "x"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert len(comps) == 1


def test_parsear_default_tolerancia_15():
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T08:00:00+00:00"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert comps[0].tolerancia_min == 15


def test_parsear_contexto_fallback_a_literal_cliente():
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T08:00:00+00:00",
         "literal_cliente": "llámame mañana"}]})
    comps = DetectorCompromisos._parsear(salida)
    assert comps[0].contexto == "llámame mañana"


# --- Formateador de transcript ---------------------------------------------

def test_formatear_transcript_distingue_agente_cliente():
    turnos = [
        {"hablante": "agente", "ts": 0.0, "texto": "Hola"},
        {"hablante": "cliente", "ts": 1.5, "texto": "Sí dígame"},
    ]
    out = _formatear_transcript(turnos)
    assert "AGENTE: Hola" in out
    assert "CLIENTE: Sí dígame" in out


def test_formatear_transcript_acepta_formato_eleven():
    """Acepta también el formato de ElevenLabs (role + message)."""
    turnos = [
        {"role": "agent", "ts": 0.0, "message": "Hola"},
        {"role": "user", "ts": 1.0, "message": "Hola"},
    ]
    out = _formatear_transcript(turnos)
    assert "AGENTE: Hola" in out
    assert "CLIENTE: Hola" in out


def test_formatear_transcript_vacio():
    assert _formatear_transcript([]) == ""
    assert _formatear_transcript(None) == ""


# --- Detector completo con chat mock --------------------------------------

def test_detectar_transcript_vacio_devuelve_vacio():
    det = DetectorCompromisos(chat=_stub_chat("nunca llamado"))
    assert det.detectar([]) == []


def test_detectar_llm_explota_no_crashea():
    det = DetectorCompromisos(chat=_stub_chat_que_explota())
    out = det.detectar([{"hablante": "cliente", "ts": 0.0, "texto": "hola"}])
    assert out == []


def test_detectar_llm_devuelve_callback():
    salida = json.dumps({"compromisos": [
        {"tipo": "callback", "fecha_objetivo": "2026-05-28T08:00:00+00:00",
         "tolerancia_min": 60, "contexto": "callback Lidia",
         "literal_cliente": "mañana entre las 10 y las 11"}]})
    det = DetectorCompromisos(
        chat=_stub_chat(salida),
        fecha_referencia_utc=datetime(2026, 5, 27, 15, 0, tzinfo=timezone.utc),
    )
    out = det.detectar([
        {"hablante": "cliente", "ts": 0, "texto": "mañana entre las 10 y las 11"},
        {"hablante": "agente", "ts": 1, "texto": "vale, te llamaré"},
    ])
    assert len(out) == 1
    assert out[0].tipo == "callback"
    assert out[0].tolerancia_min == 60


def test_detectar_pasa_fecha_referencia_al_prompt():
    capturado = {}
    def chat(messages, *, system=None, **kw):
        capturado["msg"] = messages[0]["content"]
        capturado["sys"] = system
        return '{"compromisos": []}'
    det = DetectorCompromisos(
        chat=chat,
        fecha_referencia_utc=datetime(2026, 5, 27, 15, 0, tzinfo=timezone.utc),
    )
    det.detectar([{"hablante": "cliente", "ts": 0, "texto": "x"}])
    assert "2026-05-27T15:00:00+00:00" in capturado["msg"]
    # Día Madrid: 2026-05-27 17:00 = Wednesday
    assert "Wednesday" in capturado["msg"]
    # R-TENANT: el system prompt describe el ROL, jamas un cliente concreto.
    assert "negocio emisor" in capturado["sys"]
    assert "laboratorio" not in capturado["sys"].lower()


def test_tipos_validos_son_los_cinco():
    assert TIPOS_VALIDOS == {"callback", "muestra", "email_info", "referido", "visita"}


# --- Test con el transcript REAL de Lidia (LLM mock) ----------------------

def test_transcript_lidia_extrae_callback_con_mock():
    """Verifica el pipeline completo con el transcript real de Lidia, usando un
    mock de LLM que simula la salida correcta."""
    fixture = json.loads((FIXTURES / "transcript_lidia.json").read_text(encoding="utf-8"))
    # Salida que el LLM debería devolver para este transcript
    # Llamada fue 2026-05-26T18:16Z → "mañana" desde Madrid = 2026-05-27
    salida_esperada = json.dumps({"compromisos": [{
        "tipo": "callback",
        "fecha_objetivo": "2026-05-27T10:00:00+02:00",
        "tolerancia_min": 60,
        "contexto": "Llamar mañana entre 10 y 11 para hablar con el encargado",
        "literal_cliente": "mañana por la mañana entre las 10 y las 11",
        "literal_agente": "mañana entre las diez y las once de la mañana llamaré",
    }]})
    det = DetectorCompromisos(
        chat=_stub_chat(salida_esperada),
        fecha_referencia_utc=datetime.fromisoformat(fixture["fecha_llamada_utc"]),
    )
    comps = det.detectar(fixture["transcript"])
    assert len(comps) == 1
    c = comps[0]
    assert c.tipo == "callback"
    assert c.tolerancia_min == 60
    # 10:00 Madrid = 08:00 UTC el 27 de mayo
    assert c.fecha_objetivo == "2026-05-27T08:00:00+00:00"
    assert "encargado" in c.contexto.lower() or "10" in c.contexto


# --- Opt-in: contra LLM REAL (requiere ANTHROPIC_API_KEY y opt-in flag) ----

@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("KAIZEN_TEST_LLM_REAL")),
    reason="LLM real requiere ANTHROPIC_API_KEY + KAIZEN_TEST_LLM_REAL=1",
)
def test_transcript_lidia_con_llm_real():
    fixture = json.loads((FIXTURES / "transcript_lidia.json").read_text(encoding="utf-8"))
    det = DetectorCompromisos(
        fecha_referencia_utc=datetime.fromisoformat(fixture["fecha_llamada_utc"]),
    )
    comps = det.detectar(fixture["transcript"])
    # El callback de mañana 10-11h tiene que aparecer
    callbacks = [c for c in comps if c.tipo == "callback"]
    assert len(callbacks) >= 1, f"Se esperaba al menos 1 callback, salieron: {comps}"
    cb = callbacks[0]
    # Llamada el 2026-05-26T18Z, "mañana" debe ser 2026-05-27
    assert cb.fecha_objetivo.startswith("2026-05-27"), \
        f"Fecha esperada mañana (2026-05-27), salió: {cb.fecha_objetivo}"
    # Hora esperada: 10:00 Madrid = 08:00 UTC
    assert "T08:" in cb.fecha_objetivo or "T07:" in cb.fecha_objetivo, \
        f"Hora esperada 08:00 UTC (10:00 Madrid), salió: {cb.fecha_objetivo}"
    # Tolerancia 60 (entre 10 y 11) o aceptable 30+
    assert cb.tolerancia_min >= 30
