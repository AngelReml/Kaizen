"""Pre-flight checks antes de colocar una llamada outbound (Fase 1 voz).

Verifica las 3 barreras arquitectónicas + LSSI/RGPD + estado del lead + credenciales.
Si CUALQUIER check falla, la llamada NO se coloca. Esto es defensa en profundidad: el
guard ya existe en `cola_aprobacion.verificar_token`, pero pre_flight bloquea ANTES de
generar el TwiML y llamar a la API de Twilio (ahorra tiempo, dinero y posible
incumplimiento).
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.bloqueo import bloqueo_exclusivo, escribir_atomico

TZ_ES = ZoneInfo("Europe/Madrid")

# Franja horaria comercial razonable para HORECA en España (L-V).
# Configurable a futuro vía .env si hace falta.
FRANJAS_PERMITIDAS: list[tuple[int, int]] = [(10, 13), (16, 19)]
DIAS_PERMITIDOS = {0, 1, 2, 3, 4}    # Mon-Fri (0=Mon, 6=Sun)


@dataclass
class ResultadoPreFlight:
    ok: bool
    fallos: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    contexto: dict = field(default_factory=dict)


def normalizar_telefono_es(tel: str | None) -> str | None:
    """Convierte un teléfono español a formato E.164 (+34...). None si no se puede."""
    if not tel:
        return None
    # Quitar espacios, guiones, paréntesis.
    limpio = re.sub(r"[\s\-().]", "", tel)
    if limpio.startswith("+34") and len(limpio) == 12 and limpio[3:].isdigit():
        return limpio
    if limpio.startswith("34") and len(limpio) == 11 and limpio.isdigit():
        return f"+{limpio}"
    if limpio.isdigit() and len(limpio) == 9 and limpio[0] in "6789":
        return f"+34{limpio}"
    return None


def numero_origen_conforme(from_number: str | None) -> tuple[bool, str]:
    """Orden TDF/149/2025: prohibida la numeración móvil como origen de llamadas
    comerciales en España. El origen debe ser fijo geográfico (+34 8xx/9xx) o
    numeración 800/900. Un número extranjero (p. ej. +1) tampoco es conforme y
    además los operadores lo etiquetan como spam."""
    if not from_number:
        return False, "TWILIO_FROM_NUMBER vacío"
    limpio = re.sub(r"[\s\-().]", "", from_number)
    if re.fullmatch(r"\+34[89]\d{8}", limpio):
        return True, ""
    if re.fullmatch(r"\+34[67]\d{8}", limpio):
        return False, (f"'{from_number}' es numeración móvil española: prohibida como "
                       f"origen de llamadas comerciales (Orden TDF/149/2025). Usa un "
                       f"fijo geográfico, 800 o 900.")
    return False, (f"'{from_number}' no es numeración fija española (+34 8xx/9xx), "
                   f"requerida para llamadas comerciales en España.")


# ── Quota diaria de llamadas (control de coste + anti-bucle) ─────────────────
def _quota_dir_default():
    from core.rutas import dir_state
    return dir_state() / "voz" / "quota"
_quota_lock = threading.Lock()


def _quota_dir() -> Path:
    return Path(os.environ.get("KAIZEN_VOZ_QUOTA_DIR", str(_quota_dir_default())))


def max_llamadas_dia() -> int:
    """Límite duro de llamadas salientes por día. KAIZEN_VOZ_MAX_LLAMADAS_DIA (def. 25)."""
    try:
        return int(os.environ.get("KAIZEN_VOZ_MAX_LLAMADAS_DIA", "25"))
    except ValueError:
        return 25


def _quota_path(ahora: datetime | None = None) -> Path:
    dia = (ahora or datetime.now(TZ_ES)).astimezone(TZ_ES).strftime("%Y%m%d")
    return _quota_dir() / f"quota_{dia}.json"


class QuotaCorrupta(RuntimeError):
    """El contador del día no es legible. Fail-closed: no se coloca la llamada."""


class QuotaAgotada(RuntimeError):
    """La reserva no cabe en la quota diaria."""


def _leer_contador(p: Path) -> int:
    """Lectura estricta. Un contador corrupto NO se puede tratar como un número:
    antes devolvía `max_llamadas_dia()` (fail-closed al leer), pero entonces
    `registrar_llamada_colocada` escribía max+1 y el contador quedaba
    permanentemente por encima del techo (auditoría 2026-08-02, C-12)."""
    if not p.exists():
        return 0
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get("n", 0))
    except Exception as e:  # noqa: BLE001
        raise QuotaCorrupta(f"contador de quota ilegible en {p}: {e}") from e


def llamadas_hoy(ahora: datetime | None = None) -> int:
    """Lectura tolerante para informes/pre-flight: un contador corrupto cuenta
    como agotado (fail-closed), pero nunca se escribe a partir de ese valor."""
    try:
        return _leer_contador(_quota_path(ahora))
    except QuotaCorrupta:
        return max_llamadas_dia()


def reservar_llamada(ahora: datetime | None = None) -> int:
    """Aparta un hueco de la quota ANTES de colocar la llamada. Devuelve el
    número reservado (1-based) o lanza `QuotaAgotada` / `QuotaCorrupta`.

    Comprobar y consumir van dentro del mismo candado ENTRE PROCESOS: antes se
    comprobaba en `verificar()`, se colocaba la llamada y se incrementaba
    después, con un `threading.Lock` que no protege entre procesos — dos
    llamadas concurrentes pasaban las dos (C-12).

    Si la llamada no llega a colocarse, `liberar_llamada()` devuelve el hueco.
    """
    p = _quota_path(ahora)
    with _quota_lock, bloqueo_exclusivo(p):
        n = _leer_contador(p)
        maximo = max_llamadas_dia()
        if n >= maximo:
            raise QuotaAgotada(f"quota diaria de llamadas alcanzada ({n}/{maximo})")
        escribir_atomico(p, json.dumps({"n": n + 1}))
        return n + 1


def liberar_llamada(ahora: datetime | None = None) -> int:
    """Devuelve un hueco reservado (la llamada no llegó a colocarse)."""
    p = _quota_path(ahora)
    with _quota_lock, bloqueo_exclusivo(p):
        n = _leer_contador(p)
        nuevo = max(0, n - 1)
        escribir_atomico(p, json.dumps({"n": nuevo}))
        return nuevo


def registrar_llamada_colocada(ahora: datetime | None = None) -> int:
    """Incrementa el contador del día sin comprobar el techo.

    Se mantiene para los caminos que ya reservaron por otra vía; el camino nuevo
    debe usar `reservar_llamada()` ANTES de colocar la llamada.
    """
    p = _quota_path(ahora)
    with _quota_lock, bloqueo_exclusivo(p):
        n = _leer_contador(p) + 1
        escribir_atomico(p, json.dumps({"n": n}))
        return n


def en_franja_comercial(ahora: datetime | None = None) -> tuple[bool, str]:
    """Devuelve (ok, razon). True si estamos en franja comercial española."""
    ahora = ahora or datetime.now(TZ_ES)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=TZ_ES)
    if ahora.weekday() not in DIAS_PERMITIDOS:
        return False, f"{ahora.strftime('%A')} no está en L-V (solo días laborables)"
    h = ahora.hour
    if any(ini <= h < fin for ini, fin in FRANJAS_PERMITIDAS):
        return True, ""
    return False, (f"hora {ahora.strftime('%H:%M')} fuera de franja "
                   f"({', '.join(f'{a}-{b}h' for a, b in FRANJAS_PERMITIDAS)})")


def _flag(nombre: str, valor_esperado: str = "true") -> bool:
    return os.environ.get(nombre, "false").lower() == valor_esperado


VARS_ENTORNO_REQUERIDAS = (
    "ELEVENLABS_AGENT_ID",
    "ELEVENLABS_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_API_KEY_SID",
    "TWILIO_API_KEY_SECRET",
    "TWILIO_FROM_NUMBER",
    "PUBLIC_MEDIA_BASE_URL",
)


def verificar(*, lead: dict, pendiente: dict, ahora: datetime | None = None,
              ignorar_franja: bool = False) -> ResultadoPreFlight:
    """Aplica todos los chequeos. `ignorar_franja=True` solo para tests manuales
    a tu propio número fuera de horario (V1 con tu teléfono)."""
    res = ResultadoPreFlight(ok=True)

    # ── Flags globales (las 2 primeras barreras del sandbox) ───────────────
    if not _flag("KAIZEN_ENVIO_HABILITADO"):
        res.fallos.append("KAIZEN_ENVIO_HABILITADO != true (sandbox global activo)")
    if not _flag("SDR_VOICE_ENABLED"):
        res.fallos.append("SDR_VOICE_ENABLED != true (zona ámbar consciente v0.2 §4.3)")

    # ── Aprobación del pendiente (3ª barrera) ──────────────────────────────
    estado_p = pendiente.get("estado")
    if estado_p != "aprobado":
        res.fallos.append(f"pendiente en estado '{estado_p}', no 'aprobado'")
    if not pendiente.get("token_aprobacion"):
        res.fallos.append("pendiente sin token_aprobacion")

    # ── Lead: teléfono válido + opt-out ────────────────────────────────────
    contacto = lead.get("contacto") or {}
    tel = contacto.get("telefono")
    tel_norm = normalizar_telefono_es(tel)
    if not tel:
        res.fallos.append("lead sin contacto.telefono")
    elif not tel_norm:
        res.fallos.append(f"lead.contacto.telefono '{tel}' no es un móvil español válido")
    else:
        res.contexto["telefono_e164"] = tel_norm
        if tel != tel_norm:
            res.advertencias.append(f"teléfono normalizado: '{tel}' → '{tel_norm}'")

    if lead.get("do_not_call"):
        res.fallos.append("lead.do_not_call=True (opt-out previo registrado)")

    # ── Robinson fail-closed (R-04, auditoria 2026-07-20) ──────────────────
    # Antes: el camino operativo nunca comprobaba la lista Robinson (el gate que
    # si lo hacia era codigo muerto). Ahora robinson_ok debe ser explicitamente
    # True; ausente/None/False = NO se llama. La duda cierra (GR-04).
    robinson = lead.get("robinson_ok")
    if robinson is None:
        robinson = (lead.get("contacto") or {}).get("robinson_ok")
    if robinson is not True:
        res.fallos.append(
            "robinson_ok no verificado (fail-closed R-04): sin confirmacion explicita de que "
            "el numero NO esta en la Lista Robinson, la llamada no sale")

    # ── Franja horaria comercial española ──────────────────────────────────
    if ignorar_franja:
        res.advertencias.append("franja horaria IGNORADA (solo para tests manuales)")
    else:
        ok_franja, motivo = en_franja_comercial(ahora)
        if not ok_franja:
            res.fallos.append(f"fuera de franja comercial: {motivo}")

    # ── Variables de entorno ───────────────────────────────────────────────
    faltan = [v for v in VARS_ENTORNO_REQUERIDAS if not os.environ.get(v)]
    if faltan:
        res.fallos.append(f".env: faltan {', '.join(faltan)}")

    # ── Número de origen conforme (Orden TDF/149/2025) ─────────────────────
    if os.environ.get("TWILIO_FROM_NUMBER"):
        ok_from, motivo_from = numero_origen_conforme(os.environ.get("TWILIO_FROM_NUMBER"))
        if not ok_from:
            if _flag("KAIZEN_VOZ_PERMITIR_ORIGEN_NO_CONFORME"):
                res.advertencias.append(
                    f"número de origen NO conforme (permitido por flag explícito): {motivo_from}")
            else:
                res.fallos.append(f"número de origen no conforme: {motivo_from}")

    # ── Quota diaria de llamadas (coste + anti-bucle) ──────────────────────
    n_hoy = llamadas_hoy(ahora)
    if n_hoy >= max_llamadas_dia():
        res.fallos.append(
            f"quota diaria de llamadas alcanzada ({n_hoy}/{max_llamadas_dia()}); "
            f"sube KAIZEN_VOZ_MAX_LLAMADAS_DIA solo si es deliberado")
    else:
        res.contexto["llamadas_hoy"] = n_hoy

    res.ok = not res.fallos
    return res
