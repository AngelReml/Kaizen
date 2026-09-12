"""Bloque D00-B3: RUE, sobre canonico, bitacora encadenada, PII/crypto-shredding.

Baterias que cubre: 13.3 (dedupe), 13.4 (integridad nombrando el punto), test
negativo de evento desconocido (puerta B3), R-07 (PII), R-11 (escritor unico).
"""
import sys
import threading
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core import rue
from core import pii


@pytest.fixture()
def bit():
    k = InMemoryKnowledge()
    return rue.Bitacora(k, "tenant_test", fecha_alta="2026-07-10"), k


def test_publicar_encadena_y_verifica(bit):
    b, _ = bit
    for i in range(5):
        b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="plataforma.diario.entrada",
                             payload={"n": i}, origen="plataforma.panel"))
    v = b.verificar()
    assert v == {"integra": True, "eventos": 5}


def test_manipulacion_rompe_y_nombra_el_punto(bit):
    b, k = bit
    for i in range(4):
        b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="plataforma.diario.entrada",
                             payload={"n": i}))
    ev = k.get("tenant_test", "evento", "000000000002")
    ev["payload"] = {"n": 999}                       # manipulacion en frio
    k.add("tenant_test", "evento", "000000000002", ev)
    v = b.verificar()
    assert v["integra"] is False and v["punto_ruptura"] == "000000000002"


def test_evento_desconocido_rechazado_y_registrado(bit):
    b, k = bit
    with pytest.raises(rue.EventoInvalido):
        b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="cubo.inventado.hecho"))
    evs = list(k.all("tenant_test", "evento").values())
    assert len(evs) == 1 and evs[0]["tipo"] == "plataforma.evento.rechazado"
    assert b.verificar()["integra"] is True          # el rechazo tambien encadena


def test_pii_cruda_rechazada_y_cifrada_aceptada(bit):
    b, _ = bit
    with pytest.raises(rue.PIIEnPayload):
        b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="comercial.lead.descubierto",
                             payload={"nombre": "Bar Sintetico", "email": "x@sintetico.example"}))
    alm = pii.AlmacenClaves()
    seguro = pii.cifrar_campos({"nombre": "Bar Sintetico", "email": "x@sintetico.example"},
                               ["email"], alm, "tenant_test", "lead_l1")
    s = b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="comercial.lead.descubierto",
                             payload=seguro))
    assert "email_cifrado" in s.payload and "email" not in s.payload
    clave = alm.clave_si_existe("tenant_test", "lead_l1")
    assert pii.descifrar(s.payload["email_cifrado"], clave) == "x@sintetico.example"


def test_crypto_shredding_hace_ilegible_sin_romper_cadena(bit):
    b, _ = bit
    alm = pii.AlmacenClaves()
    seguro = pii.cifrar_campos({"email": "borradme@sintetico.example"}, ["email"],
                               alm, "tenant_test", "lead_l2")
    b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="comercial.lead.descubierto",
                         payload=seguro))
    assert alm.destruir("tenant_test", "lead_l2") is True
    with pytest.raises(pii.ClaveDestruida):
        pii.descifrar(seguro["email_cifrado"], alm.clave_si_existe("tenant_test", "lead_l2"))
    assert b.verificar()["integra"] is True          # la cadena ni se entera (R-07)


def test_escritor_unico_bajo_concurrencia(bit):
    b, _ = bit
    errores = []

    def escribir(n):
        try:
            for i in range(10):
                b.publicar(rue.Sobre(tenant_id="tenant_test",
                                     tipo="plataforma.diario.entrada",
                                     payload={"hilo": n, "i": i}))
        except Exception as e:                        # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=escribir, args=(h,)) for h in range(4)]
    for h in hilos: h.start()
    for h in hilos: h.join()
    assert not errores
    v = b.verificar()
    assert v == {"integra": True, "eventos": 40}      # 4 hilos × 10, cadena integra (R-11)


def test_dedupe_por_event_id():
    vistos = set()
    s = {"event_id": "abc123"}
    assert rue.deduplicar(vistos, s) is True
    assert rue.deduplicar(vistos, s) is False          # al-menos-una-vez ⇒ consumidor dedupe


def test_nfd_y_nfc_dan_mismo_sello():
    """Auditoria 2026-07-12: 0 strings no-NFC en el historico real (466 eventos
    laboratorio) permitio normalizar en _canon() sin romper verificacion existente.
    Mismo texto, dos formas de bytes (NFC/NFD) -> mismo sello."""
    nfc = unicodedata.normalize("NFC", "café")
    nfd = unicodedata.normalize("NFD", "café")
    assert nfc != nfd                                  # distintos bytes, mismo texto visible
    k1, k2 = InMemoryKnowledge(), InMemoryKnowledge()
    b1 = rue.Bitacora(k1, "t1", fecha_alta="2026-07-10")
    b2 = rue.Bitacora(k2, "t1", fecha_alta="2026-07-10")
    comun = dict(tenant_id="t1", tipo="plataforma.diario.entrada",
                origen="test", event_id="evt-fijo", ts="2026-07-10T00:00:00+00:00")
    s1 = b1.publicar(rue.Sobre(payload={"nombre": nfc}, **comun))
    s2 = b2.publicar(rue.Sobre(payload={"nombre": nfd}, **comun))
    assert s1.hash == s2.hash                          # NFC y NFD sellan igual


def test_vector_dorado_sello_real():
    """Vector fijado por ejecucion real (no inventado) contra el contrato de
    _canon()/_encadenar() vigente. Si esto rompe, cambio el contrato: revisar
    a proposito, no arreglar el test para que pase."""
    k = InMemoryKnowledge()
    b = rue.Bitacora(k, "t1", fecha_alta="2026-07-10")
    s = b.publicar(rue.Sobre(tenant_id="t1", tipo="plataforma.diario.entrada",
                             payload={"nombre": "café"}, origen="test",
                             event_id="evt-fijo", ts="2026-07-10T00:00:00+00:00"))
    assert s.hash_prev == "ee2a0abe77431c55eca9b79d4284b5380b40b21d8471b1d4d28117266529e46c"
    assert s.hash == "cb8921a13d7bc8cc958e57a06668dc6b577b3618651e7191fb53594dc1c71d1e"


def test_outbox_persiste_antes_de_publicar(bit):
    b, _ = bit
    caja = []
    b.publicar(rue.Sobre(tenant_id="tenant_test", tipo="comercial.contacto.enviado",
                         payload={"contacto_ref": "c1"}), outbox=caja)
    assert len(caja) == 1 and caja[0]["tipo"] == "comercial.contacto.enviado"
