"""Agente conversacional de Finanzas (Fase 1.4).

Reemplaza el cascarón LLM genérico por un departamento real: recibe una pregunta,
elige la herramienta determinista adecuada, la ejecuta y compone la respuesta con datos
reales (no inventados por el LLM).

El selector de herramienta es por palabras clave (determinista y testeable). La versión
con tool-use de Claude es la evolución natural (queda anotada en docs/DEUDA_TECNICA.md).
"""
from __future__ import annotations

import unicodedata

from departments.base import Department, Task, TaskResult
from departments.finanzas import herramientas as h


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class FinanzasDepartment(Department):
    name = "finanzas"

    def __init__(self, bus, knowledge=None, *, presupuesto_mensual: float | None = None) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()
        self.presupuesto_mensual = presupuesto_mensual
        from departments.base import PipelineDepartamento
        from departments.finanzas.especialistas import (
            AgregadorDeDatos, CalculadorDeMetricas, InterpreteDeTendencias,
        )
        self.pipeline = PipelineDepartamento(
            [AgregadorDeDatos(), CalculadorDeMetricas(), InterpreteDeTendencias()],
            "finanzas", bus=bus,
        )

    def _run_legacy(self, task: Task) -> TaskResult:
        respuesta, herramienta = self.responder(task.intent, task.company)
        return TaskResult(True, respuesta[:200], {"respuesta": respuesta, "herramienta": herramienta})

    def responder(self, pregunta: str, company: str) -> tuple[str, str]:
        """Devuelve (respuesta_texto, nombre_herramienta_usada)."""
        q = _norm(pregunta)
        k, c = self.knowledge, company

        if "anomal" in q or "raro" in q or "atipic" in q:
            an = h.detectar_anomalia(k, c)
            if not an:
                return "No detecto gastos anómalos en el histórico.", "detectar_anomalia"
            lineas = "\n".join(f"- {a['descripcion']}" for a in an)
            return f"Detecté {len(an)} gasto(s) anómalo(s):\n{lineas}", "detectar_anomalia"

        if "compar" in q or "anterior" in q:
            # Periodos disjuntos y homólogos: esta semana vs la anterior (no "semana ⊆ mes").
            r = h.comparar_periodos(k, c, "semana_anterior", "semana")
            return (f"Semana anterior: {r['p1_total']:.4f}€ · Esta semana: {r['p2_total']:.4f}€ "
                    f"(variación {r['variacion_pct']}%).", "comparar_periodos")

        if "dias" in q or "aguant" in q or "runway" in q or "queda" in q:
            r = h.proyectar_quema(k, c, presupuesto_mensual=self.presupuesto_mensual)
            runway = r["dias_runway_si_no_recargas"]
            txt = f"Gasto diario medio {r['gasto_diario_medio']:.4f}€."
            txt += f" Runway estimado: {runway} días." if runway is not None else " (sin presupuesto definido para runway)."
            return txt, "proyectar_quema"

        if "caro" in q or "cara" in q or "costado mas" in q or "mas ha costado" in q:
            top = h.top_acciones_caras(k, c, n=3, periodo="semana")
            if not top:
                return "No hay gastos esta semana.", "top_acciones_caras"
            lineas = "\n".join(f"- {t['accion']}: {t['eur']:.4f}€" for t in top)
            return f"Acciones más caras de la semana:\n{lineas}", "top_acciones_caras"

        # Por defecto: cuánto se ha gastado (mes).
        r = h.consultar_gasto(k, c, "mes")
        return (f"Gasto del mes: {r['total_eur']:.4f}€ en {r['n_acciones']} acciones "
                f"(desglose: {r['desglose_por_modelo']}).", "consultar_gasto")
