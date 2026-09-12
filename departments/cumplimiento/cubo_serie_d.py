"""Cubo Cumplimiento segun KAIZEN-D08 (D8.0/D8.1/D8.2).

Regla de oro: si no esta documentado aqui, no existio legalmente. FSM de la
obligacion con INCUMPLIDA automatica por timeout; vault de evidencias con hash
sha256 (edicion posterior = CORRUPTA, detectable siempre); alertas 30/7/1;
auditor automatico reproducible; compilador de defensa con manifest integro.

GL-05 (D09): el calendario de obligaciones NO SE SIEMBRA — nace VACIO y solo
entra contenido validado linea a linea por la gestoria de Ivan (accion externa).
`CALENDARIO_SEMBRADO = False` DOCUMENTA esta garantia; NO es un guard fisico
comprobado en ningun metodo de este fichero (no existe una siembra masiva que
comprobarla evitaria) — la garantia real y comprobada es que `registrar()`
exige `fuente_validada_por` para toda obligacion REGULATORIA.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from core.rue import Sobre, nuevo_id

CALENDARIO_SEMBRADO = False    # GL-05: documenta la garantia (no comprobado en codigo;
                                # ver aviso en el docstring del modulo)

ESTADOS = ("REGISTRADA", "ASIGNADA", "EN_CURSO", "CUMPLIDA", "AUDITADA", "INCUMPLIDA",
           "ACCION_CORRECTIVA", "CERRADA", "RECHAZADA")
ALERTAS_DIAS = (30, 7, 1)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class CuboCumplimiento:
    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora

    def _emitir(self, tipo: str, payload: dict) -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="cumplimiento.cubo"))

    # ── D8.0: registro + evidencia + alertas ──
    def registrar(self, *, nombre: str, tipo: str, fecha_limite: str, area: str,
                  fuente_validada_por: str = "") -> dict:
        """Toda obligacion exige fecha clara. Las regulatorias exigen fuente validada
        (GL-05): sin gestoria detras, una fecha legal no entra."""
        if tipo == "REGULATORIA" and not fuente_validada_por:
            raise ValueError("GL-05: obligacion regulatoria sin validacion de gestoria NO entra")
        datetime.fromisoformat(fecha_limite)      # fecha borrosa = ValueError
        o = {"id": nuevo_id(), "nombre": nombre, "tipo": tipo, "fecha_limite": fecha_limite,
             "area": area, "estado": "REGISTRADA", "fuente_validada_por": fuente_validada_por,
             "alertas_emitidas": [], "evidencias": [], "ts": _ts()}
        self.k.add(self.tenant, "obligacion", o["id"], o)
        self._emitir("cumplimiento.obligacion.registrada",
                     {"obligacion_ref": o["id"], "tipo": tipo, "fecha_limite": fecha_limite})
        return o

    def asignar(self, ob_id: str, responsable: str) -> dict:
        o = self.k.get(self.tenant, "obligacion", ob_id)
        o.update(estado="ASIGNADA", responsable=responsable)
        self.k.add(self.tenant, "obligacion", ob_id, o)
        self._emitir("cumplimiento.obligacion.asignada",
                     {"obligacion_ref": ob_id, "responsable": responsable})
        return o

    def aportar_evidencia(self, ob_id: str, *, nombre_fichero: str, contenido: bytes,
                          firmante: str = "") -> dict:
        o = self.k.get(self.tenant, "obligacion", ob_id)
        ev = {"id": nuevo_id(), "fichero": nombre_fichero, "sha256": _sha(contenido),
              "bytes": len(contenido), "ts": _ts(), "firmante": firmante}
        self.k.add(self.tenant, "evidencia", ev["id"], ev)
        o["evidencias"].append(ev["id"])
        if o["estado"] in ("ASIGNADA", "REGISTRADA"):
            o["estado"] = "EN_CURSO"
        self.k.add(self.tenant, "obligacion", ob_id, o)
        self._emitir("cumplimiento.evidencia.aportada",
                     {"obligacion_ref": ob_id, "evidencia_ref": ev["id"], "sha256_hash": ev["sha256"]})
        return ev

    def verificar_evidencia(self, ev_id: str, contenido_actual: bytes) -> dict:
        ev = self.k.get(self.tenant, "evidencia", ev_id)
        integra = ev["sha256"] == _sha(contenido_actual)
        return {"evidencia_ref": ev_id, "integra": integra,
                "veredicto": "INTEGRA" if integra else "CORRUPTA (editada post-hoc)"}

    def cumplir(self, ob_id: str, *, por: str) -> dict:
        o = self.k.get(self.tenant, "obligacion", ob_id)
        if not o["evidencias"]:
            raise ValueError("sin evidencia no hay cumplimiento documentado (regla de oro)")
        o.update(estado="CUMPLIDA", cumplida_en=_ts(), cumplida_por=por)
        self.k.add(self.tenant, "obligacion", ob_id, o)
        self._emitir("cumplimiento.obligacion.cumplida", {"obligacion_ref": ob_id})
        return o

    def barrer_plazos(self, *, ahora: datetime | None = None) -> list[dict]:
        """Alertas 30/7/1 y timeout→INCUMPLIDA automatica (gate determinista)."""
        ahora = ahora or datetime.now(timezone.utc)
        salidas = []
        for ob_id, o in sorted(self.k.all(self.tenant, "obligacion").items()):
            if o["estado"] in ("CUMPLIDA", "AUDITADA", "CERRADA", "RECHAZADA", "INCUMPLIDA"):
                continue
            limite = datetime.fromisoformat(o["fecha_limite"])
            if limite.tzinfo is None:
                limite = limite.replace(tzinfo=timezone.utc)
            restante = (limite - ahora).days
            if restante < 0:
                o["estado"] = "INCUMPLIDA"
                self.k.add(self.tenant, "obligacion", ob_id, o)
                self._emitir("cumplimiento.obligacion.incumplida", {"obligacion_ref": ob_id})
                salidas.append({"obligacion": ob_id, "aviso": "INCUMPLIDA"})
                continue
            for d in ALERTAS_DIAS:
                if restante <= d and d not in o["alertas_emitidas"]:
                    o["alertas_emitidas"].append(d)
                    self.k.add(self.tenant, "obligacion", ob_id, o)
                    urg = "CRITICA" if d == 1 else ("ADVERTENCIA" if d == 7 else "INFO")
                    self._emitir("cumplimiento.alerta.plazo",
                                 {"obligacion_ref": ob_id, "dias_restantes": restante,
                                  "urgencia": urg})
                    salidas.append({"obligacion": ob_id, "aviso": f"alerta_{d}d"})
        return salidas

    # ── D8.1: validacion + auditoria ──
    def validar_expediente(self, ob_id: str) -> dict:
        o = self.k.get(self.tenant, "obligacion", ob_id)
        checklist = {"fecha_limite": bool(o.get("fecha_limite")),
                     "responsable": bool(o.get("responsable")),
                     "evidencias": bool(o.get("evidencias")),
                     "cumplida_en": bool(o.get("cumplida_en"))}
        veredicto = "COMPLETO" if all(checklist.values()) else "INCOMPLETO"
        self._emitir("cumplimiento.expediente.validado",
                     {"obligacion_ref": ob_id, "veredicto": veredicto})
        return {"obligacion_ref": ob_id, "checklist": checklist, "veredicto": veredicto}

    def auditar(self) -> dict:
        """Auditoria automatica reproducible: mismo estado → mismo veredicto."""
        hallazgos = []
        for ob_id, o in sorted(self.k.all(self.tenant, "obligacion").items()):
            if o["estado"] == "CUMPLIDA":
                v = self.validar_expediente(ob_id)["veredicto"]
                hallazgos.append({"obligacion_ref": ob_id,
                                  "veredicto": "CUMPLIDO" if v == "COMPLETO" else "CUMPLIDO_PARCIAL"})
                if v == "COMPLETO":
                    o["estado"] = "AUDITADA"
                    self.k.add(self.tenant, "obligacion", ob_id, o)
            elif o["estado"] == "INCUMPLIDA":
                hallazgos.append({"obligacion_ref": ob_id, "veredicto": "NO_CUMPLIDO"})
        acta = {"auditoria_id": nuevo_id(), "ts": _ts(), "hallazgos": hallazgos}
        self.k.add(self.tenant, "auditoria_cumplimiento", acta["auditoria_id"], acta)
        self._emitir("cumplimiento.auditoria.ejecutada",
                     {"auditoria_ref": acta["auditoria_id"], "n_hallazgos": len(hallazgos)})
        return acta

    # ── D8.2: defensa documental ──
    def compilar_defensa(self) -> dict:
        """Expediente entregable: manifest integro con hashes; nada faltante o corrupto."""
        obligaciones = sorted(self.k.all(self.tenant, "obligacion").items())
        evidencias = {e["id"]: e for e in self.k.all(self.tenant, "evidencia").values()}
        piezas, faltantes = [], []
        for ob_id, o in obligaciones:
            for ev_id in o.get("evidencias", []):
                if ev_id in evidencias:
                    piezas.append({"obligacion": ob_id, "evidencia": ev_id,
                                   "sha256": evidencias[ev_id]["sha256"]})
                else:
                    faltantes.append(ev_id)
        manifest = {"tenant": self.tenant, "ts": _ts(), "obligaciones": len(obligaciones),
                    "piezas": piezas, "faltantes": faltantes,
                    "integro": not faltantes}
        manifest["hash_manifest"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self._emitir("cumplimiento.defensa.preparada",
                     {"hash_manifest": manifest["hash_manifest"], "integro": manifest["integro"]})
        return manifest
