# HANDOFF 3 · Brainstorming estructurado (para que no se pierda)

Fecha: 2026-10-02. Documento 3 de 3 (instrucciones: `HANDOFF_1_…`; datos técnicos: `HANDOFF_2_…`).
**Estamos CONCEPTUALIZANDO** (palabra de Ángel). Nada de aquí es decisión firme salvo lo marcado **[RATIFICADO]**. Etiquetas: HECHO (probado) · DICHO (lo afirma una fuente/otra IA) · IDEA · PREGUNTA.

---

## 1. Concepto y principios
- Kaizen = empresa sintética «cultivada como un jardín» para **encontrar y probar apuestas** que ganen dinero, con agentes, aprobaciones y registro sellado. Dinero real solo cuando haga falta y lo apruebe Ángel. **[RATIFICADO]** monedero máximo 50 €; apuesta = 15 € y 3 meses; lo externo/irreversible lo ejecuta Ángel.
- Valores de Ángel: la verdad ante todo; «si hay elección no hay libertad»; excelencia como mínimo.
- Edificio: planta 1 comercial (B2B), planta 2 fondo de inversión digital (**aparcada**), planta 3 Web3 y nichos Web3. Regla: **no adoptar nada que no encaje en el plan**.

## 2. El orden (idea de Ángel, ratificada en la conversación)
**capacidades → nichos → huecos → ejecutar (→ medir)**
1. *Capacidades:* qué puede hacer Claude **y las otras IAs** (y herramientas alquiladas) hoy. La pregunta correcta según Ángel: «¿qué puede hacer Claude?», no «qué nicho hay».
2. *Nichos:* solo los que esas capacidades pueden atacar.
3. *Huecos:* lo que falta para ejecutar cada nicho (la lista de lo que hay que construir o alquilar).
4. *Ejecutar* con presupuesto y plazo; *medir* y podar.
- Por qué: buscar nichos sin saber qué se puede hacer produce ideas que no se pueden ejecutar. El motor de nichos ya existe (HECHO); el catálogo de capacidades **no** (IDEA, pendiente de «adelante»).

## 3. Mejoras propuestas al concepto
- Catálogo de capacidades vivo: cada fila con *qué hace · cómo se prueba · coste · estado · fecha de última prueba · quién lo probó*. Ningún «funciona» sin prueba fechada.
- Cada apuesta se registra con su **capacidad habilitante**; si la capacidad cae, la apuesta se revisa.
- Informes de nichos **entrantes** (Ángel o una IA los aportan) además de la búsqueda automática; botón «Añadir nicho» (IDEA, en la cola de decisiones).
- Ángel dudó si Kaizen debe empezar buscando nichos (muy complejo) o **recibiendo informes**: propuesta mixta, **buscar nichos con Claude juntos** mientras Kaizen hace lo ya preparado.

## 4. Qué conservar, congelar y descartar (sin pudor)
| Decisión | Qué |
|---|---|
| **Conservar (diferencial)** | Registro sellado, ventanilla de aprobaciones, autonomía por niveles con bloqueo de ALTA, máquina de estados de apuestas, dosier con evidencia etiquetada, el Mundo como vista honesta |
| **Congelar** | Planta 2 (fondo digital); más estética del Mundo; chat integrado en el Mundo |
| **Descartar si no aporta** | Reconstruir lo que ya hacen plataformas (equipos de agentes); reescribir sobre LangGraph/CrewAI; Langfuse (hoy) |
| **Por decidir** | n8n para el «pegamento» (solo con ≥3 flujos); catálogo de capacidades como módulo del repo |

## 5. Comprar o construir con 50 €
- Planes de pago citados (Manus Pro ~20 $/mes, n8n nube ~20 €/mes, Lindy ~50 $/mes, Apollo/Hunter ~49 $/mes, Clay ~167 $/mes) **no caben** en una apuesta sostenida de 15 € (DICHO, precios de terceros).
- Cabe: **planes gratuitos como sondas**, autoalojar (n8n en el PC), o **un mes** de suscripción pequeña. Regla: pagar solo si ahorra tiempo del operador, se probó en gratis, se cancela cuando se quiera y cabe en la apuesta.
- Octask: se usó como sonda (cuenta gratuita, 500 créditos desechables). Lecciones: **(a)** el vídeo costó 40 créditos/s y un intento de 10 s no cabía; **(b)** el contador de la cabecera se desfasó y un agente afirmó «saldo 500» siendo falso (real 357,758); **(c)** la prueba no produjo vídeo; **(d)** los activos se borran al acabar la prueba; **(e)** términos sin cláusula de marca de agua ni uso comercial de las salidas. Moraleja: **medir créditos en origen y desconfiar de lo que dice el agente**.
- Pregunta de Ángel sin resolver: ¿había un nombre/categoría para lo que construimos? Propuesta mía (etiqueta mía, no del mercado): «estudio de apuestas».

