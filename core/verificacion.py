"""Verificacion como servicio del sustrato — D00 §5 (bloque B6) + R-02/R-03 de D09.

`validar_borrador` es LA interfaz publica unica (R-03): el cubo Brand no expone
endpoint propio; se registra como PROVEEDOR del paquete 'brand'. Sin proveedor
registrado, opera el paquete embebido por defecto (P1: arranque sin dependencias).

Reproducibilidad R-02: propiedad del SISTEMA, no del modelo — el veredicto se
persiste en cache con clave (hash_contenido, version_directrices, version_prompts,
modelo_pin, paquetes). Primera evaluacion: motor real (inyectable; sin LLM por
defecto). Siguientes: cache. Cambio de version = re-evaluacion consciente.

Presets D00 §5.2: COMITE_LIGERO (bloqueante, unanimidad), COMITE_ESTANDAR (0.66),
COMITE_FORENSE (0.70, no bloquea). En modo preventivo, bajo umbral = DENEGAR.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from core.rue import Sobre

PRESETS = {
    "COMITE_LIGERO":  {"voces": 3, "umbral": 1.00, "bloqueante": True},
    "COMITE_ESTANDAR": {"voces": 3, "umbral": 0.66, "bloqueante": False},
    "COMITE_FORENSE": {"voces": 3, "umbral": 0.70, "bloqueante": False},
}

_PROVEEDORES: dict[str, object] = {}


def registrar_paquete(nombre: str, proveedor) -> None:
    """proveedor(tenant_id, tipo_contenido, contenido) -> {"veredicto","razones","version"}"""
    _PROVEEDORES[nombre] = proveedor


def quitar_paquete(nombre: str) -> None:
    _PROVEEDORES.pop(nombre, None)


# ── Paquete embebido por defecto (P1) ────────────────────────────────────────

_PROHIBIDAS_EMBEBIDAS = ("lorem", "ipsum", "xxx", "todo:", "[insertar")
_RE_PLACEHOLDER = re.compile(r"\[[A-Z_]{2,}\]|\b(TODO|FIXME|INSERTAR)\b")


def _paquete_embebido(tenant_id: str, tipo_contenido: str, contenido: str) -> dict:
    razones = []
    low = contenido.lower()
    if not contenido.strip():
        razones.append("contenido vacio")
    for p in _PROHIBIDAS_EMBEBIDAS:
        if p in low:
            razones.append(f"marca de placeholder/prohibida: {p!r}")
    if _RE_PLACEHOLDER.search(contenido):
        razones.append("placeholder sin resolver")
    return {"veredicto": "NO_APTO" if razones else "APTO",
            "razones": razones, "version": "embebido-v1"}


# ── Servicio ─────────────────────────────────────────────────────────────────

@dataclass
class Veredicto:
    veredicto: str
    razones: list
    politicas_evaluadas: list
    version_prompts: str
    hash: str
    cache_hit: bool = False

    def as_dict(self) -> dict:
        return {"veredicto": self.veredicto, "razones": self.razones,
                "politicas_evaluadas": self.politicas_evaluadas,
                "version_prompts": self.version_prompts, "hash": self.hash}


class ServicioVerificacion:
    def __init__(self, knowledge, *, bitacoras: dict | None = None,
                 modelo_pin: str = "sin-llm-v1", version_prompts: str = "v1") -> None:
        self.k = knowledge
        self.bitacoras = bitacoras or {}
        self.modelo_pin = modelo_pin
        self.version_prompts = version_prompts
        self.misses = 0                            # instrumentacion para tests R-02

    def _clave_cache(self, tenant: str, contenido: str, paquetes: tuple, versiones: str) -> str:
        cuerpo = json.dumps([hashlib.sha256(contenido.encode()).hexdigest(),
                             sorted(paquetes), versiones, self.version_prompts,
                             self.modelo_pin], sort_keys=True)
        return hashlib.sha256(cuerpo.encode()).hexdigest()

    def validar_borrador(self, tenant_id: str, tipo_contenido: str, contenido: str,
                         paquetes_politicas: tuple = ("brand",), *,
                         preset: str = "COMITE_LIGERO", modo: str = "PREVENTIVO") -> Veredicto:
        cfg = PRESETS[preset]
        resultados = []
        versiones = []
        for p in paquetes_politicas:
            prov = _PROVEEDORES.get(p, _paquete_embebido)
            r = prov(tenant_id, tipo_contenido, contenido)
            resultados.append((p, r))
            versiones.append(f"{p}:{r.get('version','?')}")
        version_str = "|".join(versiones)
        clave = self._clave_cache(tenant_id, contenido, tuple(paquetes_politicas), version_str)
        cacheado = self.k.get(tenant_id, "verificacion_cache", clave)
        if cacheado is not None:
            return Veredicto(**{**cacheado, "cache_hit": True})
        self.misses += 1
        # comite: cada paquete vota; con paquete unico, votingRuns deterministas = unanime
        aptos = sum(1 for _, r in resultados if r["veredicto"] == "APTO")
        acuerdo = aptos / len(resultados)
        if acuerdo >= cfg["umbral"]:
            v = "APTO"
        elif modo == "PREVENTIVO" and cfg["bloqueante"]:
            v = "NO_APTO"                          # bajo umbral en preventivo = denegar
        else:
            v = "AMBIGUO" if 0 < acuerdo < 1 else "NO_APTO"
        razones = [f"[{p}] {x}" for p, r in resultados for x in r["razones"]]
        h = hashlib.sha256((clave + v + json.dumps(razones, sort_keys=True)).encode()).hexdigest()
        veredicto = Veredicto(veredicto=v, razones=razones,
                              politicas_evaluadas=list(paquetes_politicas),
                              version_prompts=self.version_prompts, hash=h)
        self.k.add(tenant_id, "verificacion_cache", clave, veredicto.as_dict())
        b = self.bitacoras.get(tenant_id)
        if b is not None:
            b.publicar(Sobre(tenant_id=tenant_id, tipo="plataforma.verificacion.emitida",
                             payload={"veredicto": v, "hash": h, "modo": modo,
                                      "preset": preset, "contenido_ref": clave[:16]},
                             origen="plataforma.verificacion"))
        return veredicto
