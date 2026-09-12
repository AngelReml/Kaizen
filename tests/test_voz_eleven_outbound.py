"""Tests del cliente de ElevenLabs Outbound API (HTTP mockeado)."""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.voz_conversacional import eleven_outbound as eo


def _env_completo(mp, tmp_path):
    mp.setenv("ELEVENLABS_API_KEY", "fake_key")
    mp.setenv("ELEVENLABS_AGENT_ID", "agent_test")
    mp.setenv("ELEVENLABS_PHONE_NUMBER_ID", "phnum_test")
    # R-02 embebido en colocar_llamada_via_cai (auditoría 2026-08-02/06): sin estas
    # dos barreras de sandbox, la función ahora falla-cerrado antes de llegar al POST.
    mp.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    mp.setenv("SDR_VOICE_ENABLED", "true")
    # Aislamiento de quota (mismo patron que test_voz_pre_flight.py): sin esto,
    # colocar_llamada_via_cai consume la quota diaria REAL de core.rutas.dir_state()
    # (fuera del arbol, compartida con la app real) en cada ejecucion de pytest —
    # confirmado: 4 dias de quota_AAAAMMDD.json en KAIZEN_DATOS/state/voz/quota/
    # con conteos que solo pueden venir de tests, hasta agotar 25/25 hoy mismo.
    mp.setenv("KAIZEN_VOZ_QUOTA_DIR", str(tmp_path / "quota"))


class _Resp:
    def __init__(self, status=200, json_=None, text=""):
        self.status_code = status
        self._json = json_ or {}
        self.text = text or str(json_ or "")
    def json(self): return self._json


# ── construir_body ──────────────────────────────────────────────────────────
def test_body_minimo_sin_lead():
    body = eo.construir_body(agent_id="a", agent_phone_number_id="p",
                              to_number="+34600000000")
    assert body["agent_id"] == "a"
    assert body["agent_phone_number_id"] == "p"
    assert body["to_number"] == "+34600000000"
    assert "conversation_initiation_client_data" not in body


def test_body_con_lead_inyecta_dynamic_variables():
    lead = {"id": "x", "nombre": "Hotel La Parra",
            "categoria_icp": "hotel_boutique_con_desayuno",
            "prioridad_icp": "ALTA", "anillo": 0,
            "ubicacion": {"direccion": "Cieza, Murcia"}}
    body = eo.construir_body(agent_id="a", agent_phone_number_id="p",
                              to_number="+34600000000", lead=lead)
    vs = body["conversation_initiation_client_data"]["dynamic_variables"]
    assert vs["lead_nombre"] == "Hotel La Parra"
    assert vs["categoria"] == "hotel_boutique_con_desayuno"
    assert vs["anillo"] == "0"
    assert vs["ciudad"] == "Cieza, Murcia"


def test_body_extra_variables_se_mezclan():
    body = eo.construir_body(agent_id="a", agent_phone_number_id="p",
                              to_number="+34111", lead={"id": "x"},
                              extra_variables={"campaign": "v1", "operator": "manual"})
    vs = body["conversation_initiation_client_data"]["dynamic_variables"]
    assert vs["campaign"] == "v1" and vs["operator"] == "manual"


# ── dry_run ─────────────────────────────────────────────────────────────────
def test_dry_run_no_hace_red(monkeypatch, tmp_path):
    _env_completo(monkeypatch, tmp_path)
    llamadas = []
    monkeypatch.setattr(requests, "post",
                        lambda *a, **kw: llamadas.append(1) or _Resp(200))
    out = eo.dry_run(to_number_e164="+34600000000", lead={"id": "x", "nombre": "X"})
    assert llamadas == []                      # NO hubo POST
    assert out["would_post_to"].endswith("/outbound-call")
    assert out["body"]["to_number"] == "+34600000000"
    assert out["estado_credenciales"]["ELEVENLABS_API_KEY"] == "PRESENTE"


def test_dry_run_muestra_lo_que_falta(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_AGENT_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_PHONE_NUMBER_ID", raising=False)
    out = eo.dry_run(to_number_e164="", lead={"id": "x"})
    assert out["estado_credenciales"]["ELEVENLABS_API_KEY"] == "FALTA"
    assert out["estado_credenciales"]["TO_NUMBER"] == "FALTA"


# ── colocar_llamada_via_cai ─────────────────────────────────────────────────
def test_falla_explicito_si_falta_phone_number_id(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "x")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "a")
    monkeypatch.delenv("ELEVENLABS_PHONE_NUMBER_ID", raising=False)
    res = eo.colocar_llamada_via_cai(to_number_e164="+34600000000",
                                      lead={"id": "x"})
    assert not res.ok
    assert "ELEVENLABS_PHONE_NUMBER_ID" in res.motivo


def test_falla_si_destino_vacio(monkeypatch, tmp_path):
    _env_completo(monkeypatch, tmp_path)
    res = eo.colocar_llamada_via_cai(to_number_e164="", lead={"id": "x"})
    assert not res.ok
    assert "vacío" in res.motivo


def test_camino_feliz_devuelve_conversation_id(monkeypatch, tmp_path):
    _env_completo(monkeypatch, tmp_path)
    monkeypatch.setattr(requests, "post",
                        lambda *a, **kw: _Resp(200, {"conversation_id": "conv_xyz",
                                                     "callSid": "CA999"}))
    res = eo.colocar_llamada_via_cai(to_number_e164="+34600000000",
                                      lead={"id": "x", "nombre": "X"})
    assert res.ok
    assert res.conversation_id == "conv_xyz"
    assert res.call_sid == "CA999"


def test_propaga_error_si_eleven_401_por_scope(monkeypatch, tmp_path):
    """Caso real esperable mientras la API key no tenga convai_write."""
    _env_completo(monkeypatch, tmp_path)
    monkeypatch.setattr(requests, "post",
                        lambda *a, **kw: _Resp(401,
                            {"detail": "missing convai_write"},
                            "missing convai_write"))
    res = eo.colocar_llamada_via_cai(to_number_e164="+34600000000",
                                      lead={"id": "x"})
    assert not res.ok
    assert "401" in res.motivo
    assert "convai_write" in res.motivo


def test_recoge_excepcion_de_red(monkeypatch, tmp_path):
    _env_completo(monkeypatch, tmp_path)
    def _post(*a, **kw): raise requests.ConnectionError("DNS")
    monkeypatch.setattr(requests, "post", _post)
    res = eo.colocar_llamada_via_cai(to_number_e164="+34600000000",
                                      lead={"id": "x"})
    assert not res.ok
    assert "red:" in res.motivo
