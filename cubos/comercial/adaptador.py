"""Adaptador del cubo Comercial (canonico 3.2-3.4).

Implementa el ciclo de vida del contrato de cubo delegando en el sustrato y
SIN reescribir los modulos existentes (core/, departments/): estos siguen
operando sobre state/knowledge.json; el registro P9 es la verdad comercial
nueva y la migracion (migrar_desde_knowledge) puebla las tablas desde los
datos reales. Punto de enganche decidido en Bloque 2 y documentado en el
informe: las escrituras nuevas entran por sustrato/registro.py (que publica
los eventos del manifest); los modulos existentes no se tocan sin orden.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sustrato import bus, config, coste, registro
from sustrato.consola import log, ts_iso8601z

_RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_MANIFEST = Path(__file__).resolve().parent / "manifest.json"
def ruta_knowledge_defecto():
    from core.rutas import dir_state
    return dir_state() / "knowledge.json"

# Mapeos de migracion desde el corpus real (Bloque 0/2, documentados en informe)
MAPEO_ESTADO_12A7 = {
    "cold": "COLD", "queued": "COLD",
    "contacting": "CONTACTADO", "no_answer": "CONTACTADO", "contacted": "CONTACTADO",
    "engaged": "INTERESADO",
    "sample_requested": "COMPROMETIDO", "sample_sent": "COMPROMETIDO", "trial": "COMPROMETIDO",
    "customer": "CLIENTE",
    "lost": "DESCARTADO", "do_not_call": "NO_LLAMAR",
}
MAPEO_SEGMENTO = {
    "cafeteria_especialidad": "cafeteria_especialidad",
    "hotel_boutique_con_desayuno": "hotel_boutique",
    "restaurante_con_postre_artesanal": "restaurante_ticket_30_50",
    "tienda_gourmet_delicatessen": "otro",
    "catering_regional_premium": "otro",
}


class CuboComercial:
    """Contrato de cubo (canonico 3.2). Arranque sin pares garantizado."""

    def __init__(self, conn: sqlite3.Connection | None = None,
                 cliente_id: str = "laboratorio") -> None:
        self.cliente_id = cliente_id
        self._conn = conn if conn is not None else bus.conexion()
        self._consumidores_activos: list[str] = []
        config.validar_manifest(RUTA_MANIFEST)
        self.manifest = json.loads(RUTA_MANIFEST.read_text(encoding="utf-8"))

    # -- ciclo de vida ------------------------------------------------------
    def instalar(self) -> None:
        """Crea SUS tablas si no existen (idempotente)."""
        bus.instalar(self._conn)
        registro.instalar(self._conn)
        coste.instalar(self._conn)
        try:  # tablas del bucle P8 (Bloque 3); si aun no existe el modulo, sin fallo
            from cubos.comercial import p8_bucle
            p8_bucle.instalar(self._conn)
        except ImportError:
            pass

    def arrancar(self) -> None:
        """Registra consumidores. NUNCA falla si faltan productores: el manifest
        declara consume=[] y cualquier topic consumido de un cubo ausente
        simplemente no entrega eventos (degradacion elegante)."""
        for topic in self.manifest["consume"]:
            self._consumidores_activos.append(topic)
        log("INFO", "cubo_comercial", "arrancado", consumidores=len(self._consumidores_activos))

    def parar(self) -> None:
        self._consumidores_activos.clear()
        log("INFO", "cubo_comercial", "parado")

    # -- salud (formato exacto 3.4) -----------------------------------------
    def salud(self) -> dict:
        try:
            leads = self._conn.execute(
                "SELECT COUNT(*) FROM leads WHERE cliente_id=?", (self.cliente_id,)).fetchone()[0]
            pendientes = self._conn.execute(
                "SELECT COUNT(*) FROM compromisos WHERE estado='pendiente'").fetchone()[0]
            corte = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(
                timespec="milliseconds").replace("+00:00", "Z")
            eventos24 = self._conn.execute(
                "SELECT COUNT(*) FROM bus_eventos WHERE topic LIKE 'kaizen.comercial.%' AND ts >= ?",
                (corte,)).fetchone()[0]
        except sqlite3.Error as exc:
            return {"cubo": "comercial", "estado": "ERROR",
                    "detalle": f"registro inaccesible: {type(exc).__name__}",
                    "ts": ts_iso8601z(),
                    "contadores": {"leads": 0, "compromisos_pendientes": 0,
                                   "eventos_publicados_24h": 0}}
        estado, detalle = "OK", "operativo"
        limite = config.limite_coste_diario_eur()
        gastado = coste.comprobar_limite(self._conn)
        if limite > 0 and gastado >= 0.8 * limite:
            estado, detalle = "DEGRADADO", (
                f"coste del dia al {100 * gastado / limite:.0f}% del limite")
        return {"cubo": "comercial", "estado": estado, "detalle": detalle,
                "ts": ts_iso8601z(),
                "contadores": {"leads": int(leads),
                               "compromisos_pendientes": int(pendientes),
                               "eventos_publicados_24h": int(eventos24)}}


# -- migracion de datos reales (canonico 0.3: aditiva y con copia previa) ----
def migrar_desde_knowledge(conn: sqlite3.Connection,
                           ruta_knowledge: Path | None = None,
                           cliente_id: str = "laboratorio",
                           ruta_db_para_backup: Path | None = None) -> dict:
    """Migra leads de state/knowledge.json a la tabla leads. Idempotente
    (INSERT OR IGNORE), jamas borra ni modifica knowledge.json. Si se pasa
    ruta_db_para_backup y el fichero existe, se copia antes (kaizen.db.bak_*)."""
    ruta = Path(ruta_knowledge or ruta_knowledge_defecto())
    if ruta_db_para_backup is not None:
        origen = Path(ruta_db_para_backup)
        if origen.exists():
            marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
            shutil.copy2(origen, origen.with_name(origen.name + f".bak_{marca}"))
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    leads = datos.get(cliente_id, {}).get("lead", {})
    registro.instalar(conn)
    insertados = saltados = 0
    for clave, l in leads.items():
        bruto = str(l.get("estado_pipeline") or l.get("estado") or "cold").lower()
        estado = "NO_LLAMAR" if l.get("do_not_call") else MAPEO_ESTADO_12A7.get(bruto, "COLD")
        segmento = MAPEO_SEGMENTO.get(str(l.get("categoria_icp")), "otro")
        prioridad = str(l.get("prioridad_icp") or "MEDIA")
        if prioridad not in registro.PRIORIDADES:
            prioridad = "MEDIA"
        contacto = l.get("contacto") or {}
        telefono = contacto.get("telefono") if isinstance(contacto, dict) else None
        ubic = l.get("ubicacion") or {}
        municipio = (ubic.get("municipio") or ubic.get("localidad")) if isinstance(ubic, dict) else None
        ok = registro.insertar_lead(
            conn, id=str(l.get("id") or clave), nombre=str(l.get("nombre") or clave),
            segmento=segmento, prioridad=prioridad, cliente_id=cliente_id,
            telefono=telefono, municipio=municipio, estado=estado,
            robinson_ok=None,
            ts_creacion=l.get("creado_en"), ts_estado=l.get("fecha_ultima_transicion"))
        insertados += 1 if ok else 0
        saltados += 0 if ok else 1
    resumen = {"insertados": insertados, "ya_existian": saltados, "total_corpus": len(leads)}
    log("INFO", "cubo_comercial", "migracion desde knowledge.json", **resumen)
    return resumen
