"""D11 E1.3 (registro sync) + E1.4 (forense watchdog).

Lecciones del 2026-08-02/03 fijadas en tests: la BD del sustrato apareció VACÍA
mientras el knowledge tenía 494 leads, y el sandbox llevaba un mes abierto sin
que nadie lo viera. Ninguna de las dos cosas puede volver a ser silenciosa.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from click.testing import CliRunner

from sustrato import bus, forense
from sustrato import registro as registro_mod
from sustrato.cli import cli


def _knowledge_tmp(tmp_path, empresas):
    """knowledge.json mínimo con N leads por empresa."""
    datos = {}
    for empresa, n in empresas.items():
        datos[empresa] = {"lead": {
            f"lead_{empresa}_{i}": {
                "id": f"lead_{empresa}_{i}", "nombre": f"Negocio {i} de {empresa}",
                "estado_pipeline": "cold", "categoria_icp": "cafeteria_especialidad",
                "prioridad_icp": "ALTA",
                "contacto": {"telefono": f"96800{i:04d}"},
                "ubicacion": {"municipio": "Cieza"},
            } for i in range(n)}}
    f = tmp_path / "knowledge.json"
    f.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return f


def _db_env(tmp_path, monkeypatch):
    db = tmp_path / "kaizen_test.db"
    monkeypatch.setenv("KAIZEN_DB_PATH", str(db))
    return db


# ── E1.3 · registro sync ────────────────────────────────────────────────────

def test_sync_migra_todas_las_empresas_y_es_idempotente(tmp_path, monkeypatch):
    _db_env(tmp_path, monkeypatch)
    ruta = _knowledge_tmp(tmp_path, {"laboratorio_t": 3, "rial_t": 2})
    r1 = CliRunner().invoke(cli, ["registro", "sync", "--desde", str(ruta)])
    assert r1.exit_code == 0, r1.output
    assert "sync OK: 2 empresa(s), 5 lead(s) nuevos" in r1.output
    conn = bus.conexion()
    filas = dict(conn.execute(
        "SELECT cliente_id, COUNT(*) FROM leads GROUP BY cliente_id").fetchall())
    assert filas == {"laboratorio_t": 3, "rial_t": 2}
    # Segunda pasada: idempotente, cero nuevos.
    r2 = CliRunner().invoke(cli, ["registro", "sync", "--desde", str(ruta)])
    assert r2.exit_code == 0
    assert "0 lead(s) nuevos" in r2.output


def test_sync_sin_knowledge_no_revienta(tmp_path, monkeypatch):
    _db_env(tmp_path, monkeypatch)
    r = CliRunner().invoke(cli, ["registro", "sync", "--desde",
                                 str(tmp_path / "no_existe.json")])
    assert r.exit_code == 0
    assert "SIN KNOWLEDGE" in r.output


# ── E1.4 · forense watchdog ─────────────────────────────────────────────────

def _conn_instalada(tmp_path, monkeypatch):
    _db_env(tmp_path, monkeypatch)
    conn = bus.conexion()
    bus.instalar(conn)
    registro_mod.instalar(conn)
    return conn


def test_watchdog_canta_flag_de_peligro_abierto(tmp_path, monkeypatch):
    conn = _conn_instalada(tmp_path, monkeypatch)
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    avisos = forense.avisos_watchdog(conn, tmp_path / "sin_knowledge.json")
    assert any("KAIZEN_ENVIO_HABILITADO" in a and "FLAG ABIERTO" in a for a in avisos)


def test_watchdog_silencioso_con_flags_cerrados(tmp_path, monkeypatch):
    conn = _conn_instalada(tmp_path, monkeypatch)
    for f in forense.FLAGS_PELIGRO:
        monkeypatch.setenv(f, "false")
    avisos = forense.avisos_watchdog(conn, tmp_path / "sin_knowledge.json")
    assert avisos == []


def test_watchdog_detecta_divergencia_knowledge_vs_registro(tmp_path, monkeypatch):
    conn = _conn_instalada(tmp_path, monkeypatch)
    for f in forense.FLAGS_PELIGRO:
        monkeypatch.setenv(f, "false")
    ruta = _knowledge_tmp(tmp_path, {"laboratorio_t": 4})
    avisos = forense.avisos_watchdog(conn, ruta)          # registro vacío
    assert any("DIVERGENCIA" in a and "laboratorio_t" in a and "registro sync" in a
               for a in avisos)
    # Tras el sync, la divergencia desaparece.
    r = CliRunner().invoke(cli, ["registro", "sync", "--desde", str(ruta)])
    assert r.exit_code == 0
    assert forense.avisos_watchdog(conn, ruta) == []


def test_forense_diario_incluye_avisos_sin_alterar_veredicto(tmp_path, monkeypatch):
    from sustrato import coste, gates
    conn = _conn_instalada(tmp_path, monkeypatch)
    gates.instalar(conn)
    coste.instalar(conn)
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    r = forense.diario(conn, ruta_knowledge=tmp_path / "sin_knowledge.json")
    assert r["veredicto"] == "PASS"        # cadenas y coste mandan en el veredicto
    assert any("FLAG ABIERTO" in a for a in r["avisos"])   # pero el aviso se canta
