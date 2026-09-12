"""Brand Guardian — vela por la consistencia de tono, valores y posicionamiento del
tenant activo en TODA comunicación saliente (§2.5 / §7.4 del v0.2).

Doble capa:
  1. Reglas deterministas (estructura, longitud, placeholders, palabras prohibidas, firma).
  2. Evaluación semántica por LLM contra el manual de marca + CONTEXTO_NEGOCIO de la empresa.

Cada revisión devuelve un `BrandReview` con `aprobado`, lista de `problemas` (bloqueantes)
y `sugerencias` (consejos no bloqueantes). El SDR usa esto como gate antes de encolar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import claude_client as ai
import diario_ops as diario
from core.argumentario import patrones_argumentos_prohibidos

ROOT = Path(__file__).resolve().parent.parent.parent
# Suelo comun de palabras que dañan un posicionamiento artesanal (§2.5 v0.2). La
# lista POR TENANT vive en empresas/<t>/brand/palabras_prohibidas.json y se SUMA.
PALABRAS_PROHIBIDAS = (
    "barato", "barata", "barat",         # "lo barato sale caro" — competimos en valor
    "industrial", "fábrica", "fabrica",  # estamos en obrador, no en línea de producción
    "low-cost", "low cost", "lowcost",
    "promoción", "promocion", "oferta especial",  # tono de descuento, no de marca
    "best price", "mejor precio",
    "lorem", "ipsum",                    # placeholder accidental
)
PLACEHOLDERS_MAYUSCULAS = re.compile(r"\b(TODO|INSERTAR|XXX|FIXME|PENDIENTE)\b")
PLACEHOLDERS_CORCHETES  = re.compile(r"\[[A-Z_]{2,}\]")    # [CIUDAD], [INSERTAR_X]…
MARKDOWN_PROHIBIDO = re.compile(r"(?m)^(#+\s|---+\s*$|\*\*?|^\s*[-*]\s)")


@dataclass
class BrandReview:
    aprobado: bool
    problemas: list[str] = field(default_factory=list)        # bloqueantes
    sugerencias: list[str] = field(default_factory=list)      # no bloqueantes
    detalle_llm: str = ""                                     # dictamen del LLM completo


class BrandGuardian:
    """Revisor de marca. `semantic_evaluator` es inyectable para tests; por defecto usa
    Claude Haiku con el contexto de la empresa cargado del Diario."""

    def __init__(self, empresa: str = "laboratorio",
                 semantic_evaluator=None,
                 contexto_negocio: str | None = None,
                 chat=None) -> None:
        self.empresa = empresa
        self.contexto_negocio = (contexto_negocio
                                 if contexto_negocio is not None
                                 else diario.read("CONTEXTO_NEGOCIO", empresa))
        self.semantic = semantic_evaluator or _llm_semantic_evaluator
        self.chat = chat or ai.chat                # para análisis conversacional post-call
        # Firma esperada (extraída del CONTEXTO_NEGOCIO de la empresa).
        identidad = diario._extraer_identidad_remitente(self.contexto_negocio)
        self.remitente_nombre = identidad.get("nombre", "")
        self.remitente_empresa = identidad.get("empresa", "")
        # Argumentos prohibidos declarativos por empresa
        # (empresas/<empresa>/argumentario.json). Se SUMAN a PALABRAS_PROHIBIDAS.
        self.argumentos_prohibidos = patrones_argumentos_prohibidos(empresa)

    # ── Revisión completa ─────────────────────────────────────────────────────
    def revisar(self, asunto: str, cuerpo: str, *, lead: dict | None = None,
                usar_llm: bool = True) -> BrandReview:
        problemas: list[str] = []
        sugerencias: list[str] = []

        # ── Reglas duras ──────────────────────────────────────────────────────
        if not asunto.strip():
            problemas.append("Asunto vacío.")
        elif len(asunto) > 80:
            problemas.append(f"Asunto demasiado largo ({len(asunto)} caracteres, máx 80).")

        palabras = cuerpo.split()
        if len(palabras) < 50:
            problemas.append(f"Cuerpo demasiado corto ({len(palabras)} palabras, mín 50).")
        elif len(palabras) > 200:
            sugerencias.append(f"Cuerpo largo ({len(palabras)} palabras); el v0.2 §4 sugiere máx 150.")

        # Markdown / formato no permitido en email plano.
        if MARKDOWN_PROHIBIDO.search(cuerpo):
            problemas.append("Cuerpo contiene markdown (#, **, ---, listas con -). Email plano por §4.3.")

        # Placeholders olvidados (palabras MAYÚSCULAS o tokens entre corchetes).
        full = cuerpo + " " + asunto
        m = PLACEHOLDERS_MAYUSCULAS.search(full) or PLACEHOLDERS_CORCHETES.search(full)
        if m:
            problemas.append(f"Placeholder sin rellenar: '{m.group(0)}'.")

        # Palabras prohibidas (dañan posicionamiento artesanal).
        cuerpo_lower = cuerpo.lower()
        for p in PALABRAS_PROHIBIDAS:
            if p in cuerpo_lower:
                problemas.append(f"Palabra prohibida en el cuerpo: '{p}' (no cuadra con marca).")

        # Argumentos prohibidos del argumentario por empresa (estudios validados).
        for arg in self.argumentos_prohibidos:
            if arg["patron"] in cuerpo_lower:
                problemas.append(
                    f"Argumento prohibido [{arg['id']}]: '{arg['patron']}'. "
                    f"{arg['razon']}"
                )

        # Firma identificable: nombre + empresa.
        if self.remitente_nombre and self.remitente_nombre not in cuerpo:
            problemas.append(f"Falta el remitente '{self.remitente_nombre}' al cierre.")
        if self.remitente_empresa and self.remitente_empresa not in cuerpo:
            sugerencias.append(f"No aparece el nombre de la empresa '{self.remitente_empresa}'.")

        # ── Evaluación semántica por LLM ──────────────────────────────────────
        detalle_llm = ""
        if usar_llm and not problemas:    # solo gastamos LLM si las reglas duras pasan
            try:
                try:
                    veredicto = self.semantic(asunto, cuerpo, empresa=self.empresa,
                                              contexto_negocio=self.contexto_negocio, lead=lead)
                except TypeError:  # evaluadores inyectados antiguos sin `empresa`
                    veredicto = self.semantic(asunto, cuerpo,
                                              contexto_negocio=self.contexto_negocio, lead=lead)
            except Exception as e:
                sugerencias.append(f"Evaluación LLM falló: {e}")
            else:
                detalle_llm = veredicto.get("dictamen", "")
                if not veredicto.get("ok", True):
                    problemas.append(f"Brand Guardian (LLM): {veredicto.get('motivo', 'tono no encaja')}")

        return BrandReview(aprobado=not problemas, problemas=problemas,
                           sugerencias=sugerencias, detalle_llm=detalle_llm)

    # ── Análisis post-call: ¿el agente sonó a Iván o a IA genérica? ────────
    def analizar_tono_conversacional(self, texto_agente: str, *,
                                      lead: dict | None = None) -> "DictamenTono":
        """Evalúa SOLO los turnos del agente en una llamada (transcript ya cerrado).
        Devuelve `DictamenTono`. `self.chat` se inyecta en construcción para tests.
        """
        # Import perezoso para evitar dependencia circular en tests del propio módulo.
        from departments.comercial.sdr.voz_conversacional.analisis_calidad import DictamenTono
        if not texto_agente.strip():
            return DictamenTono(ok=False, problemas=["transcript del agente vacío"],
                                sugerencias=[], dictamen_llm="")
        lead_info = ""
        if lead:
            lead_info = (f"\nLead: {lead.get('nombre','?')} · "
                         f"tipo={lead.get('categoria_icp','?')} · "
                         f"ciudad={(lead.get('ubicacion') or {}).get('direccion','')}")
        user = (
            f"=== CONTEXTO DEL NEGOCIO ===\n{self.contexto_negocio[:1200]}\n\n"
            f"=== TURNOS DEL AGENTE EN LA LLAMADA ==={lead_info}\n{texto_agente}\n"
        )
        try:
            respuesta = self.chat(
                [{"role": "user", "content": user}],
                system=_tono_conversacional_system(self.empresa),   # R-TENANT: marca POR TENANT
                model="claude-sonnet-4-6",
                max_tokens=400,
                company=self.empresa,
            )
        except Exception as e:
            return DictamenTono(ok=False, problemas=[f"LLM falló: {e}"],
                                sugerencias=[], dictamen_llm="")
        import json as _json, re as _re
        m = _re.search(r"\{[\s\S]*\}", respuesta or "")
        if not m:
            return DictamenTono(ok=False,
                                problemas=[f"LLM no devolvió JSON: {(respuesta or '')[:80]}"],
                                sugerencias=[], dictamen_llm=respuesta or "")
        try:
            data = _json.loads(m.group(0))
        except Exception as e:
            return DictamenTono(ok=False, problemas=[f"JSON inválido: {e}"],
                                sugerencias=[], dictamen_llm=respuesta)
        return DictamenTono(
            ok=bool(data.get("ok", False)),
            problemas=list(data.get("problemas", [])),
            sugerencias=list(data.get("sugerencias", [])),
            dictamen_llm=respuesta,
        )


# ── Evaluador semántico por LLM (Haiku, barato) ──────────────────────────────
# R-10 / BG-257 (auditoria 2026-07-20): el system prompt estaba clavado a UN tenant,
# asi que el email de un segundo tenant se evaluaba con la marca del primero. Es el
# precedente que motiva R-TENANT; el detalle con nombres vive en la auditoria, no aqui.
# Ahora el prompt se construye POR TENANT desde empresas/<empresa>/brand/guia.json; si
# no hay guia, cae a una plantilla NEUTRA que interpola el nombre del tenant.

_BRAND_SYSTEM_TMPL = """Eres el Brand Guardian de {nombre}. Tu única tarea es evaluar si un
borrador de email B2B encaja con la voz e identidad de la empresa.

