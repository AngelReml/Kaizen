# -*- coding: utf-8 -*-
"""La tanda en segundo plano (B1): una a la vez, sin bloquear, con estado e informe."""
import json
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from core import apuestas as A
from core import exploracion as E
from core import exploracion_fondo as F
from core.exploracion_modelos import ApagadaOSinToken
from core.knowledge import InMemoryKnowledge, JsonKnowledge
from core.rue import Bitacora
from test_exploracion import ModeloFalso, buscar_falso, candidato, modelo_de_ciclos

EMP = "lab"


class ModeloLento(ModeloFalso):
    """Se queda esperando en la primera propuesta hasta que el test lo suelte."""

    def __init__(self, soltar: threading.Event, **kw):
        super().__init__(**kw)
        self.soltar = soltar
        self.dentro = threading.Event()

    def preguntar(self, sistema, usuario, **kw):
        self.dentro.set()
        assert self.soltar.wait(20), "el test no solto al modelo"
        return super().preguntar(sistema, usuario, **kw)


@pytest.fixture()
def entorno(tmp_path):
    k = InMemoryKnowledge()
    b = Bitacora(k, EMP, fecha_alta="2026-07-10")

    def fabrica_de(modelo=None, **extra):
        def fabrica(empresa, k_, b_):
            d = {"cliente": modelo or modelo_de_ciclos(), "buscar": buscar_falso, "parar": lambda: False,
                 "nivel_autonomia": lambda: "BAJA", "informes": tmp_path / "informes"}
            d.update(extra)
            return d
        return fabrica
    yield k, b, fabrica_de, tmp_path
    F._HILOS.clear()


def _espera(cond, t=10):
    fin = time.monotonic() + t
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_lanzar_vuelve_enseguida_y_la_tanda_corre_en_segundo_plano(entorno):
    k, b, fabrica, tmp = entorno
    soltar = threading.Event()
    m = ModeloLento(soltar, proponer=lambda mm, u: json.dumps({"candidatos": [candidato(i) for i in range(8)]}))
    t0 = time.monotonic()
    r = F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(m), informe_dir=tmp / "inf")
    assert time.monotonic() - t0 < 2 and r["lanzada"] is True                  # no espera a la tanda
    assert m.dentro.wait(5)
    st = F.estado(k, EMP)
    assert st["en_curso"] is not None and st["en_curso"]["ciclos"] == 1 and st["ultima"] is None
    soltar.set()
    assert F.esperar(EMP, 20)
    st = F.estado(k, EMP)
    assert st["en_curso"] is None and st["ultima"]["motivo"] == "completada" and st["ultima"]["dosieres"] == 5
    assert Path(st["ultima"]["informe"]).read_text(encoding="utf-8").startswith("# Informe de la tanda")
    assert A.Apuestas(k, EMP).conteo_por_estado()["DOSIER"] == 5
    assert b.verificar()["integra"] is True


def test_una_sola_tanda_a_la_vez_y_luego_se_puede_repetir(entorno):
    k, b, fabrica, tmp = entorno
    soltar = threading.Event()
    m = ModeloLento(soltar)
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(m), informe_dir=tmp / "inf")
    assert m.dentro.wait(5)
    with pytest.raises(F.YaEnMarcha, match="en marcha"):
        F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(), informe_dir=tmp / "inf")
    with pytest.raises(F.YaEnMarcha):                                          # tampoco por la via sincrona
        F.correr(k, EMP, b, fabrica()(EMP, k, b), ciclos=1)
    soltar.set()
    assert F.esperar(EMP, 20)
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(), informe_dir=tmp / "inf")
    assert F.esperar(EMP, 20) and F.estado(k, EMP)["ultima"]["dosieres"] == 5


def test_un_error_de_configuracion_sale_al_lanzar_con_instrucciones_y_no_reserva_nada(entorno):
    k, b, _, tmp = entorno
    def mala(empresa, k_, b_):
        raise ApagadaOSinToken("Falta KAIZEN_WEBLLM_TOKEN. En el PC: external_api_admin enable")
    with pytest.raises(ApagadaOSinToken, match="external_api_admin enable"):
        F.lanzar(k, EMP, b, fabrica=mala)
    assert F.estado(k, EMP) == {"en_curso": None, "ultima": None} and EMP not in F._HILOS


def test_si_la_tanda_revienta_queda_dicho_y_la_reserva_se_libera(entorno):
    k, b, fabrica, tmp = entorno
    f = tmp / "ocupado"; f.write_text("soy un fichero, no una carpeta")          # informes_dir imposible
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(), informe_dir=f / "dentro")
    assert F.esperar(EMP, 20)
    st = F.estado(k, EMP)
    assert st["en_curso"] is None and st["ultima"]["motivo"] == "error_interno" and st["ultima"]["error"]
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(), informe_dir=tmp / "inf")      # y se puede volver a lanzar
    assert F.esperar(EMP, 20) and F.estado(k, EMP)["ultima"]["motivo"] == "completada"


