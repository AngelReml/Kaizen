"""Especialistas del departamento de QA (Bloque 3)."""
from __future__ import annotations

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.qa import herramientas as h


class ValidadorDeEstructura(Especialista):
    nombre = "ValidadorDeEstructura"
    departamento = "qa"
    clase = ClaseTarea.FUNCION
    descripcion = "Verifica secciones requeridas según el tipo de artefacto."

    def ejecutar(self, input: dict, context: dict) -> dict:
        artefacto = input.get("artefacto", "")
        requeridos = input.get("secciones_requeridas", [])
        r = h.comparar_con_plantilla(artefacto, requeridos) if requeridos else {"coincide_estructura": True, "diferencias": []}
        return {"ok": r["coincide_estructura"], "secciones_faltantes": r["diferencias"]}


class DetectorDeContradicciones(Especialista):
    nombre = "DetectorDeContradicciones"
    departamento = "qa"
    clase = ClaseTarea.RAZONAMIENTO
    descripcion = "Compara el artefacto con el contexto de la empresa."

    def ejecutar(self, input: dict, context: dict) -> dict:
        # Compara el artefacto con CONTEXTO_NEGOCIO + DECISIONES de la empresa (leídos en runtime).
        # .strip() antes del 'or': sin él, "\n" siempre es truthy y el fallback nunca se usaba.
        contexto = ((context.get("contexto_negocio", "") + "\n" + context.get("decisiones", "")).strip()
                    or input.get("contexto_empresa", ""))
        r = h.detectar_contradicciones(input.get("artefacto", ""), contexto)
        return {"contradicciones": r["contradicciones"]}


class CalificadorDeCalidad(Especialista):
    nombre = "CalificadorDeCalidad"
    departamento = "qa"
    clase = ClaseTarea.CLASIFICACION
    descripcion = "Puntúa 0-10 con desglose y recomendaciones."

    def ejecutar(self, input: dict, context: dict) -> dict:
        problemas = (input.get("secciones_faltantes") or []) + (input.get("contradicciones") or [])
        puntuacion = max(0, 10 - 2 * len(problemas))
        return {"puntuacion": puntuacion,
                "desglose": {"problemas": len(problemas)},
                "recomendaciones": problemas[:3]}
