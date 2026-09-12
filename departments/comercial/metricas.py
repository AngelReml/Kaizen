"""Métricas del departamento con bandas verde/ámbar/rojo (§7.1 del v0.2).

Calcula a partir del estado actual del `LeadStore` y de los resultados de la última pasada
de Researcher/Enrichment. Solo Fase 0 está activa hoy; las métricas de SDR/AE/AM quedan
como ranuras con valor `None` hasta que sus roles se enciendan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from departments.comercial.enrichment import ResultadoEnrichment
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.researcher import ResultadoPasada

Banda = Literal["VERDE", "AMBAR", "ROJO", "NO_APLICA"]


@dataclass
class Metrica:
    nombre: str
    rol: str
    valor: float | None
    unidad: str                  # "%", "días", "n"
    banda: Banda
    detalle: str = ""


@dataclass
class CuadroMetricas:
    metricas: list[Metrica] = field(default_factory=list)
    gates_fase0: dict = field(default_factory=dict)    # ¿están superados los gates del §2.1?
    cualificados_total: int = 0
    enriquecidos_total: int = 0

    def metrica(self, nombre: str) -> Metrica | None:
        return next((m for m in self.metricas if m.nombre == nombre), None)


def _banda(valor: float | None, verde_min: float, ambar_min: float,
           mayor_es_mejor: bool = True) -> Banda:
    """Clasifica un valor en bandas. Si `mayor_es_mejor`, verde es `>=verde_min`; si no
    (caso "tasa de abandono"), verde es `<=verde_min`."""
    if valor is None:
        return "NO_APLICA"
    if mayor_es_mejor:
        if valor >= verde_min: return "VERDE"
        if valor >= ambar_min: return "AMBAR"
        return "ROJO"
    if valor <= verde_min: return "VERDE"
    if valor <= ambar_min: return "AMBAR"
    return "ROJO"


def calcular(lead_store: LeadStore, *, ultima_pasada: ResultadoPasada | None = None,
             ultimo_enrichment: ResultadoEnrichment | None = None) -> CuadroMetricas:
    cuentas = lead_store.contar_por_estado()
    cualificados_total = (cuentas.get(EstadoLead.CUALIFICADO.value, 0)
                          + cuentas.get(EstadoLead.ENRIQUECIDO.value, 0)
                          + cuentas.get(EstadoLead.EN_CONTACTO.value, 0)
                          + cuentas.get(EstadoLead.COMPROMISO_RECIPROCO.value, 0)
                          + cuentas.get(EstadoLead.MUESTRA_ENVIADA.value, 0)
                          + cuentas.get(EstadoLead.CLIENTE_ACTIVO.value, 0)
                          + cuentas.get(EstadoLead.EN_RIESGO.value, 0))
    enriquecidos_total = (cuentas.get(EstadoLead.ENRIQUECIDO.value, 0)
                          + cuentas.get(EstadoLead.EN_CONTACTO.value, 0)
                          + cuentas.get(EstadoLead.COMPROMISO_RECIPROCO.value, 0)
                          + cuentas.get(EstadoLead.MUESTRA_ENVIADA.value, 0)
                          + cuentas.get(EstadoLead.CLIENTE_ACTIVO.value, 0)
                          + cuentas.get(EstadoLead.EN_RIESGO.value, 0))

    metricas: list[Metrica] = []

    # 1) Researcher — % candidatos que pasan el ICP (§7.1 fila 1).
    if ultima_pasada and ultima_pasada.candidatos_unicos:
        pasan_icp = ultima_pasada.candidatos_unicos - ultima_pasada.descartes_icp
        pct = pasan_icp / ultima_pasada.candidatos_unicos * 100
        metricas.append(Metrica(
            "pct_pasan_icp", "Researcher", round(pct, 1), "%",
            _banda(pct, 60, 40),
            f"{pasan_icp}/{ultima_pasada.candidatos_unicos} candidatos pasaron ICP",
        ))
    else:
        metricas.append(Metrica("pct_pasan_icp", "Researcher", None, "%", "NO_APLICA",
                                "sin pasada del Researcher aún"))

    # 2) Enrichment — % de leads con contacto verificado y actual (§7.1 fila 2).
    base = cualificados_total
    pct_verif = (enriquecidos_total / base * 100) if base else None
    metricas.append(Metrica(
        "pct_contacto_verificado", "Enrichment", round(pct_verif, 1) if pct_verif is not None else None,
        "%", _banda(pct_verif, 85, 70),
        f"{enriquecidos_total}/{base} leads en estado ENRIQUECIDO o posterior",
    ))

    # 3-6) SDR / Account Executive / Account Manager — sin datos en Fase 0.
    for nombre, rol in [
        ("tasa_contacto_efectiva", "SDR"),
        ("pct_compromiso_reciproco", "SDR"),
        ("pct_muestra_a_primer_pedido", "Account Executive"),
        ("pct_activos_con_pedido_30d", "Account Manager"),
    ]:
        metricas.append(Metrica(nombre, rol, None, "%", "NO_APLICA",
                                "fase posterior (no aplica en Fase 0)"))

    # 7) Departamento — tasa de abandono por fase (perdidos / identificados_totales).
    perdidos = cuentas.get(EstadoLead.PERDIDO.value, 0)
    total_vistos = sum(cuentas.values())
    if total_vistos:
        tasa_abandono = perdidos / total_vistos * 100
        metricas.append(Metrica(
            "tasa_abandono_pipeline", "Departamento", round(tasa_abandono, 1), "%",
            _banda(tasa_abandono, 15, 25, mayor_es_mejor=False),
            f"{perdidos}/{total_vistos} leads perdidos",
        ))
    else:
        metricas.append(Metrica("tasa_abandono_pipeline", "Departamento", None, "%", "NO_APLICA"))

    # 8) Departamento — tiempo de identificación a muestra enviada (no aplica en Fase 0).
    metricas.append(Metrica("tiempo_id_a_muestra_dias", "Departamento", None, "días", "NO_APLICA",
                            "no se han enviado muestras en Fase 0"))

    # Gates del §2.1 para pasar de Fase 0 a Fase 1.
    gate_cualificados   = cualificados_total >= 100
    pct_descarte_icp    = ultima_pasada.tasa_descarte_icp if ultima_pasada else None
    gate_descarte_icp   = (pct_descarte_icp is not None and pct_descarte_icp < 40)
    pct_verif_real      = pct_verif
    gate_verificado     = (pct_verif_real is not None and pct_verif_real > 85)

    gates_fase0 = {
        "cualificados_100":        {"ok": gate_cualificados,   "valor": cualificados_total, "umbral": 100},
        "descarte_icp_menos_40":   {"ok": gate_descarte_icp,
                                    "valor": round(pct_descarte_icp, 1) if pct_descarte_icp is not None else None,
                                    "umbral": 40},
        "contacto_verificado_85":  {"ok": gate_verificado,
                                    "valor": round(pct_verif_real, 1) if pct_verif_real is not None else None,
                                    "umbral": 85},
    }
    gates_fase0["__superados__"] = all(g["ok"] for g in gates_fase0.values() if isinstance(g, dict))

    return CuadroMetricas(metricas=metricas, gates_fase0=gates_fase0,
                          cualificados_total=cualificados_total,
                          enriquecidos_total=enriquecidos_total)
