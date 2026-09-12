"""Cubo Operaciones segun KAIZEN-D05 (D5.0/D5.1) + R-08/R-09 y GAP-02 de D09.

Reglas de oro: la saturacion CIERRA la puerta automaticamente (no hay "esfuerzo
extra"); sin capacidad declarada los pedidos PENDEN con alerta — el fail-safe de
una accion externa es NO ACTUAR, jamas auto-rechazar (R-08); la confirmacion es
un claim TRANSACCIONAL sobre la capacidad de la fecha (R-09: dos concurrentes
sobre la ultima unidad → exactamente una gana). Extiende, no sustituye, a
departments/ops/herramientas.py (embrion detectado en AUDITORIA_SERIE_D).
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from core.rue import Sobre

ESTADOS_PEDIDO = ("PENDIENTE_CONFIRMACION", "CONFIRMADO", "EN_PRODUCCION", "RETENIDO",
                  "COMPLETADO", "ENTREGADO_A_LOGISTICA", "RECHAZADO")
HITOS = ("LOTE_COMPLETO", "EMPAQUETADO", "LISTO_LOGISTICA")
SLA_ALERTA_H = 24        # GAP-02: 24h pendiente → alerta operador
SLA_ESCALADO_H = 72      # 72h → evento a D01 para gestionar expectativa


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# R-09: el candado del claim de capacidad NO puede vivir en la instancia — si
# CuboOps se instancia por-peticion (un objeto nuevo por request, p.ej. en el
# panel), cada instancia trae su propio threading.Lock() y la exclusion mutua
# entre peticiones concurrentes queda anulada. Registro a nivel de MODULO,
# compartido por todas las instancias, con clave (tenant, fecha).
_locks_capacidad: dict[tuple[str, str], threading.Lock] = {}
_locks_capacidad_guard = threading.Lock()


def _lock_capacidad(tenant: str, fecha: str) -> threading.Lock:
    with _locks_capacidad_guard:
        return _locks_capacidad.setdefault((tenant, fecha), threading.Lock())


class CuboOps:
    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora

    def _emitir(self, tipo: str, payload: dict) -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="operacion.cubo"))

    # ── capacidad (recorrido B) ──
    def declarar_capacidad(self, fecha: str, lotes: int, *, por: str = "operador",
                           version_motivo: str = "") -> dict:
        actual = self.k.get(self.tenant, "capacidad", fecha) or {"fecha": fecha, "version": 0}
        c = {"fecha": fecha, "lotes": int(lotes), "version": actual["version"] + 1,
             "declarada_por": por, "motivo": version_motivo, "ts": _ts()}
        self.k.add(self.tenant, "capacidad", fecha, c)
        self._emitir("operacion.capacidad.declarada", {"fecha": fecha, "lotes": lotes,
                                                       "version": c["version"]})
        return c

    def _consumo(self, fecha: str) -> int:
        return sum(1 for p in self.k.all(self.tenant, "pedido_ops").values()
                   if p.get("fecha") == fecha and p["estado"] in
                   ("CONFIRMADO", "EN_PRODUCCION", "RETENIDO", "COMPLETADO"))

    def consultar_capacidad(self, fecha: str) -> dict:
        cap = self.k.get(self.tenant, "capacidad", fecha)
        consumida = self._consumo(fecha)
        r = {"fecha": fecha, "declarada": bool(cap), "lotes": cap["lotes"] if cap else None,
             "consumida": consumida,
             "disponible": (cap["lotes"] - consumida) if cap else None}
        self._emitir("operacion.capacidad.consultada", r)
        return r

    # ── flujo de pedido (recorrido A) ──
    def recibir_pedido(self, pedido: dict) -> dict:
        for campo in ("id", "cliente_ref", "producto", "cantidad", "fecha"):
            if not pedido.get(campo):
                raise ValueError(f"pedido mal formado: falta {campo}")
        p = dict(pedido); p["estado"] = "PENDIENTE_CONFIRMACION"; p["recibido_en"] = _ts()
        p["hitos"] = []
        self.k.add(self.tenant, "pedido_ops", p["id"], p)
        self._emitir("operacion.pedido.recibido", {"pedido_ref": p["id"], "fecha": p["fecha"]})
        return p

    def confirmar(self, pedido_id: str) -> dict:
        """Claim atomico sobre la capacidad de la fecha (R-09). Sin capacidad declarada:
        PENDE con alerta (R-08) — jamas auto-rechazo. Saturada: rechazo CON propuesta."""
        p0 = self.k.get(self.tenant, "pedido_ops", pedido_id)
        if p0 is None or p0["estado"] != "PENDIENTE_CONFIRMACION":
            raise ValueError(f"solo se confirma un PENDIENTE_CONFIRMACION")
        with _lock_capacidad(self.tenant, p0["fecha"]):        # candado global (tenant, fecha)
            p = self.k.get(self.tenant, "pedido_ops", pedido_id)
            if p is None or p["estado"] != "PENDIENTE_CONFIRMACION":
                raise ValueError(f"solo se confirma un PENDIENTE_CONFIRMACION")
            cap = self.k.get(self.tenant, "capacidad", p["fecha"])
            if cap is None:                        # R-08: fail-safe = pender
                self._emitir("operacion.capacidad.saturada",
                             {"fecha": p["fecha"], "motivo": "capacidad NO declarada",
                              "alerta": "capacidad no declarada; pedidos esperando"})
                return {"estado": "PENDIENTE_CONFIRMACION", "pendiente_por": "capacidad_no_declarada",
                        "pedido_ref": pedido_id}
            if self._consumo(p["fecha"]) >= cap["lotes"]:
                p["estado"] = "RECHAZADO"
                p["propuesta_alternativa_fecha"] = self._siguiente_fecha_libre(p["fecha"])
                self.k.add(self.tenant, "pedido_ops", pedido_id, p)
                self._emitir("operacion.pedido.rechazado",
                             {"pedido_ref": pedido_id, "motivo": "CAPACIDAD_SATURADA",
                              "propuesta_alternativa_fecha": p["propuesta_alternativa_fecha"]})
                self._emitir("operacion.capacidad.saturada",
                             {"fecha": p["fecha"], "lotes": cap["lotes"]})
                return p
            p["estado"] = "CONFIRMADO"
            self.k.add(self.tenant, "pedido_ops", pedido_id, p)
        self._emitir("operacion.pedido.confirmado", {"pedido_ref": pedido_id, "fecha": p["fecha"]})
        self._emitir("operacion.capacidad.consumida",
                     {"fecha": p["fecha"], "consumida": self._consumo(p["fecha"]),
                      "total": cap["lotes"]})
        return p

    def _siguiente_fecha_libre(self, fecha: str) -> str:
        d = datetime.fromisoformat(fecha)
        for _ in range(30):
            d += timedelta(days=1)
            f = d.strftime("%Y-%m-%d")
            cap = self.k.get(self.tenant, "capacidad", f)
            if cap is None or self._consumo(f) < cap["lotes"]:
                return f
        return (datetime.fromisoformat(fecha) + timedelta(days=31)).strftime("%Y-%m-%d")

    # ── hitos (D5.1) ──
    def registrar_hito(self, pedido_id: str, tipo_hito: str, *, foto_ref: str = "") -> dict:
        assert tipo_hito in HITOS, f"hito desconocido: {tipo_hito}"
        p = self.k.get(self.tenant, "pedido_ops", pedido_id)
        if p is None or p["estado"] in ("RECHAZADO", "PENDIENTE_CONFIRMACION"):
            raise ValueError("hito solo sobre pedidos confirmados")
        hito = {"tipo": tipo_hito, "ts": _ts(), "foto_ref": foto_ref}
        p.setdefault("hitos", []).append(hito)
        if p["estado"] == "CONFIRMADO":
            p["estado"] = "EN_PRODUCCION"
        if tipo_hito == "LISTO_LOGISTICA":
            p["estado"] = "COMPLETADO"
        self.k.add(self.tenant, "pedido_ops", pedido_id, p)
        self._emitir("operacion.pedido.hito", {"pedido_ref": pedido_id, "tipo_hito": tipo_hito})
        if p["estado"] == "COMPLETADO":
            self._emitir("operacion.pedido.completado",
                         {"pedido_ref": pedido_id, "hitos_totales": len(p["hitos"])})
        return p

    def entregar_a_logistica(self, pedido_id: str, *, albaran_ref: str) -> dict:
        p = self.k.get(self.tenant, "pedido_ops", pedido_id)
        if p is None or p["estado"] != "COMPLETADO":
            raise ValueError("no sale sin al menos LISTO_LOGISTICA (gate)")
        p["estado"] = "ENTREGADO_A_LOGISTICA"
        self.k.add(self.tenant, "pedido_ops", pedido_id, p)
        self._emitir("operacion.pedido.entregado_a_logistica",
                     {"pedido_ref": pedido_id, "albaran_ref": albaran_ref})
        return p

    # ── secuencia (D5.0.5) ──
    def proponer_secuencia(self, fecha: str) -> list[str]:
        """LOYAL y URGENTE primero; determinista y estable."""
        confirmados = [p for p in self.k.all(self.tenant, "pedido_ops").values()
                       if p.get("fecha") == fecha and p["estado"] in ("CONFIRMADO", "EN_PRODUCCION")]
        def prioridad(p):
            return (0 if p.get("urgente") else 1,
                    0 if p.get("cliente_loyal") else 1,
                    p.get("recibido_en", ""), p["id"])
        return [p["id"] for p in sorted(confirmados, key=prioridad)]

    # ── SLA GAP-02 ──
    def barrer_pendientes(self, *, ahora: datetime | None = None) -> list[dict]:
        ahora = ahora or datetime.now(timezone.utc)
        avisos = []
        for p in self.k.all(self.tenant, "pedido_ops").values():
            if p["estado"] != "PENDIENTE_CONFIRMACION":
                continue
            horas = (ahora - datetime.fromisoformat(p["recibido_en"])).total_seconds() / 3600
            if horas > SLA_ESCALADO_H:
                self._emitir("operacion.pedido.rechazado",
                             {"pedido_ref": p["id"], "motivo": "SLA_72H_ESCALADO_A_COMERCIAL",
                              "propuesta_alternativa_fecha": self._siguiente_fecha_libre(p["fecha"])})
                avisos.append({"pedido": p["id"], "sla": "72h→D01"})
            elif horas > SLA_ALERTA_H:
                self._emitir("operacion.capacidad.saturada",
                             {"alerta": f"pedido {p['id']} pendiente >24h sin capacidad declarada"})
                avisos.append({"pedido": p["id"], "sla": "24h→operador"})
        return avisos
