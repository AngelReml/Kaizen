"""Cliente del endpoint nativo de ElevenLabs CAI para llamadas outbound vía Twilio.

POST /v1/convai/twilio/outbound-call

ElevenLabs hace el POST a Twilio Calls.json por su cuenta usando el número Twilio
previamente importado (`agent_phone_number_id`), abre el WebSocket de audio
bidireccional contra su propio backend, y conversa con el cliente usando el agente
configurado. Al cierre dispara el webhook con transcript + recording.

A diferencia del intento anterior (B1a con `<Stream>` directo desde TwiML), aquí
**no construimos TwiML ni POSTamos a Twilio**. Todo lo orquesta ElevenLabs.

Módulo 8 del sistema nervioso (`docs/SISTEMA_NERVIOSO_M8.md`):

  PRE-llamada    →  `dynamic_variables_briefing(lead, company=...)` proyecta el
                    lead a `LeadDoc` y deriva las variables del briefing (M5)
                    + perfil de empresa. `colocar_llamada_via_cai(..., company=...)`
                    las inyecta automáticamente en el body de ElevenLabs CAI.

  POST-llamada  →  `procesar_transcript_post_llamada(lead_id, company, transcript,
                    knowledge=...)` corre el detector de compromisos (M4), persiste
                    la nueva interacción y aplica el motor de reintentos (M3) sobre
                    la máquina de estados del pipeline (M2).
"""
from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

CAI_OUTBOUND_URL = "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"


@dataclass
class ResultadoCAIOutbound:
    ok: bool
    conversation_id: str | None = None        # ID de la conversación en ElevenLabs
    call_sid: str | None = None               # SID de la llamada en Twilio (devuelto por ElevenLabs)
    motivo: str = ""
    detalle: dict | None = None


def construir_body(*, agent_id: str, agent_phone_number_id: str, to_number: str,
                    lead: dict | None = None,
                    extra_variables: dict | None = None) -> dict:
    """Body del POST. `conversation_initiation_client_data.dynamic_variables` se
    pasa al system prompt del agente para personalizar (lead_nombre, ciudad, etc.).
    """
    variables: dict = {}
    if lead:
        ubic = lead.get("ubicacion") or {}
        variables = {
            "lead_id":     lead.get("id", ""),
            "lead_nombre": lead.get("nombre", ""),
            "categoria":   lead.get("categoria_icp", ""),
            "prioridad":   lead.get("prioridad_icp", ""),
            "anillo":      str(lead.get("anillo", "")),
            "ciudad":      ubic.get("direccion", ""),
        }
    if extra_variables:
        variables.update(extra_variables)
    body = {
        "agent_id": agent_id,
        "agent_phone_number_id": agent_phone_number_id,
        "to_number": to_number,
    }
    if variables:
        body["conversation_initiation_client_data"] = {"dynamic_variables": variables}
    return body


def dynamic_variables_briefing(lead: dict, *, company: str) -> dict:
    """Variables del briefing (M5) listas para inyectar como `dynamic_variables`.

    Proyecta el `lead` (dict del knowledge) a `LeadDoc`, carga el perfil de empresa
    desde `empresas/<company>/perfil.json` y devuelve el dict[str, str] que produce
    `GeneradorBriefing.generar_dynamic_variables`.

    Si la proyección falla (lead sin `id`/`company`, schema corrupto), propaga la
    excepción al caller — el caller decide si caer al camino legacy o abortar.
    """
    from core.briefing import GeneradorBriefing
    from core.empresa import cargar_perfil_empresa
    from core.lead_schema import LeadDoc

    seed = dict(lead or {})
    seed.setdefault("company", company)
    if not seed.get("id"):
        raise ValueError("dynamic_variables_briefing: lead sin 'id'")
    doc = LeadDoc.from_dict(seed)
    perfil = cargar_perfil_empresa(company)
    return GeneradorBriefing(empresa_meta=perfil).generar_dynamic_variables(doc)


