"""Degradación elegante (tesis §7.2).

Si §7.1 cubre el arranque, esto cubre el runtime: qué pasa cuando un cubo publica un evento
y el consumidor está apagado, suspendido o lento. El diseño clasifica cada tipo de evento
por su exigencia de respuesta:

  broadcast                    No espera respuesta. Se persiste, el productor no espera.
  request-response opcional    Espera respuesta pero tiene fallback documentado: aplica el
                               valor degradado declarado en el contrato.
  request-response obligatoria El productor no continúa sin respuesta válida: bloquea por
                               diseño (cola persistente). No degrada.

Todo artefacto producido en modo degradado lleva tres metadatos obligatorios:
  degraded: true · degraded_reason (consumer_off|timeout|invalid_response) · degraded_event_ref

La cola persistente: eventos no atendidos guardados en el log del sistema nervioso,
aislados por empresa, ordenados por timestamp, e idempotentes por correlation_id. TTLs:
broadcast 7 días, request-response opcional 24 h, obligatoria no expira (intervención del
operador). No hay reintentos automáticos del productor —el reintento lo hace el consumidor
al revivir— para evitar tormentas de retry.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path

from core.events import Event

_RAIZ = Path(__file__).resolve().parent.parent.parent
def _default_db():
    from core.rutas import dir_state
    return dir_state() / "cola_persistente.db"


class ClaseEvento(str, Enum):
    BROADCAST = "broadcast"
    REQ_RESP_OPCIONAL = "request_response_opcional"
    REQ_RESP_OBLIGATORIA = "request_response_obligatoria"


class DegradedReason(str, Enum):
    CONSUMER_OFF = "consumer_off"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"


# TTL por clase de evento (§7.2). Obligatoria = None (no expira).
TTL_POR_CLASE = {
    ClaseEvento.BROADCAST: timedelta(days=7),
    ClaseEvento.REQ_RESP_OPCIONAL: timedelta(hours=24),
    ClaseEvento.REQ_RESP_OBLIGATORIA: None,
}


def marcar_degradado(payload: dict, reason: DegradedReason | str,
                     event_ref: str | None = None, *, valor_degradado: dict | None = None) -> dict:
    """Devuelve una copia del payload con los tres metadatos obligatorios de degradación.

    `valor_degradado` es el fallback documentado por el contrato del evento opcional (p. ej.
    {"aprobado": True} para una revisión de Brand forense con Brand apagado, §7.2).
    """
    out = dict(valor_degradado or {})
    out.update(payload)
    out["degraded"] = True
    out["degraded_reason"] = reason.value if isinstance(reason, DegradedReason) else str(reason)
    out["degraded_event_ref"] = event_ref
    return out


def es_degradado(payload: dict) -> bool:
    return bool((payload or {}).get("degraded"))


@dataclass
class ContratoEvento:
    """Declaración por tipo de evento de su clase y, si es opcional, su valor degradado.
    El valor degradado es parte del contrato, no una improvisación (§7.2)."""
    clase: ClaseEvento
    valor_degradado: dict | None = None

    def degrada(self) -> bool:
        return self.clase in (ClaseEvento.BROADCAST, ClaseEvento.REQ_RESP_OPCIONAL)


class ColaPersistente:
    """Log de eventos no atendidos en SQLite (el log del sistema nervioso, §7.2).

    Aislada por empresa, ordenada por timestamp, idempotente por correlation_id. El
    consumidor reproduce su cola al revivir; el productor nunca reintenta.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or _default_db()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._crear()

    def _crear(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cola (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                clase TEXT NOT NULL,
                consumidor TEXT NOT NULL,
                correlation_id TEXT,
                event_json TEXT NOT NULL,
                ts TEXT NOT NULL,
                expira_en TEXT,
                procesado INTEGER DEFAULT 0,
                UNIQUE(consumidor, correlation_id)
            )""")
        self._conn.commit()

    def encolar(self, event: Event, consumidor: str, clase: ClaseEvento) -> bool:
        """Guarda un evento no atendido. Idempotente: si ya existe (mismo consumidor +
        correlation_id) no duplica. Devuelve True si se insertó, False si era duplicado."""
        ttl = TTL_POR_CLASE.get(clase)
        ahora = datetime.now(timezone.utc)
        expira = (ahora + ttl).isoformat() if ttl else None
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO cola (company, clase, consumidor, correlation_id, "
                    "event_json, ts, expira_en) VALUES (?,?,?,?,?,?,?)",
                    (event.company, clase.value, consumidor, event.correlation_id,
                     event.to_json(), event.ts, expira))
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False   # idempotencia: ya estaba encolado

    def pendientes(self, consumidor: str, company: str | None = None) -> list[Event]:
        """Eventos no procesados ni expirados para un consumidor, ordenados por timestamp."""
        self.purgar_expirados()
        q = ("SELECT event_json FROM cola WHERE consumidor=? AND procesado=0 "
             + ("AND company=? " if company else "") + "ORDER BY ts ASC")
        args = (consumidor, company) if company else (consumidor,)
        with self._lock:
            filas = self._conn.execute(q, args).fetchall()
        return [Event.from_json(f[0]) for f in filas]

    def marcar_procesado(self, consumidor: str, correlation_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE cola SET procesado=1 WHERE consumidor=? AND correlation_id=?",
                (consumidor, correlation_id))
            self._conn.commit()

    def purgar_expirados(self) -> int:
        """Borra los eventos cuyo TTL venció (la obligatoria tiene expira_en NULL: no purga)."""
        ahora = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM cola WHERE expira_en IS NOT NULL AND expira_en < ?", (ahora,))
            self._conn.commit()
            return cur.rowcount

    def cerrar(self) -> None:
        with self._lock:
            self._conn.close()
