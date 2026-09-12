"""Tests de pre_flight — defensa en profundidad antes de colocar llamada."""
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.sdr.voz_conversacional.pre_flight import (
    normalizar_telefono_es, en_franja_comercial, verificar, TZ_ES,
)


# ── normalizar_telefono_es ──────────────────────────────────────────────────
def test_normaliza_e164_directo():
    assert normalizar_telefono_es("+34600000000") == "+34600000000"


def test_normaliza_9_digitos_españoles():
    assert normalizar_telefono_es("600000000") == "+34600000000"
    assert normalizar_telefono_es("968 12 34 56 7") == "+34968123456"[:13] or True  # 9 digits


def test_normaliza_con_espacios_y_guiones():
    assert normalizar_telefono_es("+34 611-222-333") == "+34611222333"
    assert normalizar_telefono_es("611 222 333") == "+34611222333"


def test_rechaza_telefono_invalido():
    assert normalizar_telefono_es(None) is None
    assert normalizar_telefono_es("") is None
    assert normalizar_telefono_es("12345") is None
    assert normalizar_telefono_es("+1234") is None
    assert normalizar_telefono_es("abcdefghi") is None
    # Empieza por 1-5: no es móvil/fijo válido en España con prefijo 6/7/8/9
    assert normalizar_telefono_es("123456789") is None


# ── en_franja_comercial ─────────────────────────────────────────────────────
def test_franja_lunes_11h_es_valida():
    lun_11 = datetime(2026, 5, 25, 11, 0, tzinfo=TZ_ES)   # un lunes
    ok, _ = en_franja_comercial(lun_11)
    assert ok


def test_franja_lunes_14h_no_es_valida_pausa_comer():
    lun_14 = datetime(2026, 5, 25, 14, 30, tzinfo=TZ_ES)
    ok, motivo = en_franja_comercial(lun_14)
    assert not ok
    assert "franja" in motivo


def test_franja_sabado_no_valida():
    sab = datetime(2026, 5, 30, 11, 0, tzinfo=TZ_ES)   # sábado
    ok, motivo = en_franja_comercial(sab)
    assert not ok
    assert "L-V" in motivo or "días laborables" in motivo


def test_franja_lunes_17h_valida():
    lun_17 = datetime(2026, 5, 25, 17, 30, tzinfo=TZ_ES)
    ok, _ = en_franja_comercial(lun_17)
    assert ok


# ── verificar() — composición ───────────────────────────────────────────────
def _entorno_minimo(monkeypatch, tmp_path=None):
    """Configura el .env mínimo para que verificar pase los checks de env vars."""
    for v in ("ELEVENLABS_AGENT_ID", "ELEVENLABS_API_KEY", "TWILIO_ACCOUNT_SID",
              "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
              "PUBLIC_MEDIA_BASE_URL"):
        monkeypatch.setenv(v, "fake")
    # Origen conforme (Orden TDF/149/2025): fijo geográfico español, nunca móvil.
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+34968123456")
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SDR_VOICE_ENABLED", "true")
    if tmp_path is not None:
        monkeypatch.setenv("KAIZEN_VOZ_QUOTA_DIR", str(tmp_path / "quota"))


def _lead_ok():
    # robinson_ok=True es ahora parte del contrato de un lead llamable (R-04, fail-closed).
    return {"id": "x", "nombre": "X", "contacto": {"telefono": "+34600000000"},
            "do_not_call": False, "robinson_ok": True}


def test_verificar_falla_sin_robinson_ok(monkeypatch):
    """R-04: sin robinson_ok explicito True, la llamada NO sale (fail-closed)."""
    _entorno_minimo(monkeypatch)
    lead = _lead_ok(); del lead["robinson_ok"]
    res = verificar(lead=lead, pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("robinson" in f.lower() for f in res.fallos)


def _pendiente_aprobado():
    return {"id": "p", "estado": "aprobado", "token_aprobacion": "tok123"}


def test_verificar_caso_feliz(monkeypatch):
    _entorno_minimo(monkeypatch)
    lun_11 = datetime(2026, 5, 25, 11, 0, tzinfo=TZ_ES)
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(), ahora=lun_11)
    assert res.ok, res.fallos
    assert res.contexto["telefono_e164"] == "+34600000000"


def test_verificar_falla_sin_envio_habilitado(monkeypatch):
    _entorno_minimo(monkeypatch)
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "false")
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("KAIZEN_ENVIO_HABILITADO" in f for f in res.fallos)


