"""Candado de umbrales de seguridad (corrección de criterio de la tesis v1.1, §6.3, §5.1).

El contrato hijo permitía que un departamento pasara sus propios thresholds y que estos
ganaran sobre el config de empresa. Eso abre la puerta a que un sub-agente autónomo se
relaje los umbrales de seguridad fijados por el operador.

Regla que esta tesis fija con firmeza:
  * Un departamento o sub-agente puede ENDURECER un umbral (pedir MÁS consenso/confianza
    del exigido), nunca RELAJARLO por debajo del mínimo de empresa.
  * Solo el operador baja un umbral de seguridad, y ese cambio queda registrado en un log
    inmutable con su firma.

Esto evita que un agente autónomo se conceda permiso a sí mismo para ejecutar decisiones
que el operador quería bloquear.

El "log inmutable" se implementa como JSONL append-only con encadenamiento de hash
(tamper-evident): alterar un registro pasado rompe la cadena y se detecta al verificar.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.opengravity.sealing import hash_canonico, GENESIS

_RAIZ = Path(__file__).resolve().parent.parent.parent
def _default_dir():
    from core.rutas import dir_state
    return dir_state()

# Suelo absoluto del sistema: ni el operador puede bajar de aquí sin tocar el código.
SUELO_ABSOLUTO_CONSENSO = 0.50
SUELO_ABSOLUTO_CONFIANZA = 0.50

# Umbrales mínimos de empresa por defecto (el operador los configura por empresa).
DEFAULT_CONSENSO = 0.66
DEFAULT_CONFIANZA = 0.70


@dataclass
class Umbrales:
    consensus_min: float
    confidence_min: float


@dataclass
class ResolucionUmbral:
    efectivos: Umbrales
    relajacion_bloqueada: bool = False       # un sub-agente intentó relajar y se ignoró
    detalle: str = ""


def resolver_umbrales(empresa_floor: Umbrales,
                      solicitud_departamento: Umbrales | None) -> ResolucionUmbral:
    """Resuelve los umbrales efectivos aplicando el candado.

    El departamento puede pedir umbrales en `solicitud_departamento`. Se aceptan solo si
    ENDURECEN (≥ el mínimo de empresa). Cualquier intento de relajar se clava al suelo de
    empresa y se marca `relajacion_bloqueada`.
    """
    if solicitud_departamento is None:
        return ResolucionUmbral(empresa_floor)

    bloqueada = False
    detalles = []
    cons = solicitud_departamento.consensus_min
    conf = solicitud_departamento.confidence_min

    if cons < empresa_floor.consensus_min:
        detalles.append(f"consenso solicitado {cons} < mínimo de empresa "
                        f"{empresa_floor.consensus_min}: ignorado.")
        cons = empresa_floor.consensus_min
        bloqueada = True
    if conf < empresa_floor.confidence_min:
        detalles.append(f"confianza solicitada {conf} < mínimo de empresa "
                        f"{empresa_floor.confidence_min}: ignorado.")
        conf = empresa_floor.confidence_min
        bloqueada = True

    return ResolucionUmbral(Umbrales(cons, conf), bloqueada, " ".join(detalles))


class LogInmutableUmbrales:
    """Log append-only, encadenado por hash, de cambios de umbral del operador."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or _default_dir()
        self._path = self._dir / "umbral_log.jsonl"
        self._lock = threading.Lock()

    def _ultimo_hash(self) -> str:
        if not self._path.exists():
            return GENESIS
        ultimo = GENESIS
        for linea in self._path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea:
                try:
                    ultimo = json.loads(linea).get("hash", ultimo)
                except Exception:  # noqa: BLE001
                    pass
        return ultimo

    def registrar_bajada(self, company: str, umbral: str, de: float, a: float,
                         firma_operador: str, motivo: str = "") -> dict:
        """Registra que el operador BAJÓ un umbral. Aplica el suelo absoluto del sistema."""
        suelo = (SUELO_ABSOLUTO_CONSENSO if "conso" in umbral.lower()
                 else SUELO_ABSOLUTO_CONFIANZA)
        if a < suelo:
            raise ValueError(f"No se puede bajar '{umbral}' a {a}: suelo absoluto {suelo}.")
        if not firma_operador:
            raise ValueError("Bajar un umbral exige firma del operador.")
        with self._lock:
            prev = self._ultimo_hash()
            registro = {
                "company": company, "umbral": umbral, "de": de, "a": a,
                "firma_operador": firma_operador, "motivo": motivo,
                "ts": datetime.now(timezone.utc).isoformat(),
                "chain_prev_hash": prev,
            }
            registro["hash"] = hash_canonico(registro)
            self._dir.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
            return registro

    def verificar(self) -> bool:
        """Verifica la cadena completa del log (tamper-evidence)."""
        if not self._path.exists():
            return True
        prev = GENESIS
        for linea in self._path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            r = json.loads(linea)
            esperado = r.get("hash")
            cuerpo = {k: v for k, v in r.items() if k != "hash"}
            if cuerpo.get("chain_prev_hash") != prev or hash_canonico(cuerpo) != esperado:
                return False
            prev = esperado
        return True

    def historial(self, company: str | None = None) -> list[dict]:
        if not self._path.exists():
            return []
        out = []
        for linea in self._path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            r = json.loads(linea)
            if company is None or r.get("company") == company:
                out.append(r)
        return out
