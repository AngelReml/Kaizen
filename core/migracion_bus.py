"""Umbral de migración del bus: SQLite → Redis (tesis §7.4).

El documento hijo fija el umbral medible que dispara la migración, para que la decisión no
se tome ni por intuición ni bajo la presión de un incidente. Se observan CUATRO métricas
diarias sobre el propio log del bus. La migración se dispara cuando AL MENOS DOS de las
cuatro cruzan su umbral durante TRES días consecutivos.

CORRECCIÓN DE CRITERIO DE LA v1.1 (§7.4): las cifras son ESTIMACIÓN, no medición. Están
razonadas pero no hay aún evidencia operativa con varios departamentos en paralelo que las
respalde. Se tratan como punto de partida y se recalibran con datos reales. El umbral
ABRE la decisión, no la ejecuta: cuando se cumple, el operador revisa los 7 días de
evidencia, estima coste y decide. Hasta entonces, el sistema sigue sobre SQLite.

Disparador cualitativo adicional: tres o más departamentos activos donde alguno necesite
respuesta síncrona en < 1 s.

Disparadores que NO cuentan (para no migrar por las razones equivocadas, §7.4):
"vamos a tener varias empresas", "queremos histórico más largo", "nos vamos a producción",
"sería más profesional".
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from core.bloqueo import bloqueo_exclusivo

_RAIZ = Path(__file__).resolve().parent.parent
def _default_dir():
    from core.rutas import dir_state
    return dir_state()

# ── Los cuatro umbrales (ESTIMACIÓN, no medición — §7.4) ──────────────────────
UMBRALES = {
    "events_per_minute_p95": 200.0,      # ~3× el ritmo de 1 departamento con voz
    "concurrent_subscribers": 5.0,       # ~3-4 departamentos compartiendo un EventType
    "consumer_lag_seconds_p95": 5.0,     # por encima se rompe el tiempo real del dashboard
    "db_write_latency_ms_p95": 25.0,     # SQLite con WAL escribe en 1-2 ms; 25 ms = contención
}
ES_ESTIMACION = True                     # candado de la corrección de la v1.1
METRICAS_MINIMAS_PARA_MIGRAR = 2         # al menos 2 de 4
DIAS_CONSECUTIVOS = 3
DEPARTAMENTOS_SINCRONOS_CUALITATIVO = 3  # disparador cualitativo

# Razones que explícitamente NO disparan migración (§7.4).
RAZONES_INVALIDAS = (
    "vamos a tener varias empresas", "queremos histórico más largo",
    "nos vamos a producción", "sería más profesional",
)


def percentil(valores: list[float], p: float = 95) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordenados) - 1)
    if f == c:
        return ordenados[f]
    return ordenados[f] + (ordenados[c] - ordenados[f]) * (k - f)


@dataclass
class MuestraDiaria:
    dia: str                              # ISO date
    metricas: dict                        # nombre → valor p95 del día
    cruzadas: list[str] = field(default_factory=list)

    @property
    def n_cruzadas(self) -> int:
        return len(self.cruzadas)


class MonitorMigracion:
    """Acumula muestras diarias y decide si la migración debe ABRIRSE (nunca ejecutarse)."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or _default_dir()
        self._path = self._dir / "migracion_bus.json"
        self._lock = threading.Lock()
        self._dias: list[dict] = self._load()

    def _load(self) -> list:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return []
        return []

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._dias, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def registrar_dia(self, metricas: dict, *, dia: str | None = None) -> MuestraDiaria:
        """Registra las cuatro métricas p95 de un día y calcula cuáles cruzan su umbral."""
        dia = dia or str(date.today())
        cruzadas = [m for m, u in UMBRALES.items() if float(metricas.get(m, 0)) >= u]
        muestra = {"dia": dia, "metricas": metricas, "cruzadas": cruzadas}
        # Candado ENTRE PROCESOS (auditoría 2026-08-02): un `threading.Lock` no basta
        # cuando el CLI y el panel son procesos distintos escribiendo el mismo fichero.
        # Se envuelve el ciclo leer-mutar-escribir COMPLETO, no solo el flush: se
        # recarga `self._dias` desde disco dentro del candado, justo antes de mutar.
        with self._lock, bloqueo_exclusivo(self._path):
            self._dias = self._load()
            # Reemplaza la muestra del día si ya existía.
            self._dias = [d for d in self._dias if d.get("dia") != dia]
            self._dias.append(muestra)
            self._dias.sort(key=lambda d: d["dia"])
            self._save()
        return MuestraDiaria(dia, metricas, cruzadas)

    def desde_bus_sqlite(self, bus, *, consumer_lag_seconds_p95: float = 0.0,
                         dia: str | None = None) -> MuestraDiaria:
        """Toma una muestra de un SQLitePersistentBus. El lag se pasa aparte (lo conoce el
        orquestador de consumidores, no el bus)."""
        metricas = {
            "events_per_minute_p95": bus.eventos_por_minuto(),
            "concurrent_subscribers": float(bus.max_suscriptores_un_tipo()),
            "consumer_lag_seconds_p95": consumer_lag_seconds_p95,
            "db_write_latency_ms_p95": percentil(bus.latencias_escritura()),
        }
        return self.registrar_dia(metricas, dia=dia)

    def dias_consecutivos_sobre_umbral(self) -> int:
        """Cuenta los últimos días consecutivos con ≥2 métricas cruzadas."""
        racha = 0
        for d in reversed(self._dias):
            if len(d.get("cruzadas", [])) >= METRICAS_MINIMAS_PARA_MIGRAR:
                racha += 1
            else:
                break
        return racha

    def decision_abierta(self) -> bool:
        """¿Se cumple el umbral cuantitativo (2 de 4 durante 3 días consecutivos)?"""
        return self.dias_consecutivos_sobre_umbral() >= DIAS_CONSECUTIVOS

    @staticmethod
    def disparador_cualitativo(n_departamentos_activos: int,
                               alguno_necesita_sincrono_sub_segundo: bool) -> bool:
        return (n_departamentos_activos >= DEPARTAMENTOS_SINCRONOS_CUALITATIVO
                and alguno_necesita_sincrono_sub_segundo)

    @staticmethod
    def razon_valida(razon: str) -> bool:
        """False si la razón es uno de los disparadores que NO cuentan (§7.4)."""
        return (razon or "").strip().lower() not in {r.lower() for r in RAZONES_INVALIDAS}

    def panel(self) -> dict:
        """Panel de salud del sistema nervioso para el dashboard del operador (§7.4)."""
        ultimo = self._dias[-1] if self._dias else {"metricas": {}, "cruzadas": []}
        filas = []
        for m, u in UMBRALES.items():
            valor = float(ultimo.get("metricas", {}).get(m, 0))
            filas.append({"metrica": m, "umbral": u, "valor": valor,
                          "cruza": valor >= u})
        return {
            "es_estimacion": ES_ESTIMACION,
            "metricas": filas,
            "dias_consecutivos_sobre_umbral": self.dias_consecutivos_sobre_umbral(),
            "dias_necesarios": DIAS_CONSECUTIVOS,
            "decision_abierta": self.decision_abierta(),
            "nota": ("Las cifras son estimación, no medición. El umbral ABRE la decisión, "
                     "no migra: el operador revisa la evidencia y decide. Sistema sigue sobre SQLite."),
        }

    def emitir_si_abierta(self, bus, company: str = "default") -> bool:
        """Si la decisión está abierta, publica bus.migration_threshold_open. Devuelve si emitió."""
        if not self.decision_abierta():
            return False
        from core.events import Event, EventType, Criticality
        bus.publish(Event(
            EventType.BUS_MIGRATION_THRESHOLD_OPEN, source="sistema_nervioso",
            payload={"panel": self.panel(),
                     "mensaje": "Umbral de migración SQLite→Redis ABIERTO. Decisión del operador."},
            company=company, criticality=Criticality.HIGH))
        return True
