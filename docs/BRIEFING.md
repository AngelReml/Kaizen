# Módulo 5 — Generador de briefing pre-call

Convierte un `LeadDoc` en **contexto operativo** para la llamada. Dos consumidores:

1. **Humano (Iván)**: resumen en markdown legible — "qué sé de este lead y por qué le
   estoy llamando ahora".
2. **Agente conversacional (ElevenLabs CAI)**: diccionario de `dynamic_variables`
   que se inyectan en el system prompt y first_message vía `{{nombre_lead}}`,
   `{{ultimo_contacto_resumen}}`, etc.

## Filosofía

- **Determinista, sin LLM**. El briefing es un proyector del estado del lead a un
  formato consumible. No inventa nada. Si falta un dato, dice "n/d".
- **Trabaja sobre `LeadDoc` ya cargado**. El caller decide cómo lo carga (del
  KnowledgeStore, de un fixture, etc.). El módulo no toca disco.
- **`empresa_meta` opcional**: si el caller pasa el perfil de la empresa
  (`empresas/<empresa>/perfil.json`), el briefing puede personalizar el lenguaje
  ("Repostería Laboratorio" en vez de "nuestra empresa"). Si no, defaults neutros.
- **Idiomático ElevenLabs**: las dynamic_variables son strings (la API CAI no
  acepta otros tipos en el body de outbound-call).

## API

```python
brief = GeneradorBriefing(empresa_meta=None)  # dict opcional con perfil

# Para Iván (markdown)
texto: str = brief.generar_resumen(lead)

# Para ElevenLabs CAI (body de POST /v1/convai/twilio/outbound-call)
vars: dict[str, str] = brief.generar_dynamic_variables(lead)
```

## Variables generadas (mínimo)

| Variable | Origen | Ejemplo |
|---|---|---|
| `nombre_lead` | `lead.metadatos_extra.nombre_contacto` o `lead.nombre` | "Lidia" |
| `nombre_contacto` | `lead.metadatos_extra.nombre_contacto` (1) | "Lidia" |
| `negocio` | `lead.nombre` | "Repostería La Curva" |
| `categoria` | `lead.categoria_icp` | "panaderia_pasteleria" |
| `ciudad` | `lead.ubicacion.direccion` (parseo simple) | "Caudete" |
| `intentos_previos` | `lead.reintentos.intentos_realizados` | "2" |
| `razon_llamada` | derivado de estado pipeline + último resultado | "callback_pactado" |
| `compromisos_pendientes` | filtrado por `cumplido=False` | "callback hoy 10-11" |
| `ultima_interaccion_resumen` | `lead.interacciones[-1].resumen_llm` | "Habló con dependienta..." |
| `ultima_interaccion_dias_atras` | `now - lead.interacciones[-1].ts` | "1" |
| `decisor_conocido` | derivado del último resumen | "el encargado" o "n/d" |
| `empresa_nombre` | `empresa_meta.nombre` o "" | "Repostería Laboratorio" |
| `empresa_producto_clave` | `empresa_meta.producto_clave` o "" | "rollicos artesanos" |

Todos los valores son strings; números convertidos con `str()`; nulos como `""`
(NO `"None"`, NO `"null"`).

**(1)** El schema actual (M1) **no tiene campo dedicado** para el nombre de la
persona contacto — el campo `nombre` es el del negocio. Como solución
intermedia, el briefing busca el nombre de la persona en `lead.metadatos_extra
.nombre_contacto`. Deuda registrada en [[TODO]] para añadirlo como campo
de primera clase del Contacto cuando Iván decida.

## Resumen markdown (para Iván)

```
# Briefing — Repostería La Curva (Caudete)
**Estado**: queued → callback pactado para hoy 10:00-11:00 Madrid
**Decisor**: el encargado (no la persona que cogió el teléfono ayer)

## Última interacción (hace 1 día)
Habló con Lidia (dependienta). Pidió callback mañana entre 10 y 11 para
hablar con el encargado. Tono cordial.

## Compromisos pendientes
- callback — hoy 10-11h Madrid — tolerancia 60min

## Histórico
- Intento 1 (2026-05-26 18:16Z): contacted_no_decisor — 89s
```

## Lo que NO hace

- No decide a qué hora llamar — eso es el motor de reintentos.
- No envía la llamada — eso es eleven_outbound.
- No detecta compromisos nuevos — eso es el detector M4.
- No tira de LLM. Pura transformación de datos.

## Tests cubren

- Lead con todos los campos rellenos → resumen completo + variables completas.
- Lead nuevo (sin interacciones) → resumen "cold", razón "primer_contacto".
- Lead con compromisos cumplidos → no aparecen en pendientes.
- Lead con compromisos pendientes → aparecen ordenados por fecha_objetivo.
- `empresa_meta` ausente → defaults neutros sin crashear.
- Todas las dynamic_variables son strings (no `int`, no `None`).
- Ciudad parseada del campo dirección (último fragmento separado por coma).
