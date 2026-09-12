"""Especialistas del departamento de Finanzas (Bloque 3)."""
from __future__ import annotations

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.finanzas import herramientas as h


class _FinBase(Especialista):
    departamento = "finanzas"

    def __init__(self, bus=None, knowledge=None) -> None:
        super().__init__(bus)
        from core.knowledge import get_knowledge
        self.knowledge = knowledge or get_knowledge()   # backend activo (singleton)


class AgregadorDeDatos(_FinBase):
    nombre = "AgregadorDeDatos"
    clase = ClaseTarea.FUNCION
    descripcion = "Agrega gastos por periodo/categoría desde la memoria."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        datos = h.consultar_gasto(self.knowledge, company, input.get("periodo", "mes"),
                                  input.get("categoria"))
        return {"datos_agregados": datos}


class CalculadorDeMetricas(_FinBase):
    nombre = "CalculadorDeMetricas"
    clase = ClaseTarea.FUNCION
    descripcion = "Calcula runway y anomalías."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = input.get("company") or context.get("company", "default")
        return {"metricas": {
            "quema": h.proyectar_quema(self.knowledge, company),
            "anomalias": h.detectar_anomalia(self.knowledge, company),
        }}


class InterpreteDeTendencias(_FinBase):
    nombre = "InterpreteDeTendencias"
    clase = ClaseTarea.SINTETIZAR
    descripcion = "Traduce métricas a lenguaje ejecutivo."

    def ejecutar(self, input: dict, context: dict) -> dict:
        company = context.get("company", "default")
        metricas = input.get("metricas", {})
        quema = metricas.get("quema", {})
        if not metricas or quema.get("gasto_diario_medio", 0) == 0:
            return {"interpretacion": "Sin datos suficientes para el periodo solicitado."}
        pregunta = input.get("pregunta_original") or context.get("intent", "")
        texto = self._chat(
            [{"role": "user", "content": f"Pregunta: {pregunta}\nMétricas: {metricas}"}],
            system="Eres Finanzas. Traduce estas métricas a una respuesta ejecutiva, breve y clara.",
            company=company,
        )
        return {"interpretacion": texto}
