# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del cubo Brand: cada ToolSpec se prueba
construyendo el objeto real (CuboBrand/AssetManager/BrandStrategist/
BrandGuardian/VoiceAuditor/DirectorBrand) contra InMemoryKnowledge y el
tenant sintetico 'laboratorio' (R-TENANT), invocando `fn` de verdad y
verificando el resultado real — mas la validacion de argumentos honesta
(ArgumentosInvalidos) para lo que debe rechazarse."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from departments.brand.asset_manager import AssetManager
from departments.brand.cubo_serie_d import CuboBrand, DirectrizInvalida
from panel_mando.herramientas.base import ArgumentosInvalidos
from panel_mando.herramientas.brand import HERRAMIENTAS

TENANT = "laboratorio"        # tenant sintetico de laboratorio (R-TENANT)

CUERPO_OK = (
    "Hola, somos Laboratorio KAIZEN, un obrador familiar con más de un siglo de historia "
    "en Cieza. Elaboramos repostería artesanal con recetas centenarias y nos encantaría que "
    "la conocierais. Si os encaja, podemos enviaros una pequeña muestra sin compromiso para "
    "que la probéis con calma. Un saludo, Equipo del Laboratorio — Laboratorio KAIZEN")

D_ARTESANIA = {"id": "MARCA.ARTESANIA", "regla": "jamas 'artesanal' sin horno/contexto real",
               "categoria": "MARCA_CRITICA", "accion": "NO_APTO_POR_MARCA",
               "palabras_prohibidas": ["artesanal"], "requiere_alguna": ["horno de leña", "obrador"],
               "estado": "ACTIVA"}


def _run(nombre, argumentos, *, k=None, tenant=TENANT, bitacora=None):
    spec = HERRAMIENTAS[nombre]
    limpios = spec.validar(argumentos)
    return spec.fn(k=k, tenant=tenant, bitacora=bitacora, **limpios)


# ── inventario de herramientas ──────────────────────────────────────────────

def test_alta_directriz_no_esta_wireada_por_riesgo_de_upsert_silencioso():
    assert "alta_directriz" not in HERRAMIENTAS


def test_todas_las_specs_tienen_nombre_consistente_y_clase_valida():
    for nombre, spec in HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert spec.clase != "IRREVERSIBLE-EXTERNA"      # frontera R2: ninguna aqui


# ── validar ──────────────────────────────────────────────────────────────────

def test_validar_veredicto_real_no_apto_por_marca():
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz(dict(D_ARTESANIA))
    r = _run("validar", {"texto": "Nuestro pan artesanal es unico"}, k=k)
    assert r["veredicto"] == "NO_APTO_POR_MARCA"
    assert r["razones"]


def test_validar_veredicto_real_apto_con_contexto():
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz(dict(D_ARTESANIA))
    r = _run("validar", {"texto": "Nuestro pan artesanal sale del horno de leña"}, k=k)
    assert r["veredicto"] == "APTO"


def test_validar_rechaza_argumento_desconocido():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["validar"].validar({"texto": "x", "intruso": "y"})


def test_validar_rechaza_falta_de_texto():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["validar"].validar({})


# ── analizar_periodo ─────────────────────────────────────────────────────────

def test_analizar_periodo_calcula_tasa_y_alerta():
    veredictos = json.dumps([{"veredicto": "APTO"}, {"veredicto": "NO_APTO_POR_MARCA"},
                             {"veredicto": "NO_APTO_POR_MARCA"}, {"veredicto": "APTO"}])
    r = _run("analizar_periodo", {"veredictos": veredictos})
    assert r["tasa_no_apto"] == 0.5 and r["alerta"] is True


def test_analizar_periodo_respeta_umbral_opcional():
    veredictos = json.dumps([{"veredicto": "APTO"}, {"veredicto": "NO_APTO_POR_MARCA"},
                             {"veredicto": "NO_APTO_POR_MARCA"}, {"veredicto": "APTO"}])
    r = _run("analizar_periodo", {"veredictos": veredictos, "umbral_no_apto": 0.9})
    assert r["alerta"] is False


