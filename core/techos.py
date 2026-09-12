"""Libro mayor de coste + techos con escalera de degradacion — D00 §6 (bloque B4).

Reglas: todo consumo genera asiento imputado a (tenant, cubo, rol, clase); el hard
stop va DELANTE de cada llamada (CORRECCIONES R2), jamas contabilidad posterior;
al alcanzar techo: downgrade → diferir → pausar nuevas IRR-EXT (las aprobadas
completan) → evento `plataforma.coste.techo_alcanzado` UNA vez por dia y tenant.
Jamas parada silenciosa; jamas perdida de acciones aprobadas.
Extiende (sin sustituir) el contador existente: unificacion = decision v1.1.
"""
from __future__ import annotations

import csv
import io
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from core import tenants as _tenants
from core.rue import Sobre, nuevo_id

CLASES = ("TRIVIAL", "ESTANDAR", "CRITICA", "COMITE")
TECHO_GLOBAL_EUR_DEFECTO = 25.0


def _techo_global_defecto() -> float:
    """Techo global (EUR/dia) configurable via KAIZEN_TECHO_GLOBAL_EUR; se lee en cada
    construccion de LibroCoste (no en el import) para que un cambio de entorno (o un
    monkeypatch de test) surta efecto. TECHO_GLOBAL_EUR_DEFECTO (25.0) es el fallback
    si la variable no esta definida — comportamiento previo intacto."""
    try:
        return float(os.environ.get("KAIZEN_TECHO_GLOBAL_EUR", str(TECHO_GLOBAL_EUR_DEFECTO)))
    except ValueError:
        return TECHO_GLOBAL_EUR_DEFECTO


def _hoy() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class TechoAlcanzado(RuntimeError):
    """Hard stop: la accion NO se ejecuta (el gasto previsto rebasaria el techo)."""


