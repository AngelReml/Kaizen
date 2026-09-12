"""Sellado y trazabilidad del veredicto (tesis §6.3).

Cada veredicto se sella con un hash SHA-256 sobre el payload canónico, encadenado con el
hash del veredicto anterior de esa misma empresa. Forma una cadena verificable por empresa
que permite:
  * auditoría completa,
  * reconstrucción del razonamiento (las N pasadas, las divergencias, la síntesis del chair),
  * comparación de veredictos sobre artefactos similares para detectar drift.

El JSON canónico se serializa con claves ordenadas y sin espacios variables, de modo que el
hash es reproducible. La cadena (head por empresa) se persiste con escritura atómica.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

from core.bloqueo import bloqueo_exclusivo

_RAIZ = Path(__file__).resolve().parent.parent.parent
def _default_dir():
    from core.rutas import dir_state
    return dir_state()

GENESIS = "0" * 64   # hash previo del primer veredicto de una empresa


def hash_canonico(payload: dict) -> str:
    """SHA-256 sobre el JSON canónico (claves ordenadas, separadores fijos, UTF-8)."""
    canonico = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


class HashChain:
    """Cadena de veredictos por empresa. Persiste solo el head (último hash) por empresa;
    la cadena completa vive en el log del bus / la bitácora."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or _default_dir()
        self._path = self._dir / "opengravity_chain.json"
        self._lock = threading.Lock()
        self._heads: dict[str, str] = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._heads, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self._path)

    def head(self, company: str) -> str:
        return self._heads.get(company, GENESIS)

    def sellar(self, company: str, payload: dict) -> dict:
        """Sella un payload: calcula el hash encadenado con el head de la empresa y avanza
        el head. Devuelve `{hash, chain_prev_hash}` para incrustar en el veredicto.

        Candado de SO entre procesos (no solo threading.Lock): dos instancias de
        HashChain en procesos distintos sobre el mismo JSON deben coordinarse. Y no
        basta con proteger el `_save()` — hay que releer el estado desde disco DENTRO
        del candado antes de decidir `prev`, o la decision se toma con un head
        obsoleto (ver core/bloqueo.py).
        """
        with bloqueo_exclusivo(self._path):
            with self._lock:
                self._heads = self._load()
                prev = self.head(company)
                cuerpo = dict(payload)
                cuerpo["chain_prev_hash"] = prev
                h = hash_canonico(cuerpo)
                self._heads[company] = h
                self._save()
                return {"hash": h, "chain_prev_hash": prev}

    def verificar(self, company: str, eslabones: list[dict]) -> bool:
        """Verifica una cadena reconstruida: cada eslabón es `{payload, hash, chain_prev_hash}`.
        Comprueba que el hash recomputado coincide y que el prev encadena correctamente.
        """
        prev = GENESIS
        for e in eslabones:
            cuerpo = dict(e.get("payload", {}))
            cuerpo["chain_prev_hash"] = prev
            if hash_canonico(cuerpo) != e.get("hash"):
                return False
            if e.get("chain_prev_hash") != prev:
                return False
            prev = e["hash"]
        return True
