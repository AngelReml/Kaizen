# MATRIZ DE CUBOS — generada 2026-09-30

**Tipo:** estado (capa 4, se regenera; no editar a mano) · **Fuente:** `cubos/*/manifest.json`, `departments/catalogo.py`, árbol y tests · **Generador:** `python herramientas/matriz_cubos.py`

«Cableado» y «verificado en vida real» NO se pueden derivar de los manifests: aparecen como no determinado hasta que exista acta.

## 1. Matriz

| Cubo | Misión (manifest) | Dossier | Autonomía | Produce | Consume | Irreversibles | Catálogo | .py | Tests* | Herramientas panel |
|---|---|---|---|---|---|---|---|---|---|---|
| brand | Guardian de marca: revisa borradores y tono; asesor, no ejecutor | D02 | BAJA | 1 | 0 | — | construido | 8 | 5 | 16 |
| comercial | Departamento Comercial HORECA | D01 | BAJA | 5 | 0 | contacto_saliente_ia, envio_email_real, compromiso_ante_cliente | construido | 49 | 44 | 10 |
| customer_success | Postventa: seguimiento de clientes e incidencias | D03 (NO EXISTE) | BAJA | 1 | 1 | — | construido | 4 | 3 | 6 |
| finanzas | Finanzas: registra y reporta; JAMAS ejecuta pagos (solo humano) | D04 | BAJA | 1 | 1 | — | construido | 6 | 8 | 12 |
| inteligencia | Inteligencia de mercado: informes; solo lee y publica analisis | D07 | CERO | 1 | 1 | — | construido (`inteligencia_mercado`) | 5 | 3 | 11 |
| legal | Legal y Cumplimiento: dictamina riesgos, gestiona el calendario de obligaciones y compila defensa documental; no ejecuta acciones externas | D08 (Cumplimiento, fusionado) | BAJA | 1 | 0 | — | construido | 5 | 2 | 15 |
| marketing | Marketing: borradores de contenido; publicar de verdad exige gate | D06 | BAJA | 2 | 0 | publicacion_externa_real | construido | 5 | 3 | 9 |
| ops | Operaciones: tareas y compromisos internos de entrega | D05 | BAJA | 1 | 1 | — | construido (`operaciones`) | 6 | 4 | 10 |
| qa | Calidad: valida salidas de otros cubos antes de que cuenten | — (sin dossier) | CERO | 1 | 1 | — | construido (`opengravity`) | 5 | 3 | 6 |
| rrhh | RRHH: gestiona los agentes de Kaizen (que directores hay, cuales faltan y como rinden); solo lee y propone | — (sin dossier; D00 lo deja ABIERTO) | CERO | 1 | 0 | — | construido | 3 | 1 | 6 |

\* ficheros de test que mencionan el cubo (heurística por texto; no es cobertura).

## 2. Grafo de eventos (declarado en manifests)

| Evento | Productor | Consumidores |
|---|---|---|
| `kaizen.brand.revision_emitida.v1` | brand | **nadie** |
| `kaizen.comercial.compromiso_creado.v1` | comercial | ops |
| `kaizen.comercial.compromiso_vencido.v1` | comercial | **nadie** |
| `kaizen.comercial.interaccion_registrada.v1` | comercial | qa |
| `kaizen.comercial.lead_actualizado.v1` | comercial | inteligencia |
| `kaizen.comercial.pedido_registrado.v1` | comercial | customer_success, finanzas |
| `kaizen.customer_success.incidencia_registrada.v1` | customer_success | **nadie** |
| `kaizen.finanzas.movimiento_registrado.v1` | finanzas | **nadie** |
| `kaizen.inteligencia.informe_publicado.v1` | inteligencia | **nadie** |
| `kaizen.legal.dictamen_emitido.v1` | legal | **nadie** |
| `kaizen.marketing.borrador_generado.v1` | marketing | **nadie** |
| `kaizen.marketing.publicacion_realizada.v1` | marketing | **nadie** |
| `kaizen.ops.tarea_completada.v1` | ops | **nadie** |
| `kaizen.qa.validacion_emitida.v1` | qa | **nadie** |
| `kaizen.rrhh.puesto_definido.v1` | rrhh | **nadie** |

Eventos consumidos sin productor declarado: ninguno.

## 3. Divergencias detectadas (estado real vs declarado)

- **Nombre doble:** el cubo `inteligencia` (manifest) es `inteligencia_mercado` en el catálogo.
- **Nombre doble:** el cubo `ops` (manifest) es `operaciones` en el catálogo.
- **Nombre doble:** el cubo `qa` (manifest) es `opengravity` en el catálogo.
- **RRHH:** el manifest declara `consume: []`, pero el código consume CUBE_STARTED, DEPT_TASK_COMPLETED, DEPT_TASK_FAILED, OPENGRAVITY_ESCALATION_REQUESTED.
- **Dossier ausente:** `customer_success` cita D03 (NO EXISTE); los otros dossiers lo mencionan como «siguiente de la serie».
- **Eventos sin ningún consumidor declarado:** 11 de 15 (ver tabla 2); solo 4 están cableados por contrato entre cubos.

## 4. No determinado desde el código

Cableado en flujo real, verificación en vida real y salud viva por tenant: requieren acta o lectura del bus en ejecución.
