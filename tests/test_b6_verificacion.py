"""Bloque D00-B6: servicio de verificacion, cache R-02, paquete enchufable, denegacion.
PUERTA B6 (adaptada por R-02): mismo borrador → mismo veredicto, N=20, garantizado
por construccion (1 miss + 19 hits)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core import verificacion as V


@pytest.fixture()
def svc():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    return V.ServicioVerificacion(k, bitacoras={"t1": b}), k, b


@pytest.fixture(autouse=True)
def _limpia_proveedores():
    yield
    V.quitar_paquete("brand")


def test_reproducibilidad_20_de_20_por_cache(svc):
    s, _, _ = svc
    borrador = "Buenos dias, le escribo desde un obrador tradicional para ofrecerle surtido semanal."
    veredictos = [s.validar_borrador("t1", "email", borrador) for _ in range(20)]
    assert len({v.veredicto for v in veredictos}) == 1
    assert len({v.hash for v in veredictos}) == 1          # 20/20 identicos
    assert s.misses == 1                                    # 1 evaluacion + 19 cache
    assert veredictos[0].cache_hit is False and veredictos[19].cache_hit is True


def test_paquete_embebido_por_defecto_deniega_placeholders(svc):
    s, _, _ = svc
    v = s.validar_borrador("t1", "email", "Estimado [NOMBRE], TODO: completar oferta")
    assert v.veredicto == "NO_APTO" and any("placeholder" in r for r in v.razones)


def test_proveedor_brand_registrado_sustituye_al_embebido(svc):
    s, _, _ = svc
    V.registrar_paquete("brand", lambda t, tc, c: {"veredicto": "NO_APTO",
                                                   "razones": ["regla de marca X"],
                                                   "version": "directrices-v2"})
    v = s.validar_borrador("t1", "email", "texto impecable sin placeholders")
    assert v.veredicto == "NO_APTO" and "[brand] regla de marca X" in v.razones


def test_cambio_de_version_de_directrices_reevalua(svc):
    s, _, _ = svc
    version = {"v": "d1"}
    V.registrar_paquete("brand", lambda t, tc, c: {"veredicto": "APTO", "razones": [],
                                                   "version": version["v"]})
    s.validar_borrador("t1", "email", "hola mundo")
    s.validar_borrador("t1", "email", "hola mundo")
    assert s.misses == 1
    version["v"] = "d2"                                     # nueva version de directrices
    s.validar_borrador("t1", "email", "hola mundo")
    assert s.misses == 2                                    # re-evaluacion consciente


def test_veredicto_emite_evento_con_hash_y_cadena_integra(svc):
    s, k, b = svc
    v = s.validar_borrador("t1", "email", "contenido limpio para evento")
    evs = [e for e in k.all("t1", "evento").values()
           if e["tipo"] == "plataforma.verificacion.emitida"]
    assert len(evs) == 1 and evs[0]["payload"]["hash"] == v.hash
    assert b.verificar()["integra"] is True


def test_cache_aislada_por_tenant(svc):
    s, k, _ = svc
    s.validar_borrador("t1", "email", "mismo texto")
    s.validar_borrador("t2", "email", "mismo texto")
    assert s.misses == 2                                    # t2 no hereda cache de t1 (I1)
    assert len(k.all("t1", "verificacion_cache")) == 1
    assert len(k.all("t2", "verificacion_cache")) == 1