def test_analizar_periodo_rechaza_umbral_no_numerico():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["analizar_periodo"].validar({"veredictos": "[]", "umbral_no_apto": "x"})


# ── directrices_activas / version_directrices ────────────────────────────────

def test_directrices_activas_lista_lo_real():
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz(dict(D_ARTESANIA))
    r = _run("directrices_activas", {}, k=k)
    assert [d["id"] for d in r["directrices"]] == ["MARCA.ARTESANIA"]


def test_version_directrices_refleja_estado_real():
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz(dict(D_ARTESANIA))
    r = _run("version_directrices", {}, k=k)
    assert r["version_directrices"] == "MARCA.ARTESANIA:1"


def test_directrices_activas_rechaza_argumentos():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["directrices_activas"].validar({"cualquiera": "x"})


# ── transicionar_directriz (IRREVERSIBLE-INTERNA) ───────────────────────────

def test_transicionar_directriz_ejecuta_transicion_real():
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz({"id": "X", "regla": "r", "categoria": "LEGAL",
                                         "accion": "APTO"})
    r = _run("transicionar_directriz", {"d_id": "X", "a": "ACTIVA"}, k=k)
    assert r["estado"] == "ACTIVA"


def test_transicionar_directriz_respeta_la_maquina_de_estados_real():
    """ARCHIVADA es inmutable: la excepcion real del dominio sube sin capturarse."""
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz({"id": "X", "regla": "r", "categoria": "LEGAL",
                                         "accion": "APTO"})
    _run("transicionar_directriz", {"d_id": "X", "a": "ACTIVA"}, k=k)
    _run("transicionar_directriz", {"d_id": "X", "a": "ARCHIVADA"}, k=k)
    with pytest.raises(DirectrizInvalida):
        _run("transicionar_directriz", {"d_id": "X", "a": "ACTIVA"}, k=k)


def test_transicionar_directriz_rechaza_falta_de_d_id():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["transicionar_directriz"].validar({"a": "ACTIVA"})


def test_transicionar_directriz_rechaza_por_libre_del_llm():
    """'por' ya NO es un Argumento(): el servidor lo fuerza a 'operador' (patron
    legal.py::_fn_cumplir_obligacion). Si el LLM intenta rellenarlo, es un
    argumento no declarado — honestidad del contrato ToolSpec."""
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["transicionar_directriz"].validar(
            {"d_id": "X", "a": "ACTIVA", "por": "el-llm-libre"})


def test_transicionar_directriz_acepta_motivo_opcional():
    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz({"id": "X", "regla": "r", "categoria": "LEGAL",
                                         "accion": "APTO"})
    r = _run("transicionar_directriz",
            {"d_id": "X", "a": "ACTIVA", "motivo": "lanzamiento"}, k=k)
    assert r["estado"] == "ACTIVA"


def test_transicionar_directriz_fuerza_por_operador_en_servidor():
    """Aunque el metodo real (CuboBrand.transicionar_directriz) no persiste 'por' en
    la directriz devuelta, el wrapper SIEMPRE lo llama con por='operador' — nunca un
    valor que el LLM pudiera inventar (verificado via monkeypatch del metodo real)."""
    import departments.brand.cubo_serie_d as cubo_mod
    capturado = {}
    original = cubo_mod.CuboBrand.transicionar_directriz

    def _espia(self, d_id, a, *, por, motivo=""):
        capturado["por"] = por
        return original(self, d_id, a, por=por, motivo=motivo)

    k = InMemoryKnowledge()
    CuboBrand(k, TENANT).alta_directriz({"id": "X", "regla": "r", "categoria": "LEGAL",
                                         "accion": "APTO"})
    cubo_mod.CuboBrand.transicionar_directriz = _espia
    try:
        _run("transicionar_directriz", {"d_id": "X", "a": "ACTIVA"}, k=k)
    finally:
        cubo_mod.CuboBrand.transicionar_directriz = original
    assert capturado["por"] == "operador"


# ── assets_vigente / assets_paleta / assets_logo ─────────────────────────────