def test_parar_todo_detiene_la_tanda_en_marcha(entorno):
    k, b, fabrica, tmp = entorno
    parar = {"v": False}
    n = {"c": 0}
    def prop(mm, u):
        n["c"] += 1
        if n["c"] == 1:
            parar["v"] = True                                                      # PARAR TODO pulsado durante el ciclo
        return json.dumps({"candidatos": [candidato(1000 * n["c"] + i) for i in range(8)]})
    F.lanzar(k, EMP, b, ciclos=5, fabrica=fabrica(ModeloFalso(proponer=prop), parar=lambda: parar["v"]), informe_dir=tmp / "inf")
    assert F.esperar(EMP, 20)
    u = F.estado(k, EMP)["ultima"]
    assert u["motivo"] == "parar_todo" and u["dosieres"] < 5


@pytest.mark.parametrize("ciclos,horas", [(0, 8), (21, 8), (-1, 8), ("3", 8), (True, 8), (None, 8),
                                          (3, 0), (3, -1), (3, 49), (3, float("nan")), (3, "8"), (3, True)])
def test_parametros_absurdos_se_rechazan_al_lanzar(entorno, ciclos, horas):
    k, b, fabrica, _ = entorno
    with pytest.raises(A.ApuestaInvalida):
        F.lanzar(k, EMP, b, ciclos=ciclos, horas=horas, fabrica=fabrica())
    assert F.estado(k, EMP)["en_curso"] is None


def test_una_reserva_caducada_no_bloquea_pero_una_vigente_si(entorno):
    k, b, fabrica, tmp = entorno
    ahora = datetime.now(timezone.utc)
    k.add(EMP, E.COLECCION_ESTADO, F.CLAVE_EN_CURSO, {"activa": True, "desde": (ahora - timedelta(hours=20)).isoformat(),
                                                      "hasta": (ahora - timedelta(hours=10)).isoformat(), "ciclos": 3})
    assert F.estado(k, EMP)["en_curso"] is None                                   # un proceso murio sin liberar
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(), informe_dir=tmp / "inf")
    assert F.esperar(EMP, 20)
    k.add(EMP, E.COLECCION_ESTADO, F.CLAVE_EN_CURSO, {"activa": True, "desde": ahora.isoformat(),
                                                      "hasta": (ahora + timedelta(hours=3)).isoformat(), "ciclos": 3})
    with pytest.raises(F.YaEnMarcha):                                              # otro proceso (la consola) la tiene
        F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica())


def test_el_estado_solo_lleva_numeros_y_rutas_nunca_textos_de_apuestas(entorno):
    k, b, fabrica, tmp = entorno
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica(), informe_dir=tmp / "inf")
    assert F.esperar(EMP, 20)
    volcado = json.dumps(F.estado(k, EMP))
    assert "zeta" not in volcado and set(F.estado(k, EMP)["ultima"]) == {
        "tanda_ref", "fin", "motivo", "error", "dosieres", "ciclos_hechos", "rechazos", "rechazados_por_repeticion", "informe"}


def test_el_progreso_por_ciclo_se_ve_en_el_estado_mientras_corre(entorno):
    k, b, fabrica, tmp = entorno
    vistos = []
    deps = fabrica()(EMP, k, b)
    F.correr(k, EMP, b, deps, ciclos=3, informe_dir=tmp / "inf",
             progreso=lambda r: vistos.append(F.estado(k, EMP)["en_curso"]["ciclos_hechos"]))
    assert vistos == [1, 2, 3]


def test_dos_lanzamientos_simultaneos_solo_uno_arranca(tmp_path):
    for ronda in range(6):
        k = JsonKnowledge(tmp_path / f"k{ronda}.json")
        b = Bitacora(k, EMP, fecha_alta="2026-07-10")
        soltar = threading.Event()
        res, barrera = [], threading.Barrier(2)
        def intento():
            barrera.wait()
            try:
                F.lanzar(k, EMP, b, ciclos=1, informe_dir=tmp_path / f"inf{ronda}",
                         fabrica=lambda e, k_, b_: {"cliente": ModeloLento(soltar), "buscar": buscar_falso,
                                                    "parar": lambda: False, "nivel_autonomia": lambda: "BAJA",
                                                    "informes": tmp_path})
                res.append("ok")
            except F.YaEnMarcha:
                res.append("ya")
        hs = [threading.Thread(target=intento) for _ in range(2)]
        [h.start() for h in hs]; [h.join(10) for h in hs]
        soltar.set()
        assert sorted(res) == ["ok", "ya"], (ronda, res)
        assert F.esperar(EMP, 30)
        F._HILOS.clear()


