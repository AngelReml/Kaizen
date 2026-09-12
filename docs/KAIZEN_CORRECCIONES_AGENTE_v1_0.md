# KAIZEN — CORRECCIONES DEL AGENTE CONSTRUCTOR v1.0

Naturaleza: documento vinculante. Se antepone a cualquier plan propio del agente. Si contradice al canonico (KAIZEN_ARQUITECTURA_CANONICA), gana el canonico; si contradice una preferencia del agente, gana este documento. Fecha: 2026-07-03 Autoridad: Ivan Carbonell. Solo el puede modificar o derogar reglas de este fichero.

## §0. AXIOMA OPERATIVO

Hecho = observado funcionando. Nunca un resumen.
Ninguna afirmacion de "completado", "en verde" o "funciona" es valida sin evidencia ejecutada en la misma sesion: salida literal de comando, hash, o captura de estado. Si la evidencia es heredada de una sesion o auditoria anterior, se reproduce antes de afirmarla. Esto ya se cumplio en el Bloque 0 — se mantiene como ley permanente, no como gesto puntual.

## §1. ERRORES PASADOS — CORRECCION OBLIGATORIA

### E1. Desfase de sincronizacion del montaje (CRITICO, recurrente)
Observado: dos veces en la ultima sesion ("retraso de sincronizacion del montaje", "reescribo cli.py desde el sandbox directamente"). Mismo patron que corrompio DECISIONES.md en Shinobibot (truncamiento silencioso en el mount de Linux). Regla permanente:
1. Tras CADA escritura en el filesystem montado, verificar integridad antes de continuar: sha256sum del fichero escrito comparado con el contenido intencionado (o al minimo, wc -l + tail -n 3).
2. Si hay desfase, no "reintentar y seguir": registrar el incidente en el informe del bloque con ruta, timestamp y metodo de resolucion.
3. Ficheros criticos (contratos, actas, cadenas de hash, .env, requirements) NUNCA se escriben una sola vez sin verificacion. La corrupcion silenciosa de un acta invalida toda la cadena.

### E2. Hosting tratado como detalle futuro
Observado: el plan S5 propone tunel ngrok desde el PC de Windows de Ivan, con "cerrado ahora" si el PC duerme, y la mudanza a mini-PC como roadmap posterior. Correccion: un producto real no tiene horario de PC domestico. El destino de despliegue (VPS Contabo existente o mini-PC en el obrador) se decide y ejecuta ANTES de entregar acceso a terceros. Reordenar el plan: la S5 no es "tunel + PIN", es "despliegue en infraestructura persistente + PIN". ngrok queda solo como puente de pruebas internas de Ivan. Prohibido: presentar a Alejandro (o a cualquier cliente) un acceso que dependa de que el PC de Ivan este encendido.

### E3. Entregabilidad de email ausente del plan
Observado: la S3 planifica "SMTP con tope diario" sin mencion a SPF/DKIM/DMARC, calentamiento de dominio ni reputacion IP. Correccion: la S3 incluye obligatoriamente, antes del primer envio a terceros:
1. Verificacion de registros SPF, DKIM y DMARC del dominio emisor (comando dig documentado en el informe).
2. Volumen inicial <= 10 emails/dia con rampa documentada.
3. Test de colocacion en bandeja (envio a cuentas propias en Gmail/Outlook, verificar carpeta de llegada) antes de tocar los 466 leads.
4. Si el dominio es frio o no autenticado: DETENER y reportar. Un SI de Alejandro que acaba en spam es un producto roto con tests en verde.

### E4. Plazo regulatorio no cruzado con el calendario del plan
Observado: el AI Act Art. 50 entra en vigor el 2026-08-02 — cuatro semanas antes del 30 de agosto. El candado de variantes existe, pero el plan de 8 semanas no marca el 2 de agosto como hito duro. Correccion: todo email generado por IA que salga en produccion a partir del 2026-08-02 debe cumplir el regimen de transparencia. Insertar en el plan un hito bloqueante "AIACT-GATE (2026-08-02)": desde esa fecha, el preflight rechaza cualquier salida sin variante aprobada aplicada. Recordar a Ivan en cada informe que la aprobacion de variantes es suya y sigue pendiente — sin insistencia, una linea.

### E5. Dependencia rota tolerada
Observado: python-multipart ausente rompe 7 tests de webhooks en instalacion limpia; se reporto como recomendacion opcional. Correccion: las dependencias que rompen la suite en instalacion limpia no son recomendaciones. Anadir a requirements.txt en el siguiente commit (una linea, cero riesgo) salvo prohibicion expresa. Una suite que solo pasa en el entorno del agente no esta en verde.

