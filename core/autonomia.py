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
import time
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


# ── gatillos de endurecimiento (G1) ─────────────────────────────────────────

RACHA_DENEGADAS = 3
# Verificar la cadena entera cuesta ~32 microsegundos por evento (medido: 3000 eventos ≈ 96 ms)
# y el pulso corre por cada cliente conectado: sin freno, N pestañas verificarian N veces por ciclo.
VIGILAR_CADA_S = 30.0
# Decisiones POSITIVAS del operador sobre una tarjeta. CADUCADA (nadie decidio) y REVOCADA (decision
# ambigua sobre algo ya aprobado) no cuentan: ni cortan ni alargan una racha de denegaciones.
_POSITIVAS = frozenset({"APROBADA", "EJECUTANDO", "EJECUTADA", "ENSAYO_SECO", "ANULADA"})


def _dt(iso: str) -> datetime:
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def incidente_de_racha(tarjetas: list[dict], cubo: str, desde: str | None) -> str | None:
    """Identificador del incidente "N denegadas seguidas" del cubo, o None.

    Cuenta solo decisiones POSTERIORES al ultimo cambio de nivel del cubo (`desde`): lo anterior
    ya se pago con aquella bajada. El id es el de la 3.ª denegacion de la racha final, estable aunque
    la racha siga creciendo.
    """
    limite = _dt(desde) if desde else None
    decididas = []
    for n in tarjetas:
        if n.get("cubo") != cubo or not n.get("decidida_en"):
            continue
        if n["estado"] != "DENEGADA" and n["estado"] not in _POSITIVAS:
            continue
        if limite is not None and _dt(n["decidida_en"]) <= limite:
            continue
        decididas.append(n)
    decididas.sort(key=lambda n: (_dt(n["decidida_en"]), n["id"]))
    racha = []
    for n in reversed(decididas):
        if n["estado"] != "DENEGADA":
            break
        racha.append(n)
    racha.reverse()
    return f"racha:{racha[RACHA_DENEGADAS - 1]['id']}" if len(racha) >= RACHA_DENEGADAS else None


def vigilar(knowledge, tenant: str, *, cola, bitacora, defectos,
            ultima: dict | None = None, cada_s: float = VIGILAR_CADA_S) -> list[dict]:
    """Aplica los gatillos de G1 y devuelve SOLO los cambios realmente aplicados.

    1. `RACHA_DENEGADAS` tarjetas seguidas denegadas de un mismo cubo -> baja ese cubo un nivel.
    2. Sello de la bitacora roto -> bajan todos los cubos de la empresa un nivel.
    El tope de gasto NO es gatillo aqui: ya lo gestiona core/techos.py.
    `defectos` = {cubo: nivel por defecto del manifest} o una funcion que lo devuelve (se llama
    solo si pasa el freno). `ultima` (dict del llamante) lleva el freno por empresa.
    """
    if ultima is not None and cada_s > 0:
        ahora = time.monotonic()
        if ahora - ultima.get(tenant, float("-inf")) < cada_s:
            return []
        ultima[tenant] = ahora
    defectos = defectos() if callable(defectos) else defectos
    aut = AutonomiaCubos(knowledge, tenant, bitacora=bitacora)
    aplicados = []
    tarjetas = cola.listar()
    for cubo, defecto in sorted(defectos.items()):
        incidente = incidente_de_racha(tarjetas, cubo, aut.ultimo_cambio(cubo))
        if incidente:
            r = aut.endurecer(cubo, defecto, causa="racha_de_denegadas", incidente=incidente)
            if r["aplicado"]:
                aplicados.append(r)
    v = bitacora.verificar()
    if not v.get("integra"):
        punto = f"sello:{v.get('punto_ruptura')}"
        for cubo, defecto in sorted(defectos.items()):
            r = aut.endurecer(cubo, defecto, causa="sello_roto", incidente=punto)
            if r["aplicado"]:
                aplicados.append(r)
    return aplicados
