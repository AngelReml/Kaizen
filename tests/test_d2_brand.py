"""Cubo Brand (D02): directrices FSM+versionado, validador categorizado, proveedor
del paquete brand en el sustrato (R-03), reproducibilidad via cache (R-02, 13.2),
aislamiento de directrices por tenant (13.1), version sin rotura (13.3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core import verificacion as V
from departments.brand.cubo_serie_d import CuboBrand, DirectrizInvalida

D_ARTESANIA = {"id": "MARCA.ARTESANIA", "regla": "jamas 'artesanal' sin horno/contexto real",
               "categoria": "MARCA_CRITICA", "accion": "NO_APTO_POR_MARCA",
               "palabras_prohibidas": ["artesanal"], "requiere_alguna": ["horno de leña", "obrador"],
               "estado": "ACTIVA"}
D_LEGAL = {"id": "LEGAL.COMPETENCIA", "regla": "prohibidas comparativas con competidores",
           "categoria": "LEGAL", "accion": "NO_APTO_POR_POLITICA",
           "palabras_prohibidas": ["competidor barato"], "estado": "ACTIVA"}


@pytest.fixture()
def brand():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    cb = CuboBrand(k, "t1", bitacora=b)
    cb.alta_directriz(dict(D_ARTESANIA))
    cb.alta_directriz(dict(D_LEGAL))
    yield cb, k, b
    V.quitar_paquete("brand")


def test_validador_categoriza_con_razones(brand):
    cb, _, _ = brand
    r = cb.validar("Nuestro pan artesanal es unico")
    assert r["veredicto"] == "NO_APTO_POR_MARCA" and r["razones"]
    r2 = cb.validar("Nuestro pan artesanal sale del horno de leña cada manana")
    assert r2["veredicto"] == "APTO"                       # contexto exigido presente
    r3 = cb.validar("mejor que cualquier competidor barato")
    assert r3["veredicto"] == "NO_APTO_POR_POLITICA"       # LEGAL pesa mas


def test_fsm_directriz_archivada_inmutable(brand):
    cb, _, _ = brand
    d = cb.alta_directriz({"id": "X", "regla": "r", "categoria": "LEGAL",
                           "accion": "APTO"})
    assert d["estado"] == "BORRADOR"
    cb.transicionar_directriz("X", "ACTIVA", por="operador")
    cb.transicionar_directriz("X", "ARCHIVADA", por="operador")
    with pytest.raises(DirectrizInvalida):
        cb.transicionar_directriz("X", "ACTIVA", por="operador")


def test_version_sin_rotura_13_3(brand):
    cb, _, _ = brand
    aprobado_v1 = "pan del obrador con horno de leña, artesanal de verdad"
    assert cb.validar(aprobado_v1)["veredicto"] == "APTO"
    cb.actualizar_directriz("LEGAL.COMPETENCIA", {"palabras_prohibidas": ["competidor barato", "grupo industrial"]},
                            por="operador")                # cambio ADITIVO
    assert cb.validar(aprobado_v1)["veredicto"] == "APTO"  # lo aprobado no se rompe
    assert cb.validar("no somos un grupo industrial")["veredicto"] == "NO_APTO_POR_POLITICA"


def test_cambio_de_directriz_emite_evento_y_cambia_version(brand):
    cb, k, b = brand
    v1 = cb.version_directrices()
    cb.actualizar_directriz("MARCA.ARTESANIA", {"regla": "igual pero v2"}, por="operador")
    assert cb.version_directrices() != v1                  # invalida cache del sustrato
    evs = [e for e in k.all("t1", "evento").values() if e["tipo"] == "brand.directriz.actualizada"]
    assert len(evs) == 1 and b.verificar()["integra"] is True


def test_proveedor_brand_en_sustrato_reproducible_20_20(brand):
    cb, k, _ = brand
    cb.registrar_en_sustrato()
    svc = V.ServicioVerificacion(k)
    borrador = "Vendemos pan artesanal sin mas contexto"
    vs = [svc.validar_borrador("t1", "email", borrador) for _ in range(20)]
    assert {v.veredicto for v in vs} == {"NO_APTO"} and svc.misses == 1   # R-02
    assert any("artesanal" in r for r in vs[0].razones)
    # el cambio de directrices invalida la cache: re-evaluacion consciente
    cb.actualizar_directriz("MARCA.ARTESANIA", {"palabras_prohibidas": []}, por="operador")
    v21 = svc.validar_borrador("t1", "email", borrador)
    assert v21.veredicto == "APTO" and svc.misses == 2


def test_aislamiento_directrices_por_tenant_13_1():
    k = InMemoryKnowledge()
    a = CuboBrand(k, "tenant_a"); b = CuboBrand(k, "tenant_b")
    a.alta_directriz({**D_LEGAL, "palabras_prohibidas": ["palabra_de_a"]})
    b.alta_directriz({**D_LEGAL, "palabras_prohibidas": ["palabra_de_b"]})
    texto = "esto contiene palabra_de_a nada mas"
    assert a.validar(texto)["veredicto"] == "NO_APTO_POR_POLITICA"
    assert b.validar(texto)["veredicto"] == "APTO"          # sin derrame entre tenants


def test_analizador_de_validaciones_alerta(brand):
    cb, _, _ = brand
    veredictos = [{"veredicto": "APTO"}, {"veredicto": "NO_APTO_POR_MARCA"},
                  {"veredicto": "NO_APTO_POR_MARCA"}, {"veredicto": "APTO"}]
    r = cb.analizar_periodo(veredictos)
    assert r["tasa_no_apto"] == 0.5 and r["alerta"] is True
