"""Director Comercial Sintético (§2.2 del v0.2).

Orquesta una pasada completa de Fase 0: instancia ICP + Anillos + Fuentes + LeadStore +
Researcher + Enrichment, ejecuta la pasada, calcula métricas y genera el reporte
ejecutivo. Es la unidad operativa de Fase 0 que el CLI invoca.

En Fase 1 incorporará la orquestación del SDR + Brand Guardian. En Fase 2, del Account
Executive + Account Manager + Sales Ops. Esta clase es el punto único de orquestación.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.knowledge import KnowledgeStore, get_knowledge
from departments.comercial.anillos import ClasificadorAnillos
from departments.comercial.distancia.base import DistanceProvider
from departments.comercial.enrichment import Enrichment, ResultadoEnrichment
from departments.comercial.fuentes.base import FuenteLeads
from departments.comercial.fuentes.google_places import GooglePlacesFuente
from departments.comercial.icp import FiltroICP
from departments.comercial.lifecycle import LeadStore
from departments.comercial.metricas import CuadroMetricas, calcular
from departments.comercial.reporting import generar_reporte
from departments.comercial.researcher import Researcher, ResultadoPasada


@dataclass
class ResultadoFase0:
    researcher: ResultadoPasada
    enrichment: ResultadoEnrichment
    cuadro: CuadroMetricas
    reporte: Path

    @property
    def gates_superados(self) -> bool:
        return bool(self.cuadro.gates_fase0.get("__superados__"))


class DirectorComercial:
    """Orquestador de Fase 0. Componibilidad: las dependencias son inyectables para tests
    (puedo pasar `fuentes=[FakeFuente()]`, `distance_provider=HaversineProvider()`, etc.).

    Defaults: Google Places + Google Routes + InMemoryKnowledge si no se pasa otra.
    """

    def __init__(self, *, empresa: str = "laboratorio",
                 knowledge: KnowledgeStore | None = None,
                 bus=None,
                 distance_provider: DistanceProvider | None = None,
                 fuentes: list[FuenteLeads] | None = None,
                 researcher_workers: int = 4,
                 enrichment_workers: int = 4) -> None:
        self.empresa = empresa
        self.knowledge = knowledge or get_knowledge()
        self.bus = bus

        self.icp = FiltroICP(empresa)
        self.lead_store = LeadStore(self.knowledge, empresa)

        if distance_provider is None:
            from departments.comercial.distancia.google_routes import get_distance_provider
            distance_provider = get_distance_provider()
        origen = self.icp.origen
        self.anillos = ClasificadorAnillos(
            distance_provider, origen["lat"], origen["lon"], self.icp.max_anillo,
        )

        if fuentes is None:
            fuentes = [GooglePlacesFuente()]
        self.fuentes = fuentes

        self.researcher = Researcher(
            icp=self.icp, anillos=self.anillos, fuentes=self.fuentes,
            lead_store=self.lead_store, bus=bus, max_workers=researcher_workers,
        )
        self.enrichment = Enrichment(
            lead_store=self.lead_store, bus=bus, max_workers=enrichment_workers,
        )

    def ejecutar_fase0(self, *, prioridades: tuple[str, ...] = ("ALTA", "MEDIA"),
                       max_por_query: int = 15, verbose: bool = True,
                       salida_reporte: Path | None = None) -> ResultadoFase0:
        if verbose:
            print(f"\n[DirectorComercial] empresa={self.empresa} "
                  f"anillo_max={self.icp.max_anillo} "
                  f"fuentes={[f.nombre for f in self.fuentes]} "
                  f"distancia={self.anillos.distancia.nombre}\n")

        res_r = self.researcher.ejecutar_pasada(prioridades=prioridades,
                                                max_por_query=max_por_query,
                                                verbose=verbose)
        res_e = self.enrichment.procesar_todos(verbose=verbose)
        cuadro = calcular(self.lead_store, ultima_pasada=res_r, ultimo_enrichment=res_e)
        reporte = generar_reporte(lead_store=self.lead_store, cuadro=cuadro, salida=salida_reporte)

        if verbose:
            print(f"\n[DirectorComercial] reporte: {reporte}")
            print(f"[DirectorComercial] gates Fase 0 superados: "
                  f"{cuadro.gates_fase0.get('__superados__')}")

        return ResultadoFase0(researcher=res_r, enrichment=res_e, cuadro=cuadro, reporte=reporte)
