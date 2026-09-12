"""Composer de mensajes de voz personalizados (Claude genera texto + ElevenLabs sintetiza).

Para cada lead:
  1. Claude Sonnet 4.6 escribe el texto del mensaje adaptado al lead concreto.
  2. Brand Guardian (versión ligera) valida que cumple R5 + tono de marca.
  3. ElevenLabs TTS sintetiza el MP3 con la voz clonada de Iván.
  4. MP3 se guarda en `_workspace/voz/` (gitignored) para que ngrok lo sirva público.
"""
from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import requests

import claude_client as ai
import diario_ops as diario

ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MEDIA_DIR = Path(__file__).resolve().parents[4] / "_workspace" / "voz"

# Teléfono de devolución de llamada (configurable; no hardcodear datos personales).
# R-TENANT: sin defecto. El telefono de devolucion es dato del tenant y sale de
# empresas/<t>/brand/firma.json; el entorno solo lo sobreescribe para ensayos.
# Llevaba dentro un numero real: PII de un tercero versionada en el arbol.
TELEFONO_CONTACTO = os.environ.get("KAIZEN_TELEFONO_CONTACTO", "")

_DIGITOS_ES = {"0": "cero", "1": "uno", "2": "dos", "3": "tres", "4": "cuatro",
               "5": "cinco", "6": "seis", "7": "siete", "8": "ocho", "9": "nueve"}


def _telefono_en_palabras(tel: str) -> str:
    """'600 000 000' → 'seis cero cero, cero cero cero, cero cero cero' (para TTS)."""
    grupos = [g for g in re.split(r"\D+", tel) if g]
    return ", ".join(" ".join(_DIGITOS_ES[d] for d in g) for g in grupos)


def _identidad_tenant(empresa: str) -> tuple[str, str, str, str]:
    """(responsable, cargo, negocio, telefono) del tenant. Nunca literales aqui.

    R-TENANT: este prompt llevaba dentro el nombre de una persona real, su cargo,
    su empresa y su telefono. Ahora todo sale del perfil y la firma del tenant.
    """
    try:
        from core.empresa import cargar_perfil_empresa
        from departments.brand import config as brand_cfg
        perfil = cargar_perfil_empresa(empresa) or {}
        firma = brand_cfg.cargar_firma(empresa) or {}
    except Exception:  # noqa: BLE001
        perfil, firma = {}, {}
    responsable = firma.get("remitente_nombre") or "el responsable comercial"
    cargo = firma.get("remitente_cargo") or "responsable comercial"
    negocio = (perfil.get("nombre") or firma.get("remitente_empresa")
               or empresa or "el negocio")
    telefono = firma.get("telefono") or TELEFONO_CONTACTO
    return responsable, cargo, negocio, telefono


def _sistema_guion_voz(empresa: str = "laboratorio") -> str:
    """System prompt del guion de voz, POR TENANT (R-TENANT)."""
    responsable, cargo, negocio, telefono = _identidad_tenant(empresa)
    return f"""Eres el asistente comercial de {responsable}, {cargo}
de {negocio}.
Vas a DEJAR UN MENSAJE DE VOZ a un cliente HORECA que NO te conoce todavía.
Primera llamada en frío.

REGLAS DEL TEXTO QUE GENERAS:
- Para ser DICHO en voz alta, no leído. Frases cortas, naturales, ritmo de habla.
- Tono cercano murciano. Sobrio. Sin presión.
- Empieza identificándote con transparencia: "Hola, buenos días. Le llama el
  asistente virtual de {responsable}, de {negocio} — soy un sistema automatizado
  con la voz de {responsable}, con su autorización."
- En UNA sola frase corta, menciona la grabación: "esta llamada queda grabada para
  control de calidad" o similar.
- En 2-3 frases personalizas al lead concreto: nombre del establecimiento, ciudad,
  UNA razón clara por la que le llamas a ÉL específicamente (lo que viste, su tipo
  de negocio, su ubicación). No genérico.
- Cuenta brevemente quién es {negocio}, usando SOLO lo que aparezca en el contexto
  de negocio que se te pasa. No inventes historia ni antigüedad. En 2 frases máximo.
- Call-to-action concreto: dile que si le interesa conocer el producto, {responsable}
  le devuelve la llamada con muestra o catálogo, y que puede llamarle al
  {telefono}. NO pidas reunión presencial todavía.
- Cierra agradeciendo y un "hasta pronto" natural.
- Duración objetivo cuando se lea: 45-60 segundos (~ 110-150 palabras).
- PROHIBIDO: "Estimado señor", "Atentamente", "ROI", "win-win", "oportunidad única",
  "barato", "industrial", "low-cost", emojis, símbolos, comillas dramatizando.
- PROHIBIDO afirmar o dar a entender que eres una persona.
- Para el teléfono, di "{_telefono_en_palabras(telefono)}" (dígito a
  dígito) para que el TTS lo pronuncie bien.

DEVUELVE SOLO EL TEXTO EXACTO que vas a leer. Sin asunto, sin comillas envolviendo,
sin formato. Solo el cuerpo del mensaje, listo para sintetizar.
"""


