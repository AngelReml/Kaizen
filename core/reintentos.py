"""Motor de reintentos (Módulo 3 del sistema nervioso).

Decide cuándo y cómo se vuelve a tocar a un lead. Política en JSON por empresa.
Ver `docs/POLITICA_REINTENTOS.md` y ADR-003.

El motor NO muta el lead directamente — devuelve una `RecomendacionReintento` que
el caller (SDR / Director / hook) aplica. Esto lo hace trivial de testear.
"""
from __future__ import annotations

import copy
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from core.lead_schema import Compromiso, LeadDoc


TZ_ES = ZoneInfo("Europe/Madrid")


# ─────────────────────────────────────────────────────────────────────────────
#  Resultados de interacción reconocidos
# ─────────────────────────────────────────────────────────────────────────────

# El motor entiende estos resultados. Si llega algo desconocido, devuelve no-op.
RESULTADOS_CONOCIDOS = frozenset({
    "no_answer",
    "callback_pactado",
    "no_buen_momento_sin_fecha",
    "no_interesa_ahora",
    "no_interesa",
    "opt_out",
    "contacted_no_decisor",
    "engaged_pide_muestra",
})


# ─────────────────────────────────────────────────────────────────────────────
#  Estructuras
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecomendacionReintento:
    transicion_a: Optional[str] = None              # estado_pipeline destino
    proxima_accion_tipo: Optional[str] = None        # llamar | email | nurturing | none
    proxima_accion_ts: Optional[str] = None          # ISO UTC
    razon: str = ""
    compromiso_a_crear: Optional[Compromiso] = None
    do_not_call: bool = False
    incrementar_intentos: bool = False               # si suma a lead.reintentos.intentos_realizados


# ─────────────────────────────────────────────────────────────────────────────
#  Motor
# ─────────────────────────────────────────────────────────────────────────────

