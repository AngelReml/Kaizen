"""Tests del comite (canonico 7.5) - Bloque 4. LLM FALSO inyectado: cero tokens."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sustrato import bus as sbus
from sustrato import comite, gates


def _conn(tmp_path):
    conn = sbus.conexion(tmp_path / "comite_test.db")
    sbus.instalar(conn)
    gates.instalar(conn)
    return conn


def _llm_secuencia(respuestas):
    """LLM falso que responde en orden; repite la ultima si se agota."""
    caja = {"i": -1}
    def llm(rol_prompt, mensaje):
        caja["i"] += 1
        return respuestas[min(caja["i"], len(respuestas) - 1)]
    return llm


def test_consenso_9_de_9(tmp_path):
    conn = _conn(tmp_path)
    d = comite.convocar(conn, "envio_email_real", {"lead": "l1"},
                        llm=_llm_secuencia(['{"voto": "PASS", "motivo": "correcto"}']))
    assert d["veredicto"] == "PASS" and d["confianza"] == 1.0
    assert len(d["votos"]) == 9
    assert {v["rol"] for v in d["votos"]} == set(comite.ROLES)
    assert {v["pasada"] for v in d["votos"]} == {1, 2, 3}
    assert set(d.keys()) >= {"veredicto", "confianza", "votos", "accion",
                             "contexto_hash", "ts"}
    json.dumps(d)  # serializable


def test_escalado_7_8(tmp_path):
    conn = _conn(tmp_path)
    ok = '{"voto": "PASS", "motivo": "sin problema"}'
    mal = '{"voto": "FAIL", "motivo": "duda legal"}'
    d8 = comite.convocar(conn, "envio_email_real", {}, llm=_llm_secuencia([mal] + [ok] * 8))
    assert d8["veredicto"] == "ESCALADO" and d8["confianza"] == 0.89
    d7 = comite.convocar(conn, "envio_email_real", {}, llm=_llm_secuencia([mal, mal] + [ok] * 7))
    assert d7["veredicto"] == "ESCALADO" and d7["confianza"] == 0.78
    d6 = comite.convocar(conn, "envio_email_real", {}, llm=_llm_secuencia([mal] * 3 + [ok] * 6))
    assert d6["veredicto"] == "FAIL" and d6["confianza"] == 0.67


def test_salida_no_parseable_es_fail(tmp_path):
    conn = _conn(tmp_path)
    d = comite.convocar(conn, "envio_email_real", {},
                        llm=_llm_secuencia(["esto no es JSON ni lo pretende"]))
    assert d["veredicto"] == "FAIL" and d.get("motivo") == "salida_no_parseable"
    assert d["confianza"] == 0.0
    # un solo voto corrupto tras 8 validos: tambien FAIL, nunca PASS
    ok = '{"voto": "PASS", "motivo": "bien"}'
    d2 = comite.convocar(conn, "envio_email_real", {},
                         llm=_llm_secuencia([ok] * 8 + ["basura", "mas basura"]))
    assert d2["veredicto"] == "FAIL" and d2.get("motivo") == "salida_no_parseable"


def test_gate_integra_comite_falso(tmp_path):
    conn = _conn(tmp_path)
    gates.set_autonomia(conn, "comercial", "ALTA", "test integracion", es_operador=True)
    v = gates.gate_preventivo(conn, "envio_email_real", {"lead": "l1"},
                              llm=_llm_secuencia(['{"voto": "PASS", "motivo": "ok"}']))
    assert v.veredicto == "PASS" and v.confianza == 1.0
    fila = conn.execute(
        "SELECT veredicto, confianza FROM verificaciones ORDER BY id DESC LIMIT 1").fetchone()
    assert fila == ("PASS", 1.0)
