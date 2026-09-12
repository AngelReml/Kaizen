"""Tests del departamento de QA (Fase 5.1): reglas, herramientas, validador, integración."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bus import InMemoryBus
from core.events import Event, EventType
from core.knowledge import InMemoryKnowledge
from core.subscriptors.qa_validador import QAValidador
from departments.base import Task
from departments.qa import reglas, herramientas as h
from departments.qa.agente import QADepartment
from departments.qa.especialistas import (
    ValidadorDeEstructura, DetectorDeContradicciones, CalificadorDeCalidad,
)

BORRADOR_OK = ("Presentación de Repostería Laboratorio",
               "Buenos días, le escribo desde Repostería Laboratorio, obrador artesano de Cieza "
               "con más de un siglo de historia, por si encajamos como proveedor de su negocio. "
               "Quedo a su disposición. Un saludo, Iván Carbonell.")


# ── reglas ──────────────────────────────────────────────────────────────────
def test_correo_sin_asunto():
    assert reglas.correo_sin_asunto("")[0] is False
    assert reglas.correo_sin_asunto("Hola")[0] is True


def test_cuerpo_corto():
    assert reglas.cuerpo_demasiado_corto("dos palabras")[0] is False
    assert reglas.cuerpo_demasiado_corto(BORRADOR_OK[1])[0] is True


def test_placeholders_detecta_marcadores():
    assert reglas.contiene_placeholders("Hola [nombre]")[0] is False
    assert reglas.contiene_placeholders("Falta TODO esto")[0] is False
    assert reglas.contiene_placeholders("lorem ipsum dolor")[0] is False


def test_placeholders_no_falso_positivo_con_todo_espanol():
    assert reglas.contiene_placeholders("Le ofrecemos todo nuestro catálogo artesano.")[0] is True


# ── herramientas ────────────────────────────────────────────────────────────
def test_validar_borrador_ok():
    assert h.validar_borrador(*BORRADOR_OK)["ok"] is True


def test_validar_borrador_con_problemas():
    r = h.validar_borrador("", "corto [nombre]")
    assert r["ok"] is False and len(r["problemas"]) >= 2


def test_detectar_contradicciones():
    r = h.detectar_contradicciones("Producto industrial a gran escala", "obrador artesano local")
    assert r["ok"] is False and r["contradicciones"]


def test_comparar_con_plantilla():
    r = h.comparar_con_plantilla("Buenos días. Un saludo.", ["buenos días", "firma"])
    assert r["coincide_estructura"] is False and "firma" in r["diferencias"]


# ── validador automático (subscriptor) ──────────────────────────────────────
def test_validador_bloquea_borrador_malo():
    bus = InMemoryBus()
    k = InMemoryKnowledge()
    QAValidador(bus, k)
    bus.publish(Event(EventType.DEPT_TASK_COMPLETED, source="redaccion",
                      payload={"lead": "x", "asunto": "", "cuerpo": "corto"}, company="laboratorio"))
    bloqueos = [e for e in bus.history() if e.source == "qa" and e.type is EventType.GUARDIAN_BLOCKED]
    assert len(bloqueos) == 1
    assert len(k.all("laboratorio", "validacion")) == 1


def test_validador_pasa_borrador_bueno():
    bus = InMemoryBus()
    QAValidador(bus, InMemoryKnowledge())
    bus.publish(Event(EventType.DEPT_TASK_COMPLETED, source="redaccion",
                      payload={"lead": "x", "asunto": BORRADOR_OK[0], "cuerpo": BORRADOR_OK[1]},
                      company="laboratorio"))
    assert not [e for e in bus.history() if e.source == "qa"]


def test_validador_ignora_otras_fuentes():
    bus = InMemoryBus()
    QAValidador(bus, InMemoryKnowledge())
    bus.publish(Event(EventType.DEPT_TASK_COMPLETED, source="prospeccion",
                      payload={"cuerpo": "corto"}, company="laboratorio"))
    assert not [e for e in bus.history() if e.source == "qa"]


# ── pipeline de especialistas (pase de excelencia: usar_pipeline activado) ──

def test_especialistas_qa_no_llaman_a_llm():
    """Confirma por codigo (no solo por lectura) lo que justifica activar
    usar_pipeline sin miedo a coste oculto: ninguno de los tres especialistas
    de QA define _chat/_get_llm mas alla de lo heredado de Especialista, y
    ejecutar() de cada uno no referencia self._chat en absoluto."""
    import inspect
    for cls in (ValidadorDeEstructura, DetectorDeContradicciones, CalificadorDeCalidad):
        fuente = inspect.getsource(cls.ejecutar)
        assert "_chat" not in fuente and "_get_llm" not in fuente
        assert "claude_client" not in fuente


def test_qa_department_usar_pipeline_esta_activado():
    assert QADepartment.usar_pipeline is True


def test_qa_pipeline_puntua_con_artefacto():
    """payload con 'artefacto' -> QADepartment.run() usa el pipeline real y
    devuelve una puntuacion 0-10 con desglose (secciones requeridas presentes,
    asi que ValidadorDeEstructura no corta el pipeline)."""
    dept = QADepartment(InMemoryBus(), knowledge=InMemoryKnowledge())
    task = Task(intent="calificar_calidad", company="laboratorio",
               payload={"artefacto": "Buenos días. Firma: Iván.",
                        "secciones_requeridas": ["buenos días", "firma"],
                        "contexto_empresa": "obrador artesano local"})
    r = dept.handle(task)
    assert r.ok is True
    assert 0 <= r.data["puntuacion"] <= 10
    assert "desglose" in r.data and "recomendaciones" in r.data


def test_qa_pipeline_corta_si_faltan_secciones_requeridas():
    """PipelineDepartamento.ejecutar() detiene la cadena en el primer
    especialista que marca ok=False (ValidadorDeEstructura) — CalificadorDe
    Calidad ni se ejecuta, asi que no hay 'puntuacion' en ese caso. Es
    comportamiento real del pipeline compartido (departments/base.py), no un
    bug de QA: se deja documentado aqui."""
    dept = QADepartment(InMemoryBus(), knowledge=InMemoryKnowledge())
    task = Task(intent="calificar_calidad", company="laboratorio",
               payload={"artefacto": "Buenos días. Un saludo.",
                        "secciones_requeridas": ["buenos días", "firma"]})
    r = dept.handle(task)
    assert r.ok is False
    assert "firma" in r.data["secciones_faltantes"]
    assert "puntuacion" not in r.data


def test_qa_pipeline_detecta_contradiccion_via_contexto_empresa(monkeypatch):
    """Sin secciones_requeridas, ValidadorDeEstructura no corta nada (ok=True
    trivial) y el pipeline llega hasta DetectorDeContradicciones. El tenant
    sintetico 'laboratorio' YA tiene CONTEXTO_NEGOCIO.md/DECISIONES.md reales
    en disco (fixture compartida por otros tests) que no mencionan ninguno de
    los rasgos de PARES_CONTRADICTORIOS — DetectorDeContradicciones prioriza
    ese contexto real sobre 'contexto_empresa' (ver especialistas.py: el
    'or' solo cae al input si contexto_negocio+decisiones esta VACIO), asi
    que aqui se vacian con monkeypatch para probar especificamente el
    fallback a 'contexto_empresa' sin tocar ni depender de esos ficheros."""
    import diario_ops
    monkeypatch.setattr(diario_ops, "read", lambda *a, **kw: "")
    dept = QADepartment(InMemoryBus(), knowledge=InMemoryKnowledge())
    task = Task(intent="calificar_calidad", company="laboratorio",
               payload={"artefacto": "Somos un fabricante industrial a gran escala.",
                        "contexto_empresa": "obrador artesano local"})
    r = dept.handle(task)
    assert r.data["contradicciones"]
    assert r.data["puntuacion"] < 10


def test_qa_pipeline_sin_problemas_puntua_diez():
    dept = QADepartment(InMemoryBus(), knowledge=InMemoryKnowledge())
    task = Task(intent="calificar_calidad", company="laboratorio",
               payload={"artefacto": "Un saludo cordial.", "contexto_empresa": ""})
    r = dept.handle(task)
    assert r.data["puntuacion"] == 10


def test_qa_legacy_sigue_intacto_pese_a_usar_pipeline_true():
    """La activacion de usar_pipeline NO debe apagar las reglas duras legacy
    (asunto vacio / cuerpo corto / placeholders) cuando el payload trae
    asunto/cuerpo en vez de 'artefacto' — es la garantia central de este
    pase: QADepartment.run() bifurca por contenido, no solo por el flag."""
    dept = QADepartment(InMemoryBus(), knowledge=InMemoryKnowledge())
    task = Task(intent="valida esto", company="laboratorio",
               payload={"asunto": "", "cuerpo": "corto [nombre]"})
    r = dept.handle(task)
    assert r.ok is False
    assert r.data["problemas"]                 # forma legacy intacta
    assert "puntuacion" not in r.data           # no se coló el pipeline


def test_qa_legacy_borrador_ok_sigue_pasando():
    dept = QADepartment(InMemoryBus(), knowledge=InMemoryKnowledge())
    task = Task(intent="valida esto", company="laboratorio",
               payload={"asunto": BORRADOR_OK[0], "cuerpo": BORRADOR_OK[1]})
    r = dept.handle(task)
    assert r.ok is True
    assert r.data["ok"] is True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1; print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
