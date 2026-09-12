"""RUE + sobre canonico + bitacora encadenada por tenant — D00 §3 (bloque B3).

Decisiones registradas (reversibles, aditivas — la unificacion con core/bus*.py y
sustrato/bus.py es decision de v1.1, DR de arquitectura):
  - El RUE vive en eventos.json (raiz). Evento fuera del RUE = rechazado y REGISTRADO.
  - Sobre canonico D00 §3.2 completo; ts SIEMPRE UTC ISO con offset (R-14).
  - Cadena por tenant: hash_0 = sha256(tenant||fecha_alta); hash_n = sha256(prev || canon(evento)).
  - Escritor unico serializado por tenant (R-11): threading.Lock por tenant.
  - PII inline prohibida en payloads (R-07): emails/telefonos crudos se rechazan;
    usar *_ref o cifrado por sujeto (core/pii.py, crypto-shredding).
  - Outbox minimo: persistir-antes-de-publicar para acciones IRREVERSIBLE-EXTERNA.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

RUTA_RUE = Path(__file__).resolve().parent.parent / "eventos.json"
_RUE_CACHE: dict | None = None
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_TELEFONO = re.compile(r"(\+34\s?)?([0-9][\s.-]?){9,}")


class EventoInvalido(ValueError):
    """Evento fuera del RUE o sobre malformado."""


class PIIEnPayload(ValueError):
    """R-07: el payload lleva PII cruda; usar *_ref o campos *_cifrado."""


def cargar_rue(ruta: Path | None = None, *, refrescar: bool = False) -> dict:
    global _RUE_CACHE
    if _RUE_CACHE is None or refrescar or ruta is not None:
        data = json.loads(Path(ruta or RUTA_RUE).read_text(encoding="utf-8"))
        if ruta is None:
            _RUE_CACHE = data
        return data
    return _RUE_CACHE


def tipo_valido(tipo: str, ruta: Path | None = None) -> bool:
    return tipo in cargar_rue(ruta)["tipos"]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def nuevo_id() -> str:
    """Identificador ordenable por tiempo (ULID-lite): ms hex + azar."""
    return f"{int(time.time() * 1000):013x}{secrets.token_hex(5)}"


def _normalizar_nfc(obj):
    """NFC en todo string, recursivo. Auditoria 2026-07-12: 0 strings no-NFC en el
    historico real de un tenant (466 eventos) -> no rompe verificacion existente."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        return {k: _normalizar_nfc(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalizar_nfc(v) for v in obj]
    return obj


