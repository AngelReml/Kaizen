# -*- coding: utf-8 -*-
"""Fase 4 — herramientas REALES del cubo Finanzas: cada ToolSpec se prueba
construyendo el objeto real (FinanzasDepartment/Liquidador/Conciliador/MotorSIF)
contra InMemoryKnowledge y el tenant sintetico 'laboratorio' (R-TENANT),
invocando `fn` de verdad y verificando el resultado real — mas la validacion
de argumentos honesta (ArgumentosInvalidos) para lo que debe rechazarse."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from departments.finanzas import cubo_serie_d as F
from panel_mando.herramientas.base import ArgumentosInvalidos
from panel_mando.herramientas.finanzas import HERRAMIENTAS

TENANT = "laboratorio"        # tenant sintetico de laboratorio (R-TENANT)


def _run(nombre, argumentos, *, k=None, tenant=TENANT, bitacora=None):
    spec = HERRAMIENTAS[nombre]
    limpios = spec.validar(argumentos)
    return spec.fn(k=k, tenant=tenant, bitacora=bitacora, **limpios)


def _sembrar_gastos(k):
    ts = datetime.now(timezone.utc).isoformat()
    for i, eur in enumerate([0.5, 1.0, 0.3]):
        k.add(TENANT, "gasto", f"g{i}",
              {"id": "x", "ts": ts, "modelo": "haiku", "usd": eur, "eur": eur,
               "tokens_in": 1, "tokens_out": 1, "accion": f"a{i}", "categoria": "otros",
               "company": TENANT})
    return k


# ── inventario de herramientas ──────────────────────────────────────────────

def test_no_wireadas_por_gate_autoafirmable_o_frontera_r2():
    """confirmar/anular tienen el gate `por != 'operador'` autoafirmable; emitir/remitir
    son IRREVERSIBLE-EXTERNA (frontera R2) — ninguna de las cuatro esta wireada."""
    for nombre in ("conciliador_confirmar", "motor_sif_emitir", "motor_sif_anular",
                  "motor_sif_remitir", "emitir", "anular", "remitir", "confirmar"):
        assert nombre not in HERRAMIENTAS


def test_todas_las_specs_tienen_nombre_consistente_y_clase_valida():
    for nombre, spec in HERRAMIENTAS.items():
        assert spec.nombre == nombre
        assert spec.clase in ("LECTURA", "REVERSIBLE", "IRREVERSIBLE-INTERNA",
                              "IRREVERSIBLE-EXTERNA")
        assert spec.clase != "IRREVERSIBLE-EXTERNA"      # frontera R2: ninguna aqui


# ── department_handle ────────────────────────────────────────────────────────

def test_department_handle_ejecuta_de_verdad_y_elige_herramienta():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("department_handle", {"intent": "¿cuánto llevamos gastado este mes?"}, k=k)
    assert r["ok"] is True
    assert r["data"]["herramienta"] == "consultar_gasto"
    assert "1.8" in r["data"]["respuesta"] or "1.80" in r["data"]["respuesta"]


def test_department_handle_rechaza_argumento_no_declarado():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["department_handle"].validar({"intent": "x", "intruso": "y"})


def test_department_handle_rechaza_falta_de_intent():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["department_handle"].validar({})


# ── consultar_gasto ───────────────────────────────────────────────────────────

def test_consultar_gasto_suma_real():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("consultar_gasto", {}, k=k)
    assert r["total_eur"] == pytest.approx(1.8)
    assert r["n_acciones"] == 3


def test_consultar_gasto_filtra_por_categoria_inexistente():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("consultar_gasto", {"periodo": "mes", "categoria": "no_existe"}, k=k)
    assert r["total_eur"] == 0.0
    assert r["n_acciones"] == 0


def test_consultar_gasto_rechaza_argumento_desconocido():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["consultar_gasto"].validar({"periodo": "mes", "intruso": "x"})


# ── proyectar_quema ───────────────────────────────────────────────────────────

def test_proyectar_quema_calcula_runway_con_presupuesto():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("proyectar_quema", {"dias": 10, "presupuesto_mensual": 16.0}, k=k)
    assert r["gasto_diario_medio"] > 0
    assert r["dias_runway_si_no_recargas"] is not None


def test_proyectar_quema_sin_presupuesto_no_da_runway():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("proyectar_quema", {}, k=k)
    assert r["dias_runway_si_no_recargas"] is None


def test_proyectar_quema_rechaza_dias_no_numerico():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["proyectar_quema"].validar({"dias": "muchos"})


# ── comparar_periodos ─────────────────────────────────────────────────────────

def test_comparar_periodos_variacion_real():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("comparar_periodos", {"p1": "semana_anterior", "p2": "semana"}, k=k)
    assert r["p2_total"] == pytest.approx(1.8)
    assert r["p1_total"] == 0.0


def test_comparar_periodos_rechaza_falta_de_p2():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["comparar_periodos"].validar({"p1": "mes"})


# ── top_acciones_caras ────────────────────────────────────────────────────────

def test_top_acciones_caras_orden_real():
    k = _sembrar_gastos(InMemoryKnowledge())
    r = _run("top_acciones_caras", {"n": 2}, k=k)
    assert len(r["top"]) == 2
    assert r["top"][0]["eur"] >= r["top"][1]["eur"]


def test_top_acciones_caras_sin_datos_lista_vacia():
    k = InMemoryKnowledge()
    r = _run("top_acciones_caras", {}, k=k)
    assert r["top"] == []


# ── detectar_anomalia ─────────────────────────────────────────────────────────

def test_detectar_anomalia_encuentra_el_gasto_atipico_real():
    k = InMemoryKnowledge()
    ts = datetime.now(timezone.utc).isoformat()
    for i, eur in enumerate([0.1, 0.1, 0.1, 0.12, 50.0]):
        k.add(TENANT, "gasto", f"g{i}",
              {"id": "x", "ts": ts, "modelo": "haiku", "usd": eur, "eur": eur,
               "tokens_in": 1, "tokens_out": 1, "accion": f"a{i}", "categoria": "otros",
               "company": TENANT})
    r = _run("detectar_anomalia", {"sensibilidad": 1.0}, k=k)
    assert any(a["eur"] == 50.0 for a in r["anomalias"])


def test_detectar_anomalia_pocos_datos_no_revienta():
    k = _sembrar_gastos(InMemoryKnowledge())   # solo 3 gastos: < 3 no aplica, aqui son 3
    r = _run("detectar_anomalia", {}, k=k)
    assert isinstance(r["anomalias"], list)


# ── conciliador_proponer / conciliador_aging ─────────────────────────────────

def _sembrar_factura(k, *, fecha_emision, importe_total=121.0, estado_cobro="PENDIENTE"):
    k.add(TENANT, "factura", "F1", {"factura_id": "F1", "importe_total": importe_total,
                                    "fecha_emision": fecha_emision, "estado": "EMITIDA",
                                    "estado_cobro": estado_cobro})


def test_conciliador_proponer_empareja_de_verdad():
    k = InMemoryKnowledge()
    ts = datetime.now(timezone.utc).isoformat()
    _sembrar_factura(k, fecha_emision=ts)
    con = F.Conciliador(k, TENANT)
    con.importar_csv("fecha,concepto,importe\n2026-07-09,transferencia,121.00\n")
    r = _run("conciliador_proponer", {}, k=k)
    assert len(r["propuestas"]) == 1
    assert r["propuestas"][0]["factura_ref"] == "F1"
    assert r["propuestas"][0]["delta"] == 0.0


def test_conciliador_proponer_sin_datos_lista_vacia():
    k = InMemoryKnowledge()
    r = _run("conciliador_proponer", {}, k=k)
    assert r["propuestas"] == []


def test_conciliador_aging_calcula_dias_reales():
    k = InMemoryKnowledge()
    hace_10_dias = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    _sembrar_factura(k, fecha_emision=hace_10_dias)
    r = _run("conciliador_aging", {}, k=k)
    assert len(r["aging"]) == 1
    assert r["aging"][0]["factura_ref"] == "F1"
    assert r["aging"][0]["dias_pendiente"] >= 10


def test_conciliador_aging_factura_cobrada_no_aparece():
    k = InMemoryKnowledge()
    ts = datetime.now(timezone.utc).isoformat()
    _sembrar_factura(k, fecha_emision=ts, estado_cobro="COBRADO")
    r = _run("conciliador_aging", {}, k=k)
    assert r["aging"] == []


# ── verificar_cadena_sif / nif_valido ─────────────────────────────────────────

def test_verificar_cadena_sif_integra_de_verdad():
    k = InMemoryKnowledge()
    sif = F.MotorSIF(k, TENANT)
    for i in range(3):
        sif.emitir(nif_obligado="SINTETICO-000A", nif_destinatario="SINTETICO-B", serie="A",
                  importe_neto=10.0 + i)
    r = _run("verificar_cadena_sif", {"nif": "SINTETICO-000A"}, k=k)
    assert r == {"integra": True, "registros": 3}


def test_verificar_cadena_sif_detecta_manipulacion_real():
    k = InMemoryKnowledge()
    sif = F.MotorSIF(k, TENANT)
    sif.emitir(nif_obligado="SINTETICO-000A", nif_destinatario="SINTETICO-B", serie="A",
              importe_neto=10.0)
    reg = k.get(TENANT, "sif_registro", "SINTETICO-000A::00000001")
    reg["importe_neto"] = 9999.0
    k.add(TENANT, "sif_registro", "SINTETICO-000A::00000001", reg)
    r = _run("verificar_cadena_sif", {"nif": "SINTETICO-000A"}, k=k)
    assert r["integra"] is False


def test_nif_valido_digito_de_control_real():
    assert _run("nif_valido", {"nif": "12345678Z"}, k=None) == {"nif": "12345678Z", "valido": True}
    assert _run("nif_valido", {"nif": "12345678A"}, k=None) == {"nif": "12345678A", "valido": False}


def test_nif_valido_rechaza_falta_de_nif():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["nif_valido"].validar({})


# ── liquidador_calcular (REVERSIBLE) ─────────────────────────────────────────

def _sembrar_pedidos(k):
    k.add(TENANT, "pedido_atribuido", "ped1",
         {"pedido_id": "ped1", "estado": "ATRIBUIDO", "via": "DIRECTA",
          "importe_bruto": 100.0, "ts": "2026-07-05T10:00:00+00:00"})
    k.add(TENANT, "pedido_atribuido", "ped2",
         {"pedido_id": "ped2", "estado": "ATRIBUIDO", "via": "REPETICION",
          "importe_bruto": 50.0, "ts": "2026-07-06T10:00:00+00:00"})
    k.add(TENANT, "pedido_atribuido", "ped3",
         {"pedido_id": "ped3", "estado": "PENDIENTE_VALIDACION", "via": "REGISTRO_EXTERNO",
          "importe_bruto": 999.0, "ts": "2026-07-07T10:00:00+00:00"})


def test_liquidador_calcular_reproducible_con_costes_json():
    k = InMemoryKnowledge()
    _sembrar_pedidos(k)
    r1 = _run("liquidador_calcular",
             {"periodo": "2026-07", "costes_directos": '{"ped1": 40.0, "ped2": 10.0}'}, k=k)
    r2 = _run("liquidador_calcular",
             {"periodo": "2026-07", "costes_directos": '{"ped1": 40.0, "ped2": 10.0}'}, k=k)
    assert r1["hash_liquidacion"] == r2["hash_liquidacion"]
    assert r1["total_comision"] == 50.0
    assert r1["excluidos_pendientes"] == ["ped3"]


def test_liquidador_calcular_sin_costes_usa_vacio_por_defecto():
    k = InMemoryKnowledge()
    _sembrar_pedidos(k)
    r = _run("liquidador_calcular", {"periodo": "2026-07"}, k=k)
    # sin costes_directos: beneficio_neto == importe_bruto
    assert r["total_atribuible"] == pytest.approx((100.0 + 50.0) * 0.5 * 2)


def test_liquidador_calcular_rechaza_falta_de_periodo():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["liquidador_calcular"].validar({})


# ── conciliador_importar_csv (REVERSIBLE) ────────────────────────────────────

def test_conciliador_importar_csv_persiste_movimientos_reales():
    k = InMemoryKnowledge()
    csv_txt = "fecha,concepto,importe\n2026-07-09,transferencia,121.00\n2026-07-10,pago,5.50\n"
    r = _run("conciliador_importar_csv", {"contenido_csv": csv_txt}, k=k)
    assert len(r["movimientos"]) == 2
    assert {m["estado"] for m in r["movimientos"]} == {"SIN_CONCILIAR"}
    guardados = k.all(TENANT, "movimiento_banco")
    assert len(guardados) == 2


def test_conciliador_importar_csv_rechaza_falta_de_contenido():
    with pytest.raises(ArgumentosInvalidos):
        HERRAMIENTAS["conciliador_importar_csv"].validar({})
