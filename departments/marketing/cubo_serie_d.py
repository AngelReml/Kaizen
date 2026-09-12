"""Cubo Marketing segun KAIZEN-D06 (D6.0) + R-10/R-15/R-20 de D09.

Regla de oro: TODO contenido pasa Brand (servicio del sustrato) antes de salir —
sin VALIDADO_POR_BRAND no avanza (bloqueante). Presupuesto en tres capas (R-10):
el hard cap real vive en la plataforma del canal (externo, anotado); aqui viven
la reconciliacion del gasto reportado y el kill-switch al 90%. Atribucion via
lead.fuentes tipo CAMPANA (R-15): jamas se toca el payload de pedido.atribuido.
Canales: SOLO adaptadores dry-run (GR-08); APIs oficiales cuando existan (R-20).
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.rue import Sobre, nuevo_id

ESTADOS_CAMPANA = ("BORRADOR", "APROBADA", "ACTIVA", "PAUSADA", "COMPLETADA", "CANCELADA")
ESTADOS_CONTENIDO = ("GENERADO", "VALIDADO_POR_BRAND", "RECHAZADO", "APROBADO", "LANZADO", "ARCHIVADO")
KILL_SWITCH_PCT = 0.9


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class GateMarketing(RuntimeError):
    pass


class CuboMarketing:
    def __init__(self, knowledge, tenant: str, *, bitacora=None, servicio_verificacion=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora
        self.svc = servicio_verificacion          # ServicioVerificacion del sustrato (B6)

    def _emitir(self, tipo: str, payload: dict) -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="marketing.cubo"))

    # ── campañas ──
    def crear_campana(self, *, nombre: str, segmento: str, canales: list[str],
                      presupuesto_eur: float, duracion_dias: int) -> dict:
        c = {"id": nuevo_id(), "nombre": nombre, "segmento": segmento, "canales": canales,
             "presupuesto_eur": float(presupuesto_eur), "gasto_reportado_eur": 0.0,
             "duracion_dias": duracion_dias, "estado": "BORRADOR", "metricas": [],
             "contenidos": [], "ts": _ts()}
        self.k.add(self.tenant, "campana", c["id"], c)
        return c

    def aprobar_campana(self, c_id: str, *, por: str) -> dict:
        if por != "operador":
            raise PermissionError("la campaña la aprueba el operador")
        c = self.k.get(self.tenant, "campana", c_id)
        c["estado"] = "APROBADA"
        self.k.add(self.tenant, "campana", c_id, c)
        return c

    # ── contenido con Brand bloqueante ──
    def crear_contenido(self, c_id: str, *, tipo: str, texto: str) -> dict:
        cont = {"id": nuevo_id(), "campana_ref": c_id, "tipo": tipo, "texto": texto,
                "estado": "GENERADO"}
        self.k.add(self.tenant, "contenido_mkt", cont["id"], cont)
        self._emitir("marketing.contenido.creado", {"contenido_ref": cont["id"], "tipo": tipo})
        return cont

    def validar_con_brand(self, cont_id: str) -> dict:
        if self.svc is None:
            raise GateMarketing("sin servicio de verificacion no se valida NADA (regla de oro)")
        cont = self.k.get(self.tenant, "contenido_mkt", cont_id)
        v = self.svc.validar_borrador(self.tenant, "marketing", cont["texto"],
                                      paquetes_politicas=("brand",))
        cont["estado"] = "VALIDADO_POR_BRAND" if v.veredicto == "APTO" else "RECHAZADO"
        cont["brand_hash"] = v.hash
        self.k.add(self.tenant, "contenido_mkt", cont_id, cont)
        if cont["estado"] == "VALIDADO_POR_BRAND":
            self._emitir("marketing.contenido.aprobado",
                         {"contenido_ref": cont_id, "brand_hash": v.hash})
        return cont

    def lanzar(self, c_id: str, cont_id: str) -> dict:
        """Lanzamiento SIEMPRE dry-run aqui (GR-08): el adaptador real es externo."""
        c = self.k.get(self.tenant, "campana", c_id)
        cont = self.k.get(self.tenant, "contenido_mkt", cont_id)
        if cont["estado"] != "VALIDADO_POR_BRAND":
            raise GateMarketing("lanzamiento imposible sin VALIDADO_POR_BRAND (13.8)")
        if self._kill_switch(c):
            raise GateMarketing("kill-switch 90% del presupuesto: campaña pausada (R-10)")
        if c["estado"] not in ("APROBADA", "ACTIVA"):
            raise GateMarketing("campaña sin aprobar")
        c["estado"] = "ACTIVA"
        cont["estado"] = "LANZADO"
        c["contenidos"].append(cont_id)
        self.k.add(self.tenant, "campana", c_id, c)
        self.k.add(self.tenant, "contenido_mkt", cont_id, cont)
        self._emitir("marketing.campana.lanzada",
                     {"campana_ref": c_id, "contenido_ref": cont_id, "dry_run": True})
        return {"dry_run": True, "campana": c_id}

    # ── presupuesto R-10 (tres capas; aqui capas 2 y 3) ──
    def _kill_switch(self, c: dict) -> bool:
        return c["gasto_reportado_eur"] >= KILL_SWITCH_PCT * c["presupuesto_eur"]

    def pausar(self, c_id: str, *, por: str) -> dict:
        """Pausa manual EXPLICITA e INCONDICIONAL (P0): no depende de la reconciliacion
        de gasto ni del kill-switch del 90%. El endpoint /cmd/marketing/pausar debe
        llamar a este metodo (no inferir el estado a partir del gasto reportado)."""
        c = self.k.get(self.tenant, "campana", c_id)
        if c is None:
            raise ValueError(f"campaña inexistente: {c_id}")
        c["estado"] = "PAUSADA"
        self.k.add(self.tenant, "campana", c_id, c)
        self._emitir("marketing.campana.ajustada",
                     {"campana_ref": c_id, "cambio": "PAUSA",
                      "razon": f"pausa manual solicitada por {por}"})
        return c

    def reconciliar_gasto(self, c_id: str, gasto_reportado_eur: float) -> dict:
        """Capa 2: el gasto REAL lo reporta el canal (asincrono). Capa 3: al 90%, pausa."""
        c = self.k.get(self.tenant, "campana", c_id)
        c["gasto_reportado_eur"] = round(c["gasto_reportado_eur"] + float(gasto_reportado_eur), 2)
        if self._kill_switch(c) and c["estado"] == "ACTIVA":
            c["estado"] = "PAUSADA"
            self._emitir("marketing.campana.ajustada",
                         {"campana_ref": c_id, "cambio": "PAUSA",
                          "razon": "kill-switch 90% presupuesto (R-10)"})
        self.k.add(self.tenant, "campana", c_id, c)
        return c

    # ── metricas y ROI via lead (R-15) ──
    def registrar_metrica(self, c_id: str, *, fecha: str, impresiones: int, clicks: int,
                          coste_eur: float) -> dict:
        c = self.k.get(self.tenant, "campana", c_id)
        m = {"fecha": fecha, "impresiones": impresiones, "clicks": clicks,
             "coste_eur": coste_eur}
        c["metricas"].append(m)
        self.k.add(self.tenant, "campana", c_id, c)
        self._emitir("marketing.campana.metrica", {"campana_ref": c_id, **m})
        return m

    def roi(self, c_id: str) -> dict:
        """Sigue la cadena campana → lead (fuentes tipo CAMPANA) → pedido_atribuido.
        R-15: cero campos nuevos en el payload del pedido."""
        leads = [lid for lid, l in self.k.all(self.tenant, "lead_canon").items()
                 if any(f.get("tipo") == "CAMPANA" and f.get("ref") == c_id
                        for f in l.get("fuentes", []))]
        pedidos = [p for p in self.k.all(self.tenant, "pedido_atribuido").values()
                   if p.get("lead_ref") in leads and p["estado"] == "ATRIBUIDO"]
        c = self.k.get(self.tenant, "campana", c_id)
        return {"campana_ref": c_id, "leads_generados": len(leads),
                "conversiones": len(pedidos),
                "gasto_reportado_eur": c["gasto_reportado_eur"],
                "verificable": True}
