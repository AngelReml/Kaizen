# Mapa de alternativas — 2026-10-02 (primera pasada)

Qué existe ya en el mercado que se solapa con Kaizen, qué cuesta y qué haría yo con ello.
**Fuentes:** búsquedas web de esta fecha (resúmenes de terceros). **Los precios cambian y no están verificados en las webs oficiales.** Los veredictos son opinión de Claude, no hechos.
Presupuesto de referencia: 50 € en total; regla vigente de 15 € y 3 meses por apuesta.

## Resumen
| Categoría | Ejemplos | Solapa con Kaizen | Coste (según fuentes) | Veredicto |
|---|---|---|---|---|
| Plataformas de «equipo de agentes» listas para usar | Octask, Manus, Lindy, Relevance AI | Agentes que ejecutan tareas y entregan resultados | Manus: [créditos diarios gratis, Pro desde 20 $/mes](https://www.lindy.ai/blog/manus-ai-pricing). Relevance AI: [plan gratuito con 200 acciones/mes](https://www.11x.ai/guides/relevance-ai-pricing). Lindy: [49,99 a 199,99 $/mes, 7 días de prueba, sin plan gratis](https://automationatlas.io/answers/lindy-pricing-explained-2026/). Octask: **no encontré información independiente** | **Alquilar y probar** con sus planes gratis como sondas de capacidades. No reconstruir lo que ya hacen |
| Automatización de flujos | n8n, Zapier, Make | Programar tareas, vigilar fuentes, conectar servicios | n8n: [edición comunitaria gratis y autoalojada, sin límite de ejecuciones, pero pones tú el servidor y el tiempo; la nube desde 20 €/mes](https://toolradar.com/blog/n8n-pricing-2026). Zapier: [100 tareas/mes gratis; agentes 400 actividades/mes](https://www.activepieces.com/blog/is-zapier-free) | **Evaluar para el «pegamento»** si hay 3 o más flujos. Con uno solo, un script y el Programador de tareas de Windows es más simple |
| Marcos de código para agentes | LangGraph, CrewAI | La Colmena (chat de directores) y las tarjetas de aprobación | [LangGraph: estado, reintentos y pasos con aprobación humana, versión 1.0 desde oct. 2025; CrewAI: equipos por roles, prototipo rápido; AutoGen en mantenimiento](https://aiagentrank.io/blog/langgraph-vs-crewai-vs-autogen-2026) | **Ignorar por ahora.** Reescribir Kaizen sobre ellos es mucho cambio sin ganancia inmediata. Útiles como fuente de ideas |
| Observabilidad y gobierno de agentes | Langfuse y similares | Registro sellado, aprobaciones, límites | Langfuse es [código abierto (MIT) y se puede autoalojar](https://aiagentrank.io/blog/ai-agent-observability-2026). Según las fuentes, la observabilidad [no sustituye al enrutado de aprobaciones ni a límites de alcance](https://prefactor.tech/compare/vs-langfuse) | **Mantener lo propio.** El registro sellado y la ventanilla de aprobaciones es lo más diferencial de Kaizen. Langfuse sería complementario, no necesario hoy |
| Generadores de vídeo, voz e imagen | Kling, PixVerse, Wan, Meta Vibes, Qwen | La capacidad que nos falta | Ver `INFORME_ESTADO_2026-10-02.md` §6 | **Alquilar en planes gratuitos.** Probar calidad y condiciones de uso comercial |

## Lo que no he investigado todavía
- Herramientas de descubrimiento de nichos y de demanda (tendencias, foros, buscadores de ideas).
- Herramientas de ventas salientes y enriquecimiento de leads (para la planta comercial).
- Fuentes de datos Web3 (para tu actividad personal).
- Si existe una categoría con nombre propio para lo que construimos (en el chat propuse «estudio de apuestas» como etiqueta mía).

## Qué cabe en 50 €
- Ninguno de los planes de pago citados cabe dentro de una apuesta de 15 € de forma sostenida: Manus Pro (20 $/mes), n8n en la nube (20 €/mes) y Lindy (50 $/mes) la superan.
- Con 50 € solo caben **planes gratuitos, autoalojar (n8n en tu PC) o una suscripción pequeña durante un solo mes de prueba**.
- Regla: pagar solo si ahorra tiempo del operador, se probó antes en gratis, se cancela cuando quieras y cabe en la apuesta.

## Limitaciones
- Octask: la búsqueda no devolvió ninguna fuente independiente. Lo único que sabemos viene del vídeo promocional y de la propia web. Empresa y condiciones **sin verificar**.
- Los precios proceden de comparativas de terceros, algunas con interés comercial (por ejemplo, un blog de un competidor).

---

# Segunda pasada (misma fecha): demanda, ventas salientes, ley y datos Web3
Mismas reservas: resúmenes de terceros, varios con interés comercial, sin verificar en origen.

## Validar demanda de un nicho
- Método que repiten las fuentes: [confirmar que la gente busca, habla y paga por una solución; la demanda se valida cuando coinciden interés, intención y dinero](https://growwithsakib.com/validate-market-demand-niche/). Encaja con los campos `senal` y `senal_real` del dosier.
- Gratis: Google Trends, el autocompletado y «la gente también pregunta» de Google, AnswerThePublic y foros donde la gente pide recomendaciones. De pago: Ahrefs, Semrush ([resumen](https://aicofounder.com/blog/best-market-research-tools-in-2026)).
- **Veredicto:** con las herramientas gratuitas basta para las primeras apuestas. Ninguna sustituye hablar con compradores reales.

## Ventas salientes y enriquecimiento de leads
- Planes gratuitos según [esta comparativa](https://dupple.com/learn/best-ai-for-sales-prospecting): Clay 100 créditos/mes, Hunter 25 búsquedas y 50 verificaciones/mes, Apollo 50 créditos/mes.
- De pago: Apollo Básico 49 $/usuario/mes, Hunter Starter 49 $/mes, Clay Launch 167 $/mes, Instantly desde 47 $/mes.
- **Veredicto:** los de pago no caben en 50 €. Kaizen ya enriquece leads internamente; los planes gratis sirven como contraste o verificación puntual.

## Ley: correo en frío B2B en España (¡importante para la planta comercial!)
- Según [esta guía](https://overloop.com/blog/es/b2b-cold-email-espana-rgpd-aepd), hay dos normas: el RGPD (¿puedo tratar este dato?; el interés legítimo exige análisis documentado) y la LSSI art. 21 (¿puedo enviar esta comunicación?; prohíbe comunicaciones comerciales electrónicas no solicitadas o no autorizadas, con excepción para clientes previos y productos similares). La guía cita multas de la LSSI de hasta 150.000 € por infracción grave.
- **Aviso de lectura crítica:** esa guía es de una empresa que vende herramientas de correo en frío, y su propio resumen («legal con condiciones: consentimiento previo o relación previa») deja dudoso que un primer correo sin relación previa encaje en la excepción. **No lo doy por resuelto.**
- **Acción recomendada:** consultar a un gestor o abogado ANTES del primer envío real. Mientras tanto, el pipeline ya limita a 2 mensajes, respeta exclusiones y exige bloques legales. Otros canales (teléfono, formularios, presencial) podrían quedar fuera del art. 21, **sin verificar**.

## Datos para Web3 (solo lectura)
- [DefiLlama](https://github.com/api-evangelist/defillama): API pública gratuita, sin autenticación en la mayoría de endpoints (TVL, precios, volúmenes, comisiones, stablecoins, puentes) y sección de rendimientos (APY). Hay API Pro con más límite.
- **Hueco:** la búsqueda no devolvió nada utilizable sobre Snapshot, Dework, Gitcoin ni Layer3. Quedan **por investigar**.
