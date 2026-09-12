"""Esquema unificado del lead (Módulo 1 del sistema nervioso).

Ver `docs/MODELO_DATOS_LEAD.md` y `docs/DECISIONES_ARQUITECTONICAS.md#adr-001`.

Filosofía: dataclass + `from_dict` blando que tolera leads existentes y rellena
defaults. Compatible bidireccional con `json.dump/load`. Cero dependencias nuevas.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from typing import Any, Optional


SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
#  Subdocumentos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Ubicacion:
    lat: Optional[float] = None
    lon: Optional[float] = None
    direccion: str = ""

    @classmethod
    def from_dict(cls, raw: dict | None) -> "Ubicacion":
        raw = raw or {}
        return cls(
            lat=raw.get("lat"),
            lon=raw.get("lon"),
            direccion=raw.get("direccion", "") or "",
        )


@dataclass
class Contacto:
    telefono: Optional[str] = None
    email: Optional[str] = None
    email_verificado: bool = False
    web: Optional[str] = None
    instagram: Optional[str] = None
    fuente_descubrimiento: str = ""

    @classmethod
    def from_dict(cls, raw: dict | None) -> "Contacto":
        raw = raw or {}
        return cls(
            telefono=raw.get("telefono"),
            email=raw.get("email"),
            email_verificado=bool(raw.get("email_verificado", False)),
            web=raw.get("web"),
            instagram=raw.get("instagram"),
            fuente_descubrimiento=raw.get("fuente_descubrimiento", "") or "",
        )


@dataclass
class Interaccion:
    """Un evento en la vida del lead: llamada, email, WhatsApp, anotación manual."""
    ts: str = field(default_factory=_now)
    tipo: str = "llamada"                  # llamada | email | whatsapp | linkedin | manual
    direccion: str = "outbound"            # outbound | inbound
    resultado: str = ""                    # contestado, no_contesta, opt_out, error_smtp, …
    canal_id: Optional[str] = None         # call_sid, message_id, conv_id …
    transcript_id: Optional[str] = None
    resumen_llm: Optional[str] = None
    duracion_s: Optional[float] = None

    @classmethod
    def from_dict(cls, raw: dict) -> "Interaccion":
        return cls(
            ts=raw.get("ts") or _now(),
            tipo=raw.get("tipo", "llamada"),
            direccion=raw.get("direccion", "outbound"),
            resultado=raw.get("resultado", "") or "",
            canal_id=raw.get("canal_id"),
            transcript_id=raw.get("transcript_id"),
            resumen_llm=raw.get("resumen_llm"),
            duracion_s=raw.get("duracion_s"),
        )


@dataclass
class Compromiso:
    """Algo que el sistema (o el lead) prometió y debe cumplirse en una fecha."""
    id: str = ""
    tipo: str = "callback"                 # callback | muestra | email_info | referido | visita
    fecha_objetivo: str = ""               # ISO UTC con hora aprox; vacío si no aplica
    tolerancia_min: int = 15
    contexto: str = ""
    origen_interaccion_id: Optional[str] = None
    cumplido: bool = False
    cumplido_en: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: dict) -> "Compromiso":
        return cls(
            id=raw.get("id", "") or "",
            tipo=raw.get("tipo", "callback"),
            fecha_objetivo=raw.get("fecha_objetivo", "") or "",
            tolerancia_min=int(raw.get("tolerancia_min", 15) or 15),
            contexto=raw.get("contexto", "") or "",
            origen_interaccion_id=raw.get("origen_interaccion_id"),
            cumplido=bool(raw.get("cumplido", False)),
            cumplido_en=raw.get("cumplido_en"),
        )


@dataclass
class PoliticaReintentos:
    """Estado del lead respecto a su política de reintentos. La política en sí (las
    reglas) vive en `empresas/<empresa>/politica_reintentos.json`."""
    proxima_accion_ts: Optional[str] = None
    proxima_accion_tipo: Optional[str] = None     # llamar | email | nurturing | none
    intentos_realizados: int = 0
    max_intentos: int = 3
    ultima_razon_reintento: str = ""

    @classmethod
    def from_dict(cls, raw: dict | None) -> "PoliticaReintentos":
        raw = raw or {}
        return cls(
            proxima_accion_ts=raw.get("proxima_accion_ts"),
            proxima_accion_tipo=raw.get("proxima_accion_tipo"),
            intentos_realizados=int(raw.get("intentos_realizados", 0) or 0),
            max_intentos=int(raw.get("max_intentos", 3) or 3),
            ultima_razon_reintento=raw.get("ultima_razon_reintento", "") or "",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Documento principal del lead
# ─────────────────────────────────────────────────────────────────────────────

# Conjunto canónico de campos del LeadDoc al nivel raíz. Se usa por `from_dict` para
# distinguir lo modelado de lo legacy y por `to_dict` para no duplicar campos extras.
_CAMPOS_MODELADOS: set[str] = set()    # se rellena al final del módulo


@dataclass
class LeadDoc:
    # Identidad
    id: str
    company: str

    # Identificación de negocio
    nombre: str = ""
    categoria_icp: str = ""
    prioridad_icp: Optional[str] = None
    anillo: int = 99                        # 99 = sin clasificar
    descripcion: str = ""
    tamano_estimado: Optional[str] = None

    # Localización + contacto
    ubicacion: Ubicacion = field(default_factory=Ubicacion)
    contacto: Contacto = field(default_factory=Contacto)

    # Estado (legacy + nuevo)
    estado: str = "identificado"            # legacy EstadoLead
    estado_pipeline: str = "cold"           # nuevo EstadoPipeline (ADR-002)
    fecha_ultima_transicion: str = field(default_factory=_now)
    razon_ultima_transicion: str = ""

    # Historial estructurado
    interacciones: list[Interaccion] = field(default_factory=list)
    compromisos: list[Compromiso] = field(default_factory=list)
    memoria_conversacional: str = ""

    # Reintentos
    reintentos: PoliticaReintentos = field(default_factory=PoliticaReintentos)

    # Compliance
    do_not_call: bool = False

    # Legacy compatibles (los conservamos para no romper los 466 leads existentes)
    checklists: dict = field(default_factory=dict)
    fuentes: list[dict] = field(default_factory=list)
    metadatos_fuente: dict = field(default_factory=dict)
    actualidad_signal: Optional[dict] = None
    historial: list[dict] = field(default_factory=list)
    distancia_minutos: Optional[float] = None
    distancia_metros: Optional[float] = None
    distancia_provider: Optional[str] = None
    email_discovery: Optional[dict] = None
    problemas_enrichment: list[str] = field(default_factory=list)
    tipo_detectado: Optional[str] = None

    # Metadatos del sistema
    creado_en: str = field(default_factory=_now)
    actualizado_en: str = field(default_factory=_now)
    agente_responsable: Optional[str] = None
    _schema_version: int = SCHEMA_VERSION

    # Cualquier campo del JSON que NO esté modelado aquí cae en este saco para no
    # perder información del knowledge real.
    metadatos_extra: dict = field(default_factory=dict)

    # ── from_dict ──────────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, raw: dict) -> "LeadDoc":
        """Construye LeadDoc desde un dict (lead del knowledge). Tolerante con campos
        ausentes (defaults) y con campos extras (preservados en `metadatos_extra`)."""
        if not raw.get("id"):
            raise ValueError("LeadDoc: campo 'id' obligatorio")
        if not raw.get("company"):
            raise ValueError("LeadDoc: campo 'company' obligatorio")

        # Sub-docs
        ubicacion = Ubicacion.from_dict(raw.get("ubicacion"))
        contacto = Contacto.from_dict(raw.get("contacto"))
        reintentos = PoliticaReintentos.from_dict(raw.get("reintentos"))
        interacciones = [Interaccion.from_dict(x) for x in (raw.get("interacciones") or [])]
        compromisos = [Compromiso.from_dict(x) for x in (raw.get("compromisos") or [])]

        # estado_pipeline derivado del legacy si no está
        estado_legacy = raw.get("estado", "identificado")
        estado_pipeline = raw.get("estado_pipeline")
        if not estado_pipeline:
            estado_pipeline = mapear_legacy_a_pipeline(estado_legacy)

        # metadatos_extra: cualquier campo del JSON que no esté modelado.
        metadatos_extra = {k: v for k, v in raw.items() if k not in _CAMPOS_MODELADOS}

        doc = cls(
            id=raw["id"], company=raw["company"],
            nombre=raw.get("nombre", "") or "",
            categoria_icp=raw.get("categoria_icp", "") or "",
            prioridad_icp=raw.get("prioridad_icp"),
            anillo=int(raw.get("anillo", 99) if raw.get("anillo") is not None else 99),
            descripcion=raw.get("descripcion", "") or "",
            tamano_estimado=raw.get("tamano_estimado"),
            ubicacion=ubicacion, contacto=contacto,
            estado=estado_legacy, estado_pipeline=estado_pipeline,
            fecha_ultima_transicion=raw.get("fecha_ultima_transicion") or raw.get("actualizado_en") or _now(),
            razon_ultima_transicion=raw.get("razon_ultima_transicion", "") or "",
            interacciones=interacciones,
            compromisos=compromisos,
            memoria_conversacional=raw.get("memoria_conversacional", "") or "",
            reintentos=reintentos,
            do_not_call=bool(raw.get("do_not_call", False)),
            checklists=raw.get("checklists") or {},
            fuentes=raw.get("fuentes") or [],
            metadatos_fuente=raw.get("metadatos_fuente") or {},
            actualidad_signal=raw.get("actualidad_signal"),
            historial=raw.get("historial") or [],
            distancia_minutos=raw.get("distancia_minutos"),
            distancia_metros=raw.get("distancia_metros"),
            distancia_provider=raw.get("distancia_provider"),
            email_discovery=raw.get("email_discovery"),
            problemas_enrichment=raw.get("problemas_enrichment") or [],
            tipo_detectado=raw.get("tipo_detectado"),
            creado_en=raw.get("creado_en") or _now(),
            actualizado_en=raw.get("actualizado_en") or _now(),
            agente_responsable=raw.get("agente_responsable"),
            _schema_version=int(raw.get("_schema_version", 0) or 0) or SCHEMA_VERSION,
            metadatos_extra=metadatos_extra,
        )
        return doc

    # ── to_dict ────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Serializa a dict listo para `json.dump`. Los campos de `metadatos_extra` se
        desempaquetan al nivel raíz para que el JSON resultante sea plano."""
        d = asdict(self)
        extras = d.pop("metadatos_extra", {}) or {}
        # extras se desempaqueta SIN sobrescribir lo modelado.
        for k, v in extras.items():
            if k not in d:
                d[k] = v
        return d