### E6. Test preexistente con dependencia de orden
Observado: un test del panel FastAPI falla en ejecucion aislada; se clasifico y se siguio. Correccion: clasificar no basta. Registrarlo en un fichero DEUDA_TECNICA.md con: test, causa, si bloquea o no, y coste estimado de arreglo. La deuda invisible es la que mata en la S7.

## §2. REGLAS PERMANENTES (errores futuros que se previenen hoy)

### R1. Git y confidencialidad
Kaizen NO va a GitHub ni a ningun repo remoto, ni privado. Commits locales solamente. Prohibido configurar remotes, prohibido sugerir push. Los 466 leads, el argumentario y las biblias de marca son datos de negocio de terceros: no salen de la maquina, no aparecen literales en informes (referencias por conteo o ID, no listados completos).

### R2. Presupuesto
El tope de coste es por sesion y lo fija Ivan explicitamente cada vez. Sin cifra explicita en la sesion actual, el tope es 0 $ (solo trabajo local). El hard stop va DELANTE de cada llamada, nunca como contabilidad posterior. Reportar gasto acumulado en cada informe con dos decimales.

### R3. Protocolo de parada
Se mantiene: si el contrato exige un dato que solo Ivan puede dar (modelo, variantes, credenciales, decision de negocio), DETENER ese frente y avanzar los frentes no bloqueados. Nunca inventar el dato, nunca elegir por el, nunca presentar menus de opciones cuando existe un unico camino correcto — si el camino es unico, ejecutarlo y declararlo.

### R4. Contacto con terceros
Ningun email, llamada, SMS o webhook llega a un tercero real sin orden explicita de Ivan en la sesion. Los tests de envio usan exclusivamente cuentas propias de Ivan. Esto incluye los 466 leads: son terceros reales, no fixtures.

### R5. Datos reales en demos
Las demos pueden usar leads reales en LECTURA (como se hizo). Prohibido que una demo escriba, contacte o modifique el estado de un lead real. Toda tarjeta de demostracion lleva el marcador [DEMO] en el texto visible hasta que la S2 genere contenido real aprobado.

### R6. Linea base de la suite
La linea base solo puede subir. Antes de cada commit: suite completa, comparar contra la ultima cifra registrada (ahora: 680 passed / 7 skipped). Cualquier bajada = bloqueo, no se committea. Registrar la cifra nueva en el informe del bloque.

### R7. Informes
Cada bloque cierra con informe en C:\Users\angel\Desktop\KAIZEN\ que contiene: que se observo funcionando (con salida literal), que NO esta (sin humo, formato "estructura X/10, musculo Y/10" o equivalente), gasto acumulado, deuda tecnica nueva, y las acciones que solo Ivan puede hacer — maximo 5 lineas para estas ultimas.

### R8. El destinatario final es Alejandro
Criterio de diseno para toda pieza visible: un panadero de 60 anos en la barra del obrador, con harina en las manos, 90 segundos. Si una pantalla necesita explicacion, esta mal. Si un flujo necesita mas de un toque por decision, esta mal. La Mesa del Jefe es el patron: saludo, resumen de ayer, tarjetas SI/NO. Nada mas entra en su pantalla sin orden expresa.

### R9. Verificacion por Ivan antes de "listo"
Ningun hito se declara "listo para Alejandro" hasta que Ivan lo haya ejecutado en SU maquina y lo confirme en sesion. El agente prepara los .cmd y las instrucciones de un paso; la validacion es humana y presencial. La S8 (congelado + ensayo) es innegociable: cero features nuevas la ultima semana.

## §3. ORDEN DE PRIORIDAD ANTE CONFLICTO

1. Seguridad de datos de terceros (R1, R4, R5)
2. Contrato canonico y protocolo de parada (R3)
3. Presupuesto (R2)
4. Integridad de escritura y cadenas de hash (E1)
5. Linea base de tests (R6)
6. Calendario (AIACT-GATE > 30 de agosto > todo lo demas)

Ante duda no resuelta por este orden: detener el frente afectado, reportar, continuar los demas.

## §4. CHECKLIST DE APERTURA DE SESION

Al iniciar cada sesion, antes de construir:
- [ ] Leer este documento completo.
- [ ] Verificar integridad de los ficheros criticos escritos en la sesion anterior (hash o tail).
- [ ] Ejecutar la suite y confirmar linea base.
- [ ] Confirmar tope de presupuesto de la sesion (si no hay cifra: 0 $).
- [ ] Listar bloqueos pendientes de Ivan en una linea cada uno.

FIN v1.0
