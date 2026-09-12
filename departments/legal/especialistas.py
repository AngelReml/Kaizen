"""Especialistas del departamento Legal (Bloque 3)."""
from __future__ import annotations

from core.task_classes import ClaseTarea
from departments.base import Especialista
from departments.legal import herramientas as h


class ExtractorDeClausulas(Especialista):
    nombre = "ExtractorDeClausulas"
    departamento = "legal"
    clase = ClaseTarea.EXTRACCION
    descripcion = "Segmenta el contrato en cláusulas."

    def ejecutar(self, input: dict, context: dict) -> dict:
        texto = input.get("texto_contrato") or input.get("contrato", "")
        clausulas = h.analizar_contrato(texto)["clausulas"]
        return {"clausulas": [{"numero": i + 1, "texto": c} for i, c in enumerate(clausulas)]}


class ClasificadorDeRiesgo(Especialista):
    nombre = "ClasificadorDeRiesgo"
    departamento = "legal"
    clase = ClaseTarea.RAZONAMIENTO
    descripcion = "Evalúa cada cláusula contra la base curada."

    def ejecutar(self, input: dict, context: dict) -> dict:
        evaluaciones = []
        for cl in input.get("clausulas", []):
            r = h.consultar_clausula_problematica(cl["texto"])
            evaluaciones.append({
                "clausula_id": cl.get("numero"),
                "riesgo": r["gravedad"] or "bajo",
                "motivo": r["motivo"],
                "bloquear": r["gravedad"] == "alta",
            })
        return {"evaluaciones": evaluaciones}


class ComparadorConPlantilla(Especialista):
    nombre = "ComparadorConPlantilla"
    departamento = "legal"
    clase = ClaseTarea.FUNCION
    descripcion = "Diff estructurado contra una plantilla."

    def ejecutar(self, input: dict, context: dict) -> dict:
        import diario_ops
        company = context.get("company", "default")
        plantilla = diario_ops.read("plantilla_contrato", company)
        if not plantilla.strip():
            return {"diferencias": [], "puntuacion_similitud": 0.0,
                    "advertencia": "No hay plantilla configurada para esta empresa"}
        contrato = input.get("texto_contrato") or input.get("contrato", "")
        requeridos = [l.strip() for l in plantilla.splitlines() if l.strip()]
        r = h.comparar_con_plantilla(contrato, requeridos)
        total = len(requeridos) or 1
        return {"diferencias": r["diferencias"],
                "puntuacion_similitud": round(1 - len(r["diferencias"]) / total, 3)}


class SintetizadorDeInforme(Especialista):
    nombre = "SintetizadorDeInforme"
    departamento = "legal"
    clase = ClaseTarea.SINTETIZAR
    descripcion = "Resumen ejecutivo: qué firmar, negociar o rechazar."

    def ejecutar(self, input: dict, context: dict) -> dict:
        evs = input.get("evaluaciones", [])
        bloqueantes = [e for e in evs if e.get("bloquear")]
        texto = self._chat(
            [{"role": "user", "content": f"Evaluaciones: {evs}\nDiferencias: {input.get('diferencias', [])}"}],
            system="Eres el Departamento Legal. Resume para el humano: qué firmar, qué negociar y qué rechazar.",
            company=context.get("company", "default"),
        )
        return {"informe_md": texto, "bloqueantes": len(bloqueantes)}
