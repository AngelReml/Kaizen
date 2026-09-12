"""Tests del wrapper `ClienteCAI` — HTTP mockeado (no toca ElevenLabs de verdad).

Cuando la API key tenga scopes convai_*, estos tests aseguran que el body que
mandamos a /v1/convai/agents/create coincide bit-a-bit con el snapshot.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.voz_conversacional import agente_config_v1 as v1
from departments.comercial.sdr.voz_conversacional.cliente_eleven_cai import (
    ClienteCAI, ResultadoDespliegue,
)


# ── Doubles ─────────────────────────────────────────────────────────────────
class _FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text or (str(json_data) if json_data else "")
    def json(self): return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}: {self.text}")


@pytest.fixture
def patcher(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake_key")
    calls = []
    def fake_get(url, **kw):
        calls.append(("GET", url, kw)); return calls[-1][3] if len(calls[-1]) > 3 else _resp_for(url, "GET")
    def fake_post(url, **kw):
        calls.append(("POST", url, kw)); return _resp_for(url, "POST", kw)
    def fake_patch(url, **kw):
        calls.append(("PATCH", url, kw)); return _resp_for(url, "PATCH", kw)

    def _resp_for(url, method, kw=None):
        if url.endswith("/v1/convai/agents") and method == "GET":
            return _FakeResp(200, {"agents": []})
        if url.endswith("/v1/convai/agents/create") and method == "POST":
            return _FakeResp(200, {"agent_id": "agent_abc123"})
        if "/v1/convai/agents/agent_abc123" in url:
            return _FakeResp(200, {"agent_id": "agent_abc123", "name": v1.NOMBRE_AGENTE})
        return _FakeResp(404, {"err": "not found"}, "not found")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "patch", fake_patch)
    return SimpleNamespace(calls=calls)


# ── Listado ─────────────────────────────────────────────────────────────────
def test_listar_agentes_devuelve_lista_aunque_la_api_envuelva_en_dict(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(requests, "get",
                        lambda url, **kw: _FakeResp(200, {"agents": [{"agent_id": "a1"}]}))
    assert ClienteCAI().listar_agentes() == [{"agent_id": "a1"}]


def test_listar_agentes_acepta_lista_directa(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(requests, "get",
                        lambda url, **kw: _FakeResp(200, [{"agent_id": "a1"}]))
    assert ClienteCAI().listar_agentes() == [{"agent_id": "a1"}]


# ── Construcción del body ───────────────────────────────────────────────────
def test_body_contiene_first_message_y_system_prompt_exactos():
    body = ClienteCAI._construir_body(v1)
    assert body["name"] == v1.NOMBRE_AGENTE
    agente = body["conversation_config"]["agent"]
    assert agente["first_message"] == v1.FIRST_MESSAGE
    assert agente["prompt"]["prompt"] == v1.SYSTEM_PROMPT
    assert agente["language"] == "es"


def test_body_lleva_llm_de_claude_sonnet_4_6():
    body = ClienteCAI._construir_body(v1)
    prompt = body["conversation_config"]["agent"]["prompt"]
    assert prompt["llm"] == "claude-sonnet-4-6"
    assert prompt["temperature"] == 0.5
    assert prompt["max_tokens"] == 200


def test_body_lleva_voz_clonada_ivan_y_modelo_multilingual():
    body = ClienteCAI._construir_body(v1)
    tts = body["conversation_config"]["tts"]
    assert tts["voice_id"] == "bQHF8nZQdy0OLdcUonXg"
    assert tts["model_id"] == "eleven_multilingual_v2"
    assert tts["stability"] == 0.5
    assert tts["similarity_boost"] == 0.85


def test_body_lleva_max_duration_10min():
    body = ClienteCAI._construir_body(v1)
    assert body["conversation_config"]["conversation"]["max_duration_seconds"] == 600


def test_body_lleva_record_voice_true_para_R1():
    body = ClienteCAI._construir_body(v1)
    privacy = body["platform_settings"]["privacy"]
    assert privacy["record_voice"] is True


# ── Despliegue idempotente ──────────────────────────────────────────────────
def test_crea_agente_nuevo_si_no_existe(patcher):
    res = ClienteCAI().crear_o_actualizar_agente(v1)
    assert res.creado is True
    assert res.agent_id == "agent_abc123"
    # Verificar que se hizo el POST a /create
    posts = [c for c in patcher.calls if c[0] == "POST" and c[1].endswith("/agents/create")]
    assert len(posts) == 1
    body_enviado = posts[0][2]["json"]
    assert body_enviado["name"] == v1.NOMBRE_AGENTE


def test_actualiza_agente_existente_en_vez_de_duplicar(monkeypatch):
    """Si ya hay un agente con el mismo nombre, hace PATCH, no POST /create."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(requests, "get",
                        lambda url, **kw: _FakeResp(200, {"agents":
                            [{"agent_id": "existing_id", "name": v1.NOMBRE_AGENTE}]}))
    posts = []; patches = []
    monkeypatch.setattr(requests, "post",
                        lambda url, **kw: (posts.append((url, kw)) or _FakeResp(200, {"ok": True})))
    monkeypatch.setattr(requests, "patch",
                        lambda url, **kw: (patches.append((url, kw)) or _FakeResp(200, {"ok": True})))
    res = ClienteCAI().crear_o_actualizar_agente(v1)
    assert res.creado is False
    assert res.agent_id == "existing_id"
    # PATCH al endpoint del agente existente, NO POST /create.
    assert any("/agents/existing_id" in u for u, _ in patches)
    assert not any(u.endswith("/agents/create") for u, _ in posts)


def test_falla_explicito_si_api_key_ausente(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        ClienteCAI()


def test_propaga_error_si_create_devuelve_4xx(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake")
    monkeypatch.setattr(requests, "get",
                        lambda url, **kw: _FakeResp(200, {"agents": []}))
    monkeypatch.setattr(requests, "post",
                        lambda url, **kw: _FakeResp(401, {"detail": "missing scope convai_write"},
                                                    "missing scope convai_write"))
    with pytest.raises(RuntimeError, match="401"):
        ClienteCAI().crear_o_actualizar_agente(v1)
