# -*- coding: utf-8 -*-
"""Herramientas reales del cubo Brand para el director plenipotenciario (Fase 4).

Wireadas contra el codigo real de `departments/brand/` (verificado leyendo cada
fichero, no el mapa de auditoria a ciegas):

- LECTURA: todas las operaciones de solo lectura del cubo, generosamente —
  validador, analizador de periodo, los tres sub-agentes consultivos
  (Guardian/Strategist/VoiceAuditor) y las lecturas de estado (directrices,
  assets, posicionamiento/tono/valores, contexto de marca).
- REVERSIBLE: `director_revisar` — el veredicto consultivo del DirectorBrand
  (no persiste nada irreversible; NO dispara el comite salvo que ya haya un
  consumidor OpenGravity suscrito al bus real, que aqui es efimero).
- IRREVERSIBLE-INTERNA: `transicionar_directriz` — transicion de una maquina
  de estados que ya valida las transiciones permitidas (ARCHIVADA inmutable);
  se propone via [PROPUESTA] y solo se dispara al aprobar. `por` NO es un
  Argumento() que el LLM pueda rellenar: `CuboBrand.transicionar_directriz`
  lo acepta pero ni lo valida (no exige un valor concreto, a diferencia de
  aprobar_campana/definir_umbral) ni lo persiste en la directriz devuelta —
  aun asi, el wrapper lo fuerza en SERVIDOR a "operador" (patron
  legal.py::_fn_cumplir_obligacion), nunca un valor libre del LLM.

SALTADA a proposito: `alta_directriz` — `CuboBrand.alta_directriz` hace un
UPSERT via `k.add()` que sobrescribe en silencio si el id ya existe (mismo
patron de riesgo (d) del auditor: un director podria pisar una directriz
existente sin darse cuenta). No hay forma de exigir aqui una comprobacion de
unicidad sin inventar semantica nueva sobre el metodo real, asi que se deja
fuera de Fase 4 (sigue disponible por otras vias del sistema).
"""
from __future__ import annotations

import json

from core.bus import InMemoryBus
from departments.brand import config as brand_cfg
from departments.brand.asset_manager import AssetManager
from departments.brand.brand_guardian import BrandGuardian
from departments.brand.brand_strategist import BrandStrategist
from departments.brand.cubo_serie_d import CuboBrand
from departments.brand.director import DirectorBrand
from departments.brand.voice_auditor import VoiceAuditor
from panel_mando.herramientas.base import Argumento, ToolSpec


def _cubo(k, tenant, bitacora):
    return CuboBrand(k, tenant, bitacora=bitacora)


# ── LECTURA: validador y analizador ──────────────────────────────────────────

def _fn_validar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return _cubo(k, tenant, bitacora).validar(kwargs["texto"])


def _fn_analizar_periodo(*, k, tenant, bitacora=None, **kwargs) -> dict:
    veredictos = json.loads(kwargs["veredictos"])
    extra = {}
    if "umbral_no_apto" in kwargs:
        extra["umbral_no_apto"] = kwargs["umbral_no_apto"]
    return _cubo(k, tenant, bitacora).analizar_periodo(veredictos, **extra)


# ── LECTURA: lecturas directas de directrices ────────────────────────────────

def _fn_directrices_activas(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"directrices": _cubo(k, tenant, bitacora).directrices_activas()}


def _fn_version_directrices(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"version_directrices": _cubo(k, tenant, bitacora).version_directrices()}


# ── LECTURA: identidad visual (AssetManager) ─────────────────────────────────

