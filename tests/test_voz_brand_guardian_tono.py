"""Tests del análisis conversacional del Brand Guardian (post-call)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.brand_guardian import BrandGuardian
from departments.comercial.sdr.voz_conversacional.analisis_calidad import DictamenTono


CTX = """## Contacto comercial (remitente)
- **Nombre:** Iván Carbonell
- **Cargo:** Director comercial
- **Empresa:** Repostería Laboratorio (Cieza)
"""


def _bg(respuesta_chat):
    def _chat(messages, system=None, **kw): return respuesta_chat
    return BrandGuardian(empresa="laboratorio", contexto_negocio=CTX, chat=_chat)


# ── Casos felices ────────────────────────────────────────────────────────────
def test_aprueba_si_llm_devuelve_ok_true():
    bg = _bg('{"ok": true, "problemas": [], "sugerencias": ["dar más pausa entre frases"]}')
    r = bg.analizar_tono_conversacional("Buenos días, le habla Iván desde Cieza...")
    assert isinstance(r, DictamenTono)
    assert r.ok is True
    assert r.problemas == []
    assert "pausa" in r.sugerencias[0]


def test_rechaza_si_llm_dice_que_sono_a_ia_generica():
    bg = _bg('{"ok": false, "problemas": ["sonó a IA, frases plantilla"], "sugerencias": ["más pausas naturales"]}')
    r = bg.analizar_tono_conversacional("Estimado señor, no dude en contactarme...")
    assert r.ok is False
    assert any("IA" in p or "plantilla" in p for p in r.problemas)


# ── Robustez ante respuestas raras del LLM ──────────────────────────────────
def test_acepta_json_envuelto_en_bloque_markdown():
    bg = _bg('```json\n{"ok": true, "problemas": [], "sugerencias": []}\n```')
    r = bg.analizar_tono_conversacional("Hola buenos días, le habla Iván...")
    assert r.ok is True


def test_no_aprueba_si_llm_devuelve_basura():
    bg = _bg("perdón, no he entendido la pregunta")
    r = bg.analizar_tono_conversacional("Hola buenos días, le habla Iván...")
    assert r.ok is False
    assert any("JSON" in p for p in r.problemas)


def test_transcript_vacio_no_invoca_llm():
    invocaciones = []
    def chat(*a, **kw):
        invocaciones.append(1); return ""
    bg = BrandGuardian(empresa="laboratorio", contexto_negocio=CTX, chat=chat)
    r = bg.analizar_tono_conversacional("")
    assert r.ok is False
    assert any("vacío" in p for p in r.problemas)
    assert invocaciones == []                # no se llamó al LLM


def test_recoge_excepcion_de_llm_y_no_explota():
    def chat(*a, **kw): raise RuntimeError("timeout en API")
    bg = BrandGuardian(empresa="laboratorio", contexto_negocio=CTX, chat=chat)
    r = bg.analizar_tono_conversacional("Buenos días, le habla Iván...")
    assert r.ok is False
    assert any("LLM falló" in p for p in r.problemas)
