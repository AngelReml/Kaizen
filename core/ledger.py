"""Ledger persistente y UNICO de gasto real — F1 (lectura del panel) / F2 (escritura).

Motivo (auditoria 2026-07-20, R-05/R-07): el gasto real de LLM vivia en memoria
(`core/cost_tracker`) o en `.kaizen_cost.json` sin tenant, y el panel leia un
libro que nadie alimentaba en produccion: el operador veia "0 centimos" mientras
el sistema acumulaba coste real. Este modulo da UNA fuente persistente que leen
el panel y los hard-stops (F1) y a la que escriben todos los caminos de gasto
(F2: `autorizar()` DELANTE de cada invoke, CORRECCIONES R2).

Reglas:
- Append-only JSONL en `state/coste/ledger.jsonl` (ruta inyectable en tests).
- Tras cada escritura se relee la ultima linea y se compara byte a byte (E1).
- Solo stdlib; jamas red. Thread-safe (lock de proceso).
- Legado: `.kaizen_cost.json` ({"date","usd"}, sin tenant) se expone como gasto
  "sin atribuir" del dia — se MUESTRA, no se duplica en el JSONL.
- Los `coste_asiento` del KnowledgeStore (B4) siguen existiendo: los escritores
  nuevos escriben AQUI; `LibroCoste` suma ambos mundos sin duplicar.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.bloqueo import bloqueo_exclusivo

EUR_PER_USD = 0.92


def _hoy() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class LedgerCoste:
    """Libro de asientos persistente por (tenant, cubo, rol, clase)."""

    def __init__(self, ruta: Path | str | None = None,
                 legacy_json: Path | str | None = None) -> None:
        self.ruta = Path(ruta) if ruta else None
        self.legacy = Path(legacy_json) if legacy_json else None
        self._lock = threading.Lock()

    # ── escritura (F2: siempre DESPUES de autorizar()/hard_stop_delante) ──
    def asentar(self, tenant: str, *, cubo: str, rol: str, clase: str,
                proveedor: str = "", modelo: str = "", unidades: float = 0,
                coste_eur: float = 0.0, causa_id: str | None = None) -> dict:
        if self.ruta is None:
            raise RuntimeError("ledger sin ruta: no puede asentar (configura ruta_ledger)")
        a = {"ts": _ts(), "dia": _hoy(), "tenant": tenant, "cubo": cubo, "rol": rol,
             "clase": clase, "proveedor": proveedor, "modelo": modelo,
             "unidades": unidades, "coste_eur": round(float(coste_eur), 6),
             "causa_id": causa_id}
        linea = json.dumps(a, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            # Candado de SO entre procesos: sin esto, dos instancias de LedgerCoste
            # en procesos distintos pueden entrelazar su escritura y su relectura
            # de verificacion (E1), haciendo que E1 compare contra una linea que
            # no es la propia (falso negativo de la verificacion).
            with bloqueo_exclusivo(self.ruta):
                with open(self.ruta, "a", encoding="utf-8", newline="\n") as f:
                    f.write(linea + "\n")
                # E1: verificar la escritura releyendo la ultima linea completa
                with open(self.ruta, "r", encoding="utf-8") as f:
                    ultima = f.read().rstrip("\n").rsplit("\n", 1)[-1]
                if ultima != linea:
                    raise IOError(f"E1: desfase al escribir asiento en {self.ruta}")
        return a

    # ── lectura ──
    def _iter(self):
        if self.ruta is None or not self.ruta.exists():
            return
        with open(self.ruta, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    yield json.loads(ln)
                except json.JSONDecodeError:
                    # linea corrupta: se ignora en la suma pero JAMAS en silencio
                    yield {"_corrupta": True, "cruda": ln[:120]}

    def lineas_corruptas(self) -> int:
        return sum(1 for a in self._iter() if a.get("_corrupta"))

    def gasto_dia(self, tenant: str, dia: str | None = None) -> float:
        dia = dia or _hoy()
        return round(sum(a.get("coste_eur", 0.0) for a in self._iter()
                         if not a.get("_corrupta")
                         and a.get("tenant") == tenant and a.get("dia") == dia), 6)

    def gasto_global_dia(self, dia: str | None = None) -> float:
        dia = dia or _hoy()
        total = sum(a.get("coste_eur", 0.0) for a in self._iter()
                    if not a.get("_corrupta") and a.get("dia") == dia)
        return round(total + self.sin_atribuir_dia(dia), 6)

    def asientos_mes(self, tenant: str, mes: str) -> list[dict]:
        return [a for a in self._iter() if not a.get("_corrupta")
                and a.get("tenant") == tenant and str(a.get("dia", "")).startswith(mes)]

    # ── legado (.kaizen_cost.json: dia actual en USD, sin tenant) ──
    def sin_atribuir_dia(self, dia: str | None = None) -> float:
        """Gasto del contador legado de claude_client, en EUR, si es del dia pedido.
        Sin tenant conocido: se muestra como 'sin atribuir' (honestidad B-02)."""
        if self.legacy is None or not self.legacy.exists():
            return 0.0
        try:
            d = json.loads(self.legacy.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0.0
        if d.get("date") != (dia or _hoy()):
            return 0.0
        return round(float(d.get("usd", 0.0)) * EUR_PER_USD, 6)
