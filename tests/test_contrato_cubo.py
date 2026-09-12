"""Tests del contrato de cubo (canonico seccion 3) - Bloque 2."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from sustrato import bus as sbus
from sustrato.config import ManifestInvalido, validar_manifest
from cubos.comercial.adaptador import CuboComercial, migrar_desde_knowledge


def _cubo_tmp(tmp_path):
    conn = sbus.conexion(tmp_path / "cubo_test.db")
    cubo = CuboComercial(conn=conn, cliente_id="__test__")
    cubo.instalar()
    return conn, cubo


def test_arranque_sin_pares(tmp_path):
    """Bus vacio y CERO cubos adicionales: arranca sin excepcion y salud OK."""
    conn, cubo = _cubo_tmp(tmp_path)
    cubo.arrancar()
    s = cubo.salud()
    assert s["estado"] == "OK"
    cubo.parar()


def test_manifest_invalido_rechazado(tmp_path):
    base = json.loads((Path(__file__).parent.parent / "cubos" / "comercial" /
                       "manifest.json").read_text(encoding="utf-8"))
    # requiere un cubo (error de diseno segun 3.1)
    malo = dict(base); malo["requiere"] = ["finanzas"]
    ruta = tmp_path / "manifest_malo.json"
    ruta.write_text(json.dumps(malo), encoding="utf-8")
    with pytest.raises(ManifestInvalido) as exc:
        validar_manifest(ruta)
    assert "requiere" in str(exc.value)
    # topic mal formado en produce
    malo2 = dict(base); malo2["produce"] = ["actualizar_lead"]
    ruta2 = tmp_path / "manifest_malo2.json"
    ruta2.write_text(json.dumps(malo2), encoding="utf-8")
    with pytest.raises(ManifestInvalido) as exc2:
        validar_manifest(ruta2)
    assert "produce" in str(exc2.value)
    # nivel de autonomia desconocido
    malo3 = dict(base); malo3["nivel_autonomia_defecto"] = "TOTAL"
    ruta3 = tmp_path / "manifest_malo3.json"
    ruta3.write_text(json.dumps(malo3), encoding="utf-8")
    with pytest.raises(ManifestInvalido) as exc3:
        validar_manifest(ruta3)
    assert "nivel_autonomia_defecto" in str(exc3.value)
    # el manifest real del cubo es valido
    validar_manifest(Path(__file__).parent.parent / "cubos" / "comercial" / "manifest.json")


def test_salud_formato(tmp_path):
    conn, cubo = _cubo_tmp(tmp_path)
    s = cubo.salud()
    assert set(s.keys()) == {"cubo", "estado", "detalle", "ts", "contadores"}
    assert s["cubo"] == "comercial"
    assert s["estado"] in ("OK", "DEGRADADO", "ERROR")
    assert set(s["contadores"].keys()) == {"leads", "compromisos_pendientes",
                                           "eventos_publicados_24h"}
    assert all(isinstance(v, int) for v in s["contadores"].values())
    assert s["ts"].endswith("Z")


def test_migracion_idempotente_y_sin_tocar_corpus(tmp_path):
    conn, cubo = _cubo_tmp(tmp_path)
    corpus = {"__test__": {"lead": {
        "cafe_uno": {"id": "cafe_uno", "nombre": "Cafe Uno", "estado_pipeline": "cold",
                     "categoria_icp": "cafeteria_especialidad", "prioridad_icp": "ALTA"},
        "hotel_dos": {"id": "hotel_dos", "nombre": "Hotel Dos", "estado_pipeline": "engaged",
                      "categoria_icp": "hotel_boutique_con_desayuno", "prioridad_icp": "MEDIA"},
        "perdido": {"id": "perdido", "nombre": "Perdido", "estado_pipeline": "lost",
                    "categoria_icp": "rareza_no_mapeada", "prioridad_icp": "BAJA"},
        "vetado": {"id": "vetado", "nombre": "Vetado", "estado_pipeline": "cold",
                   "categoria_icp": "cafeteria_especialidad", "prioridad_icp": "ALTA",
                   "do_not_call": True},
    }}}
    ruta = tmp_path / "knowledge_test.json"
    contenido = json.dumps(corpus, ensure_ascii=False)
    ruta.write_text(contenido, encoding="utf-8")
    r1 = migrar_desde_knowledge(conn, ruta, cliente_id="__test__")
    assert r1 == {"insertados": 4, "ya_existian": 0, "total_corpus": 4}
    r2 = migrar_desde_knowledge(conn, ruta, cliente_id="__test__")  # idempotente
    assert r2 == {"insertados": 0, "ya_existian": 4, "total_corpus": 4}
    filas = dict(conn.execute("SELECT id, estado FROM leads").fetchall())
    assert filas == {"cafe_uno": "COLD", "hotel_dos": "INTERESADO",
                     "perdido": "DESCARTADO", "vetado": "NO_LLAMAR"}
    seg = conn.execute("SELECT segmento FROM leads WHERE id='perdido'").fetchone()[0]
    assert seg == "otro"  # categoria desconocida -> otro, sin inventar
    assert ruta.read_text(encoding="utf-8") == contenido  # corpus intacto
