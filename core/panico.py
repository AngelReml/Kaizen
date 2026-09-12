"""Palancas formales e interruptor de panico — D00 §8.2 (bloque B7).

Tres niveles de palanca: global × tenant × clase de accion. El panico corta toda
accion IRREVERSIBLE-EXTERNA en ≤1 ciclo (gate delante de cada ejecucion), CONSERVA
colas y estado, emite evento, y su desactivacion exige operador con registro.
La seguridad degrada cerrando: en duda, la accion externa NO sale (GR-04).

F1 (auditoria 2026-07-20, R-08): el estado del panico puede PERSISTIRSE en disco
(`ruta_estado`): activar/desactivar escriben un JSON atomico verificado (E1) y un
proceso nuevo arranca leyendolo — un reinicio ya no "olvida" un PARAR TODO. Las
bitacoras (dict tenant→Bitacora) pueden ser una referencia viva: se leen en el
momento de activar/desactivar, de modo que emiten evento para cada tenant
conocido en ese instante (L2: nada invisible).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.rue import Sobre


class PanicoActivo(RuntimeError):
    """Accion IRR-EXT bloqueada por panico. La cola se conserva; nada se pierde."""


class PalancaCerrada(RuntimeError):
    pass


class Palancas:
    """Interruptores por (global | tenant | clase). Cerrado gana siempre."""

    def __init__(self) -> None:
        self._global = True
        self._tenant: dict[str, bool] = {}
        self._clase: dict[str, bool] = {}
        self._lock = threading.Lock()

    def fijar_global(self, abierta: bool) -> None:
        with self._lock:
            self._global = abierta

    def fijar_tenant(self, tenant: str, abierta: bool) -> None:
        with self._lock:
            self._tenant[tenant] = abierta

    def fijar_clase(self, clase: str, abierta: bool) -> None:
        with self._lock:
            self._clase[clase] = abierta

    def abierta(self, tenant: str, clase: str) -> bool:
        with self._lock:
            return (self._global and self._tenant.get(tenant, True)
                    and self._clase.get(clase, True))


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class Panico:
    def __init__(self, *, palancas: Palancas | None = None, bitacoras: dict | None = None,
                 ruta_estado: Path | str | None = None) -> None:
        self.palancas = palancas or Palancas()
        self.bitacoras = bitacoras if bitacoras is not None else {}
        self.ruta_estado = Path(ruta_estado) if ruta_estado else None
        self._activo = False
        self._lock = threading.Lock()
        self._cargar_estado()

    # ── persistencia (R-08): sobrevivir a reinicios ──
    def _cargar_estado(self) -> None:
        if self.ruta_estado is None or not self.ruta_estado.exists():
            return
        try:
            d = json.loads(self.ruta_estado.read_text(encoding="utf-8"))
            self._activo = bool(d.get("activo", False))
        except (OSError, json.JSONDecodeError):
            # Fichero de estado ilegible = duda; la seguridad degrada CERRANDO (GR-04):
            self._activo = True

    def _persistir(self, *, por: str, motivo: str = "") -> None:
        if self.ruta_estado is None:
            return
        contenido = json.dumps({"activo": self._activo, "por": por, "motivo": motivo,
                                "ts": _ts()}, ensure_ascii=False, sort_keys=True)
        self.ruta_estado.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta_estado.with_suffix(".tmp")
        tmp.write_text(contenido, encoding="utf-8")
        os.replace(tmp, self.ruta_estado)
        if self.ruta_estado.read_text(encoding="utf-8") != contenido:      # E1
            raise IOError(f"E1: desfase al persistir el panico en {self.ruta_estado}")

    @property
    def activo(self) -> bool:
        with self._lock:
            return self._activo

    def activar(self, *, por: str, motivo: str = "") -> None:
        with self._lock:
            self._activo = True
            self._persistir(por=por, motivo=motivo)
        for t, b in dict(self.bitacoras).items():
            b.publicar(Sobre(tenant_id=t, tipo="plataforma.panico.activado",
                             payload={"por": por, "motivo": motivo}, origen="plataforma.panico"))

    def desactivar(self, *, por: str) -> None:
        """Exige accion explicita del operador con registro (D00 §8.2)."""
        if por != "operador":
            raise PermissionError("solo el operador desactiva el panico")
        with self._lock:
            self._activo = False
            self._persistir(por=por)
        for t, b in dict(self.bitacoras).items():
            b.publicar(Sobre(tenant_id=t, tipo="plataforma.panico.desactivado",
                             payload={"por": por}, origen="plataforma.panico"))

    def gate_irrext(self, tenant: str, clase: str = "IRREVERSIBLE-EXTERNA") -> None:
        """DELANTE de toda ejecucion IRR-EXT. Corta en ≤1 ciclo; conserva colas."""
        if clase != "IRREVERSIBLE-EXTERNA":
            return
        if self.activo:
            raise PanicoActivo(f"panico activo: {tenant} no externaliza nada; cola conservada")
        if not self.palancas.abierta(tenant, clase):
            raise PalancaCerrada(f"palanca cerrada para ({tenant}, {clase})")
