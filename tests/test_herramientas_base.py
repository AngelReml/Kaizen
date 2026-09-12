# -*- coding: utf-8 -*-
"""Fase 4 — contrato de herramientas de director: aislamiento estricto por
cubo (un director jamas invoca la herramienta de otro, ni aunque el LLM la
nombre), validacion de argumentos honesta, y la frontera IRREVERSIBLE-* que
solo se dispara desde la aprobacion humana, nunca desde un turno de chat."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from panel_mando.herramientas.base import (ArgumentosInvalidos, Argumento,
                                            NoExisteHerramienta, ToolSpec,
                                            herramientas_para_prompt, invocar,
                                            invocar_aprobada)


def _spec(nombre="leer_algo", clase="LECTURA", fn=None, args=()):
    return ToolSpec(nombre=nombre, clase=clase, descripcion="d", argumentos=args,
                    fn=fn or (lambda **kw: {"ok": True, "kw": kw}))


def test_clase_invalida_rechazada_al_construir():
    with pytest.raises(ValueError):
        _spec(clase="INVENTADA")


def test_invocar_pasa_k_tenant_bitacora_y_argumentos_validados():
    reg = {"comercial": {"leer_algo": _spec(
        args=(Argumento("lead_id", "str", "id"),))}}
    r = invocar(reg, "comercial", "leer_algo", {"lead_id": "L1"},
               k="KNOW", tenant="laboratorio", bitacora="BIT")
    assert r["ok"] and r["kw"] == {"k": "KNOW", "tenant": "laboratorio",
                                   "bitacora": "BIT", "lead_id": "L1"}


def test_aislamiento_estricto_entre_cubos():
    """El director de marketing NO puede invocar una herramienta de comercial
    ni aunque el LLM escriba exactamente ese nombre — no hay fallback."""
    reg = {"comercial": {"solo_comercial": _spec("solo_comercial")},
           "marketing": {}}
    with pytest.raises(NoExisteHerramienta):
        invocar(reg, "marketing", "solo_comercial", {}, k=None, tenant="laboratorio")


def test_herramienta_inexistente_en_su_propio_cubo():
    reg = {"comercial": {}}
    with pytest.raises(NoExisteHerramienta):
        invocar(reg, "comercial", "no_existe", {}, k=None, tenant="laboratorio")


def test_argumento_no_declarado_rechazado():
    reg = {"ops": {"leer_algo": _spec(args=(Argumento("fecha", "str", "d"),))}}
    with pytest.raises(ArgumentosInvalidos):
        invocar(reg, "ops", "leer_algo", {"fecha": "2026-08-01", "intruso": "x"},
               k=None, tenant="laboratorio")


def test_argumento_obligatorio_ausente_rechazado():
    reg = {"ops": {"leer_algo": _spec(args=(Argumento("fecha", "str", "d"),))}}
    with pytest.raises(ArgumentosInvalidos):
        invocar(reg, "ops", "leer_algo", {}, k=None, tenant="laboratorio")


def test_argumento_opcional_ausente_no_rompe():
    reg = {"ops": {"leer_algo": _spec(
        args=(Argumento("nota", "str", "d", obligatorio=False),))}}
    r = invocar(reg, "ops", "leer_algo", {}, k=None, tenant="laboratorio")
    assert "nota" not in r["kw"]


def test_tipo_incorrecto_rechazado_no_coercion_silenciosa():
    reg = {"finanzas": {"leer_algo": _spec(args=(Argumento("dias", "int", "d"),))}}
    with pytest.raises(ArgumentosInvalidos):
        invocar(reg, "finanzas", "leer_algo", {"dias": "no-es-numero"},
               k=None, tenant="laboratorio")


def test_bool_acepta_bool_real_y_texto_true_false():
    reg = {"ops": {"leer_algo": _spec(args=(Argumento("urgente", "bool", "d"),))}}
    r1 = invocar(reg, "ops", "leer_algo", {"urgente": True}, k=None, tenant="laboratorio")
    r2 = invocar(reg, "ops", "leer_algo", {"urgente": "false"}, k=None, tenant="laboratorio")
    r3 = invocar(reg, "ops", "leer_algo", {"urgente": "TRUE"}, k=None, tenant="laboratorio")
    assert r1["kw"]["urgente"] is True
    assert r2["kw"]["urgente"] is False
    assert r3["kw"]["urgente"] is True


def test_bool_rechaza_texto_no_true_false_sin_coercion_silenciosa():
    """Antes del fix, bool("false") en Python es True: cualquier string no
    vacio colaba como verdadero. Ahora un texto que no sea 'true'/'false' se
    rechaza en vez de colarse como verdadero."""
    reg = {"ops": {"leer_algo": _spec(args=(Argumento("urgente", "bool", "d"),))}}
    with pytest.raises(ArgumentosInvalidos):
        invocar(reg, "ops", "leer_algo", {"urgente": "no"}, k=None, tenant="laboratorio")


def test_irreversible_interna_no_se_invoca_directo_desde_chat():
    reg = {"comercial": {"crear_compromiso": _spec("crear_compromiso",
                                                    clase="IRREVERSIBLE-INTERNA")}}
    with pytest.raises(ArgumentosInvalidos):
        invocar(reg, "comercial", "crear_compromiso", {}, k=None, tenant="laboratorio")


def test_irreversible_externa_no_se_invoca_directo_desde_chat():
    reg = {"comercial": {"enviar_email": _spec("enviar_email",
                                               clase="IRREVERSIBLE-EXTERNA")}}
    with pytest.raises(ArgumentosInvalidos):
        invocar(reg, "comercial", "enviar_email", {}, k=None, tenant="laboratorio")


def test_invocar_aprobada_dispara_irreversible_interna():
    reg = {"comercial": {"crear_compromiso": _spec("crear_compromiso",
                                                    clase="IRREVERSIBLE-INTERNA")}}
    r = invocar_aprobada(reg, "comercial", "crear_compromiso", {},
                         k=None, tenant="laboratorio")
    assert r["ok"]


def test_invocar_aprobada_rechaza_irreversible_externa():
    """R2: el chat no dispara nada al mundo real todavia — frontera deliberada."""
    reg = {"comercial": {"enviar_email": _spec("enviar_email",
                                               clase="IRREVERSIBLE-EXTERNA")}}
    with pytest.raises(ArgumentosInvalidos):
        invocar_aprobada(reg, "comercial", "enviar_email", {},
                         k=None, tenant="laboratorio")


def test_invocar_aprobada_rechaza_lectura_y_reversible():
    reg = {"ops": {"leer": _spec("leer", clase="LECTURA")}}
    with pytest.raises(ArgumentosInvalidos):
        invocar_aprobada(reg, "ops", "leer", {}, k=None, tenant="laboratorio")


def test_herramientas_para_prompt_filtra_por_clase_y_cubo():
    reg = {"ops": {"a": _spec("a", clase="LECTURA"),
                   "b": _spec("b", clase="REVERSIBLE")},
           "finanzas": {"c": _spec("c", clase="LECTURA")}}
    txt = herramientas_para_prompt(reg, "ops", clases=("LECTURA",))
    assert "- a " in txt or txt.startswith("- a")
    assert "b" not in txt.split("\n")[0]           # b es REVERSIBLE, no listada
    assert "c" not in txt                          # c es de otro cubo


def test_herramientas_para_prompt_vacio_es_honesto():
    txt = herramientas_para_prompt({}, "legal", clases=("LECTURA",))
    assert "ninguna" in txt.lower()


def test_registro_real_carga_sin_reventar():
    """El agregador de panel_mando/herramientas/__init__.py debe cargar aunque
    algunos cubos aun no tengan fichero propio (carga defensiva por cubo)."""
    from panel_mando import herramientas as H
    assert set(H.REGISTRO.keys()) == {"comercial", "brand", "ops", "finanzas",
                                      "marketing", "inteligencia", "legal", "qa",
                                      "rrhh", "customer_success"}
    for cubo, specs in H.REGISTRO.items():
        for nombre, spec in specs.items():
            assert spec.nombre == nombre
            assert spec.clase in H.CLASES_HERRAMIENTA
