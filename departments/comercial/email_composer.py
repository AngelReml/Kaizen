"""EmailComposer — genera asunto + cuerpo personalizado para un lead.

Usa Claude Sonnet 4.6 con el `REDACTOR_SYSTEM` ya validado en agentes.py (que produce los
correos que enviamos por el Diario actual). Personaliza con datos concretos del lead que
vienen del Researcher/Enrichment (categoría, ciudad, rating, tipo).

Pasa cada borrador por el Brand Guardian; si falla, hace un reintento incluyendo el
feedback como contexto de regeneración (hasta `intentos_max`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import claude_client as ai
import diario_ops as diario
from agentes import REDACTOR_SYSTEM, REDACTOR_ASUNTO_SYSTEM
from departments.comercial.brand_guardian import BrandGuardian, BrandReview


@dataclass
class Borrador:
    asunto: str
    cuerpo: str
    review: BrandReview
    intentos: int = 1
    lead_id: str | None = None
    razones_de_personalizacion: list[str] = field(default_factory=list)

    @property
    def aprobado_por_brand(self) -> bool:
        return self.review.aprobado


class EmailComposer:
    def __init__(self, *, empresa: str = "laboratorio",
                 brand_guardian: BrandGuardian | None = None,
                 chat=None,                                    # inyección para tests
                 intentos_max: int = 2) -> None:
        self.empresa = empresa
        self.brand = brand_guardian or BrandGuardian(empresa=empresa)
        self.chat = chat or ai.chat
        self.intentos_max = max(1, intentos_max)
        self._contexto_negocio = diario.read("CONTEXTO_NEGOCIO", empresa)

    def componer(self, lead: dict) -> Borrador:
        feedback: str = ""
        for intento in range(1, self.intentos_max + 1):
            asunto, cuerpo = self._generar(lead, feedback)
            review = self.brand.revisar(asunto, cuerpo, lead=lead, usar_llm=True)
            if review.aprobado:
                # E4 / cierre F-01: la transparencia AI Act se aplica EN COMPOSICIÓN
                # (fallar pronto), no en envío. Reintentar no ayuda si no hay
                # variante aprobada, así que se devuelve el veredicto tal cual.
                cuerpo, review = self._aplicar_transparencia(cuerpo, review)
                return Borrador(asunto=asunto, cuerpo=cuerpo, review=review,
                                intentos=intento, lead_id=lead.get("id"),
                                razones_de_personalizacion=self._razones(lead))
            # Reintento incorporando los problemas como feedback.
            feedback = (
                "\n\nNota: el intento anterior fue rechazado por el Brand Guardian con estos "
                f"problemas:\n- " + "\n- ".join(review.problemas)
                + "\nReescribe el borrador corrigiendo esos puntos sin perder personalización."
            )
        # Si ningún intento pasa, devolvemos el último para que el operador lo vea.
        return Borrador(asunto=asunto, cuerpo=cuerpo, review=review,
                        intentos=self.intentos_max, lead_id=lead.get("id"),
                        razones_de_personalizacion=self._razones(lead))

    def _aplicar_transparencia(self, cuerpo: str, review: BrandReview) -> tuple[str, "BrandReview"]:
        """AI Act art. 50 (candado E4, en vigor desde 2026-08-02): inserta la variante
        de transparencia APROBADA POR EL OPERADOR (aiact_email_variantes.md). Si no
        hay variante aprobada y el cuerpo no se identifica como IA, el borrador queda
        NO aprobado con el motivo explícito — fail-closed en composición."""
        from dataclasses import replace
        from core import aiact_gate
        if not aiact_gate.candado_activo():
            return cuerpo, review
        if not aiact_gate.tiene_disclosure(cuerpo):
            variante = aiact_gate.variante_email_activa(empresa=self.empresa)
            if variante:
                cuerpo = cuerpo.rstrip() + "\n\n" + variante
        if not aiact_gate.tiene_disclosure(cuerpo):
            review = replace(review, aprobado=False, problemas=list(review.problemas) + [
                "AI Act art. 50: no hay variante de transparencia APROBADA para email "
                "(cubos/comercial/aiact_email_variantes.md, sección APROBADAS) y el "
                "cuerpo no se identifica como IA. El operador debe aprobar un texto."])
        return cuerpo, review

    def _generar(self, lead: dict, feedback: str) -> tuple[str, str]:
        ficha = self._formatear_ficha(lead)
        prompt = (
            f"=== FICHA DEL CANDIDATO ===\n{ficha}\n\n"
            f"=== CONTEXTO DE LA EMPRESA ===\n{self._contexto_negocio[:1500]}\n\n"
            "Redacta el cuerpo del primer mensaje de contacto, personalizado y listo para enviar. "
            "Fírmalo con los datos del remitente que aparecen en el contexto."
            f"{feedback}"
        )
        cuerpo = self.chat(
            [{"role": "user", "content": prompt}],
            system=REDACTOR_SYSTEM,
            model="claude-sonnet-4-6",
            max_tokens=800,
            company=self.empresa,
        ).strip()
        asunto = self.chat(
            [{"role": "user", "content": f"Candidato: {lead.get('nombre','')}\nBorrador:\n{cuerpo}"}],
            system=REDACTOR_ASUNTO_SYSTEM,
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            company=self.empresa,
        ).strip()
        return asunto, cuerpo

    def _formatear_ficha(self, lead: dict) -> str:
        ubic = lead.get("ubicacion", {})
        meta = lead.get("metadatos_fuente", {}) or {}
        contacto = lead.get("contacto", {}) or {}
        rating = meta.get("rating")
        reseñas = meta.get("ratings_count")
        rating_txt = f"{rating} ({reseñas} reseñas)" if rating else "sin reseñas disponibles"
        return (
            f"Nombre: {lead.get('nombre','')}\n"
            f"Tipo: {lead.get('categoria_icp','')} (prioridad {lead.get('prioridad_icp','')})\n"
            f"Ciudad/dirección: {ubic.get('direccion','')}\n"
            f"Anillo logístico: {lead.get('anillo','?')} ({lead.get('distancia_minutos','?')} min en coche)\n"
            f"Tamaño estimado: {lead.get('tamano_estimado','desconocido')}\n"
            f"Valoración pública: {rating_txt}\n"
            f"Web: {contacto.get('web','')}\n"
            f"Teléfono: {contacto.get('telefono','')}\n"
            f"Descripción: {lead.get('descripcion','')}\n"
        )

    @staticmethod
    def _razones(lead: dict) -> list[str]:
        """Para mostrar en la cola: qué señales se usaron para personalizar."""
        out = []
        if lead.get("categoria_icp"):
            out.append(f"categoría ICP: {lead['categoria_icp']}")
        if lead.get("anillo") is not None:
            out.append(f"anillo {lead['anillo']} · {lead.get('distancia_minutos','?')} min")
        if (lead.get("metadatos_fuente") or {}).get("rating"):
            out.append(f"rating {lead['metadatos_fuente']['rating']}")
        return out