def _canon(obj) -> str:
    return json.dumps(_normalizar_nfc(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _payload_sin_pii(payload: dict) -> None:
    def rec(v, clave=""):
        if isinstance(v, dict):
            for k, x in v.items():
                rec(x, k)
        elif isinstance(v, list):
            for x in v:
                rec(x, clave)
        elif isinstance(v, str):
            if clave.endswith(("_ref", "_cifrado", "_hash")):
                return
            if RE_EMAIL.search(v) or (RE_TELEFONO.fullmatch(v.strip()) and sum(c.isdigit() for c in v) >= 9):
                raise PIIEnPayload(f"PII cruda en payload (campo {clave!r}): usar *_ref o *_cifrado (R-07)")
    rec(payload)


@dataclass
class Sobre:
    """Sobre canonico del evento (D00 §3.2)."""
    tenant_id: str
    tipo: str
    payload: dict = field(default_factory=dict)
    origen: str = "plataforma.sustrato"
    schema_version: int = 1
    correlacion_id: str = ""
    causa_id: str | None = None
    nivel_autonomia: str = "BAJA"
    coste_ref: str | None = None
    event_id: str = field(default_factory=nuevo_id)
    ts: str = field(default_factory=_ts)
    hash_prev: str = ""
    hash: str = ""

    def __post_init__(self) -> None:
        self.payload = _normalizar_nfc(self.payload)

    def cuerpo_canonico(self) -> str:
        d = asdict(self)
        d.pop("hash_prev"); d.pop("hash")
        return _canon(d)


class Bitacora:
    """Registro append-only encadenado por tenant sobre un KnowledgeStore.

    Nodos tipo "evento" con clave = f"{seq:012d}"; la secuencia ES el orden de la
    cadena (el event_id identifica, no ordena — R-11).
    """

    def __init__(self, knowledge, tenant_id: str, *, fecha_alta: str = "", ruta_rue: Path | None = None) -> None:
        self.k = knowledge
        self.tenant = tenant_id
        self.fecha_alta = fecha_alta or "2026-01-01"
        self.ruta_rue = ruta_rue
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(f"bitacora::{tenant_id}", threading.Lock())

    # ── internos ──
    def _hash_genesis(self) -> str:
        return _sha(f"{self.tenant}||{self.fecha_alta}")

    def _eventos_ordenados(self) -> list[tuple[str, dict]]:
        return sorted(self.k.all(self.tenant, "evento").items())

    def ultimo_hash(self) -> str:
        evs = self._eventos_ordenados()
        return evs[-1][1]["hash"] if evs else self._hash_genesis()

    # ── API ──
    def publicar(self, sobre: Sobre, *, outbox: list | None = None) -> Sobre:
        """Valida contra RUE + PII, encadena y persiste. Escritor unico por tenant.
        Evento de tipo desconocido: se registra `plataforma.evento.rechazado` y se lanza."""
        if sobre.tenant_id != self.tenant:
            raise EventoInvalido(f"sobre de {sobre.tenant_id!r} en bitacora de {self.tenant!r} (I2)")
        if not tipo_valido(sobre.tipo, self.ruta_rue):
            rechazo = Sobre(tenant_id=self.tenant, tipo="plataforma.evento.rechazado",
                            payload={"tipo_rechazado": sobre.tipo, "event_id_original": sobre.event_id},
                            origen="plataforma.rue", causa_id=sobre.event_id)
            self._encadenar(rechazo)
            raise EventoInvalido(f"tipo fuera del RUE: {sobre.tipo!r} (registrado el rechazo)")
        _payload_sin_pii(sobre.payload)
        if outbox is not None:                      # outbox: persistir ANTES de publicar
            outbox.append({"event_id": sobre.event_id, "tipo": sobre.tipo, "ts": sobre.ts})
        return self._encadenar(sobre)

    def _encadenar(self, sobre: Sobre) -> Sobre:
        with self._lock:
            evs = self._eventos_ordenados()
            sobre.hash_prev = evs[-1][1]["hash"] if evs else self._hash_genesis()
            sobre.hash = _sha(sobre.hash_prev + "||" + sobre.cuerpo_canonico())
            seq = f"{len(evs):012d}"
            self.k.add(self.tenant, "evento", seq, asdict(sobre))
            return sobre

    def verificar(self) -> dict:
        """Recomputa la cadena entera. Si esta rota, NOMBRA el punto exacto (D00 §13.4)."""
        prev = self._hash_genesis()
        for seq, ev in self._eventos_ordenados():
            cuerpo = {k: v for k, v in ev.items() if k not in ("hash_prev", "hash")}
            esperado = _sha(prev + "||" + _canon(cuerpo))
            if ev.get("hash_prev") != prev or ev.get("hash") != esperado:
                return {"integra": False, "punto_ruptura": seq, "event_id": ev.get("event_id")}
            prev = ev["hash"]
        return {"integra": True, "eventos": len(self._eventos_ordenados())}


def deduplicar(consumidos: set, sobre_dict: dict) -> bool:
    """Helper de consumidor idempotente (R-12): True si es nuevo, False si duplicado."""
    eid = sobre_dict["event_id"]
    if eid in consumidos:
        return False
    consumidos.add(eid)
    return True
