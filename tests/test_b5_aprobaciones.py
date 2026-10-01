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


def test_alta_bloqueada_esta_temporada_tampoco_para_el_operador(cola):
    _, k, b = cola
    assert cambiar_nivel("MEDIA", "ALTA", actor="operador", bitacora=b) == "MEDIA"
    assert cambiar_nivel("BAJA", "ALTA", actor="subagente", bitacora=b) == "BAJA"
    cambios = [e["payload"] for e in k.all("t1", "evento").values()
               if e["tipo"] == "plataforma.autonomia.cambiada"]
    assert [c["motivo"] for c in cambios] == ["nivel_bloqueado", "nivel_bloqueado"]
    assert all(c["veredicto"] == "rechazado" for c in cambios)
    # quedarse en el mismo nivel o endurecer sigue permitido
    assert cambiar_nivel("MEDIA", "BAJA", actor="subagente", bitacora=b) == "BAJA"
    assert b.verificar()["integra"] is True


def test_motivo_de_rechazo_por_relajar_sin_ser_operador(cola):
    _, k, b = cola
    assert cambiar_nivel("CERO", "BAJA", actor="subagente", bitacora=b) == "CERO"
    ev = [e["payload"] for e in k.all("t1", "evento").values()
          if e["tipo"] == "plataforma.autonomia.cambiada"]
    assert ev[-1]["motivo"] == "solo_operador_relaja"


def test_texto_de_niveles_reservados_no_promete_capacidades():
    from panel_mando.colmena import _NIVEL_EXPLICA
    for n in ("MEDIA", "ALTA"):
        assert "reservado" in _NIVEL_EXPLICA[n]
        assert "BAJA" in _NIVEL_EXPLICA[n]
        assert "ciclos propios" not in _NIVEL_EXPLICA[n]


# ── ejecuta el humano (C1/I1, docs/AUTONOMIA_v0.md) ─────────────────────────

def _aprobada_ext(c, accion="publicar landing"):
    n = c.solicitar(cubo="marketing", accion=accion, clase="IRREVERSIBLE-EXTERNA")
    c.aprobar(n["id"], por="angel")
    return n["id"]


def test_humano_camino_feliz_con_evidencia_y_huella_sellada(cola):
    import hashlib
    c, k, b = cola
    ap = _aprobada_ext(c)
    assert c.entregar_a_humano(ap, por="angel")["estado"] == "EN_MANOS"
    n = c.confirmar_hecha(ap, por="angel", evidencia="  pago hosting ref 12345  ")
    assert n["estado"] == "HECHA" and n["evidencia"] == "pago hosting ref 12345"
    assert n["evidencia_sha256"] == hashlib.sha256(b"pago hosting ref 12345").hexdigest()
    ev = {e["tipo"]: e["payload"] for e in k.all("t1", "evento").values()}
    assert ev["plataforma.aprobacion.en_manos"] == {"aprobacion_ref": ap, "por": "angel"}
    assert ev["plataforma.aprobacion.hecha"]["evidencia_sha256"] == n["evidencia_sha256"]
    assert "evidencia" not in ev["plataforma.aprobacion.hecha"]        # el texto no va a la bitacora
    assert b.verificar()["integra"] is True


def test_humano_solo_irreversible_externa_y_solo_desde_aprobada(cola):
    c, _, _ = cola
    interna = c.solicitar(cubo="ops", accion="x", clase="IRREVERSIBLE-INTERNA")
    c.aprobar(interna["id"], por="angel")
    with pytest.raises(TransicionAprobacionInvalida):
        c.entregar_a_humano(interna["id"], por="angel")
    pend = c.solicitar(cubo="marketing", accion="x", clase="IRREVERSIBLE-EXTERNA")
    with pytest.raises(TransicionAprobacionInvalida):
        c.entregar_a_humano(pend["id"], por="angel")                   # PENDIENTE
    ap = _aprobada_ext(c)
    c.entregar_a_humano(ap, por="angel")
    with pytest.raises(TransicionAprobacionInvalida):
        c.entregar_a_humano(ap, por="angel")                           # ya EN_MANOS
    with pytest.raises(TransicionAprobacionInvalida):
        c.revocar(ap, por="angel")                                     # ya no se revoca
    with pytest.raises(TransicionAprobacionInvalida):
        c.ejecutar(ap, lambda nodo: None)                              # el codigo no la ejecuta


