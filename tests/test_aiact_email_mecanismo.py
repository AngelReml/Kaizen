"""Mecanismo de transparencia AI Act para EMAIL (D11 E1.2 — cierre del F-01).

La política: el TEXTO lo aprueba solo el operador (fichero de variantes, sección
APROBADAS). El mecanismo: el composer inserta la variante activa y, si no hay
ninguna aprobada, el borrador falla EN COMPOSICIÓN (fail-closed), no en envío.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import aiact_gate
from departments.comercial.brand_guardian import BrandReview


# ── Parser del fichero de variantes ─────────────────────────────────────────

def _fichero(tmp_path, contenido):
    f = tmp_path / "variantes.md"
    f.write_text(contenido, encoding="utf-8")
    return f


def test_parser_lee_solo_la_seccion_aprobadas(tmp_path):
    f = _fichero(tmp_path, (
        "# CABECERA\n\n## APROBADAS\n\n- Mensaje generado por inteligencia artificial, "
        "revisado por un humano.\n- Segunda variante: asistente virtual de la casa.\n\n"
        "## PROPUESTAS SIN APROBAR\n\n- Esta NO debe usarse jamás.\n"))
    aprobadas = aiact_gate.variantes_email_aprobadas(f)
    assert len(aprobadas) == 2
    assert aprobadas[0].startswith("Mensaje generado por inteligencia artificial")
    assert all("NO debe usarse" not in v for v in aprobadas)
    assert aiact_gate.variante_email_activa(f) == aprobadas[0]


def test_parser_fail_closed_sin_fichero_o_sin_aprobadas(tmp_path):
    assert aiact_gate.variantes_email_aprobadas(tmp_path / "no_existe.md") == []
    f = _fichero(tmp_path, "# X\n\n## APROBADAS\n\n(ninguna)\n\n## PROPUESTAS SIN APROBAR\n\n- borrador\n")
    assert aiact_gate.variantes_email_aprobadas(f) == []
    assert aiact_gate.variante_email_activa(f) is None


def test_sin_tenant_no_se_adivina_variante():
    """R-TENANT + fail-closed: sin empresa ni ruta no hay transparencia aprobada.

    Antes el fichero era uno solo para todos, en el repo; ahora vive en la ficha
    de cada tenant y el producto NO adivina de quién es el envío."""
    assert aiact_gate.variante_email_activa() is None
    assert aiact_gate.variantes_email_aprobadas() == []
    assert aiact_gate.variante_email_activa(empresa="tenant_que_no_existe") is None


def test_el_tenant_sintetico_si_tiene_variantes_para_ejercitar_el_candado():
    """El candado debe poder probarse de punta a punta sin usar el texto
    aprobado de un cliente real. Aprobar para un tenant REAL sigue siendo del
    operador y solo de él."""
    ruta = aiact_gate.ruta_variantes_email("laboratorio")
    assert ruta.exists()
    assert aiact_gate.variante_email_activa(empresa="laboratorio")
    assert "PROPUESTAS SIN APROBAR" in ruta.read_text(encoding="utf-8")


# ── El composer aplica la transparencia en composición ──────────────────────

class _GuardianSi:
    def revisar(self, asunto, cuerpo, lead=None, usar_llm=True):
        return BrandReview(aprobado=True)


def _composer(monkeypatch, chat_cuerpo):
    """EmailComposer con chat y guardian inyectados y diario stub (sin disco)."""
    import departments.comercial.email_composer as mod
    monkeypatch.setattr(mod, "diario", type("D", (), {"read": staticmethod(lambda *a, **k: "contexto")}))
    llamadas = {"n": 0}

    def chat_fake(mensajes, system=None, model=None, max_tokens=None, company=None):
        llamadas["n"] += 1
        return chat_cuerpo if llamadas["n"] % 2 == 1 else "Asunto de prueba"

    return mod.EmailComposer(empresa="laboratorio", brand_guardian=_GuardianSi(),
                             chat=chat_fake, intentos_max=1)


def test_sin_variante_aprobada_el_borrador_falla_en_composicion(monkeypatch, tmp_path):
    monkeypatch.setattr(aiact_gate, "ruta_variantes_email",
                        lambda empresa: tmp_path / "vacio.md")
    comp = _composer(monkeypatch, "Hola, le escribo por sus postres.\n\nUn saludo, Iván")
    borrador = comp.componer({"id": "l1", "nombre": "Test"})
    assert not borrador.aprobado_por_brand
    assert any("AI Act" in p for p in borrador.review.problemas)


def test_con_variante_aprobada_se_inserta_y_aprueba(monkeypatch, tmp_path):
    f = _fichero(tmp_path, "## APROBADAS\n\n- Mensaje redactado con un sistema "
                           "automatizado y revisado por un humano de Laboratorio.\n")
    monkeypatch.setattr(aiact_gate, "ruta_variantes_email", lambda empresa: f)
    comp = _composer(monkeypatch, "Hola, le escribo por sus postres.\n\nUn saludo, Iván")
    borrador = comp.componer({"id": "l1", "nombre": "Test"})
    assert borrador.aprobado_por_brand
    assert borrador.cuerpo.endswith("revisado por un humano de Laboratorio.")
    assert aiact_gate.tiene_disclosure(borrador.cuerpo)


def test_si_el_redactor_ya_se_identifica_no_hace_falta_variante(monkeypatch, tmp_path):
    monkeypatch.setattr(aiact_gate, "ruta_variantes_email",
                        lambda empresa: tmp_path / "vacio.md")
    comp = _composer(monkeypatch, "Le escribe el asistente virtual de Laboratorio.\n\nUn saludo")
    borrador = comp.componer({"id": "l1", "nombre": "Test"})
    assert borrador.aprobado_por_brand
    assert aiact_gate.tiene_disclosure(borrador.cuerpo)


def test_variante_insertada_no_se_duplica(monkeypatch, tmp_path):
    f = _fichero(tmp_path, "## APROBADAS\n\n- Mensaje de un sistema automatizado.\n")
    monkeypatch.setattr(aiact_gate, "ruta_variantes_email", lambda empresa: f)
    comp = _composer(monkeypatch, "Cuerpo con sistema automatizado ya mencionado.")
    borrador = comp.componer({"id": "l1", "nombre": "Test"})
    assert borrador.aprobado_por_brand
    assert borrador.cuerpo.count("sistema automatizado") == 1
