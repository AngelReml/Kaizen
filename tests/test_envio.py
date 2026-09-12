"""Tests del envío SMTP guardado (Block E)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agentes
import diario_ops
from core.bus import InMemoryBus
from core.events import EventType
from core.guardian import Guardian, Decision


FICHA_OK = """# Lead Test
- **Email:** destino@ejemplo.com

---
## Borrador aprobado — 2026-05-24 10:00
**Asunto:** Presentación
Buenos días, le escribo para presentar nuestro producto artesano. Este mensaje ha sido generado con IA.
Un saludo.
"""

FICHA_ABUSIVA = FICHA_OK.replace("le escribo para presentar nuestro producto artesano",
                                 "esto es una estafa para incautos")


def _con_ficha(contenido, lead="lead_test"):
    """Crea un diario temporal con una ficha y devuelve (tmpdir_ctx)."""
    tmp = tempfile.TemporaryDirectory()
    diario_ops.DIARIO = Path(tmp.name)
    diario_ops.write_cliente(lead, contenido, company="laboratorio")
    return tmp


def _sem(action):
    return (Decision.BLOCKED, "abusivo") if "estafa" in str(action.payload).lower() else (Decision.APPROVED, "ok")


def test_smtp_send_sin_config_lanza():
    for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
        os.environ.pop(v, None)
    try:
        agentes.smtp_send("x@y.com", "a", "b")
        assert False, "debería lanzar"
    except RuntimeError:
        pass


def test_extraer_borrador():
    d = agentes._extraer_borrador(FICHA_OK)
    assert d and d["asunto"] == "Presentación" and "producto artesano" in d["cuerpo"]


def test_sin_ficha():
    orig = diario_ops.DIARIO
    tmp = tempfile.TemporaryDirectory()
    diario_ops.DIARIO = Path(tmp.name)
    try:
        r = agentes.enviar_borrador_guardado("inexistente", "laboratorio")
        assert not r["ok"]
    finally:
        diario_ops.DIARIO = orig
        tmp.cleanup()


def test_guardian_bloquea_contenido_abusivo():
    """send_email es irreversible (IRREVERSIBLES en core/guardian.py) => el Guardián
    real SIEMPRE escala por regla dura, y enviar_borrador_guardado trata ESCALATED
    como bloqueante igual que BLOCKED (antes solo miraba BLOCKED: ESCALATED colaba)."""
    orig = diario_ops.DIARIO
    tmp = _con_ficha(FICHA_ABUSIVA)
    os.environ["KAIZEN_ENVIO_HABILITADO"] = "true"
    try:
        calls = []
        r = agentes.enviar_borrador_guardado(
            "lead_test", "laboratorio", guardian=Guardian(semantic=_sem), smtp=lambda *a: calls.append(a))
        assert not r["ok"] and "Guard" in r["motivo"]
        assert calls == []                       # no se envió nada
    finally:
        diario_ops.DIARIO = orig
        os.environ.pop("KAIZEN_ENVIO_HABILITADO", None)
        tmp.cleanup()


def test_envio_sin_flag_global_no_envia():
    """Barrera 0: sin KAIZEN_ENVIO_HABILITADO=true no sale nada, aunque todo lo demás
    (ficha, borrador, ausencia de guardián) esté en regla."""
    orig = diario_ops.DIARIO
    tmp = _con_ficha(FICHA_OK)
    os.environ.pop("KAIZEN_ENVIO_HABILITADO", None)
    try:
        calls = []
        r = agentes.enviar_borrador_guardado(
            "lead_test", "laboratorio", smtp=lambda *a: calls.append(a))
        assert not r["ok"] and "KAIZEN_ENVIO_HABILITADO" in r["motivo"]
        assert calls == []
    finally:
        diario_ops.DIARIO = orig
        tmp.cleanup()


def test_envio_ok_emite_eventos():
    """Camino feliz: flag global activo, disclosure de IA en el cuerpo y sin Guardián
    (con Guardián real, send_email siempre escala: ver test_guardian_bloquea_contenido_abusivo)."""
    orig = diario_ops.DIARIO
    tmp = _con_ficha(FICHA_OK)
    os.environ["KAIZEN_ENVIO_HABILITADO"] = "true"
    try:
        bus = InMemoryBus()
        calls = []
        r = agentes.enviar_borrador_guardado(
            "lead_test", "laboratorio", bus=bus,
            smtp=lambda to, a, c: calls.append(to))
        assert r["ok"] and r["to"] == "destino@ejemplo.com"
        assert calls == ["destino@ejemplo.com"]
        tipos = [e.type for e in bus.history()]
        assert EventType.APPROVAL_GRANTED in tipos and EventType.DEPT_TASK_COMPLETED in tipos
    finally:
        diario_ops.DIARIO = orig
        os.environ.pop("KAIZEN_ENVIO_HABILITADO", None)
        tmp.cleanup()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