class MotorReintentos:
    """Carga la política de la empresa y produce `RecomendacionReintento` según
    el resultado de cada interacción.

    ASUNCIÓN DE USO: el motor decide el SIGUIENTE estado post-resultado. Asume
    que el caller (SDR / Director) ya ha registrado el resultado de la llamada
    moviendo el lead de `contacting` al estado intermedio correspondiente
    (`no_answer`, `contacted`, `engaged`). El motor solo decide de ahí hacia
    `queued` / `lost` / `do_not_call`. Esto respeta el grafo de la máquina de
    estados (M2) sin necesidad de transiciones múltiples.

    `clock` y `rng` se inyectan para tests deterministas."""

    def __init__(self, politica_path: Optional[Path] = None,
                 politica_dict: Optional[dict] = None,
                 clock=None, rng: Optional[random.Random] = None) -> None:
        if politica_dict is not None:
            self.politica = politica_dict
        elif politica_path is not None and politica_path.exists():
            self.politica = json.loads(politica_path.read_text(encoding="utf-8"))
        else:
            self.politica = _politica_default()
        self.tz = ZoneInfo(self.politica.get("tz", "Europe/Madrid"))
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.rng = rng or random.Random()

    # ── Resolución de reglas con override por categoría ────────────────────
    def regla(self, nombre: str, categoria: str = "") -> dict:
        base = dict(self.politica.get("reglas", {}).get(nombre, {}))
        if categoria:
            override = (self.politica.get("categorias_override", {})
                        .get(categoria, {})
                        .get(nombre, {}))
            base.update(override)
        return base

    # ── decidir() ──────────────────────────────────────────────────────────
    def decidir(self, lead: LeadDoc, resultado: str,
                contexto: Optional[dict] = None) -> RecomendacionReintento:
        contexto = contexto or {}
        cat = lead.categoria_icp or ""

        if resultado == "opt_out":
            r = self.regla("opt_out")
            return RecomendacionReintento(
                transicion_a=r.get("transicion", "do_not_call"),
                proxima_accion_tipo="none",
                razon=r.get("razon", "cliente pidió no más llamadas"),
                do_not_call=True,
            )

        if resultado == "no_interesa":
            r = self.regla("no_interesa")
            return RecomendacionReintento(
                transicion_a=r.get("transicion", "lost"),
                proxima_accion_tipo="none",
                razon=r.get("razon", "cliente expresó no interés"),
            )

        if resultado == "callback_pactado":
            r = self.regla("callback_pactado")
            fecha = contexto.get("callback_ts")
            if not fecha:
                # Sin fecha en el contexto, esto degenera en no_buen_momento.
                return self.decidir(lead, "no_buen_momento_sin_fecha", contexto)
            comp = Compromiso(
                id=f"cb_{lead.id}_{uuid.uuid4().hex[:8]}",
                tipo="callback",
                fecha_objetivo=fecha,
                tolerancia_min=int(r.get("tolerancia_min", 15)),
                contexto=contexto.get("contexto", "") or "callback pactado en llamada",
                origen_interaccion_id=contexto.get("origen_interaccion_id"),
            )
            return RecomendacionReintento(
                transicion_a="queued",
                proxima_accion_tipo="llamar",
                proxima_accion_ts=fecha,
                razon=f"callback pactado para {fecha}",
                compromiso_a_crear=comp,
                incrementar_intentos=False,            # callback NO cuenta como reintento
            )

        if resultado == "engaged_pide_muestra":
            r = self.regla("engaged_pide_muestra")
            return RecomendacionReintento(
                transicion_a=r.get("transicion", "sample_requested"),
                proxima_accion_tipo="enviar_muestra",
                razon="cliente pidió muestra",
            )

        if resultado in ("no_answer", "contacted_no_decisor"):
            r = self.regla(resultado, cat)
            max_int = int(r.get("max_intentos",
                                self.politica.get("default_max_intentos", 5)))
            ya = lead.reintentos.intentos_realizados
            if ya + 1 > max_int:
                return RecomendacionReintento(
                    transicion_a="lost",
                    proxima_accion_tipo="none",
                    razon=f"max intentos alcanzado ({max_int}) tras '{resultado}'",
                )
            horas = self.rng.uniform(
                float(r.get("intervalo_min_horas", 2)),
                float(r.get("intervalo_max_horas", 4)),
            )
            proxima = self._siguiente_franja_valida(self.clock() + timedelta(hours=horas))
            return RecomendacionReintento(
                transicion_a="queued",
                proxima_accion_tipo="llamar",
                proxima_accion_ts=proxima.isoformat(),
                razon=f"{resultado}; reintento {ya + 1}/{max_int}",
                incrementar_intentos=True,
            )

        if resultado == "no_buen_momento_sin_fecha":
            r = self.regla("no_buen_momento_sin_fecha")
            dias = int(r.get("espera_dias", 7))
            proxima = self._siguiente_franja_valida(
                self.clock() + timedelta(days=dias))
            return RecomendacionReintento(
                transicion_a="queued",
                proxima_accion_tipo="llamar",
                proxima_accion_ts=proxima.isoformat(),
                razon=f"no buen momento; reintento en {dias} días",
            )

        if resultado == "no_interesa_ahora":
            r = self.regla("no_interesa_ahora")
            meses = int(r.get("espera_meses", 3))
            proxima = self._siguiente_franja_valida(
                self.clock() + timedelta(days=meses * 30))
            return RecomendacionReintento(
                transicion_a="queued",
                proxima_accion_tipo="nurturing",
                proxima_accion_ts=proxima.isoformat(),
                razon=f"no interesa ahora; nurturing en {meses} meses",
            )

        # Resultado no reconocido — devolvemos no-op explícita.
        return RecomendacionReintento(
            razon=f"resultado desconocido '{resultado}'; sin acción",
        )

    # ── aplicar() — única función que muta el lead ─────────────────────────
    def aplicar(self, lead: LeadDoc, rec: RecomendacionReintento,
                machine=None) -> LeadDoc:
        """Aplica una recomendación al lead.

        Si `machine` se pasa, se usa para la transición (recomendado, así el
        historial_pipeline queda consistente). Si no, se actualiza el campo
        `estado_pipeline` directamente sin pasar por la máquina (modo "atómico
        sin auditar" — solo tests y migraciones).
        """
        if rec.do_not_call:
            lead.do_not_call = True
        if rec.transicion_a:
            if machine is not None:
                machine.transicionar(lead, rec.transicion_a, razon=rec.razon)
            else:
                lead.estado_pipeline = rec.transicion_a
        if rec.proxima_accion_tipo is not None:
            lead.reintentos.proxima_accion_tipo = rec.proxima_accion_tipo
        if rec.proxima_accion_ts is not None:
            lead.reintentos.proxima_accion_ts = rec.proxima_accion_ts
        if rec.razon:
            lead.reintentos.ultima_razon_reintento = rec.razon
        if rec.incrementar_intentos:
            lead.reintentos.intentos_realizados += 1
        if rec.compromiso_a_crear is not None:
            # Idempotencia: no duplicar un compromiso con la misma fecha+tipo.
            ya = any(c.tipo == rec.compromiso_a_crear.tipo
                     and c.fecha_objetivo == rec.compromiso_a_crear.fecha_objetivo
                     for c in lead.compromisos)
            if not ya:
                lead.compromisos.append(rec.compromiso_a_crear)
        return lead

    # ── Cálculo de franja válida en hora ES ─────────────────────────────────
    def _siguiente_franja_valida(self, dt_utc: datetime) -> datetime:
        """Dado un datetime UTC, devuelve el siguiente datetime UTC que cae en
        una franja comercial española válida."""
        dias_validos = set(self.politica.get("dias_laborables", [0, 1, 2, 3, 4]))
        franjas = self._franjas_parsed()
        if not franjas:
            return dt_utc                              # política sin franjas
        # Convierte a hora local
        local = dt_utc.astimezone(self.tz)
        for _ in range(14):                            # máximo 14 días buscando
            if local.weekday() in dias_validos:
                for inicio, fin in franjas:
                    inicio_dt = local.replace(hour=inicio, minute=0, second=0, microsecond=0)
                    fin_dt = local.replace(hour=fin, minute=0, second=0, microsecond=0)
                    if inicio_dt <= local < fin_dt:
                        return local.astimezone(timezone.utc)
                    if local < inicio_dt:
                        return inicio_dt.astimezone(timezone.utc)
            # Saltar al día siguiente
            local = (local + timedelta(days=1)).replace(
                hour=franjas[0][0], minute=0, second=0, microsecond=0)
        return local.astimezone(timezone.utc)

    def _franjas_parsed(self) -> list[tuple[int, int]]:
        raw = self.politica.get("franjas_horarias_es", ["10-13", "16-19"])
        out = []
        for f in raw:
            if "-" not in f: continue
            ini, fin = f.split("-")
            try:
                out.append((int(ini.strip()), int(fin.strip())))
            except ValueError:
                continue
        return out


def _politica_default() -> dict:
    """Política mínima razonable cuando no hay JSON en disco."""
    return {
        "version": "default",
        "default_max_intentos": 3,
        "franjas_horarias_es": ["10-13", "16-19"],
        "dias_laborables": [0, 1, 2, 3, 4],
        "tz": "Europe/Madrid",
        "reglas": {
            "no_answer": {"intervalo_min_horas": 2, "intervalo_max_horas": 4,
                          "max_intentos": 3, "ventana_dias": 7},
            "contacted_no_decisor": {"intervalo_min_horas": 2, "intervalo_max_horas": 4,
                                      "max_intentos": 3, "ventana_dias": 7},
            "no_buen_momento_sin_fecha": {"espera_dias": 7},
            "no_interesa_ahora": {"espera_meses": 3},
            "no_interesa": {"transicion": "lost", "razon": "cliente expresó no interés"},
            "opt_out": {"transicion": "do_not_call",
                        "razon": "cliente pidió no más llamadas"},
            "callback_pactado": {"tolerancia_min": 15},
            "engaged_pide_muestra": {"transicion": "sample_requested"},
        },
        "categorias_override": {},
    }