# Compatibilidad con quien lo importaba como constante (tenant sintetico).
_SISTEMA_GUION_VOZ = _sistema_guion_voz("laboratorio")

PROHIBIDAS_VOZ = ("ROI", "win-win", "win win", "atentamente", "estimado señor",
                  "oportunidad única", "barato", "barata", "industrial",
                  "low-cost", "lowcost", "lorem", "ipsum")


@dataclass
class GuionVoz:
    lead_id: str
    texto: str                            # texto a leer
    mp3_path: Path                        # MP3 generado en disco
    mp3_bytes: int
    voice_id: str
    review: dict                          # {aprobado, problemas, sugerencias}
    intentos: int = 1


def _validar_guion_voz(texto: str, empresa: str = "laboratorio") -> dict:
    """Brand Guardian ligero para guiones de voz. R5 + reglas básicas de marca."""
    problemas: list[str] = []
    sugerencias: list[str] = []
    if not texto.strip():
        return {"aprobado": False, "problemas": ["texto vacío"], "sugerencias": []}
    palabras = texto.split()
    if len(palabras) < 60:
        problemas.append(f"Texto corto ({len(palabras)} palabras, mín 60)")
    elif len(palabras) > 200:
        sugerencias.append(f"Texto largo ({len(palabras)} palabras); ideal 110-150")
    low = texto.lower()
    for p in PROHIBIDAS_VOZ:
        if p.lower() in low:
            problemas.append(f"Palabra/frase prohibida: '{p}'")
    # R-TENANT: quien firma y como se llama el negocio salen del tenant, no de
    # un literal. Antes esta validacion exigia el nombre de pila de una persona
    # concreta, asi que cualquier otro tenant fallaba la regla por diseno.
    responsable, _cargo, negocio, telefono = _identidad_tenant(empresa)
    nombre_pila = responsable.split()[0].lower() if responsable.split() else ""
    if nombre_pila and nombre_pila not in low:
        problemas.append(f"Falta identificación del remitente ({responsable})")
    if negocio.lower() not in low and empresa.lower() not in low:
        problemas.append(f"Falta nombre de la empresa ({negocio})")
    if "grabad" not in low and "grabar" not in low:
        problemas.append("Falta mención de grabación (R5)")
    if ("asistente" not in low and "virtual" not in low and "automatizad" not in low
            and "sistema" not in low):
        problemas.append("Falta identificación como asistente virtual/IA "
                         "(AI Act / normativa ES de llamadas comerciales)")
    _tel_digitos = re.sub(r"\D", "", telefono)
    _tel_palabras = _telefono_en_palabras(telefono).split(",")[0].strip()
    if _tel_digitos and _tel_digitos[:3] not in re.sub(r"\D", "", texto) \
            and _tel_palabras not in low:
        sugerencias.append(f"No deja el teléfono de devolución ({telefono} "
                           f"o dicho dígito a dígito)")
    return {"aprobado": not problemas, "problemas": problemas, "sugerencias": sugerencias}


