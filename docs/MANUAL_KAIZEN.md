# MANUAL DE KAIZEN — cómo funciona cada cosa, en sencillo

**Para:** angel (operador) · **Fecha:** 2026-07-03 · **Estado del sistema:** 669 pruebas automáticas en verde, 7 omitidas (necesitan servicios externos reales).

Kaizen es tu empresa sintética: departamentos de IA que trabajan para tus clientes (hoy: Repostería Laboratorio) bajo reglas que tú controlas. Este manual explica qué hay, cómo se mira y qué hace cada pieza. Todos los comandos se ejecutan desde la carpeta KAIZEN con tu Python de siempre.

---

## 1. El plano general (60 segundos)

Piensa en una oficina:

- **Diez departamentos** (los "[[CUBOS|cubos]]"): Comercial es el que está de verdad en marcha; los otros nueve están constituidos, con contrato y salud, listos para crecer.
- **Un cuaderno de a bordo precintado** (el bus): todo lo que pasa queda escrito, y cada línea lleva un sello matemático encadenado al anterior. Tocar una línea rompe la cadena y se detecta.
- **Un archivador de clientes** (el registro): los 466 posibles clientes de Laboratorio, con un pasillo de estados fijo: FRÍO → CONTACTADO → INTERESADO → COMPROMETIDO → CLIENTE. Nadie salta pasos.
- **Un portero con [[COMITE_3X3|comité]]** (gates + comité): las acciones serias hacia fuera (un email real, publicar algo) exigen tu permiso de nivel ALTO y 9 de 9 votos de tres revisores de IA (marca, legal, riesgo). Si algo falla por dentro, la respuesta es NO.
- **Un freno de gasto** (coste): límite diario en euros; al 80% avisa, al 100% corta en seco antes de gastar.
- **Un panel** (director) y **un vigilante diario** (forense) para mirar sin tocar.
- **Tu candado**: aflojar permisos o subir el límite de gasto solo puedes tú, con motivo escrito, y queda sellado con hash.

## 2. Los comandos del día a día

| Quiero... | Comando |
|---|---|
| Ver el estado general (pipeline, compromisos, gasto, verificaciones) | `python kaizen.py director` |
| Lo mismo pero en una página HTML para enseñar | `python kaizen.py director --html` |
| Ver la salud de los 10 departamentos | `python kaizen.py cubos estado` |
| Pasar la revisión diaria (vencidos + sellos + gasto) | `python kaizen.py forense diario` |
| Ver qué argumentos de venta funcionan mejor | `python kaizen.py p8 ranking` |
| Comprobar que nadie ha tocado el cuaderno | `python kaizen.py bus verificar-cadena` y `python kaizen.py operador verificar-cadenas` |
| Mover un lead de estado a mano | `python kaizen.py registro transicionar <id> <ESTADO> --motivo "..."` |
| Subir/bajar permisos de un departamento | `python kaizen.py operador set-autonomia <cubo> <CERO\|BAJA\|MEDIA\|ALTA> --motivo "..."` |
| Cambiar el límite diario de gasto | `python kaizen.py operador set-limite-coste <euros> --motivo "..."` |

**Primera vez en tu PC** (una sola vez): `pip install -r requirements.txt` y después `python kaizen.py registro migrar` — crea `data/kaizen.db` con tus [[REGISTRO_P9_LEADS|466 leads]] reales (hace copia de seguridad antes y jamás toca knowledge.json).

## 3. Cada pieza, explicada

**El cuaderno (bus).** Cada suceso (un lead cambia de estado, se crea un compromiso, se registra un pedido) se escribe con fecha, autor y contenido, más un sello: la huella del suceso anterior mezclada con el actual. Por eso la cadena "canta" si alguien borra o edita. Hay tres cadenas independientes: sucesos, verificaciones del portero y decisiones tuyas.

**El archivador (registro).** La verdad comercial vive en una base de datos (`data/kaizen.db`), no en papelitos. Tablas: leads, transiciones, interacciones, compromisos y pedidos. El pasillo de estados es cerrado: por ejemplo, de FRÍO solo se puede ir a CONTACTADO, NO_LLAMAR o DESCARTADO. "NO_LLAMAR" es terminal: solo tú puedes sacar a alguien de ahí, con `--operador` y motivo.