## 6. Web3 (uso personal de Ángel, solo orientativo)
- Postura: «nada de esto es ley». Web3 y nichos Web3 son la **planta 3**; no se mezcla con el fondo (planta 2, aparcada).
- Idea de Ángel: bots/agentes que hagan cosas on-chain y «farmeen» en una wallet; pérdida máxima = lo invertido. Reparos honestos: **el coste son comisiones y tiempo, no solo la inversión**; el riesgo real son estafas/contratos maliciosos y claves; **ejecuta Ángel** (C1) cualquier firma/envío.
- Notas fiscales (España, de resúmenes de terceros, **sin consultar a un gestor**): airdrop = ganancia patrimonial al recibirlo; staking = rendimiento de capital mobiliario; permuta cripto-cripto tributa. «Si no se vende no hay impuestos» **no es una conclusión que podamos dar por válida**. PREGUNTA: consultar a un gestor antes de operar con dinero real.
- Datos: DefiLlama (API pública, solo lectura) como fuente; Snapshot/Dework/Gitcoin/Layer3 **sin investigar**. Pendiente: informe Web3 para Ángel (decisión en cola).

## 7. Embudo de vídeo (capacidad candidata)
- Idea: 1–2 vídeos al día con IA gratuita como canal de contenido. Candidatas (DICHO; ver `docs/referencias/VIDEO_IA_GRATIS_CANDIDATAS_2026-10-02.md`): **Google Flow** (50 créditos Veo 3.1/día, SynthID; la más prometedora), Google Vids (~6/mes), Agnes/Pavo Flash (cupo diario, «sin límites» no es exacto), Vibes (Meta prevé suscripción), Muse AI y Flick (sin comprobar), VideoProc («4K» que era 2560×1440).
- Riesgos: quitar marcas de agua puede incumplir condiciones; las plataformas piden declarar contenido sintético; «ilimitado» = cupo diario.
- Pruebas pendientes: el mismo guion de 10–15 s en Flow, Agnes/Pavo y Vibes (tiempo, créditos, resolución real, marca de agua, formato) y varios días seguidos.
- Fuente de ideas: canal de Alejavi Rivera (vídeos `IWA9LCvNW8g`, `mRn9flyjzVk`). Aviso: YouTube mostraba sin subtítulos → **el Investigador necesita plan B** (transcribir audio en local o reintentar).

## 8. Vigilante de canales (idea)
Un agente que vigile canales elegidos por Ángel, saque lo nuevo y lo convierta en notas/ideas para el catálogo. Depende del **Investigador YouTube (Astra)**, hoy con 16 caminos de «falso ok» y la Fase 1A en marcha. Hasta que acabe la 1B no se le encarga trabajo nuevo. Regla: un vídeo solo cuenta si hay fichero válido en disco.

## 9. Skills y orden de construcción (IDEA, sin «adelante»)
Orden propuesto: **prompt-forge → experto-cowork-operativo → skill-creator**. Cada skill: caso de uso concreto, prueba de que funciona, y no sustituye a una aprobación humana.

## 10. Investigación multi-IA
- WebLLM = «el ordenador de la empresa» (analogía de Ángel): puerta de automatización de navegador a unas 16 IAs; Claude y ChatGPT **excluidos** por decisión suya; la puerta externa por API apagada tras reiniciar **a propósito**. Ángel garantiza que las 16 funcionan sin fallo y quiere un **botón para descargar todas las respuestas**.
- Piloto propuesto: la misma pregunta de investigación profunda a varias IAs de frontera, y **cotejar** (acuerdos, contradicciones, fuentes). Cautelas: las IAs inventan fuentes; un consenso no es verdad; cada afirmación clave se etiqueta VERIFICADA/RECORDADA/SUPUESTO igual que el dosier.
- Lección de la sesión: una IA «me había engañado» (Ángel) → **cualquier informe de agente es DICHO hasta que se vea la prueba**.

## 11. Contexto legal que afecta a la planta 1
Correo en frío B2B en España: RGPD + LSSI art. 21; guía de un vendedor de herramientas (interés comercial) deja dudoso el primer correo sin relación previa. **Consultar a gestor/abogado antes del primer envío real.** El pipeline ya limita a 2 mensajes, respeta exclusiones y exige bloques legales.

## 12. Preguntas abiertas
1. ¿Se escribe el catálogo de capacidades? (necesita «adelante»).
2. ¿`buscar_nichos` pide SÍ por autonomía firmada, o lo interno es libre?
3. ¿Se crea una empresa limpia para la primera ronda real?
4. ¿Se renombran los 17 ficheros del PC con nombres reales (control de nombres)?
5. ¿Se borra `vm_bundles` (19,5 GB) y cachés para recuperar disco?
6. ¿Informe Web3 para Ángel? ¿Con qué alcance?
7. ¿Se añade «Añadir nicho» al Mundo?
8. ¿Qué lentes se mantienen? (3 nuevas adoptadas **sin permiso explícito**; Ángel decide si se quedan.)
9. ¿Cuándo se consulta al gestor/abogado?
10. ¿Qué IA de las 16 se usa para el piloto multi-IA y con qué pregunta?

## 13. Qué NO está probado (resumen honesto)
Motor de nichos con **modelos y búsqueda reales**; LM Studio como proveedor real; WebLLM tras el arreglo; todas las cifras de precios y límites de terceros; calidad de cualquier vídeo gratuito; la capacidad real de Octask; los 16 caminos de Astra más allá de la 1A. Hasta que algo de esto se pruebe, se trata como **DICHO**.