class ComposerVoz:
    """Genera texto + MP3 personalizado por lead.

    `chat` y `tts_request` son inyectables para tests; defaults llaman a Anthropic y
    ElevenLabs reales respectivamente."""

    def __init__(self, *, empresa: str = "laboratorio", chat=None,
                 tts_request=None, contexto_negocio: str | None = None,
                 media_dir: Path | None = None) -> None:
        self.empresa = empresa
        self.chat = chat or ai.chat
        self.tts_request = tts_request
        self.contexto_negocio = (contexto_negocio if contexto_negocio is not None
                                 else diario.read("CONTEXTO_NEGOCIO", empresa))
        self.media_dir = media_dir or MEDIA_DIR
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def componer(self, lead: dict, *, voice_id: str | None = None,
                 model_id: str | None = None) -> GuionVoz:
        voice_id = voice_id or os.environ.get("IVAN_VOICE_ID", "")
        if not voice_id:
            raise RuntimeError("IVAN_VOICE_ID no encontrada en .env o parámetro.")
        model_id = model_id or os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

        ficha = self._ficha(lead)
        prompt = (
            f"=== CONTEXTO DEL NEGOCIO ===\n{self.contexto_negocio[:1500]}\n\n"
            f"=== LEAD CONCRETO ===\n{ficha}\n\n"
            "Escribe el mensaje exacto que voy a dejar en el contestador o que escuchará "
            "el cliente cuando descuelgue."
        )
        texto = (self.chat(
            [{"role": "user", "content": prompt}],
            system=_sistema_guion_voz(self.empresa),   # R-TENANT: identidad POR TENANT
            model="claude-sonnet-4-6",
            max_tokens=400,
            company=self.empresa,
        ) or "").strip()
        # Limpieza: quitar comillas envolventes si el LLM las metió
        texto = re.sub(r'^[\'"`]+|[\'"`]+$', "", texto).strip()

        review = _validar_guion_voz(texto)

        # TTS — incluso si el review no aprueba, sintetizamos para que el operador
        # pueda escuchar el resultado y decidir. Si rechaza, regeneramos manualmente.
        mp3 = self._sintetizar(texto, voice_id, model_id)
        return GuionVoz(
            lead_id=lead.get("id", ""),
            texto=texto, mp3_path=mp3, mp3_bytes=mp3.stat().st_size,
            voice_id=voice_id, review=review,
        )

    @staticmethod
    def _ficha(lead: dict) -> str:
        ubic = lead.get("ubicacion") or {}
        meta = lead.get("metadatos_fuente") or {}
        contacto = lead.get("contacto") or {}
        rating = meta.get("rating")
        rev = meta.get("ratings_count")
        rating_str = f"{rating} ({rev} reseñas)" if rating else "—"
        return (
            f"Nombre del establecimiento: {lead.get('nombre','')}\n"
            f"Tipo / categoría ICP: {lead.get('categoria_icp','?')} "
            f"(prioridad {lead.get('prioridad_icp','?')})\n"
            f"Ciudad / dirección: {ubic.get('direccion','?')}\n"
            f"Anillo logístico: {lead.get('anillo','?')} "
            f"({lead.get('distancia_minutos','?')} min en coche desde Cieza)\n"
            f"Valoración pública: {rating_str}\n"
            f"Tamaño estimado: {lead.get('tamano_estimado','?')}\n"
            f"Web: {contacto.get('web','?')}\n"
            f"Descripción breve: {lead.get('descripcion','')[:200]}\n"
        )

    def _sintetizar(self, texto: str, voice_id: str, model_id: str) -> Path:
        if self.tts_request is not None:
            return self.tts_request(texto, voice_id, model_id, self.media_dir)
        return self._sintetizar_real(texto, voice_id, model_id)

    def _sintetizar_real(self, texto: str, voice_id: str, model_id: str) -> Path:
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY no encontrada.")
        r = requests.post(
            ELEVEN_TTS_URL.format(voice_id=voice_id),
            headers={"xi-api-key": api_key, "Accept": "audio/mpeg",
                     "Content-Type": "application/json"},
            json={"text": texto, "model_id": model_id,
                  "voice_settings": {"stability": 0.5,
                                      "similarity_boost": 0.85,
                                      "style": 0.3}},
            timeout=120,
        )
        r.raise_for_status()
        nombre = f"voz_mensaje_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp3"
        out = self.media_dir / nombre
        out.write_bytes(r.content)
        return out