class LibroCoste:
    def __init__(self, knowledge, *, techo_global_eur: float | None = None,
                 mandatos=None, bitacoras: dict | None = None, ledger=None) -> None:
        self.k = knowledge
        self.techo_global = techo_global_eur if techo_global_eur is not None else _techo_global_defecto()
        self._mandatos = mandatos or {}            # tenant -> mandato dict (inyectable en tests)
        self._bitacoras = bitacoras or {}          # tenant -> Bitacora (opcional)
        self._ledger = ledger                      # core.ledger.LedgerCoste persistente (F1/F2)
        self._techo_avisado: set[str] = set()      # (tenant::dia) con evento ya emitido
        self._locks_meta = threading.Lock()        # protege la creacion de locks por tenant
        self._locks: dict[str, threading.Lock] = {}  # tenant -> candado de check-and-write

    # ── candado por tenant (check-and-write, C-12/G-10) ──
    def _lock_tenant(self, tenant: str) -> threading.Lock:
        with self._locks_meta:
            lock = self._locks.get(tenant)
            if lock is None:
                lock = threading.Lock()
                self._locks[tenant] = lock
            return lock

    @contextmanager
    def candado(self, tenant: str):
        """Candado exclusivo POR TENANT entre hard_stop_delante() y el asiento()
        correspondiente. En produccion el gasto real se escribe via LedgerCoste.asentar
        (core/ledger.py), no via LibroCoste.asiento() (que usan sobre todo los tests);
        hard_stop_delante() y asiento() ya toman este mismo candado por su cuenta, asi
        que el uso tipico `lc.hard_stop_delante(...); lc.asiento(...)` ya queda protegido
        salvo que otro hilo se cuele exactamente entre ambas llamadas — para cerrar ese
        hueco por completo, el llamador puede envolver ambas aqui dentro."""
        with self._lock_tenant(tenant):
            yield

    # ── mandato ──
    def _techo_tenant(self, tenant: str) -> float:
        if tenant in self._mandatos:
            return float(self._mandatos[tenant].get("techo_coste_diario_eur", 0.0))
        return float(_tenants.mandato(tenant).get("techo_coste_diario_eur", 0.0))

    # ── libro ──
    def gasto_dia(self, tenant: str, dia: str | None = None) -> float:
        dia = dia or _hoy()
        base = sum(a["coste_eur"] for a in self.k.all(tenant, "coste_asiento").values()
                   if a["dia"] == dia)
        # F1 (R-07): sumar el ledger persistente. Los escritores nuevos escriben SOLO
        # en el ledger; los coste_asiento del knowledge son el mundo B4 (tests) — no
        # hay doble conteo por regla de escritura (core/ledger.py, cabecera).
        extra = self._ledger.gasto_dia(tenant, dia) if self._ledger is not None else 0.0
        return round(base + extra, 6)

    def gasto_global_dia(self, dia: str | None = None) -> float:
        dia = dia or _hoy()
        base = sum(self.gasto_dia(t, dia) for t in self.k.companies())
        # El legado sin atribuir (claude_client) cuenta para el techo GLOBAL aunque no
        # tenga tenant: es dinero real (R-07). gasto_global_dia del ledger ya lo incluye,
        # pero los tenants presentes en knowledge ya sumaron su parte del ledger arriba —
        # aqui solo anadimos lo del ledger cuyos tenants NO estan en knowledge + legado.
        if self._ledger is not None:
            en_k = set(self.k.companies())
            extra = sum(a.get("coste_eur", 0.0) for a in self._ledger._iter()
                        if not a.get("_corrupta") and a.get("dia") == dia
                        and a.get("tenant") not in en_k)
            base += extra + self._ledger.sin_atribuir_dia(dia)
        return round(base, 6)

    def asiento(self, tenant: str, *, cubo: str, rol: str, clase: str, proveedor: str = "",
                modelo: str = "", unidades: float = 0, coste_eur: float = 0.0,
                causa_id: str | None = None) -> dict:
        """Registra el asiento. LLAMAR SIEMPRE DESPUES de hard_stop_delante()."""
        assert clase in CLASES, f"clase invalida: {clase}"
        a = {"id": nuevo_id(), "ts": datetime.now(timezone.utc).isoformat(), "dia": _hoy(),
             "tenant": tenant, "cubo": cubo, "rol": rol, "clase": clase,
             "proveedor": proveedor, "modelo": modelo, "unidades": unidades,
             "coste_eur": round(float(coste_eur), 6), "causa_id": causa_id}
        with self._lock_tenant(tenant):
            self.k.add(tenant, "coste_asiento", a["id"], a)
        return a

    # ── hard stop + escalera ──
    def hard_stop_delante(self, tenant: str, coste_previsto: float, *,
                          accion_aprobada_urgente: bool = False) -> dict:
        """DELANTE de cada llamada. Si rebasa techo (tenant o global) lanza
        TechoAlcanzado, salvo accion YA aprobada y urgente (completa, D00 §6.3.3)."""
        with self._lock_tenant(tenant):
            techo_t = self._techo_tenant(tenant)
            gasto = self.gasto_dia(tenant)
            rebasa_t = techo_t > 0 and gasto + coste_previsto > techo_t
            rebasa_g = self.techo_global > 0 and self.gasto_global_dia() + coste_previsto > self.techo_global
            if rebasa_t or rebasa_g:
                self._emitir_techo(tenant, gasto, techo_t if rebasa_t else self.techo_global)
                if accion_aprobada_urgente:
                    return {"permitido": True, "motivo": "aprobada-urgente completa (D00 §6.3.3)"}
                raise TechoAlcanzado(
                    f"techo {'tenant' if rebasa_t else 'global'} alcanzado: gasto {gasto:.4f} + "
                    f"previsto {coste_previsto:.4f} > {(techo_t if rebasa_t else self.techo_global):.4f} — "
                    "escalera: downgrade → diferir → pausar nuevas IRR-EXT")
            return {"permitido": True, "gasto_dia": gasto, "techo": techo_t}

    def _emitir_techo(self, tenant: str, gasto: float, techo: float) -> None:
        marca = f"{tenant}::{_hoy()}"
        if marca in self._techo_avisado:
            return
        self._techo_avisado.add(marca)
        b = self._bitacoras.get(tenant)
        if b is not None:
            b.publicar(Sobre(tenant_id=tenant, tipo="plataforma.coste.techo_alcanzado",
                             payload={"gasto_eur": gasto, "techo_eur": techo},
                             origen="plataforma.coste"))

    def escalera(self, tenant: str) -> dict:
        """Estado de degradacion vigente (D00 §6.3): sin parada silenciosa."""
        techo = self._techo_tenant(tenant)
        gasto = self.gasto_dia(tenant)
        tocado = techo > 0 and gasto >= techo
        return {"tenant": tenant, "gasto_dia": gasto, "techo": techo,
                "downgrade_clase": tocado, "diferir_no_urgente": tocado,
                "pausar_nuevas_irrext": tocado, "aprobadas_completan": True}

    def clase_efectiva(self, clase: str, tenant: str, *, lista_blanca: tuple = ()) -> str:
        if clase == "CRITICA" and self.escalera(tenant)["downgrade_clase"] and clase not in lista_blanca:
            return "ESTANDAR"
        return clase

    # ── export (primitiva del sustrato, D00 §6.1) ──
    def export_csv(self, tenant: str, mes: str, destino: Path | None = None) -> str:
        """CSV mensual por tenant y cubo. mes = 'AAAA-MM'."""
        filas = [a for a in self.k.all(tenant, "coste_asiento").values()
                 if a["dia"].startswith(mes)]
        if self._ledger is not None:                # F1: el CSV tambien cuenta el ledger
            filas += [{"id": "", "causa_id": a.get("causa_id"), **a}
                      for a in self._ledger.asientos_mes(tenant, mes)]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["dia", "tenant", "cubo", "rol", "clase",
                                            "proveedor", "modelo", "unidades", "coste_eur", "causa_id", "id", "ts"])
        w.writeheader()
        for a in sorted(filas, key=lambda x: x["ts"]):
            w.writerow(a)
        contenido = buf.getvalue()
        if destino:
            destino = Path(destino); destino.mkdir(parents=True, exist_ok=True)
            f = destino / f"coste_{tenant}_{mes}.csv"
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(contenido)
            if f.read_bytes().decode("utf-8") != contenido:     # E1 byte-exacto
                raise IOError(f"E1: desfase al escribir {f}")
        return contenido
