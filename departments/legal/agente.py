"""Agente de Legal (Fase 5.3). Analiza contratos/cláusulas; reemplaza el cascarón."""
from __future__ import annotations

from departments.base import Department, Task, TaskResult
from departments.legal import herramientas as h


class LegalDepartment(Department):
    name = "legal"

    def __init__(self, bus, knowledge=None) -> None:
        super().__init__(bus)
        self.knowledge = knowledge
        from departments.base import PipelineDepartamento
        from departments.legal.especialistas import (
            ExtractorDeClausulas, ClasificadorDeRiesgo, ComparadorConPlantilla, SintetizadorDeInforme,
        )
        self.pipeline = PipelineDepartamento(
            [ExtractorDeClausulas(), ClasificadorDeRiesgo(), ComparadorConPlantilla(),
             SintetizadorDeInforme()], "legal", bus=bus,
        )

    def _run_legacy(self, task: Task) -> TaskResult:
        p = task.payload
        texto = p.get("contrato") or p.get("clausula") or p.get("texto")
        if not texto:
            # Falta el insumo: petición de input, no resultado. ok=False (ver QADepartment).
            return TaskResult(False, "Legal: pásame el texto de un contrato o cláusula para analizarlo.", {})
        if p.get("clausula") and not p.get("contrato"):
            r = h.consultar_clausula_problematica(texto)
            txt = (f"Cláusula problemática ({r['gravedad']}): {r['motivo']}"
                   if r["es_problematica"] else "La cláusula no coincide con patrones problemáticos conocidos.")
            return TaskResult(not r["es_problematica"], txt, r)
        an = h.analizar_contrato(texto)
        ok = not an["riesgos"]
        txt = (f"{len(an['clausulas'])} cláusulas. Riesgos altos: {len(an['riesgos'])}, "
               f"puntos de atención: {len(an['puntos_atencion'])}.")
        return TaskResult(ok, txt, an)
