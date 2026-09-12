"""Tests del clasificador de anillos geográficos (§5.4).

Usa el proveedor Haversine para no depender de red. La integración con Google Routes
se prueba en el test E2E de Fase 0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.anillos import ClasificadorAnillos, LIMITES_ANILLOS_MIN
from departments.comercial.distancia.haversine import HaversineProvider

# Coordenadas reales aproximadas
CIEZA      = (38.2375, -1.4203)
MURCIA     = (37.9923, -1.1306)    # ~37km en recta, ~33 min real
CARTAGENA  = (37.6055, -0.9863)    # ~85km en recta, ~75 min real
ALBACETE   = (38.9943, -1.8585)    # ~90km en recta, ~85 min real (cerca de límite anillo 2-3)
MADRID     = (40.4168, -3.7038)    # >300km — anillo 3 claro


def _clasificador(max_anillo: int = 1) -> ClasificadorAnillos:
    return ClasificadorAnillos(HaversineProvider(), CIEZA[0], CIEZA[1], max_anillo_activo=max_anillo)


def test_cieza_mismo_punto_anillo_0():
    c = _clasificador()
    r = c.clasificar(*CIEZA)
    assert r.anillo == 0
    assert r.distancia_minutos < 5
    assert r.proveedor == "haversine"


def test_murcia_cae_dentro_de_anillo_1():
    c = _clasificador()
    r = c.clasificar(*MURCIA)
    assert r.anillo == 1
    assert 15 <= r.distancia_minutos <= 60   # holgura amplia para haversine aproximado


def test_cartagena_cae_dentro_de_anillo_2():
    c = _clasificador()
    r = c.clasificar(*CARTAGENA)
    assert r.anillo == 2
    assert 45 <= r.distancia_minutos <= 100


def test_madrid_cae_en_anillo_3():
    c = _clasificador()
    r = c.clasificar(*MADRID)
    assert r.anillo == 3
    assert r.distancia_minutos > LIMITES_ANILLOS_MIN[2]


def test_flag_activo_respeta_max_anillo_del_icp():
    c = _clasificador(max_anillo=1)
    assert c.clasificar(*CIEZA).activo is True
    assert c.clasificar(*MURCIA).activo is True
    assert c.clasificar(*CARTAGENA).activo is False    # anillo 2 fuera
    assert c.clasificar(*MADRID).activo is False