**El freno (coste).** Antes de cada llamada a una IA de pago se pregunta al contador: ¿cabe en el límite del día? Si no cabe, no se llama — no es un aviso, es un corte. Hoy el límite está en 14,72 € (tus 16 dólares). También suma lo que gasta el contador antiguo del sistema, para que no haya dos bolsillos.

**El aprendiz (P8).** Cada vez que se usa un argumento de venta en una interacción, se apunta si el cliente avanzó, quedó neutro o rechazó. Con 10 casos o más por argumento y tipo de cliente, sale un ranking (`p8 ranking`). Con menos de 10, dice "SIN DATOS SUFICIENTES" — no opina de oídas. Puede reordenar los argumentos en los briefings, pero no puede borrar ni editar ninguno: eso es tuyo.

**El portero y el comité (gates + comité).** Cualquier acción marcada como irreversible (enviar un email real, publicar contenido, comprometerse ante un cliente) pasa dos controles: el nivel de permiso del departamento (empiezan en BAJA; lo irreversible exige ALTA, que solo tú concedes) y un comité de 3 revisores de IA que vota 3 rondas — 9 votos. Solo 9 síes = adelante. 7-8 síes = se para y te avisa. 6 o menos = no. Cada veredicto queda sellado en la tabla de verificaciones. Y hay una acción que directamente no existe: prometer precios o condiciones a un cliente. Eso es de humanos.

**Tu candado (operador).** Endurecer (bajar permisos, bajar límite) lo puede hacer hasta el propio sistema. Aflojar, solo tú, por comando, con motivo, y queda grabado con hash. Si un programa lo intenta, recibe un error.

**El panel (director).** Solo lectura. Enseña pipeline, compromisos por fecha, las últimas verificaciones, el gasto del día y el top de argumentos. Su regla de oro: si un dato no existe, pone "SIN DATOS" — nunca un cero inventado. El `--html` genera una página sobria (colores de tu marca) sin javascript ni servidor: un fichero que puedes abrir o enseñar.

**El vigilante (forense).** Una pasada diaria: ¿hay compromisos vencidos sin cerrar? (avisa con un suceso), ¿están intactas las tres cadenas?, ¿el gasto está dentro del límite? Deja su acta sellada. Prográmalo en el Programador de tareas de Windows para que corra solo cada mañana.

## 4. Los diez departamentos hoy (sin humo)

| Departamento | Estado real hoy |
|---|---|
| **comercial** | El motor. 466 leads reales, pipeline, compromisos, P8, comité probado con votos reales. Es lo que se vende y se enseña. |
| **brand** | Guardián de marca operativo: revisa borradores (reglas duras + IA) antes de que salga nada. Ya funciona multi-empresa. |
| **marketing** | Constituido; genera borradores. Publicar de verdad está declarado irreversible: exige tu ALTA + comité. |
| **customer_success** | Constituido; escucha pedidos del comercial para el postventa. |
| **inteligencia** | Constituido; solo lee y publica análisis (nivel CERO: no puede tocar nada). |
| **finanzas** | Constituido; registra y reporta. **Jamás paga**: mover dinero no existe como acción. |
| **legal** | Constituido; dictamina (nivel CERO). |
| **ops** | Constituido; tareas y compromisos internos. |
| **qa** | Constituido; valida salidas de otros (nivel CERO). |
| **rrhh** | Constituido y **pospuesto por decisión tuya** (lo dice su propia salud). |

"Constituido" significa: contrato firmado (manifest validado), arranca solo sin depender de nadie, salud consultable, permisos por defecto prudentes, y su código funcional existente intacto. El trabajo profundo de cada uno (sus especialistas) crece a partir de aquí sin tocar el [[SUSTRATO|sustrato]].

## 5. El trabajador de baja (agente de voz)

