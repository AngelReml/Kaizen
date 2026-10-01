"""La tanda de exploracion en SEGUNDO PLANO: la que lanza el Mundo, el director de Inteligencia o la consola.

`core/exploracion.py` sabe hacer una tanda; esto sabe LANZARLA sin bloquear a nadie, de una en una:

- una sola tanda por empresa a la vez, tambien entre procesos (reserva atomica `en_curso` en el almacen):
  la consola y el panel no pueden gastar la cuota del proveedor dos veces a la vez;
- se ejecuta en un hilo; al terminar escribe el informe y deja un resumen consultable (`estado`);
- los errores de configuracion (falta el token, API apagada...) se dan AL LANZAR, con las instrucciones,
  no a escondidas dentro del hilo;
- PARAR TODO la detiene (se mira antes de cada pregunta al modelo);
- la reserva caduca sola (horas de la tanda + 1) por si el proceso muere sin liberarla.

Quien manda la orden es siempre el operador: con su clic, con su SI a la tarjeta del director, o en la consola.
"""
from __future__ import annotations

import contextlib
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import apuestas as A
from core import exploracion as E

CLAVE_EN_CURSO = "en_curso"
CLAVE_ULTIMA = "ultima"
CICLOS_MAX = 20
HORAS_MAX = 48.0

_LOCK_PROCESO = threading.Lock()          # reserva en almacenes sin transaccion (memoria)
_HILOS: dict[str, threading.Thread] = {}  # empresa -> hilo vivo de ESTE proceso


