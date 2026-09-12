"""Candado AI Act art. 50 por FECHA — E4 (roadmap F3).

Hito duro AIACT-GATE 2026-08-02 (CORRECCIONES E4): desde esa fecha, TODO mensaje
generado por IA que salga a un tercero debe llevar la transparencia (identificacion
proactiva como sistema automatizado / IA). Las 20 variantes fueron aprobadas por el
operador el 2026-07-03; lo que faltaba era el candado en el ejecutor.

Este modulo es el candado: `exigir_transparencia(texto, ahora=...)`:
  - Desde 2026-08-02 (incl.): si el texto NO contiene disclosure de IA → RECHAZA
    (fail-closed, AIActSinTransparencia). Ningun envio sale sin ella.
  - Antes de esa fecha: no bloquea, pero DEVUELVE el aviso (para rampa/pruebas).

Solo stdlib; determinista; `ahora` inyectable para tests con fecha simulada.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

# Fecha de entrada en vigor del regimen de transparencia (AI Act art. 50).
AIACT_FECHA_GATE = date(2026, 8, 2)

# Marcadores de identificacion proactiva como IA (art. 50). Basta uno, case-insensitive.
# Cubren las formas de las 20 variantes aprobadas + el email.
_MARCADORES = (
    "inteligencia artificial",
    "asistente virtual",
    "sistema automatizado",
    "mensaje automatizado",
    "generado con ia",
    "generado por ia",
    "no soy humano",
    "soy una ia",
    "soy una maquina",
    "soy una máquina",
    "asistente automatizado",
    "asistente automático",
    "asistente automatico",
    "asistente digital",
)

# Partículas de negación: si preceden a un marcador EN LA MISMA FRASE, el marcador
# no cuenta como disclosure ("no soy una inteligencia artificial" no es transparencia,
# es justo lo contrario).
_NEGACIONES = ("no es", "no soy", "sin ser", "jamas", "jamás", "nunca")

# Nº de palabras de la frase, inmediatamente antes del marcador, que se inspeccionan
# en busca de una negación.
_VENTANA_NEGACION = 6


class AIActSinTransparencia(RuntimeError):
    """E4: salida a tercero, en o tras el 2026-08-02, sin disclosure de IA. Fail-closed."""


def _negado_antes(t: str, idx: int) -> bool:
    """True si, en la misma frase, hay una partícula de negación antes de la posición idx."""
    inicio_frase = max(t.rfind(".", 0, idx), t.rfind("!", 0, idx),
                       t.rfind("?", 0, idx), t.rfind("\n", 0, idx))
    ventana = t[inicio_frase + 1:idx]
    palabras = ventana.split()[-_VENTANA_NEGACION:]
    ventana_acotada = " " + " ".join(palabras) + " "
    return any(f" {neg} " in ventana_acotada for neg in _NEGACIONES)


def tiene_disclosure(texto: str) -> bool:
    """True si el texto identifica proactivamente que es IA (art. 50).

    Un marcador negado en la misma frase ("no soy una IA") NO cuenta como disclosure.
    """
    if not texto:
        return False
    t = re.sub(r"\s+", " ", texto).lower()
    for m in _MARCADORES:
        idx = t.find(m)
        while idx != -1:
            if not _negado_antes(t, idx):
                return True
            idx = t.find(m, idx + 1)
    return False


def _fecha_de(ahora) -> date:
    if ahora is None:
        return datetime.now(timezone.utc).date()
    if isinstance(ahora, datetime):
        return ahora.date()
    return ahora


def candado_activo(ahora=None) -> bool:
    if os.environ.get("KAIZEN_AIACT_FORZAR", "").lower() == "true":
        return True
    return _fecha_de(ahora) >= AIACT_FECHA_GATE


# ── Variantes de email aprobadas por el operador (D11 E1.2 / cierre de F-01) ──
# Fichero de runtime hermano de aiact_primeros_mensajes.md (voz). SOLO el operador
# aprueba variantes (moviéndolas a la sección APROBADAS). La IA tiene PROHIBIDO
# editarlas. Sin variante aprobada → None → el composer falla cerrado.
NOMBRE_VARIANTES_EMAIL = "aiact_email_variantes.md"


def ruta_variantes_email(empresa: str) -> Path:
    """Fichero de variantes AI Act del tenant.

    R-TENANT: el texto de transparencia NOMBRA a la empresa emisora — es
    contenido de tenant, no de plataforma — así que vive en su ficha
    (`empresas/<tenant>/aiact_email_variantes.md`), fuera del árbol de git.
    Antes era una ruta fija del repo y por tanto una sola para todos.
    """
    from core.rutas import dir_empresa
    return dir_empresa(empresa) / NOMBRE_VARIANTES_EMAIL


def variantes_email_aprobadas(ruta: "Path | None" = None, *,
                              empresa: "str | None" = None) -> list[str]:
    """Lee la sección '## APROBADAS' del fichero de variantes. Robusto y fail-closed:
    fichero ausente, sección ausente o vacía → lista vacía.

    `ruta` explícita manda; si no, se resuelve desde `empresa`. Sin ninguna de
    las dos NO se adivina un tenant: se devuelve vacío, que el composer traduce
    en "no hay transparencia aprobada" y falla cerrado.
    """
    if ruta is None:
        if not empresa:
            return []
        ruta = ruta_variantes_email(empresa)
    ruta = Path(ruta)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError:
        return []
    aprobadas: list[str] = []
    en_seccion = False
    for linea in texto.splitlines():
        s = linea.strip()
        if s.startswith("## "):
            en_seccion = s.upper().startswith("## APROBADAS")
            continue
        if en_seccion and s.startswith("- "):
            variante = s[2:].strip()
            if variante:
                aprobadas.append(variante)
    return aprobadas


def variante_email_activa(ruta: "Path | None" = None, *,
                          empresa: "str | None" = None) -> "str | None":
    """La PRIMERA variante aprobada del tenant, o None si no hay ninguna."""
    aprobadas = variantes_email_aprobadas(ruta, empresa=empresa)
    return aprobadas[0] if aprobadas else None


def exigir_transparencia(texto: str, *, ahora=None, canal: str = "email") -> dict:
    """Candado por fecha. Lanza AIActSinTransparencia si toca y falta disclosure.

    Devuelve {ok, gate_activo, tiene_disclosure, aviso?} cuando NO lanza."""
    activo = candado_activo(ahora)
    ok = tiene_disclosure(texto)
    if activo and not ok:
        raise AIActSinTransparencia(
            f"AI Act art. 50 (desde {AIACT_FECHA_GATE.isoformat()}): el mensaje de {canal} no "
            "identifica que es IA. No sale hasta aplicar una variante de transparencia aprobada.")
    resultado = {"ok": True, "gate_activo": activo, "tiene_disclosure": ok, "canal": canal}
    if not ok:
        resultado["aviso"] = ("sin disclosure de IA: hoy no bloquea, pero desde "
                              f"{AIACT_FECHA_GATE.isoformat()} SI lo hara (E4).")
    return resultado
