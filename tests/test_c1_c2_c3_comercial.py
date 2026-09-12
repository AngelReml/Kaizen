"""Cubo Comercial serie D — C1 (pipeline canonico + Atribuidor), C2 (10 controles),
C3 (P8). Incluye los tests con nombre exigidos por D01 §7 y un E2E dry-run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.comercial import cubo_serie_d as C

LEAD_OK = {"id": "l1", "nombre_ref": "lead_sintetico_1",
           "fuentes": [{"url": "https://negocio.example", "fecha": "2026-07-01"}],
           "contacto": {"publicado_por_el_negocio": True}}
CUERPO_LEGAL = ("Buenos dias, le escribe el equipo comercial. Le proponemos surtido semanal. "
                "Si no desea recibir mas mensajes, responda BAJA. "
                "Puede ejercer sus derechos de acceso segun RGPD.")


@pytest.fixture()
def cubo():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    p = C.PipelineCanonico(k, "t1", bitacora=b, mandato={"max_llamadas_dia": 2})
    a = C.Atribuidor(k, "t1", bitacora=b)
    return p, a, k, b


# ── C2: los tests con nombre de D01 §7 ──

def test_lead_sin_fuente_no_entra(cubo):
    p, _, _, _ = cubo
    with pytest.raises(C.GateLegal):
        p.alta_lead({"id": "lx", "fuentes": []})


def test_contacto_no_publicado_rechazado(cubo):
    p, _, _, _ = cubo
    with pytest.raises(C.GateLegal):
        p.alta_lead({"id": "lx", "fuentes": [{"url": "https://x.example", "fecha": "2026-07-01"}],
                     "contacto": {"publicado_por_el_negocio": False}})


def test_envio_sin_bloques_imposible(cubo):
    p, _, _, _ = cubo
    p.alta_lead(LEAD_OK)
    with pytest.raises(C.GateLegal, match="S3"):
        p.enviar_email("l1", "hola, compra pan", secuencia="INICIAL", aprobacion_ref="ap1")


def test_optout_absorbente(cubo):
    p, _, _, _ = cubo
    p.alta_lead(LEAD_OK)
    p.opt_out("l1", evidencia_ref="reply_1")
    assert p.lead("l1")["estado"] == "EXCLUIDO"
    with pytest.raises(C.TransicionRechazada):
        p.transicionar("l1", "COLD", disparador="OPERADOR")      # absorbente: sin salida
    with pytest.raises(C.GateLegal, match="V2"):
        p.enviar_email("l1", CUERPO_LEGAL, secuencia="RECORDATORIO", aprobacion_ref="ap")


def test_lista_exclusion_gate(cubo):
    p, _, k, _ = cubo
    p.alta_lead(LEAD_OK)
    k.add("t1", "lead_pii", "l1", {"email": "optout@sintetico.example"})
    p.opt_out("l1")
    p.alta_lead({**LEAD_OK, "id": "l2"})
    assert p.en_lista_exclusion("optout@sintetico.example") is True
    with pytest.raises(C.GateLegal, match="S4"):
        p.enviar_email("l2", CUERPO_LEGAL, secuencia="INICIAL", aprobacion_ref="ap",
                       email_destino="optout@sintetico.example")


def test_tercer_contacto_inexistente(cubo):
    p, _, _, _ = cubo
    p.alta_lead(LEAD_OK)
    p.enviar_email("l1", CUERPO_LEGAL, secuencia="INICIAL", aprobacion_ref="ap1")
    p.enviar_email("l1", CUERPO_LEGAL, secuencia="RECORDATORIO", aprobacion_ref="ap2")
    with pytest.raises(C.GateLegal, match="S5"):
        p.enviar_email("l1", CUERPO_LEGAL, secuencia="RECORDATORIO", aprobacion_ref="ap3")


def test_llamada_sin_robinson_imposible(cubo):
    p, _, _, _ = cubo
    p.alta_lead(LEAD_OK)
    with pytest.raises(C.GateLegal, match="S6"):
        p.llamada_ia("l1", robinson_consultado=False, disclosure_test_verde=True)


def test_voz_sin_disclosure_no_abre(cubo):
    p, _, _, _ = cubo
    p.alta_lead(LEAD_OK)
    with pytest.raises(C.GateLegal, match="art.50"):
        p.llamada_ia("l1", robinson_consultado=True, disclosure_test_verde=False)
    with pytest.raises(C.GateLegal, match="cuota"):
        p.llamada_ia("l1", robinson_consultado=True, disclosure_test_verde=True,
                     cuota_dia_usada=2)


def test_registro_externo_no_autoatribuye(cubo):
    p, a, _, _ = cubo
    p.alta_lead(LEAD_OK)
    n = a.atribuir(pedido_id="ped9", lead_id="l1", via="REGISTRO_EXTERNO")
    assert n["estado"] == "PENDIENTE_VALIDACION"
    with pytest.raises(PermissionError):
        a.validar_externo("ped9", por="sistema")                 # humano SIEMPRE
    assert a.validar_externo("ped9", por="operador")["estado"] == "ATRIBUIDO"
    with pytest.raises(ValueError):
        a.atribuir(pedido_id="ped_falso", lead_id="lead_inexistente", via="REGISTRO_EXTERNO")


# ── C1: invariantes y atribucion DIRECTA ──

def test_transicion_fuera_de_grafo_rechazada_y_registrada(cubo):
    p, _, k, _ = cubo
    p.alta_lead(LEAD_OK)
    with pytest.raises(C.TransicionRechazada):
        p.transicionar("l1", "CUSTOMER", disparador="SISTEMA")   # V4/V5
    rechazos = [e for e in k.all("t1", "evento").values()
                if e["tipo"] == "comercial.pipeline.transicion"
                and e["payload"]["veredicto"] == "RECHAZADA"]
    assert len(rechazos) == 1                                     # V5: registrada


def test_mapeo_equivalencia_estados_reales_sin_perdida():
    reales = ["cold", "queued", "contacting", "no_answer", "contacted", "engaged",
              "sample_requested", "sample_sent", "trial", "customer", "lost", "do_not_call",
              "identificado", "cualificado", "enriquecido", "en_contacto",
              "compromiso_reciproco", "muestra_enviada", "cliente_activo", "en_riesgo", "perdido"]
    for e in reales:
        assert C.MAPEO_REAL_A_CANON[e] in C.ESTADOS               # ningun lead pierde su pasado


def test_e2e_dry_run_hasta_pedido_con_cadena(cubo):
    p, a, k, b = cubo
    lead = p.alta_lead(LEAD_OK)
    corr = lead["correlacion_id"]
    p.enviar_email("l1", CUERPO_LEGAL, secuencia="INICIAL", aprobacion_ref="ap1")
    p.transicionar("l1", "CONVERSACION", disparador="EVIDENCIA", causa_ref="reply_pos")
    p.transicionar("l1", "COMPROMETIDO", disparador="OPERADOR", causa_ref="compromiso_1")
    n = a.atribuir(pedido_id="ped1", lead_id="l1", via="DIRECTA", correlacion_id=corr)
    assert n["estado"] == "ATRIBUIDO" and len(n["cadena"]) >= 3   # cadena causal real
    p.transicionar("l1", "PEDIDO", disparador="EVIDENCIA", causa_ref="ped1")
    p.transicionar("l1", "CUSTOMER", disparador="OPERADOR", causa_ref="cobro_manual")
    assert p.lead("l1")["estado"] == "CUSTOMER"
    with pytest.raises(ValueError):
        a.atribuir(pedido_id="ped1", lead_id="l1", via="DIRECTA", correlacion_id=corr)
    assert b.verificar()["integra"] is True


def test_atribucion_directa_sin_cadena_no_existe(cubo):
    p, a, _, _ = cubo
    p.alta_lead(LEAD_OK)
    with pytest.raises(ValueError, match="cadena"):
        a.atribuir(pedido_id="pedx", lead_id="l1", via="DIRECTA",
                   correlacion_id="corr_inexistente")


# ── C3: P8 ──

def test_p8_asiento_ranking_y_frontera_disociada(cubo):
    p, _, k, b = cubo
    for res in ("PEDIDO", "POSITIVA", "SIN_RESPUESTA"):
        C.asiento_p8(k, "t1", bitacora=b, segmento="gourmet", argumento_id="arg_cercania",
                     canal="EMAIL", secuencia="INICIAL", resultado=res, cliente_ref="l1")
    C.asiento_p8(k, "t1", bitacora=b, segmento="gourmet", argumento_id="arg_precio",
                 canal="EMAIL", secuencia="INICIAL", resultado="NEGATIVA", cliente_ref="l2")
    r = C.ranking_argumentos(k, "t1", "gourmet")
    assert r[0]["argumento_id"] == "arg_cercania" and r[0]["usos"] == 3
    agregado = C.p8_agregado_disociado(k, "t1")
    assert all("cliente_ref" not in a and "id" not in a for a in agregado)
    assert len(agregado) == 4


# ── G4: puente real hacia Customer Success al cerrar CUSTOMER ──

LEAD_VENTA = {"id": "lx", "nombre": "Panaderia Laboratorio",
              "fuentes": [{"url": "https://negocio.example", "fecha": "2026-07-01"}],
              "contacto": {"publicado_por_el_negocio": True}}


def _hasta_customer(p, k, tenant, *, causa_customer="ped1"):
    """Recorre el pipeline canonico legitimo COLD→…→CUSTOMER (sin atajos: cada
    transicion pasa por transicionar(), igual que en produccion)."""
    p.alta_lead(LEAD_VENTA)
    p.transicionar("lx", "CONTACTADO", disparador="OPERADOR")
    p.transicionar("lx", "CONVERSACION", disparador="OPERADOR")
    p.transicionar("lx", "COMPROMETIDO", disparador="OPERADOR", causa_ref="compromiso_1")
    k.add(tenant, "pedido_atribuido", "ped1", {"pedido_id": "ped1", "lead_ref": "lx",
          "via": "DIRECTA", "estado": "ATRIBUIDO", "importe_bruto": 250.0})
    p.transicionar("lx", "PEDIDO", disparador="EVIDENCIA", causa_ref="ped1")
    return p.transicionar("lx", "CUSTOMER", disparador="OPERADOR", causa_ref=causa_customer)


def test_transicion_a_customer_sin_bus_no_emite_ni_rompe():
    """Sin bus inyectado (el caso de HOY en panel_mando/herramientas/comercial.py):
    la transicion se aplica igual, sin excepcion ni emision — comportamiento previo
    intacto para quien no pasa bus."""
    k = InMemoryKnowledge()
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    p = C.PipelineCanonico(k, "laboratorio", bitacora=b)          # bus=None por defecto
    lead = _hasta_customer(p, k, "laboratorio")
    assert lead["estado"] == "CUSTOMER"


def test_transicion_a_customer_emite_dept_task_completed_source_comercial():
    """El emisor real que faltaba (AUDITORIA G4): al cerrar CUSTOMER, PipelineCanonico
    publica DEPT_TASK_COMPLETED con source='comercial' y payload cliente_nuevo, tal
    cual lo espera CustomerSuccessDepartment._on_comercial."""
    from core.bus import InMemoryBus
    from core.events import EventType

    k = InMemoryKnowledge()
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    bus = InMemoryBus()
    recibidos = []
    bus.subscribe(recibidos.append, types=[EventType.DEPT_TASK_COMPLETED])
    p = C.PipelineCanonico(k, "laboratorio", bitacora=b, bus=bus)

    lead = _hasta_customer(p, k, "laboratorio")

    assert lead["estado"] == "CUSTOMER"
    assert len(recibidos) == 1
    ev = recibidos[0]
    assert ev.source == "comercial" and ev.company == "laboratorio"
    assert ev.payload["cliente_nuevo"] == {"nombre": "Panaderia Laboratorio",
                                           "valor_mensual": 250.0}


def test_transicion_a_customer_bus_real_dispara_alta_cliente_en_cs():
    """Flujo completo emitir→escuchar: el MISMO bus conectado a un
    CustomerSuccessDepartment real crea la ficha en cliente_cs sin que nadie
    mas que PipelineCanonico.transicionar dispare nada (CustomerSuccessDepartment
    NO se toca, solo se conecta al bus real que ahora existe)."""
    from core.bus import InMemoryBus
    from departments.customer_success.agente import CustomerSuccessDepartment

    k = InMemoryKnowledge()
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    bus = InMemoryBus()
    CustomerSuccessDepartment(bus, "laboratorio", knowledge=k)     # se autosuscribe
    p = C.PipelineCanonico(k, "laboratorio", bitacora=b, bus=bus)

    _hasta_customer(p, k, "laboratorio")

    clientes = list(k.all("laboratorio", "cliente_cs").values())
    assert len(clientes) == 1
    assert clientes[0]["nombre"] == "Panaderia Laboratorio"
    assert clientes[0]["valor_mensual"] == 250.0


def test_transicion_a_customer_bus_roto_no_rompe_la_transicion():
    """Degradacion exigida: si emitir falla (bus.publish lanza), la transicion YA
    aplicada no se deshace ni se propaga la excepcion."""
    class BusRoto:
        def publish(self, event):
            raise RuntimeError("bus no disponible")

    k = InMemoryKnowledge()
    b = Bitacora(k, "laboratorio", fecha_alta="2026-07-10")
    p = C.PipelineCanonico(k, "laboratorio", bitacora=b, bus=BusRoto())

    lead = _hasta_customer(p, k, "laboratorio")

    assert lead["estado"] == "CUSTOMER"
    assert p.lead("lx")["estado"] == "CUSTOMER"        # persistido pese al fallo de emision
