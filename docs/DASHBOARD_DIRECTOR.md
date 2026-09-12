# Módulo 7 — Director comercial · Dashboard

Vista panel del estado del departamento comercial. `kaizen comercial dashboard`.

## Filosofía

- **Determinista, sin LLM**. Proyecta el knowledge a un panel legible. Igual que
  briefing M5 — el LLM no decide qué se muestra.
- **No es el orquestador**: `departments/comercial/director.DirectorComercial`
  sigue siendo la unidad operativa de Fase 0. Este módulo es una **vista** del
  estado, no muta nada.
- **Modular**: `DashboardDirector.datos_para_dashboard()` devuelve un dict
  estructurado; `renderizar()` lo formatea a markdown plano (para logs / web);
  `imprimir(console)` lo pinta en consola con `rich`.

## Secciones del panel

1. **Cabecera**: empresa + timestamp Madrid.
2. **Estado del pipeline**: count por cada uno de los 12 estados con barra de %.
3. **Próximas acciones (24h)**: leads con `proxima_accion_ts` en próximas 24h.
4. **Compromisos pendientes (hoy/mañana)**: callback / muestra / referido /
   visita / email_info con fecha próxima, ordenados.
5. **Histórico reciente (últimos 7 días)**: interacciones agregadas con
   resultado, duración, lead.
6. **Compromisos vencidos sin cumplir**: alerta de fechas pasadas con
   `cumplido=False`.
7. **Embudo de conversión**: cold → contacted → engaged → customer con %.

## API

```python
dash = DashboardDirector(
    knowledge_loader=lambda: list_of_leads,
    empresa="laboratorio",
    clock=lambda: datetime.now(timezone.utc),
)

# Para tests / web / API:
datos: dict = dash.datos_para_dashboard()

# Markdown plano (logs, ficheros):
texto: str = dash.renderizar()

# Consola interactiva:
dash.imprimir(console=Console())   # rich
```

## Estructura del dict `datos_para_dashboard`

```python
{
  "empresa": str,
  "timestamp_madrid": str,        # "2026-05-27 14:30 Madrid"
  "total_leads": int,
  "estado_pipeline": {            # 12 buckets ordenados por matriz M2
    "cold": int, "queued": int, ..., "do_not_call": int,
  },
  "proximas_acciones_24h": [      # ordenadas por ts asc
    {"lead_id": str, "nombre": str, "ciudad": str,
     "ts_madrid": str, "tipo": str},
    ...
  ],
  "compromisos_proximos": [       # pendientes con fecha en próximos 7 días
    {"lead_id": str, "nombre": str, "tipo": str, "ts_madrid": str,
     "tolerancia_min": int, "contexto": str},
    ...
  ],
  "interacciones_recientes": [    # últimos 7 días, descendente por ts
    {"lead_id": str, "nombre": str, "ts_madrid": str,
     "resultado": str, "duracion_s": int},
    ...
  ],
  "compromisos_vencidos": [       # fecha < ahora && cumplido=False
    ... mismo shape que proximos
  ],
  "embudo": {                     # cold + contacted + engaged + customer
    "cold": int, "contacted_o_mas": int, "engaged_o_mas": int,
    "customer": int,
    "tasa_contact": float,        # contacted_o_mas / cold (0-1)
    "tasa_engaged": float,        # engaged_o_mas / contacted_o_mas
    "tasa_customer": float,       # customer / engaged_o_mas
  },
}
```

## Lo que NO hace

- No genera estrategias. Iván ve el panel y decide.
- No envía mensajes ni programa acciones — esa es responsabilidad del SDR /
  motor de reintentos.
- No incluye dashboards web (HTML) — solo terminal en esta iteración. El JSON
  estructurado existe para construirlos en el futuro sin reescribir lógica.

## Tests cubren

- `datos_para_dashboard`: 12 buckets siempre presentes (incluso si están a 0),
  ordenación por timestamp en próximas acciones, ventana 24h respetada,
  compromisos vencidos vs próximos correctamente separados, embudo con
  tasas calculadas, división por cero → 0.0.
- `renderizar` markdown: secciones presentes, "ninguno" cuando vacío.
- Casos borde: knowledge vacío, lead sin reintentos, lead sin compromisos.
