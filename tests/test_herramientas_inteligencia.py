# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del cubo Inteligencia: cada ToolSpec invoca el
objeto real de departments/inteligencia/ (CuboInteligencia, InteligenciaDepartment,
departments.inteligencia.herramientas), no un doble de prueba. R-TENANT: tenant
sintetico 'laboratorio', jamas uno real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora, Sobre
from departments.inteligencia.cubo_serie_d import CuboInteligencia
from panel_mando.herramientas import base as B
from panel_mando.herramientas import inteligencia as I

TENANT = "laboratorio"


@pytest.fixture()
def k():
    return InMemoryKnowledge()


@pytest.fixture()
def bitacora(k):
    return Bitacora(k, TENANT, fecha_alta="2026-07-10")


def _invocar(nombre, argumentos, *, k, bitacora=None):
    return B.invocar({"inteligencia": I.HERRAMIENTAS}, "inteligencia", nombre, argumentos,
                     k=k, tenant=TENANT, bitacora=bitacora)


# ── patron ───────────────────────────────────────────────────────────────

def test_patron_real_calcula_media_y_desv(k, bitacora):
    r = _invocar("patron", {"metrica": "conversion", "valores": "0.1, 0.2, 0.3"},
                 k=k, bitacora=bitacora)
    assert r["media"] == 0.2
    assert r["n"] == 3


def test_patron_sin_valores_degradacion_elegante(k):
    r = _invocar("patron", {"metrica": "conversion", "valores": ""}, k=k)
    assert "SIN_DATOS" in r["estado"]


