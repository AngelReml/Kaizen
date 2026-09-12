"""Departamento de Operaciones (Ops) — pedidos, capacidad, inventario (Fase 5.2).

Sigue la plantilla de docs/COMO_CREAR_UN_DEPARTAMENTO.md.
"""
from departments.ops.agente import OpsDepartment

# Alias: el roadmap/prompts se refieren a este departamento como OperacionesDepartment.
OperacionesDepartment = OpsDepartment

__all__ = ["OpsDepartment", "OperacionesDepartment"]
