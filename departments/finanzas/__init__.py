"""Departamento de Finanzas — primer departamento especialista real (Fase 1).

Plantilla de cómo se construye un departamento: modelo de datos sobre el KnowledgeStore,
ingestor de eventos del bus, reglas duras propias, herramientas de consulta deterministas
y un agente conversacional que las orquesta. Ver docs/COMO_CREAR_UN_DEPARTAMENTO.md.
"""
from departments.finanzas.agente import FinanzasDepartment

__all__ = ["FinanzasDepartment"]
