# -*- coding: utf-8 -*-
"""Centro de Mando (D10 v0.2) — app FastAPI. Proyeccion pura de las primitivas.

Divergencia registrada (DC-13): el SSE v1 se sirve con sondeo interno sobre la
bitacora (cursor + replay identicos al contrato §7); el hub por hooks queda como
optimizacion. Auth: token compatible con el patron existente (env KAIZEN_TOKEN);
sin token definido = solo uso local abierto (127.0.0.1), como el panel absorbido.
Arranque operador:  python -m panel_mando   →  http://127.0.0.1:8600
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse, StreamingResponse)

import claude_client
from core import tenants as T
from core.aprobaciones import ColaSustrato, TransicionAprobacionInvalida
from core.ledger import LedgerCoste
from core.panico import Panico, PanicoActivo, PalancaCerrada
from core.rue import Bitacora, Sobre
from core.techos import LibroCoste, TechoAlcanzado
from panel_mando import nucleo as N

RAIZ = Path(__file__).resolve().parent.parent
CSS = (Path(__file__).parent / "assets" / "panel.css")


def _empresas(k) -> list[str]:
    return sorted(set(k.companies()) - {"plataforma"}) or ["laboratorio"]


def _empresa_valida(valor: str, *, defecto: str) -> str:
    """R-20: `empresa` es query param de usuario interpolado sin escapar en varias
    paginas (href, data-src, <script>). Antes de esta funcion, un valor como
    `x';fetch(...)//` llegaba intacto al HTML — XSS reflejado que, con la cookie
    kz_csrf legible por JS (a proposito, para que el panel la reenvie), permitia
    ejecutar cualquier accion con la sesion del operador. Un slug de tenant SIEMPRE
    es un identificador ASCII (asi los crea /cmd/empresas/alta); exigirlo aqui no
    rompe altas nuevas, solo cierra la inyeccion."""
    v = (valor or "").strip()
    if not v:
        return defecto
    if not v.isascii() or not v.isidentifier():
        raise HTTPException(400, "empresa invalida: usa minusculas sin espacios")
    return v


# Vida de una sesion de navegador, en segundos (G-06). La cookie y el servidor
# usan el MISMO valor: si solo lo lleva la cookie, quien se la quede la usa para
# siempre porque el servidor no comprueba nada.
SESION_TTL_S = int(os.environ.get("KAIZEN_SESION_TTL_S", str(12 * 3600)) or 12 * 3600)


def crear_app(knowledge=None, *, token: str | None = None, mecha_s: int | None = None,
              ruta_registro: Path | None = None, ruta_panico: Path | None = None,
              ruta_ledger: Path | None = None, ruta_legacy_coste: Path | None = None) -> FastAPI:
    if knowledge is None:
        from core.knowledge import get_knowledge
        knowledge = get_knowledge()
    app = FastAPI(title="Centro de Mando Kaizen", docs_url=None, redoc_url=None)
    st = app.state
    st.k = knowledge
    st.token = token if token is not None else os.getenv("KAIZEN_TOKEN") or None
    st.colas = {}
    st.bitacoras = {}
    # Fase 1 de excelencia: con to_thread en juego, dos peticiones concurrentes
    # podian crear DOS instancias de ColaSustrato para el mismo tenant (check-
    # then-set sin candado) — y como el candado anti-doble-ejecucion de
    # ColaSustrato es POR INSTANCIA, dos instancias del mismo tenant no se
    # serializan entre si: se rompe justo la garantia que ese candado existe
    # para dar. Doble comprobacion dentro del lock (el primer if evita pagar
    # el coste del lock en el camino feliz, ya cacheado).
    st.colas_lock = threading.Lock()
    st.bitacoras_lock = threading.Lock()
    # R-08: bitacoras es una REFERENCIA viva (se rellena bajo demanda) y el estado
    # puede persistirse: un reinicio ya no olvida un PARAR TODO.
    st.panico = Panico(bitacoras=st.bitacoras, ruta_estado=ruta_panico)
    # R-07: ledger persistente unico; sin rutas (tests) queda inerte y todo sigue igual.
    st.ledger = LedgerCoste(ruta_ledger, legacy_json=ruta_legacy_coste)
    st.mechas = N.Mechas(mecha_s if mecha_s is not None else N.MECHA_SEGUNDOS)
    st.ruta_registro = ruta_registro
    st.tema = N.TEMA_DEFECTO
    # R-01: sesiones de navegador (cookie kz_sesion). sid -> epoch de caducidad.
    # Era un set sin caducidad: la cookie llevaba max_age, pero eso lo respeta el
    # NAVEGADOR, no el servidor — un sid robado valia para siempre mientras el
    # proceso viviera, y el set solo crecia (auditoria 2026-08-02, G-06).
    st.sesiones: dict[str, float] = {}
    st.csrf = {}                 # R-19: sid -> token CSRF de esa sesion

    def bit(empresa: str) -> Bitacora:
        if empresa not in st.bitacoras:
            with st.bitacoras_lock:
                if empresa not in st.bitacoras:        # doble check: otro hilo pudo ganar la carrera
                    try:
                        fecha_alta = T.get_tenant(empresa, st.ruta_registro)["fecha_alta"]
                    except Exception:                          # noqa: BLE001
                        fecha_alta = ""                 # sin ficha: cae al default de Bitacora
                    st.bitacoras[empresa] = Bitacora(st.k, empresa, fecha_alta=fecha_alta)
        return st.bitacoras[empresa]

    def cola(empresa: str) -> ColaSustrato:
        if empresa not in st.colas:
            with st.colas_lock:
                if empresa not in st.colas:            # doble check
                    st.colas[empresa] = ColaSustrato(st.k, empresa, bitacora=bit(empresa))
        return st.colas[empresa]

    def libro() -> LibroCoste:
        try:
            mandatos = {t["id"]: t["mandato"] for t in
                        T.cargar_registro(st.ruta_registro)["tenants"]}
        except Exception:                          # noqa: BLE001
            mandatos = {}
        return LibroCoste(st.k, mandatos=mandatos, bitacoras=st.bitacoras, ledger=st.ledger)

    # ── R-01: auth por sesion de navegador (cookie) O cabecera X-Token (API/tests).
    # Jamas un 401 con HTML delante del navegador: las paginas redirigen a /login. ──
    def _purgar_sesiones(ahora: float | None = None) -> None:
        """Retira las sesiones caducadas. Sin esto, `st.sesiones` solo crece."""
        ahora = time.time() if ahora is None else ahora
        for sid in [s for s, expira in st.sesiones.items() if expira <= ahora]:
            st.sesiones.pop(sid, None)
            st.csrf.pop(sid, None)

    def _sesion_valida(request: Request) -> bool:
        c = request.cookies.get("kz_sesion", "")
        if not c:
            return False
        _purgar_sesiones()
        return c in st.sesiones

    def auth(request: Request) -> None:
        if not st.token:
            return                                  # sin token definido: uso local abierto
        if request.headers.get("X-Token") == st.token or _sesion_valida(request):
            return
        raise HTTPException(401, "token")

    def auth_pagina(request: Request) -> RedirectResponse | None:
        """Para endpoints que sirven HTML: sin credencial → redirigir a /login."""
        if not st.token or request.headers.get("X-Token") == st.token or _sesion_valida(request):
            return None
        return RedirectResponse("/login", status_code=303)

    def identidad(datos: dict, request: Request | None = None) -> str:
        # R-19: si hay sesion autenticada, la identidad la da la SESION, no un campo `quien`
        # autodeclarado del cuerpo (que cualquiera podia fijar). Sin auth (local): como antes.
        if request is not None and st.token and _sesion_valida(request):
            return "operador"
        quien = (datos or {}).get("quien", "").strip()
        if not quien:
            raise ValueError("falta identidad: quien da la orden")
        return quien

    def verificar_csrf(request: Request) -> None:
        """R-19: en peticiones de NAVEGADOR (cookie de sesion) exige el token CSRF de la
        sesion. Los clientes de API (cabecera X-Token) y el modo local sin token estan
        exentos: no usan cookie, luego no hay riesgo CSRF.

        ACTIVO POR DEFECTO (auditoria 2026-08-02, G-05). Antes era opt-in via
        KAIZEN_CSRF_ESTRICTO=true y esa variable no estaba en el .env, asi que el
        mecanismo existia, se testeaba... y no se aplicaba en la configuracion real.
        Una defensa apagada por defecto no es una defensa. La variable sigue siendo
        el interruptor, pero ahora para DESACTIVAR (KAIZEN_CSRF_ESTRICTO=false)."""
        if os.environ.get("KAIZEN_CSRF_ESTRICTO", "true").lower() != "true":
            return
        if not st.token:
            return                                           # local abierto
        if request.headers.get("X-Token") == st.token:
            return                                           # API server-to-server
        sid = request.cookies.get("kz_sesion", "")
        if sid and sid in st.sesiones:
            esperado = st.csrf.get(sid, "")
            enviado = request.headers.get("X-CSRF", "")
            if not esperado or not secrets.compare_digest(enviado, esperado):
                raise HTTPException(403, "csrf")

    def _origen_valido(request: Request) -> bool:
        """R-20: en modo 'sin token' (KAIZEN_TOKEN no definido = 'uso local abierto'),
        auth() y verificar_csrf() devuelven de inmediato: CUALQUIER POST a /cmd/*
        pasaba sin ninguna credencial. El navegador SI manda Origin/Referer en un
        fetch cruzado (incluso en modo no-cors, que el atacante no puede desactivar
        via JS) — asi que este chequeo cierra el hueco sin exigirle al operador que
        configure un token para uso puramente local. Sin Origin NI Referer (curl,
        tests, clientes de API server-to-server): se deja pasar."""
        cabecera = request.headers.get("origin") or request.headers.get("referer") or ""
        if not cabecera:
            return True
        try:
            partes = urlsplit(cabecera)
        except ValueError:
            return False
        return partes.hostname == request.url.hostname and partes.port == request.url.port

    @app.middleware("http")
    async def _csrf_mw(request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/cmd/"):
            if not _origen_valido(request):
                return JSONResponse({"error": "origen"}, status_code=403)
            try:
                verificar_csrf(request)
            except HTTPException as e:
                return JSONResponse({"error": e.detail}, status_code=e.status_code)
        return await call_next(request)

    # ── R-16: barreras + veredicto honesto, compartido por los dos closures
    # `ejecutor` de abajo (quemar_vencidas y cmd_aprobar). Antes ambos SOLO
    # comprobaban coste/panico y `ColaSustrato.ejecutar()` marcaba EJECUTADA
    # incondicionalmente si no habia excepcion — una tarjeta IRREVERSIBLE-
    # EXTERNA aprobada quedaba "EJECUTADA" sin que nada saliera jamas al
    # mundo real (auditoria: el panel mentia). El unico canal de envio real
    # cableado hoy es el de Comercial (con su propio candado AI Act, su
    # propio claim atomico — INTOCABLE, este panel no lo toca); sin un canal
    # generico por cubo, la unica respuesta honesta para IRREVERSIBLE-
    # EXTERNA es ENSAYO_SECO, nunca EJECUTADA. Fase 4: una IRREVERSIBLE-
    # INTERNA que nace de una propuesta de Colmena con una herramienta real
    # vinculada SI se dispara de verdad aqui (CLM.ejecutar_si_viene_de_
    # herramienta); sin vinculo, sigue siendo el registro sellado generico
    # de siempre — exactamente lo que la UI ya prometia para esa clase.
    def _barreras_y_veredicto(nodo: dict, empresa: str) -> dict | None:
        if nodo["clase"] == "IRREVERSIBLE-EXTERNA":
            # accion_aprobada_urgente=True: un humano YA dijo SI (D00 §6.3.3,
            # escalera().aprobadas_completan) — el freno de coste no debe
            # bloquear lo ya aprobado, solo lo NUEVO que llegue con el techo tocado.
            libro().hard_stop_delante(empresa, 0.0, accion_aprobada_urgente=True)
        st.panico.gate_irrext(empresa, nodo["clase"])           # gate delante (L3)
        if nodo["clase"] == "IRREVERSIBLE-INTERNA":
            # Fase 2 excelencia: el gasto real de esta herramienta (si su fn
            # llama internamente al LLM) no se media ni se asentaba en ningun
            # sitio — dinero gastado de verdad, invisible en la contabilidad
            # por turno/cubo/director. finally: se asienta aunque falle DESPUES
            # de haber gastado.
            antes = claude_client.session_cost_eur()
            try:
                real = CLM.ejecutar_si_viene_de_herramienta(nodo, empresa, k=st.k,
                                                             bitacora=bit(empresa))
            finally:
                coste = max(0.0, claude_client.session_cost_eur() - antes)
                if coste > 0 and getattr(st.ledger, "ruta", None) is not None:
                    st.ledger.asentar(empresa, cubo=nodo["cubo"],
                                      rol=f"director_{nodo['cubo']}",
                                      clase="herramienta_aprobada", proveedor="anthropic",
                                      coste_eur=coste, causa_id=f"aprobacion:{nodo['id']}")
            if real is not None:
                return real
            return None                                          # sin vinculo: EJECUTADA generica
        if nodo["clase"] == "IRREVERSIBLE-EXTERNA":
            return {"estado": "ENSAYO_SECO", "dry": True,
                    "motivo": "sin canal de envio real cableado para este cubo en el panel"}
        return None                                              # EJECUTADA (comportamiento actual)

    # ── util: quemar mechas vencidas (el pulso del panel las dispara) ──
    def quemar_vencidas() -> list[dict]:
        hechas = []
        for m in st.mechas.vencidas():
            st.mechas.consumir(m["aprobacion"])
            def ejecutor(nodo, _e=m["empresa"]):
                return _barreras_y_veredicto(nodo, _e)
            try:
                n = cola(m["empresa"]).ejecutar(m["aprobacion"], ejecutor)
                hechas.append({"aprobacion": m["aprobacion"], "estado": n["estado"]})
            except (PanicoActivo, TransicionAprobacionInvalida, TechoAlcanzado) as e:
                # TechoAlcanzado faltaba aqui (solo se capturaban panico/transicion):
                # sin capturarla, salia sin control del generador de /rio/{empresa}
                # (cortando el SSE de todo cliente conectado) y el nodo quedaba
                # APROBADA/reintentada=True sin mecha activa ni ruta que lo retome —
                # una aprobacion que el operador dijo SI se quedaba atascada para
                # siempre. Se registra igual que las otras barreras: retenida, nada
                # perdido, visible para quien mire.
                hechas.append({"aprobacion": m["aprobacion"], "retenida": str(type(e).__name__)})
        # R-13: el TTL de 72h esta escrito en core/aprobaciones.py como "regla dura"
        # pero nadie lo invocaba en produccion — una tarjeta PENDIENTE se quedaba
        # pendiente para siempre en vez de caducar y (si REVERSIBLE) reencolarse.
        # quemar_vencidas() ya es el pulso periodico del panel (lo dispara /rio);
        # barrer aqui, por cada empresa conocida, la engancha sin abrir un segundo camino.
        for e in _empresas(st.k):
            for c in cola(e).barrer_caducadas():
                hechas.append({"aprobacion": c["id"], "caducada": c["estado"]})
        return hechas

    # ── manejador escudo (§6) ──
    @app.exception_handler(Exception)
    async def _escudo(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            raise exc
        return JSONResponse(N.escudo(exc), status_code=409)

    # ═══ R-01 · acceso: una clave, un boton (R8) ═══
    def _destino_seguro(ir: str) -> str:
        """Solo rutas internas: nada de esquemas ni // (anti open-redirect)."""
        return ir if ir.startswith("/") and not ir.startswith("//") and ":" not in ir else "/"

    def _form_login(mensaje: str = "", ir: str = "") -> str:
        aviso = f'<p class="aviso-ajustes">{html.escape(mensaje)}</p>' if mensaje else ""
        oculto = (f'<input type="hidden" name="ir" value="{html.escape(_destino_seguro(ir))}">'
                  if ir else "")
        return f"""<!doctype html><html lang="es" data-tema="{st.tema}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Entrar — Kaizen</title>
<link rel="stylesheet" href="/assets/panel.css"></head><body>
<main class="manana" style="max-width:26rem;margin:12vh auto;padding:0 1rem">
<h1>Kaizen</h1><p>Escribe tu clave y pulsa ENTRAR.</p>{aviso}
<form method="post" action="/login">
<input type="password" name="token" autofocus aria-label="clave" style="width:100%;font-size:1.25rem;padding:.65rem">{oculto}
<div class="botones" style="margin-top:.9rem"><button class="si" type="submit" style="width:100%">ENTRAR</button></div>
</form></main></body></html>"""

    def _entrar(destino: str = "/") -> RedirectResponse:
        _purgar_sesiones()                           # G-06: no acumular sesiones muertas
        sid = secrets.token_urlsafe(32)
        st.sesiones[sid] = time.time() + SESION_TTL_S
        csrf = secrets.token_urlsafe(32)             # R-19: token CSRF ligado a la sesion
        st.csrf[sid] = csrf
        r = RedirectResponse(_destino_seguro(destino), status_code=303)
        r.set_cookie("kz_sesion", sid, httponly=True, samesite="lax", max_age=SESION_TTL_S)
        # cookie legible por el JS del panel para reenviarla como cabecera X-CSRF
        r.set_cookie("kz_csrf", csrf, httponly=False, samesite="lax", max_age=SESION_TTL_S)
        return r

    @app.get("/api/csrf")
    def api_csrf(request: Request):
        auth(request)
        sid = request.cookies.get("kz_sesion", "")
        return {"csrf": st.csrf.get(sid, "")}

    @app.get("/logout")
    def logout(request: Request):
        """Revoca la sesion EN EL SERVIDOR, no solo en el navegador (G-06)."""
        sid = request.cookies.get("kz_sesion", "")
        st.sesiones.pop(sid, None)
        st.csrf.pop(sid, None)
        r = RedirectResponse("/login", status_code=303)
        r.delete_cookie("kz_sesion")
        r.delete_cookie("kz_csrf")
        return r

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, token: str = "", ir: str = ""):
        if not st.token or _sesion_valida(request):
            return RedirectResponse(_destino_seguro(ir) if ir else "/", status_code=303)
        if token:                                   # un-toque desde el lanzador .cmd
            if secrets.compare_digest(token, st.token):
                return _entrar(ir or "/")
            return HTMLResponse(_form_login("Esa clave no es. Prueba otra vez.", ir))
        return HTMLResponse(_form_login(ir=ir))

    @app.post("/login")
    async def login_post(request: Request):
        if not st.token:
            return RedirectResponse("/", status_code=303)
        form = await request.form()
        token = str(form.get("token", ""))
        ir = str(form.get("ir", ""))
        if token and secrets.compare_digest(token, st.token):
            return _entrar(ir or "/")
        return HTMLResponse(_form_login("Esa clave no es. Prueba otra vez.", ir))

    # ═══ P0 · esqueleto ═══
    @app.get("/latido")
    def latido():
        return {"ts": datetime.now(timezone.utc).isoformat(), "vivo": True,
                "parado": st.panico.activo}

    @app.get("/rio/{empresa}")
    async def rio(empresa: str, request: Request, desde: int = -1, ciclos: int = 0):
        auth(request)

        async def gen():
            cursor = desde
            restantes = ciclos if ciclos > 0 else 10 ** 9
            while restantes > 0:
                restantes -= 1
                try:                                     # el pulso quema mechas; una
                    # to_thread (Fase 1 excelencia): una aprobacion puede
                    # disparar una herramienta real vinculada (Fase 4) — sin
                    # esto, el hilo del event loop quedaria bloqueado y CADA
                    # cliente conectado a /rio de CUALQUIER empresa se congela.
                    await asyncio.to_thread(quemar_vencidas)
                except Exception:                         # una excepcion aqui
                    pass                                  # no debe matar el stream
                evs = sorted(st.k.all(empresa, "evento").items())
                for clave, e in evs:
                    n = int(clave)
                    if n > cursor:
                        cursor = n
                        yield f"id: {n}\ndata: {json.dumps({'n': n, 'frase': N.render(e), 'tipo': e['tipo'], 'ts': e.get('ts','')}, ensure_ascii=False)}\n\n"
                yield ": latido\n\n"
                if restantes > 0:
                    await asyncio.sleep(0.05 if ciclos else 1.0)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/paridad")
    def paridad():
        return N.cobertura_renderers()

    # ═══ P1 · gobierno ═══
    @app.get("/api/tarjetas/{empresa}")
    def tarjetas(empresa: str, request: Request):
        auth(request)
        out = []
        for x in cola(empresa).listar("PENDIENTE"):
            sale = x["clase"] == "IRREVERSIBLE-EXTERNA"
            out.append({"id": x["id"], "empresa": empresa, "titulo": x["accion"],
                        "cubo": x["cubo"],
                        "consecuencia": ("Si dices SI: la accion SALE AL MUNDO tras una mecha de "
                                         f"{st.mechas.segundos} segundos (podras deshacer)." if sale
                                         else "Si dices SI: se aplica dentro de Kaizen (deshacible)."),
                        "si_no_haces_nada": "Caduca a las 72 horas y se aborta con aviso.",
                        "contenido_ref": x.get("contenido_ref", "")})
        return {"empresa": empresa, "tarjetas": out,
                "vacio": "Nada que aprobar. Kaizen sigue trabajando; te avisare." if not out else ""}

    @app.post("/cmd/aprobar")
    async def cmd_aprobar(request: Request):
        auth(request)
        d = await request.json()
        quien = identidad(d)
        n = cola(d["empresa"]).aprobar(d["id"], por=quien)
        if n["clase"] == "IRREVERSIBLE-EXTERNA" and st.mechas.segundos > 0:
            m = st.mechas.armar(d["id"], d["empresa"])
            return {"estado": "EN_MECHA", "dispara": m["dispara"],
                    "mensaje": f"Se hara en {st.mechas.segundos} segundos — puedes DESHACER."}
        quemadas = await asyncio.to_thread(quemar_vencidas)
        def ejecutor(nodo):
            return _barreras_y_veredicto(nodo, d["empresa"])
        # to_thread (Fase 1 excelencia): una IRREVERSIBLE-INTERNA vinculada a
        # una herramienta real (Fase 4) puede tardar; sin esto, el panel
        # entero se congela para todo el mundo mientras dura la aprobacion.
        n2 = await asyncio.to_thread(cola(d["empresa"]).ejecutar, d["id"], ejecutor)
        return {"estado": n2["estado"], "quemadas": quemadas}

    @app.post("/cmd/deshacer")
    async def cmd_deshacer(request: Request):
        auth(request)
        d = await request.json()
        quien = identidad(d)
        if not st.mechas.desarmar(d["id"]):
            raise TransicionAprobacionInvalida("la mecha ya se consumio o no existia")
        n = cola(d["empresa"]).revocar(d["id"], por=quien)
        return {"estado": n["estado"], "mensaje": "Deshecho a tiempo: no salio nada."}

    @app.post("/cmd/denegar")
    async def cmd_denegar(request: Request):
        auth(request)
        d = await request.json()
        n = cola(d["empresa"]).denegar(d["id"], por=identidad(d), motivo=d.get("motivo", ""))
        return {"estado": n["estado"]}

    @app.post("/cmd/tic")
    async def cmd_tic(request: Request):
        auth(request)
        quemadas = await asyncio.to_thread(quemar_vencidas)
        return {"quemadas": quemadas, "encendidas": st.mechas.encendidas()}

    @app.post("/cmd/parar_todo")
    async def cmd_parar(request: Request):
        auth(request)
        d = await request.json()
        quien = identidad(d)
        for e in _empresas(st.k):     # L2: precalentar bitacoras → el evento queda SELLADO
            bit(e)
        st.panico.activar(por=quien, motivo=d.get("motivo", "orden del operador"))
        retenidas = sum(len(c.listar("APROBADA")) for c in st.colas.values())
        return {"estado": "TODO_PARADO", "retenidas": retenidas,
                "mensaje": "TODO PARADO — nada saldra de Kaizen. No se ha perdido nada."}

    @app.post("/cmd/reanudar")
    async def cmd_reanudar(request: Request):
        auth(request)
        d = await request.json()
        quien = identidad(d)
        for e in _empresas(st.k):     # el evento de reanudacion tambien queda sellado
            bit(e)
        st.panico.desactivar(por=quien)
        return {"estado": "EN_MARCHA", "mensaje": "Reanudado. Las acciones retenidas siguen en su sitio."}

    # ═══ P3 · sala: historias, sello, dinero ═══
    @app.get("/api/historias/{empresa}")
    def api_historias(empresa: str, request: Request):
        auth(request)
        return {"historias": N.historias(st.k, empresa)}

    @app.get("/api/sello/{empresa}")
    def api_sello(empresa: str, request: Request):
        auth(request)
        v = bit(empresa).verificar()
        if v.get("integra"):
            return {"integra": True,
                    "mensaje": f"Historial sellado intacto: {v['eventos']} pasos comprobados."}
        return {"integra": False,
                "mensaje": f"ATENCION: el sello se rompe en el paso {int(v['punto_ruptura'])}. Nada anterior ha cambiado; investiga ese punto.",
                "detalle_tecnico": v}

    @app.get("/api/dinero/{empresa}")
    def api_dinero(empresa: str, request: Request):
        auth(request)
        lb = libro()
        gasto = lb.gasto_dia(empresa)
        try:
            tope = lb._techo_tenant(empresa)
        except Exception:                          # noqa: BLE001
            tope = 0.0
        sa = st.ledger.sin_atribuir_dia()          # R-07: el gasto legado se MUESTRA, no se oculta
        frase = f"Hoy: {N.dinero_humano(gasto)}" + (f" de {N.dinero_humano(tope)}" if tope else "")
        if sa:
            frase += f" · y {N.dinero_humano(sa)} de la plataforma (sin atribuir)"
        return {"frase": frase,
                "gasto_eur": gasto, "tope_eur": tope, "sin_atribuir_eur": sa,
                "modo_ahorro": bool(tope and gasto >= tope)}

    @app.get("/api/dinero/{empresa}/export.csv")
    def api_dinero_csv(empresa: str, request: Request, mes: str = ""):
        auth(request)
        mes = mes or datetime.now(timezone.utc).strftime("%Y-%m")
        return PlainTextResponse(libro().export_csv(empresa, mes), media_type="text/csv")

    # ═══ P4 · cubos y ajustes ═══
    CATALOGO_CONTROLES = {
        "comercial": [("transicionar etapa", "/cmd/comercial/transicion")],
        "brand": [("suspender directriz", "/cmd/brand/suspender")],
        "ops": [("declarar capacidad de hoy", "/cmd/ops/capacidad")],
        "finanzas": [("calcular liquidacion del mes", "/cmd/finanzas/liquidar")],
        "marketing": [("pausar campaña", "/cmd/marketing/pausar")],
        "inteligencia": [("responder a un aviso", "/cmd/inteligencia/alerta")],
        "customer_success": [("(llega con D03)", "")],
    }
    st.catalogo_controles = CATALOGO_CONTROLES
    NOMBRES_CUBOS = {"comercial": "Comercial", "brand": "Marca", "ops": "Operaciones",
                     "finanzas": "Finanzas", "marketing": "Marketing", "inteligencia": "Inteligencia",
                     "customer_success": "Exito de cliente"}

    def _datos_cubos(empresa: str) -> dict:
        conteos = {t: len(v) for t, v in st.k.all(empresa).items()}
        tarjetas_cubos = []
        for cubo, controles in CATALOGO_CONTROLES.items():
            tarjetas_cubos.append({"cubo": cubo,
                                   "controles": [{"nombre": n_, "endpoint": e_} for n_, e_ in controles],
                                   "actividad": sum(v for k_, v in conteos.items()
                                                    if k_.startswith(cubo[:4]) or cubo == "comercial" and k_ in ("lead_canon", "pedido_atribuido"))})
        return {"cubos": tarjetas_cubos, "conteos": conteos}

    @app.get("/api/cubos/{empresa}")
    def api_cubos(empresa: str, request: Request):
        auth(request)
        return _datos_cubos(empresa)

    @app.post("/cmd/ops/capacidad")
    async def cmd_ops_capacidad(request: Request):
        auth(request)
        d = await request.json()
        from departments.ops.cubo_serie_d import CuboOps
        c = CuboOps(st.k, d["empresa"], bitacora=bit(d["empresa"]))
        return c.declarar_capacidad(d["fecha"], int(d["lotes"]), por=identidad(d))

    @app.post("/cmd/inteligencia/alerta")
    async def cmd_intel_alerta(request: Request):
        auth(request)
        d = await request.json()
        from departments.inteligencia.cubo_serie_d import CuboInteligencia
        i = CuboInteligencia(st.k, d["empresa"], bitacora=bit(d["empresa"]))
        return i.resolver_alerta(d["alerta_id"], veredicto=d["veredicto"], por=identidad(d))

    @app.post("/cmd/brand/suspender")
    async def cmd_brand_susp(request: Request):
        auth(request)
        d = await request.json()
        from departments.brand.cubo_serie_d import CuboBrand
        b = CuboBrand(st.k, d["empresa"], bitacora=bit(d["empresa"]))
        return b.transicionar_directriz(d["directriz_id"], "SUSPENDIDA", por=identidad(d))

    @app.post("/cmd/finanzas/liquidar")
    async def cmd_fin_liquidar(request: Request):
        auth(request)
        d = await request.json()
        from departments.finanzas.cubo_serie_d import Liquidador
        lq = Liquidador(st.k, d["empresa"], bitacora=bit(d["empresa"]))
        identidad(d)
        return lq.calcular(d["periodo"], costes_directos=d.get("costes_directos", {}))

    @app.post("/cmd/marketing/pausar")
    async def cmd_mkt_pausar(request: Request):
        auth(request)
        d = await request.json()
        from departments.marketing.cubo_serie_d import CuboMarketing
        m = CuboMarketing(st.k, d["empresa"], bitacora=bit(d["empresa"]))
        identidad(d)
        return m.reconciliar_gasto(d["campana_id"], 0.0) | {"nota": "pausa via kill-switch/estado"}

    @app.post("/cmd/comercial/transicion")
    async def cmd_com_trans(request: Request):
        auth(request)
        d = await request.json()
        from departments.comercial.cubo_serie_d import PipelineCanonico
        p = PipelineCanonico(st.k, d["empresa"], bitacora=bit(d["empresa"]))
        identidad(d)
        return p.transicionar(d["lead_id"], d["a"], disparador="OPERADOR",
                              causa_ref=d.get("causa_ref", "panel"))

    @app.post("/cmd/empresas/alta")
    async def cmd_alta(request: Request):
        auth(request)
        d = await request.json()
        identidad(d)
        ruta = st.ruta_registro or T.ruta_registro_tenants()
        reg = json.loads(Path(ruta).read_text(encoding="utf-8"))
        nid = d["id"].strip().lower()
        if not nid.isascii() or not nid.isidentifier():
            raise ValueError("identidad de empresa invalida: usa minusculas sin espacios")
        if any(t["id"] == nid for t in reg["tenants"]):
            raise ValueError(f"la empresa {nid!r} ya existe")
        reg["tenants"].append({"id": nid, "razon_social": d.get("razon_social", nid),
                               "vertical": d.get("vertical", "por definir"), "estado": "activo",
                               "fecha_alta": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                               "partner_id": None, "referencia_credenciales": "fuera del repo",
                               "mandato": {"nivel_por_defecto": "BAJA",
                                           "techo_coste_diario_eur": 5.0,
                                           "max_emails_dia": 10, "max_llamadas_dia": 25,
                                           "horario_contacto": {"inicio": "10:00", "fin": "18:30",
                                                                "dias": "L-V", "tz": "Europe/Madrid"},
                                           "ventana_repeticion_meses": 12,
                                           "PROVISIONAL": "valores recomendados; ajustalos en Ajustes"}})
        contenido = json.dumps(reg, ensure_ascii=False, indent=1)
        Path(ruta).write_text(contenido, encoding="utf-8")
        if Path(ruta).read_text(encoding="utf-8") != contenido:     # E1
            raise IOError("E1: desfase al escribir el registro")
        bit(nid).publicar(Sobre(
            tenant_id=nid, tipo="plataforma.tenant.creado",
            payload={"empresa_ref": nid}, origen="plataforma.panel"))
        return {"creada": nid, "mandato": "recomendado (ajustable)"}

    @app.post("/cmd/ajustes/tope")
    async def cmd_tope(request: Request):
        auth(request)
        d = await request.json()
        quien = identidad(d)
        nuevo = float(d["tope_eur"])
        if not (0 <= nuevo <= 100):
            raise ValueError("el tope diario debe estar entre 0 y 100 € (guarda de Ajustes)")
        ruta = st.ruta_registro or T.ruta_registro_tenants()
        reg = json.loads(Path(ruta).read_text(encoding="utf-8"))
        for t in reg["tenants"]:
            if t["id"] == d["empresa"]:
                anterior = t["mandato"]["techo_coste_diario_eur"]
                t["mandato"]["techo_coste_diario_eur"] = nuevo
                break
        else:
            raise ValueError("empresa sin ficha")
        # Paridad con /cmd/empresas/alta (mismo fichero, mismo patron
        # read-modify-write): verificacion E1 y evento sellado. Sin esto, un
        # cambio de dinero de gobierno podia "quedar guardado" segun la
        # respuesta 200 sin estarlo de verdad en disco, y sin dejar rastro
        # tamper-evident de quien subio el tope y cuando.
        contenido = json.dumps(reg, ensure_ascii=False, indent=1)
        Path(ruta).write_text(contenido, encoding="utf-8")
        if Path(ruta).read_text(encoding="utf-8") != contenido:     # E1
            raise IOError("E1: desfase al escribir el registro")
        bit(d["empresa"]).publicar(Sobre(
            tenant_id=d["empresa"], tipo="plataforma.mandato.actualizado",
            payload={"quien": quien, "tope_anterior_eur": anterior, "tope_nuevo_eur": nuevo},
            origen="plataforma.panel"))
        return {"empresa": d["empresa"], "tope_eur": nuevo,
                "volver_recomendado": 5.0}

    # ═══ P2/P3/P5 · paginas ═══
    def _pagina(titulo: str, cuerpo: str, tema: str) -> str:
        # R-20: `tema` es un query param de usuario; sin whitelist, un valor como
        # `x"><script>...` rompe el atributo data-tema e inyecta JS en el origen
        # autenticado (XSS reflejado). Centralizado AQUI porque manana()/sala()/
        # tecnico()/colmena_pagina() comparten esta funcion: un solo punto cierra
        # las cuatro rutas a la vez.
        if tema not in N.TEMAS_VALIDOS:
            tema = st.tema
        return f"""<!doctype html><html lang="es" data-tema="{tema}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title><link rel="stylesheet" href="/assets/panel.css"></head>
<body><header><span class="empresa" id="empresa"></span>
<button id="parar" class="parar" title="manten pulsado 2 segundos">PARAR TODO</button>
<span id="latido" class="latido" data-max-seg="5">al dia</span></header>
{cuerpo}
<script>
const LATIDO_MAX_SEG=5;let ult=Date.now();
async function late(){{try{{const r=await fetch('/latido');const j=await r.json();ult=Date.now();
document.getElementById('latido').textContent=j.parado?'TODO PARADO':'al dia';
document.getElementById('latido').className='latido '+(j.parado?'parado':'ok');}}catch(e){{}}
if((Date.now()-ult)/1000>LATIDO_MAX_SEG){{document.getElementById('latido').textContent='reconectando...';
document.getElementById('latido').className='latido tarde';}}}}
setInterval(late,2000);late();
let t0=null;const bp=document.getElementById('parar');
bp.addEventListener('mousedown',()=>{{t0=Date.now();bp.classList.add('armado');}});
bp.addEventListener('mouseup',async()=>{{bp.classList.remove('armado');
function kzCsrf(){{const m=document.cookie.match(/(?:^|;\\s*)kz_csrf=([^;]*)/);return m?decodeURIComponent(m[1]):'';}}
if(t0&&(Date.now()-t0)>=2000){{await fetch('/cmd/parar_todo',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF':kzCsrf()}},body:JSON.stringify({{quien:'operador',motivo:'boton'}})}});late();}}t0=null;}});
</script></body></html>"""

    @app.get("/assets/panel.css")
    def css():
        return PlainTextResponse(CSS.read_text(encoding="utf-8") if CSS.exists() else "",
                                 media_type="text/css")

    @app.get("/", response_class=HTMLResponse)
    def manana(request: Request, empresa: str = "", tema: str = ""):
        r = auth_pagina(request)
        if r:
            return r
        emps = _empresas(st.k)
        empresa = _empresa_valida(empresa, defecto=emps[0])
        pend = cola(empresa).listar("PENDIENTE")
        frases = N.resumen_manana(st.k, empresa, libro=libro(), pendientes=len(pend))
        saludo = "Buenos dias." if datetime.now().hour < 15 else "Buenas tardes."
        fr = "".join(f'<p class="frase"><a href="{f["fuente"]}">{html.escape(f["texto"])}</a></p>'
                     for f in frases)
        tj = "".join(
            f'<article class="tarjeta"><h3>{html.escape(x["accion"])}</h3>'
            f'<p class="empresa-tag">{empresa}</p>'
            f'<p class="consecuencia">Si dices SI: '
            f'{"sale al mundo (con mecha de deshacer)" if x["clase"] == "IRREVERSIBLE-EXTERNA" else "se aplica dentro de Kaizen"}.</p>'
            f'<p class="caducidad">Si no haces nada: caduca a las 72 h y se aborta.</p>'
            f'<div class="botones"><button class="si" data-id="{x["id"]}">SI (manten pulsado)</button>'
            f'<button class="no" data-id="{x["id"]}">NO</button></div></article>'
            for x in pend)
        vacio = ('<p class="vacio">Nada que aprobar. Kaizen sigue trabajando; te avisare.</p>'
                 if not pend else "")
        selector = ("" if len(emps) < 2 else
                    "<nav class='selector'>" + " ".join(
                        f"<a href='/?empresa={e}' class='{'activa' if e == empresa else ''}'>{e}</a>"
                        for e in emps) + "</nav>")
        cuerpo = f"""<main class="manana">{selector}
<h1>{saludo}</h1><section class="resumen">{fr}</section>
<section id="tarjetas"><h2>Esperan tu SI</h2>{tj}{vacio}</section>
<p class="ir-sala"><a href="/sala?empresa={html.escape(empresa)}">Sala de maquinas →</a> ·
<a href="/chat?empresa={html.escape(empresa)}">Colmena — hablar con los directores →</a></p></main>
<script>document.getElementById('empresa').textContent={json.dumps(empresa)};</script>"""
        return _pagina("La Mañana — Kaizen", cuerpo, tema or st.tema)

    @app.get("/sala", response_class=HTMLResponse)
    def sala(request: Request, empresa: str = "", tema: str = ""):
        r = auth_pagina(request)
        if r:
            return r
        empresa = _empresa_valida(empresa, defecto=_empresas(st.k)[0])
        hs = N.historias(st.k, empresa, limite=12)
        hh = "".join(f'<details class="historia"><summary>{html.escape(h["ultimo"])} '
                     f'<small>({h["pasos"]} paso{"s" if h["pasos"] != 1 else ""})</small></summary><ol>'
                     + "".join(f"<li>{html.escape(f_)}</li>" for f_ in h["frases"])
                     + f'</ol><p class="tec"><a href="/sala/tecnico?empresa={html.escape(empresa)}">ver detalle tecnico</a></p></details>'
                     for h in hs) or '<p class="vacio">Aun no hay historias que contar.</p>'
        cubos_datos = _datos_cubos(empresa)["cubos"]
        cc = "".join(
            f'<div class="cubo"><h3>{html.escape(NOMBRES_CUBOS.get(c["cubo"], c["cubo"]))}</h3>'
            f'<p class="actividad">{c["actividad"]} evento{"s" if c["actividad"] != 1 else ""} registrado{"s" if c["actividad"] != 1 else ""}</p>'
            + ('<p class="controles">' + "".join(
                f'<span class="control-pastilla">{html.escape(ctrl["nombre"])}</span>'
                for ctrl in c["controles"] if ctrl["endpoint"]) + '</p>'
               if any(ctrl["endpoint"] for ctrl in c["controles"]) else "")
            + '</div>'
            for c in cubos_datos) or '<p class="vacio">Aun no hay cubos con actividad.</p>'
        cuerpo = f"""<main class="sala"><h1>Sala de maquinas</h1>
<nav class="pestanas"><a href="#historias">Historias</a> <a href="#cubos">Cubos</a>
<a href="#salud">Salud</a> <a href="#dinero">Dinero</a> <a href="#ajustes">Ajustes</a></nav>
<section id="historias"><h2>Historias</h2>{hh}</section>
<section id="cubos"><h2>Cubos</h2>{cc}</section>
<section id="salud"><h2>Salud del historial</h2>
<p id="salud-estado" class="salud pendiente">Sin comprobar todavia.</p>
<button id="comprobar-sello" class="comprobar" data-src="/api/sello/{html.escape(empresa)}">Comprobar el sello del historial</button></section>
<section id="dinero"><h2>Dinero</h2><div id="dinero-datos" data-src="/api/dinero/{html.escape(empresa)}"></div>
<p><a href="/api/dinero/{html.escape(empresa)}/export.csv">Descargar el mes (CSV)</a></p></section>
<section id="ajustes"><h2>Ajustes</h2><p class="aviso-ajustes">Esta zona cambia como trabaja Kaizen.
Cada ajuste tiene un valor recomendado al que puedes volver.</p></section>
<p><a href="/?empresa={html.escape(empresa)}">← Volver a La Mañana</a> ·
<a href="/sala/tecnico?empresa={html.escape(empresa)}">cajon tecnico</a></p></main>
<script>document.getElementById('empresa').textContent={json.dumps(empresa)};
for(const el of document.querySelectorAll('[data-src]:not(#comprobar-sello)')){{fetch(el.dataset.src).then(r=>r.json()).then(j=>{{el.textContent=j.frase||JSON.stringify(j).slice(0,400);}}).catch(()=>{{}});}}
document.getElementById('comprobar-sello').addEventListener('click', (ev) => {{
  const el = document.getElementById('salud-estado');
  el.textContent = 'Comprobando...'; el.className = 'salud pendiente';
  fetch(ev.target.dataset.src).then(r => r.json()).then(j => {{
    el.textContent = j.mensaje; el.className = 'salud ' + (j.integra ? 'ok' : 'mal');
  }}).catch(() => {{ el.textContent = 'No se pudo comprobar.'; el.className = 'salud mal'; }});
}});
</script>"""
        return _pagina("Sala de maquinas — Kaizen", cuerpo, tema or st.tema)

    @app.get("/sala/tecnico", response_class=HTMLResponse)
    def tecnico(request: Request, empresa: str = "", tema: str = ""):
        r = auth_pagina(request)
        if r:
            return r
        empresa = _empresa_valida(empresa, defecto=_empresas(st.k)[0])
        evs = sorted(st.k.all(empresa, "evento").items())[-40:]
        filas = "".join(
            f"<tr><td class='mono'>{int(c)}</td><td>{html.escape(e['tipo'])}</td>"
            f"<td>{html.escape(N.render(e, st.k, empresa))}</td>"
            f"<td class='mono sello-tinta' title='sello'>{html.escape(e.get('hash','')[:12])}</td></tr>"
            for c, e in evs)
        cuerpo = f"""<main class="tecnico"><h1>Cajon tecnico</h1>
<p>Rio crudo (ultimos 40) · <a href="/rio/{html.escape(empresa)}?desde=-1&ciclos=1">stream</a> ·
paridad de tipos de evento cubiertos: <span id="par" data-src="/api/paridad"></span></p>
<table><thead><tr><th>nº</th><th>tipo</th><th>frase</th><th>sello</th></tr></thead>
<tbody>{filas}</tbody></table>
<p><a href="/sala?empresa={html.escape(empresa)}">← Sala</a></p></main>
<script>fetch('/api/paridad').then(r=>r.json()).then(j=>{{document.getElementById('par').textContent=j.cubiertos+'/'+j.total;}});</script>"""
        return _pagina("Cajon tecnico — Kaizen", cuerpo, tema or st.tema)

    app.state.quemar_vencidas = quemar_vencidas

    # Colmena (chat de directores): mismas guardas (auth/CSRF/identidad), cero
    # duplicados — ver panel_mando/colmena.py.
    from panel_mando import colmena as CLM
    CLM.registrar(app, auth=auth, auth_pagina=auth_pagina, identidad=identidad,
                  cola=cola, bit=bit, libro=libro, pagina=_pagina,
                  empresas=lambda: _empresas(st.k))
    return app


def main() -> None:                                # pragma: no cover
    """Arranque del operador. AQUI (y solo aqui) se carga .env: el panel del
    operador SIEMPRE ve su KAIZEN_TOKEN (R-01); los tests jamas lo cargan."""
    import argparse
    import socket
    import threading
    import webbrowser

    import uvicorn
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    ap = argparse.ArgumentParser(prog="panel_mando")
    ap.add_argument("--abrir", action="store_true",
                    help="abre el navegador ya autenticado (un toque, R8)")
    args = ap.parse_args()
    token = os.getenv("KAIZEN_TOKEN") or None
    url = ("http://127.0.0.1:8600/" if not token
           else f"http://127.0.0.1:8600/login?token={token}")

    # Mismo patron que panel_mando/colmena.py::main(): sin este chequeo, un
    # doble clic en CENTRO DE MANDO.cmd cuando el panel ya corria intentaba
    # bind() sobre el 8600 ya ocupado, reventaba dentro de una ventana
    # minimizada, y el navegador se abria igual contra la instancia original
    # — el fallo pasaba inadvertido salvo que el operador fuese a buscarlo.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        ya_corre = s.connect_ex(("127.0.0.1", 8600)) == 0
    if ya_corre:
        print("El Centro de Mando ya corre en 8600; abro el navegador.")
        if args.abrir:
            webbrowser.open(url)
        return

    # R-TENANT: el estado (panico, ledger) es DATO y vive en la raiz de datos,
    # no en el arbol del repo. Antes apuntaba a RAIZ/state (residuo pre-F5); un
    # PARAR TODO persistido alli y la Colmena leyendo KAIZEN_DATOS habrian sido
    # dos memorias de panico distintas.
    from core import rutas as R
    app = crear_app(token=token,
                    ruta_panico=R.dir_state() / "panico" / "estado.json",
                    ruta_ledger=R.dir_state() / "coste" / "ledger.jsonl",
                    ruta_legacy_coste=RAIZ / ".kaizen_cost.json")
    if args.abrir:
        threading.Timer(2.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=8600)
