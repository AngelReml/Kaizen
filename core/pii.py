"""PII por sujeto con crypto-shredding — R-07 de D09 (bloque B3).

Contrato: la cadena de la bitacora hashea SOLO ciphertext; suprimir a un sujeto
(art. 17 RGPD) = destruir su clave. La cadena queda integra; el dato, ilegible.

Esquema v1 (registrado como DIVERGENTE-PROVISIONAL): keystream sha256(clave||contador)
XOR — estructuralmente correcto para el contrato de shredding; sustituir por AES-GCM
cuando la dependencia `cryptography` entre en la dieta (decision v1.1). Las claves
viven en un almacen SEPARADO de los datos (destruible de forma independiente).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path


class ClaveDestruida(KeyError):
    """El sujeto fue suprimido: su PII es ilegible para siempre."""


class AlmacenClaves:
    """Claves por (tenant, sujeto). En produccion: state/pii_claves/<tenant>.json
    (fichero aparte de los datos); en tests: memoria."""

    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = Path(ruta) if ruta else None
        self._mem: dict[str, str] = {}
        if self.ruta and self.ruta.exists():
            self._mem = json.loads(self.ruta.read_text(encoding="utf-8"))

    def _persistir(self) -> None:
        if self.ruta:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            contenido = json.dumps(self._mem, ensure_ascii=False, sort_keys=True)
            self.ruta.write_text(contenido, encoding="utf-8")
            if self.ruta.read_text(encoding="utf-8") != contenido:   # E1
                raise IOError(f"E1: desfase al escribir {self.ruta}")

    def clave(self, tenant: str, sujeto: str) -> str:
        kid = f"{tenant}::{sujeto}"
        if kid not in self._mem:
            self._mem[kid] = secrets.token_hex(32)
            self._persistir()
        return self._mem[kid]

    def clave_si_existe(self, tenant: str, sujeto: str) -> str | None:
        return self._mem.get(f"{tenant}::{sujeto}")

    def destruir(self, tenant: str, sujeto: str) -> bool:
        """Crypto-shredding: borrar la clave = suprimir al sujeto."""
        kid = f"{tenant}::{sujeto}"
        if kid in self._mem:
            del self._mem[kid]
            self._persistir()
            return True
        return False


def _keystream(clave_hex: str, n: int) -> bytes:
    out = b""
    contador = 0
    while len(out) < n:
        out += hashlib.sha256(bytes.fromhex(clave_hex) + contador.to_bytes(8, "big")).digest()
        contador += 1
    return out[:n]


def cifrar(texto: str, clave_hex: str) -> str:
    datos = texto.encode("utf-8")
    ks = _keystream(clave_hex, len(datos))
    return bytes(a ^ b for a, b in zip(datos, ks)).hex()


def descifrar(cifrado_hex: str, clave_hex: str | None) -> str:
    if clave_hex is None:
        raise ClaveDestruida("clave destruida: PII suprimida (crypto-shredding)")
    datos = bytes.fromhex(cifrado_hex)
    ks = _keystream(clave_hex, len(datos))
    return bytes(a ^ b for a, b in zip(datos, ks)).decode("utf-8")


def cifrar_campos(payload: dict, campos: list[str], almacen: AlmacenClaves,
                  tenant: str, sujeto: str) -> dict:
    """Devuelve copia del payload con <campo> → <campo>_cifrado (apto para bitacora)."""
    clave = almacen.clave(tenant, sujeto)
    out = dict(payload)
    for c in campos:
        if c in out and isinstance(out[c], str):
            out[f"{c}_cifrado"] = cifrar(out.pop(c), clave)
    out["pii_sujeto_ref"] = sujeto
    return out
