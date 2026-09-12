"""Bloque D00-B4: libro de coste, hard stop delante, escalera, export CSV.
Prueba dura 13.2 (runaway): el techo muerde, nada aprobado se pierde, evento unico."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core.techos import LibroCoste, TechoAlcanzado

MANDATO = {"techo_coste_diario_eur": 1.0}


@pytest.fixture()
def libro():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    return LibroCoste(k, techo_global_eur=100.0, mandatos={"t1": MANDATO, "t2": MANDATO},
                      bitacoras={"t1": b}), k, b


def test_runaway_el_techo_muerde_delante(libro):
    lc, k, b = libro
    ejecutadas = 0
    with pytest.raises(TechoAlcanzado):
        for _ in range(100):                      # agente en bucle (13.2)
            lc.hard_stop_delante("t1", 0.3)
            lc.asiento("t1", cubo="comercial", rol="investigador", clase="ESTANDAR",
                       coste_eur=0.3)
            ejecutadas += 1
    assert ejecutadas == 3                        # 0.9 gastado; la 4a (1.2) NO se ejecuta
    assert lc.gasto_dia("t1") <= 1.0 + 0.3        # gasto ≤ techo + margen de 1 accion
    eventos = [e for e in k.all("t1", "evento").values()
               if e["tipo"] == "plataforma.coste.techo_alcanzado"]
    assert len(eventos) == 1                      # evento emitido UNA vez
    esc = lc.escalera("t1")
    assert esc["downgrade_clase"] is False        # 0.9 < 1.0: aun no tocado
    lc.asiento("t1", cubo="comercial", rol="x", clase="TRIVIAL", coste_eur=0.1)
    assert lc.escalera("t1")["pausar_nuevas_irrext"] is True


def test_aprobada_urgente_completa_aunque_haya_techo(libro):
    lc, _, _ = libro
    lc.asiento("t1", cubo="comercial", rol="x", clase="ESTANDAR", coste_eur=1.0)
    r = lc.hard_stop_delante("t1", 0.2, accion_aprobada_urgente=True)
    assert r["permitido"] is True                 # D00 §6.3.3: las aprobadas completan


def test_downgrade_de_clase_critica(libro):
    lc, _, _ = libro
    assert lc.clase_efectiva("CRITICA", "t1") == "CRITICA"
    lc.asiento("t1", cubo="c", rol="r", clase="CRITICA", coste_eur=1.0)
    assert lc.clase_efectiva("CRITICA", "t1") == "ESTANDAR"
    assert lc.clase_efectiva("CRITICA", "t1", lista_blanca=("CRITICA",)) == "CRITICA"
    assert lc.clase_efectiva("TRIVIAL", "t1") == "TRIVIAL"


def test_imputacion_aislada_y_export_csv(libro, tmp_path):
    lc, _, _ = libro
    lc.asiento("t1", cubo="comercial", rol="redactor", clase="ESTANDAR", coste_eur=0.2)
    lc.asiento("t2", cubo="brand", rol="validador", clase="CRITICA", coste_eur=0.4)
    assert lc.gasto_dia("t1") == 0.2 and lc.gasto_dia("t2") == 0.4   # I4: sin bolsa comun
    mes = __import__("datetime").datetime.now().strftime("%Y-%m")
    csv1 = lc.export_csv("t1", mes, tmp_path)
    assert "comercial" in csv1 and "brand" not in csv1               # fuga cero en export
    assert (tmp_path / f"coste_t1_{mes}.csv").exists()


def test_techo_global_tambien_muerde():
    k = InMemoryKnowledge()
    lc = LibroCoste(k, techo_global_eur=0.5, mandatos={"a": {"techo_coste_diario_eur": 10},
                                                       "b": {"techo_coste_diario_eur": 10}})
    lc.asiento("a", cubo="c", rol="r", clase="TRIVIAL", coste_eur=0.4)
    with pytest.raises(TechoAlcanzado):
        lc.hard_stop_delante("b", 0.2)            # 0.4 + 0.2 > 0.5 global