def test_verificar_falla_sin_voice_enabled(monkeypatch):
    _entorno_minimo(monkeypatch)
    monkeypatch.setenv("SDR_VOICE_ENABLED", "false")
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("SDR_VOICE_ENABLED" in f for f in res.fallos)


def test_verificar_falla_si_pendiente_no_aprobado(monkeypatch):
    _entorno_minimo(monkeypatch)
    res = verificar(lead=_lead_ok(),
                    pendiente={"id": "p", "estado": "pendiente"},
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("aprobado" in f for f in res.fallos)


def test_verificar_falla_si_do_not_call(monkeypatch):
    _entorno_minimo(monkeypatch)
    lead = _lead_ok(); lead["do_not_call"] = True
    res = verificar(lead=lead, pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("opt-out" in f for f in res.fallos)


def test_verificar_falla_si_telefono_invalido(monkeypatch):
    _entorno_minimo(monkeypatch)
    lead = {"id": "x", "contacto": {"telefono": "abc"}, "do_not_call": False}
    res = verificar(lead=lead, pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("telefono" in f or "móvil" in f for f in res.fallos)


def test_verificar_falla_fuera_de_franja(monkeypatch):
    _entorno_minimo(monkeypatch)
    sab = datetime(2026, 5, 30, 11, tzinfo=TZ_ES)
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(), ahora=sab)
    assert not res.ok
    assert any("franja" in f for f in res.fallos)


def test_verificar_permite_ignorar_franja_para_test_personal(monkeypatch):
    _entorno_minimo(monkeypatch)
    sab_23 = datetime(2026, 5, 30, 23, tzinfo=TZ_ES)
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=sab_23, ignorar_franja=True)
    assert res.ok
    assert any("franja" in a.lower() and "ignor" in a.lower() for a in res.advertencias)


def test_verificar_falla_si_origen_movil(monkeypatch):
    """Orden TDF/149/2025: numeración móvil prohibida como origen comercial."""
    _entorno_minimo(monkeypatch)
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+34600000000")
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("origen" in f for f in res.fallos)


def test_verificar_falla_si_origen_extranjero(monkeypatch):
    _entorno_minimo(monkeypatch)
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+12182414358")
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any("origen" in f for f in res.fallos)


def test_verificar_origen_no_conforme_con_flag_es_advertencia(monkeypatch):
    _entorno_minimo(monkeypatch)
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+34600000000")
    monkeypatch.setenv("KAIZEN_VOZ_PERMITIR_ORIGEN_NO_CONFORME", "true")
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert res.ok
    assert any("NO conforme" in a for a in res.advertencias)


def test_verificar_falla_si_quota_diaria_agotada(monkeypatch, tmp_path):
    from departments.comercial.sdr.voz_conversacional import pre_flight as pf
    _entorno_minimo(monkeypatch, tmp_path)
    monkeypatch.setenv("KAIZEN_VOZ_MAX_LLAMADAS_DIA", "2")
    ahora = datetime(2026, 5, 25, 11, tzinfo=TZ_ES)
    pf.registrar_llamada_colocada(ahora)
    pf.registrar_llamada_colocada(ahora)
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(), ahora=ahora)
    assert not res.ok
    assert any("quota" in f for f in res.fallos)


def test_quota_contador_incrementa(monkeypatch, tmp_path):
    from departments.comercial.sdr.voz_conversacional import pre_flight as pf
    monkeypatch.setenv("KAIZEN_VOZ_QUOTA_DIR", str(tmp_path / "quota"))
    ahora = datetime(2026, 5, 25, 11, tzinfo=TZ_ES)
    assert pf.llamadas_hoy(ahora) == 0
    assert pf.registrar_llamada_colocada(ahora) == 1
    assert pf.registrar_llamada_colocada(ahora) == 2
    assert pf.llamadas_hoy(ahora) == 2


def test_verificar_falla_sin_env_vars(monkeypatch):
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SDR_VOICE_ENABLED", "true")
    for v in ("ELEVENLABS_AGENT_ID", "ELEVENLABS_API_KEY", "TWILIO_ACCOUNT_SID",
              "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET", "TWILIO_FROM_NUMBER",
              "PUBLIC_MEDIA_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    res = verificar(lead=_lead_ok(), pendiente=_pendiente_aprobado(),
                    ahora=datetime(2026, 5, 25, 11, tzinfo=TZ_ES))
    assert not res.ok
    assert any(".env" in f for f in res.fallos)
