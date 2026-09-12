"""Bus de mensajes — el sistema nervioso (Capa 1).

Criticidad máxima: si esta capa falla, el sistema entero colapsa. Responsabilidades
del roadmap: transporte, persistencia ligera, replay y ordenación.

Backend pluggable:
- `InMemoryBus`: en proceso, sin infraestructura. Para desarrollo y tests.
- `RedisStreamsBus`: la tecnología cerrada del stack. Persistencia y replay nativos.

`get_bus()` elige Redis si REDIS_URL está disponible y responde; si no, cae a memoria.
"""
from __future__ import annotations

import os
import sys
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from core.events import Event, EventType

Handler = Callable[[Event], None]


class MessageBus(ABC):
    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publica un evento: lo persiste y lo entrega a los suscriptores."""

    @abstractmethod
    def subscribe(self, handler: Handler, types: Iterable[EventType] | None = None) -> None:
        """Registra un handler. Si `types` es None, recibe todos los eventos."""

    @abstractmethod
    def history(self, company: str | None = None) -> list[Event]:
        """Devuelve el historial ordenado (replay), filtrable por empresa."""


def _matches(event: Event, types: set[EventType] | None) -> bool:
    return types is None or event.type in types


def _dispatch(handler: Handler, event: Event) -> None:
    """Entrega a un suscriptor aislando su fallo. El bus es la capa crítica: un handler
    roto (p. ej. la bitácora si el disco falla) no debe tumbar al emisor ni impedir la
    entrega a los demás suscriptores."""
    try:
        handler(event)
    except Exception as e:  # noqa: BLE001 — aislamiento deliberado de suscriptores
        nombre = getattr(handler, "__name__", repr(handler))
        print(f"[bus] el suscriptor {nombre} falló al procesar {event.type.value}: {e}",
              file=sys.stderr)


class InMemoryBus(MessageBus):
    """Backend en proceso: síncrono, ordenado, con replay. Sin infraestructura."""

    def __init__(self) -> None:
        self._subs: list[tuple[Handler, set[EventType] | None]] = []
        self._log: list[Event] = []
        self._lock = threading.Lock()

    def publish(self, event: Event) -> None:
        with self._lock:
            self._log.append(event)
            subs = list(self._subs)
        for handler, types in subs:
            if _matches(event, types):
                _dispatch(handler, event)

    def subscribe(self, handler: Handler, types: Iterable[EventType] | None = None) -> None:
        with self._lock:
            self._subs.append((handler, set(types) if types else None))

    def history(self, company: str | None = None) -> list[Event]:
        with self._lock:
            return [e for e in self._log if company is None or e.company == company]


class RedisStreamsBus(MessageBus):
    """Backend Redis Streams: persistencia, replay y ordenación nativos.

    Implementación inicial: dispatch en el momento de publicar + replay vía XRANGE.
    Los grupos de consumidores (entrega distribuida, ack) se añadirán cuando haya
    procesos separados que consuman el stream.
    """

    STREAM = "soe:events"

    def __init__(self, url: str | None = None) -> None:
        import redis  # dependencia opcional, solo si se usa este backend
        self._r = redis.from_url(url or os.getenv("REDIS_URL", "redis://localhost:6379"))
        self._subs: list[tuple[Handler, set[EventType] | None]] = []

    def publish(self, event: Event) -> None:
        self._r.xadd(self.STREAM, {"data": event.to_json()})
        for handler, types in list(self._subs):
            if _matches(event, types):
                _dispatch(handler, event)

    def subscribe(self, handler: Handler, types: Iterable[EventType] | None = None) -> None:
        self._subs.append((handler, set(types) if types else None))

    def history(self, company: str | None = None) -> list[Event]:
        out: list[Event] = []
        for _entry_id, fields in self._r.xrange(self.STREAM):
            raw = fields.get(b"data") or fields.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            event = Event.from_json(raw)
            if company is None or event.company == company:
                out.append(event)
        return out


def get_bus() -> MessageBus:
    """Devuelve el bus configurado.

    Cascada (mismo patrón que `core.knowledge.get_knowledge`: Neo4j->Json->Memoria):
      1. Redis si REDIS_URL está definido y responde.
      2. SQLitePersistentBus en `core.rutas.dir_state()` — persiste entre reinicios sin
         infraestructura adicional (tesis §7.4).
      3. InMemoryBus como último recurso, solo si SQLite falla (p. ej. disco/permisos).
    """
    url = os.getenv("REDIS_URL")
    if url:
        try:
            bus = RedisStreamsBus(url)
            bus._r.ping()
            return bus
        except Exception:
            pass
    try:
        from core.bus_sqlite import SQLitePersistentBus
        return SQLitePersistentBus()
    except Exception:
        return InMemoryBus()
