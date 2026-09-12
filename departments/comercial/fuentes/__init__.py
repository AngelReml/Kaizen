"""Fuentes de descubrimiento de candidatos.

Cada fuente implementa `FuenteLeads.buscar(...)` y devuelve `CandidatoCrudo`. El Researcher
las orquesta en paralelo y deduplica.
"""
