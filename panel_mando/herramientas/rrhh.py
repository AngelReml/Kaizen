# -*- coding: utf-8 -*-
"""Herramientas REALES del director de RRHH (Fase 4 — plenipotenciarios).

RRHH esta POSPUESTO segun el manifest: este cubo wirea EXCLUSIVAMENTE
LECTURA (introspeccion del propio sistema), ninguna escritura de negocio.
Ninguna funcion aqui atrapa excepciones salvo para traducir un objeto no
serializable a dict — si algo falla, la excepcion sube y la capa de
invocacion la reporta.

Pase de excelencia (auditoria): `mapa`, `rendimiento` y `propuestas`
construian antes un RRHHDepartment sobre un InMemoryBus() DESECHABLE en
cada llamada. RRHHDepartment solo aprende escuchando `cube.started` /
`dept.task_completed` / `dept.task_failed` en SU bus — con un bus nuevo en
cada invocacion, SIEMPRE ve un sistema vacio: `mapa()` decia cobertura
"10%" (solo el propio rrhh), `rendimiento()` decia siempre `{"alertas":
[]}` y `propuestas()` sugeria siempre lo mismo, pasara lo que pasara en el
sistema real. Documentado honestamente en el fichero pero enganoso en la
practica (auditoria confirmada). Estas 3 funciones ahora leen estado REAL
y PERSISTENTE en vez de reconstruir un departamento vacio:

  - `mapa`: catalogo = `cubos.base.manifiestos_instalados()`, el catalogo
    REAL en disco (cubos/*/manifest.json — los 10 cubos instalados hoy).
    Se descarto `core.resiliencia.arranque.CUBOS_CATALOGO` como fuente:
    sus nombres NO coinciden con los cubos reales ("operaciones" en vez
    de "ops", "inteligencia_mercado" en vez de "inteligencia", falta
    "qa" y sobra "opengravity", que no tiene directorio en cubos/) y
    mantenerlo sincronizado a mano con cubos/*/manifest.json es
    exactamente el tipo de duplicacion que ya causo el desfase. Los
    "presentes" salen de la tabla `colmena_agentes` (panel_mando/
    colmena.py): el registro PERSISTENTE, por tenant, de que director
    esta REALMENTE "dado de alta" — el mismo verbo que usa colmena.py
    para el alta real. Se investigo si `core.bus.get_bus()` (bus
    persistente en SQLite, `core/bus_sqlite.py::SQLitePersistentBus`)
    podria reconstruir "presentes" repitiendo el historial de
    `cube.started`: NO sirve, porque solo los departamentos que heredan
    de `CuboDepartamento` (Marketing, CustomerSuccess, Inteligencia,
    RRHH) publican ese evento — Comercial/Finanzas/Legal/Ops/QA heredan
    de `Department` a secas y NUNCA lo emiten (ver departments/cubo.py y
    departments/base.py), asi que ese camino daria "presentes"
    sistematicamente incompleto para media plantilla de cubos por una
    razon de arquitectura, no de actividad real. `colmena_agentes` no
    tiene ese problema: es la MISMA tabla para los 10 directores.
  - `rendimiento`: investigado a fondo (ver abajo) — no existe hoy una
    fuente persistente y consultable de tasas de fallo/completado por
    departamento fuera del proceso vivo del panel. Se devuelve
    explicitamente `datos_disponibles: False` con el motivo, nunca un
    `{"alertas": []}` silencioso que finja haber comprobado y no haber
    encontrado nada.
  - `propuestas`: se deriva de forma determinista de la cobertura REAL
    calculada arriba (el primer cubo realmente faltante, no siempre el
    primero de un catalogo fijo) y, honestamente, ya NO inventa
    propuestas de rendimiento que no puede respaldar con datos.

Investigacion de `rendimiento` (para que quede registrado el porque):
RRHHDepartment acumula `_completados`/`_fallos` (dict en memoria) solo
mientras escucha `dept.task_completed`/`dept.task_failed` en un bus vivo
(departments/rrhh/agente.py). Ese agregado no se persiste en ningun sitio:
ni en el KnowledgeStore (`k.all(tenant, ...)` no tiene un tipo de nodo
para esto — el unico subscriptor que persiste algo relacionado con
calidad de tareas es `core/subscriptors/qa_validador.py`, que guarda
nodos `"validacion"` de QA, no contadores de fallo por departamento), ni
en una tabla propia tipo `colmena_agentes`. Existe en teoria un bus
persistente (`core.bus.get_bus()` -> `SQLitePersistentBus` con
`.history(company)`) que SI guarda cada evento `dept.task_completed`/
`dept.task_failed` publicado por los departamentos reales del panel — pero
usarlo aqui exigiria: (a) que esta herramienta de LECTURA abra una
conexion nueva a la infraestructura del bus de produccion en cada
invocacion (o incluso Redis, si `REDIS_URL` esta configurado — cascada de
`get_bus()`), con el consiguiente riesgo/coste que este pase de excelencia
no estaba mandatado a asumir, y (b) reimplementar fuera de
RRHHDepartment la misma agregacion completados/fallos que ya vive alli,
duplicando logica. Se opta por la respuesta honesta explicita en vez de
ese camino; si se decide perseguirlo, es un cambio de alcance mayor
(deberia vivir en RRHHDepartment mismo, no en este wrapper).

apto=true pero NO wireadas para este cubo (instruccion explicita del
encargo, tratadas como REVERSIBLE en el mapa general pero pospuestas
aqui): RRHHDepartment.mapa/.rendimiento SI se wirean (la nota del mapa
las trata como LECTURA-equivalente para rrhh, introspeccion pura sin
escritura de negocio).

Nota sobre `handle`: sigue construyendo un RRHHDepartment fresco sobre un
InMemoryBus() propio (fuera del alcance de este pase: solo se pidio
reemplazar `mapa`/`rendimiento`/`propuestas`) — para intents de
mapa/rendimiento/propuestas via `handle`, seguira viendo el sistema vacio
de siempre porque delega en los METODOS de RRHHDepartment
(departments/rrhh/agente.py, fuera del ambito de este grupo). Los
wrappers `mapa`/`rendimiento`/`propuestas` de aqui abajo son ahora la
via honesta; `handle` queda documentado como pendiente."""
from __future__ import annotations

