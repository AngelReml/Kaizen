# Módulo 6 — Consulta natural (NLQ)

`kaizen pregunta "¿cuántos hoteles boutique tengo en queued?"` → respuesta legible.

ADR-005 ratificado: **text-to-filter**, no text-to-SQL. El LLM solo decide QUÉ
filtros aplicar; quien filtra es código determinista. Cero ejecución de código
ni SQL generados.

## Filosofía

- **Seguridad por construcción**: el LLM nunca produce código ejecutable, solo
  un JSON con campos y operadores de una lista cerrada. Si genera un operador
  desconocido, se descarta con error legible.
- **Schema cerrado**: los campos consultables son una lista finita (ver abajo).
  Nada de "consulta cualquier cosa" — solo lo modelado.
- **Determinismo**: misma pregunta da mismo resultado si el knowledge no cambió.
- **Knowledge loader inyectable**: tests sin disco; producción usa
  `KnowledgeStore` con la empresa.

## API

```python
nlq = ConsultaNatural(chat=None, knowledge_loader=None, company="laboratorio")
respuesta: str = nlq.responder("¿cuántos hoteles en queued?")

# Para tests o composición:
consulta: Consulta = nlq.interpretar(pregunta)  # LLM
resultado: dict = nlq.aplicar(consulta, leads)
texto: str = nlq.formatear(resultado, consulta)
```

## Schema de la consulta

```python
@dataclass
class FiltroConsulta:
    campo: str       # uno de CAMPOS_CONSULTABLES
    op: str          # uno de OPERADORES (eq, neq, gte, lte, contains, tiene)
    valor: str|int|float|bool

@dataclass
class Consulta:
    filtros: list[FiltroConsulta]
    tipo_respuesta: str   # "count" | "list" | "summary"
    limite: int = 20      # max leads a listar
    agrupar_por: str|None = None   # solo si tipo_respuesta == "summary"
```

## Campos consultables (lista cerrada)

| Campo | Op válidos | Notas |
|---|---|---|
| `estado_pipeline` | eq, neq | uno de los 12 estados M2 |
| `categoria_icp` | eq, neq, contains | "hotel_boutique_con_desayuno", etc. |
| `prioridad_icp` | eq, neq | "ALTA", "MEDIA", "BAJA" |
| `anillo` | eq, gte, lte | int |
| `intentos_realizados` | eq, gte, lte | int de `reintentos.intentos_realizados` |
| `do_not_call` | eq | bool |
| `ciudad` | eq, contains | parseada de `ubicacion.direccion` |
| `tiene_compromiso` | tiene | "callback" / "muestra" / "*" (cualquiera pendiente) |
| `dias_desde_ultima_interaccion` | gte, lte | int |
| `tipo_detectado` | eq, contains | "hotel", "restaurante", etc. |

Cualquier campo fuera de esta lista → filtro descartado + warning.

## Operadores (lista cerrada)

- `eq` / `neq`: igualdad / desigualdad
- `gte` / `lte`: numérico
- `contains`: substring case-insensitive (solo en strings)
- `tiene`: presencia de compromiso pendiente del tipo dado (* = cualquiera)

## Tipos de respuesta

- `count`: número total y un breve listado de los 3 primeros como muestra.
- `list`: hasta `limite` resultados con id, nombre, estado, ciudad.
- `summary`: agrupado por `agrupar_por` (campo). Devuelve breakdown.

## Prompt al LLM

System prompt explícito con:

1. Lista de campos consultables (no inventar).
2. Lista de operadores válidos.
3. Schema JSON exacto a devolver.
4. Pocos ejemplos one-shot.
5. Si no entiende la pregunta → devuelve `{"error": "no_interpretable", "razon": "..."}`.

## Lo que NO hace (esta iteración)

- Consultas con fechas relativas complejas ("hace dos viernes") → unsupported,
  registrado en [[TODO]].
- Joins entre leads (ej. "quién pidió la misma muestra que X") → unsupported.
- Modificar leads → solo lectura. Comando separado en el futuro.
- Caché — siempre relee el knowledge.

## Tests cubren

- Parser puro: JSON limpio, markdown, error explícito, operador inválido,
  campo inválido, valor de tipo incorrecto.
- Aplicador puro (sin LLM): count, list con límite, summary con groupby,
  filtros encadenados (AND), `tiene_compromiso` filtrando pendientes,
  `dias_desde_ultima_interaccion` cálculo correcto contra clock fijo.
- Pipeline completo con chat mock.
- Opcional opt-in con LLM real contra preguntas en español.
