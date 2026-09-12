"""Tests del motor de comité OpenGravity: verdict, mediator, selector, committee.

Cubren los tres fixes de §4.4 (temperature 0, votingRuns 3, catálogo de negocio) y la
validación endurecida de §6.2. Sin red: el `chat` es un doble inyectado.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.opengravity.verdict import (
    parse_and_validate, invalid_verdict, VerdictValidationError, Verdict, RiskLevel,
)
from core.opengravity.mediator import mediar, EscalationReason
from core.opengravity.role_selector import componer, MAX_MIEMBROS
from core.opengravity.role_registry import ROLE_REGISTRY, roles_de_dominio, DOMINIOS
from core.opengravity.committee import Committee


# ── Verdict: validación endurecida (cierra el bug del risk_level vacío) ───────
def test_risk_level_vacio_rechazado():
    with pytest.raises(VerdictValidationError):
        parse_and_validate('{"verdict":"PASS","confidence":0.9,"risk_level":""}', "x")


def test_findings_obligatorio_si_no_pass():
    with pytest.raises(VerdictValidationError):
        parse_and_validate('{"verdict":"FAIL","confidence":0.9,"risk_level":"high","findings":[]}', "x")


def test_confidence_fuera_de_rango():
    with pytest.raises(VerdictValidationError):
        parse_and_validate('{"verdict":"PASS","confidence":2.0,"risk_level":"low"}', "x")


def test_verdict_fuera_de_enum():
    with pytest.raises(VerdictValidationError):
        parse_and_validate('{"verdict":"MAYBE","confidence":0.9,"risk_level":"low"}', "x")


def test_verdict_valido():
    v = parse_and_validate(
        '{"verdict":"PASS","confidence":0.8,"risk_level":"low","findings":[],"rationale":"ok"}', "r")
    assert v.verdict is Verdict.PASS and v.risk_level is RiskLevel.LOW and v.valido


def test_json_envuelto_en_texto():
    v = parse_and_validate('Aquí va: {"verdict":"PASS","confidence":0.7,"risk_level":"medium"} fin', "r")
    assert v.verdict is Verdict.PASS


# ── Mediator: consenso, confianza, escalado, voto inválido descartado ─────────
def _mv(rid, v, c=0.9, risk="low"):
    findings = [] if v == "PASS" else [__import__("core.opengravity.verdict", fromlist=["Finding"]).Finding("block", "x")]
    from core.opengravity.verdict import MemberVerdict, Verdict as V, RiskLevel as R
    return MemberVerdict(rid, V(v), c, R(risk), findings, "r")


def test_consenso_bajo_escala():
    m = mediar([_mv("a", "PASS"), _mv("b", "PASS"), _mv("c", "PASS"),
                _mv("d", "FAIL"), _mv("e", "FAIL")])
    assert m.consensus == pytest.approx(0.6)
    assert m.escalate and m.escalation_reason is EscalationReason.LOW_CONSENSUS


def test_confianza_baja_escala():
    m = mediar([_mv("a", "PASS", 0.4), _mv("b", "PASS", 0.4), _mv("c", "PASS", 0.4)])
    assert m.escalate and m.escalation_reason is EscalationReason.LOW_CONFIDENCE


def test_voto_invalido_descartado_no_cuenta():
    m = mediar([_mv("a", "PASS"), _mv("b", "PASS"), invalid_verdict("c", "risk vacío")])
    assert m.n_validos == 2 and m.n_invalidos == 1
    assert m.consensus == pytest.approx(1.0) and m.verdict is Verdict.PASS


def test_empate_pide_mediador_llm():
    m = mediar([_mv("a", "PASS"), _mv("b", "FAIL")])
    assert m.needs_mediator_llm


def test_todos_invalidos_escala_validation_failed():
    m = mediar([invalid_verdict("a", "x"), invalid_verdict("b", "y")])
    assert m.escalate and m.escalation_reason is EscalationReason.VALIDATION_FAILED


def test_pesos_ponderan_consenso():
    # b,c (PASS, peso 1.0) vs a (FAIL, peso 1.5) → PASS=2.0 gana sobre FAIL=1.5 en el tally.
    m = mediar([_mv("a", "FAIL"), _mv("b", "PASS"), _mv("c", "PASS")],
               {"a": 1.5, "b": 1.0, "c": 1.0}, consensus_min=0.5)
    assert m.tally["PASS"] > m.tally["FAIL"]
    assert m.verdict is Verdict.PASS        # consenso 0.571 ≥ 0.5


# ── Selector: catálogo de negocio, tope 5, cruces, contrarian ─────────────────
def test_15_roles_negocio_mas_transversales():
    # 15 roles de negocio = 5 dominios × 3 (contrarian cuenta en Finanzas y es transversal).
    negocio = [r for r in ROLE_REGISTRY.values() if r.domain in DOMINIOS]
    assert len(negocio) == 15
    assert all(len(roles_de_dominio(d)) == 3 for d in DOMINIOS)
    # Transversales: chair, mediator_llm (+ contrarian, compartido con Finanzas).
    assert {"chair", "mediator_llm", "contrarian"} <= {
        r.role_id for r in ROLE_REGISTRY.values() if r.transversal}


def test_temperatura_cero_en_todos():
    assert all(r.temperature == 0.0 for r in ROLE_REGISTRY.values())


def test_contrarian_en_comercial():
    comp = componer("propuesta comercial con descuento y argumentario", domain="comercial")
    assert "contrarian" in {r.role_id for r in comp.miembros}


def test_tope_cinco_miembros():
    comp = componer("contrato con cláusula RGPD, propuesta con descuento, forecast de margen, "
                    "campaña de lanzamiento, entrega y proveedor")
    assert len(comp.miembros) <= MAX_MIEMBROS


def test_cruce_de_dominios_suma_roles():
    comp = componer("propuesta comercial con cláusula de confidencialidad y RGPD",
                    domain="comercial")
    ids = {r.role_id for r in comp.miembros}
    assert any(r.domain == "legal" for r in comp.miembros) or "legal" in comp.dominios_cruzados
    assert "deal_qualifier" in ids


# ── Committee: votingRuns y temperatura 0 ─────────────────────────────────────
def _fake_chat_factory(verdict_seq):
    it = iter(verdict_seq)
    temps_vistas = []

    def chat(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
        temps_vistas.append(temperature)
        if "Chair" in system:
            return "síntesis"
        if "Mediador" in system:
            return "PASS"
        v = next(it, "PASS")
        f = [] if v == "PASS" else [{"severity": "block", "text": "x"}]
        return json.dumps({"verdict": v, "confidence": 0.9, "risk_level": "low",
                           "findings": f, "rationale": "r"})
    chat.temps = temps_vistas
    return chat


def test_committee_corre_3_pasadas_por_miembro():
    chat = _fake_chat_factory(["PASS"] * 100)
    c = Committee(chat=chat)
    out = c.run(artifact="contrato con cláusula RGPD", company="x", voting_runs=3,
                contexto_empresa="ctx")
    # 3 miembros legales × 3 pasadas = 9 llamadas de miembro (+ chair)
    assert all(len(m.pasadas) == 3 for m in out.members)
    assert out.mediacion.verdict is Verdict.PASS


def test_committee_temperatura_cero():
    chat = _fake_chat_factory(["PASS"] * 100)
    c = Committee(chat=chat)
    c.run(artifact="contrato RGPD", company="x", voting_runs=1, contexto_empresa="ctx")
    # Todas las llamadas de miembro/chair pasan temperature=0 (ninguna None salvo, ya 0).
    assert all(t == 0.0 for t in chat.temps)


def test_committee_reintento_unico_y_descarte():
    # Primera pasada inválida (risk vacío), reintento también inválido → voto descartado.
    bad = json.dumps({"verdict": "PASS", "confidence": 0.9, "risk_level": ""})

    def chat(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
        if "Chair" in system:
            return "s"
        return bad
    c = Committee(chat=chat)
    out = c.run(artifact="contrato RGPD", company="x", voting_runs=1, contexto_empresa="ctx")
    assert all(not m.consolidado.valido for m in out.members)
    assert out.mediacion.escalation_reason is EscalationReason.VALIDATION_FAILED


def test_consolidacion_por_mayoria_de_pasadas():
    # Un miembro: PASS, PASS, FAIL → mayoría PASS (detecta la alucinación de la 3ª pasada).
    chat = _fake_chat_factory(["PASS", "PASS", "FAIL"])
    c = Committee(chat=chat)
    out = c.run(artifact="contrato RGPD", company="x", domain="legal", voting_runs=3,
                contexto_empresa="ctx")
    # El primer miembro consolida a PASS pese a la pasada FAIL.
    assert out.members[0].consolidado.verdict is Verdict.PASS
