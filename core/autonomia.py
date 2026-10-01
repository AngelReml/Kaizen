"""Nivel de autonomia EFECTIVO por empresa y cubo — docs/AUTONOMIA_v0.md (F3 del plan).

Hasta ahora la Colmena leia solo el valor por defecto del manifest: un nivel estatico, igual
para todas las empresas, y `cambiar_nivel()` no estaba conectada a nada. Este modulo guarda,
por (empresa, cubo), un nivel que REEMPLAZA al defecto cuando existe:

- endurecer (bajar un nivel) es programatico: lo hacen los gatillos del barrido (F4);
- subir lo hace SOLO el operador (F5) y nunca hasta un nivel bloqueado (ALTA, esta temporada);
- cada cambio se sella en la bitacora (`plataforma.autonomia.cambiada`, con cubo y causa);
- un mismo incidente baja el nivel UNA sola vez (guarda de incidentes ya aplicados);
- nunca se baja de CERO.

El override reemplaza (no limita con min) porque el manifest declara un DEFECTO, no un techo:
el operador debe poder subir por encima de el (hasta MEDIA).

No toca `sustrato/gates` (camino legado de Comercial, solo operador, con su propia cadena).
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone

from core.aprobaciones import NIVELES, NIVELES_BLOQUEADOS, cambiar_nivel

COLECCION = "autonomia_cubo"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomiaCubos:
    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.bitacora = bitacora

    # ── lectura ──
    def registro(self, cubo: str) -> dict | None:
        return self.k.get(self.tenant, COLECCION, cubo)

    def nivel(self, cubo: str, defecto: str) -> str:
        """Nivel vigente: el guardado si existe y es valido; si no, el defecto del manifest."""
        r = self.registro(cubo)
        if r and r.get("nivel") in NIVELES:
            return r["nivel"]
        return defecto if defecto in NIVELES else "CERO"

    def ultimo_cambio(self, cubo: str) -> str | None:
        """Instante del ultimo cambio de nivel del cubo (ISO) o None si nunca cambio."""
        r = self.registro(cubo)
        return r["historial"][-1]["ts"] if r and r.get("historial") else None

    # ── escritura (atomica entre procesos: mismo patron que Bitacora._encadenar) ──
    def _tx(self):
        tx = getattr(self.k, "transaccion", None)
        return tx() if tx else contextlib.nullcontext()

    def endurecer(self, cubo: str, defecto: str, *, causa: str, incidente: str) -> dict:
        """Baja UN nivel por un incidente. Idempotente por `incidente`; nunca baja de CERO."""
        with self._tx():
            r = self.registro(cubo) or {"cubo": cubo, "nivel": None, "historial": [],
                                        "incidentes": []}
            actual = self.nivel(cubo, defecto)
            if incidente in r["incidentes"]:
                return {"cubo": cubo, "de": actual, "a": actual, "aplicado": False,
                        "razon": "incidente_ya_aplicado"}
            r["incidentes"].append(incidente)
            if NIVELES.index(actual) == 0:
                r["nivel"] = actual
                self.k.add(self.tenant, COLECCION, cubo, r)
                return {"cubo": cubo, "de": actual, "a": actual, "aplicado": False,
                        "razon": "ya_en_CERO"}
            pedido = NIVELES[NIVELES.index(actual) - 1]
            nuevo = cambiar_nivel(actual, pedido, actor="sistema", bitacora=self.bitacora,
                                  tenant=self.tenant, cubo=cubo, causa=causa)
            r["nivel"] = nuevo
            r["historial"].append({"ts": _ahora(), "de": actual, "a": nuevo,
                                   "actor": "sistema", "causa": causa, "incidente": incidente})
            self.k.add(self.tenant, COLECCION, cubo, r)
            return {"cubo": cubo, "de": actual, "a": nuevo, "aplicado": True, "razon": causa}

    def fijar(self, cubo: str, defecto: str, nivel: str, *, por: str, motivo: str = "") -> dict:
        """Fija el nivel por decision del OPERADOR (subir o bajar). ALTA bloqueada."""
        if nivel not in NIVELES:
            raise ValueError(f"nivel desconocido: {nivel!r}")
        if nivel in NIVELES_BLOQUEADOS:
            if self.bitacora is not None:                     # el intento tambien se sella
                cambiar_nivel(self.nivel(cubo, defecto), nivel, actor="operador",
                              bitacora=self.bitacora, tenant=self.tenant, cubo=cubo,
                              causa="intento_de_fijar_nivel_bloqueado")
            raise ValueError(f"el nivel {nivel} esta bloqueado esta temporada (docs/AUTONOMIA_v0.md)")
        with self._tx():
            r = self.registro(cubo) or {"cubo": cubo, "nivel": None, "historial": [],
                                        "incidentes": []}
            actual = self.nivel(cubo, defecto)
            if nivel == actual:
                return {"cubo": cubo, "de": actual, "a": actual, "aplicado": False,
                        "razon": "sin_cambio"}
            nuevo = cambiar_nivel(actual, nivel, actor="operador", bitacora=self.bitacora,
                                  tenant=self.tenant, cubo=cubo,
                                  causa=motivo or "decision_del_operador")
            r["nivel"] = nuevo
            r["historial"].append({"ts": _ahora(), "de": actual, "a": nuevo, "actor": "operador",
                                   "por": por, "causa": motivo or "decision_del_operador"})
            self.k.add(self.tenant, COLECCION, cubo, r)
            return {"cubo": cubo, "de": actual, "a": nuevo, "aplicado": True,
                    "razon": motivo or "decision_del_operador"}


def manifest_efectivo(knowledge, tenant: str, cubo: str, manifest: dict) -> dict:
    """Copia del manifest con `nivel_autonomia_defecto` sustituido por el nivel vigente de la
    empresa. Asi el codigo que ya lee esa clave (Colmena, Mundo) no cambia de forma."""
    defecto = (manifest or {}).get("nivel_autonomia_defecto", "CERO")
    vigente = AutonomiaCubos(knowledge, tenant).nivel(cubo, defecto)
    if vigente == defecto:
        return manifest
    return {**manifest, "nivel_autonomia_defecto": vigente, "nivel_autonomia_manifest": defecto}
