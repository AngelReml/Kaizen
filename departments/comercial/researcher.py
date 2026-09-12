"""Researcher — el primer agente del Departamento Comercial (§2.4 del v0.2).

Identifica empresas HORECA en el área de influencia logística del tenant. Opera N hilos
de búsqueda paralela con `ThreadPoolExecutor` sobre las fuentes configuradas (default:
Google Places). Aplica el ICP determinista y clasifica por anillo geográfico antes de
crear el lead en el `LeadStore`.

Sin mocks: una pasada hace llamadas reales a las APIs configuradas.
"""
from __future__ import annotations

import re
import sys
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterable

from core.events import Event, EventType
from departments.comercial.anillos import ClasificadorAnillos
from departments.comercial.fuentes.base import CandidatoCrudo, FuenteLeads
from departments.comercial.icp import FiltroICP
from departments.comercial.lifecycle import EstadoLead, LeadStore


@dataclass
class CampaniaBusqueda:
    query: str
    centro: dict
    radio_m: int
    categoria_target: str
    anillo_target: int


@dataclass
class ResultadoPasada:
    campanas: int = 0
    candidatos_brutos: int = 0
    duplicados: int = 0
    candidatos_unicos: int = 0
    descartes_icp: int = 0
    descartes_anillo: int = 0
    cualificados_nuevos: int = 0
    leads_ya_existentes: int = 0
    detalle_por_categoria: dict[str, int] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)

    @property
    def tasa_descarte_icp(self) -> float:
        return round(self.descartes_icp / self.candidatos_unicos * 100, 1) if self.candidatos_unicos else 0.0