from core.bus import InMemoryBus
from cubos.base import manifiestos_instalados
from departments.base import Task
from departments.rrhh import herramientas as h
from departments.rrhh.agente import RRHHDepartment
from sustrato import bus as sbus

from panel_mando.herramientas.base import Argumento, ToolSpec

# Mismo esquema que panel_mando/colmena.py::_DDL (solo la tabla que nos
# interesa aqui). Duplicado deliberado y minimo: colmena.py esta fuera del
# ambito de este grupo de trabajo (lo edita otra persona en paralelo), y
# `CREATE TABLE IF NOT EXISTS` es idempotente — si colmena.py ya la creo,
# esto es un no-op; si esta herramienta corre antes que colmena.py en un
# proceso/tenant nuevo, la deja lista igualmente vacia (cobertura real 0%,
# nunca una excepcion de "no existe la tabla").
_DDL_COLMENA_AGENTES = """
CREATE TABLE IF NOT EXISTS colmena_agentes (
  empresa    TEXT NOT NULL,
  cubo       TEXT NOT NULL,
  role_id    TEXT NOT NULL,
  uid        TEXT NOT NULL UNIQUE,
  ts_alta    TEXT NOT NULL,
  evento_alta_id INTEGER,
  PRIMARY KEY (empresa, cubo)
);
"""


def _cubos_dados_de_alta(tenant: str) -> set[str]:
    """Cubos con un director REALMENTE dado de alta para `tenant`, leido de
    la tabla persistente `colmena_agentes` (panel_mando/colmena.py)."""
    conn = sbus.conexion()
    try:
        conn.executescript(_DDL_COLMENA_AGENTES)
        filas = conn.execute(
            "SELECT cubo FROM colmena_agentes WHERE empresa = ?", (tenant,)).fetchall()
        return {fila[0] for fila in filas}
    finally:
        conn.close()


def _mapa_real(tenant: str) -> dict:
    """Mismo contrato que RRHHDepartment.mapa()/h.mapa_capacidades(): dict
    con catalogo/presentes/faltantes/fuera_de_catalogo/cobertura — pero con
    datos reales y persistentes en vez de un bus desechable vacio."""
    catalogo = sorted(manifiestos_instalados())   # los 10 cubos reales en disco
    dados_de_alta = _cubos_dados_de_alta(tenant)
    catalogo_set = set(catalogo)
    presentes = sorted(dados_de_alta & catalogo_set)
    faltantes = sorted(catalogo_set - dados_de_alta)
    fuera_de_catalogo = sorted(dados_de_alta - catalogo_set)
    cobertura = round(len(presentes) / len(catalogo), 3) if catalogo else 0.0
    return {"catalogo": catalogo, "presentes": presentes, "faltantes": faltantes,
            "fuera_de_catalogo": fuera_de_catalogo, "cobertura": cobertura}


# ── LECTURA ──────────────────────────────────────────────────────────────

def _fn_handle(*, k, tenant, bitacora=None, intent: str = "estado", **kw) -> dict:
    dept = RRHHDepartment(InMemoryBus(), company=tenant)
    task = Task(intent=intent, payload={}, company=tenant)
    result = dept.handle(task)
    return {"ok": result.ok, "summary": result.summary, "data": result.data}


def _fn_mapa(*, k, tenant, bitacora=None, **kw) -> dict:
    return _mapa_real(tenant)


def _fn_rendimiento(*, k, tenant, bitacora=None, **kw) -> dict:
    return {
        "alertas": [],
        "datos_disponibles": False,
        "motivo": (
            "No hay una fuente PERSISTENTE de tasas de fallo/completado por "
            "departamento fuera del proceso vivo del panel (investigado: "
            "RRHHDepartment solo acumula completados/fallos en memoria "
            "mientras escucha el bus; el knowledge store no guarda ese "
            "contador — ver docstring del modulo). 'alertas: []' NO significa "
            "'se comprobo y no hay problemas': significa que esta herramienta "
            "no tiene de donde leerlos todavia."
        ),
    }


