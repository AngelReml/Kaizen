"""Panel mínimo (Fase 1): FastAPI + WebSocket. Feed de eventos del bus en tiempo real.

Sin Node: la interfaz es una página HTML autocontenida servida en /.
Cuando el panel crezca (tarjetas de departamento, chat con el Director, diagnóstico)
pasará a React. Arranque local:  uvicorn api.server:app --reload
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import agentes
import claude_client
from core import cost_tracker
from core.bitacora import attach
from core.bus import get_bus
from core.config_store import get_config
from core.director import Director
from core.empresa import Empresa, RegistroEmpresas
from core.events import Event, EventType
from core.guardian import Guardian, llm_semantic_evaluator
from core.knowledge import get_knowledge
from core.subscriptors.finanzas_ingestor import FinanzasIngestor
from core.subscriptors.qa_validador import QAValidador
from departments.prospeccion import ProspeccionDepartment
from departments.redaccion import RedaccionDepartment
from departments.especialistas import crear_departamentos
from departments.protocolos import ProspeccionARedaccion
from departments.finanzas.agente import FinanzasDepartment
from departments.finanzas import reglas as finanzas_reglas
from departments.finanzas import herramientas as finanzas_h
from departments.qa.agente import QADepartment
from departments.qa import herramientas as qa_h
from departments.ops.agente import OpsDepartment
from departments.legal.agente import LegalDepartment
from departments.legal import reglas as legal_reglas

bus = get_bus()
attach(bus)                  # la bitácora registra todos los eventos
claude_client.set_bus(bus)   # la contabilidad de coste (CLI) emite al bus
cost_tracker.set_bus(bus)    # la contabilidad de los especialistas emite al bus

# Persistencia: config (Postgres o memoria) + conocimiento (Neo4j o memoria).
config = get_config()
knowledge = get_knowledge()
if not config.list_companies():
    # Siembra data-driven: cada empresa es una carpeta diario/<slug>/ con CONTEXTO_NEGOCIO.md.
    # El sistema NO conoce ninguna empresa a priori; las descubre del Diario en runtime.
    from core.rutas import dir_diario
    _diario_dir = dir_diario()
    if _diario_dir.exists():
        for _d in sorted(p for p in _diario_dir.iterdir() if (p / "CONTEXTO_NEGOCIO.md").exists()):
            _texto = (_d / "CONTEXTO_NEGOCIO.md").read_text(encoding="utf-8", errors="replace")
            import diario_ops as _do
            _nombre = _do._extraer_identidad_remitente(_texto).get("empresa") or _d.name
            config.add_company(_d.name, _nombre, "")

# Ingestor de Finanzas: cada evento de coste se materializa como nodo Gasto.
FinanzasIngestor(bus, knowledge)
# Validador de QA: valida automáticamente los borradores de Redacción.
QAValidador(bus, knowledge)

# SOE_SIM=1 arranca el panel en modo simulación (sin red ni coste).
_SIM = os.getenv("SOE_SIM") == "1"

# Empresa por defecto del panel (multi-tenant: configurable, no hardcodeada).
_COMPANY_DEFAULT = os.getenv("KAIZEN_COMPANY", "laboratorio")

# Seguridad (auditoría 2026-06-07): en modo REAL sin KAIZEN_TOKEN los endpoints
# sensibles y el WebSocket quedan CERRADOS (fail-closed), no abiertos. Para el modo
# desarrollo abierto: SOE_SIM=1, o KAIZEN_ALLOW_NO_TOKEN=1 como opt-in explícito.
if not os.getenv("KAIZEN_TOKEN") and not _SIM:
    print("[server] AVISO: panel REAL sin KAIZEN_TOKEN — los endpoints sensibles y el "
          "WebSocket quedan BLOQUEADOS. Define KAIZEN_TOKEN en .env (o "
          "KAIZEN_ALLOW_NO_TOKEN=1 si asumes el riesgo en local).", file=sys.stderr)
PRESUPUESTO_MENSUAL_EUR = 500.0
_redaccion = RedaccionDepartment(bus, simulacion=_SIM)
_departamentos = {
    "prospeccion": ProspeccionDepartment(bus, simulacion=_SIM),
    "redaccion": _redaccion,
    **crear_departamentos(bus, simulacion=_SIM),   # Desarrollo, RRHH (cascarones; pospuestos por roadmap 5.4)
    # Departamentos REALES reemplazan a sus cascarones:
    "finanzas": FinanzasDepartment(bus, knowledge, presupuesto_mensual=PRESUPUESTO_MENSUAL_EUR),
    "qa": QADepartment(bus, knowledge),
    "ops": OpsDepartment(bus, knowledge),
    "legal": LegalDepartment(bus, knowledge),
}
# Human-in-the-loop real (auditoría 2026-06-07): en modo REAL las acciones de
# criticidad alta NO se auto-aprueban. El Director ya publica APPROVAL_REQUESTED al
# panel; la aprobación humana efectiva es invocar /send (u otra acción explícita).
# En simulación, o con KAIZEN_AUTO_APPROVE=1 (opt-in consciente), se aprueba solo.
_AUTO_APPROVE = _SIM or os.getenv("KAIZEN_AUTO_APPROVE", "").lower() in ("1", "true")


def _confirmacion_humana(interpretacion: str) -> bool:
    if _AUTO_APPROVE:
        return True
    print(f"[server] Aprobación humana requerida (denegada por defecto): "
          f"{interpretacion}", file=sys.stderr)
    return False


director = Director(bus, _departamentos, confirm=_confirmacion_humana)

# KAIZEN_USE_PIPELINES=1 activa los sub-agentes con routing de modelos en cada departamento.
# Vacío (defecto): comportamiento legacy.
if bool(os.getenv("KAIZEN_USE_PIPELINES", "")):
    for _slug in ("prospeccion", "redaccion", "legal", "finanzas", "qa", "ops"):
        _departamentos[_slug].usar_pipeline = True

# Protocolo automático: al encontrar leads, Prospección dispara Redacción sin Director.
ProspeccionARedaccion(bus, _redaccion)

# Guardián: capa semántica LLM (salvo simulación) + reglas duras de Finanzas inyectadas.
guardian = Guardian(
    bus,
    semantic=(None if _SIM else llm_semantic_evaluator),
    reglas_extra=[finanzas_reglas.como_regla_guardian, legal_reglas.como_regla_guardian],
)

# Registro de empresas en memoria, cargado desde la config persistente.
registro = RegistroEmpresas()
for c in config.list_companies():
    registro.alta(Empresa(c["slug"], c["nombre"], c.get("sector", ""), c.get("contexto", "")))

# ws → empresa suscrita (None = todas; filtrado SERVER-SIDE, no en el cliente JS).
_clients: dict[WebSocket, str | None] = {}
_queue: "asyncio.Queue[str]" = asyncio.Queue()
_loop: asyncio.AbstractEventLoop | None = None


def _on_event(event: Event) -> None:
    """Suscriptor del bus (puede correr en otro hilo): encola para el broadcaster."""
    if _loop is not None:
        _loop.call_soon_threadsafe(_queue.put_nowait, event.to_json())


bus.subscribe(_on_event)


async def _broadcaster() -> None:
    while True:
        data = await _queue.get()
        try:
            ev_company = json.loads(data).get("company")
        except Exception:
            ev_company = None
        for ws, comp in list(_clients.items()):
            # Aislamiento multi-empresa server-side: un cliente suscrito a una
            # empresa NO recibe eventos de otras (DEUDA_TECNICA #4).
            if comp and ev_company and comp != ev_company:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                _clients.pop(ws, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_running_loop()
    task = asyncio.create_task(_broadcaster())
    bus.publish(Event(EventType.SYSTEM_STARTED, source="panel", company=_COMPANY_DEFAULT))
    yield
    task.cancel()


app = FastAPI(title="SOE Panel", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=str(STATIC / "assets")), name="assets")


# ── Autenticación por token (Block D) ─────────────────────────────────────────
# Si KAIZEN_TOKEN está definido, se exige en endpoints sensibles y en el WebSocket.
# Si no está definido, el panel queda abierto (modo desarrollo).
def _check_token(token: str | None) -> bool:
    expected = os.getenv("KAIZEN_TOKEN", "")
    if expected:
        return hmac.compare_digest(token or "", expected)
    # Sin token configurado: fail-closed en modo REAL. Abierto SOLO en simulación,
    # bajo test real (proceso pytest efectivamente cargado — no un simple nombre de
    # variable de entorno que cualquiera podría fijar para colarse), o con el
    # opt-in explícito KAIZEN_ALLOW_NO_TOKEN=1 / KAIZEN_TEST_MODE=1.
    return (_SIM or "pytest" in sys.modules
            or os.getenv("KAIZEN_TEST_MODE") == "1"
            or os.getenv("KAIZEN_ALLOW_NO_TOKEN") == "1")


async def auth_dep(authorization: str | None = Header(None)) -> None:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if not _check_token(token):
        raise HTTPException(status_code=401, detail="No autorizado")


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "sim": _SIM,                       # True = simulación (sin LLM); False = modo REAL (Claude)
        "bus": type(bus).__name__,
        "knowledge": type(knowledge).__name__,
        "config": type(config).__name__,
        "eventos": len(bus.history()),
    }


@app.post("/emit", dependencies=[Depends(auth_dep)])
async def emit(marker: str = "demo") -> dict:
    """Publica un evento de prueba para validar el feed en vivo."""
    bus.publish(Event(
        EventType.DEPT_TASK_STARTED, source="demo",
        payload={"marker": marker}, company=_COMPANY_DEFAULT,
    ))
    return {"ok": True}


@app.get("/companies", dependencies=[Depends(auth_dep)])
async def companies() -> list[dict]:
    """Empresas registradas para el selector del panel."""
    return [{"slug": e.slug, "nombre": e.nombre, "sector": e.sector} for e in registro.lista()]


@app.get("/finanzas", dependencies=[Depends(auth_dep)])
async def finanzas(company: str = _COMPANY_DEFAULT) -> dict:
    """Resumen financiero para la tarjeta de Finanzas del panel."""
    if registro.get(company) is None:
        raise HTTPException(status_code=404, detail=f"Empresa desconocida: {company}")
    mes = finanzas_h.consultar_gasto(knowledge, company, "mes")
    quema = finanzas_h.proyectar_quema(knowledge, company, presupuesto_mensual=PRESUPUESTO_MENSUAL_EUR)
    return {
        "gasto_dia_eur": finanzas_h.consultar_gasto(knowledge, company, "hoy")["total_eur"],
        "gasto_mes_eur": mes["total_eur"],
        "presupuesto_mensual_eur": PRESUPUESTO_MENSUAL_EUR,
        "runway_dias": quema["dias_runway_si_no_recargas"],
        "top": finanzas_h.top_acciones_caras(knowledge, company, n=3, periodo="semana"),
        "alertas": len(finanzas_h.detectar_anomalia(knowledge, company)),
    }


@app.post("/intent", dependencies=[Depends(auth_dep)])
async def intent(text: str = Body(..., embed=True),
                  company: str = Body(_COMPANY_DEFAULT, embed=True)) -> dict:
    """Orden en lenguaje natural al Director, para la empresa indicada.

    `text`/`company` viajan en el cuerpo JSON (antes iban en la query string, donde
    quedaban expuestos en logs de acceso / historial del navegador). Cuerpo esperado:
    {"text": "...", "company": "..."}."""
    if registro.get(company) is None:
        return {"ok": False, "resumen": f"Empresa desconocida: {company}"}
    result = await asyncio.to_thread(director.handle_intent, text, company=company)
    return {"ok": result.ok, "resumen": result.summary}


@app.post("/send", dependencies=[Depends(auth_dep)])
async def send(lead: str, company: str = _COMPANY_DEFAULT) -> dict:
    """Envía el borrador aprobado de un lead (acción irreversible). Pasa por el Guardián.

    Invocar este endpoint ES la aprobación humana del envío. Requiere SMTP configurado
    y que la ficha del lead tenga un email real y un borrador aprobado.
    """
    if registro.get(company) is None:
        return {"ok": False, "motivo": f"Empresa desconocida: {company}"}
    return await asyncio.to_thread(
        lambda: agentes.enviar_borrador_guardado(
            lead, company, bus=bus, guardian=guardian, qa_validar=qa_h.validar_borrador,
        )
    )


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str | None = Query(None),
                      company: str | None = Query(None)) -> None:
    if not _check_token(token):
        await websocket.close(code=1008)   # policy violation
        return
    await websocket.accept()
    _clients[websocket] = company or None
    for event in bus.history():        # replay del historial al conectar (filtrado)
        if company and getattr(event, "company", None) and event.company != company:
            continue
        await websocket.send_text(event.to_json())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _clients.pop(websocket, None)


# ── Fase 1 Voz: webhooks de Twilio + ElevenLabs CAI ──────────────────────────
# Reciben los 3 eventos asíncronos post-call (status, recording, transcript) y disparan
# el análisis de calidad cuando los tres han llegado. No exigen el `auth_dep` (token
# Kaizen) porque la autenticación es por firma HMAC del proveedor.

from fastapi import Request


def _bypass_firma_permitido() -> bool:
    """KAIZEN_VOICE_SIG_BYPASS=true solo surte efecto en simulación o bajo pytest.
    En modo REAL el flag se IGNORA: un webhook sin firma válida nunca entra
    (auditoría 2026-06-07 — integridad del pipeline post-call)."""
    if os.environ.get("KAIZEN_VOICE_SIG_BYPASS", "false").lower() != "true":
        return False
    if _SIM or "PYTEST_CURRENT_TEST" in os.environ:
        return True
    print("[server] AVISO: KAIZEN_VOICE_SIG_BYPASS=true IGNORADO en modo real "
          "(las firmas de webhook se verifican siempre).", file=sys.stderr)
    return False


def _url_publica_twilio(request: Request) -> str:
    """URL usada para verificar la firma Twilio. Twilio firma la URL EXTERNA (pública)
    que invocó, no la que ve el proceso local — detrás de un proxy/túnel (ngrok, nginx)
    `request.url` puede llevar host/esquema internos y la firma nunca coincidiría.
    Si PUBLIC_MEDIA_BASE_URL está definida, reconstruimos la URL pública a partir de
    ella + el path (+ query) de la petición; si no, caemos a `request.url` (dev local)."""
    base = os.environ.get("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")
    if not base:
        return str(request.url)
    url = base + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    return url


def _firma_twilio_valida(url: str, params: dict, signature: str | None) -> bool:
    """Twilio firma con HMAC-SHA1(auth_token, url + sorted(params concatenated))."""
    if _bypass_firma_permitido():
        return True
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not token or not signature:
        return False
    import base64, hashlib, hmac
    sorted_pairs = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    computed = base64.b64encode(
        hmac.new(token.encode(), (url + sorted_pairs).encode(), hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(computed, signature)


def _firma_eleven_valida(payload_bytes: bytes, signature: str | None) -> bool:
    """ElevenLabs firma webhooks con HMAC-SHA256(secret, body)."""
    if _bypass_firma_permitido():
        return True
    secret = os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret or not signature:
        return False
    import hashlib, hmac
    computed = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def _tenant_de_llamada(call_sid: str) -> str:
    """R-06 (auditoria 2026-07-20): deriva el tenant DUEÑO de la llamada en vez de
    atribuir la PII de todos al tenant por defecto. Busca el nodo `llamada`
    con ese call_sid entre las empresas conocidas. Si no aparece (huerfano), NO lo cuela
    bajo el tenant por defecto en silencio: lo atribuye a un area de cuarentena y lo registra."""
    try:
        companies = list(knowledge.companies())
    except Exception:  # noqa: BLE001
        companies = [_COMPANY_DEFAULT]
    for c in companies:
        try:
            if knowledge.get(c, "llamada", call_sid) is not None:
                return c
        except Exception:  # noqa: BLE001
            continue
    print(f"[server] AVISO R-06: call_sid {call_sid!r} sin tenant conocido; "
          f"a cuarentena 'desconocido' (no se atribuye a {_COMPANY_DEFAULT}).", file=sys.stderr)
    return "desconocido"


def _post_call_orquestador(company: str = _COMPANY_DEFAULT):
    """Construye un orquestador con el LeadStore + Knowledge ya configurados arriba."""
    from departments.comercial.lifecycle import LeadStore
    from departments.comercial.sdr.voz_conversacional.post_call import PostCallOrchestrator
    return PostCallOrchestrator(lead_store=LeadStore(knowledge, company),
                                 knowledge=knowledge, company=company)


@app.post("/comercial/voz/twilio/status")
async def voz_twilio_status(request: Request) -> dict:
    """StatusCallback de Twilio: initiated → ringing → answered → completed."""
    body = await request.body()
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    url = _url_publica_twilio(request)
    if not _firma_twilio_valida(url, params, request.headers.get("X-Twilio-Signature")):
        raise HTTPException(status_code=403, detail="firma Twilio inválida")
    from departments.comercial.sdr.voz_conversacional import transcripts as _t
    call_sid = params.get("CallSid", "")
    estado = params.get("CallStatus", "")
    duracion = float(params.get("CallDuration") or 0.0)
    parches = {"twilio_status": estado}
    if duracion:
        parches["duracion_s"] = duracion
    tenant = _tenant_de_llamada(call_sid)               # R-06: tenant real, no _COMPANY_DEFAULT
    try:
        _t.actualizar_llamada(knowledge, tenant, call_sid, **parches)
    except KeyError:
        # webhook recibido para una llamada que no creamos (huérfana) — toleramos
        pass
    if estado == "completed":
        _t.marcar_evento_completado(knowledge, tenant, call_sid, "status_completed")
        _post_call_orquestador(tenant).tal_vez_disparar_analisis(call_sid)
    return {"ok": True}


@app.post("/comercial/voz/twilio/recording")
async def voz_twilio_recording(request: Request) -> dict:
    """RecordingStatusCallback: la grabación está lista para descargar."""
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    if not _firma_twilio_valida(_url_publica_twilio(request), params,
                                 request.headers.get("X-Twilio-Signature")):
        raise HTTPException(status_code=403, detail="firma Twilio inválida")

    from departments.comercial.sdr.voz_conversacional import transcripts as _t
    from departments.comercial.sdr.voz_conversacional.grabaciones import descargar_recording
    call_sid = params.get("CallSid", "")
    rec_url  = params.get("RecordingUrl", "")
    rec_dur  = float(params.get("RecordingDuration") or 0.0)

    res = descargar_recording(call_sid=call_sid, recording_url=rec_url, duracion_s=rec_dur)
    tenant = _tenant_de_llamada(call_sid)               # R-06: grabaciones segmentadas por tenant real
    if res.ok:
        try:
            _t.actualizar_llamada(knowledge, tenant, call_sid,
                                  recording_path=str(res.ruta),
                                  recording_url_twilio=rec_url,
                                  recording_bytes=res.bytes,
                                  recording_sha256=res.sha256)
        except KeyError:
            pass
    else:
        try:
            _t.marcar_no_conforme(knowledge, tenant, call_sid,
                                  f"descarga_recording_fallo:{res.motivo}")
        except KeyError:
            pass
    _t.marcar_evento_completado(knowledge, tenant, call_sid, "recording")
    _post_call_orquestador(tenant).tal_vez_disparar_analisis(call_sid)
    return {"ok": res.ok}


@app.post("/comercial/voz/eleven/transcript")
async def voz_eleven_transcript(request: Request) -> dict:
    """Webhook de ElevenLabs CAI con el transcript al cierre de la conversación.

    Schema esperado del payload (ElevenLabs CAI 2024):
      { conversation_id, agent_id, transcript: [{role, message, time_in_call_secs}, ...],
        metadata: { ... call_sid via custom variable / parameter ... } }
    """
    body = await request.body()
    if not _firma_eleven_valida(body, request.headers.get("ElevenLabs-Signature")):
        raise HTTPException(status_code=403, detail="firma ElevenLabs inválida")
    import json as _json
    payload = _json.loads(body.decode("utf-8")) if body else {}

    from departments.comercial.sdr.voz_conversacional import transcripts as _t
    # ElevenLabs no nos da el CallSid de Twilio directamente; sí pasamos lead_id como
    # <Parameter>. Recuperamos el call_sid del metadata custom_data o del custom_data del transcript.
    meta = payload.get("metadata") or {}
    custom = (payload.get("conversation_initiation_client_data")
              or payload.get("conversation_initiation_data")
              or {}).get("dynamic_variables") or meta.get("custom_data") or {}
    call_sid = custom.get("call_sid") or meta.get("call_sid") or payload.get("conversation_id", "")

    raw_transcript = payload.get("transcript") or []
    transcript = []
    for turno in raw_transcript:
        role = (turno.get("role") or "").lower()
        hablante = "agente" if role in ("agent", "assistant", "agente") else "cliente"
        transcript.append({
            "hablante": hablante,
            "ts": float(turno.get("time_in_call_secs", 0) or 0),
            "texto": turno.get("message") or turno.get("text") or "",
        })
    tenant = _tenant_de_llamada(call_sid)               # R-06: transcript (PII) al tenant real
    try:
        _t.persistir_transcript(knowledge, tenant, call_sid, transcript)
    except KeyError:
        # huérfano — el call_sid no estaba en nuestra Knowledge. Creamos shell mínima.
        _t.marcar_evento_completado(knowledge, tenant, call_sid, "transcript")
    _post_call_orquestador(tenant).tal_vez_disparar_analisis(call_sid)
    return {"ok": True, "turnos": len(transcript)}
