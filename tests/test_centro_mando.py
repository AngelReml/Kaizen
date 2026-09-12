"""Tests del Centro de Mando v1."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

import centro_mando
from centro_mando import app


def test_instancias_registradas():
    with TestClient(app) as c:
        d = c.get("/api/instancias").json()
        assert "laboratorio" in d["instancias"]


def test_estado_honesto_sin_bd():
    """La instancia real del repo puede no tener data/kaizen.db: SIN DATOS (None), sin fingir."""
    with TestClient(app) as c:
        d = c.get("/api/estado?instancia=laboratorio").json()
        assert len(d["cubos"]) == 10
        nombres = {x["nombre"] for x in d["cubos"]}
        assert "comercial" in nombres and "rrhh" in nombres
        com = next(x for x in d["cubos"] if x["nombre"] == "comercial")
        assert com["contratado"] is True          # contratados.json del repo
        assert com["autonomia"] in ("CERO", "BAJA", "MEDIA", "ALTA")


def test_instancia_desconocida_404_y_sin_rutas_libres():
    with TestClient(app) as c:
        assert c.get("/api/estado?instancia=../../etc").status_code == 404
        r = c.post("/api/accion", json={"instancia": "no_existe", "accion": "forense"})
        assert r.status_code == 404


def test_acciones_validadas_y_via_cli(monkeypatch, tmp_path):
    llamadas = []
    def falso(ruta, args):
        llamadas.append((Path(ruta).name, args))
        return "salida simulada OK"
    monkeypatch.setattr(centro_mando, "EJECUTOR", falso)
    with TestClient(app) as c:
        # accion desconocida rechazada
        assert c.post("/api/accion", json={"instancia": "laboratorio",
                                           "accion": "borrar_todo"}).status_code == 400
        # set_autonomia exige motivo
        assert c.post("/api/accion", json={"instancia": "laboratorio", "accion": "set_autonomia",
                                           "cubo": "brand", "nivel": "MEDIA",
                                           "motivo": ""}).status_code == 400
        # y con motivo va por el CLI de la instancia (candado + hash alli)
        r = c.post("/api/accion", json={"instancia": "laboratorio", "accion": "set_autonomia",
                                        "cubo": "brand", "nivel": "MEDIA",
                                        "motivo": "subida temporal para campana"})
        assert r.status_code == 200 and "simulada" in r.json()["salida"]
        assert llamadas[-1][1][:2] == ["operador", "set-autonomia"]


def test_contratar_es_marcador_v1(tmp_path, monkeypatch):
    """contratar/descontratar escribe contratados.json de la instancia (marcador)."""
    inst = tmp_path / "cliente_x"
    (inst / "cubos" / "brand").mkdir(parents=True)
    (inst / "cubos" / "brand" / "manifest.json").write_text(json.dumps({
        "cubo": "brand", "version": "1.0.0", "cliente_id": "x", "descripcion": "d",
        "produce": [], "consume": [], "nivel_autonomia_defecto": "BAJA",
        "acciones_irreversibles": [], "requiere": []}), encoding="utf-8")
    registro = tmp_path / "registro.json"
    registro.write_text(json.dumps([{"nombre": "cliente_x", "ruta": str(inst)}]),
                        encoding="utf-8")
    monkeypatch.setattr(centro_mando, "RUTA_REGISTRO", registro)
    with TestClient(app) as c:
        r = c.post("/api/accion", json={"instancia": "cliente_x", "accion": "contratar",
                                        "cubo": "brand"})
        assert r.status_code == 200
        datos = json.loads((inst / "contratados.json").read_text(encoding="utf-8"))
        assert datos["brand"] is True
        d = c.get("/api/estado?instancia=cliente_x").json()
        assert d["cubos"][0]["contratado"] is True
        assert d["pipeline"] is None and d["coste_hoy_eur"] is None  # SIN DATOS honesto


def _instancia_tmp(tmp_path, monkeypatch):
    inst = tmp_path / "inst"
    (inst / "cubos" / "brand").mkdir(parents=True)
    (inst / "cubos" / "brand" / "manifest.json").write_text(json.dumps({
        "cubo": "brand", "version": "1.0.0", "cliente_id": "x", "descripcion": "d",
        "produce": [], "consume": [], "nivel_autonomia_defecto": "BAJA",
        "acciones_irreversibles": [], "requiere": []}), encoding="utf-8")
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps([{"nombre": "inst", "ruta": str(inst)}]), encoding="utf-8")
    monkeypatch.setattr(centro_mando, "RUTA_REGISTRO", reg)
    return inst


def test_alta_formulario_visible():
    with TestClient(app) as c:
        r = c.get("/alta")
        assert r.status_code == 200 and "Alta de empresa" in r.text
        assert "NUNCA hay que decir" in r.text            # el form ES la checklist


def test_alta_crea_ficha_completa(tmp_path, monkeypatch):
    inst = _instancia_tmp(tmp_path, monkeypatch)
    with TestClient(app) as c:
        r = c.post("/api/alta", json={
            "instancia": "inst", "nombre_empresa": "Panadería Pedro SL",
            "actividad": "Pan de masa madre", "publico": "bares de Padron",
            "tono": "cercano y artesano", "nunca_decir": "somos los mas baratos\nrebajas",
            "palabras_prohibidas": "barato, industrial", "responsable": "Pedro Garcia",
            "cargo": "Gerente", "departamentos": ["brand"]})
        assert r.status_code == 200
        slug = r.json()["empresa"]
        assert slug == "panaderia_pedro_sl"                 # acentos y espacios resueltos
        base = inst / "empresas" / slug
        perfil = json.loads((base / "perfil.json").read_text(encoding="utf-8"))
        assert perfil["nombre"] == "Panadería Pedro SL"
        palabras = json.loads((base / "brand" / "palabras_prohibidas.json")
                              .read_text(encoding="utf-8"))
        assert palabras["palabras"] == ["barato", "industrial"]   # esquema del guardian
        vetos = json.loads((base / "brand" / "argumentos_prohibidos.json")
                           .read_text(encoding="utf-8"))
        assert len(vetos["argumentos"]) == 2
        firma = json.loads((base / "brand" / "firma.json").read_text(encoding="utf-8"))
        assert firma["remitente_nombre"] == "Pedro Garcia"
        contratados = json.loads((base / "contratados.json").read_text(encoding="utf-8"))
        assert contratados == {"brand": True}
        # no sobrescribe
        r2 = c.post("/api/alta", json={"instancia": "inst",
                                       "nombre_empresa": "panaderia pedro sl",
                                       "responsable": "Pedro"})
        assert r2.status_code == 409


def test_alta_valida_entradas(tmp_path, monkeypatch):
    _instancia_tmp(tmp_path, monkeypatch)
    with TestClient(app) as c:
        assert c.post("/api/alta", json={"instancia": "inst", "nombre_empresa": "..//..",
                                         "responsable": "X"}).status_code == 400
        assert c.post("/api/alta", json={"instancia": "inst", "nombre_empresa": "Bar Y",
                                         "responsable": "  "}).status_code == 400