class Researcher:
    """Búsqueda + dedup + ICP + anillo + creación del lead. No hace enrichment."""

    def __init__(self, *, icp: FiltroICP, anillos: ClasificadorAnillos,
                 fuentes: Iterable[FuenteLeads], lead_store: LeadStore,
                 bus=None, max_workers: int = 4) -> None:
        self.icp = icp
        self.anillos = anillos
        self.fuentes = list(fuentes)
        self.lead_store = lead_store
        self.bus = bus
        self.max_workers = max_workers
        self._lock = threading.Lock()   # protege estado compartido en agregación

    # ── Construcción de campañas a partir del ICP (data-driven) ────────────
    def construir_campanas(self, prioridades: tuple[str, ...] = ("ALTA", "MEDIA")) -> list[CampaniaBusqueda]:
        """Combina (categorías × ciudades del anillo activo). El radio se calcula desde el
        límite del anillo máximo activo para que la geo-bias de Places cubra todo el área."""
        origen = self.icp.origen
        max_anillo = self.icp.max_anillo
        # Estimación generosa: 90 km/h media de carretera murciana × minutos del anillo.
        from departments.comercial.anillos import LIMITES_ANILLOS_MIN
        radio_m = int(LIMITES_ANILLOS_MIN.get(max_anillo, 45) * 1500)      # 1.5 km/min de holgura

        campanas: list[CampaniaBusqueda] = []
        anillos_data = self.icp.data.get("geografia", {}).get("anillos", {})
        for anillo in range(max_anillo + 1):
            ciudades = anillos_data.get(str(anillo), [])
            for tipo in self.icp._tipos_incluidos:
                if tipo["prioridad"] not in prioridades:
                    continue
                seeds = tipo.get("query_seeds") or [tipo["categoria"].replace("_", " ")]
                for seed in seeds:
                    for ciudad in ciudades:
                        campanas.append(CampaniaBusqueda(
                            query=f"{seed} en {ciudad}",
                            centro={"lat": origen["lat"], "lon": origen["lon"]},
                            radio_m=radio_m,
                            categoria_target=tipo["categoria"],
                            anillo_target=anillo,
                        ))
        return campanas

    # ── Pasada completa ────────────────────────────────────────────────────
    def ejecutar_pasada(self, *, prioridades: tuple[str, ...] = ("ALTA", "MEDIA"),
                        max_por_query: int = 15, verbose: bool = True) -> ResultadoPasada:
        from datetime import datetime, timezone
        ts_pasada = datetime.now(timezone.utc).isoformat()
        campanas = self.construir_campanas(prioridades)
        res = ResultadoPasada(campanas=len(campanas))
        if verbose:
            print(f"[Researcher] {len(campanas)} campañas de búsqueda · "
                  f"{len(self.fuentes)} fuente(s) · workers={self.max_workers}")

        candidatos_brutos: list[tuple[CandidatoCrudo, str]] = []   # (cand, categoria_target)
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futuros = {ex.submit(self._buscar_una, c, max_por_query): c for c in campanas}
            for fut in as_completed(futuros):
                c = futuros[fut]
                try:
                    items = fut.result()
                    candidatos_brutos.extend((cand, c.categoria_target) for cand in items)
                except Exception as e:
                    msg = f"campaña '{c.query}' falló: {e}"
                    res.errores.append(msg)
                    print(f"[Researcher] {msg}", file=sys.stderr)

        res.candidatos_brutos = len(candidatos_brutos)
        if verbose:
            print(f"[Researcher] candidatos brutos: {res.candidatos_brutos}")

        # Dedup por (fuente, id_externo). Fallback a slug del nombre si la fuente no da id.
        unicos: dict[tuple[str, str], tuple[CandidatoCrudo, str]] = {}
        for cand, categoria in candidatos_brutos:
            clave = (cand.fuente, cand.id_externo or _slug(cand.nombre))
            if clave not in unicos:
                unicos[clave] = (cand, categoria)
        res.candidatos_unicos = len(unicos)
        res.duplicados = res.candidatos_brutos - res.candidatos_unicos

        # ICP + anillo + creación del lead
        for cand, categoria_target in unicos.values():
            decision = self.icp.evaluar({
                "nombre": cand.nombre,
                "place_types": cand.place_types,
                "descripcion": cand.descripcion,
            })
            if not decision.aceptado:
                res.descartes_icp += 1
                self._registrar_descarte(cand, categoria_target, "icp",
                                         decision.razones[0] if decision.razones else "sin razón")
                continue

            if not (cand.ubicacion.get("lat") and cand.ubicacion.get("lon")):
                res.errores.append(f"{cand.nombre}: sin coordenadas, se descarta")
                res.descartes_anillo += 1
                self._registrar_descarte(cand, categoria_target, "anillo", "sin coordenadas")
                continue
            try:
                anillo_res = self.anillos.clasificar(
                    cand.ubicacion["lat"], cand.ubicacion["lon"], cand.direccion,
                )
            except Exception as e:
                res.errores.append(f"{cand.nombre}: clasificación anillo falló: {e}")
                res.descartes_anillo += 1
                self._registrar_descarte(cand, categoria_target, "anillo",
                                         f"clasificación falló: {e}")
                continue

            if not anillo_res.activo:
                res.descartes_anillo += 1
                self._registrar_descarte(
                    cand, categoria_target, "anillo",
                    f"anillo {anillo_res.anillo} fuera del máximo activo "
                    f"({anillo_res.distancia_minutos} min)")
                continue

            lead_id = _slug(cand.nombre)
            if self.lead_store.get(lead_id) is not None:
                res.leads_ya_existentes += 1
                continue

            self.lead_store.crear(lead_id, {
                "nombre": cand.nombre,
                "tipo_detectado": cand.tipo_principal,
                "categoria_icp": decision.categoria,
                "prioridad_icp": decision.prioridad,
                "anillo": anillo_res.anillo,
                "ubicacion": {**cand.ubicacion, "direccion": cand.direccion},
                "distancia_minutos": anillo_res.distancia_minutos,
                "distancia_metros": anillo_res.distancia_metros,
                "distancia_provider": anillo_res.proveedor,
                "fuentes": [{"nombre": cand.fuente, "id_externo": cand.id_externo}],
                "contacto": {
                    "telefono": cand.metadatos.get("telefono"),
                    "web": cand.metadatos.get("web"),
                },
                "metadatos_fuente": cand.metadatos,
                "descripcion": cand.descripcion,
                # I-1 (D11 E1): el insumo más fuerte del ICP se persiste con el lead.
                "place_types": list(cand.place_types or []),
                # I-3 (D11 E1): señal y peso del match — la decisión lleva sus insumos.
                "icp_match": {"senal": decision.senal, "peso": decision.peso,
                              "razon": decision.razones[0] if decision.razones else ""},
            }, razon=f"Identificado por Researcher pasada para {decision.categoria}")

            # Puente aditivo hacia el modelo canonico D01 (lead_canon). Nunca debe
            # tumbar la pasada de Fase 0: cualquier fallo se registra en res.errores.
            try:
                from departments.comercial.cubo_serie_d import PipelineCanonico
                from departments.comercial.puente_canonico import (
                    construir_lead_canonico, dar_alta_canonico,
                )
                pipeline_canon = PipelineCanonico(self.lead_store.k, self.lead_store.company,
                                                  bitacora=None)
                lead_canon = construir_lead_canonico(cand, decision, anillo_res, ts=ts_pasada)
                dar_alta_canonico(pipeline_canon, lead_canon)
            except Exception as e:
                res.errores.append(f"puente a lead_canon fallo (no bloquea Fase 0): {e}")

            self.lead_store.transicionar(
                lead_id, EstadoLead.CUALIFICADO,
                razon=f"ICP: {decision.razones[0]}",
                detalle={"categoria": decision.categoria, "prioridad": decision.prioridad},
            )
            res.cualificados_nuevos += 1
            res.detalle_por_categoria[decision.categoria] = (
                res.detalle_por_categoria.get(decision.categoria, 0) + 1
            )

            if self.bus is not None:
                self.bus.publish(Event(
                    EventType.DEPT_TASK_COMPLETED, source="researcher",
                    payload={"lead": lead_id, "categoria": decision.categoria,
                             "anillo": anillo_res.anillo},
                    company=self.lead_store.company,
                ))

        if verbose:
            print(f"[Researcher] únicos={res.candidatos_unicos} "
                  f"descarte_icp={res.descartes_icp} ({res.tasa_descarte_icp}%) "
                  f"descarte_anillo={res.descartes_anillo} "
                  f"cualificados_nuevos={res.cualificados_nuevos} "
                  f"ya_existentes={res.leads_ya_existentes}")
        return res

    # ── Helpers ────────────────────────────────────────────────────────────
    def _registrar_descarte(self, cand: CandidatoCrudo, categoria_target: str,
                            clase: str, razon: str) -> None:
        """I-2 (D11 E1): los descartes se persisten con sus insumos. Un pipeline que
        solo guarda a los aceptados no puede medir sus falsos negativos ni rescatar
        ambiguos después. Nodo tipo 'descarte' en el knowledge (mismo almacén, otra
        colección); clave = slug del nombre (idempotente por pasada)."""
        from datetime import datetime, timezone
        try:
            self.lead_store.k.add(self.lead_store.company, "descarte", _slug(cand.nombre), {
                "nombre": cand.nombre,
                "clase": clase,                      # 'icp' | 'anillo'
                "razon": razon,
                "categoria_target": categoria_target,
                # Insumos completos de la decisión (lección I-1 aplicada también aquí):
                "place_types": list(cand.place_types or []),
                "descripcion": cand.descripcion,
                "tipo_detectado": cand.tipo_principal,
                "fuente": cand.fuente,
                "id_externo": cand.id_externo,
                "ubicacion": dict(cand.ubicacion or {}),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:                        # el registro de descartes jamás
            print(f"[Researcher] aviso: descarte de {cand.nombre} no registrado: {e}",
                  file=sys.stderr)                    # tumba la pasada (observabilidad)

    def _buscar_una(self, c: CampaniaBusqueda, max_resultados: int) -> list[CandidatoCrudo]:
        out: list[CandidatoCrudo] = []
        for fuente in self.fuentes:
            out.extend(fuente.buscar(c.query, centro=c.centro,
                                     radio_m=c.radio_m, max_resultados=max_resultados))
        return out


def _slug(texto: str) -> str:
    """Slug estable para usar como ID del lead. Sin acentos, minúsculas, snake_case."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s-]", "", t)
    return re.sub(r"[\s_]+", "_", t).strip("_")[:64]
