"""Tests de regresion de las correcciones de fase 2 (orden del operador
2026-07-03: 'arregla todo', voz excluida)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from click.testing import CliRunner


def test_grupo_comercial_completo_sin_colision():
    """La colision de grupos Click dejaba fase0/fase1/voz inalcanzables."""
    import kaizen
    comandos = set(kaizen.cli.commands["comercial"].commands.keys())
    assert "dashboard" in comandos            # lo que sobrevivia antes
    assert len(comandos) > 1, f"solo {comandos}: el arbol sigue inaccesible"


def test_exit_code_1_ante_runtime_error(monkeypatch):
    import kaizen
    import agentes

    def revienta(*a, **k):
        raise RuntimeError("fallo simulado")
    monkeypatch.setattr(agentes, "prospectar", revienta)
    monkeypatch.setattr(kaizen, "_check_budget", lambda *a, **k: None)
    r = CliRunner().invoke(kaizen.cli, ["prospectar", "perfil de prueba"])
    assert r.exit_code == 1                   # antes devolvia 0 pese al fallo


def test_import_os_presente_en_kaizen():
    import kaizen
    assert hasattr(kaizen, "os")              # NameError latente corregido


def test_prompt_prospeccion_blindado():
    fuente = Path(__file__).parent.parent.joinpath("agentes.py").read_text(encoding="utf-8")
    assert "<<<DATOS_WEB>>>" in fuente and "REGLA DE SEGURIDAD" in fuente


def test_brand_guardian_respeta_empresa(monkeypatch):
    from departments.comercial.brand_guardian import BrandGuardian
    visto = {}

    def evaluador(asunto, cuerpo, *, empresa=None, contexto_negocio="", lead=None):
        visto["empresa"] = empresa
        return {"ok": True, "motivo": "", "dictamen": "APROBADO"}
    cuerpo = (
        "Buenos días. Le escribo desde Laboratorio KAIZEN, un tenant sintético, "
        "porque trabajamos con cafeterías y restaurantes de la zona y creo que "
        "nuestro producto de ensayo podría encajar con su carta. Sin ningún "
        "compromiso, me gustaría enviarle información y, si le interesa, unas "
        "muestras para que las pruebe su equipo con calma. Quedo a su disposición "
        "para lo que necesite. Un saludo cordial,\nEquipo del Laboratorio"
    )
    bg = BrandGuardian(empresa="laboratorio", semantic_evaluator=evaluador)
    bg.revisar("Presentación del tenant sintético", cuerpo, usar_llm=True)
    # La NUEVA tubería pasa la empresa de la instancia al evaluador inyectado;
    # antes el evaluador jamás recibía empresa (y el interno fijaba 'laboratorio').
    assert visto.get("empresa") == "laboratorio"
    fuente = Path(__file__).parent.parent.joinpath(
        "departments/comercial/brand_guardian.py").read_text(encoding="utf-8")
    assert "company=empresa," in fuente        # el evaluador interno ya no fija laboratorio
    assert 'empresa=self.empresa' in fuente    # y revisar() propaga la empresa real
