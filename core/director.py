"""Director — orquestador supremo (Capa 3).

Responsabilidad: enrutar la intención inicial del CEO al departamento adecuado,
ejecutar el bucle de reflexión para acciones por encima de un umbral de criticidad
(verbaliza su interpretación y pide confirmación humana), y consolidar el resultado.
No microgestiona: una vez delega, el departamento ejecuta.
"""
from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable

from core.bus import MessageBus
from core.events import Event, EventType, Criticality
from departments.base import Department, Task, TaskResult

# Enrutado por palabras clave (sustituible por un router LLM en el futuro).
ROUTING: dict[str, tuple[str, ...]] = {
    "prospeccion": ("lead", "prospect", "candidat", "busca", "buscar", "hotel",
                    "tienda", "cliente", "gourmet", "distribuidor"),
    "redaccion": ("redact", "escrib", "mensaje", "borrador", "email", "correo"),
    "legal": ("legal", "contrato", "contractual", "clausula", "rgpd", "juridic",
              "normativa", "licencia"),
    "desarrollo": ("desarroll", "codigo", "programa", "bug", "feature", "despliegue",
                   "tecnic", "integra"),
    "qa": ("calidad", "valida", "revisa", "verifica", "prueba", "testea"),
    "finanzas": ("finanz", "presupuesto", "factura", "margen", "rentab", "tesoreria",
                 "gast", "cost", "dinero", "runway", "euros", "aguant", "ritmo",
                 "caro", "cara", "anomal"),
    "ops": ("operacion", "logistic", "proveedor", "inventario", "pedido", "almacen",
            "reparto", "capacidad", "stock", "materia"),
    "rrhh": ("rrhh", "contrata", "personal", "empleado", "nomina", "plantilla"),
}

# Palabras que elevan la criticidad (acciones hacia el exterior / irreversibles).
ALTA_CRITICIDAD = ("envia", "enviar", "manda", "mandar", "contacta", "publica", "paga", "pagar")

# Intención de CONSULTA del Diario (leer lo que YA tenemos): nunca prospecta ni gasta.
# Exige un verbo de consulta Y un objeto del Diario, para no confundir con una búsqueda.
CONSULTA_VERBOS = ("muestra", "muestrame", "ensename", "ver ", "lista", "listar",
                   "dame", "cuales", "cuantos", "que tenemos", "que hay")
CONSULTA_OBJETOS = ("client", "lead", "ficha", "diario", "tenemos", "ya ten")
# Verbos de BÚSQUEDA (prospección de nuevos candidatos): tienen prioridad sobre consulta.
BUSQUEDA = ("busca", "buscar", "prospect", "encuentra")

_ORDEN = [Criticality.LOW, Criticality.MEDIUM, Criticality.HIGH, Criticality.CRITICAL]


