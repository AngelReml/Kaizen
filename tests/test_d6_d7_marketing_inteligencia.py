"""Cubos Marketing (D06) e Inteligencia (D07).
D06: brand bloqueante (13.2/13.8), kill-switch presupuesto (R-10, 13.4), ROI via lead
(R-15, 13.5), aislamiento (13.1). D07: umbral versionado (13.5), clasificacion (13.3),
disociacion (13.8), correlacion honesta (13.6), FP con n pequeño (R-17), no-ejecuta."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora, Sobre
from core import verificacion as V
from departments.marketing.cubo_serie_d import CuboMarketing, GateMarketing
from departments.inteligencia.cubo_serie_d import CuboInteligencia


@pytest.fixture()
def mkt():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    V.registrar_paquete("brand", lambda t, tc, c: {"veredicto": "NO_APTO" if "industrial" in c.lower()
                                                   else "APTO",
                                                   "razones": ["palabra prohibida"] if "industrial" in c.lower() else [],
                                                   "version": "d-v1"})
    svc = V.ServicioVerificacion(k)
    yield CuboMarketing(k, "t1", bitacora=b, servicio_verificacion=svc), k, b
    V.quitar_paquete("brand")


def test_contenido_sin_brand_imposible_y_rechazo_bloquea(mkt):
    m, _, _ = mkt
    c = m.crear_campana(nombre="otono", segmento="gourmet", canales=["dry"],
                        presupuesto_eur=100, duracion_dias=14)
    m.aprobar_campana(c["id"], por="operador")
    malo = m.crear_contenido(c["id"], tipo="COPY", texto="pan industrial barato")
    with pytest.raises(GateMarketing, match="VALIDADO_POR_BRAND"):
        m.lanzar(c["id"], malo["id"])                          # sin validar: imposible
    assert m.validar_con_brand(malo["id"])["estado"] == "RECHAZADO"
    with pytest.raises(GateMarketing):
        m.lanzar(c["id"], malo["id"])                          # rechazado: imposible
    bueno = m.crear_contenido(c["id"], tipo="COPY", texto="pan de obrador con horno de leña")
    assert m.validar_con_brand(bueno["id"])["estado"] == "VALIDADO_POR_BRAND"
    assert m.lanzar(c["id"], bueno["id"])["dry_run"] is True


def test_kill_switch_90pct_pausa_r10(mkt):
    m, _, _ = mkt
    c = m.crear_campana(nombre="x", segmento="s", canales=["dry"],
                        presupuesto_eur=100, duracion_dias=7)
    m.aprobar_campana(c["id"], por="operador")
    cont = m.crear_contenido(c["id"], tipo="COPY", texto="texto valido")
    m.validar_con_brand(cont["id"])
    m.lanzar(c["id"], cont["id"])
    m.reconciliar_gasto(c["id"], 89.0)
    assert m.k.get("t1", "campana", c["id"])["estado"] == "ACTIVA"
    m.reconciliar_gasto(c["id"], 1.5)                          # 90.5 ≥ 90%
    assert m.k.get("t1", "campana", c["id"])["estado"] == "PAUSADA"
    cont2 = m.crear_contenido(c["id"], tipo="COPY", texto="otro valido")
    m.validar_con_brand(cont2["id"])
    with pytest.raises(GateMarketing, match="kill-switch"):
        m.lanzar(c["id"], cont2["id"])


def test_roi_via_lead_r15(mkt):
    m, k, _ = mkt
    c = m.crear_campana(nombre="x", segmento="s", canales=["dry"],
                        presupuesto_eur=50, duracion_dias=7)
    k.add("t1", "lead_canon", "l1", {"id": "l1", "fuentes":
          [{"tipo": "CAMPANA", "ref": c["id"], "fecha": "2026-07-01"}]})
    k.add("t1", "lead_canon", "l2", {"id": "l2", "fuentes":
          [{"tipo": "WEB", "url": "https://x.example", "fecha": "2026-07-01"}]})
    k.add("t1", "pedido_atribuido", "p1", {"pedido_id": "p1", "lead_ref": "l1",
                                           "estado": "ATRIBUIDO", "via": "DIRECTA"})
    r = m.roi(c["id"])
    assert r["leads_generados"] == 1 and r["conversiones"] == 1  # l2 no cuenta


def test_intel_umbral_versionado_y_clasificacion():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    i = CuboInteligencia(k, "t1", bitacora=b)
    with pytest.raises(PermissionError):
        i.definir_umbral("conversion", 0.08, 0.12, por="subagente")
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    u2 = i.definir_umbral("conversion", 0.06, 0.12, por="operador")
    assert u2["version"] == 2 and len(u2["historial"]) == 2      # 13.5: versionado
    assert i.detectar("conversion", 0.10) is None                # dentro de rango
    assert i.detectar("conversion", 0.055)["severidad"] == "INFO"
    assert i.detectar("churn", 0.5) is None                      # sin umbral: sin ruido
    a = i.detectar("conversion", 0.30)                           # exceso enorme
    assert a["severidad"] == "CRITICA"
    assert b.verificar()["integra"] is True


def test_intel_disociacion_correlacion_y_fp_r17():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    i = CuboInteligencia(k, "t1", bitacora=b)
    k.add("t1", "p8_asiento", "a1", {"id": "a1", "segmento": "g", "resultado": "PEDIDO",
                                     "cliente_ref": "SECRETO_l1"})
    agregado = i.agregar_p8()
    assert agregado and all("cliente_ref" not in a for a in agregado)   # 13.8
    b.publicar(Sobre(tenant_id="t1", tipo="marketing.campana.ajustada",
                     payload={"cambio": "PAUSA"}, origen="marketing.cubo"))
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    a = i.detectar("conversion", 0.30)
    prop = i.correlacionar(a["alerta_id"])
    assert prop["confianza"] == "ALTA" and "NO causalidad" in prop["narrativa"]
    i.resolver_alerta(a["alerta_id"], veredicto="DESCARTADA", por="operador")
    fp = i.tasa_falsos_positivos()
    assert fp["medible"] is False                                # n<15: informativa (R-17)
    assert fp["criticas_falsas"] == 1 and fp["bloqueante_ok"] is False
    rep = i.reporte_ejecutivo("2026-07")
    assert "operador" in rep["resumen"]                          # propone, no ejecuta


def test_intel_sin_datos_degradacion_elegante():
    i = CuboInteligencia(InMemoryKnowledge(), "t1")
    assert "SIN_DATOS" in i.patron("conversion", [])["estado"]
    assert i.patron("conversion", [0.1, 0.2, 0.3])["media"] == 0.2