def test_evidencia_obligatoria_y_acotada_y_solo_desde_en_manos(cola):
    c, _, _ = cola
    ap = _aprobada_ext(c)
    with pytest.raises(TransicionAprobacionInvalida):
        c.confirmar_hecha(ap, por="angel", evidencia="ok")             # aun APROBADA
    c.entregar_a_humano(ap, por="angel")
    for mala in ("", "   ", None):
        with pytest.raises(ValueError, match="evidencia"):
            c.confirmar_hecha(ap, por="angel", evidencia=mala)
    with pytest.raises(ValueError, match="500"):
        c.confirmar_hecha(ap, por="angel", evidencia="x" * 501)
    assert c._get(ap)["estado"] == "EN_MANOS"                          # nada se movio
    assert c.confirmar_hecha(ap, por="angel", evidencia="x" * 500)["estado"] == "HECHA"
    with pytest.raises(TransicionAprobacionInvalida):
        c.confirmar_hecha(ap, por="angel", evidencia="otra vez")       # exactamente una vez


def test_anular_en_manos_exige_motivo_y_deja_traza(cola):
    c, k, b = cola
    ap = _aprobada_ext(c)
    c.entregar_a_humano(ap, por="angel")
    with pytest.raises(ValueError, match="motivo"):
        c.anular_en_manos(ap, por="angel", motivo=" ")
    n = c.anular_en_manos(ap, por="angel", motivo="ya no hace falta")
    assert n["estado"] == "ANULADA" and "ya no hace falta" in n["motivo"]
    assert "plataforma.aprobacion.no_hecha" in [e["tipo"] for e in k.all("t1", "evento").values()]
    with pytest.raises(TransicionAprobacionInvalida):
        c.anular_en_manos(ap, por="angel", motivo="otra vez")
    assert b.verificar()["integra"] is True


def test_exactamente_una_via_ejecutor_o_humano_nunca_las_dos(cola):
    c, _, _ = cola
    for _ in range(20):
        ap = _aprobada_ext(c)
        res = {"cod": 0, "hum": 0}

        def por_codigo():
            try:
                c.ejecutar(ap, lambda nodo: None); res["cod"] += 1
            except TransicionAprobacionInvalida:
                pass

        def por_humano():
            try:
                c.entregar_a_humano(ap, por="angel"); res["hum"] += 1
            except TransicionAprobacionInvalida:
                pass

        hs = [threading.Thread(target=f) for f in (por_codigo, por_humano)]
        [h.start() for h in hs]; [h.join() for h in hs]
        assert res["cod"] + res["hum"] == 1, res


def test_en_manos_no_caduca_aunque_pasen_las_horas(cola):
    from datetime import datetime, timedelta, timezone
    c, _, _ = cola
    ap = _aprobada_ext(c)
    c.entregar_a_humano(ap, por="angel")
    c.barrer_caducadas(ahora=datetime.now(timezone.utc) + timedelta(hours=500))
    assert c._get(ap)["estado"] == "EN_MANOS"


def test_frases_del_feed_para_los_estados_nuevos_y_el_cambio_de_nivel():
    from panel_mando import nucleo as N
    assert "tus manos" in N.render({"tipo": "plataforma.aprobacion.en_manos", "payload": {}})
    assert "evidencia" in N.render({"tipo": "plataforma.aprobacion.hecha", "payload": {}})
    f = N.render({"tipo": "plataforma.autonomia.cambiada",
                  "payload": {"cubo": "marketing", "de": "BAJA", "a": "CERO",
                              "causa": "racha_de_denegadas", "veredicto": "aplicado"}})
    assert f == "el nivel de marketing paso de BAJA a CERO por tres noes seguidos"
    r = N.render({"tipo": "plataforma.autonomia.cambiada",
                  "payload": {"cubo": "qa", "veredicto": "rechazado"}})
    assert "rechazado" in r and "qa" in r
