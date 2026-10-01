# -*- coding: utf-8 -*-
"""Lanzador herramientas/apuestas.py (A6): tanda, listar, ver y decidir, con modelo y busqueda simulados."""
import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from core import apuestas as A
from core import exploracion as E
from core.exploracion_modelos import ApagadaOSinToken
from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from test_exploracion import ModeloFalso, buscar_falso, candidato, dosier_json

spec = importlib.util.spec_from_file_location("cli_apuestas", RAIZ / "herramientas" / "apuestas.py")
CLI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CLI)

EMP = "lab"


class Consola:
    def __init__(self, respuestas=()):
        self.lineas = []
        self.respuestas = list(respuestas)
        self.preguntas = []

    def salida(self):
        def preguntar(texto):
            self.preguntas.append(texto)
            if not self.respuestas:
                raise EOFError
            return self.respuestas.pop(0)
        return CLI.Salida(imprimir=self.lineas.append, preguntar=preguntar)

    @property
    def texto(self):
        return "\n".join(self.lineas)


@pytest.fixture()
def entorno(tmp_path):
    k = InMemoryKnowledge()
    b = Bitacora(k, EMP, fecha_alta="2026-07-10")

    def deps(**kw):
        d = {"k": k, "empresa": EMP, "bitacora": b, "parar": lambda: False, "informes": tmp_path / "informes",
             "cliente": ModeloFalso(proponer=lambda m, u: json.dumps({"candidatos": [candidato(1000 * m.llamada_proponer + i) for i in range(8)]})),
             "buscar": buscar_falso}
        d.update(kw)
        return d

    def correr(argv, consola=None, **kw):
        consola = consola or Consola()
        codigo = CLI.main(argv, deps=deps(**kw), out=consola.salida())
        return codigo, consola
    return k, b, correr, tmp_path


def _una_apuesta(k, b, n=1):
    ap = A.Apuestas(k, EMP, bitacora=b)
    r = ap.crear_borrador({kk: v for kk, v in candidato(n).items() if kk in ("titulo", "problema", "publico", "por_que_ahora")},
                          candidato(n)["coordenadas"])
    ap.completar_dosier(r["id"], E.coercionar_dosier(json.loads(dosier_json()), buscar_falso("x")))
    return ap, r["id"]


# ── tanda ───────────────────────────────────────────────────────────────────

def test_tanda_de_extremo_a_extremo_deja_apuestas_informe_y_progreso(entorno):
    k, b, correr, tmp = entorno
    codigo, c = correr(["tanda", "--ciclos", "2"])
    assert codigo == 0
    assert "ciclo 0: 5 dosieres" in c.texto and "ciclo 1: 5 dosieres" in c.texto and "Terminada: completada" in c.texto
    informe = Path(next(l for l in c.lineas if l.startswith("Informe: "))[len("Informe: "):])
    assert informe.exists() and informe.read_text(encoding="utf-8").startswith("# Informe de la tanda")
    assert A.Apuestas(k, EMP).conteo_por_estado()["DOSIER"] == 10
    assert b.verificar()["integra"] is True


def test_tanda_respeta_parar_todo(entorno):
    _, _, correr, _ = entorno
    codigo, c = correr(["tanda"], parar=lambda: True)
    assert codigo == 0 and "Terminada: parar_todo" in c.texto and "0 dosieres" in c.texto


def test_tanda_con_sello_roto_no_empieza(entorno):
    k, b, correr, _ = entorno
    b.publicar(__import__("core.rue", fromlist=["Sobre"]).Sobre(tenant_id=EMP, tipo="comercial.lead.descubierto", payload={}, origen="t"))
    clave = sorted(k.all(EMP, "evento"))[0]
    ev = k.get(EMP, "evento", clave); ev["payload"] = {"manipulado": True}; k.add(EMP, "evento", clave, ev)
    codigo, c = correr(["tanda"])
    assert "Terminada: sello_roto" in c.texto


def test_tanda_con_error_fatal_avisa_y_deja_informe(entorno):
    _, _, correr, _ = entorno
    cliente = ModeloFalso(proponer=lambda m, u: ApagadaOSinToken("La API externa de WebLLM esta apagada (403). Enciendela con enable."))
    codigo, c = correr(["tanda"], cliente=cliente)
    assert codigo == 0 and "Terminada: error_fatal" in c.texto and "Aviso: La API externa de WebLLM esta apagada" in c.texto
    assert any(l.startswith("Informe: ") for l in c.lineas)


def test_tanda_sin_token_explica_que_hacer_y_no_filtra_nada(entorno, monkeypatch):
    _, _, correr, _ = entorno
    monkeypatch.delenv("KAIZEN_WEBLLM_TOKEN", raising=False)
    monkeypatch.delenv("KAIZEN_EXPLORACION_MODELO", raising=False)
    codigo, c = correr(["tanda"], cliente=None)
    assert codigo == 2 and "No se pudo:" in c.texto and "external_api_admin enable" in c.texto


