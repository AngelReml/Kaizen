# -*- coding: utf-8 -*-
"""Nivel de autonomia efectivo por empresa y cubo (core/autonomia.py, docs/AUTONOMIA_v0.md F3)."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.autonomia import COLECCION, AutonomiaCubos, manifest_efectivo
from core.knowledge import InMemoryKnowledge, JsonKnowledge
from core.rue import Bitacora

T = "t1"


@pytest.fixture()
def aut():
    k = InMemoryKnowledge()
    b = Bitacora(k, T, fecha_alta="2026-07-10")
    return AutonomiaCubos(k, T, bitacora=b), k, b


def _eventos(k):
    return [e["payload"] for e in k.all(T, "evento").values()
            if e["tipo"] == "plataforma.autonomia.cambiada"]


def test_sin_registro_vale_el_defecto_del_manifest(aut):
    a, _, _ = aut
    assert a.nivel("comercial", "BAJA") == "BAJA"
    assert a.nivel("qa", "CERO") == "CERO"
    assert a.nivel("x", "BASURA") == "CERO"          # defecto invalido: lo mas prudente
    assert a.ultimo_cambio("comercial") is None


def test_endurecer_baja_un_nivel_y_se_sella_con_cubo_y_causa(aut):
    a, k, b = aut
    r = a.endurecer("comercial", "MEDIA", causa="racha_de_denegadas", incidente="i1")
    assert (r["de"], r["a"], r["aplicado"]) == ("MEDIA", "BAJA", True)
    assert a.nivel("comercial", "MEDIA") == "BAJA"
    ev = _eventos(k)
    assert ev == [{"de": "MEDIA", "a": "BAJA", "actor": "sistema", "veredicto": "aplicado",
                   "cubo": "comercial", "causa": "racha_de_denegadas"}]
    assert b.verificar()["integra"] is True
    assert a.ultimo_cambio("comercial") is not None


def test_un_incidente_baja_una_sola_vez(aut):
    a, k, _ = aut
    assert a.endurecer("legal", "MEDIA", causa="c", incidente="i1")["aplicado"] is True
    r = a.endurecer("legal", "MEDIA", causa="c", incidente="i1")
    assert r["aplicado"] is False and r["razon"] == "incidente_ya_aplicado"
    assert a.nivel("legal", "MEDIA") == "BAJA"
    assert len(_eventos(k)) == 1


def test_nunca_baja_de_cero_y_no_emite_evento(aut):
    a, k, _ = aut
    r = a.endurecer("qa", "CERO", causa="c", incidente="i1")
    assert r["aplicado"] is False and r["razon"] == "ya_en_CERO"
    assert a.nivel("qa", "CERO") == "CERO"
    assert _eventos(k) == []
    # y el incidente queda anotado: no se reabre si luego el operador sube el nivel
    a.fijar("qa", "CERO", "BAJA", por="angel", motivo="revisado")
    assert a.endurecer("qa", "CERO", causa="c", incidente="i1")["razon"] == "incidente_ya_aplicado"
    assert a.nivel("qa", "CERO") == "BAJA"


def test_dos_incidentes_distintos_bajan_dos_niveles(aut):
    a, _, _ = aut
    a.endurecer("ops", "MEDIA", causa="c", incidente="i1")
    a.endurecer("ops", "MEDIA", causa="c", incidente="i2")
    assert a.nivel("ops", "MEDIA") == "CERO"


def test_operador_sube_hasta_media_y_queda_en_el_historial(aut):
    a, k, b = aut
    r = a.fijar("inteligencia", "BAJA", "MEDIA", por="angel", motivo="ficha buena")
    assert (r["de"], r["a"], r["aplicado"]) == ("BAJA", "MEDIA", True)
    assert a.nivel("inteligencia", "BAJA") == "MEDIA"      # el override REEMPLAZA al defecto
    h = a.registro("inteligencia")["historial"][-1]
    assert (h["actor"], h["por"], h["causa"]) == ("operador", "angel", "ficha buena")
    assert _eventos(k)[-1]["actor"] == "operador"
    assert b.verificar()["integra"] is True


def test_operador_puede_bajar_y_sin_cambio_no_emite(aut):
    a, k, _ = aut
    assert a.fijar("finanzas", "BAJA", "CERO", por="angel")["aplicado"] is True
    r = a.fijar("finanzas", "BAJA", "CERO", por="angel")
    assert r["aplicado"] is False and r["razon"] == "sin_cambio"
    assert len(_eventos(k)) == 1


def test_alta_bloqueada_tampoco_para_el_operador_y_el_intento_se_sella(aut):
    a, k, b = aut
    with pytest.raises(ValueError, match="bloqueado"):
        a.fijar("comercial", "BAJA", "ALTA", por="angel")
    assert a.nivel("comercial", "BAJA") == "BAJA"
    assert a.registro("comercial") is None
    ev = _eventos(k)
    assert ev[-1]["veredicto"] == "rechazado" and ev[-1]["motivo"] == "nivel_bloqueado"
    assert b.verificar()["integra"] is True


def test_nivel_desconocido_se_rechaza(aut):
    a, _, _ = aut
    with pytest.raises(ValueError, match="desconocido"):
        a.fijar("comercial", "BAJA", "TOTAL", por="angel")


def test_manifest_efectivo_no_muta_el_original_y_conserva_el_defecto():
    k = InMemoryKnowledge()
    man = {"cubo": "legal", "nivel_autonomia_defecto": "BAJA"}
    assert manifest_efectivo(k, T, "legal", man) is man          # sin override: el mismo objeto
    AutonomiaCubos(k, T).endurecer("legal", "BAJA", causa="c", incidente="i")
    ef = manifest_efectivo(k, T, "legal", man)
    assert ef["nivel_autonomia_defecto"] == "CERO" and ef["nivel_autonomia_manifest"] == "BAJA"
    assert man == {"cubo": "legal", "nivel_autonomia_defecto": "BAJA"}


def test_empresas_distintas_no_se_contaminan():
    k = InMemoryKnowledge()
    AutonomiaCubos(k, "a").endurecer("legal", "BAJA", causa="c", incidente="i")
    assert AutonomiaCubos(k, "a").nivel("legal", "BAJA") == "CERO"
    assert AutonomiaCubos(k, "b").nivel("legal", "BAJA") == "BAJA"


def test_manifest_desconocido_no_revienta():
    k = InMemoryKnowledge()
    assert manifest_efectivo(k, T, "nuevo", {}) == {}


def test_concurrencia_no_pierde_bajadas(tmp_path):
    """Dos incidentes distintos a la vez sobre MEDIA deben dejar CERO (no BAJA por pisarse)."""
    for ronda in range(10):
        k = JsonKnowledge(tmp_path / f"k{ronda}.json")
        a = AutonomiaCubos(k, T)
        barrera = threading.Barrier(2)

        def baja(i):
            barrera.wait()
            AutonomiaCubos(k, T).endurecer("ops", "MEDIA", causa="c", incidente=f"i{i}")

        hilos = [threading.Thread(target=baja, args=(i,)) for i in range(2)]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        assert a.nivel("ops", "MEDIA") == "CERO", f"ronda {ronda}"
        assert set(k.get(T, COLECCION, "ops")["incidentes"]) == {"i0", "i1"}


def test_subir_exige_motivo_dentro_de_fijar_y_no_cambia_nada_si_falta(aut):
    a, k, _ = aut
    for sin in ("", "   ", None):
        with pytest.raises(ValueError, match="motivo"):
            a.fijar("qa", "CERO", "BAJA", por="angel", motivo=sin)
    assert a.registro("qa") is None and _eventos(k) == []
    assert a.fijar("qa", "CERO", "BAJA", por="angel", motivo="ok")["aplicado"] is True
    assert a.fijar("qa", "CERO", "CERO", por="angel")["aplicado"] is True     # bajar: sin motivo


def test_el_motivo_libre_solo_deja_su_huella_en_la_bitacora_y_no_hay_pii_que_rechazar(aut):
    import hashlib
    a, k, b = aut
    texto = "el cliente Fulano (fulano@example.com) debe 12000 EUR"
    a.fijar("qa", "CERO", "BAJA", por="angel", motivo=texto)           # antes: PIIEnPayload
    ev = _eventos(k)[-1]
    assert ev["causa"] == "decision_del_operador"
    assert ev["motivo_sha256"] == hashlib.sha256(texto.encode()).hexdigest()
    assert "fulano" not in str(ev) and "12000" not in str(ev)
    assert a.registro("qa")["historial"][-1]["causa"] == texto           # el texto vive en el historial
    from panel_mando import nucleo as N
    assert "fulano" not in N.render({"tipo": "plataforma.autonomia.cambiada", "payload": ev})
    assert b.verificar()["integra"] is True


def test_sin_interbloqueo_con_la_bitacora_real_publicando_a_la_vez(tmp_path):
    """Regresion: endurecer/fijar sellaban DENTRO del candado de datos, y la bitacora toma sus
    candados en orden contrario (ABBA): dos hilos se bloqueaban para siempre. Se detecta con un
    plazo: si algun hilo sigue vivo, hay interbloqueo."""
    from core.rue import Sobre
    k = JsonKnowledge(tmp_path / "k.json")
    b = Bitacora(k, T, fecha_alta="2026-07-10")
    aut = AutonomiaCubos(k, T, bitacora=b)

    def cambia_niveles():
        for i in range(50):
            aut.fijar("qa", "CERO", "BAJA" if i % 2 == 0 else "CERO", por="x", motivo="m")
            aut.endurecer("ops", "MEDIA", causa="c", incidente=f"i{i}")

    def publica():
        for i in range(100):
            b.publicar(Sobre(tenant_id=T, tipo="plataforma.diario.entrada", payload={"n": i},
                             origen="t"))

    hilos = [threading.Thread(target=f, daemon=True) for f in (cambia_niveles, publica, publica)]
    [h.start() for h in hilos]
    limite = time.monotonic() + 30
    for h in hilos:
        h.join(timeout=max(0.0, limite - time.monotonic()))
    assert not any(h.is_alive() for h in hilos), "interbloqueo entre AutonomiaCubos y Bitacora"
    assert b.verificar()["integra"] is True
