"""La bitacora no pierde eventos ni rompe la cadena con varios procesos escribiendo el mismo fichero."""
import multiprocessing as mp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import JsonKnowledge
from core.rue import Bitacora, Sobre

T = "laboratorio"


def _publicar(args):
    ruta, n, tag = args
    b = Bitacora(JsonKnowledge(ruta), T, fecha_alta="2026-07-10")
    for i in range(n):
        b.publicar(Sobre(tenant_id=T, tipo="comercial.lead.descubierto", payload={"lead_ref": f"{tag}{i}"}, origen="t"))
    return n


def test_varios_procesos_no_pierden_eventos_ni_rompen_la_cadena(tmp_path):
    ruta = str(tmp_path / "k.json")
    with mp.get_context("spawn").Pool(4) as pool:
        pool.map(_publicar, [(ruta, 40, f"p{j}") for j in range(4)])
    b = Bitacora(JsonKnowledge(ruta), T, fecha_alta="2026-07-10")
    v = b.verificar()
    assert v["integra"] is True and v["eventos"] == 160, v


def test_la_transaccion_es_reentrante_en_el_mismo_hilo(tmp_path):
    k = JsonKnowledge(str(tmp_path / "k.json"))
    with k.transaccion():
        k.add(T, "x", "a", {"v": 1})
        assert k.get(T, "x", "a") == {"v": 1}
        with k.transaccion():
            assert k.all(T, "x") == {"a": {"v": 1}}
