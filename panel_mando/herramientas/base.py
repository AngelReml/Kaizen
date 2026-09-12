# -*- coding: utf-8 -*-
"""Contrato de herramienta de director (Fase 4 — plenipotenciarios por cubo).

Un director es plenipotenciario DENTRO de su cubo: puede leer estado real
(LECTURA) y escribir internamente lo que su autonomia BAJA permite
(REVERSIBLE) sin pedir permiso — es exactamente lo que "BAJA" significa en
D00 §4.2. Las IRREVERSIBLE-* siguen exigiendo SIEMPRE tarjeta y aprobacion
humana: una herramienta de esa clase JAMAS se ejecuta desde aqui; el director
la ofrece via el protocolo [PROPUESTA] ya existente, y solo al aprobarla el
ejecutor del panel (panel_mando/app.py::_barreras_y_veredicto) la dispara de
verdad — cerrando el hueco de honestidad de la Fase 1 (P0: "EJECUTADA" sin
que nada se ejecutara).

Frontera de seguridad (LEER ANTES DE TOCAR): el nombre de cubo que decide que
REGISTRO[cubo] se consulta viene SIEMPRE del agente autenticado que esta
hablando (colmena_agentes.cubo), NUNCA de un campo que el texto del LLM
pueda rellenar. Un director de Marketing no puede invocar una herramienta de
Finanzas ni aunque el texto del modelo la nombre: `invocar()` solo busca
dentro de `REGISTRO[cubo_del_agente]`; si el nombre no esta ahi, es un
NoExisteHerramienta, nunca un fallback a otro cubo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

CLASES_HERRAMIENTA = ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA", "IRREVERSIBLE-EXTERNA")


class NoExisteHerramienta(KeyError):
    """El nombre no esta registrado para ESE cubo (pueda o no existir en otro)."""


class ArgumentosInvalidos(ValueError):
    pass


@dataclass(frozen=True)
class Argumento:
    nombre: str
    tipo: str                 # "str" | "int" | "float" | "bool"
    descripcion: str
    obligatorio: bool = True


@dataclass(frozen=True)
class ToolSpec:
    """Una herramienta real de un cubo. `fn` recibe SIEMPRE (k, tenant,
    bitacora, **argumentos_validados) y devuelve un dict JSON-serializable
    con el resultado — nunca None, nunca una excepcion silenciada: si algo
    falla, `fn` debe dejar que la excepcion suba (la capa de invocacion la
    reporta al operador, no la esconde)."""
    nombre: str
    clase: str                 # uno de CLASES_HERRAMIENTA
    descripcion: str
    argumentos: tuple[Argumento, ...]
    fn: Callable[..., dict]

    def __post_init__(self) -> None:
        if self.clase not in CLASES_HERRAMIENTA:
            raise ValueError(f"clase de herramienta invalida: {self.clase!r}")

    def firma_para_prompt(self) -> str:
        args = ", ".join(
            f'{a.nombre}{"" if a.obligatorio else "?"}: {a.tipo} — {a.descripcion}'
            for a in self.argumentos) or "(sin argumentos)"
        return f"- {self.nombre} [{self.clase}]: {self.descripcion}\n    argumentos: {args}"

    def validar(self, argumentos: dict) -> dict:
        """Solo pasan los argumentos declarados, con el tipo declarado. Un
        campo desconocido o de tipo incorrecto es ArgumentosInvalidos, nunca
        una coercion silenciosa (honestidad: el operador ve el motivo exacto)."""
        limpios: dict[str, Any] = {}
        declarados = {a.nombre: a for a in self.argumentos}
        desconocidos = set(argumentos) - set(declarados)
        if desconocidos:
            raise ArgumentosInvalidos(f"argumentos no declarados: {sorted(desconocidos)}")
        for a in self.argumentos:
            if a.nombre not in argumentos:
                if a.obligatorio:
                    raise ArgumentosInvalidos(f"falta argumento obligatorio: {a.nombre!r}")
                continue
            v = argumentos[a.nombre]
            try:
                if a.tipo == "str":
                    limpios[a.nombre] = str(v)
                elif a.tipo == "int":
                    limpios[a.nombre] = int(v)
                elif a.tipo == "float":
                    limpios[a.nombre] = float(v)
                elif a.tipo == "bool":
                    if isinstance(v, bool):
                        limpios[a.nombre] = v
                    elif isinstance(v, str) and v.strip().lower() in ("true", "false"):
                        limpios[a.nombre] = v.strip().lower() == "true"
                    else:
                        raise ValueError(
                            f"se esperaba bool o texto 'true'/'false', llego {v!r}")
                else:
                    limpios[a.nombre] = v
            except (TypeError, ValueError) as exc:
                raise ArgumentosInvalidos(
                    f"argumento {a.nombre!r} debe ser {a.tipo}: {exc}") from exc
        return limpios


def invocar(registro: dict[str, dict[str, ToolSpec]], cubo: str, nombre: str,
           argumentos: dict, *, k, tenant: str, bitacora=None) -> dict:
    """Punto UNICO de disparo real. `cubo` viene del agente autenticado, no
    del texto del modelo (ver docstring del modulo). LECTURA/REVERSIBLE se
    llaman desde aqui igual; IRREVERSIBLE-* se rechazan aqui a proposito —
    esas SOLO se disparan desde el ejecutor de aprobaciones del panel, nunca
    desde un turno de chat directo (ver `invocar_aprobada` mas abajo)."""
    spec = (registro.get(cubo) or {}).get(nombre)
    if spec is None:
        raise NoExisteHerramienta(
            f"el cubo {cubo!r} no tiene una herramienta llamada {nombre!r}")
    if spec.clase in ("IRREVERSIBLE-INTERNA", "IRREVERSIBLE-EXTERNA"):
        raise ArgumentosInvalidos(
            f"{nombre!r} es {spec.clase}: se propone con [PROPUESTA], no se invoca directo")
    limpios = spec.validar(argumentos)
    return spec.fn(k=k, tenant=tenant, bitacora=bitacora, **limpios)


def invocar_aprobada(registro: dict[str, dict[str, ToolSpec]], cubo: str, nombre: str,
                     argumentos: dict, *, k, tenant: str, bitacora=None) -> dict:
    """Disparo real de una IRREVERSIBLE-INTERNA YA APROBADA por el operador
    (llamada SOLO desde el ejecutor de aprobaciones, nunca desde un turno de
    chat). IRREVERSIBLE-EXTERNA se rechaza tambien aqui a proposito: el chat
    no dispara nada al mundo real todavia — esa es una frontera deliberada
    (R2), no un olvido; ver INFORME de la sesion."""
    spec = (registro.get(cubo) or {}).get(nombre)
    if spec is None:
        raise NoExisteHerramienta(
            f"el cubo {cubo!r} no tiene una herramienta llamada {nombre!r}")
    if spec.clase != "IRREVERSIBLE-INTERNA":
        raise ArgumentosInvalidos(
            f"{nombre!r} es {spec.clase}: invocar_aprobada() solo dispara IRREVERSIBLE-INTERNA")
    limpios = spec.validar(argumentos)
    return spec.fn(k=k, tenant=tenant, bitacora=bitacora, **limpios)


def herramientas_para_prompt(registro: dict[str, dict[str, ToolSpec]], cubo: str, *,
                             clases: tuple[str, ...]) -> str:
    specs = [s for s in (registro.get(cubo) or {}).values() if s.clase in clases]
    if not specs:
        return "(ninguna herramienta de este tipo en tu cubo)"
    return "\n".join(s.firma_para_prompt() for s in sorted(specs, key=lambda s: s.nombre))
