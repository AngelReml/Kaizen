"""I-1/I-2/I-3 (D11 E1) — los insumos de cada decisión se persisten con la decisión.

Hallazgo del experimento de determinismo 2026-08-03: solo el 20% del corpus era
re-derivable porque place_types no se guardaba, los descartes se perdían y el peso
del match no quedaba registrado. Estos tests fijan la lección para siempre.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.anillos import ClasificadorAnillos
from departments.comercial.distancia.base import DistanceProvider, ResultadoDistancia
from departments.comercial.fuentes.base import CandidatoCrudo, FuenteLeads
from departments.comercial.icp import FiltroICP
from departments.comercial.lifecycle import LeadStore
from departments.comercial.researcher import Researcher


class DistanciaFija(DistanceProvider):
    nombre = "fija_test"

    def medir(self, olat, olon, dlat, dlon, direccion_destino=None):
        return ResultadoDistancia(minutos=10.0, metros=9000.0, proveedor=self.nombre)


class FuenteFija(FuenteLeads):
    nombre = "fuente_test"

    def __init__(self, candidatos):
        self._candidatos = candidatos
        self._servido = False

    def buscar(self, query, *, centro=None, radio_m=30000, max_resultados=20):
        if self._servido:
            return []
        self._servido = True
        return list(self._candidatos)


def _candidatos():
    return [
        # Aceptado por señal FUERTE (place_type de tienda gourmet).
        CandidatoCrudo(fuente="fuente_test", id_externo="pt-1",
                       nombre="Delicias del Test",
                       direccion="Calle Uno, Cieza",
                       ubicacion={"lat": 38.24, "lon": -1.42},
                       tipo_principal="deli",
                       place_types=["deli"],
                       descripcion="", metadatos={"telefono": "968000001"}),
        # Aceptado por señal DÉBIL (keyword en el nombre, sin place_types).
        CandidatoCrudo(fuente="fuente_test", id_externo="kw-1",
                       nombre="Cafetería de Especialidad Test",
                       direccion="Calle Dos, Cieza",
                       ubicacion={"lat": 38.25, "lon": -1.43},
                       tipo_principal=None, place_types=[],
                       descripcion="", metadatos={}),
        # Rechazado por el ICP (sin señal alguna).
        CandidatoCrudo(fuente="fuente_test", id_externo="rj-1",
                       nombre="Ferretería Tornillo Feliz",
                       direccion="Calle Tres, Cieza",
                       ubicacion={"lat": 38.26, "lon": -1.44},
                       tipo_principal="hardware_store", place_types=["hardware_store"],
                       descripcion="", metadatos={}),
    ]


def _researcher(k):
    icp = FiltroICP("laboratorio")
    origen = icp.origen
    anillos = ClasificadorAnillos(DistanciaFija(), origen["lat"], origen["lon"],
                                  icp.max_anillo)
    store = LeadStore(k, "laboratorio")
    return Researcher(icp=icp, anillos=anillos, fuentes=[FuenteFija(_candidatos())],
                      lead_store=store, max_workers=1), store


def test_i1_place_types_se_persisten_en_el_lead():
    k = InMemoryKnowledge()
    r, store = _researcher(k)
    r.ejecutar_pasada(verbose=False)
    lead = store.get("delicias_del_test")
    assert lead is not None
    assert lead["place_types"] == ["deli"]
    # Y el aceptado sin place_types persiste la lista vacía (no ausencia).
    lead2 = store.get("cafeteria_de_especialidad_test")
    assert lead2 is not None
    assert lead2["place_types"] == []


def test_i3_senal_y_peso_del_match_se_persisten():
    k = InMemoryKnowledge()
    r, store = _researcher(k)
    r.ejecutar_pasada(verbose=False)
    fuerte = store.get("delicias_del_test")["icp_match"]
    assert fuerte["senal"] == "place_type" and fuerte["peso"] == 2
    assert fuerte["razon"].startswith("Encaja en")
    debil = store.get("cafeteria_de_especialidad_test")["icp_match"]
    assert debil["senal"] == "keyword" and debil["peso"] == 1


def test_i2_descartes_se_registran_con_insumos_y_razon():
    k = InMemoryKnowledge()
    r, _ = _researcher(k)
    res = r.ejecutar_pasada(verbose=False)
    assert res.descartes_icp == 1
    descartes = k.all("laboratorio", "descarte")
    assert "ferreteria_tornillo_feliz" in descartes
    d = descartes["ferreteria_tornillo_feliz"]
    assert d["clase"] == "icp"
    assert d["razon"]                       # razón no vacía
    assert d["place_types"] == ["hardware_store"]   # insumos completos del rechazo
    assert d["fuente"] == "fuente_test" and d["id_externo"] == "rj-1"
    assert d["ts"]


def test_i2_descarte_por_anillo_tambien_se_registra():
    class DistanciaLejos(DistanceProvider):
        nombre = "lejos_test"

        def medir(self, olat, olon, dlat, dlon, direccion_destino=None):
            return ResultadoDistancia(minutos=500.0, metros=400000.0, proveedor=self.nombre)

    k = InMemoryKnowledge()
    icp = FiltroICP("laboratorio")
    origen = icp.origen
    anillos = ClasificadorAnillos(DistanciaLejos(), origen["lat"], origen["lon"],
                                  icp.max_anillo)
    store = LeadStore(k, "laboratorio")
    r = Researcher(icp=icp, anillos=anillos, fuentes=[FuenteFija(_candidatos()[:1])],
                   lead_store=store, max_workers=1)
    res = r.ejecutar_pasada(verbose=False)
    assert res.descartes_anillo == 1
    d = k.all("laboratorio", "descarte")["delicias_del_test"]
    assert d["clase"] == "anillo"
    assert "fuera del máximo activo" in d["razon"]


def test_decision_icp_rechazo_no_lleva_senal():
    icp = FiltroICP("laboratorio")
    d = icp.evaluar({"nombre": "Ferretería Tornillo Feliz",
                     "place_types": ["hardware_store"], "descripcion": ""})
    assert not d.aceptado and d.senal is None and d.peso == 0
