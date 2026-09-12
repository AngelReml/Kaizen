"""Tests del Filtro ICP de Laboratorio (§5.2 / §5.3 del v0.2).

El criterio del documento: distinguir Ballester (excluido) de un hotel boutique
(incluido) sin que el LLM lo invente. Estas pruebas codifican esa promesa.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.icp import FiltroICP


def _icp() -> FiltroICP:
    return FiltroICP("laboratorio")


# ── Exclusiones por marca / competencia directa ──────────────────────────────
def test_rechaza_marca_excluida_por_palabra_completa():
    icp = _icp()
    d = icp.evaluar({"nombre": "Panadería Marca Sintetica Excluida Uno S.L.",
                    "place_types": ["bakery"]})
    assert d.aceptado is False
    assert any("Marca Sintetica Excluida Uno" in r for r in d.razones)


def test_rechaza_todas_las_marcas_excluidas():
    icp = _icp()
    for marca in ("Marca Sintetica Excluida Uno", "Marca Sintetica Excluida Dos",
                  "Marca Sintetica Excluida Tres"):
        d = icp.evaluar({"nombre": f"Distribuidora {marca}", "place_types": ["cafe"]})
        assert d.aceptado is False, f"{marca} debería rechazarse"
        assert any(marca in r for r in d.razones)


def test_la_marca_excluida_gana_sobre_un_tipo_incluido():
    """Un hotel que encaja por place_type pero lleva marca excluida: fuera."""
    icp = _icp()
    d = icp.evaluar({"nombre": "Marca Sintetica Excluida Dos Hotel",
                    "place_types": ["hotel"]})
    assert d.aceptado is False


def test_no_falso_positivo_por_substring():
    """Una marca excluida no debe matchear dentro de palabras más largas."""
    icp = _icp()
    d = icp.evaluar({"nombre": "Precocinados Unofrio", "place_types": ["restaurant"]})
    # Por palabra: no contiene "ballester" como palabra independiente → no se excluye
    # por marca. Puede excluirse por otra razón o aceptarse según keywords; lo único que
    # exigimos aquí es que la razón de rechazo, si la hay, NO sea "Ballester".
    if not d.aceptado:
        assert not any("Ballester" in r for r in d.razones)


# ── Inclusiones ──────────────────────────────────────────────────────────────
def test_acepta_hotel_boutique_por_place_type():
    icp = _icp()
    d = icp.evaluar({"nombre": "Hotel La Parra", "place_types": ["lodging"]})
    assert d.aceptado is True
    assert d.categoria == "hotel_boutique_con_desayuno"
    assert d.prioridad == "ALTA"


def test_acepta_cafeteria_de_especialidad_por_keyword():
    icp = _icp()
    d = icp.evaluar({"nombre": "Café Tostadero",
                     "place_types": ["cafe"],
                     "descripcion": "Cafetería de especialidad y brunch artesanal en Murcia."})
    assert d.aceptado is True
    assert d.categoria == "cafeteria_especialidad"


def test_acepta_tienda_gourmet_con_prioridad_alta():
    icp = _icp()
    d = icp.evaluar({"nombre": "Casa Marca Sintetica Excluida Tres",   # coincide con marca → debe ganar EXCLUIR
                     "place_types": ["deli"],
                     "descripcion": "Conservas gourmet artesanas"})
    # La marca excluida tiene precedencia sobre cualquier inclusión:
    # NO admitimos que un escaparate gourmet con ese nombre se cuele.
    assert d.aceptado is False


def test_acepta_tienda_gourmet_sin_marca_problematica():
    icp = _icp()
    d = icp.evaluar({"nombre": "Delicatessen El Olivo",
                     "place_types": ["deli"],
                     "descripcion": "Tienda gourmet con productos artesanos de origen"})
    assert d.aceptado is True
    assert d.categoria == "tienda_gourmet_delicatessen"
    assert d.prioridad == "ALTA"


def test_descarte_por_place_type_excluido():
    icp = _icp()
    d = icp.evaluar({"nombre": "Super del Pueblo", "place_types": ["supermarket"]})
    assert d.aceptado is False
    assert any("cadena_sintetica_excluida" in r for r in d.razones)


def test_default_rechaza_si_no_encaja():
    icp = _icp()
    d = icp.evaluar({"nombre": "Taller mecánico Juan",
                     "place_types": ["car_repair"],
                     "descripcion": "Reparación de coches"})
    assert d.aceptado is False


# ── Selección por prioridad cuando hay varios matches ────────────────────────
def test_prioridad_alta_gana_cuando_encajan_varias_categorias():
    """Un negocio que matchea tanto 'tienda_gourmet' (ALTA) como 'cafeteria_especialidad'
    (ALTA por keyword) debe quedar en la primera categoría ALTA encontrada (el orden de
    importancia es ALTA > MEDIA > BAJA; entre ALTA-ALTA, gana la primera del JSON)."""
    icp = _icp()
    d = icp.evaluar({"nombre": "El Colmado del Brunch",
                     "place_types": ["grocery_store"],
                     "descripcion": "Tienda gourmet de productos artesanos con esquina de brunch"})
    assert d.aceptado is True
    assert d.prioridad == "ALTA"
