# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del cubo Marketing: cada ToolSpec invoca el
objeto real de departments/marketing/ (CuboMarketing, MarketingDepartment,
departments.marketing.herramientas), no un doble de prueba. R-TENANT: tenant
sintetico 'laboratorio', jamas uno real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core import verificacion as V
from panel_mando.herramientas import base as B
from panel_mando.herramientas import marketing as M

TENANT = "laboratorio"


@pytest.fixture()
def k():
    return InMemoryKnowledge()


@pytest.fixture()
def bitacora(k):
    return Bitacora(k, TENANT, fecha_alta="2026-07-10")


def _invocar(nombre, argumentos, *, k, bitacora=None):
    return B.invocar({"marketing": M.HERRAMIENTAS}, "marketing", nombre, argumentos,
                     k=k, tenant=TENANT, bitacora=bitacora)


# ── crear_campana ────────────────────────────────────────────────────────

def test_crear_campana_construye_borrador_real(k, bitacora):
    r = _invocar("crear_campana", {
        "nombre": "otono", "segmento": "gourmet", "canales": "email, blog",
        "presupuesto_eur": 500.0, "duracion_dias": 14,
    }, k=k, bitacora=bitacora)
    assert r["estado"] == "BORRADOR"
    assert r["canales"] == ["email", "blog"]                 # coma -> list[str]
    assert r["presupuesto_eur"] == 500.0
    guardada = k.get(TENANT, "campana", r["id"])
    assert guardada is not None and guardada["nombre"] == "otono"


