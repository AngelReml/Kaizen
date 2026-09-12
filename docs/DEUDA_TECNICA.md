# Deuda técnica — auditoría honesta

*Fase 0.4 del roadmap. Lista sin maquillaje de lo que se simplificó o se hizo mal al
construir el esqueleto. Para cada ítem: archivo, qué falla, impacto y fase de arreglo.*

---

## Los 6 ítems mínimos exigidos por el roadmap

### 1. Enrutado por keywords frágil
- **Dónde:** `core/director.py:_keyword_router` + dict `ROUTING`.
- **Qué falla:** el enrutado elige el primer departamento cuya keyword aparezca en la intención, en orden de diccionario. Términos se solapan: "revisa" está en QA, pero "revisa el contrato" debe ir a Legal (funciona solo porque Legal está antes en el dict). Una intención ambigua va al departamento equivocado sin avisar. No hay desempate ni confianza.
- **Impacto:** medio. Enrutados incorrectos silenciosos; el usuario no sabe por qué su orden fue a otro sitio.
- **Arreglo:** Fase 1+ (router LLM con score de confianza; si baja del umbral, el Director pregunta). Ya está previsto como sustituible.

### 2. Departamentos especialistas son cascarones
- **Dónde:** `departments/especialistas.py` (legal, desarrollo, qa, finanzas, ops, rrhh).
- **Qué falla:** los 6 son la misma clase `LLMDepartment` con distinto prompt. No tienen modelo de datos, ni reglas duras propias, ni herramientas, ni memoria. Solo responden texto del LLM. Reporté la "Fase 5" como hecha cuando son fachadas.
- **Impacto:** alto. El sistema *parece* tener 8 departamentos; tiene 2 reales (Prospección, Redacción) y 6 fachadas.
- **Arreglo:** Fase 1 (Finanzas real como plantilla) y Fase 5 (QA, Ops, Legal reales) del roadmap nuevo.

### 3. El Guardián semántico asume buena fe del LLM
- **Dónde:** `core/guardian.py:GUARDIAN_SEMANTIC_SYSTEM` + `llm_semantic_evaluator`.
- **Qué falla:** la defensa de nivel 2 es un prompt que pide al LLM detectar inyección. Un atacante motivado puede construir contenido que evada el clasificador (es el problema clásico de un LLM juzgando texto adversarial). El parseo del veredicto es por substring ("BLOCKED" in resp), engañable si el motivo contiene esa palabra.
- **Impacto:** medio-alto (la mitigación real es que las reglas duras de nivel 1 van primero y no dependen del LLM; pero el nivel 2 da falsa sensación de robustez).
- **Arreglo:** Fase 3+ (batería adversarial más amplia; parseo estructurado del veredicto; defensa en profundidad).

### 4. El WebSocket emite a todos sin filtrar por empresa
- **Dónde:** `api/server.py:_broadcaster` + `_on_event`.
- **Qué falla:** todos los eventos se envían a todos los clientes conectados; el filtrado por empresa es **solo en el cliente** (JS). Un cliente malicioso/curioso recibe por el cable los eventos de TODAS las empresas y los ve en DevTools. El aislamiento multi-empresa NO se cumple en el transporte.
- **Impacto:** alto en cuanto haya más de un cliente/empresa con datos sensibles. Fuga de datos entre empresas a nivel de transporte.
- **Arreglo:** Fase 3/6 (filtrado server-side: el WS se suscribe a una empresa según el usuario autenticado; nunca se le envían eventos de otras).

### 5. Extracción de emails sin validación
- **Dónde:** `agentes.py:_extract_emails`.
- **Qué falla:** regex permisiva; acepta emails malformados, imágenes con texto tipo email, falsos positivos de páginas. No valida MX ni sintaxis estricta. El primer email encontrado se usa como destinatario.
- **Impacto:** medio. Riesgo de enviar a direcciones basura o equivocadas (peor con envío real activo).
- **Arreglo:** Fase 2.3 / Fase 3.4 (validación de sintaxis, verificación de dominio/MX, blacklist de bounces).

### 6. Aserción de test cambiada durante la sesión
- **Dónde:** `tests/test_multiempresa.py:test_bus_aislado_dos_empresas`.
- **Qué pasó:** la aserción original comprobaba que ninguna palabra del contenido de una empresa apareciera en el flujo de la otra. Falló porque el `_sim_executor` devolvía leads fijos ("Ejemplo Gourmet S.L.") para TODA empresa, así que "gourmet" salía en las dos. Se cambió a comprobar solo el campo `intent`.
- **Veredicto:** el cambio fue **legítimo** (el aislamiento por `company` sí funciona; la aserción era demasiado amplia), PERO tapó la deficiencia real: el simulador no era contextual.
- **Estado:** la deficiencia de fondo se ha arreglado en Fase 0.3 (simulador contextual por sector). La aserción actual es correcta.

