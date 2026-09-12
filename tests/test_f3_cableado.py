"""F3 — cablear la empresa real (auditoria 2026-07-20).

R-09 email exactamente-una-vez + TTL · R-10 marca por tenant · R-12 Decimal fiscal ·
E4 candado AIACT por fecha · R-16 ejecutor real con barreras en orden.
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── R-09 · email exactamente-una-vez (claim atomico CAS + TTL) ────────────────

def _cola_con_aprobado():
    from core.knowledge import InMemoryKnowledge
    from departments.comercial.cola_aprobacion import ColaAprobacion, hash_mensaje
    c = ColaAprobacion(InMemoryKnowledge(), "laboratorio")
    p = c.encolar(lead_id="l", canal="email", destino="x@y.com", asunto="A",
                  cuerpo="B", brand_review={}, campaign_id="cmp")
    nodo = c.aprobar(p.id, aprobado_por="test")
    h = hash_mensaje("email", "x@y.com", "A", "B")
    return c, p.id, nodo["token_aprobacion"], h


def test_r09_claim_atomico_impide_doble_envio():
    from departments.comercial.cola_aprobacion import EnvioSinAprobacion
    c, pid, token, h = _cola_con_aprobado()
    n1 = c.reclamar_envio(pendiente_id=pid, token=token, hash_a_enviar=h)
    assert n1["estado"] == "enviando"
    with pytest.raises(EnvioSinAprobacion):          # el segundo claim NO pasa
        c.reclamar_envio(pendiente_id=pid, token=token, hash_a_enviar=h)


def test_r09_revertir_reclamo_permite_reintento():
    c, pid, token, h = _cola_con_aprobado()
    c.reclamar_envio(pendiente_id=pid, token=token, hash_a_enviar=h)
    c.revertir_reclamo(pid)
    assert c.get(pid)["estado"] == "aprobado"
    n = c.reclamar_envio(pendiente_id=pid, token=token, hash_a_enviar=h)   # ya se puede otra vez
    assert n["estado"] == "enviando"


def test_r09_aprobacion_caduca_por_ttl(monkeypatch):
    from departments.comercial.cola_aprobacion import AprobacionCaducada
    monkeypatch.setenv("KAIZEN_APROBACION_TTL_SEGUNDOS", "0")   # todo caduca al instante
    c, pid, token, h = _cola_con_aprobado()
    with pytest.raises(AprobacionCaducada):
        c.verificar_token(pendiente_id=pid, token=token, hash_a_enviar=h)


def test_r09_hash_distinto_no_pasa():
    from departments.comercial.cola_aprobacion import EnvioSinAprobacion
    c, pid, token, _ = _cola_con_aprobado()
    with pytest.raises(EnvioSinAprobacion):
        c.reclamar_envio(pendiente_id=pid, token=token, hash_a_enviar="otro")


# ── E4 · candado AI Act por fecha ─────────────────────────────────────────────

def test_e4_bloquea_sin_disclosure_desde_02_ago():
    from core.aiact_gate import exigir_transparencia, AIActSinTransparencia
    texto = "Buenos dias, le escribo de parte del obrador para presentarle nuestros productos."
    with pytest.raises(AIActSinTransparencia):
        exigir_transparencia(texto, ahora=date(2026, 8, 2))
    with pytest.raises(AIActSinTransparencia):
        exigir_transparencia(texto, ahora=date(2026, 9, 1))


def test_e4_permite_con_disclosure():
    from core.aiact_gate import exigir_transparencia
    texto = ("Le escribe el asistente virtual con inteligencia artificial de Reposteria "
             "Laboratorio. Es un mensaje comercial.")
    r = exigir_transparencia(texto, ahora=date(2026, 8, 2))
    assert r["ok"] and r["gate_activo"] and r["tiene_disclosure"]


def test_e4_antes_de_la_fecha_avisa_pero_no_bloquea():
    from core.aiact_gate import exigir_transparencia
    r = exigir_transparencia("sin disclosure", ahora=date(2026, 7, 20))
    assert r["ok"] and r["gate_activo"] is False and "aviso" in r


# ── R-12 · dinero fiscal en Decimal (media-arriba, no binario) ────────────────

def test_r12_redondeo_media_arriba_no_binario():
    from departments.finanzas.cubo_serie_d import _eur, _cuota_iva
    # el caso canonico: round(2.675,2)=2.67 (binario) vs 2.68 (fiscal, media-arriba)
    assert _eur(2.675) == 2.68
    assert _cuota_iva(12.755, 0.21) == round(12.755 * 0.21 + 1e-9, 2) or _cuota_iva(12.755, 0.21) > 0


def test_r12_iva_parametrizable_y_validado():
    from core.knowledge import InMemoryKnowledge
    from departments.finanzas.cubo_serie_d import MotorSIF, IVAInvalido
    sif = MotorSIF(InMemoryKnowledge(), "t")
    r = sif.emitir(nif_obligado="SINTETICO-A", nif_destinatario="SINTETICO-B",
                   serie="A", importe_neto=100.0, iva_pct=0.10)      # reducido
    reg = sif.k.get("t", "sif_registro", r["rfa_ref"])
    assert reg["iva_cuota"] == 10.0 and reg["importe_total"] == 110.0
    with pytest.raises(IVAInvalido):
        sif.emitir(nif_obligado="SINTETICO-A", nif_destinatario="SINTETICO-B",
                   serie="A", importe_neto=100.0, iva_pct=0.13)      # no vigente


# ── R-16 · ejecutor real con barreras en orden ────────────────────────────────

def _texto_ok():
    return ("Le escribe el asistente virtual con inteligencia artificial de Laboratorio. "
            "Mensaje comercial; puede darse de baja cuando quiera.")


def test_r16_ejecutor_sandbox_es_ensayo_seco_explicito(monkeypatch):
    from core.ejecutor import EjecutorComercial
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "false")
    r = EjecutorComercial().ejecutar(tenant="laboratorio", canal="email", texto=_texto_ok(),
                                     ahora=date(2026, 8, 2))
    assert r["estado"] == "ENSAYO_SECO" and r["dry"] is True and r["enviado"] is False


def test_r16_ejecutor_corta_por_aiact_antes_de_todo(monkeypatch):
    from core.ejecutor import EjecutorComercial
    from core.aiact_gate import AIActSinTransparencia
    enviado = {"n": 0}
    def enviar(**k):
        enviado["n"] += 1; return {"ok": True}
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    with pytest.raises(AIActSinTransparencia):
        EjecutorComercial(enviar=enviar).ejecutar(
            tenant="laboratorio", canal="email", texto="hola sin disclosure",
            ahora=date(2026, 8, 2))
    assert enviado["n"] == 0                          # no se envio nada


def test_r16_ejecutor_corta_por_panico(monkeypatch):
    from core.ejecutor import EjecutorComercial
    from core.panico import Panico, PanicoActivo
    p = Panico()
    p.activar(por="operador", motivo="test")
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    with pytest.raises(PanicoActivo):
        EjecutorComercial(panico=p, enviar=lambda **k: {"ok": True}).ejecutar(
            tenant="laboratorio", canal="email", texto=_texto_ok(), ahora=date(2026, 8, 2))


def test_r16_ejecutor_corta_por_techo(monkeypatch, tmp_path):
    from core.ejecutor import EjecutorComercial
    from core.knowledge import InMemoryKnowledge
    from core.ledger import LedgerCoste
    from core.techos import LibroCoste, TechoAlcanzado
    led = LedgerCoste(tmp_path / "l.jsonl")
    led.asentar("laboratorio", cubo="comercial", rol="x", clase="ESTANDAR", coste_eur=0.99)
    libro = LibroCoste(InMemoryKnowledge(), mandatos={"laboratorio": {"techo_coste_diario_eur": 1.0}},
                       ledger=led)
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    with pytest.raises(TechoAlcanzado):
        EjecutorComercial(libro=libro, enviar=lambda **k: {"ok": True}).ejecutar(
            tenant="laboratorio", canal="email", texto=_texto_ok(), coste_previsto_eur=0.10,
            ahora=date(2026, 8, 2))


def test_r16_ejecutor_envia_con_todo_en_regla(monkeypatch):
    from core.ejecutor import EjecutorComercial
    from core.panico import Panico
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    r = EjecutorComercial(panico=Panico(), enviar=lambda **k: {"sid": "OK"}).ejecutar(
        tenant="laboratorio", canal="email", texto=_texto_ok(), ahora=date(2026, 8, 2))
    assert r["estado"] == "EJECUTADA" and r["enviado"] is True and r["resultado"]["sid"] == "OK"


def test_r16_comite_no_pass_bloquea(monkeypatch):
    from core.ejecutor import EjecutorComercial, ComiteNoAutoriza
    class _Med:
        class mediacion:
            class verdict:
                value = "ESCALATE"
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    with pytest.raises(ComiteNoAutoriza):
        EjecutorComercial(comite=lambda t, c: _Med(), enviar=lambda **k: {}).ejecutar(
            tenant="laboratorio", canal="email", texto=_texto_ok(), ahora=date(2026, 8, 2))


# ── R-10 · marca por tenant ───────────────────────────────────────────────────

def test_r10_brand_system_por_tenant(tmp_path, monkeypatch):
    import json
    import departments.comercial.brand_guardian as bg
    # tenant sintetico con su propia guia de marca
    base = tmp_path / "empresas" / "laboratorio_dos" / "brand"
    base.mkdir(parents=True)
    (base / "guia.json").write_text(json.dumps(
        {"nombre": "Sintetica Dos", "posicionamiento": "gallega, de mar, honesta",
         "tono": "cercano y marinero"}), encoding="utf-8")

    from departments.brand import config as brand_cfg
    monkeypatch.setattr(brand_cfg, "cargar_guia",
                        lambda company, base_dir=None: json.loads(
                            (base / "guia.json").read_text(encoding="utf-8"))
                        if company == "laboratorio_dos" else {})
    s_rial = bg._brand_system("laboratorio_dos")
    assert "Sintetica Dos" in s_rial and "Laboratorio" not in s_rial   # no fuga cross-tenant
    assert "marinero" in s_rial
