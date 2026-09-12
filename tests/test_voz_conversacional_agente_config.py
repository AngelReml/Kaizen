"""Tests del snapshot del agente CAI v1 — integridad del audit trail.

No probamos el comportamiento del agente (eso pasa en V0 simulador y V1 llamada real),
solo que el snapshot que se commitea al repo está completo, consistente y cumple R5
(aviso de grabación al inicio).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.voz_conversacional import agente_config_v1 as v1


# ── Integridad básica ────────────────────────────────────────────────────────
def test_version_y_voz_correctas():
    assert v1.VERSION == "v1"
    assert v1.VOZ["voice_id"] == "bQHF8nZQdy0OLdcUonXg"
    assert v1.VOZ["category"] == "cloned"
    assert v1.VOZ["tts_model"] == "eleven_multilingual_v2"


def test_llm_es_claude_sonnet_4_6_con_byo_key():
    assert v1.LLM["provider"] == "anthropic"
    assert v1.LLM["model"] == "claude-sonnet-4-6"
    assert v1.LLM["byo_api_key"] is True


def test_conversacion_tiene_timeouts_protectores():
    """Protección contra coste runaway: max 10min y idle timeout."""
    assert v1.CONVERSATION["max_duration_s"] <= 900       # <=15min absoluto
    assert v1.CONVERSATION["idle_timeout_s"] <= 60
    assert v1.CONVERSATION["allow_interruptions"] is True


def test_grabacion_activada():
    """R1: toda llamada se graba (cobertura ElevenLabs además de Twilio Record=true)."""
    assert v1.PRIVACY["recordings_eleven"] is True
    assert v1.PRIVACY["conversation_history"] == "save"


# ── R5: compliance del aviso ────────────────────────────────────────────────
def test_first_message_contiene_aviso_de_grabacion():
    """El primer mensaje del agente debe mencionar la grabación (cumple R5
    incluso en el simulador donde el <Say> Twilio aún no existe)."""
    txt = v1.FIRST_MESSAGE.lower()
    assert "grabad" in txt, "Falta mención de grabación en el First Message"


def test_first_message_identifica_al_remitente():
    """Identificación clara del remitente al inicio.

    R-TENANT: `agente_config_v*` es un SNAPSHOT DE DESPLIEGUE — conserva la
    identidad con la que se desplegó y por eso nombra a un tenant concreto.
    Lo que este test fija es la obligación (identificarse), no de quién."""
    txt = v1.FIRST_MESSAGE.lower()
    assert v1.NOMBRE_AGENTE, "el snapshot debe declarar el agente desplegado"
    assert len(txt) > 40, "el saludo debe identificar a quien llama"
    assert "le habla" in txt or "le llama" in txt or "soy" in txt


def test_first_message_ofrece_opt_out_inmediato():
    """LSSI: el cliente debe poder colgar sin penalización al inicio."""
    txt = v1.FIRST_MESSAGE.lower()
    assert "colgar" in txt or "no continuar" in txt or "no recibir" in txt


def test_aviso_legal_twilio_existe_y_cubre_grabacion():
    """El <Say> Twilio previo al Stream también debe avisar de grabación."""
    aviso = v1.aviso_legal_twilio()
    assert aviso, "Aviso legal vacío"
    low = aviso.lower()
    assert "grabad" in low
    assert "comercial" in low or "comerciales" in low
    assert "colgar" in low or "no continuar" in low


# ── System prompt: contenidos críticos ──────────────────────────────────────
def test_system_prompt_incluye_compromiso_reciproco():
    """El agente debe conocer las señales del v0.2 §3.2."""
    p = v1.SYSTEM_PROMPT.lower()
    assert "compromiso recíproco" in p or "compromiso reciproco" in p
    assert "muestra" in p
    # Algunas señales clave deben estar.
    assert any(s in p for s in ("proveedor actual", "volumen", "evento"))


def test_system_prompt_blinda_contra_engano_de_ia():
    """Si el cliente pregunta si es IA, debe responder honestamente."""
    p = v1.SYSTEM_PROMPT.lower()
    assert "ia" in p or "inteligencia artificial" in p or "sistema asistente" in p
    assert "honest" in p


def test_system_prompt_prohibe_jerga_corporativa():
    """El tono Laboratorio NO admite ROI/win-win/oportunidad única."""
    p = v1.SYSTEM_PROMPT.lower()
    assert "roi" in p or "win-win" in p or "win win" in p or "jerga" in p


def test_system_prompt_define_cierre_explicito():
    """Hay reglas claras de cuándo colgar (no enrollarse)."""
    p = v1.SYSTEM_PROMPT.lower()
    assert "cerrar la llamada" in p or "cerrar" in p
    assert any(c in p for c in ("minutos sin progreso", "no le interesa", "agradeciendo"))


def test_tools_v0_vacio_pero_v1_propuesto():
    """En V0 no se conectan tools (validamos conversación pura)."""
    assert v1.TOOLS_V0 == []
    nombres_v1 = {t["name"] for t in v1.TOOLS_V1_PROPUESTA}
    # Los tools imprescindibles de V1 deben estar contemplados.
    assert "marcar_compromiso_reciproco" in nombres_v1
    assert "derivar_a_humano" in nombres_v1
    assert "marcar_opt_out" in nombres_v1


# ── Sanidad de longitudes ───────────────────────────────────────────────────
def test_system_prompt_no_es_trivialmente_corto():
    assert len(v1.SYSTEM_PROMPT) > 1500


def test_first_message_no_es_excesivamente_largo():
    """Apertura debe ser <500 chars para no agotar al cliente."""
    assert len(v1.FIRST_MESSAGE) < 500
