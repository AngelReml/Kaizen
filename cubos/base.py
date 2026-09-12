"""Cubo generico: da contrato de cubo (canonico 3.2-3.4) a un departamento
del catalogo sin reescribir su codigo. El codigo funcional de cada
departamento sigue viviendo en departments/<nombre>/ y no se toca; esta capa
aporta manifest validado, ciclo de vida, salud honesta y autonomia por
defecto. Comercial usa su adaptador rico (cubos/comercial/adaptador.py).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sustrato import bus, config, coste
from sustrato.consola import log, ts_iso8601z

RAIZ_CUBOS = Path(__file__).resolve().parent


def manifiestos_instalados() -> dict[str, Path]:
    """nombre_cubo -> ruta del manifest, para todos los cubos en cubos/*/."""
    out = {}
    for ruta in sorted(RAIZ_CUBOS.glob("*/manifest.json")):
        out[ruta.parent.name] = ruta
    return out


class CuboGenerico:
    """Contrato de cubo minimo y honesto para departamentos no-comerciales."""

    def __init__(self, nombre: str, conn: sqlite3.Connection | None = None, *,
                knowledge=None, tenant: str | None = None) -> None:
        self.nombre = nombre
        ruta = RAIZ_CUBOS / nombre / "manifest.json"
        config.validar_manifest(ruta)
        self.manifest = json.loads(ruta.read_text(encoding="utf-8"))
        self._conn = conn if conn is not None else bus.conexion()
        self._consumidores_activos: list[str] = []
        self.k = knowledge
        self.tenant = tenant

    # -- ciclo de vida ------------------------------------------------------
    def instalar(self) -> None:
        bus.instalar(self._conn)
        coste.instalar(self._conn)

    def arrancar(self) -> None:
        """NUNCA falla si faltan productores: consumir topics de cubos no
        instalados es legal por diseno (degradacion elegante)."""
        self._consumidores_activos = list(self.manifest.get("consume", []))
        log("INFO", f"cubo_{self.nombre}", "arrancado",
            consumidores=len(self._consumidores_activos))

    def parar(self) -> None:
        self._consumidores_activos.clear()
        log("INFO", f"cubo_{self.nombre}", "parado")

    # -- salud (mismo esquema 3.4; contadores genericos honestos) ------------
    def salud(self) -> dict:
        try:
            corte_dt = datetime.now(timezone.utc) - timedelta(hours=24)
            corte = corte_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            publicados = self._conn.execute(
                "SELECT COUNT(*) FROM bus_eventos WHERE topic LIKE ? AND ts >= ?",
                (f"kaizen.{self.nombre}.%", corte)).fetchone()[0]
        except sqlite3.Error as exc:
            return {"cubo": self.nombre, "estado": "ERROR",
                    "detalle": f"bus inaccesible: {type(exc).__name__}",
                    "ts": ts_iso8601z(),
                    "contadores": {"eventos_publicados_24h": 0,
                                   "consumidores_declarados": 0,
                                   "acciones_irreversibles": 0}}
        eventos_bus = int(publicados)
        eventos_bitacora = 0
        prefijos_rue = self.manifest.get("produce_rue")
        if prefijos_rue and self.k is not None and self.tenant is not None:
            try:
                for ev in self.k.all(self.tenant, "evento").values():
                    ts_ev = ev.get("ts")
                    tipo_ev = ev.get("tipo", "")
                    if not ts_ev:
                        continue
                    if datetime.fromisoformat(ts_ev) < corte_dt:
                        continue
                    if any(tipo_ev.startswith(p) for p in prefijos_rue):
                        eventos_bitacora += 1
            except (AttributeError, KeyError, TypeError, ValueError):
                # conteo opcional (produce_rue): degrada sin romper el resto de salud()
                eventos_bitacora = 0
        estado, detalle = "OK", "operativo"
        limite = coste.limite_vigente(self._conn)
        gastado = coste.comprobar_limite(self._conn)
        if limite > 0 and gastado >= 0.8 * limite:
            estado, detalle = "DEGRADADO", (
                f"coste del dia al {100 * gastado / limite:.0f}% del limite")
        nota = self.manifest.get("nota_estado")
        if nota:  # p.ej. rrhh pospuesto por decision del operador
            detalle = nota
        return {"cubo": self.nombre, "estado": estado, "detalle": detalle,
                "ts": ts_iso8601z(),
                "contadores": {
                    "eventos_publicados_24h": eventos_bus + eventos_bitacora,
                    "eventos_bus_24h": eventos_bus,
                    "eventos_bitacora_24h": eventos_bitacora,
                    "consumidores_declarados": len(self.manifest.get("consume", [])),
                    "acciones_irreversibles": len(self.manifest.get("acciones_irreversibles", [])),
                }}


def construir(nombre: str, conn: sqlite3.Connection | None = None, *,
              knowledge=None, tenant: str | None = None):
    """Fabrica: comercial usa su adaptador rico; el resto, CuboGenerico."""
    if nombre == "comercial":
        from cubos.comercial.adaptador import CuboComercial
        return CuboComercial(conn=conn)
    return CuboGenerico(nombre, conn=conn, knowledge=knowledge, tenant=tenant)
