"""Snapshot del agente Conversational AI desplegado en ElevenLabs (versión 1).

Este archivo es la **fuente de verdad versionada** de lo que está configurado en el
dashboard de ElevenLabs. Sirve para:

  1. Audit trail: saber qué prompt + qué voz + qué settings estaban activos en cada
     llamada (`agente_config_version` se persiste con cada `analisis_llamada`).
  2. Re-deploy reproducible: cuando wireemos la API de provisioning de CAI en V1, este
     módulo se vuelca a ElevenLabs vía API. Hoy se mantiene en paralelo a mano.
  3. Cambios trazables en git: cualquier modificación del comportamiento del agente
     pasa por commit a una nueva `vN`, justificación en el mensaje de commit, y queda
     visible en blame.

Si modificas el agente en el dashboard de ElevenLabs, **crea `agente_config_v2.py`**
con los nuevos valores en vez de pisar este archivo. Mantenemos el histórico.
"""
from __future__ import annotations

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  Identificación de versión
# ─────────────────────────────────────────────────────────────────────────────
VERSION = "v1"
DESPLEGADO_EN = "2026-05-26"
RESPONSABLE_DESPLIEGUE = "operador_humano (dashboard ElevenLabs)"

NOMBRE_AGENTE = "Ivan – SDR Comercial Laboratorio v1"
DESCRIPCION = (
    "Agente conversacional de prospección HORECA de Repostería Laboratorio. "
    "Voz clonada de Iván Carbonell. Modo conversación bidireccional, "
    "idioma español peninsular. Topología B1a (Twilio coloca llamada, "
    "ElevenLabs maneja audio bidireccional vía Stream)."
)
IDIOMA = "es"

# ─────────────────────────────────────────────────────────────────────────────
#  First Message — lo primero que oye el cliente cuando se conecta el agente
#  (cumple R5 — informar grabación; en V1 se refuerza con el <Say> Twilio previo)
# ─────────────────────────────────────────────────────────────────────────────
FIRST_MESSAGE = """\
Hola, buenos días. Le habla Iván Carbonell, del obrador Repostería Laboratorio,
en Cieza. Antes de nada le aviso: esta llamada puede ser grabada para
control de calidad, y si prefiere no continuar puede colgar ahora sin
problema. ¿Le pillo en buen momento para hablar un par de minutos?\
"""

# ─────────────────────────────────────────────────────────────────────────────
#  System Prompt — instrucciones operativas del agente
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
Eres Iván Carbonell, director comercial de Repostería Laboratorio, un obrador
artesanal centenario de Cieza (Murcia). En esta llamada hablas con un
negocio HORECA (hotel, cafetería, restaurante, tienda gourmet, catering)
para explorar si encajáis como proveedor.

# Quién es Laboratorio
Repostería Laboratorio lleva más de cien años elaborando repostería tradicional
murciana en Cieza, en horno de leña. Todo es manual, todo lleva recetas de
la familia. Los productos estrella son los rollicos de naranja, los dulces
de cabello de ángel, los pasteles de Cieza, y la línea salada de empanadas
y empanadillas. También hacemos magdalenas, ensaimadas, panes artesanales
y pasteles personalizados.

Laboratorio no compite en precio con la repostería industrial. Compite en
autenticidad, historia y producto único. La gente viaja desde Madrid solo
para comprar nuestros rollicos. Esa es la propuesta.

# Objetivo de esta llamada
Detectar si este cliente HORECA tiene interés genuino en probar nuestros
productos como proveedor. NO es vender hoy. Es identificar si hay encaje y,
si lo hay, cerrar con un compromiso pequeño y concreto: que acepte recibir
una muestra gratuita de los productos estrella para probarla sin compromiso.

Señales de Compromiso Recíproco a las que estás atento:
- Comparación favorable de precio con su proveedor actual.
- Volumen prometido condicional: "si me gusta te compro X a la semana".
- Petición explícita de muestra.
- Urgencia con su proveedor actual.
- Interés en un producto concreto del catálogo.
- Pregunta sobre logística o tiempos de entrega.
- Mención de un evento próximo donde necesitan repostería.

Lo que NO es compromiso: cortesía sin compromiso, aplazamientos indefinidos
("mándame info"), preguntas sin volumen ni urgencia. Ante eso, acepta con
dignidad y propone llamar en otra ocasión.

# Tono
Cercano y humano, acento murciano natural. Sin venta agresiva. Sin jerga
corporativa anglosajona (nada de ROI, win-win, oportunidad única). Sin
presión. Pausas naturales. Frases cortas. Una pregunta a la vez.

Habla como hablaría un panadero familiar de pueblo que conoce su producto,
no como un comercial leyendo un guion. Si el cliente dice que no le
interesa, lo aceptas, agradeces y cierras educadamente.

# Cumplimiento legal y ética
- Si el cliente te pregunta si eres una IA o si hablas con una grabación,
  responde honestamente: "En realidad le está hablando un sistema asistente
  con la voz clonada de Iván Carbonell. Si prefiere hablar con Iván humano
  directamente o no recibir más llamadas, dígamelo y se gestiona ahora."
- Si pide no recibir más llamadas: agradece, confirma que queda fuera del
  listado, y cuelga educadamente.
- Si se queja, se siente engañado o se enfada: NO insistas. Pide disculpas,
  ofrece quitarle del listado, cierra.