def test_assets_vigente_lee_el_manifiesto_real():
    r = _run("assets_vigente", {})
    assert r["version"] == "1.0"
    assert r["paleta"]["primario"] == "#1F2933"
    assert r["n_logos"] == 1


def test_assets_paleta_coincide_con_asset_manager_real():
    r = _run("assets_paleta", {})
    assert r == AssetManager(TENANT).paleta()


def test_assets_logo_por_defecto():
    r = _run("assets_logo", {})
    assert r["logo"]["id"] == "logo_principal"
    assert r["logo"]["estado"] == "placeholder"


def test_assets_logo_inexistente_devuelve_none_no_excepcion():
    r = _run("assets_logo", {"logo_id": "no_existe"})
    assert r["logo"] is None


# ── strategist_* ─────────────────────────────────────────────────────────────

def test_strategist_posicionamiento_real():
    r = _run("strategist_posicionamiento", {})
    assert "sintetica de pruebas" in r["posicionamiento"]


def test_strategist_tono_real():
    r = _run("strategist_tono", {})
    assert r["descripcion"] == "Directo y sobrio, sin superlativos."


def test_strategist_valores_real():
    r = _run("strategist_valores", {})
    assert "honestidad" in r["valores"]


def test_strategist_encaja_veta_por_heuristica_sin_llm():
    r = _run("strategist_encaja",
            {"propuesta": "Ofrecemos resultados garantizados para todos", "usar_llm": False})
    assert r["encaja"] is False


def test_strategist_encaja_sin_conflicto_sin_llm():
    r = _run("strategist_encaja",
            {"propuesta": "Explicamos como funciona el producto", "usar_llm": False})
    assert r["encaja"] is True


# ── guardian_revisar (sin LLM real: semantic=None en el constructor del wrapper) ─

def test_guardian_revisar_aprueba_email_limpio():
    r = _run("guardian_revisar", {"asunto": "Repostería artesanal de Cieza", "cuerpo": CUERPO_OK})
    assert r["aprobado"], r["problemas"]


def test_guardian_revisar_detecta_palabra_prohibida_real():
    r = _run("guardian_revisar", {
        "asunto": "Oferta",
        "cuerpo": "Te ofrecemos el producto más barato del mercado. " * 6})
    assert not r["aprobado"]
    assert any("barato" in p for p in r["problemas"])


def test_guardian_revisar_rechaza_argumento_no_declarado():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["guardian_revisar"].validar({"asunto": "a", "cuerpo": "c", "lead_id": "L1"})


# ── voice_auditar (transcript vacio: camino real sin llamar a la API) ───────

def test_voice_auditar_transcript_vacio_no_llama_llm():
    r = _run("voice_auditar", {"texto_agente": ""})
    assert r["ok"] is False
    assert "vacío" in r["problemas"][0]


def test_voice_auditar_rechaza_falta_de_texto_agente():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["voice_auditar"].validar({})


# ── contexto_marca ────────────────────────────────────────────────────────────

def test_contexto_marca_compone_texto_real():
    r = _run("contexto_marca", {})
    assert "Posicionamiento:" in r["contexto_marca"]
    assert "honestidad" in r["contexto_marca"]


# ── director_revisar (REVERSIBLE: orquesta Guardian sin LLM, sin OpenGravity) ─

def test_director_revisar_aprueba_sin_campana_sin_comite():
    r = _run("director_revisar", {"asunto": "Repostería artesanal de Cieza", "cuerpo": CUERPO_OK})
    assert r["aprobado"] is True
    assert r["comite"] is None
    assert r["degradado"] is False


def test_director_revisar_campana_degrada_sin_opengravity_suscrito():
    r = _run("director_revisar", {
        "asunto": "Repostería artesanal de Cieza", "cuerpo": CUERPO_OK,
        "artifact_type": "campana", "usar_llm": False})
    assert r["degradado"] is True
    assert r["comite"] is None


def test_director_revisar_rechaza_falta_de_cuerpo():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["director_revisar"].validar({"asunto": "a"})
