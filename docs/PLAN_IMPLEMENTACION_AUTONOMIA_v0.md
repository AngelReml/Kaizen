# Plan de implementación — Autonomía v0

Estado: **ejecutado F0–F6 el 2026-10-01** (ver §6 Resultado). F7 = cierre.
Decisiones de Ángel (confirmadas): **F1 G1 H1 I1 J1** (ver `docs/SUELO_Y_VOCABULARIO_v0.md` para el contexto firmado).
Rama: `claude/clever-wozniak-p7mins`. No se toca Shinobi ni se mezclan Planta 1 / Planta 2.

---

## 1. Qué hay hoy (verificado leyendo el código, no de memoria)

| Hecho | Dónde |
|---|---|
| 3 clases de acción: REVERSIBLE / IRREVERSIBLE-INTERNA / IRREVERSIBLE-EXTERNA | `core/aprobaciones.py` |
| 4 niveles CERO/BAJA/MEDIA/ALTA, **definidos en 5 sitios independientes** | `core/aprobaciones.py`, `core/tenants.py`, `sustrato/gates.py`, `sustrato/config.py`, `centro_mando.py` |
| Camino **Colmena** (panel): CERO solo lee; BAJA+ escribe reversible y propone tarjetas; **MEDIA y ALTA se comportan como BAJA** (solo cambia el texto) | `panel_mando/colmena.py` (`_NIVEL_EXPLICA`, `_validar_propuesta`) |
| Camino **gates** (SQLite, legado de Comercial): la matriz exige nivel mínimo por acción; **ALTA es el mínimo para email real, contacto saliente y compromiso ante cliente, siempre con comité** | `sustrato/gates.py` (`MATRIZ_ACCIONES`) |
| El nivel que lee la Colmena es **solo el valor por defecto del manifest** (estático). No existe un nivel "efectivo" por empresa y cubo | `colmena.py` 282/442/623/826, `mundo.py` 474 |
| `cambiar_nivel()` (solo endurecer; relajar exige operador; se registra) **no está conectada a nada**: solo la llama un test | `core/aprobaciones.py:179` |
| Ya existe un techo diario de coste por empresa con escalera de degradación | `core/techos.py` |
| El patrón para que el operador cambie un ajuste con auditoría ya existe | `app.py` `/cmd/ajustes/tope` |
| Barrido periódico del panel (donde ya se engancha `barrer_caducadas`) | `app.py` ~289 |
| Cubos en CERO: **Inteligencia, Calidad, RRHH**. El resto en BAJA | `cubos/*/manifest.json` |

## 2. Correcciones a lo que dije antes (honestidad)

1. Dije que MEDIA y ALTA eran idénticos a BAJA. **Solo es cierto en la Colmena.** En `sustrato/gates` ALTA sí es distinto: habilita acciones externas con comité.
2. Dije que G1 ("bajar un nivel ante incidentes") era una tarea pequeña. **No lo es:** no existe un nivel efectivo por empresa y cubo; hay que crearlo y leerlo en 5 puntos.
3. G1 incluía "tope de gasto superado". El monedero de 50 € **aún no existe**. Lo único que hay es el techo diario por empresa, que ya tiene su propia escalera de degradación. **Desviación propuesta:** el gatillo de gasto de G1 queda cubierto por `core/techos.py` y no se duplica. G1 implementa dos gatillos: sello roto y 3 denegaciones seguidas.

## 3. Fases (cada una con su prueba; un commit por fase)

### F0 — Documento de autonomía (solo texto)
`docs/AUTONOMIA_v0.md`: matriz clase × nivel, significado de cada nivel, decisiones F1 G1 H1 I1 J1, límites conocidos.
Prueba: revisión de Ángel.

### F1 — Honestidad de los niveles (F1)
- `_NIVEL_EXPLICA`: MEDIA y ALTA se describen como **reservados** y se aclara que hoy se comportan como BAJA en la Colmena. No se promete a un agente nada que el código no hace (por ejemplo "ciclos propios", que no existen).
- ALTA queda **bloqueado esta temporada** en el camino nuevo (`core`): no se puede fijar ni por el panel ni por `cambiar_nivel`.
- **No se toca `sustrato/gates`** (legado de Comercial, solo operador, sellado). Se documenta como límite abierto: ahí un operador todavía puede poner ALTA.
Prueba: tests de texto y de bloqueo de ALTA.

