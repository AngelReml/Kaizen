"""Servidor de ENSAYO para las pruebas de extremo a extremo del Mundo (tests/e2e/mundo.e2e.js).

Arranca la app REAL del Centro de Mando (`crear_app`) sobre un directorio de datos temporal (tenant sintético `laboratorio`, nunca datos de cliente) y le añade unas rutas
`/_e2e/*` SOLO en este proceso de prueba, para provocar hechos por los caminos reales del
backend: la bitácora sellada, el bus del sustrato y la cola de aprobaciones. Nada de esto existe
en el producto: el Mundo no sabe que estas rutas existen.

Uso:  python tests/e2e/servidor_e2e.py --puerto 8620 [--datos DIR] [--mecha 6]
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

EMPRESA = "laboratorio"


def crear(datos: Path, mecha_s: int = 6, token: str | None = None):
    """Devuelve la app real con las rutas de control de ensayo montadas."""
    os.environ["KAIZEN_DATOS"] = str(datos)
    os.environ.pop("KAIZEN_TOKEN", None)          # el token entra por parametro, no por el entorno
    from fastapi import Request

    from core.aprobaciones import ColaSustrato
    from core.knowledge import JsonKnowledge
    from core.rue import Bitacora, Sobre
    from panel_mando.app import crear_app
    from sustrato import bus

    k = JsonKnowledge(datos / "knowledge.json")          # persistente: el backend se puede reiniciar sin perder la cadena
    app = crear_app(k, token=token, mecha_s=mecha_s, ruta_ledger=datos / "ledger.jsonl")     # ledger de coste activo (si no, queda inerte)
    st = app.state

    def bitacora() -> Bitacora:
        if EMPRESA not in st.bitacoras:
            st.bitacoras[EMPRESA] = Bitacora(k, EMPRESA, fecha_alta="2026-07-10")
        return st.bitacoras[EMPRESA]

    def cola() -> ColaSustrato:
        if EMPRESA not in st.colas:
            st.colas[EMPRESA] = ColaSustrato(k, EMPRESA, bitacora=bitacora())
        return st.colas[EMPRESA]

    @app.post("/_e2e/evento")
    async def e2e_evento(request: Request):
        d = await request.json()
        s = bitacora().publicar(Sobre(tenant_id=EMPRESA, tipo=d["tipo"], payload=d.get("payload", {}),
                                      origen="e2e", correlacion_id=d.get("hilo", "")))
        return {"ok": True, "tipo": s.tipo}

    @app.post("/_e2e/lead")
    async def e2e_lead(request: Request):
        """Solo pruebas: deja leads sintéticos en un estado del embudo (sin datos de personas)."""
        d = await request.json()
        for i in range(int(d.get("n", 1))):
            k.add(EMPRESA, "lead_canon", f"{d['estado'].lower()}_{i}", {"id": f"{d['estado'].lower()}_{i}", "estado": d["estado"]})
        return {"ok": True}

    @app.post("/_e2e/mkt")
    async def e2e_mkt(request: Request):
        """Solo pruebas: campanas y contenidos sinteticos de Marketing (sin textos ni nombres reales)."""
        d = await request.json()
        for i, (estado, pres, gasto) in enumerate(d.get("campanas", [])):
            k.add(EMPRESA, "campana", f"c{i}", {"id": f"c{i}", "nombre": f"campana {i}", "estado": estado, "presupuesto_eur": pres, "gasto_reportado_eur": gasto, "metricas": []})
        for estado, n in d.get("contenidos", {}).items():
            for i in range(int(n)):
                k.add(EMPRESA, "contenido_mkt", f"t_{estado}_{i}", {"id": f"t_{estado}_{i}", "estado": estado, "texto": "x"})
        return {"ok": True}

    @app.post("/_e2e/marca")
    async def e2e_marca(request: Request):
        """Solo pruebas: veredictos y directrices sinteticos de Marca (sin reglas ni textos)."""
        d = await request.json()
        for v, n in d.get("veredictos", {}).items():
            for _ in range(int(n)):
                bitacora().publicar(Sobre(tenant_id=EMPRESA, tipo="plataforma.verificacion.emitida", payload={"veredicto": v, "hash": "h"}, origen="e2e"))
        for i in range(int(d.get("directrices", 0))):
            k.add(EMPRESA, "directriz", f"d{i}", {"id": f"d{i}", "estado": "ACTIVA"})
        return {"ok": True}

    @app.post("/_e2e/legal")
    async def e2e_legal(request: Request):
        """Solo pruebas: obligaciones sinteticas de Legal (sin nombres ni fuentes reales)."""
        from datetime import datetime, timedelta, timezone
        d = await request.json()
        ahora = datetime.now(timezone.utc)
        for i, (estado, dias) in enumerate(d.get("obligaciones", [])):
            k.add(EMPRESA, "obligacion", f"o{i}", {"id": f"o{i}", "nombre": f"obligacion {i}", "tipo": "OPERATIVA", "estado": estado,
                                                   "fecha_limite": (ahora + timedelta(days=dias, hours=1)).isoformat(), "evidencias": []})
        for i in range(int(d.get("evidencias", 0))):
            k.add(EMPRESA, "evidencia", f"e{i}", {"id": f"e{i}"})
        return {"ok": True}

    @app.post("/_e2e/bus")
    async def e2e_bus(request: Request):
        d = await request.json()
        conn = bus.conexion()
        try:
            bus.instalar(conn)
            bus.publicar(conn, d["topic"], d.get("productor", "e2e"), d.get("payload", {}))
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/_e2e/bus_dias")
    async def e2e_bus_dias(request: Request):
        """Solo pruebas: eventos del bus con fecha retrasada (para ver el pulso de 14 dias). Rompe la cadena de hash del bus
        de ENSAYO a proposito; la del sello de la bitacora (la que verifica el juego) no se toca."""
        from datetime import datetime, timedelta, timezone
        d = await request.json()
        conn = bus.conexion()
        try:
            bus.instalar(conn)
            for dias in d["dias_atras"]:
                i = bus.publicar(conn, d["topic"], "e2e", {})
                ts = (datetime.now(timezone.utc) - timedelta(days=int(dias))).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute("UPDATE bus_eventos SET ts = ? WHERE id = ?", (ts, i))
                conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/_e2e/aprobacion")
    async def e2e_aprobacion(request: Request):
        d = await request.json()
        n = cola().solicitar(cubo=d.get("cubo", "comercial"), accion=d["accion"],
                             clase=d.get("clase", "IRREVERSIBLE-INTERNA"), contenido_ref=d.get("ref", ""))
        return {"ok": True, "id": n["id"]}

    @app.post("/_e2e/romper_sello")
    async def e2e_romper():
        clave = sorted(k.all(EMPRESA, "evento"))[0]
        ev = k.get(EMPRESA, "evento", clave)
        ev["payload"] = {"manipulado": True}
        k.add(EMPRESA, "evento", clave, ev)
        return {"ok": True, "clave": clave}

    @app.post("/_e2e/coste")
    async def e2e_coste(request: Request):
        """Gasto de hoy en el contador del sustrato (limite propio de los cubos, 16 € por defecto): lleva su salud a DEGRADADO."""
        from sustrato import coste
        d = await request.json()
        conn = bus.conexion()
        try:
            coste.instalar(conn)
            coste.registrar(conn, "otro", "e2e", 1, float(d["eur"]))
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/_e2e/cubo_nuevo")
    async def e2e_cubo_nuevo():
        """Un cubo NUEVO en el catalogo (manifest instalado en disco): el edificio debe reservarle un solar."""
        import json as _json
        import cubos.base as cb
        ruta = datos / "cubo_prueba" / "manifest.json"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(_json.dumps({"cubo": "prueba", "version": "1.0.0", "descripcion": "Cubo de ensayo (e2e)",
                                     "produce": [], "consume": [], "nivel_autonomia_defecto": "CERO",
                                     "acciones_irreversibles": [], "requiere": []}), encoding="utf-8")
        orig = getattr(cb, "_e2e_original", None) or cb.manifiestos_instalados
        cb._e2e_original = orig
        cb.manifiestos_instalados = lambda: {**orig(), "prueba": ruta}
        return {"ok": True}

    @app.post("/_e2e/alta_cubo")
    async def e2e_alta_cubo():
        """Alta del director del cubo nuevo, como la hace la Colmena (fila + evento sellado en el bus)."""
        from panel_mando import colmena as CLM
        conn = CLM._conn()
        try:
            with bus.transaccion(conn):
                conn.execute("INSERT OR IGNORE INTO colmena_agentes (empresa, cubo, role_id, uid, ts_alta, evento_alta_id) VALUES (?,?,?,?,?,NULL)",
                             (EMPRESA, "prueba", "director_prueba", "KZ-PRUEBA-E2E", "2026-09-30T10:00:00Z"))
                bus.publicar_en_tx(conn, "kaizen.colmena.agente_registrado.v1", "colmena",
                                   {"empresa": EMPRESA, "cubo": "prueba", "role_id": "director_prueba", "uid": "KZ-PRUEBA-E2E", "duenio": "operador"})
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/_e2e/gasto")
    async def e2e_gasto(request: Request):
        """Gasto de hoy en el ledger de coste del tenant (el que ve la Tesorería y el que activa el modo ahorro)."""
        d = await request.json()
        st.ledger.asentar(EMPRESA, cubo="comercial", rol="director_comercial", clase="herramienta_aprobada",
                          proveedor="anthropic", coste_eur=float(d["eur"]), causa_id="e2e")
        return {"ok": True}

    @app.post("/_e2e/chat")
    async def e2e_chat(request: Request):
        """Un mensaje en el chat de la Colmena (sala si `cubo` es null), por el camino real que sella en el bus."""
        from panel_mando import colmena as CLM
        d = await request.json()
        conn = CLM._conn()
        try:
            tipo, cubo = ("sala", "") if not d.get("cubo") else ("individual", d["cubo"])
            ses = conn.execute("SELECT id FROM colmena_sesiones WHERE empresa=? AND tipo=? AND cubo=?", (EMPRESA, tipo, cubo)).fetchone()[0]
            autor = d.get("autor", "director")
            quien = d.get("autor_cubo") or d.get("cubo")                # en la sala habla un director concreto
            aid = ("director_" + quien) if autor == "director" and quien else d.get("autor_id", "operador")
            CLM._insertar_mensaje(conn, ses, autor, aid, d["texto"])
        finally:
            conn.close()
        return {"ok": True}

    @app.post("/_e2e/caducar_sesiones")
    async def e2e_caducar():
        """La sesion del navegador caduca en el servidor (como al pasar el TTL o reiniciar)."""
        st.sesiones.clear()
        st.csrf.clear()
        return {"ok": True}

    @app.get("/_e2e/estado")
    async def e2e_estado():
        return {"colas": sorted(st.colas), "eventos": len(k.all(EMPRESA, "evento"))}

    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8620)
    ap.add_argument("--datos", default="")
    ap.add_argument("--mecha", type=int, default=6)
    ap.add_argument("--token", default="", help="modo con clave: sesion, cookie y CSRF de verdad")
    a = ap.parse_args()
    datos = Path(a.datos) if a.datos else Path(tempfile.mkdtemp(prefix="kaizen_e2e_"))
    datos.mkdir(parents=True, exist_ok=True)
    import uvicorn
    uvicorn.run(crear(datos, a.mecha, a.token or None), host="127.0.0.1", port=a.puerto, log_level="warning")


if __name__ == "__main__":
    main()