def _fn_assets_vigente(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return AssetManager(tenant).vigente()


def _fn_assets_paleta(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return AssetManager(tenant).paleta()


def _fn_assets_logo(*, k, tenant, bitacora=None, **kwargs) -> dict:
    logo_id = kwargs.get("logo_id", "logo_principal")
    return {"logo": AssetManager(tenant).logo(logo_id)}


# ── LECTURA: posicionamiento/tono/valores/duda interpretativa (Strategist) ──

def _fn_strategist_posicionamiento(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"posicionamiento": BrandStrategist(tenant).posicionamiento()}


def _fn_strategist_tono(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return BrandStrategist(tenant).tono()


def _fn_strategist_valores(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"valores": BrandStrategist(tenant).valores()}


def _fn_strategist_encaja(*, k, tenant, bitacora=None, **kwargs) -> dict:
    usar_llm = kwargs.get("usar_llm", True)
    return BrandStrategist(tenant).encaja(kwargs["propuesta"], usar_llm=usar_llm)


# ── LECTURA: revision deterministica+semantica de un artefacto (Guardian) ──

def _fn_guardian_revisar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    lead_raw = kwargs.get("lead")
    lead = json.loads(lead_raw) if lead_raw else None
    usar_llm = kwargs.get("usar_llm", True)
    exigir_firma = kwargs.get("exigir_firma", True)
    r = BrandGuardian(tenant).revisar(kwargs["asunto"], kwargs["cuerpo"], lead=lead,
                                      usar_llm=usar_llm, exigir_firma=exigir_firma)
    return {"aprobado": r.aprobado, "problemas": r.problemas,
            "sugerencias": r.sugerencias, "detalle_llm": r.detalle_llm}


# ── LECTURA: auditoria de tono de una llamada cerrada (VoiceAuditor) ────────

def _fn_voice_auditar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    lead_raw = kwargs.get("lead")
    lead = json.loads(lead_raw) if lead_raw else None
    d = VoiceAuditor(tenant).auditar(kwargs["texto_agente"], lead=lead)
    return {"ok": d.ok, "problemas": d.problemas,
            "sugerencias": d.sugerencias, "dictamen_llm": d.dictamen_llm}


# ── LECTURA: contexto de marca compacto (config declarativa) ────────────────

def _fn_contexto_marca(*, k, tenant, bitacora=None, **kwargs) -> dict:
    return {"contexto_marca": brand_cfg.contexto_marca(tenant)}


# ── REVERSIBLE: veredicto consultivo del director (orquesta los sub-agentes) ─

def _fn_director_revisar(*, k, tenant, bitacora=None, **kwargs) -> dict:
    lead_raw = kwargs.get("lead")
    lead = json.loads(lead_raw) if lead_raw else None
    bus = InMemoryBus()
    director = DirectorBrand(bus, tenant)
    return director.revisar(
        asunto=kwargs["asunto"], cuerpo=kwargs["cuerpo"],
        artifact_type=kwargs.get("artifact_type"), lead=lead,
        correlation_id=kwargs.get("correlation_id"),
        usar_llm=kwargs.get("usar_llm", True))


# ── IRREVERSIBLE-INTERNA: transicion de estado de una directriz existente ──

def _fn_transicionar_directriz(*, k, tenant, bitacora=None, **kwargs) -> dict:
    """Fuerza el actor en SERVIDOR (patron legal.py::_fn_cumplir_obligacion):
    'por' NUNCA viene del LLM, siempre "operador"."""
    return _cubo(k, tenant, bitacora).transicionar_directriz(
        kwargs["d_id"], kwargs["a"], por="operador", motivo=kwargs.get("motivo", ""))


HERRAMIENTAS: dict[str, ToolSpec] = {
    "validar": ToolSpec(
        nombre="validar", clase="LECTURA",
        descripcion="Valida un texto contra las directrices de marca ACTIVAS del tenant "
                    "y devuelve el veredicto categorizado con razones itemizadas.",
        argumentos=(Argumento("texto", "str", "texto a validar contra las directrices"),),
        fn=_fn_validar),

    "analizar_periodo": ToolSpec(
        nombre="analizar_periodo", clase="LECTURA",
        descripcion="Analiza una lista de veredictos de validaciones ya emitidas y calcula "
                    "la tasa de NO_APTO, alertando si supera el umbral.",
        argumentos=(
            Argumento("veredictos", "str",
                      "lista de veredictos como JSON, p.ej. "
                      '[{"veredicto": "APTO"}, {"veredicto": "NO_APTO_POR_MARCA"}]'),
            Argumento("umbral_no_apto", "float",
                      "umbral de tasa de NO_APTO para disparar la alerta (por defecto 0.5)",
                      obligatorio=False),
        ),
        fn=_fn_analizar_periodo),

    "directrices_activas": ToolSpec(
        nombre="directrices_activas", clase="LECTURA",
        descripcion="Lista las directrices de marca en estado ACTIVA del tenant.",
        argumentos=(),
        fn=_fn_directrices_activas),

    "version_directrices": ToolSpec(
        nombre="version_directrices", clase="LECTURA",
        descripcion="Devuelve la huella de version de las directrices activas (id:version "
                    "por directriz), util para saber si algo cambio.",
        argumentos=(),
        fn=_fn_version_directrices),

    "assets_vigente": ToolSpec(
        nombre="assets_vigente", clase="LECTURA",
        descripcion="Version vigente del set de identidad visual del tenant (paleta, "
                    "tipografias, numero de logos y plantillas).",
        argumentos=(),
        fn=_fn_assets_vigente),

    "assets_paleta": ToolSpec(
        nombre="assets_paleta", clase="LECTURA",
        descripcion="Paleta de colores vigente del tenant.",
        argumentos=(),
        fn=_fn_assets_paleta),

    "assets_logo": ToolSpec(
        nombre="assets_logo", clase="LECTURA",
        descripcion="Metadatos de un logo del tenant por id (por defecto 'logo_principal').",
        argumentos=(
            Argumento("logo_id", "str", "id del logo a consultar", obligatorio=False),
        ),
        fn=_fn_assets_logo),

    "strategist_posicionamiento": ToolSpec(
        nombre="strategist_posicionamiento", clase="LECTURA",
        descripcion="Posicionamiento de marca declarado en la guia del tenant.",
        argumentos=(),
        fn=_fn_strategist_posicionamiento),

    "strategist_tono": ToolSpec(
        nombre="strategist_tono", clase="LECTURA",
        descripcion="Tono de voz declarado en la guia de marca del tenant.",
        argumentos=(),
        fn=_fn_strategist_tono),

    "strategist_valores": ToolSpec(
        nombre="strategist_valores", clase="LECTURA",
        descripcion="Valores de marca declarados en la guia del tenant.",
        argumentos=(),
        fn=_fn_strategist_valores),

    "strategist_encaja": ToolSpec(
        nombre="strategist_encaja", clase="LECTURA",
        descripcion="Resuelve una duda interpretativa: si una propuesta encaja con la "
                    "guia de marca del tenant (heuristica de veto; con LLM opcional).",
        argumentos=(
            Argumento("propuesta", "str", "texto de la propuesta a evaluar"),
            Argumento("usar_llm", "bool",
                      "si se razona con LLM contra la guia completa (por defecto true)",
                      obligatorio=False),
        ),
        fn=_fn_strategist_encaja),

    "guardian_revisar": ToolSpec(
        nombre="guardian_revisar", clase="LECTURA",
        descripcion="Revisa un artefacto (asunto+cuerpo) contra las reglas deterministas "
                    "de marca del tenant (longitud, placeholders, palabras/argumentos "
                    "prohibidos, firma) y, opcionalmente, evaluacion semantica.",
        argumentos=(
            Argumento("asunto", "str", "asunto del artefacto"),
            Argumento("cuerpo", "str", "cuerpo del artefacto"),
            Argumento("lead", "str",
                      "datos del lead como JSON, p.ej. {\"nombre\": \"Ana\"} (opcional)",
                      obligatorio=False),
            Argumento("usar_llm", "bool",
                      "si se evalua semanticamente con LLM (por defecto true)",
                      obligatorio=False),
            Argumento("exigir_firma", "bool",
                      "si se exige la firma del remitente al cierre (por defecto true)",
                      obligatorio=False),
        ),
        fn=_fn_guardian_revisar),

    "voice_auditar": ToolSpec(
        nombre="voice_auditar", clase="LECTURA",
        descripcion="Audita los turnos del agente en una llamada ya cerrada contra la "
                    "guia de marca del tenant (tono, personalizacion, presion indebida).",
        argumentos=(
            Argumento("texto_agente", "str", "transcript de los turnos del agente"),
            Argumento("lead", "str",
                      "datos del lead como JSON, p.ej. {\"nombre\": \"Ana\"} (opcional)",
                      obligatorio=False),
        ),
        fn=_fn_voice_auditar),

    "contexto_marca": ToolSpec(
        nombre="contexto_marca", clase="LECTURA",
        descripcion="Texto compacto de la guia de marca del tenant (posicionamiento, "
                    "valores, tono, que no decir), listo para inyectar a un LLM.",
        argumentos=(),
        fn=_fn_contexto_marca),

    "director_revisar": ToolSpec(
        nombre="director_revisar", clase="REVERSIBLE",
        descripcion="Veredicto consultivo completo del Director Brand sobre un artefacto: "
                    "aplica el Brand Guardian y, si es una campana aprobada y hay comite "
                    "OpenGravity real disponible, incorpora su veredicto (si no, degrada "
                    "con bandera de auditoria). No persiste nada irreversible.",
        argumentos=(
            Argumento("asunto", "str", "asunto del artefacto"),
            Argumento("cuerpo", "str", "cuerpo del artefacto"),
            Argumento("artifact_type", "str",
                      "tipo de artefacto (p.ej. 'campana' activa el comite preventivo)",
                      obligatorio=False),
            Argumento("lead", "str",
                      "datos del lead como JSON, p.ej. {\"nombre\": \"Ana\"} (opcional)",
                      obligatorio=False),
            Argumento("correlation_id", "str",
                      "id de correlacion para trazar la revision (opcional)",
                      obligatorio=False),
            Argumento("usar_llm", "bool",
                      "si el Guardian evalua semanticamente con LLM (por defecto true)",
                      obligatorio=False),
        ),
        fn=_fn_director_revisar),

    "transicionar_directriz": ToolSpec(
        nombre="transicionar_directriz", clase="IRREVERSIBLE-INTERNA",
        descripcion="Transiciona una directriz de marca existente a un nuevo estado segun "
                    "la maquina de estados ya validada (BORRADOR/ACTIVA/SUSPENDIDA/"
                    "DEPRECADA/ARCHIVADA/CANCELADA; ARCHIVADA es inmutable). El 'por' lo "
                    "fuerza el servidor a 'operador', nunca un valor libre del LLM.",
        argumentos=(
            Argumento("d_id", "str", "id de la directriz a transicionar"),
            Argumento("a", "str", "estado destino"),
            Argumento("motivo", "str", "motivo de la transicion", obligatorio=False),
        ),
        fn=_fn_transicionar_directriz),
}

__all__ = ["HERRAMIENTAS"]
