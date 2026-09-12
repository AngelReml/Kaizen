"""Tests del catalogo de cubos con contrato canonico - Fase 2.

Cada cubo: manifest valido, arranque sin pares, salud con esquema correcto.
Gates: una accion irreversible declarada SOLO en un manifest recibe el
tratamiento ALTA + comite (fila mas restrictiva, canonico 7.2).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from sustrato import bus as sbus
from sustrato import comite, gates
from sustrato.config import validar_manifest
from cubos import base as cubos_base

NOMBRES = sorted(cubos_base.manifiestos_instalados().keys())
TENANT = "laboratorio"


def test_hay_diez_cubos():
    assert len(NOMBRES) == 10
    assert "comercial" in NOMBRES and "rrhh" in NOMBRES


@pytest.mark.parametrize("nombre", NOMBRES)
def test_manifest_valido(nombre):
    validar_manifest(cubos_base.manifiestos_instalados()[nombre])


@pytest.mark.parametrize("nombre", NOMBRES)
def test_arranque_sin_pares_y_salud(nombre, tmp_path):
    conn = sbus.conexion(tmp_path / f"cubo_{nombre}.db")
    cubo = cubos_base.construir(nombre, conn=conn)
    cubo.instalar()
    cubo.arrancar()          # bus vacio, cero cubos adicionales: no debe fallar
    s = cubo.salud()
    assert set(s.keys()) == {"cubo", "estado", "detalle", "ts", "contadores"}
    assert s["cubo"] == nombre and s["estado"] in ("OK", "DEGRADADO", "ERROR")
    assert s["ts"].endswith("Z")
    assert all(isinstance(v, int) for v in s["contadores"].values())
    cubo.parar()


def test_rrhh_declara_su_posposicion(tmp_path):
    conn = sbus.conexion(tmp_path / "rrhh.db")
    cubo = cubos_base.construir("rrhh", conn=conn)
    cubo.instalar()
    assert "pospuesto" in cubo.salud()["detalle"]


def test_accion_irreversible_de_manifest_exige_alta_y_comite(tmp_path, monkeypatch):
    """publicacion_externa_real SOLO existe en el manifest de marketing."""
    conn = sbus.conexion(tmp_path / "gates_manifest.db")
    sbus.instalar(conn)
    gates.instalar(conn)
    convocado = []
    monkeypatch.setattr(comite, "convocar", lambda *a, **k: convocado.append(1) or {
        "veredicto": "FAIL", "confianza": 0.0, "votos": [], "accion": "x",
        "contexto_hash": "h", "ts": "t"})
    # nivel BAJA (defecto): FAIL nivel_insuficiente SIN convocar comite
    v = gates.gate_preventivo(conn, "publicacion_externa_real", {}, cubo="marketing")
    assert v.veredicto == "FAIL" and v.motivo == "nivel_insuficiente"
    assert convocado == []
    # nivel ALTA (operador): ahora SI exige comite
    gates.set_autonomia(conn, "marketing", "ALTA", "test", es_operador=True)
    v2 = gates.gate_preventivo(conn, "publicacion_externa_real", {}, cubo="marketing")
    assert convocado == [1]          # comite convocado
    assert v2.veredicto == "FAIL"    # y el dictamen del comite manda


# ── fusion Legal+Cumplimiento: salud() cuenta tambien la bitacora ──────────

def test_legal_declara_produce_rue_y_autonomia_baja():
    """La fusion exige que legal sea alcanzable (BAJA) y declare honestamente los
    tipos de evento reales que emite departments/cumplimiento/cubo_serie_d.py."""
    manifest = cubos_base.manifiestos_instalados()["legal"]
    import json
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert m["nivel_autonomia_defecto"] == "BAJA"
    assert "cumplimiento.obligacion.registrada" in m["produce_rue"]
    assert all(t.startswith("cumplimiento.") for t in m["produce_rue"])
    # produce_rue NUNCA se mezcla con 'produce' (ese es el canal validado kaizen.<cubo>.*)
    assert not set(m["produce_rue"]) & set(m["produce"])


def test_salud_legal_cuenta_eventos_de_bitacora_ademas_del_bus(tmp_path):
    conn = sbus.conexion(tmp_path / "cubo_legal_bitacora.db")
    k = InMemoryKnowledge()
    ts_reciente = datetime.now(timezone.utc).isoformat()
    k.add(TENANT, "evento", "000000000000",
         {"tipo": "cumplimiento.obligacion.registrada", "ts": ts_reciente,
          "payload": {"obligacion_ref": "x"}})
    cubo = cubos_base.construir("legal", conn=conn, knowledge=k, tenant=TENANT)
    cubo.instalar(); cubo.arrancar()
    s = cubo.salud()
    c = s["contadores"]
    assert c["eventos_bitacora_24h"] == 1
    assert c["eventos_bus_24h"] == 0
    assert c["eventos_publicados_24h"] == c["eventos_bus_24h"] + c["eventos_bitacora_24h"]
    cubo.parar()


def test_salud_sin_knowledge_no_cuenta_bitacora_y_no_rompe(tmp_path):
    """Retrocompatibilidad: construir/CuboGenerico sin knowledge/tenant (como hoy
    los llama sustrato/cli.py) siguen funcionando igual que antes de la fusion."""
    conn = sbus.conexion(tmp_path / "cubo_legal_sin_knowledge.db")
    cubo = cubos_base.construir("legal", conn=conn)
    cubo.instalar(); cubo.arrancar()
    s = cubo.salud()
    assert s["contadores"]["eventos_bitacora_24h"] == 0
    cubo.parar()
