# Modelo de datos — Departamento de Finanzas (Fase 1.1)

## Modelo conceptual (Neo4j)
```
Nodos:
  (:Gasto {id, ts, modelo, usd, eur, tokens_in, tokens_out, accion, categoria, company})
  (:Categoria {nombre, company})
  (:Presupuesto {periodo, tope_eur, company})
  (:Alerta {id, nivel, mensaje, ts, resuelta, company})

Relaciones:
  (Gasto)-[:DE_CATEGORIA]->(Categoria)
  (Gasto)-[:CONTRA_PRESUPUESTO]->(Presupuesto)
  (Alerta)-[:DISPARADA_POR]->(Gasto)
```

## Realización en el código (adaptación)
El modelo se implementa **sobre la abstracción `KnowledgeStore`** (`core/knowledge.py`),
no con Cypher directo. Motivo: así es testeable en memoria HOY (`InMemoryKnowledge`) y
funciona con Neo4j cuando se valide en vivo (`Neo4jKnowledge`), sin reescribir la lógica.

- Cada `Gasto` se guarda como `knowledge.add(company, "gasto", id, {...})`.
- `Categoria`, `Presupuesto`, `Alerta` se modelan igual (tipo = nombre del nodo) cuando se
  necesiten persistir; por ahora la categoría va como propiedad del `Gasto` y el presupuesto
  es configuración (`PRESUPUESTO_MENSUAL_EUR` en el panel).
- Las relaciones del modelo conceptual se resuelven por las propiedades compartidas
  (`company`, `categoria`) al consultar; la versión con relaciones explícitas en Neo4j queda
  para cuando los grafos crezcan (ver [[DEUDA_TECNICA]]).

## Ingesta
`core/subscriptors/finanzas_ingestor.py` (`FinanzasIngestor`) escucha `COST_RECORDED` y crea
un `Gasto` por evento, aislado por empresa. Categoría automática por modelo
(`haiku`→tareas-ligeras, `sonnet`→análisis, `opus`→análisis-profundo).

**Limitación conocida:** el evento de coste no lleva el departamento origen, así que la
categorización fina por departamento no es posible aún (deuda #13). Se categoriza por modelo.

## Consultas
`departments/finanzas/herramientas.py` calcula de forma determinista sobre los `Gasto`:
`consultar_gasto`, `proyectar_quema`, `comparar_periodos`, `top_acciones_caras`,
`detectar_anomalia`. Sin LLM.
