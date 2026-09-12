"""Tests del contrato sobre el bus: clasificador, candado de umbrales, sellado, departamento.

Cubren §6.3 (contrato, candado), §6.5 (preventivo/forense) y §6.1 (comunicación por eventos).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.bus import InMemoryBus
from core.events import EventType, Event, Criticality
from core.opengravity.classifier import (
    clasificar, Modo, evaluar_ajuste_catalogo,
)
from core.opengravity.thresholds import (
    Umbrales, resolver_umbrales, LogInmutableUmbrales,
)
from core.opengravity.sealing import HashChain, hash_canonico, GENESIS
from core.opengravity.committee import Committee
from core.opengravity.vote_history import VoteHistory
from core.opengravity.department import OpenGravity, solicitar_revision


def _fake_chat(verdict="PASS", conf=0.92):
    def chat(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
        if "Chair" in system:
            return "síntesis del comité"
        f = [] if verdict == "PASS" else [{"severity": "block", "text": "x"}]
        return json.dumps({"verdict": verdict, "confidence": conf, "risk_level": "low",
                           "findings": f, "rationale": "r"})
    return chat


# ── Clasificador preventivo/forense (§6.5) ────────────────────────────────────
def test_email_frio_es_forense():
    c = clasificar(artifact_type="email_frio", artifact_text="hola, te escribo...")
    assert c.modo is Modo.FORENSE and not c.bloquea


def test_contrato_firmable_es_preventivo():
    c = clasificar(artifact_type="contrato_firmable", artifact_text="contrato de servicios")
    assert c.modo is Modo.PREVENTIVO and c.bloquea


def test_regla_dura_R1_compromiso_tercero():
    # Aunque el tipo sea forense, comprometer cifra/firma de tercero fuerza preventivo.
    c = clasificar(artifact_type="email_frio",
                   artifact_text="te confirmo el importe de 3.000 EUR, total a pagar el día 30")
    assert c.modo is Modo.PREVENTIVO and c.regla_dura == "R1"


def test_regla_dura_R2_sector_estricto():
    c = clasificar(artifact_type="email_frio", artifact_text="campaña", domain="finanzas",
                   sector="sanitario")
    assert c.modo is Modo.PREVENTIVO and c.regla_dura == "R2"


def test_R2_se_levanta_con_override_firmado():
    c = clasificar(artifact_type="email_frio", artifact_text="mensaje", domain="finanzas",
                   sector="sanitario", override_firmado=True)
    assert c.modo is Modo.FORENSE


def test_ajuste_catalogo_promueve_por_fails():
    s = evaluar_ajuste_catalogo("email_frio", Modo.FORENSE, fails_riesgo_alto_30d=3)
    assert s and s.a is Modo.PREVENTIVO and s.requiere_adr


def test_ajuste_catalogo_degrada_por_pass():
    s = evaluar_ajuste_catalogo("contrato_firmable", Modo.PREVENTIVO,
                                todos_pass_trimestre=True, confianza_media_trimestre=0.97)
    assert s and s.a is Modo.FORENSE


# ── Candado de umbrales (§6.3) ────────────────────────────────────────────────
def test_subagente_no_puede_relajar():
    floor = Umbrales(0.66, 0.70)
    r = resolver_umbrales(floor, Umbrales(0.50, 0.50))   # intenta relajar
    assert r.relajacion_bloqueada
    assert r.efectivos.consensus_min == 0.66 and r.efectivos.confidence_min == 0.70


def test_subagente_puede_endurecer():
    floor = Umbrales(0.66, 0.70)
    r = resolver_umbrales(floor, Umbrales(0.80, 0.85))   # endurece
    assert not r.relajacion_bloqueada
    assert r.efectivos.consensus_min == 0.80


def test_operador_baja_umbral_queda_en_log_inmutable():
    tmp = Path(tempfile.mkdtemp())
    log = LogInmutableUmbrales(base_dir=tmp)
    log.registrar_bajada("laboratorio", "consensus_min", 0.66, 0.60, "IVAN-FIRMA", "piloto")
    log.registrar_bajada("laboratorio", "confidence_min", 0.70, 0.65, "IVAN-FIRMA")
    assert log.verificar()                       # cadena íntegra
    assert len(log.historial("laboratorio")) == 2


def test_log_detecta_manipulacion():
    tmp = Path(tempfile.mkdtemp())
    log = LogInmutableUmbrales(base_dir=tmp)
    log.registrar_bajada("laboratorio", "consensus_min", 0.66, 0.60, "FIRMA")
    # Manipula el fichero a mano.
    p = tmp / "umbral_log.jsonl"
    contenido = p.read_text(encoding="utf-8").replace("0.6", "0.1")
    p.write_text(contenido, encoding="utf-8")
    assert not log.verificar()                   # tamper-evidence


def test_no_se_puede_bajar_de_suelo_absoluto():
    tmp = Path(tempfile.mkdtemp())
    log = LogInmutableUmbrales(base_dir=tmp)
    with pytest.raises(ValueError):
        log.registrar_bajada("laboratorio", "consensus_min", 0.66, 0.30, "FIRMA")


def test_bajar_umbral_exige_firma():
    tmp = Path(tempfile.mkdtemp())
    log = LogInmutableUmbrales(base_dir=tmp)
    with pytest.raises(ValueError):
        log.registrar_bajada("laboratorio", "consensus_min", 0.66, 0.60, "")


# ── Sellado y cadena (§6.3) ───────────────────────────────────────────────────
def test_hash_canonico_reproducible():
    a = hash_canonico({"b": 1, "a": 2})
    b = hash_canonico({"a": 2, "b": 1})
    assert a == b                                # orden de claves no importa


def test_cadena_encadena_y_verifica():
    tmp = Path(tempfile.mkdtemp())
    ch = HashChain(base_dir=tmp)
    p1 = {"decision": "uno"}
    t1 = ch.sellar("laboratorio", p1)
    assert t1["chain_prev_hash"] == GENESIS
    p2 = {"decision": "dos"}
    t2 = ch.sellar("laboratorio", p2)
    assert t2["chain_prev_hash"] == t1["hash"]   # encadenado
    eslabones = [{"payload": p1, **t1}, {"payload": p2, **t2}]
    assert ch.verificar("laboratorio", eslabones)


def test_cadena_aislada_por_empresa():
    tmp = Path(tempfile.mkdtemp())
    ch = HashChain(base_dir=tmp)
    ch.sellar("laboratorio", {"x": 1})
    t = ch.sellar("otra", {"y": 1})
    assert t["chain_prev_hash"] == GENESIS       # cada empresa arranca su cadena


# ── Departamento OpenGravity sobre el bus (§6.1, §6.3) ────────────────────────
def _og(bus, verdict="PASS", conf=0.92):
    tmp = Path(tempfile.mkdtemp())
    return OpenGravity(bus, committee=Committee(chat=_fake_chat(verdict, conf)),
                       vote_history=VoteHistory(base_dir=tmp), chain=HashChain(base_dir=tmp),
                       contexto_loader=lambda c: "Repostería artesanal.")


def test_review_completed_se_emite():
    bus = InMemoryBus()
    completed = []
    bus.subscribe(completed.append, types=[EventType.OPENGRAVITY_REVIEW_COMPLETED])
    og = _og(bus)
    solicitar_revision(bus, artifact="email frío a cafetería", company="laboratorio",
                       mode="forensic", domain="brand", artifact_type="email_frio")
    assert len(completed) == 1
    assert completed[0].payload["verdict"] == "PASS"
    assert "trace" in completed[0].payload


def test_preventivo_bloquea_y_no_ejecuta_si_escala():
    bus = InMemoryBus()
    escal = []
    bus.subscribe(escal.append, types=[EventType.OPENGRAVITY_ESCALATION_REQUESTED])
    og = _og(bus, verdict="FAIL")
    ver = og.revisar(artifact="propuesta vinculante, total a pagar 5000 EUR, firma",
                     company="laboratorio", domain="comercial")
    assert ver.bloquea                      # R1 forzó preventivo
    assert not ver.ejecutable               # FAIL → no ejecuta
    assert len(escal) >= 0                   # FAIL con consenso alto no escala necesariamente


def test_forense_siempre_ejecutable():
    bus = InMemoryBus()
    og = _og(bus, verdict="FAIL")
    ver = og.revisar(artifact="email frío individual", company="laboratorio",
                     mode="forensic", domain="brand", artifact_type="email_frio")
    assert ver.mode == "forensic" and ver.ejecutable      # forense ejecuta de inmediato


def test_relajacion_bloqueada_se_reporta():
    bus = InMemoryBus()
    og = _og(bus)
    ver = og.revisar(artifact="contrato RGPD", company="laboratorio", domain="legal",
                     thresholds={"consensus_min": 0.10, "confidence_min": 0.10})
    assert ver.relajacion_bloqueada