# ─────────────────────────────────────────────────────────────────────────────
#  Mapeo legacy → pipeline (importante para load de leads existentes)
# ─────────────────────────────────────────────────────────────────────────────

# Definido aquí (no en pipeline_state_machine.py) para evitar import circular.
# Las constantes nuevas de EstadoPipeline vivirán en M2 y son strings, así que
# aquí solo necesitamos las strings literales (ADR-002).
_MAPEO_LEGACY_A_PIPELINE: dict[str, str] = {
    "identificado":         "cold",
    "cualificado":          "cold",
    "enriquecido":          "cold",
    "en_contacto":          "contacting",
    "compromiso_reciproco": "engaged",
    "muestra_enviada":      "sample_sent",
    "cliente_activo":       "customer",
    "en_riesgo":            "customer",       # con flag riesgo_churn en metadatos_extra
    "perdido":              "lost",
}


def mapear_legacy_a_pipeline(estado_legacy: str) -> str:
    """Mapea un EstadoLead viejo al EstadoPipeline nuevo. Default a `cold` si el
    estado legacy no se reconoce — la migración nunca falla por estado raro."""
    return _MAPEO_LEGACY_A_PIPELINE.get(estado_legacy, "cold")


# ─────────────────────────────────────────────────────────────────────────────
#  Init módulo: rellenamos _CAMPOS_MODELADOS para from_dict
# ─────────────────────────────────────────────────────────────────────────────

_CAMPOS_MODELADOS = {f.name for f in fields(LeadDoc)}
