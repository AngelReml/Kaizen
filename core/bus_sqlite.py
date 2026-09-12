"""Bus sobre SQLite — el sistema nervioso v1 (tesis §2.3, §7.4).

El Roadmap v1.0 preveía Redis Streams desde el principio. La tesis, por evidencia
operativa, decidió que SQLite basta para el volumen del piloto (§7.4). Este backend
persiste el log de eventos en SQLite con WAL, lo que da:

  * persistencia y replay nativos (gemelo de RedisStreamsBus pero sin infraestructura),
  * el "log del propio sistema nervioso" donde vive la cola persistente (§7.2),
  * las cuatro métricas que el monitor de migración observa (§7.4): eventos/min, lag,
    suscriptores concurrentes y latencia de escritura en SQLite.

Cuando las métricas crucen el umbral (2 de 4 durante 3 días), el monitor ABRE la decisión
de migrar a Redis; no la ejecuta (§7.4).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from core.bus import MessageBus, Handler, _matches, _dispatch
from core.events import Event, EventType

_RAIZ = Path(__file__).resolve().parent.parent
def _default_db():
    """R-TENANT: la raiz de datos se resuelve en cada llamada, no en el import."""
    from core.rutas import dir_state
    return dir_state() / "sistema_nervioso.db"


class SQLitePersistentBus(MessageBus):
    """Bus persistente en SQLite. Síncrono y ordenado, como InMemoryBus, pero sobrevive a
    reinicios y registra métricas de salud para el monitor de migración."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or _default_db()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._crear()
        self._subs: list[tuple[Handler, set[EventType] | None]] = []
        self._lock = threading.Lock()

    def _crear(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS eventos (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT, type TEXT NOT NULL, source TEXT, company TEXT NOT NULL,
                correlation_id TEXT, criticality TEXT, ts TEXT NOT NULL,
                data TEXT NOT NULL, write_latency_ms REAL
            )""")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_company ON eventos(company)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON eventos(ts)")
        self._conn.commit()

    def publish(self, event: Event) -> None:
        # Mide la latencia de escritura en SQLite (métrica db_write_latency_ms del §7.4).
        t0 = time.perf_counter()
        with self._lock:
            self._conn.execute(
                "INSERT INTO eventos (id, type, source, company, correlation_id, "
                "criticality, ts, data, write_latency_ms) VALUES (?,?,?,?,?,?,?,?,?)",
                (event.id, event.type.value, event.source, event.company,
                 event.correlation_id, event.criticality.value, event.ts,
                 event.to_json(), None))
            self._conn.commit()
            latency_ms = (time.perf_counter() - t0) * 1000.0
            self._conn.execute(
                "UPDATE eventos SET write_latency_ms=? WHERE id=? AND ts=?",
                (latency_ms, event.id, event.ts))
            self._conn.commit()
            subs = list(self._subs)
        for handler, types in subs:
            if _matches(event, types):
                _dispatch(handler, event)

    def subscribe(self, handler: Handler, types: Iterable[EventType] | None = None) -> None:
        with self._lock:
            self._subs.append((handler, set(types) if types else None))

    def history(self, company: str | None = None) -> list[Event]:
        q = "SELECT data FROM eventos" + (" WHERE company=?" if company else "") + " ORDER BY seq ASC"
        args = (company,) if company else ()
        with self._lock:
            filas = self._conn.execute(q, args).fetchall()
        return [Event.from_json(f[0]) for f in filas]

    # ── Métricas de salud para el monitor de migración (§7.4) ─────────────────
    def suscriptores_por_tipo(self) -> dict[str, int]:
        """Cuántos suscriptores escuchan cada tipo (concurrent_subscribers del §7.4)."""
        conteo: dict[str, int] = {}
        with self._lock:
            subs = list(self._subs)
        for _handler, types in subs:
            etiquetas = [t.value for t in types] if types else ["*"]
            for e in etiquetas:
                conteo[e] = conteo.get(e, 0) + 1
        return conteo

    def max_suscriptores_un_tipo(self) -> int:
        c = self.suscriptores_por_tipo()
        return max(c.values()) if c else 0

    def latencias_escritura(self, *, ultimos: int = 1000) -> list[float]:
        with self._lock:
            filas = self._conn.execute(
                "SELECT write_latency_ms FROM eventos WHERE write_latency_ms IS NOT NULL "
                "ORDER BY seq DESC LIMIT ?", (ultimos,)).fetchall()
        return [f[0] for f in filas]

    def eventos_por_minuto(self, *, ventana_min: int = 5) -> float:
        """Tasa de eventos/min sobre la ventana reciente (events_per_minute del §7.4)."""
        with self._lock:
            filas = self._conn.execute(
                "SELECT ts FROM eventos ORDER BY seq DESC LIMIT 5000").fetchall()
        if not filas:
            return 0.0
        ahora = datetime.now(timezone.utc)
        n = 0
        for (ts,) in filas:
            try:
                t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except ValueError:
                continue
            if t.tzinfo is None:
                # ts naive (legacy): lo asumimos UTC para no romper la resta aware-naive.
                t = t.replace(tzinfo=timezone.utc)
            if (ahora - t).total_seconds() <= ventana_min * 60:
                n += 1
        return n / ventana_min if ventana_min else float(n)

    def cerrar(self) -> None:
        with self._lock:
            self._conn.close()