Por tu orden, nada de esta fase toca la voz. Queda aparcado y documentado para cuando vuelva: (1) redesplegar el agente v2 en ElevenLabs — el desplegado sigue siendo el v1, que no se identifica como IA: **no hacer llamadas reales hasta ese redeploy**; (2) los webhooks de voz atribuyen todo a Laboratorio; (3) prefijo 400 antes de octubre 2026; (4) rellenar `robinson_ok` de cada lead antes de llamar (el sistema lo exige y bloquea sin él). Las 20 frases de presentación ya están aprobadas y cargadas: esa parte está lista.

## 6. Dar de alta un cliente nuevo

Hoy la vía sana es **una instalación por cliente**: copia la carpeta KAIZEN, vacía `state/knowledge.json` y `data/`, crea `empresas/<cliente>/` con su `perfil.json`, `argumentario.json` y `brand/` (mira `empresas/laboratorio/` como plantilla), y migra sus leads. Así cada cliente tiene su caja, sus sellos y su gasto, sin mezclarse. El multi-cliente en una sola instalación existe a medias y no está listo para producción: no lo uses para dos clientes de pago.

## 7. Rutina recomendada

Diaria (automática si la programas): `forense diario` y `bus metrica-diaria`. Cuando trabajes: `director` al empezar, `cubos estado` si algo huele raro. Semanal: `p8 ranking` para ver qué argumento gana, y una copia de la carpeta a un disco externo (tu git es solo local: ese disco es tu única red de seguridad).

## 8. Si algo va mal

"CADENA CORRUPTA: primer id corrupto = N" → alguien o algo tocó esa fila; los datos posteriores al sello roto no son de fiar hasta revisarlos. "DEGRADADO" en salud → casi siempre gasto ≥80% del límite; míralo en `director`. "LimiteCosteSuperado" → el freno actuó: o esperas a mañana o subes el límite tú con motivo. Un lead en NO_LLAMAR → se respeta; solo tú lo reactivas. Y si la suite de pruebas (`python -m pytest -q`) no da "669 passed", algo se ha tocado: los informes `INFORME_*.md` de la raíz cuentan la historia completa de cada pieza.

## 9. El [[CENTRO_DE_MANDO|Centro de Mando]] (nuevo, 2026-07-03)

Tu mesa de control multi-empresa. Se abre con **doble clic en `CENTRO DE MANDO.cmd`** (en la carpeta KAIZEN): arranca el motor en una ventana minimizada y te abre el navegador en `http://127.0.0.1:8600`. Solo funciona en tu PC; no está expuesto a internet. Para cerrarlo: cierra la ventana minimizada «Kaizen Centro».

Arriba, el **desplegable de empresa**. Cada empresa es una instalación de Kaizen registrada en `centro_instancias.json` (hoy: laboratorio; cuando des de alta a un cliente, añades una línea con su nombre y su carpeta). Al elegir empresa ves: su pipeline y su gasto del día, la tabla de los 10 departamentos — contratado sí/no, nivel de autonomía, acciones irreversibles, notas — y sus últimas verificaciones.

Y puedes tocar, con dos verdades importantes:

1. **Las acciones van por el CLI de cada instancia**, no por un atajo: cuando subes la autonomía de un departamento desde el Centro, por debajo se ejecuta `kaizen operador set-autonomia ... --motivo "..."` EN esa instancia — así el candado del operador y la cadena de hash de ESA empresa siguen mandando. El motivo es obligatorio; sin motivo, el Centro ni lo intenta.
2. **"Contratado" es un marcador comercial (v1)**: te sirve para ver y organizar qué ha comprado cada cliente. No abre permisos por sí solo — lo que un departamento puede hacer lo deciden siempre su autonomía y los gates. (Hacer que "no contratado" bloquee además en los gates es la mejora natural de la v2.)

Botones rápidos por empresa: **Forense diario** (la revisión del día, con su acta sellada) y **Regenerar panel cliente** (el HTML sobrio que le enseñas a Pedro o Alejandro). La caja negra de abajo muestra la salida literal de cada acción — lo que el sistema dijo de verdad, sin adornos.


## 10. Sin comandos: los tres doble-clic

