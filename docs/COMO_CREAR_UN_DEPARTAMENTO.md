# Cómo crear un departamento (Fase 1.6)

Patrón obligatorio para construir un departamento real. Caso de estudio: **Finanzas**.
Todo departamento nuevo replica estas 9 secciones y produce su documento equivalente.

---

## 1. Resumen ejecutivo
Una frase: qué hace el departamento.
> **Finanzas:** vigila el gasto en tiempo real, responde preguntas sobre dinero con datos
> reales y aplica reglas duras de presupuesto.

## 2. Modelo de datos
Entidades, relaciones, schema. Se implementa sobre `KnowledgeStore` (memoria/Neo4j).
> **Finanzas:** nodos `Gasto` (+ Categoria/Presupuesto/Alerta conceptuales). Ver
> `docs/FINANZAS_SCHEMA.md`.

## 3. Subscriptor de bus
Qué eventos consume y qué nodos crea. Archivo en `core/subscriptors/`.
> **Finanzas:** `FinanzasIngestor` escucha `COST_RECORDED` → crea un `Gasto` por evento,
> aislado por empresa.

## 4. Reglas duras propias
Funciones puras `(pasa: bool, motivo: str)`, inyectadas en el Guardián vía `reglas_extra`
(el departamento depende de `core`, nunca al revés). Archivo `departments/<dep>/reglas.py`.
> **Finanzas:** `gasto_diario_supera_porcentaje`, `tasa_llamadas_por_minuto`,
> `coste_unico_supera_techo` + adaptador `como_regla_guardian`.

## 5. Herramientas
Funciones deterministas (Python, sin LLM) que calculan sobre el `KnowledgeStore`. El LLM
las orquesta, pero los números salen de aquí. Archivo `departments/<dep>/herramientas.py`.
> **Finanzas:** `consultar_gasto`, `proyectar_quema`, `comparar_periodos`,
> `top_acciones_caras`, `detectar_anomalia`.

## 6. Agente conversacional
Hereda de `Department`. `responder(pregunta, company)` elige la herramienta y compone la
respuesta con datos reales. Reemplaza al cascarón en `especialistas.py`.
> **Finanzas:** `FinanzasDepartment` (selector por keywords; tool-use LLM es la evolución).
> Debe responder: cuánto se ha gastado, cuántos días de runway, acción más cara, gasto raro,
> comparar periodos.

## 7. Vista en el panel
Tarjeta + endpoint que la alimenta. Actualiza en vivo con los eventos relevantes del bus.
> **Finanzas:** tarjeta con gasto del mes (barra vs presupuesto), gasto del día, runway y
> alertas; endpoint `GET /finanzas`; se refresca al llegar eventos `cost.*`.

## 8. Tests obligatorios
Un archivo por pieza, con datos sembrados y resultado verificable.
> **Finanzas:** `test_finanzas_ingestor`, `test_finanzas_reglas` (adversariales),
> `test_finanzas_herramientas`, `test_finanzas_agente` (elección de herramienta).

## 9. Caso de estudio
Extractos reales del departamento construido como referencia. Para Finanzas, este mismo
documento + el código en `departments/finanzas/` y `core/subscriptors/finanzas_ingestor.py`.

---

### Checklist para un departamento nuevo
- [ ] `docs/<DEP>_SCHEMA.md`
- [ ] `core/subscriptors/<dep>_ingestor.py` (si consume eventos)
- [ ] `departments/<dep>/reglas.py` + tests adversariales
- [ ] `departments/<dep>/herramientas.py` + tests con datos sembrados
- [ ] `departments/<dep>/agente.py` (reemplaza el cascarón) + test de elección de herramienta
- [ ] Tarjeta + endpoint en el panel
- [ ] Wire en `api/server.py` (ingestor, dept real, reglas_extra del Guardián)
- [ ] Documento equivalente a este, instanciado para el departamento

---
Relacionados: [[FINANZAS_SCHEMA]]
