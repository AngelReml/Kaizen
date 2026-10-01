"""Cola de aprobacion unificada del sustrato — D00 §4.3/§4.2 (bloque B5).

Maquina de estados estricta:
    PENDIENTE → APROBADA → EJECUTADA
         ↘ DENEGADA          ↘ (fallo) → REINTENTO/ANULADA
         ↘ CADUCADA (72 h sin decision)
    APROBADA → REVOCADA (antes de ejecutar)
    APROBADA → EN_MANOS → HECHA | ANULADA   (IRREVERSIBLE-EXTERNA que ejecuta el HUMANO, decision
                                             C1 de docs/AUTONOMIA_v0.md: el agente prepara, el
                                             operador ejecuta y confirma con evidencia)

Reglas duras: claim atomico (exactamente-una-vez); la revocacion gana si llega antes
del claim; caducidad R-13 de D09 (REVERSIBLE reencola UNA vez, IRR-EXT aborta siempre);
toda transicion emite `plataforma.aprobacion.*` con identidad; candado de umbrales
(sub-agentes solo endurecen). Es la cola del SUSTRATO: no sustituye a la de comercial
(INTOCABLE) — la unificacion fisica es decision v1.1; los cubos nuevos usan ESTA.
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timedelta, timezone

from core.rue import Sobre, nuevo_id

CLASES_ACCION = ("REVERSIBLE", "IRREVERSIBLE-INTERNA", "IRREVERSIBLE-EXTERNA")
NIVELES = ("CERO", "BAJA", "MEDIA", "ALTA")
# Niveles que NO se pueden fijar esta temporada (docs/AUTONOMIA_v0.md §2): ALTA queda
# reservado hasta que una apuesta demuestre con evidencia que se lo merece.
NIVELES_BLOQUEADOS = frozenset({"ALTA"})
CADUCIDAD_HORAS = 72
EVIDENCIA_MAX = 500


class TransicionAprobacionInvalida(ValueError):
    pass


def _ts(ahora: datetime | None = None) -> str:
    return (ahora or datetime.now(timezone.utc)).isoformat()


class ColaSustrato:
    """Una cola por tenant, sobre KnowledgeStore (tipo 'aprobacion_sustrato')."""

    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora
        self._lock = threading.Lock()

    # ── internos ──
    def _emitir(self, tipo: str, payload: dict) -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="plataforma.aprobaciones"))

    def _get(self, ap_id: str) -> dict:
        n = self.k.get(self.tenant, "aprobacion_sustrato", ap_id)
        if n is None:
            raise KeyError(f"aprobacion inexistente: {ap_id}")
        return n

    def _put(self, n: dict) -> None:
        self.k.add(self.tenant, "aprobacion_sustrato", n["id"], n)

    # ── FSM ──
    def solicitar(self, *, cubo: str, accion: str, clase: str, contenido_ref: str = "",
                  ahora: datetime | None = None, reencolada_de: str | None = None) -> dict:
        assert clase in CLASES_ACCION, f"clase invalida: {clase}"
        n = {"id": nuevo_id(), "tenant": self.tenant, "cubo": cubo, "accion": accion,
             "clase": clase, "contenido_ref": contenido_ref, "estado": "PENDIENTE",
             "creada_en": _ts(ahora), "decidida_por": None, "reencolada_de": reencolada_de,
             "reencolada": False, "ejecutada_en": None}
        self._put(n)
        self._emitir("plataforma.aprobacion.solicitada",
                     {"aprobacion_ref": n["id"], "cubo": cubo, "accion": accion, "clase": clase})
        return n

    def aprobar(self, ap_id: str, *, por: str) -> dict:
        with self._lock:
            n = self._get(ap_id)
            if n["estado"] != "PENDIENTE":
                raise TransicionAprobacionInvalida(f"aprobar desde {n['estado']} no permitido")
            n.update(estado="APROBADA", decidida_por=por, decidida_en=_ts())
            self._put(n)
        self._emitir("plataforma.aprobacion.concedida", {"aprobacion_ref": ap_id, "por": por})
        return n

    def denegar(self, ap_id: str, *, por: str, motivo: str = "") -> dict:
        with self._lock:
            n = self._get(ap_id)
            if n["estado"] != "PENDIENTE":
                raise TransicionAprobacionInvalida(f"denegar desde {n['estado']} no permitido")
            n.update(estado="DENEGADA", decidida_por=por, motivo=motivo, decidida_en=_ts())
            self._put(n)
        self._emitir("plataforma.aprobacion.denegada", {"aprobacion_ref": ap_id, "por": por})
        return n

    def revocar(self, ap_id: str, *, por: str) -> dict:
        """Solo desde APROBADA y ANTES del claim: la revocacion gana si llega antes."""
        with self._lock:
            n = self._get(ap_id)
            if n["estado"] != "APROBADA":
                raise TransicionAprobacionInvalida(
                    f"revocar desde {n['estado']} no permitido (si ya EJECUTADA, llego tarde)")
            n.update(estado="REVOCADA", decidida_por=por, decidida_en=_ts())
            self._put(n)
        self._emitir("plataforma.aprobacion.revocada", {"aprobacion_ref": ap_id, "por": por})
        return n

    def ejecutar(self, ap_id: str, ejecutor, *, por: str = "sistema") -> dict:
        """Claim atomico: exactamente-una-vez. `ejecutor(nodo)` hace el trabajo real.
        Fallo del ejecutor → REINTENTO (una vez mas) o ANULADA."""
        with self._lock:                                   # claim
            n = self._get(ap_id)
            if n["estado"] != "APROBADA":
                raise TransicionAprobacionInvalida(
                    f"ejecutar exige APROBADA; esta en {n['estado']}")
            n.update(estado="EJECUTANDO")
            self._put(n)
        try:
            resultado = ejecutor(n)
        except Exception as e:                             # noqa: BLE001
            with self._lock:
                n = self._get(ap_id)
                if n.get("reintentada"):
                    n.update(estado="ANULADA", motivo=f"fallo repetido: {e}")
                else:
                    n.update(estado="APROBADA", reintentada=True)  # REINTENTO disponible
                self._put(n)
            raise
        # El ejecutor real (p.ej. EjecutorComercial) puede devolver su resultado con el
        # estado REAL ("EJECUTADA" o "ENSAYO_SECO" si el sandbox global esta cerrado). Si
        # no devuelve nada (None, retro-compatibilidad), se asume EJECUTADA como antes.
        estado_final = "EJECUTADA"
        if isinstance(resultado, dict) and resultado.get("estado"):
            estado_final = resultado["estado"]
        # Si el ejecutor explica POR QUE no se hizo (p. ej. ANULADA: falta una configuracion), el motivo se
        # conserva: antes se perdia y la tarjeta solo decia "ANULADA" sin decir que hacer.
        extra = {"motivo": str(resultado["motivo"])[:400]} if isinstance(resultado, dict) and resultado.get("motivo") else {}
        with self._lock:
            n = self._get(ap_id)
            n.update(estado=estado_final, ejecutada_en=_ts(), ejecutada_por=por, **extra)
            self._put(n)
        self._emitir("plataforma.aprobacion.concedida",
                     {"aprobacion_ref": ap_id, "hito": "ejecutada", "por": por})
        return n

    # ── ejecuta el humano (C1/I1) ──
    def entregar_a_humano(self, ap_id: str, *, por: str) -> dict:
        """APROBADA → EN_MANOS. Solo IRREVERSIBLE-EXTERNA. Reclama la tarjeta igual que
        `ejecutar`: si el ejecutor automatico la reclamo antes, esto falla (y viceversa), asi
        que una accion sale o por codigo o por manos humanas, nunca por las dos."""
        with self._lock:
            n = self._get(ap_id)
            if n["estado"] != "APROBADA":
                raise TransicionAprobacionInvalida(
                    f"entregar a humano exige APROBADA; esta en {n['estado']}")
            if n["clase"] != "IRREVERSIBLE-EXTERNA":
                raise TransicionAprobacionInvalida(
                    f"solo IRREVERSIBLE-EXTERNA la ejecuta un humano; esta es {n['clase']}")
            n.update(estado="EN_MANOS", entregada_por=por, entregada_en=_ts())
            self._put(n)
        self._emitir("plataforma.aprobacion.en_manos", {"aprobacion_ref": ap_id, "por": por})
        return n

    def confirmar_hecha(self, ap_id: str, *, por: str, evidencia: str) -> dict:
        """EN_MANOS → HECHA, con evidencia obligatoria. La evidencia queda en la tarjeta; en la
        bitacora solo su huella sha256 (sellada y comprobable, sin volcar el texto al feed)."""
        evidencia = (evidencia or "").strip()
        if not evidencia:
            raise ValueError("confirmar como hecha exige evidencia (referencia, recibo, enlace...)")
        if len(evidencia) > EVIDENCIA_MAX:
            raise ValueError(f"la evidencia no puede pasar de {EVIDENCIA_MAX} caracteres")
        huella = hashlib.sha256(evidencia.encode("utf-8")).hexdigest()
        with self._lock:
            n = self._get(ap_id)
            if n["estado"] != "EN_MANOS":
                raise TransicionAprobacionInvalida(
                    f"confirmar como hecha exige EN_MANOS; esta en {n['estado']}")
            n.update(estado="HECHA", hecha_por=por, hecha_en=_ts(), evidencia=evidencia,
                     evidencia_sha256=huella)
            self._put(n)
        self._emitir("plataforma.aprobacion.hecha",
                     {"aprobacion_ref": ap_id, "por": por, "evidencia_sha256": huella})
        return n

    def anular_en_manos(self, ap_id: str, *, por: str, motivo: str) -> dict:
        """EN_MANOS → ANULADA: el humano decide no hacerla. Sin esta salida la tarjeta quedaria
        EN_MANOS para siempre (nada caduca ahi: ya la aprobo una persona)."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValueError("anular exige un motivo")
        with self._lock:
            n = self._get(ap_id)
            if n["estado"] != "EN_MANOS":
                raise TransicionAprobacionInvalida(
                    f"anular desde EN_MANOS; esta en {n['estado']}")
            n.update(estado="ANULADA", motivo=f"no hecha por el humano: {motivo}",
                     anulada_por=por, anulada_en=_ts())
            self._put(n)
        self._emitir("plataforma.aprobacion.no_hecha", {"aprobacion_ref": ap_id, "por": por})
        return n

    def barrer_caducadas(self, *, ahora: datetime | None = None) -> list[dict]:
        """PENDIENTE > 72h → CADUCADA. Post-caducidad R-13: REVERSIBLE se reencola UNA
        vez con aviso; IRR-EXT/IRR-INT se aborta SIEMPRE (jamas auto-reenvio)."""
        ahora = ahora or datetime.now(timezone.utc)
        limite = timedelta(hours=CADUCIDAD_HORAS)
        resultado = []
        ids = sorted(self.k.all(self.tenant, "aprobacion_sustrato").keys())
        for ap_id in ids:
            # Candado por item: releemos el nodo FRESCO dentro del candado y
            # re-comprobamos PENDIENTE antes de escribir CADUCADA, para no pisar una
            # aprobacion/denegacion/revocacion concurrente que ya lo saco de PENDIENTE.
            with self._lock:
                n = self._get(ap_id)
                if n["estado"] != "PENDIENTE":
                    continue
                creada = datetime.fromisoformat(n["creada_en"])
                if ahora - creada <= limite:
                    continue
                n.update(estado="CADUCADA")
                self._put(n)
            self._emitir("plataforma.aprobacion.caducada", {"aprobacion_ref": n["id"]})
            if n["clase"] == "REVERSIBLE" and not n.get("reencolada_de"):
                nueva = self.solicitar(cubo=n["cubo"], accion=n["accion"], clase=n["clase"],
                                       contenido_ref=n["contenido_ref"], ahora=ahora,
                                       reencolada_de=n["id"])
                with self._lock:
                    n = self._get(ap_id)
                    n["reencolada"] = True
                    self._put(n)
                resultado.append(nueva)
            resultado.append(n)
        return resultado

    def listar(self, estado: str | None = None) -> list[dict]:
        xs = list(self.k.all(self.tenant, "aprobacion_sustrato").values())
        return [x for x in xs if estado is None or x["estado"] == estado]