Olvida la ventana negra. En la carpeta KAIZEN tienes tres ficheros que se usan con doble clic:

| Fichero | Qué hace | Cuándo |
|---|---|---|
| **PRIMERA VEZ.cmd** | Instala lo necesario, crea la base de datos con tus 466 leads y genera el primer panel | Una sola vez |
| **CENTRO DE MANDO.cmd** | Abre tu mesa de control en el navegador | Cada vez que quieras gobernar |
| **REVISION DIARIA.cmd** | Pasa el forense del día y te abre el panel actualizado | Cada mañana (o prográmalo) |

## 11. El alta de un cliente, sin fricción (el caso Pedro)

En el Centro de Mando hay un botón **«+ Alta de empresa»**. Es un formulario en lenguaje llano — nombre, a qué se dedica, cómo quiere sonar, qué no se puede decir nunca, quién firma, y qué departamentos contrata. Son las preguntas exactas de la reunión con el cliente: rellénalo con él en 10 minutos, o mándale las preguntas tal cual.

Al pulsar «Crear la ficha», Kaizen construye solo la carpeta de esa empresa: su perfil, su biblia de marca (guía de tono, palabras prohibidas, vetos con el formato exacto que el guardián entiende), su firma y su lista de departamentos contratados. Desde ese momento el guardián de marca ya juzga los textos de ese cliente con SU criterio, no con el de Laboratorio. Y como siempre: nace con permisos BAJOS — nada sale al mundo sin tu autonomía y el comité.


## 12. La [[MESA_DEL_JEFE|Mesa del Jefe]] (lo que vera Alejandro)

La pagina de Alejandro: saludo, resumen de ayer en una linea, y tarjetas grandes SI/NO. Cada tarjeta dice quien la propone (que departamento), que quiere hacer y por que, con el texto completo desplegable. Su SI deja la propuesta aprobada en cola de ejecucion (el disparo real llega en la S3 del plan: portero + comite + envio con tope diario); su NO tambien queda registrado y el sistema aprende. Decision irreversible y sellada.

Para probarla TU hoy: doble clic en "CREAR TARJETAS DEMO.cmd" (fabrica 3 tarjetas con leads reales y texto de plantilla marcado [DEMO]) y despues doble clic en "MESA DEL JEFE.cmd". Para el movil de Alejandro (S5 del plan): tunel seguro + PIN (MESA_PIN en .env) + icono en su pantalla de inicio. Regla: la Mesa jamas se expone por tunel sin PIN configurado.

**Plan hasta el 30 de agosto (corregido por CORRECCIONES v1.0):** S1 Mesa (HECHA; validacion tuya pendiente, R9) - S2 [[RITUAL_DE_LA_MANANA|ritual de la manana]] con IA real que fabrica las tarjetas - S3 envio real tras el SI, con ENTREGABILIDAD obligatoria antes del primer tercero: SPF/DKIM/DMARC verificados con dig y documentados, rampa <=10 emails/dia, test de bandeja en cuentas propias; dominio frio o sin autenticar = PARAR (E3) - S4 prospeccion Maps por circulos cosida al registro - S5 DESPLIEGUE EN INFRAESTRUCTURA PERSISTENTE (VPS Contabo existente o mini-PC del obrador, decidido y ejecutado ANTES de dar acceso a terceros; ngrok solo para tus pruebas internas; prohibido que Alejandro dependa de tu PC encendido, E2) + PIN + movil, y tu semana viviendo como Alejandro - S6-7 escuchantes (ops/cs/finanzas) + informe semanal + pulido - S8 congelacion y ensayo general (cero features, R9). **HITO DURO [[AIACT_GATE|AIACT-GATE]] 2026-08-02 (E4):** desde esa fecha, ninguna salida generada por IA sin regimen de transparencia aplicado; el preflight ya rechaza primeros mensajes fuera del fichero aprobado, y el ejecutor de emails de la S3 debera aplicar el mismo candado por fecha. Estado variantes: las 20 APROBADAS por el operador el 2026-07-03 (evidencia reproducida hoy: 20 variantes en el fichero runtime + test E2E en verde).
