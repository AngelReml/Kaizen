"""Cubo Inteligencia segun KAIZEN-D07 (D7.0/D7.1/D7.2) + R-05/R-17 de D09.

Regla de oro: propone, JAMAS ejecuta. Dos niveles de P8 (R-05): la fuente puede
llevar cliente_ref; el AGREGADO sale disociado (sin identificadores). Umbrales
versionados por el operador; alertas clasificadas por desviacion; correlacion
documentada con confianza (nunca certeza); FP con n pequeño segun R-17.
Degradacion elegante: sin P8, este cubo queda inactivo y nada se rompe.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from core.rue import Sobre, nuevo_id


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class CuboInteligencia:
    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora

    def _emitir(self, tipo: str, payload: dict) -> None:
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                  origen="inteligencia.cubo"))

    # ── D7.0: agregacion disociada (R-05) + umbrales versionados ──
    def agregar_p8(self) -> list[dict]:
        out = []
        for a in self.k.all(self.tenant, "p8_asiento").values():
            out.append({k: v for k, v in a.items() if k not in ("cliente_ref", "id")})
        return out

    def definir_umbral(self, metrica: str, minimo: float, maximo: float, *, por: str) -> dict:
        if por != "operador":
            raise PermissionError("los umbrales los define el operador (regla de oro)")
        if not (minimo < maximo):
            raise ValueError("rango invalido")
        actual = self.k.get(self.tenant, "umbral", metrica) or {"version": 0, "historial": []}
        u = {"metrica": metrica, "minimo": minimo, "maximo": maximo,
             "version": actual["version"] + 1,
             "historial": actual["historial"] + [{"version": actual["version"] + 1,
                                                  "minimo": minimo, "maximo": maximo,
                                                  "ts": _ts()}]}
        self.k.add(self.tenant, "umbral", metrica, u)
        self._emitir("inteligencia.umbral.definido",
                     {"metrica": metrica, "version": u["version"]})
        return u

    # ── D7.1: patron + anomalia ──
    def patron(self, metrica: str, valores: list[float]) -> dict:
        """Determinista: mismos datos → mismo resultado."""
        if not valores:
            return {"metrica": metrica, "n": 0, "estado": "SIN_DATOS (degradacion elegante)"}
        media = round(statistics.fmean(valores), 6)
        desv = round(statistics.pstdev(valores), 6) if len(valores) > 1 else 0.0
        r = {"metrica": metrica, "n": len(valores), "media": media, "desv": desv}
        self._emitir("inteligencia.patron.calculado", r)
        return r

    def detectar(self, metrica: str, valor: float) -> dict | None:
        u = self.k.get(self.tenant, "umbral", metrica)
        if u is None:
            return None                            # sin umbral no hay alerta (no ruido)
        if u["minimo"] <= valor <= u["maximo"]:
            return None
        ancho = u["maximo"] - u["minimo"]
        exceso = min(abs(valor - u["minimo"]), abs(valor - u["maximo"])) / ancho if ancho else 1
        sev = "CRITICA" if exceso > 1.0 else ("ADVERTENCIA" if exceso > 0.25 else "INFO")
        alerta = {"alerta_id": nuevo_id(), "metrica": metrica, "valor": valor,
                  "rango": [u["minimo"], u["maximo"]], "severidad": sev,
                  "estado": "EMITIDA", "ts": _ts()}
        self.k.add(self.tenant, "alerta", alerta["alerta_id"], alerta)
        self._emitir("inteligencia.alerta.emitida",
                     {"alerta_ref": alerta["alerta_id"], "metrica": metrica,
                      "severidad": sev})
        return alerta

    def resolver_alerta(self, alerta_id: str, *, veredicto: str, por: str) -> dict:
        assert veredicto in ("RECONOCIDA", "DESCARTADA", "RESUELTA")
        a = self.k.get(self.tenant, "alerta", alerta_id)
        if a is None:
            raise ValueError(f"alerta inexistente: {alerta_id}")
        a["estado"] = veredicto
        self.k.add(self.tenant, "alerta", alerta_id, a)
        return a

    def tasa_falsos_positivos(self) -> dict:
        """R-17: con n<15 la tasa es INFORMATIVA; el umbral bloqueante es 0 falsos CRITICA."""
        alertas = list(self.k.all(self.tenant, "alerta").values())
        n = len(alertas)
        descartadas = [a for a in alertas if a["estado"] == "DESCARTADA"]
        criticas_falsas = [a for a in descartadas if a["severidad"] == "CRITICA"]
        return {"n": n, "descartadas": len(descartadas),
                "tasa": round(len(descartadas) / n, 4) if n else 0.0,
                "medible": n >= 15,
                "criticas_falsas": len(criticas_falsas),
                "bloqueante_ok": len(criticas_falsas) == 0}

    # ── D7.2: correlacion (nunca certeza) + reporte ──
    def correlacionar(self, alerta_id: str, *, ventana_horas: int = 48) -> dict | None:
        a = self.k.get(self.tenant, "alerta", alerta_id)
        t_alerta = datetime.fromisoformat(a["ts"])
        candidatos = []
        for ev in self.k.all(self.tenant, "evento").values():
            if ev["tipo"].startswith("inteligencia."):
                continue
            dt = abs((datetime.fromisoformat(ev["ts"]) - t_alerta).total_seconds()) / 3600
            if dt <= ventana_horas:
                candidatos.append((dt, ev))
        if not candidatos:
            return None
        dt, ev = min(candidatos, key=lambda x: x[0])
        confianza = "ALTA" if dt < 1 else ("MEDIA" if dt < 12 else "BAJA")
        prop = {"alerta_ref": alerta_id, "evento_ref": ev["event_id"],
                "tipo_evento": ev["tipo"], "horas_de_distancia": round(dt, 2),
                "confianza": confianza,
                "narrativa": (f"coincidieron en el tiempo ({round(dt,1)} h); "
                              "correlacion documentada, NO causalidad probada")}
        self._emitir("inteligencia.correlacion.propuesta", prop)
        return prop

    def reporte_ejecutivo(self, periodo: str) -> dict:
        alertas = list(self.k.all(self.tenant, "alerta").values())
        r = {"periodo": periodo, "alertas": len(alertas),
             "por_severidad": {s: sum(1 for a in alertas if a["severidad"] == s)
                               for s in ("CRITICA", "ADVERTENCIA", "INFO")},
             "resumen": (f"{len(alertas)} alertas en {periodo}. "
                         "Este informe PROPONE; las decisiones son del operador."),
             "ts": _ts()}
        self._emitir("inteligencia.reporte.ejecutivo", {"periodo": periodo,
                                                        "alertas": len(alertas)})
        return r