# ── Candado de umbrales / autonomia (D00 §4.2) ──────────────────────────────

def decidir_cambio_nivel(actual: str, pedido: str, *, actor: str) -> tuple[str, str, str]:
    """Decision PURA (sin I/O): (nivel resultante, veredicto, motivo del rechazo).
    Sub-agentes SOLO endurecen (bajar nivel); relajar exige operador; un nivel bloqueado
    (ALTA esta temporada) no lo fija nadie, ni el operador."""
    ia, ip = NIVELES.index(actual), NIVELES.index(pedido)
    if pedido in NIVELES_BLOQUEADOS and pedido != actual:
        return actual, "rechazado", "nivel_bloqueado"
    if ip > ia and actor != "operador":
        return actual, "rechazado", "solo_operador_relaja"
    return pedido, "aplicado", ""


def sellar_cambio_nivel(actual: str, pedido: str, *, actor: str, veredicto: str, motivo: str = "",
                        bitacora=None, tenant: str = "", cubo: str = "", causa: str = "",
                        extra: dict | None = None) -> None:
    """Sella `plataforma.autonomia.cambiada`. Va APARTE de la decision para que quien guarda estado
    pueda decidir dentro de su candado y sellar FUERA: publicar en la bitacora toma el candado de
    la bitacora, y tomarlo con otro candado de datos ya cogido invierte el orden que usa
    `Bitacora._encadenar` (interbloqueo ABBA, comprobado)."""
    if bitacora is None:
        return
    bitacora.publicar(Sobre(tenant_id=tenant or bitacora.tenant,
                            tipo="plataforma.autonomia.cambiada",
                            payload={"de": actual, "a": pedido, "actor": actor,
                                     "veredicto": veredicto,
                                     **({"motivo": motivo} if motivo else {}),
                                     **({"cubo": cubo} if cubo else {}),
                                     **({"causa": causa} if causa else {}),
                                     **(extra or {})},
                            origen="plataforma.autonomia"))


def cambiar_nivel(actual: str, pedido: str, *, actor: str, bitacora=None, tenant: str = "",
                  cubo: str = "", causa: str = "") -> str:
    """Decide y sella (para quien no guarda estado propio). Rechazos: se REGISTRAN."""
    nuevo, veredicto, motivo = decidir_cambio_nivel(actual, pedido, actor=actor)
    sellar_cambio_nivel(actual, pedido, actor=actor, veredicto=veredicto, motivo=motivo,
                        bitacora=bitacora, tenant=tenant, cubo=cubo, causa=causa)
    return nuevo
