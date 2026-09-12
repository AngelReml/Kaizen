"""Bloque D00-B7: panico bajo carga (13.5), palancas 3 niveles, higiene de config (13.10).
Montaje 13.5: acciones aprobadas ejecutandose en hilos; panico a mitad → 0 externalizadas
tras el corte, estado consistente, reanudacion sin perdida ni duplicado."""
import os
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core.rue import Bitacora
from core.aprobaciones import ColaSustrato, TransicionAprobacionInvalida
from core.panico import Panico, Palancas, PanicoActivo, PalancaCerrada

RAIZ = Path(__file__).parent.parent


def test_panico_bajo_carga_conserva_cola_y_reanuda():
    k = InMemoryKnowledge()
    b = Bitacora(k, "t1", fecha_alta="2026-07-10")
    cola = ColaSustrato(k, "t1", bitacora=b)
    pan = Panico(bitacoras={"t1": b})
    ids = []
    for i in range(60):
        n = cola.solicitar(cubo="comercial", accion=f"envio {i}", clase="IRREVERSIBLE-EXTERNA")
        cola.aprobar(n["id"], por="operador")
        ids.append(n["id"])

    externalizadas, bloqueadas = [], []

    def ejecutor(nodo):
        pan.gate_irrext("t1", nodo["clase"])       # gate DELANTE (≤1 ciclo)
        externalizadas.append(nodo["id"])

    def trabajador(lote):
        for ap_id in lote:
            try:
                cola.ejecutar(ap_id, ejecutor)
            except PanicoActivo:
                bloqueadas.append(ap_id)

    # primera mitad en 2 hilos concurrentes, panico, segunda mitad en 2 hilos
    hilos1 = [threading.Thread(target=trabajador, args=(m,))
              for m in (ids[0:15], ids[15:30])]
    for h in hilos1: h.start()
    for h in hilos1: h.join()
    pan.activar(por="operador", motivo="simulacro 13.5")
    corte = len(externalizadas)
    hilos2 = [threading.Thread(target=trabajador, args=(m,))
              for m in (ids[30:45], ids[45:60])]
    for h in hilos2: h.start()
    for h in hilos2: h.join()
    assert len(externalizadas) == corte             # 0 externalizadas tras el corte
    # conservacion: nada se perdio — lo no ejecutado sigue recuperable
    estados = {x["estado"] for x in cola.listar()}
    assert estados <= {"EJECUTADA", "APROBADA"}     # sin estados corruptos
    pan.desactivar(por="operador")
    pendientes = [x["id"] for x in cola.listar("APROBADA")]
    for ap_id in pendientes:
        cola.ejecutar(ap_id, ejecutor)              # reanudacion limpia
    assert sorted(externalizadas) == sorted(ids)    # sin perdida NI duplicado
    assert len(externalizadas) == len(set(externalizadas)) == 60
    assert b.verificar()["integra"] is True


def test_desactivar_exige_operador():
    pan = Panico()
    pan.activar(por="operador")
    with pytest.raises(PermissionError):
        pan.desactivar(por="subagente")
    assert pan.activo is True


def test_palancas_tres_niveles_cerrado_gana():
    p = Palancas()
    pan = Panico(palancas=p)
    pan.gate_irrext("t1")                           # todo abierto: pasa
    p.fijar_clase("IRREVERSIBLE-EXTERNA", False)
    with pytest.raises(PalancaCerrada):
        pan.gate_irrext("t1")
    p.fijar_clase("IRREVERSIBLE-EXTERNA", True)
    p.fijar_tenant("t1", False)
    with pytest.raises(PalancaCerrada):
        pan.gate_irrext("t1")
    pan.gate_irrext("t2")                           # otro tenant no afectado
    p.fijar_tenant("t1", True)
    p.fijar_global(False)
    with pytest.raises(PalancaCerrada):
        pan.gate_irrext("t2")
    pan.gate_irrext("t2", clase="REVERSIBLE")       # solo IRR-EXT se gatea aqui


def test_higiene_config_produccion_13_10():
    """Bypass HMAC cerrado y voz OFF en la CONFIG DE REFERENCIA (no en el env vivo,
    que otros tests mutan — leccion E6); sin secretos obvios en el arbol."""
    sample = RAIZ / ".env.sample"
    if sample.exists():
        cfg = sample.read_text(encoding="utf-8", errors="replace").lower()
        for linea in cfg.splitlines():
            l = linea.strip()
            if l.startswith("kaizen_voice_sig_bypass"):
                assert "true" not in l, "bypass HMAC abierto en config de referencia"
            if l.startswith("sdr_voice_enabled"):
                assert "true" not in l, "voz ON en config de referencia (debe estar OFF)"
    patron = re.compile(r"sk-ant-[A-Za-z0-9-]{20,}|xoxb-[0-9A-Za-z-]{20,}|AKIA[0-9A-Z]{16}")
    sospechosos = []
    for sub in ("core", "departments", "api", "sustrato", "cubos"):
        for f in (RAIZ / sub).rglob("*.py"):
            if patron.search(f.read_text(encoding="utf-8", errors="replace")):
                sospechosos.append(str(f))
    assert not sospechosos, f"posibles secretos en arbol: {sospechosos}"
