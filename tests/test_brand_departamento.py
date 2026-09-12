"""Tests del departamento Brand: config-driven, contrato por eventos, comité para campañas,
degradación elegante cuando OpenGravity está apagado (§6.4, §7.2)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import EventType, Event
from core.opengravity.committee import Committee
from core.opengravity.vote_history import VoteHistory
from core.opengravity.sealing import HashChain
from core.opengravity.department import OpenGravity
from departments.brand import config as brand_cfg
from departments.brand.brand_guardian import BrandGuardian
from departments.brand.brand_strategist import BrandStrategist
from departments.brand.asset_manager import AssetManager
from departments.brand.director import DirectorBrand

CUERPO_OK = (
    "Hola, somos Laboratorio KAIZEN, un obrador familiar con más de un siglo de historia "
    "en Cieza. Elaboramos repostería artesanal con recetas centenarias y nos encantaría que "
    "la conocierais. Si os encaja, podemos enviaros una pequeña muestra sin compromiso para "
    "que la probéis con calma. Un saludo, Equipo del Laboratorio — Laboratorio KAIZEN")


def _fake_chat(verdict="PASS"):
    def chat(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
        if "Chair" in system:
            return "el comité valida"
        f = [] if verdict == "PASS" else [{"severity": "block", "text": "x"}]
        return json.dumps({"verdict": verdict, "confidence": 0.9, "risk_level": "low",
                           "findings": f, "rationale": "encaja"})
    return chat


# ── Config-driven ─────────────────────────────────────────────────────────────
def test_config_laboratorio_se_carga():
    assert brand_cfg.cargar_guia("laboratorio").get("posicionamiento")
    assert "barato" in brand_cfg.palabras_prohibidas("laboratorio")
    assert brand_cfg.cargar_firma("laboratorio").get("remitente_nombre") == "Equipo del Laboratorio"


def test_asset_manager_vigente():
    am = AssetManager("laboratorio")
    v = am.vigente()
    assert v["paleta"] and v["version"]


def test_guardian_detecta_palabra_prohibida():
    g = BrandGuardian("laboratorio", semantic_evaluator=None)
    r = g.revisar("Oferta", "Te ofrecemos el producto más barato del mercado. " * 6)
    assert not r.aprobado
    assert any("barato" in p for p in r.problemas)


def test_guardian_aprueba_email_limpio():
    g = BrandGuardian("laboratorio", semantic_evaluator=None)
    r = g.revisar("Repostería artesanal de Cieza con un siglo de historia", CUERPO_OK)
    assert r.aprobado, r.problemas


def test_guardian_exige_firma():
    g = BrandGuardian("laboratorio", semantic_evaluator=None)
    cuerpo = ("Hola, somos un obrador con historia y recetas centenarias y nos encantaría "
              "que probaseis nuestros productos artesanales sin ningún compromiso por vuestra "
              "parte en absoluto, muchas gracias por vuestro tiempo y atención prestada hoy.")
    r = g.revisar("Asunto válido", cuerpo)
    assert not r.aprobado
    assert any("Equipo del Laboratorio" in p for p in r.problemas)


# ── Contrato + comité para campañas (§6.4) ────────────────────────────────────
def _wire(bus):
    tmp = Path(tempfile.mkdtemp())
    OpenGravity(bus, committee=Committee(chat=_fake_chat()), vote_history=VoteHistory(base_dir=tmp),
                chain=HashChain(base_dir=tmp), contexto_loader=lambda c: "Repostería.")
    return DirectorBrand(bus, "laboratorio", guardian=BrandGuardian("laboratorio", semantic_evaluator=None))


def test_campana_levanta_comite():
    bus = InMemoryBus()
    director = _wire(bus)
    res = director.revisar(asunto="Repostería artesanal de Cieza", cuerpo=CUERPO_OK,
                           artifact_type="campana", usar_llm=False)
    assert res["comite"] is not None
    assert res["comite"]["verdict"] == "PASS"
    assert not res["degradado"]


def test_contrato_por_eventos():
    bus = InMemoryBus()
    completed = []
    bus.subscribe(completed.append, types=[EventType.BRAND_REVIEW_COMPLETED])
    _wire(bus)
    bus.publish(Event(EventType.BRAND_REVIEW_REQUESTED, source="comercial",
                      payload={"decision_id": "d1", "asunto": "Repostería de Cieza",
                               "cuerpo": CUERPO_OK, "artifact_type": "campana", "usar_llm": False},
                      company="laboratorio"))
    assert len(completed) == 1 and completed[0].payload["aprobado"]


def test_degradacion_si_opengravity_apagado():
    # Brand sin OpenGravity suscrito → la campaña sale con bandera de auditoría (§7.2).
    bus = InMemoryBus()
    director = DirectorBrand(bus, "laboratorio", guardian=BrandGuardian("laboratorio", semantic_evaluator=None))
    res = director.revisar(asunto="Repostería de Cieza", cuerpo=CUERPO_OK,
                           artifact_type="campana", usar_llm=False)
    assert res["degradado"] and res["degraded_reason"] == "consumer_off"
    assert res["comite"] is None


def test_cube_started_al_arrancar():
    bus = InMemoryBus()
    started = []
    bus.subscribe(started.append, types=[EventType.CUBE_STARTED])
    DirectorBrand(bus, "laboratorio", guardian=BrandGuardian("laboratorio", semantic_evaluator=None))
    assert any(e.payload.get("cube") == "brand" for e in started)
