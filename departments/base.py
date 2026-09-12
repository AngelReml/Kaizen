"""Base de departamentos: orquestador departamental + contrato de tarea.

Un departamento recibe una Task del Director, emite su ciclo de vida al bus
(started → completed/failed) y devuelve un TaskResult. Subclasear y definir
`name` + `run`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.bus import MessageBus
from core.events import Event, EventType, Criticality


@dataclass
class Task:
    intent: str
    payload: dict = field(default_factory=dict)
    company: str = "default"
    correlation_id: str | None = None


@dataclass
class TaskResult:
    ok: bool
    summary: str
    data: dict = field(default_factory=dict)


class Department:
    name = "base"
    usar_pipeline: bool = False

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._current_company = "unknown"

    def _emit(self, etype: EventType, task: Task, payload: dict,
              crit: Criticality = Criticality.LOW) -> None:
        self.bus.publish(Event(
            etype, source=self.name, payload=payload,
            company=task.company, correlation_id=task.correlation_id, criticality=crit,
        ))

    def handle(self, task: Task) -> TaskResult:
        """Plantilla común: emite el ciclo de vida y delega en `run`."""
        self._emit(EventType.DEPT_TASK_STARTED, task, {"intent": task.intent})
        try:
            result = self.run(task)
        except Exception as e:
            self._emit(EventType.DEPT_TASK_FAILED, task, {"error": str(e)}, Criticality.HIGH)
            return TaskResult(False, f"Fallo en {self.name}: {e}")
        evt = EventType.DEPT_TASK_COMPLETED if result.ok else EventType.DEPT_TASK_FAILED
        # Se incluyen los datos del resultado para que otros departamentos puedan reaccionar.
        self._emit(evt, task, {"resumen": result.summary, **result.data})
        return result

    def run(self, task: Task) -> TaskResult:
        """Bifurca: pipeline de especialistas (si activo) o lógica legacy."""
        self._current_company = getattr(task, "company", "unknown")
        if self.usar_pipeline and hasattr(self, "pipeline"):
            return self._run_con_pipeline(task)
        return self._run_legacy(task)

    def _run_legacy(self, task: Task) -> TaskResult:
        raise NotImplementedError

    def _run_con_pipeline(self, task: Task) -> TaskResult:
        try:
            return self.pipeline.ejecutar(task)
        except Exception as e:
            import traceback
            self._emit_warning(
                f"pipeline {self.__class__.__name__} falló con {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )
            return self._run_legacy(task)

    def _emit_warning(self, mensaje: str) -> None:
        if self.bus:
            self.bus.publish(Event(
                EventType.DEPT_TASK_FAILED,
                source=self.__class__.__name__.lower(),
                payload={"warning": mensaje},
                company=getattr(self, "_current_company", "unknown"),
                criticality=Criticality.HIGH,
            ))


# ─────────────────────────────────────────────────────────────
#  Sub-agentes: Especialista + PipelineDepartamento (Bloque 3)
# ─────────────────────────────────────────────────────────────


class Especialista:
    """Sub-agente especialista. Cada uno declara su ClaseTarea, que determina el tier de
    modelo (cheap/medium/heavy) o FUNCION (lógica pura, sin LLM)."""
    nombre = "especialista"
    departamento = "base"
    descripcion = ""
    clase = None   # se asigna en cada subclase: una ClaseTarea

    def __init__(self, bus: MessageBus | None = None) -> None:
        self.bus = bus

    def ejecutar(self, input: dict, context: dict) -> dict:
        raise NotImplementedError

    def _get_llm(self):
        from core.task_classes import get_model_for_class
        entry = get_model_for_class(self.clase)
        if entry is None:
            raise NotImplementedError(f"{self.nombre} es FUNCION: no instancia LLM.")
        return entry

    def _chat(self, messages: list, system: str, max_tokens: int = 1024,
              company: str = "default") -> str:
        """Llama al LLM del tier de la clase, con reintentos (is_retriable + advance, máx 3),
        y emite COST_RECORDED con campos extendidos. Requiere langchain en runtime."""
        from core.model_router import advance, is_retriable
        from core import cost_tracker as ct
        from core import autorizacion as az
        entry = self._get_llm()
        prompt = system + "\n\n" + "\n".join(m.get("content", "") for m in messages)
        intentos = 0
        while True:
            try:
                # R-05: hard stop DELANTE de cada invoke. Estima con el precio del tier,
                # el tamaño real del prompt (~4 caracteres/token, igual criterio que
                # claude_client.estimar_usd) y el max_tokens real solicitado; si el dia
                # rebasa el tope, no se invoca (CosteNoAutorizado).
                previsto = ct.precio(getattr(entry, "provider", ""), entry.model_id,
                                     len(prompt) / 4.0, max_tokens)
                az.autorizar_gasto(company, previsto * ct.EUR_PER_USD)
                resp = entry.build().invoke(prompt)
                texto = getattr(resp, "content", str(resp))
                usage = getattr(resp, "usage_metadata", None) or {}
                eur = ct.record_specialist(self.departamento, self.nombre, str(self.clase.value),
                                           entry.model_id, usage.get("input_tokens", 0),
                                           usage.get("output_tokens", 0),
                                           provider=entry.provider, company=company)
                # R-05: y persiste el coste real en el ledger unico (lo ven panel + hard-stop).
                az.registrar_gasto(company, cubo=self.departamento, rol=self.nombre,
                                   modelo=entry.model_id, proveedor=getattr(entry, "provider", ""),
                                   coste_eur=eur, clase=str(self.clase.value))
                return texto
            except Exception as e:
                if is_retriable(e) and intentos < 3:
                    intentos += 1
                    nxt = advance(entry)
                    if nxt is None:
                        raise RuntimeError("Todos los modelos agotados") from e
                    entry = nxt
                    continue
                raise

    def _emit(self, etype: EventType, company: str, payload: dict) -> None:
        if self.bus is not None:
            self.bus.publish(Event(etype, source=self.nombre, payload=payload, company=company))


class PipelineDepartamento:
    """Orquesta especialistas en secuencia: el output de uno es input del siguiente.

    Construye el contexto de la empresa en tiempo de ejecución (leído del Diario, nunca
    hardcodeado). Si un especialista lanza, la excepción sube a Department._run_con_pipeline
    (traceback al bus + fallback al legacy). Si un especialista devuelve {ok: False}, el
    pipeline se detiene y devuelve TaskResult ok=False con los problemas.
    """

    def __init__(self, especialistas: list[Especialista], nombre_departamento: str,
                 *, bus: MessageBus | None = None, simulacion: bool = False) -> None:
        self.especialistas = especialistas
        self.nombre_departamento = nombre_departamento
        self.bus = bus
        self.simulacion = simulacion
        for esp in especialistas:
            if esp.bus is None:
                esp.bus = bus

    def planificar(self, task: Task) -> list[Especialista]:
        return list(self.especialistas)   # por defecto: todos en secuencia

    def ejecutar(self, task: Task) -> TaskResult:
        if not getattr(task, "company", None):
            raise ValueError("PipelineDepartamento requiere task.company para leer el contexto.")
        import diario_ops
        ctx_negocio = diario_ops.read("CONTEXTO_NEGOCIO", task.company)
        context = {
            "company": task.company,
            "intent": task.intent,
            "simulacion": self.simulacion,
            "contexto_negocio": ctx_negocio,
            "decisiones": diario_ops.read("DECISIONES", task.company),
            "identidad_remitente": diario_ops._extraer_identidad_remitente(ctx_negocio),
            "outputs_anteriores": {},
        }
        data = dict(task.payload)
        for esp in self.planificar(task):
            out = esp.ejecutar({**data, **context}, context) or {}
            context["outputs_anteriores"][esp.nombre] = out
            data = {**data, **out}
            if out.get("ok") is False:
                problemas = out.get("problemas") or [out.get("motivo", "validación fallida")]
                if self.bus is not None:
                    self.bus.publish(Event(
                        EventType.DEPT_TASK_FAILED, source=self.nombre_departamento,
                        payload={"warning": f"{esp.nombre} marcó problemas: {problemas}"},
                        company=task.company, criticality=Criticality.HIGH,
                    ))
                return TaskResult(False, f"{esp.nombre}: {'; '.join(map(str, problemas))}", data)
        return TaskResult(True, f"Pipeline {self.nombre_departamento} completado.", data)
