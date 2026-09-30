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


def crear(datos: Path, mecha_s: int = 6):
    """Devuelve la app real con las rutas de control de ensayo montadas."""
    os.environ["KAIZEN_DATOS"] = str(datos)
    os.environ.pop("KAIZEN_TOKEN", None)
    from fastapi import Request

    from core.aprobaciones import ColaSustrato
    from core.knowledge import JsonKnowledge
    from core.rue import Bitacora, Sobre
    from panel_mando.app import crear_app
    from sustrato import bus

    k = JsonKnowledge(datos / "knowledge.json")          # persistente: el backend se puede reiniciar sin perder la cadena
    app = crear_app(k, mecha_s=mecha_s, ruta_ledger=datos / "ledger.jsonl")     # ledger de coste activo (si no, queda inerte)
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

    @app.get("/_e2e/estado")
    async def e2e_estado():
        return {"colas": sorted(st.colas), "eventos": len(k.all(EMPRESA, "evento"))}

    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8620)
    ap.add_argument("--datos", default="")
    ap.add_argument("--mecha", type=int, default=6)
    a = ap.parse_args()
    datos = Path(a.datos) if a.datos else Path(tempfile.mkdtemp(prefix="kaizen_e2e_"))
    datos.mkdir(parents=True, exist_ok=True)
    import uvicorn
    uvicorn.run(crear(datos, a.mecha), host="127.0.0.1", port=a.puerto, log_level="warning")


if __name__ == "__main__":
    main()
