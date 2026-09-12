"""Cadena de hash de integridad (canonico 4.4).

hash = sha256_hex(hash_prev + "|" + topic + "|" + payload + "|" + ts), UTF-8.
Genesis: 64 ceros. La MISMA funcion se reutiliza para las tres cadenas
(bus_eventos, verificaciones, decisiones_operador), cada una independiente.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable

GENESIS = "0" * 64


def calcular(hash_prev: str, topic: str, payload: str, ts: str) -> str:
    base = f"{hash_prev}|{topic}|{payload}|{ts}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


def verificar(filas: Iterable[tuple]) -> tuple[bool, int, int | None]:
    """Recorre filas (id, topic, payload, ts, hash_prev, hash) en orden.

    Devuelve (intacta, n_verificadas, primer_id_corrupto|None). Corrupto si
    el hash almacenado no reproduce el calculo o si hash_prev no enlaza con
    el hash anterior (o con GENESIS en la primera fila).
    """
    n = 0
    esperado_prev = GENESIS
    for fila in filas:
        id_, topic, payload, ts, hash_prev, hash_ = fila
        if hash_prev != esperado_prev:
            return (False, n, id_)
        if calcular(hash_prev, topic, payload, ts) != hash_:
            return (False, n, id_)
        esperado_prev = hash_
        n += 1
    return (True, n, None)
