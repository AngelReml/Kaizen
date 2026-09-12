"""Bloque D00-B5: cola unificada, claim atomico, caducidad R-13, candado de autonomia.
Bateria 13.6: carreras de doble-ejecucion y aprobar-luego-revocar; relajacion rechazada."""
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core.aprobaciones import ColaSustrato, TransicionAprobacionInvalida, cambiar_nivel


@pytest.fixture()
def cola():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    return ColaSustrato(k, "t1", bitacora=b), k, b


def test_fsm_camino_feliz_con_eventos(cola):
    c, k, _ = cola
    n = c.solicitar(cubo="comercial", accion="enviar email", clase="IRREVERSIBLE-EXTERNA",
                    contenido_ref="borrador_1")
    c.aprobar(n["id"], por="operador")
    hechos = []
    c.ejecutar(n["id"], lambda nodo: hechos.append(nodo["id"]))
    assert hechos == [n["id"]]
    assert c._get(n["id"])["estado"] == "EJECUTADA"
    tipos = [e["tipo"] for e in k.all("t1", "evento").values()]
    assert tipos.count("plataforma.aprobacion.solicitada") == 1
    assert "plataforma.aprobacion.concedida" in tipos


def test_claim_atomico_exactamente_una_vez(cola):
    c, _, _ = cola
    n = c.solicitar(cubo="comercial", accion="enviar", clase="IRREVERSIBLE-EXTERNA")
    c.aprobar(n["id"], por="operador")
    ejecuciones, errores = [], []

    def intentar():
        try:
            c.ejecutar(n["id"], lambda nodo: ejecuciones.append(1))
        except TransicionAprobacionInvalida as e:
            errores.append(e)

    hilos = [threading.Thread(target=intentar) for _ in range(6)]
    for h in hilos: h.start()
    for h in hilos: h.join()
    assert len(ejecuciones) == 1 and len(errores) == 5     # exactamente-una-vez (13.6)


def test_revocacion_gana_si_llega_antes_del_claim(cola):
    c, _, _ = cola
    n = c.solicitar(cubo="comercial", accion="enviar", clase="IRREVERSIBLE-EXTERNA")
    c.aprobar(n["id"], por="operador")
    c.revocar(n["id"], por="operador")
    with pytest.raises(TransicionAprobacionInvalida):
        c.ejecutar(n["id"], lambda nodo: None)             # revocada: no se ejecuta
    assert c._get(n["id"])["estado"] == "REVOCADA"


def test_caducidad_72h_r13(cola):
    c, _, _ = cola
    ayer3 = datetime.now(timezone.utc) - timedelta(hours=80)
    rev = c.solicitar(cubo="ops", accion="reordenar cola", clase="REVERSIBLE", ahora=ayer3)
    ext = c.solicitar(cubo="comercial", accion="enviar email", clase="IRREVERSIBLE-EXTERNA",
                      ahora=ayer3)
    c.barrer_caducadas()
    assert c._get(rev["id"])["estado"] == "CADUCADA" and c._get(rev["id"])["reencolada"] is True
    assert c._get(ext["id"])["estado"] == "CADUCADA" and not c._get(ext["id"]).get("reencolada")
    reenc = [x for x in c.listar("PENDIENTE") if x.get("reencolada_de") == rev["id"]]
    assert len(reenc) == 1                                  # REVERSIBLE: reencolada UNA vez
    # segunda caducidad de la reencolada → NO se re-reencola (R-13)
    reenc[0]["creada_en"] = (datetime.now(timezone.utc) - timedelta(hours=80)).isoformat()
    c._put(reenc[0])
    c.barrer_caducadas()
    assert c._get(reenc[0]["id"])["estado"] == "CADUCADA"
    assert all(x.get("reencolada_de") != reenc[0]["id"] for x in c.listar())


def test_fallo_del_ejecutor_reintento_luego_anulada(cola):
    c, _, _ = cola
    n = c.solicitar(cubo="comercial", accion="enviar", clase="IRREVERSIBLE-EXTERNA")
    c.aprobar(n["id"], por="operador")
    with pytest.raises(RuntimeError):
        c.ejecutar(n["id"], lambda nodo: (_ for _ in ()).throw(RuntimeError("smtp caido")))
    assert c._get(n["id"])["estado"] == "APROBADA"          # REINTENTO disponible
    with pytest.raises(RuntimeError):
        c.ejecutar(n["id"], lambda nodo: (_ for _ in ()).throw(RuntimeError("smtp caido")))
    assert c._get(n["id"])["estado"] == "ANULADA"           # fallo repetido


def test_candado_subagente_no_relaja_y_queda_registrado(cola):
    _, k, b = cola
    assert cambiar_nivel("BAJA", "CERO", actor="subagente", bitacora=b) == "CERO"   # endurecer si
    assert cambiar_nivel("BAJA", "ALTA", actor="subagente", bitacora=b) == "BAJA"   # relajar NO
    assert cambiar_nivel("BAJA", "MEDIA", actor="operador", bitacora=b) == "MEDIA"  # operador si
    cambios = [e for e in k.all("t1", "evento").values()
               if e["tipo"] == "plataforma.autonomia.cambiada"]
    assert any(e["payload"]["veredicto"] == "rechazado" for e in cambios)
    assert b.verificar()["integra"] is True