# ── listar / ver ────────────────────────────────────────────────────────────

def test_listar_vacio_y_con_filtro(entorno):
    k, b, correr, _ = entorno
    _, c = correr(["listar"])
    assert "No hay apuestas" in c.texto
    _una_apuesta(k, b)
    _, c = correr(["listar"])
    assert "DOSIER" in c.texto and "ultimos 8 caracteres" in c.texto
    _, c = correr(["listar", "--estado", "elegida"])
    assert "No hay apuestas en estado ELEGIDA" in c.texto


def test_ver_por_id_completo_o_por_sufijo_y_errores_claros(entorno):
    k, b, correr, _ = entorno
    ap, i = _una_apuesta(k, b, 1)
    for ref in (i, i[-8:], i[:10]):
        codigo, c = correr(["ver", ref])
        assert codigo == 0 and "Primer paso gratuito" in c.texto
    codigo, c = correr(["ver", "abc"])
    assert codigo == 2 and "no hay ninguna apuesta" in c.texto
    codigo, c = correr(["ver", "zzzzzzzz"])
    assert codigo == 2 and "no hay ninguna apuesta" in c.texto
    _una_apuesta(k, b, 2)
    codigo, c = correr(["ver", i[:8]])                                   # prefijo de tiempo comun a las dos
    assert codigo == 2 and "ambiguo" in c.texto


# ── decidir ─────────────────────────────────────────────────────────────────

def test_flujo_completo_de_decisiones_por_el_lanzador(entorno):
    k, b, correr, _ = entorno
    ap, i = _una_apuesta(k, b)
    assert correr(["--por", "angel", "elegir", i])[0] == 0
    codigo, c = correr(["probar", i, "--umbral", "20", "--plazo", "30"])
    assert codigo == 0 and "ahora esta en EN_PRUEBA" in c.texto
    codigo, c = correr(["medir", i, "--valor", "25,5", "--ref", "panel de visitas"])
    assert codigo == 0 and "La regla propone CRECE" in c.texto
    codigo, c = correr(["cerrar", i, "crece", "--esperaba", "veinte", "--paso", "pidieron 25", "--haria-distinto", "nada"])
    assert codigo == 0 and "ahora esta en CRECE" in c.texto
    r = ap.obtener(i)
    assert r["estado"] == "CRECE" and r["medicion"]["valor"] == 25.5 and r["historial"][2]["por"] == "angel"


def test_lo_que_falta_se_pregunta(entorno):
    k, b, correr, _ = entorno
    ap, i = _una_apuesta(k, b)
    consola = Consola(["no me convence", "que gustara", "no gusto", "otro publico"])
    codigo, c = correr(["descartar", i], consola=consola)
    assert codigo == 0 and "ahora esta en DESCARTADA" in c.texto
    assert len(consola.preguntas) == 4 and ap.obtener(i)["aprendizaje"]["paso"] == "no gusto"


def test_sin_poder_preguntar_y_faltando_datos_falla_con_mensaje(entorno):
    k, b, correr, _ = entorno
    ap, i = _una_apuesta(k, b)
    codigo, c = correr(["descartar", i])                                  # sin respuestas: EOF
    assert codigo == 2 and "razon" in c.texto and ap.obtener(i)["estado"] == "DOSIER"


def test_transiciones_imposibles_dan_error_claro_y_no_cambian_nada(entorno):
    k, b, correr, _ = entorno
    ap, i = _una_apuesta(k, b)
    codigo, c = correr(["probar", i])
    assert codigo == 2 and "no esta permitido" in c.texto
    codigo, c = correr(["medir", i, "--valor", "mucho", "--ref", "x"])
    assert codigo == 2 and "numero" in c.texto
    assert ap.obtener(i)["estado"] == "DOSIER"


def test_la_coma_decimal_y_el_coste_cero_se_respetan(entorno):
    k, b, correr, _ = entorno
    ap, i = _una_apuesta(k, b)
    correr(["elegir", i]); correr(["probar", i, "--comparador", "<="])
    codigo, c = correr(["medir", i, "--valor", "3,5", "--ref", "formulario"])
    assert codigo == 0 and ap.obtener(i)["criterio"]["coste_max_eur"] == 0 and "CRECE" in c.texto     # 3.5 <= 10


def test_el_lanzador_cmd_existe_y_usa_expansion_diferida():
    cmd = (RAIZ / "lanzadores" / "NICHOS.cmd").read_text(encoding="utf-8")
    assert "enabledelayedexpansion" in cmd and "!id!" in cmd and "%id%" not in cmd
    assert "herramientas\\apuestas.py tanda" in cmd and "python -X utf8" in cmd
