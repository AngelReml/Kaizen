"""Preventivo o forense: cuándo bloquea y cuándo audita (tesis §6.5).

Modelo dual de criterio determinista. No se elige por capricho del departamento ni por
prompt: se elige por clasificación del artefacto sobre un catálogo explícito.

  Preventivo (gate): el output afecta a un tercero externo y su reversión costaría
    (contratos firmables, propuestas con cifras vinculantes, lanzamientos públicos, gasto
    sobre umbral, campañas). El cubo se BLOQUEA hasta veredicto.
  Forense (auditor): todo lo demás (emails fríos individuales, transcripts post-llamada,
    transiciones de estado, cualificaciones, mensajes operativos). El cubo EJECUTA de
    inmediato; el veredicto llega después.

Dos reglas duras ganan SIEMPRE sobre el catálogo (§6.5):
  R1. Cualquier artefacto que comprometa firma, cifra o cuenta de un tercero externo es
      preventivo aunque el catálogo lo marque forense.
  R2. Cualquier empresa con cumplimiento sectorial estricto (sanitario, financiero,
      infantil) fuerza preventivo en los dominios que tocan ese cumplimiento, salvo
      override firmado por el operador y auditado como ADR.

El catálogo no es ley natural (§6.5): se ajusta con la evidencia, pero cada ajuste se
documenta como ADR por empresa, nunca como cambio silencioso. La promoción/degradación
automática vive en `evaluar_ajuste_catalogo()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Modo(str, Enum):
    PREVENTIVO = "preventive"
    FORENSE = "forensic"


# ── Catálogo base de tipos de artefacto → modo por defecto (§6.5) ─────────────
CATALOGO_PREVENTIVO: set[str] = {
    "contrato_firmable", "propuesta_vinculante", "lanzamiento_publico",
    "campana", "gasto_sobre_umbral", "comunicado_publico", "cotizacion_vinculante",
}
CATALOGO_FORENSE: set[str] = {
    "email_frio", "transcript_post_llamada", "transicion_estado",
    "cualificacion", "mensaje_operativo", "borrador_interno", "nota_interna",
}

# Sectores con cumplimiento estricto (R2). Empresa marca su sector en perfil.json.
SECTORES_ESTRICTOS: set[str] = {"sanitario", "salud", "financiero", "banca", "infantil", "menores"}

# Señales de que un artefacto compromete firma/cifra/cuenta de un tercero (R1).
_SENALES_COMPROMISO_TERCERO = (
    "firma", "firmar", "firmado", "iban", "transferencia", "pago a", "importe de",
    "precio final", "total a pagar", "cuenta bancaria", "número de cuenta",
    "numero de cuenta", "vinculante", "se compromete a pagar", "factura por",
)


@dataclass
class Clasificacion:
    modo: Modo
    motivo: str
    regla_dura: str | None = None      # "R1" | "R2" | None
    bloquea: bool = False              # True si preventivo

    def __post_init__(self) -> None:
        self.bloquea = self.modo is Modo.PREVENTIVO


def _toca_cumplimiento(domain: str | None, sector: str | None) -> bool:
    if not sector or sector.lower() not in SECTORES_ESTRICTOS:
        return False
    # Dominios que tocan cumplimiento en un sector estricto.
    return (domain or "").lower() in {"legal", "finanzas", "brand", "comercial"}


def clasificar(*, artifact_type: str | None = None, artifact_text: str = "",
               domain: str | None = None, sector: str | None = None,
               override_firmado: bool = False) -> Clasificacion:
    """Clasifica un artefacto en preventivo/forense aplicando catálogo + reglas duras.

    `artifact_type` es la clave del catálogo si el departamento la conoce; si no, el modo
    base se infiere conservadoramente como forense salvo que el texto dispare R1.
    `override_firmado` solo lo puede pasar el departamento cuando el operador firmó un ADR.
    """
    t = (artifact_text or "").lower()

    # R1 — compromiso de firma/cifra/cuenta de tercero ⇒ preventivo (gana sobre catálogo).
    if any(s in t for s in _SENALES_COMPROMISO_TERCERO):
        return Clasificacion(Modo.PREVENTIVO,
                             "Compromete firma, cifra o cuenta de un tercero externo.", "R1")

    # R2 — sector estricto en dominio sensible ⇒ preventivo, salvo override firmado (ADR).
    if _toca_cumplimiento(domain, sector) and not override_firmado:
        return Clasificacion(Modo.PREVENTIVO,
                             f"Sector con cumplimiento estricto ({sector}) en dominio {domain}.",
                             "R2")

    # Catálogo base.
    if artifact_type in CATALOGO_PREVENTIVO:
        return Clasificacion(Modo.PREVENTIVO, f"Tipo '{artifact_type}' en catálogo preventivo.")
    if artifact_type in CATALOGO_FORENSE:
        return Clasificacion(Modo.FORENSE, f"Tipo '{artifact_type}' en catálogo forense.")

    # Desconocido ⇒ forense por defecto (no bloquea el flujo; el veredicto llega después).
    return Clasificacion(Modo.FORENSE,
                         f"Tipo '{artifact_type or 'desconocido'}' no catalogado: forense por defecto.")


# ── Ajuste del catálogo por evidencia (§6.5) ──────────────────────────────────
PROMOVER_SI_FAILS_ALTO = 3          # ≥3 FAILs de riesgo alto en la ventana ⇒ candidato a preventivo
VENTANA_PROMOCION_DIAS = 30
DEGRADAR_SI_PASS_CONFIANZA = 0.95   # PASS con confianza ≥0.95 todo un trimestre ⇒ candidato a forense
VENTANA_DEGRADACION_DIAS = 90


@dataclass
class SugerenciaAjuste:
    artifact_type: str
    de: Modo
    a: Modo
    motivo: str
    requiere_adr: bool = True       # cada ajuste se documenta como ADR por empresa (§6.5)


def evaluar_ajuste_catalogo(artifact_type: str, modo_actual: Modo, *,
                            fails_riesgo_alto_30d: int = 0,
                            todos_pass_trimestre: bool = False,
                            confianza_media_trimestre: float = 0.0) -> SugerenciaAjuste | None:
    """Sugiere (no aplica) promover forense→preventivo o degradar preventivo→forense.

    Nunca cambia configuración en silencio: devuelve una sugerencia que el operador
    materializa como ADR. Devuelve None si no procede ajuste.
    """
    if modo_actual is Modo.FORENSE and fails_riesgo_alto_30d >= PROMOVER_SI_FAILS_ALTO:
        return SugerenciaAjuste(
            artifact_type, Modo.FORENSE, Modo.PREVENTIVO,
            f"{fails_riesgo_alto_30d} FAILs de riesgo alto en {VENTANA_PROMOCION_DIAS} días "
            f"(umbral {PROMOVER_SI_FAILS_ALTO}). Candidato a bloquear preventivamente.")
    if (modo_actual is Modo.PREVENTIVO and todos_pass_trimestre
            and confianza_media_trimestre >= DEGRADAR_SI_PASS_CONFIANZA):
        return SugerenciaAjuste(
            artifact_type, Modo.PREVENTIVO, Modo.FORENSE,
            f"Todo PASS con confianza media {confianza_media_trimestre:.2f} "
            f"(≥{DEGRADAR_SI_PASS_CONFIANZA}) durante un trimestre. Bloquea sin necesidad.")
    return None
