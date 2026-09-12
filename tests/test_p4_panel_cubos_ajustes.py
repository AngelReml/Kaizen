"""D10 P4 — Cubos y Ajustes: paridad de acciones (catalogo→rutas reales), controles
que llaman funciones testeadas (L3), alta de empresa E2E con guardas, tope acotado.
Puerta P4: mapa accion→control completo; alta E2E de empresa sintetica desde el panel."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from core.knowledge import InMemoryKnowledge
from panel_mando.app import crear_app

REGISTRO_TMP = {"version": 1, "tenants": [
    {"id": "laboratorio", "razon_social": "x", "vertical": "v", "estado": "activo",
     "fecha_alta": "2026-05-24", "partner_id": None, "referencia_credenciales": "fuera",
     "mandato": {"nivel_por_defecto": "BAJA", "techo_coste_diario_eur": 5.0}}]}


def _montaje(tmp_path):
    ruta = tmp_path / "tenants.json"
    ruta.write_text(json.dumps(REGISTRO_TMP), encoding="utf-8")
    k = InMemoryKnowledge()
    app = crear_app(k, mecha_s=0, ruta_registro=ruta)
    return app, TestClient(app, raise_server_exceptions=False), k, ruta


def test_paridad_de_acciones_catalogo_contra_rutas(tmp_path):
    """7 cubos, no 8: /cmd/cumplimiento/obligacion se retiro (Fase 5 excelencia,
    fusion Legal+Cumplimiento) por ser un subconjunto estrictamente mas pobre
    de lo que ya wirea legal.py::registrar_obligacion (hardcodeaba tipo=INTERNA,
    no exponia fuente_validada_por, no comprobaba autonomia)."""
    app, c, _, _ = _montaje(tmp_path)
    rutas = {r.path for r in app.routes}
    catalogo = app.state.catalogo_controles
    assert len(catalogo) == 7                                  # los 7 cubos presentes
    for cubo, controles in catalogo.items():
        assert controles, f"cubo sin control: {cubo}"
        for nombre, endpoint in controles:
            if endpoint:                                       # D03 aun sin dossier
                assert endpoint in rutas, f"control sin ruta: {cubo}:{nombre}"
    j = c.get("/api/cubos/laboratorio").json()
    assert len(j["cubos"]) == 7


def test_control_llama_funcion_real_con_evento(tmp_path):
    _, c, k, _ = _montaje(tmp_path)
    r = c.post("/cmd/ops/capacidad", json={"empresa": "laboratorio", "fecha": "2026-07-15",
                                           "lotes": 5, "quien": "operador"})
    assert r.status_code == 200 and r.json()["lotes"] == 5
    tipos = [e["tipo"] for e in k.all("laboratorio", "evento").values()]
    assert "operacion.capacidad.declarada" in tipos            # L3: quedo rastro


def test_alta_de_empresa_e2e_con_guardas(tmp_path):
    _, c, k, ruta = _montaje(tmp_path)
    mala = c.post("/cmd/empresas/alta", json={"id": "Con Espacios!", "quien": "operador"})
    assert mala.status_code == 409                             # guarda: id invalida
    r = c.post("/cmd/empresas/alta", json={"id": "sintetica", "razon_social": "Sintetica SL",
                                           "quien": "operador"})
    assert r.json()["creada"] == "sintetica"
    reg = json.loads(ruta.read_text(encoding="utf-8"))
    ficha = next(t for t in reg["tenants"] if t["id"] == "sintetica")
    assert ficha["mandato"]["nivel_por_defecto"] == "BAJA"     # nace prudente
    tipos = [e["tipo"] for e in k.all("sintetica", "evento").values()]
    assert "plataforma.tenant.creado" in tipos
    dup = c.post("/cmd/empresas/alta", json={"id": "sintetica", "quien": "operador"})
    assert dup.status_code == 409                              # guarda: duplicado


def test_tope_acotado_y_volver_a_recomendado(tmp_path):
    _, c, _, ruta = _montaje(tmp_path)
    fuera = c.post("/cmd/ajustes/tope", json={"empresa": "laboratorio", "tope_eur": 999,
                                              "quien": "operador"})
    assert fuera.status_code == 409                            # guarda: 0-100
    ok = c.post("/cmd/ajustes/tope", json={"empresa": "laboratorio", "tope_eur": 8,
                                           "quien": "operador"})
    assert ok.json()["tope_eur"] == 8 and ok.json()["volver_recomendado"] == 5.0
    reg = json.loads(ruta.read_text(encoding="utf-8"))
    assert reg["tenants"][0]["mandato"]["techo_coste_diario_eur"] == 8
