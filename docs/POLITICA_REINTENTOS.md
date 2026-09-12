# Módulo 3 — Motor de reintentos

Decide **cuándo** se vuelve a tocar a un lead, **cómo** (llamar / email / nurturing) y
**si se rinde** (LOST / DO_NOT_CALL). Reglas data-driven en JSON por empresa.

## Filosofía

- El motor **no muta el lead** directamente. Recibe (lead, resultado de la última
  interacción) y devuelve una `RecomendacionReintento`. El caller (SDR / Director)
  decide si la aplica.
- La política vive en `empresas/<empresa>/politica_reintentos.json` y se carga al
  arrancar. Iván puede editar sin tocar código (ADR-003).
- Cada categoría de lead puede tener overrides — un hotel boutique puede valer 5
  intentos donde una gasolinera vale 2.
- Las **franjas horarias comerciales** son respetadas para programar la próxima
  llamada: si toca reintentar en 2h y eso cae fuera de franja, se desplaza a la
  siguiente ventana válida.

## Casos cubiertos (mínimo)

| Resultado de la interacción | Acción del motor |
|---|---|
| `no_answer` | Reintento en 2-4h aleatorio, máximo 3 en ventana 7 días, rotando franja. Al alcanzar el máximo → LOST con razón "max_intentos_no_answer". |
| `callback_pactado` | Crea `Compromiso(tipo=callback)`, programa `proxima_accion_ts` = fecha pactada con tolerancia 15min. Pipeline → QUEUED. |
| `no_buen_momento_sin_fecha` | Reintento en 7 días (configurable), pipeline → QUEUED. |
| `no_interesa_ahora` | Nurturing en 3 meses, pipeline → QUEUED con tipo `nurturing`. |
| `no_interesa` | Pipeline → LOST. Razón obligatoria. |
| `opt_out` | Pipeline → DO_NOT_CALL. `lead.do_not_call=True`. Terminal duro. |
| `contacted_no_decisor` (caso Lidia) | Si pacta callback → ver `callback_pactado`. Si no → reintento `no_answer` estándar. |
| `engaged_pide_muestra` | Pipeline → SAMPLE_REQUESTED. Crea compromiso de envío. |

## Schema del JSON

```json
{
  "version": "1.0",
  "empresa": "laboratorio",
  "actualizado": "2026-05-27",
  "default_max_intentos": 5,
  "franjas_horarias_es": ["10-13", "16-19"],
  "dias_laborables": [0, 1, 2, 3, 4],
  "reglas": {
    "no_answer": {
      "intervalo_min_horas": 2,
      "intervalo_max_horas": 4,
      "max_intentos": 3,
      "ventana_dias": 7
    },
    "no_buen_momento_sin_fecha": {"espera_dias": 7},
    "no_interesa_ahora": {"espera_meses": 3},
    "no_interesa": {"transicion": "lost", "razon": "cliente expresó no interés"},
    "opt_out": {"transicion": "do_not_call", "razon": "cliente pidió no más llamadas"},
    "callback_pactado": {"tolerancia_min": 15}
  },
  "categorias_override": {
    "hotel_boutique_con_desayuno": {
      "no_answer": {"max_intentos": 5}
    }
  }
}
```

## Flujo

```
[Resultado de interacción] → MotorReintentos.decidir(lead, resultado, contexto)
                                       │
                                       ↓
                          RecomendacionReintento {
                            transicion_a,            # str | None
                            proxima_accion_tipo,     # llamar/email/nurturing/none
                            proxima_accion_ts,       # ISO UTC
                            razon,
                            compromiso_a_crear,      # Compromiso | None
                            do_not_call_flag,        # bool
                          }
                                       │
                                       ↓
                 SDR / Director → motor.aplicar(lead, rec, pipeline_machine)
```

## Cálculo de "siguiente franja válida"

Si el motor decide "reintentar en 3h" y eso cae fuera de franja comercial española
(L-V 10-13 / 16-19), la próxima acción se desplaza al inicio de la siguiente ventana
válida. Ejemplos:

- Lunes 12:30 + 3h = 15:30 → cae en pausa de comida → se mueve a 16:00.
- Viernes 18:00 + 4h = 22:00 → se mueve al lunes 10:00.

La rotación de franja para `no_answer` (mismo lead, varios reintentos) es: el 1er
intento en franja mañana, 2º en tarde, 3º en franja distinta del día siguiente.

## Tests cubren

- Cada uno de los resultados anteriores (8 casos).
- `no_answer` con max_intentos alcanzado → LOST.
- `no_answer` con override por categoría (hotel boutique = 5 intentos).
- Cálculo de franja: timestamp que cae en pausa de comida → ajustado al inicio
  de la franja siguiente.
- Cálculo cross-weekend (viernes tarde → lunes mañana).
- `callback_pactado` crea compromiso con tolerancia configurada.
- `aplicar()` muta el lead correctamente (transición + reintentos + compromiso).
- Re-aplicar la misma recomendación es idempotente (no duplica compromiso).
- Política inexistente → fallback a defaults razonables (no crash).