---

## Deuda adicional encontrada en la auditoría

### 7. El panel auto-aprueba todo
- **Dónde:** `api/server.py` — `Director(..., confirm=lambda _: True)`.
- **Qué falla:** el bucle de reflexión del Director (aprobación humana por criticidad) está cortocircuitado en el panel: todo se aprueba solo. Hoy no hace daño porque Prospección es de baja criticidad, pero en cuanto un departamento emita acciones de alta criticidad, se ejecutarían sin pregunta.
- **Impacto:** alto en el futuro. Anula una garantía de control.
- **Arreglo:** Fase 3 (human-in-the-loop real sobre WebSocket: el panel muestra la solicitud y el humano aprueba/deniega).

### 8. El envío esquiva el corto-circuito del Guardián con un truco
- **Dónde:** `agentes.py:enviar_borrador_guardado`.
- **Qué falla:** como `guardian.evaluate("send_email")` escala por regla dura ANTES de correr la capa semántica, el chequeo de contenido se hace usando un kind falso `"draft_review"` para forzar que corra el semántico. Funciona, pero es un hack que indica que el diseño del Guardián no contempla bien "irreversible + revisar contenido" a la vez.
- **Impacto:** bajo-medio (funciona, pero es frágil ante cambios).
- **Arreglo:** Fase 3 (rediseñar `Guardian.evaluate` para componer reglas duras + semántica sin cortocircuito).

### 9. RedisStreamsBus no tiene consumidores entre procesos
- **Dónde:** `core/bus.py:RedisStreamsBus`.
- **Qué falla:** `publish` despacha a los suscriptores **en el mismo proceso** y persiste en el stream; no usa grupos de consumidores. El replay tras reinicio funciona, pero un segundo proceso (p. ej. un worker) no recibe eventos en vivo. La promesa de "cualquier departamento reacciona a cualquier otro" se rompe en arquitectura multiproceso.
- **Impacto:** alto cuando se separen workers del API (Fase 8.1).
- **Arreglo:** Fase 4/8 (grupos de consumidores Redis Streams + ack).

### 10. Adaptadores Neo4j/Postgres nunca validados en vivo
- **Dónde:** `core/knowledge.py:Neo4jKnowledge`, `core/config_store.py:PostgresConfig`.
- **Qué falla:** escritos "a ciegas" según las APIs, sin ejecutarse jamás contra los servicios reales. Bugs probables: serialización de `datetime` en Cypher, `client_encoding` en Postgres, reconexión.
- **Impacto:** alto hasta validarse.
- **Arreglo:** Fase 0.1 (en curso; tests reales escritos en `test_persistencia_real.py`, pendientes de `docker compose up`).

### 11. Parseo frágil del markdown del LLM
- **Dónde:** `agentes.py:_split_fichas` y `_extraer_borrador`.
- **Qué falla:** dependen de que el LLM use exactamente `### ` para candidatos y `## Borrador aprobado` / `**Asunto:**`. Si el LLM varía el formato, el parseo falla en silencio (0 fichas, borrador no encontrado).
- **Impacto:** medio. Pérdida silenciosa de datos generados.
- **Arreglo:** Fase 1+ (pedir salida estructurada JSON al LLM en vez de parsear markdown).

### 12. Orden causal de eventos en el panel
- **Dónde:** `core/bus.py:InMemoryBus.publish` (despacho síncrono anidado).
- **Qué falla:** cuando un evento dispara otros durante su despacho, los hijos pueden llegar al panel antes que el padre (se vio: redacción aparece antes que el "completed" de prospección).
- **Impacto:** bajo (cosmético en el feed).
- **Arreglo:** Fase 4 (orden por ID de stream de Redis con consumidores asíncronos).

### 13. Contabilidad de coste global, no por empresa en disco
- **Dónde:** `claude_client.py` (`.kaizen_cost.json` es global).
- **Qué falla:** el coste se guarda en un único archivo global; los eventos llevan `company` pero el archivo no separa por empresa. El presupuesto es del sistema entero, no por cliente.
- **Impacto:** medio cuando haya varios clientes (no se puede facturar coste por cliente).
- **Arreglo:** Fase 1 (departamento Finanzas: ingestor a Neo4j con `Gasto` por empresa).