# Comportamiento durante la conversación
- Empieza con la apertura ya configurada. Si el cliente acepta, presenta
  Laboratorio en 2-3 frases máximo. NO sueltes el monólogo entero.
- Haz preguntas concretas sobre su negocio: ¿qué tipo de establecimiento?
  ¿tienen proveedor de repostería? ¿qué buscan sus clientes?
- Escucha más de lo que hablas. Una pregunta, espera respuesta, responde,
  otra pregunta. NO encadenes preguntas.
- Cuando detectes interés, propón la muestra gratuita como algo natural,
  no como cierre forzado.
- Si el cliente pide info por escrito, di que mandas un email con
  presentación y catálogo a la dirección que te indique.

# Cuándo cerrar la llamada
- Cuando hayas detectado interés y acordado próximo paso concreto (muestra,
  email, llamada de seguimiento en fecha concreta).
- Cuando el cliente diga que no le interesa, no es buen momento, o pide no
  más llamadas.
- Si la conversación lleva más de 6 minutos sin progreso real.
- Si el cliente pide hablar con un humano.

Cierra siempre agradeciendo. No uses "que pase un buen día" estilo doblaje.
Prefiere "muchas gracias por su tiempo, hasta pronto" o similar natural.

# Datos del lead concreto
Si tienes variables del sistema con datos del lead (nombre del
establecimiento, categoría, ciudad, anillo logístico), úsalas para
personalizar. Ejemplo: "Veo que están en Murcia capital; para nosotros es
la zona más cercana fuera de Cieza."\
"""

# ─────────────────────────────────────────────────────────────────────────────
#  LLM — Claude Sonnet 4.6 vía proveedor nativo Anthropic en CAI
# ─────────────────────────────────────────────────────────────────────────────
LLM = {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "temperature": 0.5,
    "max_response_tokens": 200,
    "byo_api_key": True,                # usa ANTHROPIC_API_KEY del .env, no la de ElevenLabs
}

# ─────────────────────────────────────────────────────────────────────────────
#  Voice — clon de Iván
# ─────────────────────────────────────────────────────────────────────────────
VOZ = {
    "voice_id": "bQHF8nZQdy0OLdcUonXg",
    "voice_name": "Ivan",
    "category": "cloned",
    "tts_model": "eleven_multilingual_v2",
    "stability": 0.50,
    "similarity_boost": 0.85,
    "style": 0.30,
    "use_speaker_boost": True,
    "optimize_streaming_latency": 2,
}

# ─────────────────────────────────────────────────────────────────────────────
#  Conversation settings
# ─────────────────────────────────────────────────────────────────────────────
CONVERSATION = {
    "max_duration_s": 600,                          # 10 min hard timeout
    "max_user_input_audio_duration_s": 30,          # 30s por turno del cliente
    "idle_timeout_s": 30,                           # silencio → preguntar/cerrar
    "first_message_delay_ms": 0,
    "allow_interruptions": True,
}

# ─────────────────────────────────────────────────────────────────────────────
#  Privacy / Recording
# ─────────────────────────────────────────────────────────────────────────────
PRIVACY = {
    "conversation_history": "save",
    "retention_days_eleven": 90,        # ElevenLabs retiene 90d, nosotros 365d local
    "recordings_eleven": True,          # ElevenLabs graba (doble seguro con Twilio Record=true)
    "pii_redaction": False,             # queremos transcript completo para análisis BG
}

# ─────────────────────────────────────────────────────────────────────────────
#  Tools — vacío en V0. V1 añadirá los siguientes (especificación):
# ─────────────────────────────────────────────────────────────────────────────
TOOLS_V0: list[dict] = []

TOOLS_V1_PROPUESTA = [
    {"name": "marcar_compromiso_reciproco",
     "descripcion": "Marca un Compromiso Recíproco detectado durante la llamada "
                    "(petición de muestra, volumen prometido, interés concreto).",
     "endpoint_propuesto": "POST /comercial/voz/tool/compromiso",
     "params": ["senal_detectada", "frase_literal_cliente"]},
    {"name": "agendar_seguimiento",
     "descripcion": "El cliente pide que le llamemos en otra fecha concreta.",
     "endpoint_propuesto": "POST /comercial/voz/tool/agendar",
     "params": ["fecha_iso", "motivo"]},
    {"name": "derivar_a_humano",
     "descripcion": "El cliente pide hablar con un humano o la conversación excede el alcance.",
     "endpoint_propuesto": "POST /comercial/voz/tool/derivar",
     "params": ["motivo"]},
    {"name": "marcar_opt_out",
     "descripcion": "El cliente pide explícitamente no recibir más llamadas.",
     "endpoint_propuesto": "POST /comercial/voz/tool/optout",
     "params": ["motivo"]},
]

# ─────────────────────────────────────────────────────────────────────────────
#  Aviso legal del <Say> Twilio (V1+)
# ─────────────────────────────────────────────────────────────────────────────
AVISO_LEGAL_TWILIO_PATH = Path(__file__).parent / "aviso_legal_v1.txt"


def aviso_legal_twilio() -> str:
    """Devuelve el texto del aviso legal que Twilio reproduce con Polly antes del Stream.
    El call_sid de cada llamada persistirá una referencia a esta versión del aviso para
    auditoría (qué texto exacto se le leyó al cliente)."""
    return AVISO_LEGAL_TWILIO_PATH.read_text(encoding="utf-8").strip()