# ── revision independiente de la fase B ─────────────────────────────────────

def _reserva_huerfana(k, *, pid, hace_min=1):
    ahora = datetime.now(timezone.utc)
    ini = (ahora - timedelta(minutes=hace_min)).isoformat()
    k.add(EMP, E.COLECCION_ESTADO, F.CLAVE_EN_CURSO, {"activa": True, "desde": ini, "latido": ini, "ciclos": 3, "ciclos_hechos": 0,
                                                       "hasta": (ahora + timedelta(hours=9)).isoformat(), "pid": pid})


def test_una_reserva_huerfana_de_este_proceso_no_bloquea_el_boton(entorno):
    k, b, fabrica_de, tmp = entorno
    _reserva_huerfana(k, pid=__import__("os").getpid())            # el hilo murio sin liberar (no hay nada corriendo)
    assert F.estado(k, EMP)["en_curso"] is None
    F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica_de())             # y se puede lanzar
    assert F.esperar(EMP, 20)
    assert A.Apuestas(k, EMP).conteo_por_estado()["DOSIER"] == 5


@pytest.mark.skipif(__import__("os").name != "posix", reason="comprobar un pid ajeno solo en posix")
def test_una_reserva_de_otro_proceso_muerto_se_descarta_y_la_de_uno_vivo_no(entorno):
    import subprocess
    k, b, fabrica_de, tmp = entorno
    p = subprocess.Popen([sys.executable, "-c", "pass"]); p.wait()
    _reserva_huerfana(k, pid=p.pid)                                 # pid de un proceso que ya termino
    assert F.estado(k, EMP)["en_curso"] is None
    _reserva_huerfana(k, pid=__import__("os").getppid())            # el proceso padre sigue vivo y no es el nuestro
    assert F.estado(k, EMP)["en_curso"] is not None
    with pytest.raises(F.YaEnMarcha):
        F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica_de())


def test_una_reserva_sin_latido_reciente_caduca(entorno):
    k, b, fabrica_de, tmp = entorno
    _reserva_huerfana(k, pid=__import__("os").getppid(), hace_min=F.LATIDO_MAX_S // 60 + 5)
    assert F.estado(k, EMP)["en_curso"] is None


def test_liberar_no_pisa_la_reserva_de_otra_tanda(entorno):
    k, b, fabrica_de, tmp = entorno
    ahora = datetime.now(timezone.utc)
    vieja = F._reservar(k, EMP, ciclos=1, horas=1, ahora=ahora - timedelta(hours=3))
    F._ACTIVAS.add(EMP)
    try:
        nueva = F._reservar(k, EMP, ciclos=2, horas=1, ahora=ahora)           # la vieja caduco por hora; otra tanda reserva
        assert nueva != vieja
        F._liberar(k, EMP, vieja)                                              # la vieja termina tarde
        F._latir(k, EMP, vieja)
        r = k.get(EMP, E.COLECCION_ESTADO, F.CLAVE_EN_CURSO)
        assert r["activa"] is True and r["desde"] == nueva and r["ciclos_hechos"] == 0
    finally:
        F._ACTIVAS.discard(EMP)


def test_la_reserva_es_atomica_con_muchos_hilos(entorno):
    k, b, fabrica_de, tmp = entorno
    barrera, ok, rechazos = threading.Barrier(12), [], []
    F._ACTIVAS.add(EMP)

    def intento():
        barrera.wait()
        try:
            F._reservar(k, EMP, ciclos=1, horas=1, ahora=datetime.now(timezone.utc)); ok.append(1)
        except F.YaEnMarcha:
            rechazos.append(1)
    try:
        hs = [threading.Thread(target=intento) for _ in range(12)]
        [h.start() for h in hs]; [h.join(10) for h in hs]
    finally:
        F._ACTIVAS.discard(EMP)
    assert len(ok) == 1 and len(rechazos) == 11


def test_lanzar_se_niega_con_inteligencia_en_cero_o_parar_todo_activo_sea_cual_sea_la_ruta(entorno):
    k, b, fabrica_de, tmp = entorno
    with pytest.raises(A.ApuestaInvalida, match="CERO"):
        F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica_de(nivel_autonomia=lambda: "CERO"))
    with pytest.raises(A.ApuestaInvalida, match="PARADO"):
        F.lanzar(k, EMP, b, ciclos=1, fabrica=fabrica_de(parar=lambda: True))
    assert A.Apuestas(k, EMP).listar() == [] and F.estado(k, EMP)["en_curso"] is None
