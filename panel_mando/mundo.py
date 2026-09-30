# -*- coding: utf-8 -*-
"""Mundo — la vista isometrica de Kaizen servida en el MISMO origen del panel.

El juego (`mundo/index.html`) es una proyeccion mas del sustrato, como el resto
del panel: aqui NO hay almacen propio ni escritura. Este modulo aporta solo
tres cosas —una ruta de pagina y dos endpoints de LECTURA— y reutiliza los
existentes tal cual para actuar (/cmd/aprobar|denegar|deshacer|parar_todo|
reanudar, /api/csrf, /api/tarjetas, /api/sello, /api/dinero, /latido):
  - GET /mundo               la pagina estatica (se lee de disco en cada peticion).
  - GET /api/mundo/estado    foto completa de una empresa: cubos, dinero, tarjetas...
  - GET /api/mundo/rio       SSE que une la bitacora RUE, el bus del sustrato y el chat de la Colmena.

Reglas que este fichero se impone:
  * SOLO LECTURA y sin efectos secundarios en `estado`. En particular NO se
    llama a `_alta_empresa` (la ruta /api/colmena/agentes da de alta a los 10
    directores al LEERLA): las tablas colmena_* se consultan solo si existen y
    jamas se crean; sin tabla, todos los cubos salen `alta:false`. Unica
    excepcion, deliberada: si faltan las tablas de infraestructura del bus o
    del coste (vacias, IF NOT EXISTS), se instalan para que la salud del cubo
    sea medible en vez de un «SIN DATOS» permanente en una instalacion nueva.
  * Todo lo que sale es JSON (ensure_ascii=False); nunca HTML interpolado. La
    unica pieza HTML es el fichero estatico de /mundo.
  * Aislamiento de tenant (R-TENANT): del bus solo salen eventos sin clave
    `empresa` en el payload (globales) o con la empresa pedida. Nunca se
    filtran datos de otro tenant, y de cada evento del bus solo sale una frase
    derivada del topic: el payload no viaja.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from panel_mando import colmena as CLM
from panel_mando import nucleo as N
from panel_mando import rendimiento as REND
from panel_mando.herramientas import rrhh as RRHH
from sustrato import bus, coste
from sustrato.consola import ts_iso8601z

RAIZ = Path(__file__).resolve().parent.parent
LIMITE_POR_CICLO = 200          # tope de eventos por ciclo y canal (SSE)
LIMITE_RECIENTES = 40

# Prefijo del RUE -> cubo de colmena (los nombres de la Colmena, no los del RUE).
CUBO_POR_PREFIJO_RUE = {
    "comercial": "comercial", "brand": "brand", "finanzas": "finanzas",
    "operacion": "ops", "marketing": "marketing",
    "inteligencia": "inteligencia", "cumplimiento": "legal",
    "plataforma": None,
}


# ── conversion de eventos al formato unificado ───────────────────────────────

def _cubo_de_rue(tipo: str, payload: dict) -> str | None:
    """Cubo por prefijo del tipo; si el payload declara uno CONOCIDO, manda el
    payload (p. ej. una aprobacion de Marca es de `brand` aunque el tipo sea
    `plataforma.aprobacion.*`)."""
    declarado = (payload or {}).get("cubo")
    if isinstance(declarado, str) and declarado in CLM.CUBOS_ORDEN:
        return declarado
    return CUBO_POR_PREFIJO_RUE.get((tipo or "").split(".")[0])


def evento_rue(n: int, e: dict) -> dict:
    """Evento de la bitacora RUE -> formato unificado."""
    tipo = str(e.get("tipo", ""))
    payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
    aprobacion = None
    if tipo.startswith("plataforma.aprobacion."):
        ref = payload.get("aprobacion_ref")        # clave real: core/aprobaciones.py
        aprobacion = str(ref) if ref else None
    return {"canal": "rue", "id": int(n), "tipo": tipo,
            "cubo": _cubo_de_rue(tipo, payload), "frase": N.render(e),
            "ts": e.get("ts", ""), "aprobacion": aprobacion}


def _frase_bus(topic: str) -> tuple[str | None, str]:
    """`kaizen.<cubo>.<evento_en_pasado>.v<n>` -> (cubo|None, frase legible)."""
    partes = topic.split(".")
    seg = partes[1] if len(partes) > 1 else ""
    evento = partes[2].replace("_", " ") if len(partes) > 2 else topic
    # Segmento de cubo de colmena o alias del RUE (operacion, cumplimiento...);
    # `colmena` y lo desconocido -> null.
    cubo = seg if seg in CLM.NOMBRES else CUBO_POR_PREFIJO_RUE.get(seg)
    quien = CLM.NOMBRES.get(cubo or seg, seg.capitalize())
    return cubo, (f"{quien}: {evento}" if seg else evento)


def evento_bus(id_: int, ts: str, topic: str) -> dict:
    cubo, frase = _frase_bus(topic)
    return {"canal": "bus", "id": int(id_), "tipo": topic, "cubo": cubo,
            "frase": frase, "ts": ts, "aprobacion": None}


def _clave_ts(ev: dict):
    """RUE guarda `+00:00` y el bus `Z`: se ordena por instante, no por texto."""
    try:
        d = datetime.fromisoformat(str(ev["ts"]).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (d.timestamp(), ev["canal"], ev["id"])
    except (ValueError, KeyError):
        return (0.0, ev.get("canal", ""), ev.get("id", 0))


# ── lecturas (jamas escriben) ────────────────────────────────────────────────

def _tabla_existe(conn: sqlite3.Connection, nombre: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nombre,)).fetchone() is not None


def _eventos_bus(conn, empresa: str, *, desde: int | None = None,
                 limite: int = LIMITE_POR_CICLO) -> tuple[list[dict], int]:
    """Eventos del bus visibles para `empresa`, ascendentes por id, y el mayor
    id ESCANEADO (los ajenos tambien avanzan el cursor: no se reintentan).
    `desde=None` = los ultimos `limite` (para `recientes`)."""
    if not _tabla_existe(conn, "bus_eventos"):
        return [], (desde if desde is not None else 0)
    if desde is None:
        filas = conn.execute("SELECT id, ts, topic, payload FROM bus_eventos "
                             "ORDER BY id DESC LIMIT ?", (limite,)).fetchall()[::-1]
    else:
        filas = conn.execute("SELECT id, ts, topic, payload FROM bus_eventos "
                             "WHERE id>? ORDER BY id ASC LIMIT ?", (desde, limite)).fetchall()
    out, ultimo = [], (desde if desde is not None else 0)
    for id_, ts, topic, payload in filas:
        ultimo = max(ultimo, id_)
        try:
            p = json.loads(payload)
        except (TypeError, ValueError):
            p = {}
        dueno = p.get("empresa") if isinstance(p, dict) else None
        if dueno is not None and dueno != empresa:
            continue                                    # dato de otro tenant: jamas
        out.append(evento_bus(id_, ts, topic))
    return out, ultimo


def _ultimo_id_bus(conn) -> int:
    if not _tabla_existe(conn, "bus_eventos"):
        return 0
    return int(conn.execute("SELECT COALESCE(MAX(id),0) FROM bus_eventos").fetchone()[0])


def evento_chat(id_: int, ts: str, sala: bool, autor_tipo: str, autor_id: str,
                cubo_sesion: str, texto: str, ap_id: str | None) -> dict:
    """Mensaje del chat de la Colmena -> formato unificado. El TIPO lleva quien y donde
    (`colmena.sala.director`, `colmena.individual.director`, `colmena.individual.operador`,
    `colmena.sala.operador`); `cubo` solo se rellena para un director (el que habla)."""
    cubo = None
    if autor_tipo == "director":
        c = str(autor_id).removeprefix("director_")
        cubo = c if c in CLM.NOMBRES else (cubo_sesion or None)
    frase = texto if autor_tipo == "director" else f"Tú: {texto}"
    return {"canal": "chat", "id": int(id_), "tipo": f"colmena.{'sala' if sala else 'individual'}.{autor_tipo}",
            "cubo": cubo, "frase": frase, "ts": ts, "aprobacion": ap_id or None}


def _mensajes_chat(conn, empresa: str, *, desde: int, limite: int = LIMITE_POR_CICLO) -> tuple[list[dict], int]:
    """Mensajes de directores y del operador (no las notas de sistema) con id > `desde`,
    ascendentes, y el mayor id visto. Sin las tablas de Colmena: nada. Nunca crea nada."""
    if not (_tabla_existe(conn, "colmena_mensajes") and _tabla_existe(conn, "colmena_sesiones")):
        return [], max(desde, 0)
    filas = conn.execute(
        "SELECT m.id, m.ts, s.tipo, m.autor_tipo, m.autor_id, s.cubo, m.texto, m.ap_id "
        "FROM colmena_mensajes m JOIN colmena_sesiones s ON s.id=m.sesion_id "
        "WHERE s.empresa=? AND m.id>? AND m.autor_tipo IN ('director','operador') "
        "ORDER BY m.id ASC LIMIT ?", (empresa, desde, limite)).fetchall()
    ultimo = desde
    out = []
    for id_, ts, tipo_s, atipo, aid, cubo_s, texto, ap in filas:
        ultimo = max(ultimo, id_)
        out.append(evento_chat(id_, ts, tipo_s == "sala", atipo, aid, cubo_s or "", str(texto), ap))
    return out, ultimo


def _ultimo_id_chat(conn) -> int:
    if not _tabla_existe(conn, "colmena_mensajes"):
        return 0
    return int(conn.execute("SELECT COALESCE(MAX(id),0) FROM colmena_mensajes").fetchone()[0])


def _agentes_y_ultimos(conn, empresa: str) -> tuple[dict, dict]:
    """(cubo -> fila de colmena_agentes, cubo -> ultimo mensaje individual).
    Sin las tablas: dicts vacios. Nunca crea nada."""
    agentes, ultimos = {}, {}
    if _tabla_existe(conn, "colmena_agentes"):
        for cubo, role, uid, ts in conn.execute(
                "SELECT cubo, role_id, uid, ts_alta FROM colmena_agentes WHERE empresa=?",
                (empresa,)):
            agentes[cubo] = {"role_id": role, "uid": uid, "ts_alta": ts}
    if _tabla_existe(conn, "colmena_sesiones") and _tabla_existe(conn, "colmena_mensajes"):
        for cubo, texto, ts in conn.execute(
                "SELECT s.cubo, m.texto, m.ts FROM colmena_sesiones s "
                "JOIN colmena_mensajes m ON m.id=(SELECT MAX(id) FROM colmena_mensajes "
                "WHERE sesion_id=s.id) WHERE s.empresa=? AND s.tipo='individual'",
                (empresa,)):
            ultimos[cubo] = {"texto": texto[:80], "ts": ts}
    return agentes, ultimos


def _cubos_instalados() -> list[str]:
    """Orden de la Colmena; los instalados fuera de ese orden, al final por nombre."""
    instalados = set(CLM._manifiestos())
    return ([c for c in CLM.CUBOS_ORDEN if c in instalados]
            + sorted(instalados - set(CLM.CUBOS_ORDEN)))


def registrar(app, *, auth, auth_pagina, cola, bit, empresas, empresa_valida,
              dinero, quemar_vencidas) -> None:
    """Cuelga /mundo y /api/mundo/* del panel. Recibe las closures de crear_app
    (auth, cola, bit, dinero...) para no duplicar ningun guardian ni logica."""
    st = app.state

    def _conn_lectura() -> sqlite3.Connection:
        conn = bus.conexion()
        # Solo infraestructura vacia (nunca datos de Colmena) y solo si falta.
        if not _tabla_existe(conn, "bus_eventos"):
            bus.instalar(conn)
        if not _tabla_existe(conn, "costes"):
            coste.instalar(conn)
        return conn

    def _cursor_rue(empresa: str) -> int:
        claves = [int(c) for c in st.k.all(empresa, "evento")]
        return max(claves) if claves else -1        # la cadena empieza en n=0: vacia = -1, para no saltarse el primero

    def _recientes(empresa: str, conn) -> list[dict]:
        rue = [evento_rue(int(c), e) for c, e in
               sorted(st.k.all(empresa, "evento").items(), key=lambda kv: int(kv[0]))
               [-LIMITE_RECIENTES:]]
        del_bus, _ = _eventos_bus(conn, empresa, limite=LIMITE_POR_CICLO)
        return sorted(rue + del_bus, key=_clave_ts)[-LIMITE_RECIENTES:]

    def _tarjetas(empresa: str) -> dict:
        """`pendientes` (numero) y `mechas` (cuenta atras viva de esa empresa,
        con el texto y el cubo del nodo de la cola). El detalle de las tarjetas
        pendientes lo da /api/tarjetas/{empresa}."""
        nodos = {x["id"]: x for x in cola(empresa).listar()}
        mechas = []
        for m in st.mechas.encendidas():
            if m["empresa"] != empresa:
                continue
            n = nodos.get(m["aprobacion"], {})
            mechas.append({"aprobacion": m["aprobacion"], "dispara": m["dispara"],
                           "accion": n.get("accion", ""), "cubo": n.get("cubo", "")})
        return {"pendientes": sum(1 for x in nodos.values() if x["estado"] == "PENDIENTE"),
                "mechas": mechas}

    def _rendimiento(empresa: str, conn, cubos: list[dict]) -> dict:
        """Lee coste, pedidos y decisiones reales y aplica panel_mando/rendimiento.py. Si algo falla
        devuelve vacio (el juego lo muestra como «sin medir»), nunca un grado inventado."""
        try:
            costes = []
            if _tabla_existe(conn, "costes"):
                costes = [{"cubo": r[0], "ts": r[1], "coste_eur": r[2]} for r in conn.execute(
                    "SELECT cubo, ts, coste_eur FROM costes WHERE estado = 'liquidado'")]
            pedidos = list(st.k.all(empresa, "pedido_atribuido").values())
            return REND.rendimiento_desde(cubos, costes, pedidos, cola(empresa).listar())
        except Exception:                                    # noqa: BLE001
            return {}

    def _sello(empresa: str) -> dict:
        """Verificacion real y completa de la cadena en cada foto: un sello roto se ve al momento."""
        try:
            v = bit(empresa).verificar()
            if v.get("integra"):
                return {"integra": True, "pasos": int(v.get("eventos", 0)),
                        "mensaje": f"Historial sellado intacto: {v.get('eventos', 0)} pasos comprobados."}
            return {"integra": False, "pasos": 0,
                    "mensaje": f"ATENCION: el sello se rompe en el paso {int(v['punto_ruptura'])}."}
        except Exception as exc:                             # noqa: BLE001
            return {"integra": False, "pasos": 0, "mensaje": f"sello no verificable: {type(exc).__name__}"}

    @app.get("/mundo", response_class=HTMLResponse)
    def mundo_pagina(request: Request, empresa: str = ""):
        r = auth_pagina(request)
        if r:
            return r
        empresa_valida(empresa, defecto=empresas()[0])       # 400 si invalida; no se interpola
        ruta = RAIZ / "mundo" / "index.html"
        try:
            html = ruta.read_text(encoding="utf-8")          # en cada peticion: sin cache de proceso
        except OSError:
            raise HTTPException(404, "el mundo no esta instalado: falta mundo/index.html")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/mundo/estado")
    def mundo_estado(request: Request, empresa: str = ""):
        auth(request)
        emps = empresas()
        empresa = empresa_valida(empresa, defecto=emps[0])
        try:
            from core import tenants as T
            estado_tenant = T.get_tenant(empresa, st.ruta_registro)["estado"]
        except Exception:                                    # noqa: BLE001
            estado_tenant = "desconocido"

        conn = _conn_lectura()
        try:
            agentes, ultimos = _agentes_y_ultimos(conn, empresa)
            manifiestos = CLM._manifiestos()
            cubos = []
            for cubo in _cubos_instalados():
                man = manifiestos.get(cubo, {})
                a = agentes.get(cubo)
                salud = CLM._salud_cubo(conn, cubo, empresa=empresa, knowledge=st.k)
                cubos.append({
                    "cubo": cubo, "nombre": CLM.NOMBRES.get(cubo, cubo),
                    "mision": man.get("descripcion", "SIN DATOS"),
                    "autonomia": man.get("nivel_autonomia_defecto", "CERO"),
                    "irreversibles": man.get("acciones_irreversibles", []) or [],
                    "nota_estado": man.get("nota_estado", ""),
                    "alta": a is not None,
                    "uid": a["uid"] if a else None,
                    "role_id": a["role_id"] if a else None,
                    "ts_alta": a["ts_alta"] if a else None,
                    "salud": {"estado": salud.get("estado", "SIN DATOS"),
                              "detalle": salud.get("detalle", ""),
                              "eventos_24h": int((salud.get("contadores") or {})
                                                 .get("eventos_publicados_24h", 0))},
                    "ultimo": ultimos.get(cubo),
                })
            rend = _rendimiento(empresa, conn, cubos)
            for c in cubos:
                c["rendimiento"] = rend.get(c["cubo"])
            cursor_bus = _ultimo_id_bus(conn)
            cursor_chat = _ultimo_id_chat(conn)
            recientes = _recientes(empresa, conn)
        finally:
            conn.close()

        sello = _sello(empresa)

        # RRHH: el mapa y las propuestas del cubo RRHH real (panel_mando/herramientas/rrhh.py),
        # calculados con sus funciones puras sobre estos mismos datos: el juego no reimplementa nada.
        mapa = RRHH.mapa_desde([c["cubo"] for c in cubos], [c["cubo"] for c in cubos if c["alta"]])
        return JSONResponse({
            "empresa": empresa, "empresas": emps, "ahora": ts_iso8601z(),
            "parado": bool(st.panico.activo),
            "tenant": {"estado": estado_tenant},
            "cubos": cubos,
            "dinero": dinero(empresa),
            "tarjetas": _tarjetas(empresa),
            "sello": sello,
            "rrhh": {"mapa": mapa, "propuestas": RRHH.propuestas_desde(mapa)},
            "cursores": {"rue": _cursor_rue(empresa), "bus": cursor_bus, "chat": cursor_chat},
            "recientes": recientes,
        })

    @app.get("/api/mundo/rio")
    async def mundo_rio(request: Request, empresa: str = "", desde_rue: int = -1,
                        desde_bus: int = -1, desde_chat: int = -1, ciclos: int = 0):
        auth(request)
        empresa = empresa_valida(empresa, defecto=empresas()[0])

        def leer_bus(cursor: int):
            conn = _conn_lectura()
            try:
                return _eventos_bus(conn, empresa, desde=cursor)
            finally:
                conn.close()

        def leer_chat(cursor: int):
            conn = _conn_lectura()
            try:
                return _mensajes_chat(conn, empresa, desde=cursor)
            finally:
                conn.close()

        def emitir(ev: dict) -> str:
            # U+2028/2029 crudos: JSON valido, pero muchos lectores de lineas
            # (splitlines, proxies) los parten en dos; escapados siguen siendo JSON.
            dato = (json.dumps(ev, ensure_ascii=False)
                    .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
            return f"id: {ev['canal']}:{ev['id']}\ndata: {dato}\n\n"

        async def gen():
            c_rue, c_bus, c_chat = desde_rue, desde_bus, desde_chat
            restantes = ciclos if ciclos > 0 else 10 ** 9
            while restantes > 0:
                restantes -= 1
                try:                       # mismo pulso que /rio: quema mechas vencidas
                    await asyncio.to_thread(quemar_vencidas)
                except Exception:          # noqa: BLE001 — no debe matar el stream
                    pass
                # Canal RUE (claves numericas, tal como /rio). Tope por ciclo.
                nuevos = [(int(c), e) for c, e in st.k.all(empresa, "evento").items()
                          if int(c) > c_rue]
                for n, e in sorted(nuevos, key=lambda x: x[0])[:LIMITE_POR_CICLO]:
                    c_rue = n
                    yield emitir(evento_rue(n, e))
                # Canal bus (con cursor propio; la lectura sqlite va a un hilo).
                try:
                    evs, c_bus = await asyncio.to_thread(leer_bus, c_bus)
                except Exception:          # noqa: BLE001 — bus caido: el RUE sigue
                    evs = []
                for ev in evs:
                    yield emitir(ev)
                # Canal chat de la Colmena: lo que dicen los directores y el operador.
                try:
                    msgs, c_chat = await asyncio.to_thread(leer_chat, c_chat)
                except Exception:          # noqa: BLE001 — sin chat, el resto sigue
                    msgs = []
                for ev in msgs:
                    yield emitir(ev)
                yield ": latido\n\n"
                if restantes > 0:
                    await asyncio.sleep(0.05 if ciclos else 1.0)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store"})
