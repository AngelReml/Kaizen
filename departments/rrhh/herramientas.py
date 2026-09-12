"""Herramientas deterministas de RRHH / gestión de agentes (tesis §3.9).

RRHH en clave Kaizen gestiona los propios agentes del sistema: qué existe, qué falta, cómo
rinden. Es introspección del sistema sobre sí mismo. Por eso sus herramientas leen el
catálogo de cubos, el registro de roles del comité y los contadores de ejecución que el
agente acumula del bus —no datos de negocio.
"""
from __future__ import annotations

from core.resiliencia.arranque import CUBOS_CATALOGO

# Tasa de fallo (fallos / (fallos+completados)) que dispara alerta de rendimiento.
UMBRAL_TASA_FALLO = 0.30
MIN_EJECUCIONES = 5          # no alertar con muy pocas ejecuciones (ruido estadístico)


def mapa_capacidades(activos: set[str]) -> dict:
    """Compara los cubos activos contra el catálogo objetivo de los diez (§3)."""
    catalogo = set(CUBOS_CATALOGO)
    presentes = sorted(activos & catalogo)
    faltantes = sorted(catalogo - activos)
    extra = sorted(activos - catalogo)      # cubos activos fuera del catálogo (p. ej. alias)
    cobertura = round(len(presentes) / len(catalogo), 3) if catalogo else 0.0
    return {"catalogo": sorted(catalogo), "presentes": presentes, "faltantes": faltantes,
            "fuera_de_catalogo": extra, "cobertura": cobertura}


def roles_comite() -> dict:
    """Inventario de roles del comité de verificación (capacidad del cubo OpenGravity)."""
    from core.opengravity.role_registry import ROLE_REGISTRY, DOMINIOS
    negocio = [r for r in ROLE_REGISTRY.values() if r.domain in DOMINIOS]
    transversales = [r.role_id for r in ROLE_REGISTRY.values() if r.transversal]
    return {"roles_negocio": len(negocio), "transversales": sorted(set(transversales)),
            "dominios": list(DOMINIOS)}


def detectar_bajo_rendimiento(completados: dict[str, int], fallos: dict[str, int]) -> list[dict]:
    """Departamentos cuya tasa de fallo supera el umbral (con muestra suficiente)."""
    alertas = []
    for dept in set(completados) | set(fallos):
        ok = completados.get(dept, 0)
        ko = fallos.get(dept, 0)
        total = ok + ko
        if total < MIN_EJECUCIONES:
            continue
        tasa = ko / total if total else 0.0
        if tasa >= UMBRAL_TASA_FALLO:
            alertas.append({"departamento": dept, "tasa_fallo": round(tasa, 3),
                            "fallos": ko, "ejecuciones": total})
    return sorted(alertas, key=lambda a: a["tasa_fallo"], reverse=True)


def propuestas_mejora(mapa: dict, bajo_rendimiento: list[dict]) -> list[str]:
    """Convierte el mapa de capacidades y el rendimiento en propuestas accionables (§3.9)."""
    props: list[str] = []
    # Orden de construcción del catálogo (§3.11) para sugerir el siguiente cubo a activar.
    orden = list(CUBOS_CATALOGO)
    for dept in orden:
        if dept in mapa.get("faltantes", []):
            props.append(f"Activar el cubo «{dept}»: falta para completar el catálogo "
                         f"(cobertura actual {int(mapa.get('cobertura',0)*100)}%).")
            break   # solo el siguiente según orden de valor
    for a in bajo_rendimiento:
        props.append(f"Revisar «{a['departamento']}»: tasa de fallo {int(a['tasa_fallo']*100)}% "
                     f"en {a['ejecuciones']} ejecuciones.")
    if not props:
        props.append("Sin huecos de capacidad ni alertas de rendimiento. Sistema saludable.")
    return props
