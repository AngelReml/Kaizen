"""Cubo Finanzas (D04): liquidacion reproducible (FA0), conciliacion+aging (FA2),
motor SIF nucleo: cadena por NIF (13.4), exactamente-una-numeracion, anulacion sin
borrado (13.7), remision con reintentos que jamas bloquea (R-01, 13.5), NIF valido."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from departments.finanzas import cubo_serie_d as F

NIF_SINT = "SINTETICO-000A"


@pytest.fixture()
def fin():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    return k, b


def _sembrar_pedidos(k):
    k.add("t1", "pedido_atribuido", "ped1", {"pedido_id": "ped1", "estado": "ATRIBUIDO",
                                             "via": "DIRECTA", "importe_bruto": 100.0,
                                             "ts": "2026-07-05T10:00:00+00:00"})
    k.add("t1", "pedido_atribuido", "ped2", {"pedido_id": "ped2", "estado": "ATRIBUIDO",
                                             "via": "REPETICION", "importe_bruto": 50.0,
                                             "ts": "2026-07-06T10:00:00+00:00"})
    k.add("t1", "pedido_atribuido", "ped3", {"pedido_id": "ped3", "estado": "PENDIENTE_VALIDACION",
                                             "via": "REGISTRO_EXTERNO", "importe_bruto": 999.0,
                                             "ts": "2026-07-07T10:00:00+00:00"})


def test_liquidacion_reproducible_y_pendientes_fuera(fin):
    k, b = fin
    _sembrar_pedidos(k)
    liq = F.Liquidador(k, "t1", bitacora=b)
    costes = {"ped1": 40.0, "ped2": 10.0}
    l1 = liq.calcular("2026-07", costes_directos=costes)
    l2 = liq.calcular("2026-07", costes_directos=costes)
    assert l1["hash_liquidacion"] == l2["hash_liquidacion"]      # recomputar = identico
    assert l1["total_comision"] == 50.0                           # (60+40)*0.5
    assert l1["excluidos_pendientes"] == ["ped3"]                 # PENDIENTE fuera con informe
    assert b.verificar()["integra"] is True


def test_conciliacion_manual_y_aging(fin):
    k, _ = fin
    sif = F.MotorSIF(k, "t1")
    sif.emitir(nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="A",
               importe_neto=100.0)
    con = F.Conciliador(k, "t1")
    con.importar_csv("fecha,concepto,importe\n2026-07-09,transferencia,121.00\n")
    props = con.proponer()
    assert len(props) == 1 and props[0]["delta"] == 0.0
    with pytest.raises(PermissionError):
        con.confirmar(props[0], por="sistema")                    # humano confirma
    con.confirmar(props[0], por="operador")
    assert con.aging() == []                                      # cobrada: sin aging


def test_cadena_sif_por_nif_verificable_e_independiente(fin):
    k, _ = fin
    sif = F.MotorSIF(k, "t1")
    for i in range(5):
        sif.emitir(nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="A",
                   importe_neto=10.0 + i)
    v = sif.verificar_cadena(NIF_SINT)
    assert v == {"integra": True, "registros": 5}
    reg = k.get("t1", "sif_registro", f"{NIF_SINT}::00000002")
    reg["importe_neto"] = 9999.0                                  # manipulacion en frio
    k.add("t1", "sif_registro", f"{NIF_SINT}::00000002", reg)
    v2 = sif.verificar_cadena(NIF_SINT)
    assert v2["integra"] is False and v2["punto"] == f"{NIF_SINT}::00000002"


def test_anulacion_encadena_y_borrado_no_existe(fin):
    k, _ = fin
    sif = F.MotorSIF(k, "t1")
    r = sif.emitir(nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="A",
                   importe_neto=100.0)
    with pytest.raises(PermissionError):
        sif.anular(r["rfa_ref"], motivo="error", por="sistema")   # humano SIEMPRE
    sif.anular(r["rfa_ref"], motivo="error de importe", por="operador")
    assert sif.verificar_cadena(NIF_SINT)["registros"] == 2       # la original SIGUE
    assert k.get("t1", "sif_registro", r["rfa_ref"])["tipo_registro"] == "ALTA"
    # 13.7: borrado imposible por construccion — no existe ruta de borrado en el modulo
    assert not any("borrar" in n or "delete" in n for n in dir(F.MotorSIF))


def test_remision_fallida_no_bloquea_emision_r01(fin):
    k, _ = fin
    sim = F.AEATSimulador(fallos_antes_de_aceptar=99)             # AEAT caida
    sif = F.MotorSIF(k, "t1", remisor=sim)
    r = sif.emitir(nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="A",
                   importe_neto=100.0)
    assert r["remision"]["codigo"] == "PENDIENTE_REINTENTO"       # no aceptada...
    r2 = sif.emitir(nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="A",
                    importe_neto=200.0)                           # ...y se sigue emitiendo
    assert r2["factura_id"].endswith("000002")
    assert sif.verificar_cadena(NIF_SINT)["integra"] is True


def test_validacion_estructural_nif_e_incompleta(fin):
    k, _ = fin
    sif = F.MotorSIF(k, "t1")
    assert F.nif_valido("12345678Z") is True                      # digito de control OK
    assert F.nif_valido("12345678A") is False
    with pytest.raises(ValueError, match="NIF_INVALIDO"):
        sif.emitir(nif_obligado="99999X", nif_destinatario="SINTETICO-B", serie="A",
                   importe_neto=10.0)
    with pytest.raises(ValueError, match="INCOMPLETA"):
        sif.emitir(nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="",
                   importe_neto=10.0)


def test_motor_marcado_no_conforme_hasta_fb0():
    assert F.NO_CONFORME_TODAVIA is True                          # honestidad fisica
    r = F.MotorSIF(InMemoryKnowledge(), "t1").emitir(
        nif_obligado=NIF_SINT, nif_destinatario="SINTETICO-B", serie="A", importe_neto=10.0)
    reg_ref = r["rfa_ref"]