class YaEnMarcha(RuntimeError):
    """Ya hay una tanda de esta empresa en curso (en este proceso o en otro)."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _tx(k):
    t = getattr(k, "transaccion", None)
    return t() if t else _LOCK_PROCESO


# ── dependencias reales (las mismas para el panel, el director y la consola) ─

def fabrica_real(empresa: str, k, bitacora) -> dict:
    """Cliente de modelo, busqueda web, PARAR TODO persistido, nivel de Inteligencia e informes: lo REAL.
    El cliente se crea AQUI: si falta el token, la excepcion (con instrucciones) sale al lanzar."""
    from core import rutas as R
    from core.autonomia import AutonomiaCubos
    from core.exploracion_busqueda import buscar_ddgs
    from core.exploracion_modelos import cliente_desde_entorno
    from core.panico import Panico
    ruta_panico = R.dir_state() / "panico" / "estado.json"

    def nivel_inteligencia() -> str:
        import json as _json

        from cubos.base import manifiestos_instalados
        try:
            defecto = _json.loads(manifiestos_instalados()["inteligencia"].read_text(encoding="utf-8")).get(
                "nivel_autonomia_defecto", "CERO")
        except Exception:                                    # noqa: BLE001 — sin manifest legible: lo prudente
            defecto = "CERO"
        return AutonomiaCubos(k, empresa).nivel("inteligencia", defecto)

    return {"cliente": cliente_desde_entorno(empresa), "buscar": buscar_ddgs,
            "parar": lambda: Panico(ruta_estado=ruta_panico).activo,       # se relee en cada comprobacion
            "nivel_autonomia": nivel_inteligencia, "informes": R.dir_empresa(empresa) / "exploracion"}


# ── reserva y estado ────────────────────────────────────────────────────────

def _reservar(k, empresa: str, *, ciclos: int, horas: float, ahora: datetime) -> None:
    with _tx(k):
        r = k.get(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO)
        if r and r.get("activa") and r.get("hasta", "") > ahora.isoformat():
            raise YaEnMarcha(f"ya hay una busqueda de nichos en marcha desde {r.get('desde', '?')[:16]} "
                             "(espera a que termine, o pulsa PARAR TODO)")
        k.add(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO,
              {"activa": True, "desde": ahora.isoformat(), "hasta": (ahora + timedelta(hours=horas + 1)).isoformat(),
               "ciclos": ciclos, "ciclos_hechos": 0, "pid": os.getpid()})


def _liberar(k, empresa: str) -> None:
    with _tx(k):
        r = k.get(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO) or {}
        k.add(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO, {**r, "activa": False, "fin": _ahora().isoformat()})


def estado(k, empresa: str) -> dict:
    """{en_curso: {...}|None, ultima: {...}|None}. Solo datos (numeros, estados, rutas): ningun texto de apuestas."""
    r = k.get(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO)
    vivo = bool(r and r.get("activa") and r.get("hasta", "") > _ahora().isoformat())
    return {"en_curso": ({"desde": r["desde"], "ciclos": r.get("ciclos"), "ciclos_hechos": r.get("ciclos_hechos", 0)}
                         if vivo else None),
            "ultima": k.get(empresa, E.COLECCION_ESTADO, CLAVE_ULTIMA)}


# ── correr (sincrono) y lanzar (en un hilo) ─────────────────────────────────

def _validar(ciclos, horas) -> None:
    if not isinstance(ciclos, int) or isinstance(ciclos, bool) or not (1 <= ciclos <= CICLOS_MAX):
        raise A.ApuestaInvalida(f"ciclos debe ser un entero entre 1 y {CICLOS_MAX}")
    if not (isinstance(horas, (int, float)) and not isinstance(horas, bool) and 0 < horas <= HORAS_MAX):
        raise A.ApuestaInvalida(f"horas debe ser un numero entre 0 y {HORAS_MAX:g}")


def correr(k, empresa: str, bitacora, deps: dict, *, ciclos: int = 3, horas: float = 8.0, progreso=None,
           informe_dir=None, reloj=None) -> tuple[dict, Path]:
    """Una tanda COMPLETA y sincrona (reserva, ejecucion, informe, resumen). La usan el hilo y la consola."""
    _validar(ciclos, horas)
    ahora = _ahora()
    _reservar(k, empresa, ciclos=ciclos, horas=horas, ahora=ahora)
    try:
        ap = A.Apuestas(k, empresa, bitacora=bitacora, reloj=reloj)
        ctx = E.Contexto(k=k, empresa=empresa, apuestas=ap, cliente=deps["cliente"], buscar=deps["buscar"],
                         bitacora=bitacora, reloj=reloj)

        def al_terminar(res: dict) -> None:
            r = k.get(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO) or {}
            k.add(empresa, E.COLECCION_ESTADO, CLAVE_EN_CURSO, {**r, "ciclos_hechos": r.get("ciclos_hechos", 0) + 1})
            if progreso:
                progreso(res)
        t = E.ejecutar_tanda(ctx, ciclos=ciclos, horas_max=horas, parar=deps.get("parar"),
                             sello_integro=lambda: bitacora.verificar().get("integra", False),
                             nivel_autonomia=deps.get("nivel_autonomia"), al_terminar_ciclo=al_terminar)
        carpeta = Path(informe_dir) if informe_dir else Path(deps["informes"])
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"informe_{_ahora().strftime('%Y%m%d-%H%M%S')}_{t['tanda_id']}.md"
        ruta.write_text(E.generar_informe(ctx, t), encoding="utf-8")
        k.add(empresa, E.COLECCION_ESTADO, CLAVE_ULTIMA,
              {"tanda_ref": t["tanda_id"], "fin": t["fin"], "motivo": t["motivo"], "error": t.get("error", ""),
               "dosieres": t["dosieres"], "ciclos_hechos": t["ciclos_hechos"], "rechazos": t["rechazos"],
               "rechazados_por_repeticion": t["rechazados_por_repeticion"], "informe": str(ruta)})
        return t, ruta
    finally:
        _liberar(k, empresa)


def lanzar(k, empresa: str, bitacora, *, ciclos: int = 3, horas: float = 8.0, fabrica=None, reloj=None,
           informe_dir=None) -> dict:
    """Lanza la tanda en un hilo y VUELVE ENSEGUIDA. Los errores de configuracion o una tanda ya en marcha se
    dan aqui (con instrucciones); lo que pase despues queda en `estado(...).ultima`."""
    _validar(ciclos, horas)
    if estado(k, empresa)["en_curso"] is not None:
        raise YaEnMarcha("ya hay una busqueda de nichos en marcha (espera a que termine, o pulsa PARAR TODO)")
    deps = (fabrica or fabrica_real)(empresa, k, bitacora)             # falla AQUI si falta el token, etc.
    ya = threading.Event()
    fallo: list[Exception] = []

    def hilo() -> None:
        try:
            correr(k, empresa, bitacora, deps, ciclos=ciclos, horas=horas, reloj=reloj, informe_dir=informe_dir)
        except YaEnMarcha as e:                                       # otro proceso se adelanto entre la comprobacion y la reserva
            fallo.append(e)
        except Exception as e:                                        # noqa: BLE001 — queda dicho, no se pierde
            with contextlib.suppress(Exception):
                k.add(empresa, E.COLECCION_ESTADO, CLAVE_ULTIMA,
                      {"tanda_ref": "", "fin": _ahora().isoformat(), "motivo": "error_interno",
                       "error": f"{type(e).__name__}: {str(e)[:200]}", "dosieres": 0, "ciclos_hechos": 0,
                       "rechazos": 0, "rechazados_por_repeticion": 0, "informe": ""})
        finally:
            ya.set()

    t = threading.Thread(target=hilo, name=f"tanda-{empresa}", daemon=True)
    with _LOCK_PROCESO:
        vivo = _HILOS.get(empresa)
        if vivo is not None and vivo.is_alive():
            raise YaEnMarcha("ya hay una busqueda de nichos en marcha en este proceso")
        _HILOS[empresa] = t
        t.start()
    return {"lanzada": True, "ciclos": ciclos, "horas": horas, "hilo": t, "terminada": ya, "fallo": fallo}


def esperar(empresa: str, timeout: float = 30.0) -> bool:
    """Espera a que termine el hilo de esta empresa (para pruebas). True si ya no hay hilo vivo."""
    t = _HILOS.get(empresa)
    if t is None:
        return True
    t.join(timeout)
    return not t.is_alive()
