"""Tests del Brand Guardian — reglas duras y evaluación semántica (LLM inyectado)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.brand_guardian import BrandGuardian

CONTEXTO_TEST = """## Contacto comercial (remitente)
- **Nombre:** Equipo del Laboratorio
- **Cargo:** Director comercial
- **Empresa:** Laboratorio KAIZEN
- **Teléfono:** 968000000
"""

# Cuerpo OK base usado por varios tests
CUERPO_OK = (
    "Buenos días,\n\nLes escribo desde Laboratorio KAIZEN, un tenant sintético que "
    "existe solo para ensayar el circuito. Quería presentarles nuestro producto de "
    "ensayo, pensado para comprobar que el sistema se comporta igual con cualquier "
    "cliente. Creo que podría encajar con la carta de su establecimiento y me haría "
    "ilusión que lo vieran con calma. Si les apetece probarlo, estaré encantado de "
    "acercarme con una selección y contarles cómo trabajamos, sin ningún "
    "compromiso por su parte.\n\nUn saludo,\nEquipo del Laboratorio\n"
    "Laboratorio KAIZEN\n968000000"
)


def _sem_acepta(asunto, cuerpo, **kw):
    return {"ok": True, "motivo": "tono de marca OK", "dictamen": "APROBADO|OK"}


def _sem_rechaza(asunto, cuerpo, **kw):
    return {"ok": False, "motivo": "suena a IA genérica", "dictamen": "NO_APROBADO|genérico"}


def _bg(semantic=None):
    return BrandGuardian(empresa="laboratorio",
                         semantic_evaluator=semantic or _sem_acepta,
                         contexto_negocio=CONTEXTO_TEST)


# ── Reglas duras ─────────────────────────────────────────────────────────────
def test_rechaza_asunto_vacio():
    r = _bg().revisar("", CUERPO_OK)
    assert not r.aprobado and any("Asunto vacío" in p for p in r.problemas)


def test_rechaza_asunto_largo():
    r = _bg().revisar("x" * 100, CUERPO_OK)
    assert not r.aprobado and any("Asunto demasiado largo" in p for p in r.problemas)


def test_rechaza_cuerpo_corto():
    r = _bg().revisar("Asunto", "Hola, un saludo.")
    assert not r.aprobado and any("corto" in p for p in r.problemas)


def test_rechaza_palabra_prohibida():
    cuerpo_malo = CUERPO_OK.replace("nuestro producto de", "nuestro producto barato de")
    r = _bg().revisar("Asunto", cuerpo_malo)
    assert not r.aprobado and any("'barato'" in p or "'barat'" in p for p in r.problemas)


def test_rechaza_markdown():
    cuerpo_md = "Buenos días,\n\n## Nuestra propuesta\n\n" + CUERPO_OK
    r = _bg().revisar("Asunto", cuerpo_md)
    assert not r.aprobado and any("markdown" in p.lower() for p in r.problemas)


def test_rechaza_placeholder():
    cuerpo_ph = CUERPO_OK.replace("su establecimiento", "[CIUDAD]")
    r = _bg().revisar("Asunto", cuerpo_ph)
    assert not r.aprobado and any("Placeholder" in p for p in r.problemas)


def test_rechaza_sin_firma_remitente():
    cuerpo_sin_firma = CUERPO_OK.replace("Equipo del Laboratorio", "Un saludo cordial")
    r = _bg().revisar("Asunto", cuerpo_sin_firma)
    assert not r.aprobado and any("remitente" in p for p in r.problemas)


# ── Evaluación semántica (LLM inyectado) ─────────────────────────────────────
def test_acepta_correo_OK_con_llm_que_aprueba():
    r = _bg(semantic=_sem_acepta).revisar("Repostería artesanal para vuestra carta", CUERPO_OK)
    assert r.aprobado
    assert "APROBADO" in r.detalle_llm


def test_rechaza_si_llm_dice_que_suena_a_IA():
    r = _bg(semantic=_sem_rechaza).revisar("Repostería artesanal para vuestra carta", CUERPO_OK)
    assert not r.aprobado
    assert any("genérica" in p for p in r.problemas)


def test_llm_no_se_invoca_si_reglas_duras_ya_rechazan():
    invocaciones = []
    def sem_que_cuenta(*a, **kw):
        invocaciones.append(1)
        return {"ok": True, "motivo": "ok", "dictamen": "x"}
    _bg(semantic=sem_que_cuenta).revisar("", CUERPO_OK)   # asunto vacío → rechazo duro
    assert invocaciones == []                              # no se llamó al LLM


# ── Argumentos prohibidos del argumentario por empresa ──────────────────────
# (empresas/laboratorio/argumentario.json → argumentos_prohibidos)

def test_rechaza_argumento_prohibido_superlativo():
    """Un superlativo absoluto es regla dura por substring en el argumentario."""
    cuerpo_malo = CUERPO_OK.replace(
        "nuestro producto de ensayo",
        "el mejor del mundo, sin discusion",
    )
    r = _bg().revisar("Asunto válido", cuerpo_malo)
    assert not r.aprobado
    assert any("superlativo_absoluto" in p for p in r.problemas), r.problemas


def test_rechaza_argumento_prohibido_promesa_de_resultado():
    """Prometer un resultado está bloqueado: no es verificable."""
    cuerpo_malo = CUERPO_OK.replace(
        "nuestro producto de ensayo",
        "algo con lo que garantizamos que duplicas ventas",
    )
    r = _bg().revisar("Asunto válido", cuerpo_malo)
    assert not r.aprobado
    assert any("promesa_de_resultado" in p for p in r.problemas), r.problemas


def test_acepta_argumento_que_funciona_margen():
    """'Margen 70% garantizado' es uno de los argumentos validados; no debe
    activar ningún patrón prohibido."""
    cuerpo = CUERPO_OK + "\n\nP.D.: margen 70% garantizado por porción, merma cero."
    r = _bg().revisar("Asunto válido", cuerpo)
    # No nos importa la decisión final (el LLM mockeado decide); solo que
    # ninguna regla dura cita los IDs prohibidos.
    assert not any("calidad_premium" in p for p in r.problemas)
    assert not any("abuela_tradicional" in p for p in r.problemas)


def test_empresa_sin_argumentario_no_rompe_brand_guardian():
    """Si la empresa no tiene argumentario.json, BrandGuardian sigue funcionando
    con las PALABRAS_PROHIBIDAS legacy."""
    bg = BrandGuardian(empresa="empresa_inventada",
                       semantic_evaluator=_sem_acepta,
                       contexto_negocio=CONTEXTO_TEST)
    assert bg.argumentos_prohibidos == []
    r = bg.revisar("Asunto válido", CUERPO_OK)
    # Reglas duras solo dependen del cuerpo legacy; no añade falsos positivos.
    assert not any("Argumento prohibido" in p for p in r.problemas)
