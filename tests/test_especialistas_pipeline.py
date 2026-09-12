"""Tests de especialistas y pipelines (Bloque 3). _chat mockeado; sin LLM ni red real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.knowledge import InMemoryKnowledge
from core.task_classes import ClaseTarea, get_model_for_class
from departments.base import Especialista, PipelineDepartamento, Task

# Mock global de _chat: ningún test llama a un LLM real.
Especialista._chat = lambda self, messages, system, max_tokens=1024, company="default": " ".join(["palabra"] * 60)

import departments.prospeccion as P
from departments.prospeccion import Buscador, ExtractorDeContacto, ClasificadorDeFit, GeneradorDeFicha
from departments.redaccion import AnalistaDePerfil, RedactorDeCuerpo, GeneradorDeAsunto, ValidadorDeFormato
from departments.finanzas.especialistas import AgregadorDeDatos, CalculadorDeMetricas, InterpreteDeTendencias
from departments.qa.especialistas import ValidadorDeEstructura, DetectorDeContradicciones, CalificadorDeCalidad
from departments.ops.especialistas import ConsultorDeCapacidad, AlertadorDeStock
from departments.legal.especialistas import ExtractorDeClausulas, ClasificadorDeRiesgo, SintetizadorDeInforme


class _FakeDDGS:
    def text(self, q, max_results=6):
        return []


def test_smoke_finanzas():
    bus, k = InMemoryBus(), InMemoryKnowledge()
    pipe = PipelineDepartamento([AgregadorDeDatos(bus, k), CalculadorDeMetricas(bus, k),
                                 InterpreteDeTendencias(bus, k)], "finanzas")
    r = pipe.ejecutar(Task(intent="cuánto gastado", company="c", payload={"company": "c"}))
    assert r.ok and "interpretacion" in r.data and "metricas" in r.data


def test_smoke_qa():
    bus = InMemoryBus()
    pipe = PipelineDepartamento([ValidadorDeEstructura(bus), DetectorDeContradicciones(bus),
                                 CalificadorDeCalidad(bus)], "qa")
    r = pipe.ejecutar(Task(intent="valida", company="c",
                           payload={"artefacto": "texto artesano local", "contexto_empresa": "obrador artesano"}))
    assert r.ok and "puntuacion" in r.data


def test_smoke_ops():
    bus, k = InMemoryBus(), InMemoryKnowledge()
    pipe = PipelineDepartamento([ConsultorDeCapacidad(bus, k), AlertadorDeStock(bus, k)], "ops")
    r = pipe.ejecutar(Task(intent="capacidad", company="c", payload={"company": "c"}))
    assert r.ok and "alertas" in r.data and "ocupada_pct" in r.data


def test_smoke_legal():
    bus = InMemoryBus()
    pipe = PipelineDepartamento([ExtractorDeClausulas(bus), ClasificadorDeRiesgo(bus),
                                 SintetizadorDeInforme(bus)], "legal")
    r = pipe.ejecutar(Task(intent="analiza", company="c",
                           payload={"texto_contrato": "El proveedor asume responsabilidad ilimitada."}))
    assert r.ok and "informe_md" in r.data and "evaluaciones" in r.data


def test_smoke_redaccion():
    bus = InMemoryBus()
    pipe = PipelineDepartamento([AnalistaDePerfil(bus), RedactorDeCuerpo(bus),
                                 GeneradorDeAsunto(bus), ValidadorDeFormato(bus)], "redaccion")
    r = pipe.ejecutar(Task(intent="redacta", company="c",
                           payload={"ficha_lead": "lead", "contexto_empresa": "empresa"}))
    assert r.ok and "cuerpo" in r.data and "asunto" in r.data and "problemas" in r.data


def test_smoke_prospeccion():
    P.DDGS = _FakeDDGS                       # sin red
    bus = InMemoryBus()
    pipe = PipelineDepartamento([Buscador(bus), ExtractorDeContacto(bus),
                                 ClasificadorDeFit(bus), GeneradorDeFicha(bus)], "prospeccion")
    r = pipe.ejecutar(Task(intent="busca leads", company="c", payload={"perfil": "tiendas gourmet"}))
    assert r.ok and "resultados_raw" in r.data and "fichas_md" in r.data


# ── verificación de clases / routing ──────────────────────────────────────────
def test_clasificador_fit_usa_modelo_barato():
    assert ClasificadorDeFit.clase is ClaseTarea.CLASIFICACION


def test_razonamiento_usa_modelo_pesado():
    assert ClasificadorDeRiesgo.clase is ClaseTarea.RAZONAMIENTO


def test_funcion_no_llama_llm():
    P.DDGS = _FakeDDGS
    llamado = {"v": False}
    b = Buscador(InMemoryBus())
    b._chat = lambda *a, **k: llamado.__setitem__("v", True) or ""
    assert Buscador.clase is ClaseTarea.FUNCION
    b.ejecutar({"perfil": "x"}, {"intent": "x", "company": "c"})
    assert llamado["v"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1; print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
