"""Bloqueo exclusivo ENTRE PROCESOS para contadores en fichero.

Por que existe (auditoria 2026-08-02, hallazgos B-03 / C-12 / G-10): el repo
tenia tres contadores con el mismo fallo — comprobar un limite y consumirlo
despues, protegidos solo por un `threading.Lock`. Un lock de hilo no sirve
cuando el CLI y `api/server.py` son procesos distintos escribiendo el MISMO
fichero: los dos leen el mismo valor, los dos deciden que caben y los dos
gastan. El techo se rebasa y ademas se pierde gasto por last-writer-wins.

Este modulo da el candado que faltaba. En SQLite el equivalente ya existe y es
`BEGIN IMMEDIATE` (ver `sustrato.bus.transaccion`).

Solo stdlib. Usa el bloqueo de fichero del sistema operativo:
  - Windows: msvcrt.locking (bloqueo obligatorio sobre el fichero .lock)
  - POSIX:   fcntl.flock
Ambos los libera el SO si el proceso muere, asi que un crash no deja el
candado echado para siempre.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

try:                                    # POSIX
    import fcntl
    _WINDOWS = False
except ImportError:                     # Windows
    import msvcrt
    _WINDOWS = True


class BloqueoNoDisponible(TimeoutError):
    """No se pudo tomar el candado en el tiempo dado: preferimos fallar a gastar."""


def _tomar(fh) -> bool:
    """Intento NO bloqueante. True si se obtuvo el candado."""
    try:
        if _WINDOWS:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _soltar(fh) -> None:
    try:
        if _WINDOWS:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def bloqueo_exclusivo(ruta: str | Path, *, timeout_s: float = 10.0,
                      espera_s: float = 0.02):
    """Candado exclusivo entre procesos asociado a `ruta` (usa `<ruta>.lock`).

    Envuelve el ciclo COMPLETO leer-decidir-escribir, no solo la escritura: si
    solo se protege el write, la decision ya se tomo con datos obsoletos.

    Lanza `BloqueoNoDisponible` si no lo consigue en `timeout_s`. Fallar es lo
    correcto aqui: es un candado de gasto, y ante la duda no se gasta.
    """
    candado = Path(str(ruta) + ".lock")
    candado.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + timeout_s
    fh = open(candado, "a+b")
    try:
        fh.seek(0)
        while not _tomar(fh):
            if time.monotonic() >= limite:
                raise BloqueoNoDisponible(
                    f"no se pudo bloquear {candado} en {timeout_s:.1f}s; "
                    f"otro proceso lo tiene tomado")
            time.sleep(espera_s)
            fh.seek(0)
        try:
            yield
        finally:
            _soltar(fh)
    finally:
        fh.close()


def escribir_atomico(ruta: str | Path, contenido: str) -> None:
    """tmp + os.replace, con el directorio ya creado. El rename es atomico en el
    mismo volumen: un corte a media escritura no deja el fichero a medias."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    tmp.write_text(contenido, encoding="utf-8")
    os.replace(tmp, destino)
