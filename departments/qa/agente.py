"""Agente de QA (Fase 5.1). Valida borradores que se le pasan; reemplaza el cascarón."""
from __future__ import annotations

from departments.base import Department, Task, TaskResult
from departments.qa import herramientas as h


class QADepartment(Department):
    """Pase de excelencia (auditoria): el pipeline de especialistas
    (ValidadorDeEstructura, DetectorDeContradicciones, CalificadorDeCalidad —
    ver especialistas.py) ya se construye en __init__ pero quedaba MUERTO
    porque `usar_pipeline` nunca se ponia a True aqui, a diferencia de
    Marketing/Inteligencia/CustomerSuccess. Investigado ANTES de tocar nada
    (regla 1): ninguno de los tres especialistas llama a `self._chat`/
    `self._get_llm` ni importa `claude_client`/`ai.chat` — son deterministas
    (grep sobre especialistas.py, confirmado), asi que activarlo no mete
    coste oculto de LLM.

    Se activa aqui como flag de CLASE (`usar_pipeline = True`, igual que las
    otras tres) porque es la forma honesta de decir "el pipeline es el flujo
    real de este departamento" — pero NO se deja que eso mate el flujo
    legacy de reglas duras de correo (asunto vacio / cuerpo corto /
    placeholders, en departments/qa/reglas.py via herramientas.py), que
    sigue siendo la UNICA cobertura real de esos cuatro chequeos: el
    pipeline no los repite (su ValidadorDeEstructura compara contra una
    lista de 'secciones_requeridas' explicita, un concepto distinto).
    `Department.run()` (departments/base.py, fuera de este ambito) no mira
    el intent — es un booleano de instancia/clase puro — asi que activar
    `usar_pipeline=True` a secas habria apagado esas reglas duras para
    SIEMPRE en cualquier `.handle()`, incluida la instancia real que
    `api/server.py` conecta al bus vivo (`QADepartment(bus, knowledge)`),
    sin que nada de esto estuviera pedido ni sea seguro sin mas pruebas.
    Por eso `run()` se sobreescribe aqui: decide segun lo que TRAE el
    payload (¿'artefacto' para puntuar, o 'asunto'/'cuerpo' para validar
    reglas?), no segun un flag ciego."""
    name = "qa"
    usar_pipeline = True

    def __init__(self, bus, knowledge=None) -> None:
        super().__init__(bus)
        self.knowledge = knowledge
        from departments.base import PipelineDepartamento
        from departments.qa.especialistas import (
            ValidadorDeEstructura, DetectorDeContradicciones, CalificadorDeCalidad,
        )
        self.pipeline = PipelineDepartamento(
            [ValidadorDeEstructura(), DetectorDeContradicciones(), CalificadorDeCalidad()],
            "qa", bus=bus,
        )

    def run(self, task: Task) -> TaskResult:
        """Bifurca por CONTENIDO del payload, no solo por el flag heredado:
        'artefacto' -> pipeline de puntuacion 0-10 (especialistas); 'asunto'/
        'cuerpo' (o ninguno de los dos) -> reglas duras legacy. Ver docstring
        de la clase para el porque."""
        self._current_company = getattr(task, "company", "unknown")
        if self.usar_pipeline and hasattr(self, "pipeline") and "artefacto" in (task.payload or {}):
            return self._run_con_pipeline(task)
        return self._run_legacy(task)

    def _run_legacy(self, task: Task) -> TaskResult:
        p = task.payload
        if "cuerpo" in p or "asunto" in p:
            r = h.validar_borrador(p.get("asunto", ""), p.get("cuerpo", ""), p.get("contexto", ""))
            txt = "Validación QA OK." if r["ok"] else "QA encontró problemas: " + "; ".join(r["problemas"])
            return TaskResult(r["ok"], txt, r)
        # Falta el insumo: NO es trabajo completado. ok=False para que el orquestador no lo
        # confunda con una validación superada.
        return TaskResult(False, "QA: pásame un borrador (asunto y cuerpo) para validarlo.", {})
