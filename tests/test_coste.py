"""Tests del contador de costes del sustrato (canonico 9) — Bloque 1.

BD temporal y limite inyectado por entorno; JAMAS toca data/kaizen.db real
ni .kaizen_cost.json real (ruta legado inyectada a tmp).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from sustrato import bus as sbus
from sustrato import coste


def _entorno(tmp_path, monkeypatch, limite="10.00"):
    monkeypatch.setenv("LIMITE_COSTE_DIARIO_EUR", limite)
    monkeypatch.setenv("KAIZEN_LOGS_DIR", str(tmp_path / "logs"))
    coste._aviso_80_emitido_hoy = None  # reset del guard una-vez-al-dia
    conn = sbus.conexion(tmp_path / "coste_test.db")
    coste.instalar(conn)
    legado = tmp_path / "legado_inexistente.json"
    return conn, legado


def test_hard_stop(tmp_path, monkeypatch):
    conn, legado = _entorno(tmp_path, monkeypatch, limite="10.00")
    coste.registrar(conn, "openrouter", "comite", 1000, 6.0)
    # 6.00 gastado + 5.00 estimado > 10.00 => hard stop SIN llamar
    with pytest.raises(coste.LimiteCosteSuperado):
        coste.autorizar(conn, 5.0, ruta_legado=legado)
    # y no se registro ningun gasto adicional
    assert coste.comprobar_limite(conn, ruta_legado=legado) == pytest.approx(6.0)
    # bajo el limite si autoriza y devuelve el gastado
    assert coste.autorizar(conn, 1.0, ruta_legado=legado) == pytest.approx(6.0)


def test_warn_al_80(tmp_path, monkeypatch):
    conn, legado = _entorno(tmp_path, monkeypatch, limite="10.00")
    coste.registrar(conn, "openrouter", "comite", 500, 7.9)
    assert not _hay_warn_80(tmp_path)          # 79% : sin aviso
    coste.registrar(conn, "openrouter", "comite", 10, 0.2)
    assert _hay_warn_80(tmp_path)              # 81% : WARN emitido
    assert coste.comprobar_limite(conn, ruta_legado=legado) == pytest.approx(8.1)


def _hay_warn_80(tmp_path) -> bool:
    logs = list((tmp_path / "logs").glob("kaizen_*.log"))
    if not logs:
        return False
    contenido = logs[0].read_text(encoding="utf-8")
    return "WARN | coste | gasto diario al 80%" in contenido


def test_puente_contador_legado(tmp_path, monkeypatch):
    """El gasto del contador existente (.kaizen_cost.json, USD) suma al freno."""
    conn, _ = _entorno(tmp_path, monkeypatch, limite="10.00")
    from sustrato.consola import ts_iso8601z
    legado = tmp_path / "kaizen_cost.json"
    legado.write_text('{"date": "%s", "usd": 10.0}' % ts_iso8601z()[:10], encoding="utf-8")
    assert coste.comprobar_limite(conn, ruta_legado=legado) == pytest.approx(9.2)  # 10 USD * 0.92
    with pytest.raises(coste.LimiteCosteSuperado):
        coste.autorizar(conn, 1.0, ruta_legado=legado)   # 9.2 + 1.0 > 10.00


if __name__ == "__main__":
    print("Ejecutar con pytest (usa fixtures tmp_path/monkeypatch).")
