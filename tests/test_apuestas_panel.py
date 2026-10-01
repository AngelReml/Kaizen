# -*- coding: utf-8 -*-
"""Panel de apuestas: GET /api/apuestas/{empresa}, POST /cmd/apuestas/transicion y la foto del Mundo (A5)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import claude_client
from core import apuestas as A
from core.aprobaciones import ColaSustrato
from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from panel_mando.app import crear_app

EMP = "laboratorio"
CLAVE = "clave-de-prueba-apuestas"
TITULO = "Recordatorios zzsecretoz de plazos fiscales para autonomos"


def coords(**kw):
    base = {"modelo_ingreso": "servicio_por_encargo", "cliente": "pyme", "canal": "contacto_directo", "mercado": "es_ES",
            "coste_inicial": "0", "tiempo_senal": "<=7d", "sector": "gestorias de barrio"}
    base.update(kw)
    return base


def dosier():
    return {"nicho": {"problema": "Los autonomos olvidan fechas de impuestos", "publico": "Autonomos de servicios",
                      "por_que_ahora": "Nuevas obligaciones"},
            "evidencia": [{"afirmacion": "Hay recargos por presentar tarde", "etiqueta": "RECORDADA"},
                          {"afirmacion": "Existen calendarios oficiales", "etiqueta": "SUPUESTO"}],
            "coste": {"importe_eur": 0, "concepto": "ninguno", "alternativa_gratuita": "Hoja compartida con avisos"},
            "senal": {"que_se_mide": "Personas que piden el aviso", "umbral": 10, "comparador": ">=", "plazo_dias": 14,
                      "fuente_dato": "Respuestas recibidas"},
            "capacidades": {"necesarias": ["redactar"], "tiene": ["redactar"], "faltan": []},
            "necesita_del_operador": ["Publicar el mensaje"],
            "senal_real": {"que_personas": "Autonomos del grupo", "como_se_obtiene": "Cuantos responden"},
            "primer_paso_gratuito": "Preguntar en un grupo si pagarian",
            "riesgo_legal": {"nivel": "bajo", "por_que": "Sin datos sensibles"}}


@pytest.fixture()
def montaje(tmp_path, monkeypatch):
    monkeypatch.delenv("KAIZEN_TOKEN", raising=False)
    monkeypatch.setenv("KAIZEN_DB_PATH", str(tmp_path / "kaizen.db"))
    monkeypatch.setattr(claude_client, "budget_status", lambda: (True, None))
    monkeypatch.setattr(claude_client, "session_cost_eur", lambda: 0.0)

    def hacer(token=None):
        k = InMemoryKnowledge()
        app = crear_app(k, token=token, mecha_s=0)
        b = Bitacora(k, EMP, fecha_alta="2026-07-10")
        app.state.bitacoras[EMP] = b
        app.state.colas[EMP] = ColaSustrato(k, EMP, bitacora=b)
        return k, b, TestClient(app, raise_server_exceptions=False)
    return hacer


def _apuesta_en_dosier(k, b):
    ap = A.Apuestas(k, EMP, bitacora=b)
    r = ap.crear_borrador({"titulo": TITULO, "problema": "Los autonomos olvidan fechas y pagan recargos evitables.",
                           "publico": "Autonomos de servicios sin gestor", "por_que_ahora": "Nuevas obligaciones"}, coords())
    ap.completar_dosier(r["id"], dosier())
    return ap, r["id"]


def _post(c, **cuerpo):
    return c.post("/cmd/apuestas/transicion", json={"empresa": EMP, "quien": "operador", **cuerpo})


# ── lectura ─────────────────────────────────────────────────────────────────

def test_lista_vacia_y_con_apuestas(montaje):
    k, b, c = montaje()
    j = c.get(f"/api/apuestas/{EMP}").json()
    assert j["apuestas"] == [] and j["conteo"]["BORRADOR"] == 0 and j["pide_medicion"] == []
    _, ap_id = _apuesta_en_dosier(k, b)
    j = c.get(f"/api/apuestas/{EMP}").json()
    assert j["conteo"]["DOSIER"] == 1 and j["apuestas"][0]["id"] == ap_id and j["apuestas"][0]["borrador"]["titulo"] == TITULO
    assert j["apuestas"][0]["dosier"]["senal"]["umbral"] == 10


def test_empresa_desconocida_en_la_lectura(montaje):
    _, _, c = montaje()
    assert c.get("/api/apuestas/no_existe").status_code == 404


def test_con_clave_la_lectura_y_la_decision_exigen_autenticacion(montaje):
    k, b, c = montaje(token=CLAVE)
    _, ap_id = _apuesta_en_dosier(k, b)
    assert c.get(f"/api/apuestas/{EMP}").status_code in (401, 403)
    r = c.post("/cmd/apuestas/transicion", json={"empresa": EMP, "id": ap_id, "accion": "elegir", "quien": "operador"})
    assert r.status_code in (401, 403) and A.Apuestas(k, EMP).obtener(ap_id)["estado"] == "DOSIER"
    assert c.get(f"/api/apuestas/{EMP}", headers={"X-Token": CLAVE}).status_code == 200
    r = c.post("/cmd/apuestas/transicion", headers={"X-Token": CLAVE},
               json={"empresa": EMP, "id": ap_id, "accion": "elegir", "quien": "operador"})
    assert r.status_code == 200 and A.Apuestas(k, EMP).obtener(ap_id)["estado"] == "ELEGIDA"


# ── decisiones ──────────────────────────────────────────────────────────────

def test_camino_completo_por_http_y_sellado(montaje):
    k, b, c = montaje()
    ap, ap_id = _apuesta_en_dosier(k, b)
    assert _post(c, id=ap_id, accion="elegir").json()["apuesta"]["estado"] == "ELEGIDA"
    r = _post(c, id=ap_id, accion="iniciar_prueba", criterio={"plazo_dias": 30}).json()["apuesta"]
    assert r["estado"] == "EN_PRUEBA" and r["criterio"]["plazo_dias"] == 30 and r["criterio"]["coste_max_eur"] == 0
    r = _post(c, id=ap_id, accion="registrar_medicion", valor=4, referencia="hoja de respuestas").json()["apuesta"]
    assert r["estado"] == "MEDIDA" and r["propuesta_regla"]["decision"] == "PODADA"
    r = _post(c, id=ap_id, accion="cerrar", decision="PODADA",
              aprendizaje={"esperaba": "diez respuestas", "paso": "solo cuatro", "haria_distinto": "otro canal"}).json()["apuesta"]
    assert r["estado"] == "PODADA" and r["aprendizaje"]["paso"] == "solo cuatro"
    tipos = [e["tipo"] for e in k.all(EMP, "evento").values()]
    assert tipos[-5:] == ["inteligencia.apuesta.dosier_completado", "inteligencia.apuesta.elegida", "inteligencia.apuesta.en_prueba",
                          "inteligencia.apuesta.medida", "inteligencia.apuesta.podada"]
    assert b.verificar()["integra"] is True


def test_descartar_por_http(montaje):
    k, b, c = montaje()
    _, ap_id = _apuesta_en_dosier(k, b)
    r = _post(c, id=ap_id, accion="descartar", razon="no me convence", aprendizaje={"esperaba": "mas", "paso": "nada", "haria_distinto": "otro"})
    assert r.status_code == 200 and r.json()["apuesta"]["estado"] == "DESCARTADA"


@pytest.mark.parametrize("cuerpo,fragmento", [
    ({"accion": "elegir"}, "falta el id"),
    ({"id": 5, "accion": "elegir"}, "falta el id"),
    ({"id": "x", "accion": "borrar_todo"}, "accion desconocida"),
    ({"id": "x", "accion": ["elegir"]}, "accion desconocida"),
    ({"id": "inexistente", "accion": "elegir"}, "inexistente"),
    ({"empresa": "otra", "id": "x", "accion": "elegir"}, "empresa desconocida"),
    ({"empresa": ["laboratorio"], "id": "x", "accion": "elegir"}, "empresa desconocida"),
])
def test_entradas_invalidas_son_409_y_no_cambian_nada(montaje, cuerpo, fragmento):
    k, b, c = montaje()
    _apuesta_en_dosier(k, b)
    antes = json.dumps(A.Apuestas(k, EMP).listar(), sort_keys=True)
    r = c.post("/cmd/apuestas/transicion", json={"empresa": EMP, "quien": "operador", **cuerpo})
    assert r.status_code == 409 and fragmento in r.text
    assert json.dumps(A.Apuestas(k, EMP).listar(), sort_keys=True) == antes


@pytest.mark.parametrize("cuerpo", ["texto", [1, 2], 5, None])
def test_cuerpo_que_no_es_objeto_es_409(montaje, cuerpo):
    _, _, c = montaje()
    assert c.post("/cmd/apuestas/transicion", json=cuerpo).status_code == 409


def test_sin_identidad_o_json_roto_se_rechaza(montaje):
    k, b, c = montaje()
    _, ap_id = _apuesta_en_dosier(k, b)
    assert c.post("/cmd/apuestas/transicion", json={"empresa": EMP, "id": ap_id, "accion": "elegir"}).status_code == 409
    assert c.post("/cmd/apuestas/transicion", content=b"{roto", headers={"Content-Type": "application/json"}).status_code == 409
    assert A.Apuestas(k, EMP).obtener(ap_id)["estado"] == "DOSIER"


@pytest.mark.parametrize("cuerpo,fragmento", [
    ({"accion": "iniciar_prueba", "criterio": "texto"}, None),
    ({"accion": "iniciar_prueba", "criterio": {"coste_max_eur": 50}}, "coste_max_eur"),
    ({"accion": "registrar_medicion", "valor": "mucho", "referencia": "x"}, "valor"),
    ({"accion": "cerrar", "decision": "TALVEZ", "aprendizaje": {}}, "CRECE o PODADA"),
    ({"accion": "descartar", "razon": 5, "aprendizaje": 7}, "razon"),
])
def test_cuerpos_hostiles_en_cada_accion_dan_409_nunca_500(montaje, cuerpo, fragmento):
    k, b, c = montaje()
    ap, ap_id = _apuesta_en_dosier(k, b)
    ap.elegir(ap_id, por="op")
    if cuerpo["accion"] in ("registrar_medicion", "cerrar"):
        ap.iniciar_prueba(ap_id, por="op")
    r = _post(c, id=ap_id, **cuerpo)
    assert r.status_code == 409, r.text
    if fragmento:
        assert fragmento in r.text


def test_saltarse_estados_no_es_posible_por_http(montaje):
    k, b, c = montaje()
    _, ap_id = _apuesta_en_dosier(k, b)
    for accion, extra in (("iniciar_prueba", {}), ("registrar_medicion", {"valor": 1, "referencia": "abc"}),
                          ("cerrar", {"decision": "CRECE", "aprendizaje": {"esperaba": "abc", "paso": "abc", "haria_distinto": "abc"}})):
        r = _post(c, id=ap_id, accion=accion, **extra)
        assert r.status_code == 409 and "no esta permitido" in r.text
    assert A.Apuestas(k, EMP).obtener(ap_id)["estado"] == "DOSIER"


def test_la_decision_queda_registrada_con_quien_la_toma(montaje):
    k, b, c = montaje()
    _, ap_id = _apuesta_en_dosier(k, b)
    assert _post(c, id=ap_id, accion="elegir", quien="angel").status_code == 200
    h = A.Apuestas(k, EMP).obtener(ap_id)["historial"][-1]
    assert (h["actor"], h["por"], h["a"]) == ("operador", "angel", "ELEGIDA")


# ── la foto del Mundo: solo numeros ─────────────────────────────────────────

def test_el_mundo_cuenta_apuestas_por_estado_sin_ningun_texto(montaje):
    k, b, c = montaje()
    ap, ap_id = _apuesta_en_dosier(k, b)
    ap.elegir(ap_id, por="op")
    j = c.get("/api/mundo/estado", params={"empresa": EMP}).json()
    assert j["apuestas"]["conteo"]["ELEGIDA"] == 1 and j["apuestas"]["conteo"]["DOSIER"] == 0
    assert j["apuestas"]["pide_medicion"] == 0
    volcado = json.dumps(j)
    for texto in ("zzsecretoz", "Recordatorios", "olvidan fechas", "Preguntar en un grupo", "Hoja compartida"):
        assert texto not in volcado


def test_el_mundo_avisa_de_los_plazos_vencidos_sin_cambiar_el_estado(montaje):
    k, b, c = montaje()
    ap, ap_id = _apuesta_en_dosier(k, b)
    ap.elegir(ap_id, por="op"); ap.iniciar_prueba(ap_id, por="op")
    r = ap.obtener(ap_id); r["criterio"]["fecha_limite"] = "2020-01-01"; k.add(EMP, A.COLECCION, ap_id, r)
    j = c.get("/api/mundo/estado", params={"empresa": EMP}).json()
    assert j["apuestas"]["pide_medicion"] == 1 and j["apuestas"]["conteo"]["EN_PRUEBA"] == 1
    assert c.get(f"/api/apuestas/{EMP}").json()["pide_medicion"] == [ap_id]


def test_el_mundo_sin_apuestas_da_ceros(montaje):
    _, _, c = montaje()
    j = c.get("/api/mundo/estado", params={"empresa": EMP}).json()
    assert j["apuestas"] == {"conteo": {e: 0 for e in A.ESTADOS}, "pide_medicion": 0}


def test_los_eventos_de_apuestas_salen_en_el_feed_del_mundo(montaje):
    k, b, c = montaje()
    _apuesta_en_dosier(k, b)
    j = c.get("/api/mundo/estado", params={"empresa": EMP}).json()
    frases = [e["frase"] for e in j["recientes"] if e["tipo"].startswith("inteligencia.apuesta.")]
    assert any("propuse una apuesta nueva" in f for f in frases) and all("zzsecretoz" not in f for f in frases)