### F2 — Inteligencia sube a BAJA (J1)
- `cubos/inteligencia/manifest.json`: `CERO → BAJA`. Calidad y RRHH siguen en CERO.
- Antes de cambiarlo: listar qué herramientas de Inteligencia son REVERSIBLE y cuáles proponen tarjetas, para decir con exactitud qué gana el cubo.
- Regenerar `docs/MATRIZ_CUBOS.md` con su herramienta; revisar tests que asuman CERO.
Prueba: suite completa verde + test nuevo del manifest.

### F3 — Nivel efectivo por empresa y cubo (base de G1)
- Nuevo `core/autonomia.py` sobre el KnowledgeStore (colección por empresa).
- `nivel_efectivo(cubo)` = el menor entre el manifest y el override guardado.
- Se lee en los 5 puntos actuales. Un solo helper, un solo sitio.
- Cada cambio emite `plataforma.autonomia.cambiada` (ya definido en D00) en la bitácora.
Prueba: unitarios + concurrencia (el store ya es multi-proceso seguro).

### F4 — Gatillos de endurecimiento automático (G1)
En el barrido del panel (junto a `barrer_caducadas`):
- **3 tarjetas DENEGADAS seguidas del mismo cubo** → baja un nivel ese cubo.
- **Sello de la bitácora roto** → baja un nivel todos los cubos de esa empresa.
- Idempotente: el mismo incidente no baja dos veces; tras restaurar, hace falta un incidente nuevo.
- "Te avisa" = evento sellado en la bitácora (visible en el feed del Mundo si ya hay mapeo; si no, se anota como pendiente, no se inventa).
Prueba: tests de cada gatillo, de idempotencia y de no-bajar-de-CERO.

### F5 — Subir nivel: solo el operador (G1)
- `POST /cmd/ajustes/autonomia` siguiendo el patrón de `/cmd/ajustes/tope` (auth, identidad, verificación E1, evento sellado).
- La respuesta incluye el historial del cubo (acierto, ROI de `rendimiento.py`) para "decidir con la ficha delante".
- Rechaza ALTA (bloqueado) y cualquier subida pedida por un agente.
Prueba: auth/CSRF, rechazo de ALTA, rechazo de actor no operador, evento sellado.

### F6 — Ejecuta el humano (I1), solo núcleo
- `ColaSustrato`: nuevos pasos `APROBADA → EN_MANOS → HECHA` con referencia de evidencia, sin alterar las transiciones existentes.
- Solo clases IRREVERSIBLE-EXTERNA. Eventos `plataforma.aprobacion.*` con el mismo formato.
Prueba: FSM completa, claim exactamente-una-vez, revocación, caducidad sin regresiones (`test_b5_aprobaciones.py` íntegro).
**Fuera de esta fase:** pantalla/endpoint de la lista de pasos; depende del formato de dosier y de los estados de apuesta (capas 2 y 3).

### F7 — Cierre
Suite completa, e2e del Mundo (20/20), `docs/LINEA_BASE.md`, `docs/CONTRATO_MUNDO.md` si cambia algo visible, revisión de código y de seguridad del diff, push.

## 4. Lo que NO se implementa ahora (y por qué)

| Elemento | Motivo |
|---|---|
| H1 (lanzador manual del ciclo 0) | Necesita formato de dosier y estados de apuesta: capas 2 y 3, aún sin firmar. |
| MEDIA = "ciclos propios con tope" | No hay planificador ni tope de cómputo. Se deja como reservado, no se simula. |
| Monedero de 50 € / un clic hasta 15 € | Necesita petición de financiación y su flujo (capa Consejo/financiación). |
| Bloqueo de ALTA en `sustrato/gates` | Legado de Comercial, solo operador y sellado. Decisión de Ángel si quiere cerrarlo. |

## 5. Autoevaluación de rigor

**¿Hay suficiente rigor?** Para F0–F5: sí, una vez hecha la lectura anterior, que corrigió tres cosas (sección 2). Para F6: sí en el núcleo. Para H1, MEDIA y monedero: no, y por eso no se implementan.

**¿Se cubre cada punto?** F1→F1, G1→F3/F4/F5 (con una desviación declarada), H1→bloqueado, I1→F6 (núcleo), J1→F2.