Marca de {nombre}: {posicionamiento}
Tono: {tono}

Rechaza si:
- Suena a IA genérica o plantilla obvia (frases vacías, "no dude en contactarme", "espero
  su pronta respuesta", "atentamente quedo a su disposición").
- Hace promesas de descuento o ventaja de precio.
- Es agresivo, presiona o pide reunión inmediatamente.
- Usa jerga corporativa anglosajona ("ROI", "win-win", "best-in-class").
- No personaliza al destinatario (nombre del negocio, sector, ubicación o pista concreta).

Acepta si:
- Suena humano, escrito por alguien con historia real de la empresa.
- Personaliza al lead específico.
- Es breve y deja la puerta abierta sin presionar.
- Termina con una firma humana real.

Responde EXACTAMENTE con dos líneas:
APROBADO|NO_APROBADO
<motivo en una frase>
"""

_BRAND_DEFECTO = {
    "nombre": "la empresa",
    "posicionamiento": ("sobria, honesta, centrada en su oficio; compite en autenticidad, "
                        "no en precio"),
    "tono": "cálido pero profesional; nunca agresivo, nunca de vendedor",
}


def _brand_system(empresa: str = "laboratorio") -> str:
    """System prompt del Brand Guardian POR TENANT (R-10). Lee empresas/<t>/brand/guia.json."""
    datos = dict(_BRAND_DEFECTO)
    try:
        from departments.brand import config as brand_cfg
        guia = brand_cfg.cargar_guia(empresa) or {}
    except Exception:  # noqa: BLE001
        guia = {}
    nombre = guia.get("nombre") or guia.get("empresa") or empresa
    datos["nombre"] = nombre
    if guia.get("posicionamiento"):
        datos["posicionamiento"] = str(guia["posicionamiento"])
    if guia.get("tono") or guia.get("voz"):
        datos["tono"] = str(guia.get("tono") or guia.get("voz"))
    return _BRAND_SYSTEM_TMPL.format(**datos)


# R-TENANT (2026-08-04): el arreglo R-10 se aplico al camino de EMAIL (_brand_system)
# pero este, el de VOZ, seguia clavado a un cliente concreto — la misma fuga que
# BG-257, sin cerrar, en el otro canal. Ahora tambien se construye POR TENANT.
_TONO_CONVERSACIONAL_TMPL = """Eres el Brand Guardian de {nombre} analizando una llamada
telefónica ya cerrada. Tu trabajo es evaluar SOLO los turnos del agente (no el cliente).

Marca de {nombre}: {posicionamiento}
Tono: {tono}

Rechaza si:
- Sonó a IA genérica o plantilla obvia ("no dude en contactarme", "espero su pronta
  respuesta", "atentamente quedo a su disposición").
- Cayó en jerga corporativa anglosajona (ROI, win-win, best-in-class, oportunidad única).
- Hizo promesas de descuento/ventaja de precio.
- Presionó al cliente o insistió tras una negativa clara.
- Monopolizó la conversación (>70% del tiempo hablando).
- No personalizó al lead concreto (nombre del negocio, ubicación o pista específica).
- No respetó el opt-out cuando se insinuó.

Acepta si:
- Sonó humano, escrito por alguien con historia real de la empresa.
- Personalizó al lead específico.
- Hizo preguntas concretas y escuchó.
- Cerró respetuosamente.

Devuelve EXACTAMENTE JSON sin markdown:
{{
  "ok": true|false,
  "problemas": ["..."],   // si ok=false
  "sugerencias": ["..."]  // 1-3 sugerencias concretas para mejorar la próxima llamada
}}
"""


def _tono_conversacional_system(empresa: str = "laboratorio") -> str:
    """System prompt del analisis de tono de VOZ, POR TENANT (R-TENANT)."""
    datos = dict(_BRAND_DEFECTO)
    try:
        from departments.brand import config as brand_cfg
        guia = brand_cfg.cargar_guia(empresa) or {}
    except Exception:  # noqa: BLE001
        guia = {}
    datos["nombre"] = guia.get("nombre") or guia.get("empresa") or empresa
    if guia.get("posicionamiento"):
        datos["posicionamiento"] = str(guia["posicionamiento"])
    if guia.get("tono") or guia.get("voz"):
        datos["tono"] = str(guia.get("tono") or guia.get("voz"))
    return _TONO_CONVERSACIONAL_TMPL.format(**datos)


def _llm_semantic_evaluator(asunto: str, cuerpo: str, *,
                            contexto_negocio: str = "", lead: dict | None = None,
                            empresa: str = "laboratorio") -> dict:
    """Llama a Claude Haiku para evaluar el tono. Coste despreciable (<0.001€)."""
    info_lead = ""
    if lead:
        info_lead = (f"\nLead: {lead.get('nombre','')} · "
                     f"tipo={lead.get('categoria_icp','')} · "
                     f"ciudad={lead.get('ubicacion',{}).get('ciudad', lead.get('ubicacion',{}).get('direccion',''))}")
    user = (
        f"=== CONTEXTO {empresa.upper()} ===\n{contexto_negocio[:1200]}\n\n"
        f"=== BORRADOR ==={info_lead}\n"
        f"Asunto: {asunto}\n\n{cuerpo}\n"
    )
    respuesta = ai.chat(
        [{"role": "user", "content": user}],
        system=_brand_system(empresa),            # R-10: marca POR TENANT, no clavada
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        company=empresa,
    )
    lineas = [l.strip() for l in (respuesta or "").splitlines() if l.strip()]
    veredicto = (lineas[0] if lineas else "").upper()
    motivo = lineas[1] if len(lineas) > 1 else ""
    return {"ok": veredicto.startswith("APROBADO"),
            "motivo": motivo, "dictamen": respuesta or ""}
