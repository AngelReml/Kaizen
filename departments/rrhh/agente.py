"""Departamento RRHH / Personas — gestión de agentes (tesis §3.9).

Gestiona los propios agentes del sistema: qué existe, qué falta, cómo rinden. Es
introspección del sistema sobre sí mismo. Escucha el bus para saber qué cubos están vivos
(cube.started) y cómo rinden (dept.task_completed/failed), y mide la verificación
(opengravity.escalation_requested).

Contrato:
  Consume: el ciclo de vida y las demandas de todos los departamentos (cube.started,
           dept.task_completed, dept.task_failed) y las escaladas de OpenGravity.
  Produce: mapa de capacidades (hr.capability_map) y alertas de rendimiento
           (hr.performance_alert).
"""
from __future__ import annotations

import unicodedata

from core.events import Event, EventType, Criticality
from departments.base import Task, TaskResult
from departments.cubo import CuboDepartamento
from departments.rrhh import herramientas as h


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class RRHHDepartment(CuboDepartamento):
    name = "rrhh"
    consume = (EventType.CUBE_STARTED, EventType.DEPT_TASK_COMPLETED,
               EventType.DEPT_TASK_FAILED, EventType.OPENGRAVITY_ESCALATION_REQUESTED)
    produce = (EventType.HR_CAPABILITY_MAP, EventType.HR_PERFORMANCE_ALERT)

    def __init__(self, bus, company: str = "default") -> None:
        self._activos: set[str] = set()
        self._completados: dict[str, int] = {}
        self._fallos: dict[str, int] = {}
        self._escaladas = 0
        super().__init__(bus, company)

    # ── Contrato: consumo (introspección del bus) ────────────────────────────
    def _registrar_suscripciones(self) -> None:
        self._suscribir(self._on_cube, [EventType.CUBE_STARTED])
        self._suscribir(self._on_completed, [EventType.DEPT_TASK_COMPLETED])
        self._suscribir(self._on_failed, [EventType.DEPT_TASK_FAILED])
        self._suscribir(self._on_escalada, [EventType.OPENGRAVITY_ESCALATION_REQUESTED])

    def _on_cube(self, event: Event) -> None:
        cube = (event.payload or {}).get("cube")
        if cube and cube != self.name:      # no se cuenta a sí mismo como descubrimiento
            self._activos.add(cube)

    def _on_completed(self, event: Event) -> None:
        self._completados[event.source] = self._completados.get(event.source, 0) + 1

    def _on_failed(self, event: Event) -> None:
        self._fallos[event.source] = self._fallos.get(event.source, 0) + 1

    def _on_escalada(self, event: Event) -> None:
        self._escaladas += 1

    # ── Acciones del cubo ────────────────────────────────────────────────────
    def mapa(self) -> dict:
        activos = set(self._activos) | {self.name}     # RRHH también está activo
        m = h.mapa_capacidades(activos)
        self._producir(EventType.HR_CAPABILITY_MAP, m, criticality=Criticality.LOW)
        return m

    def rendimiento(self) -> list[dict]:
        alertas = h.detectar_bajo_rendimiento(self._completados, self._fallos)
        for a in alertas:
            self._producir(EventType.HR_PERFORMANCE_ALERT, a, criticality=Criticality.HIGH)
        return alertas

    def propuestas(self) -> list[str]:
        activos = set(self._activos) | {self.name}
        return h.propuestas_mejora(h.mapa_capacidades(activos),
                                   h.detectar_bajo_rendimiento(self._completados, self._fallos))

    def _run_legacy(self, task: Task) -> TaskResult:
        q = _norm(task.intent)
        if "mapa" in q or "capacidad" in q or "falta" in q or "huec" in q:
            m = self.mapa()
            return TaskResult(True, f"Cobertura {int(m['cobertura']*100)}% · "
                              f"faltan {len(m['faltantes'])} cubos.", {"mapa": m})
        if "rendimiento" in q or "fallo" in q or "rinde" in q:
            a = self.rendimiento()
            return TaskResult(True, f"{len(a)} departamento(s) bajo rendimiento.", {"alertas": a})
        if "propuesta" in q or "mejora" in q or "siguiente" in q:
            p = self.propuestas()
            return TaskResult(True, f"{len(p)} propuesta(s).", {"propuestas": p})
        return TaskResult(True, "RRHH operativo. Pídeme el mapa de capacidades, rendimiento o "
                          "propuestas de mejora.", {"activos": sorted(self._activos)})