**Dudas que quedan (no las resuelvo en silencio):**
1. **Sello roto → baja todos los cubos de la empresa.** Es mi interpretación; la alternativa es solo avisar. Elegí bajar porque una cadena rota afecta a todo lo registrado.
2. **Coste de verificar la cadena completa en cada barrido.** El Mundo ya lo hace en cada foto y crece con los eventos. Se mide antes de engancharlo; si pesa, se verifica con menos frecuencia.
3. **Windows:** todo lo nuevo se prueba aquí en Linux. No está verificado en tu PC.
4. **`sustrato/gates` sigue permitiendo ALTA al operador.** Límite documentado, no resuelto.
5. **Qué gana exactamente Inteligencia en BAJA** depende de qué herramientas REVERSIBLE tiene. Se comprueba en F2 antes de afirmarlo.

**Recursos:** uso las herramientas del repo (lectura, pruebas, git) y, al cierre, las revisiones de código y de seguridad. Los conectores restantes (Vercel, HubSpot, Figma, Gmail, Canva, Asana, etc.) no aportan a esta tarea y usarlos sería decorado, no rigor.

## 6. Resultado (lo que se hizo de verdad, con las desviaciones)

| Fase | Commit | Estado | Desviación respecto al plan |
|---|---|---|---|
| F0 | docs | hecha | — |
| F1 | niveles honestos + ALTA bloqueada en `core` | hecha | — |
| F2 | Inteligencia a BAJA | hecha | Lo que gana hoy son las herramientas REVERSIBLE que ya tiene (`detectar`, `resolver_alerta`, `observar`) y proponer tarjetas. **No existe aún ninguna herramienta para escribir un dosier**: llegará con el formato de dosier (capas 2 y 3). Se cambió además la descripción del manifest, que decía "solo lee". |
| F3 | `core/autonomia.py` | hecha | El override **reemplaza** al defecto (no `min`): el manifest declara un defecto, no un techo, y el operador debe poder subir por encima. |
| F4 | gatillos | hecha | Freno de 30 s por empresa (verificar la cadena cuesta ~32 µs/evento medido, y el pulso corre por cada cliente conectado). El gatillo de gasto no se duplica: lo cubre `core/techos.py`. REVOCADA y CADUCADA no cuentan ni cortan una racha. |
| F5 | `POST /cmd/ajustes/autonomia` | hecha | Subir exige motivo; bajar no. |
| F6 | cola `EN_MANOS`/`HECHA` | **solo núcleo** | Tocó más de lo previsto: registro RUE (`eventos.json`, 3 tipos), frases del feed, `FIRMES` del rendimiento, la racha de G1 y el contador `en_manos` de la foto del mundo. **Sin endpoint ni pantalla**: cambiar `cmd_aprobar` para entregar a humano toca la mecha y depende del formato de dosier. Hoy solo se puede usar desde código. |

### Qué salió mal por el camino (honesto)
- Un test existente (`test_p0_panel_esqueleto`) falló al integrar F4 y **yo lo pasé por alto**: encadené el commit a un `| tail` que ocultaba el código de salida. Causa real: ese test construye su bitácora con otra `fecha_alta` que la del panel, así que el panel veía la cadena rota y el gatillo disparó como debía. Corregido en su commit (`41d495b`) y desde entonces compruebo `exit=$?`.
- Mi afirmación de que MEDIA y ALTA "eran idénticos a BAJA" solo valía para la Colmena (§2).

### Lo que sigue abierto
1. `sustrato/gates` sigue permitiendo ALTA al operador (legado de Comercial, sellado, solo operador).
2. Sello roto ⇒ baja todos los cubos de la empresa. El sello depende de `fecha_alta` del registro de empresas: **si alguien edita esa fecha, el panel verá la cadena rota y G1 endurecerá todo.** Es la misma señal roja que ya enseña el mundo, pero el efecto es mayor; se restaura con `/cmd/ajustes/autonomia`.
3. Todo probado en Linux; **no en Windows**.
4. F6 sin endpoint/pantalla; H1 y MEDIA no implementados (bloqueados por capas 2 y 3).
5. `ENSAYO_SECO` no cuenta como decisión "firme" en el rendimiento (comportamiento previo; no tocado).