def colocar_llamada_via_cai(*, to_number_e164: str, lead: dict,
                             agent_id: str | None = None,
                             agent_phone_number_id: str | None = None,
                             api_key: str | None = None,
                             company: str | None = None) -> ResultadoCAIOutbound:
    """Disparo real. Lee credenciales del entorno por defecto.

    Si se pasa `company`, las variables del briefing (M5) se mezclan al body como
    `extra_variables` — sin sobrescribir las claves legacy (`lead_id`, `lead_nombre`,
    `categoria`, `prioridad`, `anillo`, `ciudad`) que ya consume el agente.
    """
    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
    agent_id = agent_id or os.environ.get("ELEVENLABS_AGENT_ID", "")
    agent_phone_number_id = (agent_phone_number_id
                              or os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", ""))

    faltan = [n for n, v in {
        "ELEVENLABS_API_KEY": api_key,
        "ELEVENLABS_AGENT_ID": agent_id,
        "ELEVENLABS_PHONE_NUMBER_ID": agent_phone_number_id,
    }.items() if not v]
    if faltan:
        return ResultadoCAIOutbound(ok=False, motivo=f"faltan en .env: {', '.join(faltan)}")
    if not to_number_e164:
        return ResultadoCAIOutbound(ok=False, motivo="to_number_e164 vacío")

    # R-02 embebido: barrera de sandbox DENTRO de la función, no solo en el CLI que
    # la llama. `VoiceChannel.colocar_llamada` (canales/voz.py) ya lleva su propio
    # guard (`guardia_llamada_real`) embebido; este camino (CAI) solo lo tenía en
    # el caller (kaizen.py -> pre_flight.verificar), así que cualquier otro caller
    # (test, script, futuro endpoint) podía colocar la llamada saltándoselo. Fail-
    # closed: sin las dos barreras del sandbox global, no se llama.
    if os.environ.get("KAIZEN_ENVIO_HABILITADO", "false").lower() != "true":
        return ResultadoCAIOutbound(ok=False, motivo="KAIZEN_ENVIO_HABILITADO != true (sandbox global).")
    if os.environ.get("SDR_VOICE_ENABLED", "false").lower() != "true":
        return ResultadoCAIOutbound(ok=False,
                                     motivo="SDR_VOICE_ENABLED != true (zona ambar consciente v0.2 §4.3).")

    # Quota diaria: se RESERVA aqui, antes del POST, no se cuenta despues.
    # Comprobar-y-luego-contar dejaba pasar dos llamadas concurrentes y, si el
    # proceso moria entre el POST y el contador, la llamada se hacia sin contarse
    # (auditoria 2026-08-02, C-12). Si algo falla despues, se libera el hueco.
    from departments.comercial.sdr.voz_conversacional import pre_flight as _pf
    try:
        _pf.reservar_llamada()
    except (_pf.QuotaAgotada, _pf.QuotaCorrupta) as e:
        return ResultadoCAIOutbound(ok=False, motivo=str(e))

    extra = None
    if company:
        try:
            extra = dynamic_variables_briefing(lead, company=company)
        except Exception as e:                                  # noqa: BLE001
            print(f"[m8] briefing fallback para lead {lead.get('id','?')}: {e}",
                  file=sys.stderr)
            extra = None

    body = construir_body(agent_id=agent_id,
                           agent_phone_number_id=agent_phone_number_id,
                           to_number=to_number_e164, lead=lead,
                           extra_variables=extra)
    try:
        r = requests.post(CAI_OUTBOUND_URL,
                          headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                          json=body, timeout=30)
    except Exception as e:
        _pf.liberar_llamada()          # no salio ninguna llamada: devolver el hueco
        return ResultadoCAIOutbound(ok=False, motivo=f"red: {e}")
    if r.status_code >= 400:
        _pf.liberar_llamada()          # ElevenLabs rechazo: tampoco se coloco
        return ResultadoCAIOutbound(ok=False, motivo=f"ElevenLabs {r.status_code}: {r.text[:300]}",
                                     detalle={"status": r.status_code, "body": r.text[:1000]})
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    # La reserva ya cuenta como llamada colocada: no se vuelve a incrementar.
    return ResultadoCAIOutbound(
        ok=True,
        conversation_id=data.get("conversation_id"),
        call_sid=data.get("callSid") or data.get("call_sid"),
        detalle=data,
    )


def dry_run(*, to_number_e164: str, lead: dict,
            agent_id: str | None = None,
            agent_phone_number_id: str | None = None,
            api_key: str | None = None,
            company: str | None = None) -> dict:
    """NO marca ningún teléfono. Devuelve exactamente lo que se mandaría:

        {
            "would_post_to": URL,
            "headers": {...},
            "body": {...},
            "estado_credenciales": {...},   # qué falta o está presente
        }

    Si `company` se pasa, el body incluye las variables del briefing (M5) tal cual
    se enviarían en una llamada real.
    """
    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
    agent_id = agent_id or os.environ.get("ELEVENLABS_AGENT_ID", "")
    agent_phone_number_id = (agent_phone_number_id
                              or os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", ""))

    estado = {
        "ELEVENLABS_API_KEY": "PRESENTE" if api_key else "FALTA",
        "ELEVENLABS_AGENT_ID": agent_id or "FALTA",
        "ELEVENLABS_PHONE_NUMBER_ID": agent_phone_number_id or "FALTA",
        "TO_NUMBER": to_number_e164 or "FALTA",
    }
    extra = None
    if company:
        try:
            extra = dynamic_variables_briefing(lead, company=company)
        except Exception as e:                                  # noqa: BLE001
            print(f"[m8] dry_run briefing fallback: {e}", file=sys.stderr)
            extra = None
    body = construir_body(agent_id=agent_id or "<<FALTA>>",
                           agent_phone_number_id=agent_phone_number_id or "<<FALTA>>",
                           to_number=to_number_e164 or "<<FALTA>>", lead=lead,
                           extra_variables=extra)
    return {
        "would_post_to": CAI_OUTBOUND_URL,
        "headers": {"xi-api-key": "<oculto>" if api_key else "<<FALTA>>",
                    "Content-Type": "application/json"},
        "body": body,
        "estado_credenciales": estado,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  M8 — POST-llamada: ingesta del transcript al sistema nervioso
# ─────────────────────────────────────────────────────────────────────────────

OPTOUT_KEYWORDS: tuple[str, ...] = (
    "no me llaméis más", "no me llaméis mas", "no llaméis más", "no llaméis mas",
    "no llamen más", "no llamen mas", "no me llame más", "no me llame mas",
    "borrad mi número", "borradme", "quítenme de la lista", "borreme",
    "no quiero recibir más llamadas", "no quiero recibir mas llamadas",
)

NO_INTERESA_KEYWORDS: tuple[str, ...] = (
    "no me interesa", "no nos interesa", "no estamos interesados",
)

# Mapeo del resultado derivado a la transición intermedia desde CONTACTING.
# El motor de reintentos (M3) parte de este estado intermedio y produce la
# transición final (queued / lost / do_not_call).
_INTERMEDIA_POR_RESULTADO: dict[str, str] = {
    "no_answer":            "no_answer",
    "contacted_no_decisor": "contacted",
    "callback_pactado":     "contacted",
    "no_buen_momento_sin_fecha": "contacted",
    "no_interesa_ahora":    "contacted",
    "no_interesa":          "contacted",
    "engaged_pide_muestra": "engaged",
    "opt_out":              "contacted",
}


@dataclass
class ResultadoPostLlamada:
    ok: bool = True
    motivo: str = ""
    resultado_derivado: str = ""
    compromisos_nuevos: list = field(default_factory=list)
    estado_anterior: str = ""
    estado_intermedio: str = ""
    estado_final: str = ""
    interaccion_id: str = ""
    proxima_accion_ts: str = ""
    proxima_accion_tipo: str = ""


def derivar_resultado_llamada(transcript: list[dict],
                              compromisos: list,
                              *,
                              opt_out_keywords: tuple[str, ...] = OPTOUT_KEYWORDS,
                              no_interesa_keywords: tuple[str, ...] = NO_INTERESA_KEYWORDS,
                              ) -> str:
    """Mapea (transcript, compromisos detectados) a uno de los `RESULTADOS_CONOCIDOS`
    del motor de reintentos. Heurística determinista, sin LLM.
    """
    if not transcript:
        return "no_answer"
    texto_cliente = " ".join(
        (t.get("texto") or t.get("message") or "").lower()
        for t in transcript
        if (t.get("hablante") or t.get("role", "")).lower() in ("cliente", "user", "")
    )
    if any(k in texto_cliente for k in opt_out_keywords):
        return "opt_out"
    if any(c.tipo == "callback" for c in compromisos):
        return "callback_pactado"
    if any(c.tipo == "muestra" for c in compromisos):
        return "engaged_pide_muestra"
    if any(k in texto_cliente for k in no_interesa_keywords):
        return "no_interesa"
    # Hay diálogo, pero sin compromiso accionable: tratado como contacto con
    # no-decisor para que el motor reagenda un reintento dentro de la ventana.
    return "contacted_no_decisor"


def procesar_transcript_post_llamada(*,
                                     lead_id: str,
                                     company: str,
                                     transcript: list[dict],
                                     knowledge=None,
                                     detector=None,
                                     motor=None,
                                     machine=None,
                                     call_sid: str | None = None,
                                     conversation_id: str | None = None,
                                     duracion_s: float | None = None,
                                     resumen_llm: str | None = None,
                                     resultado: str | None = None,
                                     contexto_extra: dict | None = None,
                                     clock=None,
                                     ) -> ResultadoPostLlamada:
    """Ingesta del webhook de ElevenLabs CAI al sistema nervioso (M8).

    Flujo:
      1. Carga el lead del `KnowledgeStore` (o usa el inyectado).
      2. `DetectorCompromisos.detectar(transcript)` → compromisos (M4).
      3. Añade los compromisos al lead (idempotente por tipo+fecha).
      4. Registra la interacción con metadatos de la llamada.
      5. Deriva el `resultado` (callback_pactado / no_answer / …) si no se pasó.
      6. Si el lead está en `contacting`, transiciona al estado intermedio
         (no_answer / contacted / engaged) vía `PipelineMachine` (M2).
      7. `MotorReintentos.decidir(...)` + `aplicar(..., machine=...)` produce la
         transición final (queued / lost / do_not_call) y la próxima acción (M3).
      8. Persiste el lead actualizado en el knowledge.

    Idempotente respecto a transiciones inválidas: si el motor sugiere una
    transición no permitida desde el estado actual, registra la interacción y
    devuelve `ok=False` con `motivo`.
    """
    from core.briefing import _parsear_ts as _briefing_parsear_ts   # reaprovecho
    from core.compromisos import DetectorCompromisos
    from core.knowledge import get_knowledge
    from core.lead_schema import Interaccion, LeadDoc
    from core.pipeline_state_machine import (
        EstadoPipeline, PipelineMachine, TransicionInvalida,
    )
    from core.reintentos import MotorReintentos

    if not lead_id or not company:
        return ResultadoPostLlamada(ok=False, motivo="lead_id y company son obligatorios")

    kstore = knowledge or get_knowledge()
    lead_raw = kstore.get(company, "lead", lead_id)
    if lead_raw is None:
        return ResultadoPostLlamada(ok=False, motivo=f"lead {company}/{lead_id} no existe")

    lead = LeadDoc.from_dict(lead_raw)
    estado_inicial = lead.estado_pipeline

    # 1. Detectar compromisos del transcript
    det = detector or DetectorCompromisos(company=company)
    nuevos_compromisos = det.detectar(transcript or [])

    # 2. Añadir compromisos al lead (idempotente por tipo+fecha_objetivo)
    interaccion_id = f"int_{uuid.uuid4().hex[:10]}"
    agregados = []
    for c in nuevos_compromisos:
        ya = any(x.tipo == c.tipo and x.fecha_objetivo == c.fecha_objetivo
                 for x in lead.compromisos)
        if ya:
            continue
        if not c.origen_interaccion_id:
            c.origen_interaccion_id = interaccion_id
        lead.compromisos.append(c)
        agregados.append(c)

    # 3. Derivar resultado si el caller no lo pasó
    resultado_final = resultado or derivar_resultado_llamada(
        transcript or [], nuevos_compromisos,
    )

    # 4. Registrar la interacción
    now_iso = (clock or (lambda: datetime.now(timezone.utc)))().isoformat()
    inter = Interaccion(
        ts=now_iso,
        tipo="llamada",
        direccion="outbound",
        resultado=resultado_final,
        canal_id=call_sid or conversation_id,
        transcript_id=conversation_id or call_sid,
        resumen_llm=resumen_llm,
        duracion_s=duracion_s,
    )
    # Anclamos el id a metadatos_extra del lead para mantener trazabilidad sin
    # tocar el schema (id no es campo de primera clase de Interaccion).
    lead.metadatos_extra.setdefault("interaccion_ids", {})[inter.ts] = interaccion_id
    lead.interacciones.append(inter)

    # 5. Transición intermedia desde CONTACTING (si procede)
    mach = machine or PipelineMachine()
    intermedio = ""
    motivo = ""
    if lead.estado_pipeline == EstadoPipeline.CONTACTING.value:
        destino = _INTERMEDIA_POR_RESULTADO.get(resultado_final)
        if destino and PipelineMachine.puede_transicionar(lead.estado_pipeline, destino):
            try:
                lead, _ = mach.transicionar(
                    lead, destino,
                    razon=f"post-llamada: {resultado_final}",
                    evento_disparador=call_sid or conversation_id or "",
                    detalle={"interaccion_id": interaccion_id,
                             "duracion_s": duracion_s or 0},
                )
                intermedio = destino
            except TransicionInvalida as e:                     # noqa: BLE001
                motivo = f"transición intermedia inválida: {e}"

    # 6. Motor de reintentos
    pol_path = None
    try:
        from core.rutas import dir_empresa
        candidato = dir_empresa(company) / "politica_reintentos.json"
        if candidato.exists():
            pol_path = candidato
    except Exception:
        pol_path = None
    m_motor = motor or MotorReintentos(politica_path=pol_path)

    callback_ts = ""
    if resultado_final == "callback_pactado":
        cb = next((c for c in nuevos_compromisos if c.tipo == "callback"), None)
        if cb is None:
            cb = next((c for c in lead.compromisos
                       if c.tipo == "callback" and not c.cumplido), None)
        if cb and cb.fecha_objetivo:
            callback_ts = cb.fecha_objetivo

    ctx = dict(contexto_extra or {})
    if callback_ts and "callback_ts" not in ctx:
        ctx["callback_ts"] = callback_ts
    ctx.setdefault("origen_interaccion_id", interaccion_id)

    rec = m_motor.decidir(lead, resultado_final, contexto=ctx)
    estado_final = lead.estado_pipeline
    if rec.transicion_a:
        if PipelineMachine.puede_transicionar(lead.estado_pipeline, rec.transicion_a):
            try:
                m_motor.aplicar(lead, rec, machine=mach)
                estado_final = lead.estado_pipeline
            except TransicionInvalida as e:                     # noqa: BLE001
                motivo = motivo or f"motor: transición {rec.transicion_a} inválida: {e}"
                # Aplicamos lo no-transicional (proxima_accion, intentos, compromiso)
                m_motor.aplicar(lead, _rec_sin_transicion(rec), machine=None)
        else:
            motivo = motivo or (
                f"motor: {rec.transicion_a} no permitido desde {lead.estado_pipeline}; "
                f"se omite transición y se conserva el resto"
            )
            m_motor.aplicar(lead, _rec_sin_transicion(rec), machine=None)

    # 7. Persistir
    kstore.add(company, "lead", lead.id, lead.to_dict())

    return ResultadoPostLlamada(
        ok=not motivo,
        motivo=motivo,
        resultado_derivado=resultado_final,
        compromisos_nuevos=agregados,
        estado_anterior=estado_inicial,
        estado_intermedio=intermedio,
        estado_final=estado_final,
        interaccion_id=interaccion_id,
        proxima_accion_ts=lead.reintentos.proxima_accion_ts or "",
        proxima_accion_tipo=lead.reintentos.proxima_accion_tipo or "",
    )


def _rec_sin_transicion(rec):
    """Clona la recomendación quitando el campo `transicion_a` para reintentar
    la aplicación sin disparar la máquina (cuando la transición no es válida).
    """
    from core.reintentos import RecomendacionReintento
    return RecomendacionReintento(
        transicion_a=None,
        proxima_accion_tipo=rec.proxima_accion_tipo,
        proxima_accion_ts=rec.proxima_accion_ts,
        razon=rec.razon,
        compromiso_a_crear=rec.compromiso_a_crear,
        do_not_call=rec.do_not_call,
        incrementar_intentos=rec.incrementar_intentos,
    )
