"""Historial de votos y pesos por rol (tesis §4.3, §5.2).

`vote_history.ts` en Shinobi persistía, pero con solo 2 reviews reales los pesos no se
diferenciaban aún. Esta tesis fija la honestidad: el aprendizaje de pesos necesita un
mínimo de votos reales por rol antes de poder diferenciar (§5.2). Hasta ese mínimo, todos
los roles pesan 1.0 —el comité no finge una precisión que no tiene.

Persistencia JSON atómica (temp + os.replace), aislada por empresa, gemela del patrón de
`JsonKnowledge` y del fichero de coste. Un rol acumula aciertos cuando su veredicto
coincide con el resultado finalmente validado por el operador (cuando este resuelve una
escalada o confirma/revierte un veredicto forense).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
def _default_dir():
    from core.rutas import dir_state
    return dir_state()

# Mínimo de votos resueltos por rol antes de diferenciar su peso (§5.2).
MIN_VOTOS_PARA_DIFERENCIAR = 10
PESO_NEUTRO = 1.0
PESO_MIN = 0.5
PESO_MAX = 1.5


class VoteHistory:
    """Pesos por rol y por empresa. Thread-safe; persiste en `state/vote_history.json`."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or _default_dir()
        self._path = self._dir / "vote_history.json"
        self._lock = threading.Lock()
        self._data: dict = self._load()

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
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self._path)

    def _registro(self, company: str, role_id: str) -> dict:
        return self._data.setdefault(company, {}).setdefault(
            role_id, {"aciertos": 0, "fallos": 0, "total": 0})

    def registrar(self, company: str, role_id: str, acerto: bool) -> None:
        """Registra el resultado de un voto una vez el operador resuelve la verdad."""
        with self._lock:
            reg = self._registro(company, role_id)
            reg["total"] += 1
            if acerto:
                reg["aciertos"] += 1
            else:
                reg["fallos"] += 1
            self._save()

    def peso(self, company: str, role_id: str) -> float:
        """Peso del rol en [PESO_MIN, PESO_MAX]. 1.0 mientras no haya datos suficientes."""
        reg = self._data.get(company, {}).get(role_id)
        if not reg or reg["total"] < MIN_VOTOS_PARA_DIFERENCIAR:
            return PESO_NEUTRO
        tasa = reg["aciertos"] / reg["total"] if reg["total"] else 0.5
        # Mapea tasa de acierto [0,1] → peso [PESO_MIN, PESO_MAX] centrado en 1.0 a tasa 0.5.
        peso = PESO_MIN + tasa * (PESO_MAX - PESO_MIN)
        return round(peso, 4)

    def diferenciado(self, company: str) -> bool:
        """¿Hay ya algún rol con suficientes votos para que su peso difiera del neutro?"""
        for reg in self._data.get(company, {}).values():
            if reg.get("total", 0) >= MIN_VOTOS_PARA_DIFERENCIAR:
                return True
        return False

    def snapshot(self, company: str) -> dict:
        return dict(self._data.get(company, {}))
