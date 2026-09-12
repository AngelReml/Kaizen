# Módulo 4 — Detector de compromisos

Convierte un transcript de llamada en una lista de **compromisos accionables** que
el sistema debe ejecutar después. ADR-004 ratificado.

## Qué es un compromiso (y qué no)

**SÍ es compromiso** algo accionable con fecha/referencia concreta:

- *Callback*: "Llámame mañana entre las 10 y las 11."
- *Muestra*: "Mándame una caja de rollicos a esta dirección."
- *Email_info*: "Mándame info por email a x@y.com."
- *Referido*: "Habla con mi mujer, ella decide; su teléfono es X."
- *Visita*: "Pásate la semana que viene por la tienda."

**NO es compromiso**:

- Cortesías y saludos ("hasta pronto", "que tengas buen día").
- Promesas vagas sin fecha ("ya te llamaré yo cuando me decida").
- Información del negocio del cliente (es contexto, no compromiso).
- Frases hipotéticas ("si me interesa ya te diré").

## Distinción con `CompromisoDetector` existente

`departments/comercial/sdr/compromiso.py` ya tenía un `CompromisoDetector` que decide
si una respuesta contiene **señales de Compromiso Recíproco** del v0.2 §3.2 (intención
clara de cerrar). Eso es un **clasificador binario**.

Este módulo (`core/compromisos.py`) hace algo distinto: **extracción estructurada
de eventos futuros concretos** del transcript completo, con fechas absolutas, tipo y
literales. Los dos coexisten — distinguidos por nombre: `DetectorCompromisos` aquí.

## API

```python
detector = DetectorCompromisos(chat=None, fecha_referencia_utc=None)
compromisos: list[Compromiso] = detector.detectar(transcript)
```

- `transcript`: lista de turnos con `{hablante: "agente"|"cliente", ts: float, texto: str}`.
- `fecha_referencia_utc`: datetime UTC. Si None, usa `datetime.now(UTC)`. Define
  el "hoy" del LLM para resolver fechas relativas ("mañana", "el viernes").
- Devuelve `list[Compromiso]` (subdoc del lead_schema). Lista vacía si no hay nada.

## Pipeline

```
Transcript (lista de turnos)
        │
        ↓
Formateado a diálogo legible: "AGENTE: ...\nCLIENTE: ...\n..."
        │
        ↓
Claude Sonnet 4.6 con system prompt específico + fecha_referencia
        │
        ↓
Output JSON: { "compromisos": [{tipo, fecha_objetivo, tolerancia_min,
                                 contexto, literal_cliente, literal_agente}, ...] }
        │
        ↓
Parser tolerante: regex extrae el bloque JSON, json.loads
        │
        ↓
Validación: cada compromiso tiene tipo válido (5 tipos) y fecha parseable
        │
        ↓
Lista de `Compromiso` (lead_schema) con `id` generado, `cumplido=False`
```

## Manejo de fechas relativas

El LLM recibe la `FECHA_REFERENCIA` (UTC + Madrid + día de la semana) y debe convertir:

- "mañana" → fecha_referencia + 1 día
- "la semana que viene" → fecha_referencia + 7 días
- "el viernes" → próximo viernes (si hoy es viernes, el siguiente)
- "en 15 días" → fecha_referencia + 15
- "entre las 10 y las 11" → hora exacta 10:00 + tolerancia_min=60
- "a las 10" o "sobre las 10" → 10:00 + tolerancia_min=15 (default)
- "por la mañana" sin hora → 11:00 + tolerancia_min=120
- "por la tarde" sin hora → 17:00 + tolerancia_min=120

## Manejo de zona horaria

El LLM razona en **hora local Madrid** y devuelve la fecha con el offset explícito
(`+02:00` verano, `+01:00` invierno). El parser **normaliza a UTC** antes de
almacenar. Ejemplo:

- LLM devuelve: `"2026-05-28T10:00:00+02:00"` (10:00 Madrid en mayo).
- Parser almacena: `"2026-05-28T08:00:00+00:00"` (UTC).

Esto separa responsabilidades: el LLM trabaja en la TZ del cliente (más fiable
que pedirle conversión a UTC), el código normaliza a UTC para el almacenamiento.

## Validación del output

El parser tolera:
- Bloques de markdown (```json ... ```).
- Texto suelto antes/después del JSON.
- Campos extras (se ignoran).

El parser RECHAZA y devuelve lista vacía:
- JSON no parseable (logueamos el error a stderr).
- `tipo` no está en {callback, muestra, email_info, referido, visita}.
- `fecha_objetivo` ni es null ni es ISO válido.

## Tests críticos

Test obligatorio: el transcript real de la llamada con Lidia
(`conv_3201ksjr0472f5gssmkcpw0mrjqj`) almacenado en
`tests/fixtures/transcript_lidia.json`. El detector debe extraer **un compromiso de
tipo `callback`** con `fecha_objetivo` = día siguiente a la llamada a las 08:00 UTC
(equivale a 10:00 hora Madrid) y `tolerancia_min ≥ 30` (franja 10-11).

Validado contra Claude Sonnet 4.6 real con `KAIZEN_TEST_LLM_REAL=1`: ✓ pasa.
Este test se salta en CI por defecto (requiere API key + opt-in).

## Lo que NO hace

- No persiste los compromisos al lead — eso lo hace el caller usando el
  `lead.compromisos.append(...)` o el motor de reintentos en su `aplicar()`.
- No comprueba si el compromiso ya existía — eso es responsabilidad del motor
  de reintentos (idempotencia por (tipo, fecha)).
- No envía recordatorios ni cumple los compromisos — eso es trabajo del scheduler
  / Director (módulos futuros).