def test_crear_campana_rechaza_argumento_no_declarado(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("crear_campana", {
            "nombre": "x", "segmento": "s", "canales": "email",
            "presupuesto_eur": 10.0, "duracion_dias": 7, "intruso": "no",
        }, k=k)


def test_crear_campana_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("crear_campana", {
            "nombre": "x", "segmento": "s", "canales": "email", "duracion_dias": 7,
        }, k=k)


def test_crear_campana_rechaza_tipo_incorrecto(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("crear_campana", {
            "nombre": "x", "segmento": "s", "canales": "email",
            "presupuesto_eur": "no-es-numero", "duracion_dias": 7,
        }, k=k)


# ── crear_contenido ──────────────────────────────────────────────────────

def test_crear_contenido_real(k, bitacora):
    c = _invocar("crear_campana", {
        "nombre": "x", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 100.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    cont = _invocar("crear_contenido", {
        "c_id": c["id"], "tipo": "COPY", "texto": "pan de obrador con horno de leña",
    }, k=k, bitacora=bitacora)
    assert cont["estado"] == "GENERADO"
    assert cont["campana_ref"] == c["id"]
    assert k.get(TENANT, "contenido_mkt", cont["id"])["texto"].startswith("pan de obrador")


def test_crear_contenido_real_visible_via_piezas(k, bitacora):
    """AUDITORIA G4, flujo completo escribir->leer con el escritor REAL: lo que
    crear_contenido escribe en 'contenido_mkt' debe ser lo que piezas() ve, sin
    ningun paso manual intermedio."""
    c = _invocar("crear_campana", {
        "nombre": "x", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 100.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    cont = _invocar("crear_contenido", {
        "c_id": c["id"], "tipo": "COPY", "texto": "pan de obrador con horno de leña",
    }, k=k, bitacora=bitacora)
    r = _invocar("piezas", {}, k=k)
    assert len(r["piezas"]) == 1 and r["piezas"][0]["id"] == cont["id"]


# ── validar_con_brand: gate real, sin doble ──────────────────────────────

def test_validar_con_brand_aprueba_texto_limpio(k, bitacora):
    c = _invocar("crear_campana", {
        "nombre": "x", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 100.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    cont = _invocar("crear_contenido", {
        "c_id": c["id"], "tipo": "COPY", "texto": "pan de obrador con horno de leña",
    }, k=k, bitacora=bitacora)
    v = _invocar("validar_con_brand", {"cont_id": cont["id"]}, k=k, bitacora=bitacora)
    assert v["estado"] == "VALIDADO_POR_BRAND"
    assert "brand_hash" in v


def test_validar_con_brand_rechaza_con_paquete_brand_real(k, bitacora):
    """Registra el paquete 'brand' real (como test_d6_d7) para verificar que la
    herramienta usa el ServicioVerificacion REAL, no un stub interno."""
    V.registrar_paquete("brand", lambda t, tc, c: {
        "veredicto": "NO_APTO" if "industrial" in c.lower() else "APTO",
        "razones": ["palabra prohibida"] if "industrial" in c.lower() else [],
        "version": "d-v1"})
    try:
        c = _invocar("crear_campana", {
            "nombre": "x", "segmento": "s", "canales": "dry",
            "presupuesto_eur": 100.0, "duracion_dias": 7,
        }, k=k, bitacora=bitacora)
        cont = _invocar("crear_contenido", {
            "c_id": c["id"], "tipo": "COPY", "texto": "pan industrial barato",
        }, k=k, bitacora=bitacora)
        v = _invocar("validar_con_brand", {"cont_id": cont["id"]}, k=k, bitacora=bitacora)
        assert v["estado"] == "RECHAZADO"
    finally:
        V.quitar_paquete("brand")


# ── LECTURA: roi, plan, piezas, metricas_alcance ─────────────────────────

def test_roi_via_lead_real(k, bitacora):
    c = _invocar("crear_campana", {
        "nombre": "x", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 50.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    k.add(TENANT, "lead_canon", "l1", {"id": "l1", "fuentes":
          [{"tipo": "CAMPANA", "ref": c["id"], "fecha": "2026-07-01"}]})
    k.add(TENANT, "pedido_atribuido", "p1", {"pedido_id": "p1", "lead_ref": "l1",
                                             "estado": "ATRIBUIDO", "via": "DIRECTA"})
    r = _invocar("roi", {"c_id": c["id"]}, k=k, bitacora=bitacora)
    assert r["leads_generados"] == 1 and r["conversiones"] == 1 and r["verificable"] is True


def test_roi_rechaza_argumento_desconocido(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("roi", {"c_id": "x", "extra": 1}, k=k)


def test_plan_real_delega_en_marketing_department(k):
    r = _invocar("plan", {"n": 3}, k=k)
    assert "plan" in r and len(r["plan"]) == 3
    assert all("tema" in idea for idea in r["plan"])


def test_plan_opcional_usa_default(k):
    r = _invocar("plan", {}, k=k)
    assert len(r["plan"]) == 5                     # default n=5 de MarketingDepartment.plan


def test_piezas_real_lee_del_knowledge(k):
    """AUDITORIA G4: el productor real es CuboMarketing.crear_contenido, que escribe
    en 'contenido_mkt' (no 'contenido', el tipo legacy de registrar_pieza sin
    llamador real en produccion). piezas() debe leer del tipo que de verdad se
    escribe, con el esquema real (tema/canal/estado/ts que trae una pieza real)."""
    k.add(TENANT, "contenido_mkt", "cm1", {
        "id": "cm1", "tema": "pan de masa madre", "formato": "post", "canal": "blog",
        "cuerpo": "cuerpo", "estado": "publicada", "ts": "2026-08-01T00:00:00+00:00",
    })
    r = _invocar("piezas", {}, k=k)
    assert len(r["piezas"]) == 1 and r["piezas"][0]["tema"] == "pan de masa madre"
    r_filtro = _invocar("piezas", {"estado": "borrador"}, k=k)
    assert r_filtro["piezas"] == []


def test_piezas_ya_no_lee_del_tipo_legacy_contenido(k):
    """El tipo 'contenido' (registrar_pieza/publicar_pieza, sin llamador real) queda
    deliberadamente fuera de piezas() tras el fix: no hay perdida porque nada real lo
    escribia en produccion (verificado por la AUDITORIA G4)."""
    from departments.marketing import herramientas as h
    h.registrar_pieza(k, TENANT, tema="huerfano", formato="post", canal="blog",
                      cuerpo="c", estado="publicada")
    r = _invocar("piezas", {}, k=k)
    assert r["piezas"] == []


def test_metricas_alcance_real(k):
    from departments.marketing import herramientas as h
    k.add(TENANT, "contenido_mkt", "cm1", {
        "id": "cm1", "tema": "t1", "formato": "post", "canal": "blog",
        "cuerpo": "c", "estado": "publicada", "ts": "2026-08-01T00:00:00+00:00",
    })
    h.registrar_lead_inbound(k, TENANT, nombre="Ana", canal="blog", origen_pieza=None)
    r = _invocar("metricas_alcance", {}, k=k)
    assert r["piezas_publicadas"] == 1 and r["leads_inbound"] == 1
    assert r["por_canal"] == {"blog": 1}


# ── IRREVERSIBLE-INTERNA: rechazadas al invocar directo (contrato base.py) ──

def test_lanzar_es_irreversible_interna_no_se_invoca_directo(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("lanzar", {"c_id": "x", "cont_id": "y"}, k=k)


def test_registrar_metrica_es_irreversible_interna_no_se_invoca_directo(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("registrar_metrica", {
            "c_id": "x", "fecha": "2026-08-01", "impresiones": 100,
            "clicks": 5, "coste_eur": 3.5,
        }, k=k)


# ── pero invocar_aprobada SI dispara la ejecucion real ───────────────────

def test_lanzar_invocar_aprobada_ejecuta_de_verdad_dry_run(k, bitacora):
    """Patron 'servidor fuerza el actor': crear_campana deja la campaña en BORRADOR y
    NO hay ningun camino independiente para invocar aprobar_campana -- el wrapper de
    'lanzar' la fuerza el mismo, con por='operador', justo antes de lanzar. Esto es lo
    que de verdad pasa cuando el operador aprueba una tarjeta [PROPUESTA] real de
    'lanzar': invocar_aprobada() debe dejar la campaña ACTIVA de verdad, sin excepcion."""
    c = _invocar("crear_campana", {
        "nombre": "y", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 100.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    assert c["estado"] == "BORRADOR"
    cont = _invocar("crear_contenido", {
        "c_id": c["id"], "tipo": "COPY", "texto": "pan de obrador con horno de leña",
    }, k=k, bitacora=bitacora)
    _invocar("validar_con_brand", {"cont_id": cont["id"]}, k=k, bitacora=bitacora)
    r = B.invocar_aprobada({"marketing": M.HERRAMIENTAS}, "marketing", "lanzar",
                           {"c_id": c["id"], "cont_id": cont["id"]},
                           k=k, tenant=TENANT, bitacora=bitacora)
    assert r["dry_run"] is True
    assert k.get(TENANT, "campana", c["id"])["estado"] == "ACTIVA"


def test_lanzar_sobre_campana_pausada_sigue_fallando_con_gate(k, bitacora):
    """Para cualquier estado que NO sea BORRADOR, el wrapper NO fuerza aprobar_campana
    -- lanzar() debe seguir lanzando su propio GateMarketing tal cual, para no
    reabrir/relanzar una campaña que no deberia."""
    from departments.marketing.cubo_serie_d import CuboMarketing, GateMarketing
    c = _invocar("crear_campana", {
        "nombre": "y", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 100.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    cont = _invocar("crear_contenido", {
        "c_id": c["id"], "tipo": "COPY", "texto": "pan de obrador con horno de leña",
    }, k=k, bitacora=bitacora)
    _invocar("validar_con_brand", {"cont_id": cont["id"]}, k=k, bitacora=bitacora)
    m = CuboMarketing(k, TENANT, bitacora=bitacora, servicio_verificacion=V.ServicioVerificacion(k))
    m.aprobar_campana(c["id"], por="operador")
    m.pausar(c["id"], por="operador")
    assert k.get(TENANT, "campana", c["id"])["estado"] == "PAUSADA"
    with pytest.raises(GateMarketing):
        B.invocar_aprobada({"marketing": M.HERRAMIENTAS}, "marketing", "lanzar",
                           {"c_id": c["id"], "cont_id": cont["id"]},
                           k=k, tenant=TENANT, bitacora=bitacora)
    assert k.get(TENANT, "campana", c["id"])["estado"] == "PAUSADA"


def test_registrar_metrica_invocar_aprobada_ejecuta_de_verdad(k, bitacora):
    c = _invocar("crear_campana", {
        "nombre": "x", "segmento": "s", "canales": "dry",
        "presupuesto_eur": 100.0, "duracion_dias": 7,
    }, k=k, bitacora=bitacora)
    r = B.invocar_aprobada({"marketing": M.HERRAMIENTAS}, "marketing", "registrar_metrica", {
        "c_id": c["id"], "fecha": "2026-08-01", "impresiones": 1000,
        "clicks": 40, "coste_eur": 12.5,
    }, k=k, tenant=TENANT, bitacora=bitacora)
    assert r["impresiones"] == 1000
    guardada = k.get(TENANT, "campana", c["id"])
    assert len(guardada["metricas"]) == 1 and guardada["metricas"][0]["clicks"] == 40


# ── aislamiento de cubo (sanity contra el registro real de este cubo) ────

def test_todas_las_specs_declaran_su_propio_nombre_y_clase_valida():
    for nombre, spec in M.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in B.CLASES_HERRAMIENTA
