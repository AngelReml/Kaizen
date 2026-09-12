"""Tenant sintético 'laboratorio' (D11 E0.2) — el circuito se ensaya contra
nosotros mismos, jamás contra un tercero real.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from click.testing import CliRunner

from herramientas.generar_tenant_laboratorio import EMPRESA, generar
from sustrato import bus
from sustrato.cli import cli


def test_generador_es_determinista_e_inofensivo(tmp_path):
    k1, k2 = tmp_path / "k1.json", tmp_path / "k2.json"
    r1 = generar(k1, n=50)
    r2 = generar(k2, n=50)
    assert r1["leads"] == r2["leads"] == 50
    assert k1.read_text(encoding="utf-8") == k2.read_text(encoding="utf-8")  # determinista
    datos = json.loads(k1.read_text(encoding="utf-8"))
    leads = datos[EMPRESA]["lead"]
    assert all(l["sintetico"] for l in leads.values())
    assert all(l["contacto"]["email"].endswith(".invalid") for l in leads.values())
    assert all("Sintétic" in l["nombre"] or "Sintético" in l["nombre"]
               for l in leads.values())
    # I-1/I-3 de serie: los sintéticos nacen con sus insumos persistidos.
    assert all(l["place_types"] and l["icp_match"]["senal"] for l in leads.values())


def test_generador_preserva_las_demas_empresas(tmp_path):
    k = tmp_path / "k.json"
    k.write_text(json.dumps({"otra_empresa": {"lead": {"x": {"id": "x", "nombre": "X"}}}},
                            ensure_ascii=False), encoding="utf-8")
    generar(k, n=10)
    datos = json.loads(k.read_text(encoding="utf-8"))
    assert datos["otra_empresa"]["lead"]["x"]["nombre"] == "X"   # intacta
    assert len(datos[EMPRESA]["lead"]) == 10
    assert (tmp_path / "k.json.bak_laboratorio").exists()        # backup previo


def test_sintetico_recorre_sync_y_tarjetas_demo(tmp_path, monkeypatch):
    """El camino Mesa completo sobre el tenant sintético: knowledge → P9 → tarjetas."""
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "lab.db"))
    k = tmp_path / "k.json"
    generar(k, n=12)
    r = CliRunner().invoke(cli, ["registro", "sync", "--desde", str(k)])
    assert r.exit_code == 0, r.output
    assert "12 lead(s) nuevos" in r.output
    conn = bus.conexion()
    filas = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE cliente_id=? AND estado='COLD' AND prioridad='ALTA'",
        (EMPRESA,)).fetchone()[0]
    assert filas > 0
    r2 = CliRunner().invoke(cli, ["mesa", "proponer-demo", "--n", "3"])
    assert r2.exit_code == 0, r2.output
    assert r2.output.count("tarjeta creada") == 3
    cuerpos = [c for (c,) in conn.execute("SELECT cuerpo FROM propuestas").fetchall()]
    assert len(cuerpos) == 3 and all("[DEMO" in c for c in cuerpos)
