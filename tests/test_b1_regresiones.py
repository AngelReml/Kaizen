"""Tests de regresión del bloque D00-B1 (serie D).

Cubren los tres defectos quirúrgicos de la auditoría 2026-07-02, corregidos el
2026-07-03 y verificados en AUDITORIA_D01 §C0.4. Estos tests los hacen permanentes:

  1. Colisión CLI: un segundo @cli.group("comercial") dejaba inalcanzables ~1.000
     líneas (aprobación de envíos, voz). Regresión = walk de --help sobre TODOS los
     comandos registrados (exigido por D00 §7.2 y B1.3) + alcanzabilidad explícita
     de la zona que estuvo rota.
  2. python-multipart ausente de requirements.txt (rompía 7 tests de webhooks en
     instalación limpia). Regresión = presencia declarada.
  3. BG-257: brand_guardian forzaba company="laboratorio" para todo tenant. Regresión =
     la empresa pasada por parámetro es la que llega al LLM (sin literal forzado).

Sin red ni LLM: el evaluador semántico se sustituye por un doble de prueba.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from click.testing import CliRunner

import kaizen
from departments.comercial import brand_guardian as bg

RAIZ = Path(__file__).parent.parent


# ─── 1. Colisión CLI ─────────────────────────────────────────────────────────

def _walk(cmd, ruta=()):
    """Recorre recursivamente todos los comandos registrados en el CLI."""
    yield ruta, cmd
    if isinstance(cmd, click.Group):
        for nombre, sub in sorted(cmd.commands.items()):
            yield from _walk(sub, ruta + (nombre,))


def test_walk_help_de_todos_los_comandos():
    """--help de cada comando registrado sale con código 0 (B1.3: una colisión
    futura de grupos rompe este test, no la producción)."""
    runner = CliRunner()
    fallos = []
    total = 0
    for ruta, _cmd in _walk(kaizen.cli):
        total += 1
        res = runner.invoke(kaizen.cli, [*ruta, "--help"])
        if res.exit_code != 0:
            fallos.append((" ".join(ruta) or "<raíz>", res.exit_code,
                           repr(res.exception)))
    assert total >= 30, f"se esperaban ≥30 comandos registrados, hay {total}"
    assert not fallos, f"--help falla en: {fallos}"


def test_zona_antes_inalcanzable_sigue_alcanzable():
    """La colisión sobreescribía el grupo `comercial` y ocultaba fase0/fase1/voz."""
    comercial = kaizen.cli.commands.get("comercial")
    assert comercial is not None, "el grupo `comercial` no está registrado"
    assert {"fase0", "fase1", "dashboard"} <= set(comercial.commands), (
        f"subcomandos de `comercial` incompletos: {sorted(comercial.commands)}")
    fase1 = comercial.commands["fase1"]
    esperados = {"preparar", "cola", "aprobar", "aprobar-campania", "rechazar",
                 "enviar", "muestra"}
    assert esperados <= set(fase1.commands), (
        f"la zona de aprobación/envío no está completa: {sorted(fase1.commands)}")


# ─── 2. python-multipart declarado ───────────────────────────────────────────

def test_python_multipart_declarado_en_requirements():
    lineas = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
    declarado = [l for l in lineas
                 if l.strip() and not l.strip().startswith("#")
                 and l.strip().lower().startswith("python-multipart")]
    assert declarado, ("python-multipart no está declarado en requirements.txt "
                       "(bug B0/D14 reabierto: 7 tests de webhooks caerían en "
                       "instalación limpia)")


# ─── 3. BG-257: la empresa del parámetro llega al LLM ────────────────────────

def test_brand_guardian_propaga_empresa_sin_literal_forzado(monkeypatch):
    capturado = {}

    def chat_doble(mensajes, system="", model="", max_tokens=0, company=None, **kw):
        capturado["company"] = company
        return "APROBADO\nsin problemas"

    monkeypatch.setattr(bg.ai, "chat", chat_doble)
    res = bg._llm_semantic_evaluator("Asunto de prueba", "Cuerpo de prueba",
                                     contexto_negocio="ctx", lead=None,
                                     empresa="empresa_test")
    assert capturado.get("company") == "empresa_test", (
        f"BG-257 reabierto: se envió company={capturado.get('company')!r} "
        "en lugar de la empresa pasada por parámetro")
    assert res["ok"] is True and "motivo" in res and "dictamen" in res