def test_patron_rechaza_argumento_no_declarado(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("patron", {"metrica": "x", "valores": "1,2", "intruso": "no"}, k=k)


def test_patron_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("patron", {"metrica": "x"}, k=k)


# ── detectar (REVERSIBLE) ────────────────────────────────────────────────

def test_detectar_sin_umbral_no_genera_alerta(k, bitacora):
    r = _invocar("detectar", {"metrica": "conversion", "valor": 0.5}, k=k, bitacora=bitacora)
    assert r["alerta"] is None


def test_detectar_fuera_de_rango_crea_alerta_real(k, bitacora):
    i = CuboInteligencia(k, TENANT, bitacora=bitacora)
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    r = _invocar("detectar", {"metrica": "conversion", "valor": 0.30}, k=k, bitacora=bitacora)
    assert r["severidad"] == "CRITICA"
    assert k.get(TENANT, "alerta", r["alerta_id"]) is not None


def test_detectar_rechaza_tipo_incorrecto(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("detectar", {"metrica": "x", "valor": "no-es-numero"}, k=k)


# ── resolver_alerta (REVERSIBLE) ─────────────────────────────────────────

def test_resolver_alerta_real_transiciona_estado(k, bitacora):
    i = CuboInteligencia(k, TENANT, bitacora=bitacora)
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    a = i.detectar("conversion", 0.30)
    r = _invocar("resolver_alerta",
                 {"alerta_id": a["alerta_id"], "veredicto": "DESCARTADA", "por": "operador"},
                 k=k, bitacora=bitacora)
    assert r["estado"] == "DESCARTADA"
    assert k.get(TENANT, "alerta", a["alerta_id"])["estado"] == "DESCARTADA"


def test_resolver_alerta_inexistente_deja_subir_la_excepcion(k):
    with pytest.raises(ValueError):
        _invocar("resolver_alerta",
                 {"alerta_id": "no-existe", "veredicto": "DESCARTADA", "por": "operador"}, k=k)


def test_resolver_alerta_rechaza_argumento_desconocido(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("resolver_alerta",
                 {"alerta_id": "x", "veredicto": "DESCARTADA", "por": "operador", "extra": 1},
                 k=k)


# ── tasa_falsos_positivos ────────────────────────────────────────────────

def test_tasa_falsos_positivos_real(k, bitacora):
    i = CuboInteligencia(k, TENANT, bitacora=bitacora)
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    a = i.detectar("conversion", 0.30)
    i.resolver_alerta(a["alerta_id"], veredicto="DESCARTADA", por="operador")
    r = _invocar("tasa_falsos_positivos", {}, k=k, bitacora=bitacora)
    assert r["medible"] is False                      # n<15: informativa (R-17)
    assert r["criticas_falsas"] == 1


# ── correlacionar ────────────────────────────────────────────────────────

def test_correlacionar_real_encuentra_evento_cercano(k, bitacora):
    i = CuboInteligencia(k, TENANT, bitacora=bitacora)
    bitacora.publicar(Sobre(tenant_id=TENANT, tipo="marketing.campana.ajustada",
                            payload={"cambio": "PAUSA"}, origen="marketing.cubo"))
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    a = i.detectar("conversion", 0.30)
    r = _invocar("correlacionar", {"alerta_id": a["alerta_id"]}, k=k, bitacora=bitacora)
    assert r["confianza"] == "ALTA"
    assert "NO causalidad" in r["narrativa"]


def test_correlacionar_sin_candidatos_devuelve_dict_no_none(k, bitacora):
    i = CuboInteligencia(k, TENANT, bitacora=bitacora)
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    a = i.detectar("conversion", 0.30)
    r = _invocar("correlacionar", {"alerta_id": a["alerta_id"], "ventana_horas": 48},
                 k=k, bitacora=bitacora)
    assert r["correlacion"] is None                   # nunca None crudo: siempre dict


# ── reporte_ejecutivo ────────────────────────────────────────────────────

def test_reporte_ejecutivo_real(k, bitacora):
    i = CuboInteligencia(k, TENANT, bitacora=bitacora)
    i.definir_umbral("conversion", 0.08, 0.12, por="operador")
    i.detectar("conversion", 0.30)
    r = _invocar("reporte_ejecutivo", {"periodo": "2026-07"}, k=k, bitacora=bitacora)
    assert r["alertas"] == 1
    assert "operador" in r["resumen"]


# ── observar (REVERSIBLE) ────────────────────────────────────────────────

def test_observar_real_registra_senal(k, bitacora):
    r = _invocar("observar",
                 {"tipo": "competidor", "tema": "bajada de precio", "fuente": "web",
                  "relevancia": 5, "detalle": "detalle x"},
                 k=k, bitacora=bitacora)
    assert r["tipo"] == "competidor"
    assert r["relevancia"] == 5
    guardada = k.get(TENANT, "senal_mercado", r["id"])
    assert guardada is not None and guardada["tema"] == "bajada de precio"


def test_observar_opcionales_usan_default(k):
    r = _invocar("observar", {"tipo": "tendencia", "tema": "masa madre"}, k=k)
    assert r["fuente"] == ""
    assert r["relevancia"] == 3


def test_observar_rechaza_falta_obligatorio(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("observar", {"tema": "sin tipo"}, k=k)


# ── briefing ──────────────────────────────────────────────────────────────

def test_briefing_real_agrega_senales(k):
    h = __import__("departments.inteligencia.herramientas", fromlist=["x"])
    h.registrar_senal(k, TENANT, tipo="competidor", tema="rival baja precio",
                      fuente="web", relevancia=5)
    r = _invocar("briefing", {}, k=k)
    assert r["n_senales"] == 1
    assert len(r["alertas_competencia"]) == 1


# ── listar_senales / listar_tendencias ───────────────────────────────────

def test_listar_senales_real_lee_del_knowledge(k):
    from departments.inteligencia import herramientas as h
    h.registrar_senal(k, TENANT, tipo="precio", tema="subida proveedor", fuente="email")
    r = _invocar("listar_senales", {}, k=k)
    assert len(r["senales"]) == 1 and r["senales"][0]["tipo"] == "precio"
    r_filtro = _invocar("listar_senales", {"tipo": "competidor"}, k=k)
    assert r_filtro["senales"] == []


def test_listar_tendencias_real_agrupa_por_repeticion(k):
    from departments.inteligencia import herramientas as h
    for _ in range(3):
        h.registrar_senal(k, TENANT, tipo="tendencia", tema="masa madre en auge")
    r = _invocar("listar_tendencias", {}, k=k)
    assert len(r["tendencias"]) == 1
    assert r["tendencias"][0]["repeticiones"] == 3


# ── sanity: todas las specs declaran su propio nombre y clase valida ────

def test_todas_las_specs_declaran_su_propio_nombre_y_clase_valida():
    for nombre, spec in I.HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in B.CLASES_HERRAMIENTA


def test_solo_definir_umbral_alerta_es_irreversible():
    """Este cubo tiene una unica IRREVERSIBLE-INTERNA: definir_umbral_alerta (fuerza
    por='operador' en servidor). El resto sigue siendo LECTURA/REVERSIBLE."""
    clases = {spec.clase for spec in I.HERRAMIENTAS.values()}
    assert clases <= {"LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA"}
    irreversibles = {n for n, s in I.HERRAMIENTAS.items() if s.clase == "IRREVERSIBLE-INTERNA"}
    assert irreversibles == {"definir_umbral_alerta"}


# ── definir_umbral_alerta (IRREVERSIBLE-INTERNA) ─────────────────────────

def test_definir_umbral_alerta_no_se_invoca_directo(k):
    with pytest.raises(B.ArgumentosInvalidos):
        _invocar("definir_umbral_alerta",
                 {"metrica": "conversion", "minimo": 0.08, "maximo": 0.12}, k=k)


def test_definir_umbral_alerta_rechaza_por_libre_del_llm(k):
    """'por' no es un Argumento(): el servidor lo fuerza a 'operador', nunca el LLM."""
    with pytest.raises(B.ArgumentosInvalidos):
        I.HERRAMIENTAS["definir_umbral_alerta"].validar(
            {"metrica": "conversion", "minimo": 0.08, "maximo": 0.12, "por": "el-llm-libre"})


def test_definir_umbral_alerta_invocar_aprobada_deja_detectar_funcionar(k, bitacora):
    """Antes de este fix, detectar() SIEMPRE devolvia None: no habia forma de que un
    umbral llegara a existir. invocar_aprobada (tras aprobacion humana real) lo fuerza
    por='operador' en servidor y ahora detectar() SI puede emitir una alerta real."""
    r = B.invocar_aprobada({"inteligencia": I.HERRAMIENTAS}, "inteligencia",
                           "definir_umbral_alerta",
                           {"metrica": "conversion", "minimo": 0.08, "maximo": 0.12},
                           k=k, tenant=TENANT, bitacora=bitacora)
    assert r["metrica"] == "conversion" and r["version"] == 1
    assert k.get(TENANT, "umbral", "conversion") is not None
    alerta = _invocar("detectar", {"metrica": "conversion", "valor": 0.30}, k=k, bitacora=bitacora)
    assert alerta["severidad"] == "CRITICA"
