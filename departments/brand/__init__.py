"""Departamento Brand — el segundo cubo del catálogo (tesis §3.2, §6.4).

Define y protege cómo la empresa se ve, suena y se percibe. Intercepta todo lo que sale
del sistema y verifica que suena a esa empresa concreta. Primer cubo que levanta comités
de verificación (para validar campañas).

Cuatro sub-agentes:
  * Brand Strategist — posicionamiento, tono, valores (rol nuevo).
  * Brand Guardian   — revisa cada artefacto saliente (promovido del Comercial, §6.4).
  * Asset Manager    — custodia logos, plantillas, paletas (rol nuevo).
  * Voice Auditor    — evalúa turnos del agente en llamadas (heredado del Comercial).
"""
from departments.brand.brand_guardian import BrandGuardian, BrandReview
from departments.brand.brand_strategist import BrandStrategist
from departments.brand.asset_manager import AssetManager
from departments.brand.voice_auditor import VoiceAuditor, DictamenTono
from departments.brand.director import DirectorBrand

__all__ = [
    "BrandGuardian", "BrandReview", "BrandStrategist", "AssetManager",
    "VoiceAuditor", "DictamenTono", "DirectorBrand",
]