def _norm(text: str) -> str:
    """Minúsculas sin acentos, para comparar palabras clave de forma robusta."""
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class Director:
    def __init__(
        self,
        bus: MessageBus,
        departments: dict[str, Department],
        *,
        confirm: Callable[[str], bool] | None = None,
        umbral: Criticality = Criticality.HIGH,
        router: Callable[[str], str | None] | None = None,
    ) -> None:
        self.bus = bus
        self.departments = departments
        self.confirm = confirm
        self.umbral = umbral
        self._router = router or self._keyword_router

    # ── enrutado y criticidad ────────────────────────────────────────────
    def _keyword_router(self, intent: str) -> str | None:
        low = _norm(intent)
        for dept, kws in ROUTING.items():
            if dept in self.departments and any(k in low for k in kws):
                return dept
        return None

    def estimate_criticality(self, intent: str) -> Criticality:
        low = _norm(intent)
        return Criticality.HIGH if any(k in low for k in ALTA_CRITICIDAD) else Criticality.LOW

    def _supera_umbral(self, crit: Criticality) -> bool:
        return _ORDEN.index(crit) >= _ORDEN.index(self.umbral)

    # ── consulta del Diario (lectura, no prospección) ─────────────────────
    def _es_consulta(self, intent: str) -> bool:
        low = _norm(intent)
        if any(b in low for b in BUSQUEDA):
            return False                       # "busca/encuentra nuevos" → prospección
        return (any(v in low for v in CONSULTA_VERBOS)
                and any(o in low for o in CONSULTA_OBJETOS))

    def _responder_consulta(self, intent: str, company: str) -> TaskResult:
        """Responde leyendo el Diario: sin red, sin LLM, sin coste."""
        import diario_ops as diario
        low = _norm(intent)
        clientes = [c for c in diario.list_clientes(company) if not c.startswith("prospeccion_")]
        # ¿Pide una ficha concreta? ("ver ficha de X", "muéstrame la ficha de X")
        if "ficha" in low or low.strip().startswith("ver "):
            for slug in clientes:
                base = _norm(slug)
                for forma in (base, base.replace("_", " "), base.replace("_", "")):
                    if forma and (forma in low or forma.replace(" ", "") in low.replace(" ", "")):
                        ficha = diario.read_cliente(slug, company)
                        return TaskResult(True, ficha or f"La ficha '{slug}' está vacía.")
        # Por defecto: lista de clientes/leads del Diario.
        if not clientes:
            return TaskResult(True, "No hay clientes ni leads en el Diario todavía.")
        return TaskResult(True, f"Clientes y leads en el Diario ({len(clientes)}):\n"
                          + "\n".join(f"- {c}" for c in clientes))

    # ── flujo principal ──────────────────────────────────────────────────
    def handle_intent(self, intent: str, *, company: str = "default",
                      payload: dict | None = None) -> TaskResult:
        cid = uuid.uuid4().hex
        self._pub(EventType.INTENT_RECEIVED, company, cid, {"intent": intent})

        # Consulta del Diario: se responde con datos locales, sin prospectar ni gastar.
        if self._es_consulta(intent):
            self._pub(EventType.INTENT_ROUTED, company, cid,
                      {"intent": intent, "departamento": "diario"})
            result = self._responder_consulta(intent, company)
            self._pub(EventType.RESULT_CONSOLIDATED, company, cid,
                      {"departamento": "diario", "ok": result.ok, "resumen": result.summary})
            return result

        dept_name = self._router(intent)
        if dept_name is None:
            self._pub(EventType.RESULT_CONSOLIDATED, company, cid,
                      {"intent": intent, "resultado": "sin departamento"})
            return TaskResult(False, "No supe a qué departamento enrutar esta intención.")
        self._pub(EventType.INTENT_ROUTED, company, cid,
                  {"intent": intent, "departamento": dept_name})

        # Bucle de reflexión: por encima del umbral, pide confirmación humana.
        crit = self.estimate_criticality(intent)
        if self._supera_umbral(crit):
            interpretacion = f"Voy a pedir a '{dept_name}' que ejecute: {intent}"
            self._pub(EventType.APPROVAL_REQUESTED, company, cid,
                      {"interpretacion": interpretacion}, crit)
            aprobado = bool(self.confirm(interpretacion)) if self.confirm else False
            self._pub(
                EventType.APPROVAL_GRANTED if aprobado else EventType.APPROVAL_DENIED,
                company, cid, {"interpretacion": interpretacion},
            )
            if not aprobado:
                return TaskResult(False, "Acción no aprobada por el humano.")

        task = Task(intent=intent, payload=payload or {}, company=company, correlation_id=cid)
        result = self.departments[dept_name].handle(task)
        self._pub(EventType.RESULT_CONSOLIDATED, company, cid,
                  {"departamento": dept_name, "ok": result.ok, "resumen": result.summary})
        return result

    def _pub(self, etype: EventType, company: str, cid: str, payload: dict,
             crit: Criticality = Criticality.LOW) -> None:
        self.bus.publish(Event(
            etype, source="director", payload=payload,
            company=company, correlation_id=cid, criticality=crit,
        ))
