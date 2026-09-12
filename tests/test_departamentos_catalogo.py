"""Tests de los departamentos 3-10 del catálogo y del catálogo de cubos.

Cubre Marketing (§3.3), Customer Success (§3.4), Inteligencia (§3.8), RRHH (§3.9), la base
CuboDepartamento (§2.1/§7.1) y el catálogo + orquestador (§3.11/§7.1). Sin red: se ejercitan
las acciones deterministas y el contrato de eventos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import Event, EventType
from core.knowledge import get_knowledge
from core.resiliencia.arranque import Orquestador, verificar_combinaciones
from departments.base import Task
from departments import catalogo


# ── Base CuboDepartamento + contrato ──────────────────────────────────────────
def test_cubo_emite_cube_started_y_declara_contrato():
    bus = InMemoryBus()
    started = []
    bus.subscribe(started.append, types=[EventType.CUBE_STARTED])
    from departments.marketing.agente import MarketingDepartment
    MarketingDepartment(bus, "laboratorio")
    assert started and started[0].payload["cube"] == "marketing"
    assert "marketing.lead_inbound" in started[0].payload["produce"]


def test_producir_solo_tipos_declarados():
    bus = InMemoryBus()
    from departments.marketing.agente import MarketingDepartment
    m = MarketingDepartment(bus, "laboratorio")
    import pytest
    with pytest.raises(AssertionError):
        m._producir(EventType.CS_CHURN_ALERT, {})   # no está en su contrato produce


# ── §3.3 Marketing ────────────────────────────────────────────────────────────
def test_marketing_plan_publicar_inbound():
    bus = InMemoryBus()
    prod = []
    bus.subscribe(prod.append, types=[EventType.MARKETING_LEAD_INBOUND,
                                      EventType.MARKETING_CONTENT_PUBLISHED])
    from departments.marketing.agente import MarketingDepartment
    m = MarketingDepartment(bus, "laboratorio")
    # Posicionamiento llega del Brand por evento.
    bus.publish(Event(EventType.BRAND_REVIEW_COMPLETED, source="brand",
                      payload={"aprobado": True, "asunto": "Repostería centenaria"}, company="laboratorio"))
    m._objeciones = ["es caro"]
    plan = m.plan()
    assert any("es caro" in i["tema"] for i in plan)
    p = m.publicar_pieza(tema="Un siglo de obrador", canal="blog", cuerpo="historia artesanal")
    m.captar_inbound(nombre="Hotel La Parra", canal="blog", origen_pieza=p["id"])
    tipos = [e.type for e in prod]
    assert EventType.MARKETING_CONTENT_PUBLISHED in tipos
    assert EventType.MARKETING_LEAD_INBOUND in tipos


# ── §3.4 Customer Success ──────────────────────────────────────────────────────
def test_cs_churn_renovacion_upsell():
    bus = InMemoryBus()
    alerts = []
    bus.subscribe(alerts.append, types=[EventType.CS_CHURN_ALERT, EventType.CS_RENEWAL,
                                        EventType.CS_UPSELL_OPPORTUNITY])
    from departments.customer_success.agente import CustomerSuccessDepartment
    from departments.customer_success import herramientas as h
    k = get_knowledge()
    cs = CustomerSuccessDepartment(bus, "laboratorio", knowledge=k)
    # Cliente sano con NPS alto → upsell.
    feliz = h.alta_cliente(k, "laboratorio", nombre="Cliente B", valor_mensual=300)
    h.registrar_contacto(k, "laboratorio", feliz["id"], nps=10)
    # Cliente en riesgo: NPS detractor.
    triste = h.alta_cliente(k, "laboratorio", nombre="Bar Pepe", valor_mensual=100)
    h.registrar_contacto(k, "laboratorio", triste["id"], nps=3)

    riesgo = cs.barrido_churn()
    assert any(r["nombre"] == "Bar Pepe" for r in riesgo)
    ups = cs.barrido_upsell()
    assert any(o["nombre"] == "Cliente B" for o in ups)
    cs.renovar(feliz["id"])
    tipos = [e.type for e in alerts]
    assert EventType.CS_CHURN_ALERT in tipos
    assert EventType.CS_UPSELL_OPPORTUNITY in tipos
    assert EventType.CS_RENEWAL in tipos


# ── §3.8 Inteligencia de Mercado ───────────────────────────────────────────────
def test_inteligencia_competidor_y_briefing():
    bus = InMemoryBus()
    eventos = []
    bus.subscribe(eventos.append, types=[EventType.INTEL_COMPETITOR_ALERT, EventType.INTEL_BRIEFING])
    from departments.inteligencia.agente import InteligenciaDepartment
    intel = InteligenciaDepartment(bus, "laboratorio", knowledge=get_knowledge())
    # Señal de competidor relevante → alerta.
    intel.observar(tipo="competidor", tema="Rival baja precios en HORECA", relevancia=5,
                   fuente="prensa")
    # Señal poco relevante → no alerta.
    intel.observar(tipo="competidor", tema="Competidor cambia de logo", relevancia=2)
    intel.briefing()
    tipos = [e.type for e in eventos]
    assert EventType.INTEL_COMPETITOR_ALERT in tipos
    assert tipos.count(EventType.INTEL_COMPETITOR_ALERT) == 1   # solo la relevante
    assert EventType.INTEL_BRIEFING in tipos


def test_inteligencia_consume_senal_de_cs():
    bus = InMemoryBus()
    from departments.inteligencia.agente import InteligenciaDepartment
    from departments.inteligencia import herramientas as h
    k = get_knowledge()
    InteligenciaDepartment(bus, "laboratorio", knowledge=k)
    bus.publish(Event(EventType.CS_CHURN_ALERT, source="customer_success",
                      payload={"nombre": "Bar Pepe", "motivos": ["NPS 3"]}, company="laboratorio"))
    assert len(h.senales(k, "laboratorio", tipo="conversacion")) == 1


# ── §3.9 RRHH (introspección del sistema) ──────────────────────────────────────
def test_rrhh_mapa_capacidades_por_introspeccion():
    bus = InMemoryBus()
    from departments.rrhh.agente import RRHHDepartment
    rrhh = RRHHDepartment(bus, "laboratorio")          # se suscribe a cube.started
    # Otros cubos arrancan y anuncian su presencia.
    for cube in ("comercial", "brand", "marketing", "customer_success"):
        bus.publish(Event(EventType.CUBE_STARTED, source=cube,
                          payload={"cube": cube}, company="laboratorio"))
    mapa = rrhh.mapa()
    assert "comercial" in mapa["presentes"] and "rrhh" in mapa["presentes"]
    assert "finanzas" in mapa["faltantes"]
    assert 0 < mapa["cobertura"] < 1


def test_rrhh_detecta_bajo_rendimiento():
    bus = InMemoryBus()
    alerts = []
    bus.subscribe(alerts.append, types=[EventType.HR_PERFORMANCE_ALERT])
    from departments.rrhh.agente import RRHHDepartment
    rrhh = RRHHDepartment(bus, "laboratorio")
    # 6 ejecuciones de 'legal', 4 fallan (>30%).
    for _ in range(2):
        bus.publish(Event(EventType.DEPT_TASK_COMPLETED, source="legal", company="laboratorio"))
    for _ in range(4):
        bus.publish(Event(EventType.DEPT_TASK_FAILED, source="legal", company="laboratorio"))
    a = rrhh.rendimiento()
    assert any(x["departamento"] == "legal" for x in a)
    assert alerts


# ── Catálogo + Orquestador (§3.11, §7.1) ───────────────────────────────────────
def test_catalogo_tiene_diez_cubos_en_orden():
    info = catalogo.info()
    assert len(info) == 10
    assert [c["orden"] for c in info] == list(range(1, 11))
    assert catalogo.CUADRADO_MINIMO == ("comercial", "brand", "marketing", "customer_success")


def test_orquestador_arranca_cubos_autocontenidos():
    # Arranca cubos sin dependencias externas de credenciales (Comercial construye fuentes
    # de Google y necesita GOOGLE_MAPS_API_KEY; queda fuera del arranque offline).
    bus = InMemoryBus()
    started = []
    bus.subscribe(started.append, types=[EventType.CUBE_STARTED])
    orq = Orquestador(bus)
    combo = ["brand", "marketing", "customer_success", "rrhh", "opengravity"]
    catalogo.registrar_en_orquestador(orq, solo=combo)
    orq.arrancar("laboratorio", combo)
    nombres = {e.payload["cube"] for e in started}
    assert set(combo) <= nombres


def test_matriz_combinaciones_de_los_cubos_nuevos():
    # Los cuatro cubos nuevos: toda combinación no vacía arranca sin error (§7.1).
    fabricas = {n: catalogo.FABRICAS[n]
                for n in ("marketing", "customer_success", "inteligencia_mercado", "rrhh")}
    fallidas = verificar_combinaciones(fabricas, lambda: InMemoryBus())
    assert fallidas == []