### 14. Prompt de sesión de la CLI aún codifica Laboratorio
- **Dónde:** `kaizen.py:SESSION_SYSTEM` y `BANNER`.
- **Qué falla:** la CLI sigue diciendo "Repostería Laboratorio" a fuego (el refactor multi-empresa del Block C tocó los agentes, no el chat de la CLI).
- **Impacto:** bajo (la CLI es la herramienta personal de Laboratorio; pero es inconsistente con multi-empresa).
- **Arreglo:** Fase 6.1 (auditoría de hardcoding completa).

### 15. Sin pytest en el entorno; runners manuales
- **Dónde:** todos los `tests/test_*.py`.
- **Qué falla:** los tests traen su propio runner en `__main__`. Funciona, pero no hay configuración pytest unificada, ni cobertura, ni CI.
- **Impacto:** bajo-medio.
- **Arreglo:** Fase 4.2 (CI/CD con pytest + cobertura).

---

## Resumen
- **Crítico antes de cliente externo:** #4 (fuga WS entre empresas), #7 (auto-aprobación), #10 (backends sin validar).
- **Importante para producto real:** #2 (cascarones), #1 (router), #13 (coste por empresa), #5 (emails).
- **Mejora continua:** el resto.

Ningún ítem es sorpresa: son el precio de construir un esqueleto completo rápido. El roadmap los recoloca en su fase. Esta lista es el contrato de honestidad: no se da por "hecho" lo que está aquí hasta que su fase lo cierre.

---

## Resueltos
- **`guardian.py` (raíz) + `check_budget` + `check_no_env_access` — RESUELTO (2026-05-25).**
  El módulo de la raíz colisionaba de nombre con `core/guardian.py` (el Guardián real del SOE)
  y contenía dos funciones muertas (`check_budget`, `check_no_env_access`) que duplicaban la
  lógica de `core/guardian.py:_hard_rules` y no las llamaba nadie. Se renombró a `cli_utils.py`
  conservando solo las 3 funciones vivas (`sanitize_query`, `max_retries`, `require_approval`);
  las dos muertas se eliminaron. Imports actualizados en `agentes.py` y `departments/prospeccion.py`.

---

## Registro E6 (CORRECCIONES v1.0) — 2026-07-03

Formato: id | test/pieza | causa | ¿bloquea? | coste estimado

**DT-26.07.03-1 · Tests de voz escriben la quota REAL (incidente hoy).**
`tests/test_voz_eleven_outbound.py` (y pre_flight) incrementan `state/voz/quota/quota_YYYYMMDD.json` de PRODUCCION en cada ejecucion de la suite; tras ~12 ejecuciones en el dia, el contador llego a 25/25 y 3 tests cayeron (suite 678/2). Incidente E1: ruta `state/voz/quota/quota_20260703.json`, detectado 2026-07-03T18:44Z por checklist §4, resuelto con backup `*.bak_incidente_tests` + reset a `{"n": 0}` + suite verificada 680/7. NO bloquea si se resetea; se re-envenena con >~12 suites/dia. Arreglo real: fixture tmp para quota en esos tests (~30 min) — corresponde a la vuelta del trabajador de voz (hoy de baja por orden del operador).

**DT-26.07.03-2 · test_ws_replay_al_conectar dependia del orden de la suite. RESUELTO 2026-07-03.**
Causa: api.server carga .env (KAIZEN_TOKEN entra al entorno) y solo test_auth lo limpiaba. Arreglo aplicado en test_panel.py (pop tras import). Evidencia: pasa aislado y en suite.

**DT-26.07.03-3 · Dos IDs de modelo Sonnet conviven** (`claude-sonnet-4-6` en claude_client/agentes/consulta_natural; `claude-sonnet-4-5` en model_router/cost_tracker). No bloquea hoy; riesgo de 404 futuro. Coste: 15 min + decision de Ivan sobre el ID canonico.

**DT-26.07.03-4 · Doble contabilidad de coste** (claude_client.py vs core/cost_tracker.py, tarifas divergentes). El [[SUSTRATO|sustrato]] ya SUMA ambas para el freno; unificar tarifas: ~1-2 h. No bloquea.

**DT-26.07.03-5 · Voz aparcada (no tocar sin orden):** webhooks con empresa fija, pii_redaction no llega a ElevenLabs, redeploy v2 pendiente, prefijo 400 (limite oct-2026). Bloquea SOLO llamadas reales.

**DT-26.07.03-6 · [[CENTRO_DE_MANDO|Centro de Mando]] sin token local** (127.0.0.1 sin auth). Riesgo bajo (solo local); coste ~30 min. No exponer jamas por tunel tal cual.

**DT-26.07.03-7 · `contratados` es marcador sin enforcement en gates** (decision v1 documentada). Coste enforcement: ~1 h. No bloquea: autonomia+[[COMITE_3X3|comite]] siguen mandando.
