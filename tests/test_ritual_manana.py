"""Tests del ritual de la manana (S2). LLM falso inyectado: cero gasto."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sustrato import bus as sbus
from sustrato import propuestas, registro
from cubos.comercial import ritual_manana


def _entorno(tmp_path):
    conn = sbus.conexion(tmp_path / "ritual.db")
    sbus.instalar(conn); registro.instalar(conn); propuestas.instalar(conn)
    for i, (nombre, seg) in enumerate([("Cafe Uno", "cafeteria_especialidad"),
                                       ("Hotel Dos", "hotel_boutique"),
                                       ("Meson Tres", "restaurante_ticket_30_50")]):
        registro.insertar_lead(conn, id=f"l{i+1}", nombre=nombre, segmento=seg,
                               prioridad="ALTA", cliente_id="laboratorio")
    registro.insertar_lead(conn, id="l_media", nombre="Bar Media", segmento="otro",
                           prioridad="MEDIA", cliente_id="laboratorio")
    return conn


def _llm_ok(sistema, usuario):
    """Salida de LLM falsa, firmada por el tenant SINTETICO.

    Iba firmada por una persona real de un cliente real; con el diario del tenant
    sintetico en su sitio, el Brand Guardian ya comprueba la firma y la vetaba —
    con razon."""
    return json.dumps({"asunto": "Producto de ensayo para su carta",
                       "cuerpo": ("Buenos dias. Le escribo desde Laboratorio KAIZEN "
                                  "porque trabajamos con negocios de hosteleria de la "
                                  "zona y creo que nuestro producto de ensayo puede "
                                  "encajar muy bien con su carta y con sus clientes de "
                                  "siempre. Sin ningun compromiso, me gustaria enviarle "
                                  "informacion y, si le parece bien, unas muestras para "
                                  "que las pruebe su equipo con calma y decida con datos. "
                                  "Quedo a su disposicion para lo que necesite. "
                                  "Un saludo cordial,\nEquipo del Laboratorio")})


def test_ritual_crea_tarjetas_reales_sin_demo(tmp_path):
    conn = _entorno(tmp_path)
    r = ritual_manana.generar(conn, n=3, llm=_llm_ok)
    assert r["creadas"] == 3 and r["descartadas"] == 0
    tarjetas = propuestas.pendientes(conn)
    assert len(tarjetas) == 3
    for t in tarjetas:
        assert "[DEMO]" not in t["cuerpo"] and "[DEMO]" not in t["resumen"]
        assert t["cuerpo"].startswith("Asunto: ")
        assert t["lead_id"] in ("l1", "l2", "l3")
    arg = conn.execute("SELECT argumento_id FROM propuestas LIMIT 1").fetchone()[0]
    assert arg  # enlazado al argumentario real (P8 aprendera de esto)


def test_seleccion_excluye_pendientes_y_media(tmp_path):
    conn = _entorno(tmp_path)
    ritual_manana.generar(conn, n=1, llm=_llm_ok)          # crea tarjeta para l1
    otra = ritual_manana.seleccionar_leads(conn, 5)
    ids = {l["id"] for l in otra}
    assert "l1" not in ids                                  # ya tiene pendiente
    assert "l_media" not in ids                             # prioridad MEDIA fuera
    assert ids == {"l2", "l3"}


def test_brand_veta_y_se_descarta(tmp_path):
    conn = _entorno(tmp_path)
    def llm_malo(sistema, usuario):
        return json.dumps({"asunto": "Oferta", "cuerpo": "Cuerpo corto."})  # <50 palabras
    r = ritual_manana.generar(conn, n=2, llm=llm_malo)
    assert r["creadas"] == 0 and r["descartadas"] == 2
    assert all("brand_veto" in m for m in r["motivos"])
    assert propuestas.pendientes(conn) == []                # ninguna tarjeta mala


def test_no_parseable_se_descarta_sin_romper(tmp_path):
    conn = _entorno(tmp_path)
    r = ritual_manana.generar(conn, n=2, llm=lambda s, u: "esto no es json")
    assert r["creadas"] == 0 and r["descartadas"] == 2
    assert all("no_parseable" in m for m in r["motivos"])


def test_no_toca_estado_de_leads(tmp_path):
    conn = _entorno(tmp_path)
    ritual_manana.generar(conn, n=3, llm=_llm_ok)
    estados = {f[0] for f in conn.execute("SELECT estado FROM leads").fetchall()}
    assert estados == {"COLD"}                              # R5: sin escrituras en leads