def _fn_propuestas(*, k, tenant, bitacora=None, **kw) -> dict:
    mapa = _mapa_real(tenant)
    propuestas: list[str] = []
    if mapa["faltantes"]:
        siguiente = mapa["faltantes"][0]
        propuestas.append(
            f"Dar de alta el director de «{siguiente}»: falta para completar el "
            f"catalogo real de {len(mapa['catalogo'])} cubos instalados "
            f"(cobertura actual {int(mapa['cobertura']*100)}%).")
    else:
        propuestas.append(
            f"Los {len(mapa['catalogo'])} cubos instalados tienen director dado de "
            f"alta. Sin huecos de cobertura.")
    propuestas.append(
        "Sin datos de rendimiento observables fuera del proceso vivo del panel "
        "(ver herramienta 'rendimiento'): no se proponen acciones de rendimiento "
        "por falta de fuente persistente, no porque no haga falta revisarlo.")
    return {"propuestas": propuestas}


def _fn_mapa_capacidades(*, k, tenant, bitacora=None, activos: str, **kw) -> dict:
    conjunto = {a.strip() for a in activos.split(",") if a.strip()}
    return h.mapa_capacidades(conjunto)


def _fn_roles_comite(*, k, tenant, bitacora=None, **kw) -> dict:
    return h.roles_comite()


HERRAMIENTAS: dict[str, ToolSpec] = {
    "handle": ToolSpec(
        nombre="handle", clase="LECTURA",
        descripcion="Ejecuta el flujo real del departamento de RRHH (RRHHDepartment.handle) "
                    "segun el texto de intent (mapa/capacidad, rendimiento/fallo, "
                    "propuesta/mejora, o estado general); emite el ciclo de vida al bus y "
                    "devuelve ok/summary/data. NOTA: a diferencia de 'mapa'/'rendimiento'/"
                    "'propuestas' de aqui abajo, 'handle' sigue construyendo un "
                    "RRHHDepartment sobre un bus desechable (fuera del alcance de este "
                    "pase) — para esos intents preferir las herramientas dedicadas.",
        argumentos=(
            Argumento("intent", "str",
                     "texto de intencion, p. ej. 'mapa de capacidades', 'rendimiento', "
                     "'propuestas de mejora' (informativo)", obligatorio=False),
        ),
        fn=_fn_handle),
    "mapa": ToolSpec(
        nombre="mapa", clase="LECTURA",
        descripcion="Mapa de capacidades REAL: catalogo = los cubos instalados en disco "
                    "(cubos.base.manifiestos_instalados), presentes = cubos con director "
                    "REALMENTE dado de alta para este tenant (tabla persistente "
                    "colmena_agentes). Devuelve {catalogo, presentes, faltantes, "
                    "fuera_de_catalogo, cobertura} con datos persistentes, no un bus "
                    "desechable vacio.",
        argumentos=(), fn=_fn_mapa),
    "rendimiento": ToolSpec(
        nombre="rendimiento", clase="LECTURA",
        descripcion="Alertas de bajo rendimiento por departamento. HONESTO: hoy no existe "
                    "una fuente persistente de tasas de fallo/completado fuera del proceso "
                    "vivo del panel, asi que devuelve {alertas: [], datos_disponibles: "
                    "False, motivo} en vez de fingir que comprobo y no encontro nada.",
        argumentos=(), fn=_fn_rendimiento),
    "propuestas": ToolSpec(
        nombre="propuestas", clase="LECTURA",
        descripcion="Propuestas de mejora derivadas de forma determinista de la cobertura "
                    "REAL (el cubo realmente faltante segun colmena_agentes, no siempre el "
                    "mismo del catalogo fijo). No inventa propuestas de rendimiento: no hay "
                    "datos persistentes que las respalden (ver herramienta 'rendimiento').",
        argumentos=(), fn=_fn_propuestas),
    "mapa_capacidades": ToolSpec(
        nombre="mapa_capacidades", clase="LECTURA",
        descripcion="Compara un conjunto de cubos activos (pasado por el llamador) contra "
                    "el catalogo objetivo de los diez cubos. Devuelve {catalogo, presentes, "
                    "faltantes, fuera_de_catalogo, cobertura}.",
        argumentos=(
            Argumento("activos", "str",
                     "nombres de cubos activos separados por comas, p. ej. "
                     "'comercial,brand,rrhh'"),
        ),
        fn=_fn_mapa_capacidades),
    "roles_comite": ToolSpec(
        nombre="roles_comite", clase="LECTURA",
        descripcion="Inventario de roles del comite de verificacion OpenGravity: numero de "
                    "roles de negocio, roles transversales y dominios cubiertos.",
        argumentos=(), fn=_fn_roles_comite),
}

__all__ = ["HERRAMIENTAS"]
