# KAIZEN-D04 — DEPARTAMENTO FINANZAS · MOTOR SIF VERIFACTU
## Serie de dossieres departamentales KAIZEN · Documento 04

**Autor:** Iván Carbonell (ZapWeave)
**Fecha de emisión:** 2026-07-08
**Versión:** 1.0 (gobernada por D00 §0.7)
**Declara contra:** KAIZEN-D00 v1.0. Estructura conforme a la plantilla obligatoria de la serie (D01).
**Propietario en el RUE de:** todos los tipos `finanzas.*` (payloads en Anexo A).
**Resolución fundacional (§0.3):** un motor, dos caras, tres planos, dos pistas.
**Documento de canal asociado:** dossier VeriGest (33 págs.: marco regulatorio, playbook de migración, scripts comerciales, objeciones). Aquí se referencia como especificación de canal; **no se duplica**.

---

## ÍNDICE

- §0 — Naturaleza, posición y la resolución un-motor-dos-caras
- §1 — Misión, fronteras y recorridos E2E (Pista A: liquidación · Pista B: factura verificable)
- §2 — Anatomía del trabajo humano que replica (y la regla de la gestoría)
- §3 — Roles y sub-agentes: catálogo completo
- §4 — Definiciones formales: liquidación, registro de facturación conforme, cadenas
- §5 — Declaración de interoperabilidad (Anexo I de D00, cumplimentado)
- §6 — Autonomía y verificación aplicadas: matriz acción × nivel
- §7 — Cumplimiento integrado: RRSIF regla → control → test
- §8 — Bucle de datos (P8) y sistema de registro (P9)
- §9 — Economía del cubo y del motor
- §10 — Kits de despliegue (pyme y partner-gestoría) y superficies
- §11 — Estado real vs. dossier: declaración de greenfield honesto
- §12 — Programa de construcción a v1.0: bloques FA (Pista A) y FB (Pista B)
- §13 — Batería de pruebas duras
- §14 — Pruebas de vida real pre-registradas (VR-D04-01/02/03)
- §15 — Riesgos de segundo orden
- §16 — Puertas v1.0: DoD comercial (A), la-firma-es-la-puerta (B) y falsación
- Anexo A — Esquemas de payload `finanzas.*` v1
- Anexo B — Crosswalk RRSIF → secciones de este dossier

---

## §0 — NATURALEZA, POSICIÓN Y LA RESOLUCIÓN UN-MOTOR-DOS-CARAS

### §0.1 Herencias
Convención de estados, precedencia, ciclo de vida y reglas R1–R4: D00 §0.2–0.6. Garantías G1–G5 del sustrato: se usan, no se reconstruyen. Índice: plantilla D01.

### §0.2 Marco legal de referencia — FIJADO (verificación de detalle en FB0)
Ley 11/2021 (arts. 29.2.j y **201 bis LGT**: 150.000 € por ejercicio y tipo de producto para el fabricante/comercializador de software no conforme; 50.000 € por ejercicio para el usuario que lo tenga) · **RD 1007/2023 (RRSIF)** · **Orden HAC/1177/2024** (formatos de registro, huella, registro de eventos, QR, remisión, declaración responsable) · RD 254/2025 (fechas de los obligados: **01-01-2027** contribuyentes de Sociedades; **01-07-2027** resto, incluido IRPF). Dos relojes distintos y la trampa está en confundirlos: **las fechas de 2027 son de los usuarios; el software comercializado debe ser conforme desde ya** — la obligación del fabricante corre desde 2025. El reloj real de la Pista B no es enero de 2027: es la fecha de la primera venta. Fuera de alcance v1.0 (FIJADO): obligados en SII, territorios forales (TicketBAI/Navarra), y la factura electrónica B2B de la Ley Crea y Crece — que es **otra** obligación distinta de Verifactu, frontera vigilada pero no construida.

### §0.3 La resolución — FIJADO
- **Tres planos que no se confunden:** (1) VeriGest como *tenant* de Kaizen (ya real: usa el cubo Comercial para prospectar gestorías); (2) Verifactu como *capacidad legal* del cubo Finanzas (si emite facturas, es un SIF y cumple el RRSIF, sin opción); (3) VeriGest como *producto* white-label B2B2B vía gestorías.
- **Un motor:** un único motor SIF certificado vive en este dossier y sirve a las dos caras. Construirlo dos veces sería el pecado capital del operador único.
- **Dos caras del mismo motor:** cara Kaizen (el cubo Finanzas vendido a la pyme directa) y cara VeriGest (licencias multi-obligado a través de la gestoría). Mismo núcleo, dos pieles, dos líneas de ingreso.
- **Dos pistas con puertas separadas:** **Pista A** (cubo Finanzas mínimo: liquidaciones, cobros, caja — **no emite facturas → no es SIF → cero carga RRSIF**, puede operar ya) y **Pista B** (motor SIF completo — su puerta es la declaración responsable firmada, §16.2).
- **Primer obligado de la Pista B:** la propia S.L. — el motor se come su propia comida antes de venderse.
- **Convergencia arquitectónica:** el RRSIF exige registros encadenados por huella y registro de eventos inalterable: la misma disciplina que la bitácora hash de D00 §3.4. El sustrato ya piensa como la norma; la implementación RRSIF es una cadena legal específica **aparte** (formatos y serialización de la Orden), con el mismo ADN.
- **Impacto en D00 (nota v1.1, no reabre nada):** la ficha de tenant gana el campo opcional `partner_id` (gestoría → sus obligados) para la jerarquía B2B2B.

---

## §1 — MISIÓN, FRONTERAS Y RECORRIDOS E2E

### §1.1 Misión en una frase
El cubo Finanzas convierte el resultado comercial en dinero ordenado y ley cumplida: **liquida** lo atribuido con números reproducibles, **registra** cobros y caja, y —cuando la Pista B esté firmada— **emite facturas verificables** cuya integridad puede comprobar hasta Hacienda.

### §1.2 Qué NO es — FIJADO
- **No es asesoría fiscal ni contable** (coherente con la cl. 12 del contrato tipo). Calcula, registra, emite y documenta; no interpreta la norma para el cliente.
- **No sustituye a la gestoría: la alimenta** (§2.2). La gestoría es canal (F4 de la Tesis), no competidor.
- **No es contabilidad oficial completa** (libros, cuentas anuales): exporta datos limpios hacia quien la lleva.
- **No opera** SII, forales ni factura-e B2B Crea y Crece en v1.0 (§0.2).
- **No borra jamás un registro de facturación:** anular es escribir un registro nuevo (§4.3). El doble uso no es un riesgo a mitigar: es una imposibilidad de construcción (§13.7).

### §1.3 Recorrido A — LOS PASOS de una liquidación (Pista A)

| # | Paso | Actor | Decide | Gate/verificación | Evento (RUE) |
|---|---|---|---|---|---|
| A1 | Cierre de periodo: agregación de `comercial.pedido.atribuido` del mes del tenant | Liquidador | Sistema | **Solo atribuciones firmes**: estado ATRIBUIDO con cadena íntegra; PENDIENTE_VALIDACION queda fuera con informe | — |
| A2 | Cálculo del beneficio neto por pedido con los costes directos del **Anexo I firmado** (Laboratorio) o del Anexo II (contrato tipo) | Liquidador | Sistema | Determinista y **reproducible**: re-ejecutar = mismos números; parámetros versionados | `finanzas.liquidacion.calculada` |
| A3 | Borrador de liquidación (detalle por pedido, total, periodo) al operador y al cliente | Liquidador | Sistema | Verificación aritmética independiente (recomputación) | — |
| A4 | Revisión y aprobación | Operador (con cliente) | **Humano** | Cola D00 §4.3; discrepancia → vía de revisión de la cl. 2.5 | `plataforma.aprobacion.*` → `finanzas.liquidacion.aprobada` |
| A5 | Emisión de la factura propia por el importe liquidado | Emisor | Sistema (post-aprobación) | **Degradado pre-Pista-B:** emisión por el medio actual de la S.L., registrada aquí con referencia; **post-B:** recorrido §1.4 | `finanzas.factura.emitida` |
| A6 | Envío y seguimiento de vencimiento | Emisor/AE-Fin | Sistema | plazo del contrato | — |
| A7 | Registro del cobro (entrada manual o import CSV bancario) | Conciliador | Operador registra / sistema propone | — | `finanzas.cobro.registrado` |
| A8 | Conciliación cobro↔factura↔liquidación | Conciliador | Sistema propone, humano confirma en BAJA | tolerancias del mandato | `finanzas.cobro.conciliado` |
| A9 | Señal a Comercial: CUSTOMER confirmado por cobro (V4 de D01); señal P8 de comportamiento de pago | Bus | — | frontera §8 | consumido por D01 |
| A10 | Informe de caja y aging del tenant | Tesorería | Sistema | — | `finanzas.caja.informe` |

### §1.4 Recorrido B — LOS PASOS de una factura verificable (motor SIF, modo VERI*FACTU)

| # | Paso | Actor | Decide | Gate/verificación | Evento |
|---|---|---|---|---|---|
| B1 | Solicitud de emisión (del propio cubo, del obligado en su panel, o de la gestoría para su cliente) | interfaz | según §6 | acuerdo de facturación por tercero vigente cuando emite el sistema en nombre del obligado | — |
| B2 | Validación fiscal determinista: NIF válido, serie correcta del obligado, datos mínimos de factura completos, desglose de IVA coherente | Validador | Sistema | **estructural, no LLM**; incompleto = no existe la factura | — |
| B3 | Aprobación según nivel (§6) | Operador/obligado | **Humano** (BAJA) / lote (MEDIA) | cola D00 | `plataforma.aprobacion.*` |
| B4 | Generación del **registro de facturación de alta** con todos los campos de la Orden | Generador RFA | Sistema | esquema validado contra los anexos oficiales (FB0) | — |
| B5 | **Huella encadenada** al registro anterior **del mismo obligado** (SHA-256) + sello temporal | Encadenador | Sistema | cadena por NIF, jamás cruzada (§13.1); reloj monotónico (§13.3) | — |
| B6 | Persistencia (outbox) **antes** de nada más | almacén | Sistema | exactamente-una-factura (§13.2) | `finanzas.factura.emitida` |
| B7 | **Remisión inmediata a AEAT** con flujo de control (respetar el tiempo de espera indicado en la respuesta) | Remisor | Sistema — **deber legal, no decisión: automático en todos los niveles** | cola con reintento conforme; incidencia = remisión al restablecerse, la factura ya emitida sigue válida | `finanzas.remision.enviada` |
| B8 | Respuesta AEAT: aceptado / aceptado con errores / rechazado | Remisor | Sistema | rechazo → subsanación como **nuevo envío**, la cadena no se toca | `finanzas.remision.aceptada` / `.rechazada` |
| B9 | Factura entregable: PDF con **QR tributario** (URL de cotejo AEAT) y leyenda de factura verificable | Generador de factura | Sistema | **gate estructural: sin QR válido y leyenda, el documento no sale** (patrón bloques-obligatorios de D01) | — |
| B10 | Entrega al destinatario (email/panel) | canal | según §6 | — | — |
| B11 | Espejo a bitácora + **registro de eventos SIF** (log legal propio, encadenado, de la Orden) | Sustrato + SIF | Sistema | dos cadenas: la legal (RRSIF) y la operativa (D00 §3.4), verificables ambas | `finanzas.sif.evento_registrado` |
| B12 | Anulación/rectificación cuando toque: **registro de anulación** o factura rectificativa (serie R) encadenados; borrado inexistente por construcción | Operador/obligado | **Humano siempre** | §4.3 | `finanzas.factura.anulada` |

---

## §2 — ANATOMÍA DEL TRABAJO HUMANO QUE REPLICA

### §2.1 Descomposición

| Función humana | Qué hace de verdad | Rol sintético |
|---|---|---|
| Administrativo de facturación | Emite, numera, persigue vencimientos, no se equivoca de serie | Validador + Generador RFA + Emisor |
| Contable auxiliar | Registra cobros, concilia banco, cuadra el mes | Conciliador + Tesorería |
| El dueño con la libreta del 50/50 | Calcula "lo tuyo y lo mío" a ojo | Liquidador (con números reproducibles y cadena de pedidos) |
| La gestoría | Impuestos, libros, criterio fiscal | **Nadie.** Se le entrega export limpio y acceso partner. |

### §2.2 La regla de la gestoría — FIJADO
El canal VeriGest vive o muere por esto: **el cubo hace el trabajo mecánico que la gestoría no quiere (registro conforme, cadena, remisión, orden) y le entrega mejor materia prima para el trabajo que sí quiere (criterio, impuestos, cliente)**. Ninguna función del cubo compite con el servicio facturable de una gestoría; toda superficie partner (§10.3) está diseñada para que la gestoría quede mejor ante su cliente. El día que este dossier proponga "asesoramiento fiscal automático", ha traicionado su canal: veto estructural.

---

## §3 — ROLES Y SUB-AGENTES: CATÁLOGO COMPLETO

Formato: misión · entrada→proceso→salida · clase de tarea · autonomía · verificación · estado.

### §3.1 Liquidador — **E parcial** (cálculo 50/50 en papel; sistematización en FA0)
- **Misión:** convertir los pedidos atribuibles del mes en números que el cliente y el operador pueden defender.
- **E→P→S:** agregación de `comercial.pedido.atribuido` (ATRIBUIDO únicamente) por periodo + Anexo I/II firmado → aplicación de costes directos por pedido → cálculo de beneficio neto y comisión 50/50 o variable → borrador de liquidación.
- **Clase:** TRIVIAL (determinista; recomputación = resultado idéntico o fallo de datos).
- **Autonomía:** REVERSIBLE (borradores). **Verificación:** recomputación independiente (test universal en FA1).
- **Estado:** existe de facto (célula Laboratorio calcula mensualmente); su sistematización queda en FA0.

### §3.2 Validador (Pista B) — **P·FB0**
- **Misión:** imposibilidad de emitir una factura fiscal deficiente (NIF, serie, datos mínimos, IVA coherente).
- **E→P→S:** solicitud de emisión → validación estructural **determinista**, no LLM → veredicto {EMITABLE, INCOMPLETA, NIF_INVALIDO, SERIE_ILEGAL} → bloquea si no EMITABLE.
- **Clase:** TRIVIAL. **Autonomía:** bloqueante (cierra, no abre). **Verificación:** test por caso negativo.

### §3.3 Generador RFA (Pista B) — **P·FB1**
- **Misión:** producir el registro de facturación de alta conforme a la Orden HAC/1177/2024 en su forma XML/TXT según protocolo, con todos los campos mapeados.
- **E→P→S:** datos de factura validados → mapeo contra esquema oficial (anexos de la Orden) → serialización determinista → RFA con hash interior pre-huella.
- **Clase:** ESTANDAR (P6: modelo barato para serialización; JSON→XML es transformación, no generación). **Autonomía:** REVERSIBLE. **Verificación:** validación contra esquema; test de equivalencia (factura → RFA → factura) sin pérdida.

### §3.4 Encadenador (Pista B) — **P·FB1**
- **Misión:** que la integridad de la cadena fiscal sea computable por cualquiera (AEAT incluida).
- **E→P→S:** RFA nuevo + última huella de este obligado → cálculo SHA-256(huella_anterior || RFA_canonico) → RFA con huella nueva → entrada en bitácora de huellas por NIF.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE. **Verificación:** bitácora verificable en C §13.4; jamás caída de huella o resincronización.

### §3.5 Remisor (Pista B) — **P·FB2**
- **Misión:** garantizar que el AEAT vea la factura o que sea evidente por qué no la vio (requisito legal estricto).
- **E→P→S:** RFA encadenado → construcción de sobres SOAP según protocolo AEAT → envío inmediato → reintento exponencial con respeto a los tiempos de la respuesta → acta de remisión.
- **Clase:** CRITICA (depende de tercero, latencia variable). **Autonomía:** IRREVERSIBLE-EXTERNA automática en TODOS los niveles (no es decisión, es deber). **Verificación:** fallo de remisión = alerta al operador + bloqueo de nueva emisión del obligado hasta que se resuelva (§15.5).
- **Nota de diseño:** el delay de AEAT nunca causa que una factura válida emitida sea inválida; la remisión fallida es un acto separado que se reintentar indefinidamente sin afectar la factura (§4.2).

### §3.6 Generador de factura (Pista B) — **P·FB3**
- **Misión:** PDF legible y verificable (con QR tributario).
- **E→P→S:** RFA remitido con respuesta AEAT aceptada + template + datos del obligado/destinatario → PDF con QR generado (URL de cotejo AEAT en tiempo real o estático según protocolo) + leyenda de factura verificable integrada → documento con firma digital (opcional, regulatorio varía).
- **Clase:** ESTANDAR. **Autonomía:** REVERSIBLE. **Verificación:** QR funcional (test de resolución, enlace vivo a AEAT).

### §3.7 Emisor (Pista A y B) — **E parcial**
- **Misión:** matar la categoría "factura pendiente de envío"; el documento llega al tiempo correcto por el canal correcto.
- **Entrada:** factura aprobada y (en Pista B) remitida. **Salida:** entrega en panel y/o email.
- **Clase:** TRIVIAL. **Autonomía:** REVERSIBLE (reenvío a solicitud). **Verificación:** entrega registrada.

### §3.8 Conciliador — **P·FA2**
- **Misión:** el banco dice una cosa, la factura dice otra; aquí se entierran las diferencias.
- **E→P→S:** extracto bancario (CSV o QIF importado) + facturas emitidas → matching por cantidad/cuenta/fecha con tolerancia del mandato → propuestas de conciliación → confirmación del operador → actualización de estados de cobro.
- **Clase:** ESTANDAR. **Autonomía:** propone (BAJA); confirma operador (todos los niveles). **Verificación:** aging del tenant (factura sin cobro después de plazo = informe).

### §3.9 Liquidador de Pista B — **P·FB4** (rol separado del de Pista A, aunque el nombre se reutilice)
- **Misión:** para el partner gestoría: liquidación de las comisiones de VeriGest por obligado gestionado y uso de la plataforma.
- **Entrada:** uso agregado del motor SIF por partner y obligado. **Salida:** factura mensal o trimestral del partner. **Nota:** doble liquidación (cliente final paga factura válida RRSIF; partner paga el software de emisión) — dos cadenas que jamás se tocan.

---

## §4 — DEFINICIONES FORMALES: LIQUIDACIÓN, REGISTRO, CADENAS

### §4.1 Liquidación (Pista A) — FIJADO
Un documento binding que afirma: "el pedido X tiene beneficio Y, tu parte es Z, fecha de corte T, verificable en [link]".

```
Liquidacion = {
  periodo: AAAA-MM,
  tenant_id,
  pedidos: [
    {
      pedido_id (referencia D01),
      via_atribucion (DIRECTA|REPETICION|REGISTRO_EXTERNO),
      importe_bruto,
      costes_directos (itemizado de Anexo I/II),
      beneficio_neto = importe_bruto - costes_directos,
      comision_50_50 | comision_variable (según contrato)
    }
  ],
  total_atribuible,
  total_comision,
  hash_pedidos (SHA-256(pedidos.*.pedido_id en orden)),
  veredicto_recalculable: VERIFICABLE | ERROR_DATOS,
  versionado_anexo_fiscal,
  fecha_calculo_ts,
  numero_revisor_opcionalmente_firmante
}
```

Propriedades: sin "salvo cambios", sin "a revisión"; es la verdad del mes, disputable solo con evidencia (recalcular con los mismos parámetros = mismos números). El día que una liquidación no sea reproducible, tiene error.

### §4.2 Factura verificable (Pista B) — FIJADO
No es una factura fiscal "más"; es una factura XML válida ante AEAT + un estado de encadenamiento computable.

```
FacturaVerificable = {
  numero_serie_obligado,
  fecha_emision,
  nif_obligado, nif_destinatario,
  descripcion (una sola línea o itemizado conforme),
  importe_neto, iva_base_imponible, iva_cuota, importe_total,
  numero_registro_atribuible | numero_liquidacion (trazabilidad interna),
  **registro_facturacion_alta (RFA):** {
    ...campos Orden HAC/1177/2024...,
    huella_anterior,
    huella_esta_factura = SHA-256(huella_anterior || RFA_canonico),
    ts_huella (sello temporal AEAT si viene de la remisión),
    estado_remision: ACEPTADA|ACEPTADA_CON_ERRORES|RECHAZADA,
    acta_remision: { ts, respuesta_codigo, acta_campos }
  },
  **qr_tributario** (URL con tokenización de la huella, resoluble por AEAT),
  leyenda_factura_verificable,
  pdf_entregable: { firma_digital_opcional, qr_embebido, ...  }
}
```

Propriedades: la huella encadenada vive tanto en la bitácora D00 como en el registro legal RRSIF (dos cadenas, jamás cruzadas). Anulación es un registro de anulación nuevo en la cadena; borrado no existe.

### §4.3 Anulación y rectificación — FIJADO
El RRSIF **no permite eliminar registros**. Las opciones legales:

- **Anulación:** factura válida que se revoca. Se registra un evento de anulación encadenado con motivo. La factura original sigue en la cadena (inmutable), pero marcada ANULADA. El acto no es borrarlo: es cerrar el ciclo. Test §13.7.
- **Rectificativa:** nueva factura serie R que corrige. Ambas cadenas: la original y la nueva encadenada. Jamás borrado.

Bloqueo de código (§13.2): **la única ruta de "borrado" de una factura es la anulación —una nueva entrada encadenada—**. No existe `DELETE FROM facturas WHERE id=X`.

### §4.4 Integridad verificable — FIJADO
Cualquiera puede computar:

```
huella_n = SHA-256(huella_{n-1} || contenido_canonico_RFA_n)
if huella_n_reportado == huella_n_calculado:
  estado = INTEGRA
else:
  estado = ALTERADA (señala dónde)
```

La bitácora SIF legal (llave NIF, ordenada por huella) es por sí sola la prueba. No necesita un "servicio de verificación" aparte; es verificable a mano si hace falta (aunque claro, el teléfono la valida en segundos).

---

## §5 — DECLARACIÓN DE INTEROPERABILIDAD (Anexo I de D00, cumplimentado)

### §5.A — Eventos que PUBLICA

| Tipo (RUE) | v | Payload | Frecuencia | Outbox | Verificación | Cumplimiento | Coste |
|---|---|---|---|---|---|---|---|
| `finanzas.liquidacion.calculada` | 1 | A.1 | mensual por tenant | no | recomputación | — | TRIVIAL |
| `finanzas.liquidacion.aprobada` | 1 | A.2 | = anterior | **sí** (consumida por Comercial para CUSTOMER) | post-aprobación D00 §4.3 | — | TRIVIAL |
| `finanzas.factura.emitida` | 1 | A.3 (Pista A), A.4 (Pista B) | venta a venta / legislado | **sí** (B: clave, es la jurisdicción) | preventiva (bloques) + post-aprobación; B: determinista RFA | cumplimiento §7 | canal (A), CRITICA (B) |
| `finanzas.remision.enviada` | 1 | A.5 | Pista B = factura | **sí** | logs de protocolo AEAT | legal | CRITICA |
| `finanzas.remision.aceptada` / `.rechazada` | 1 | A.6 | respuesta AEAT | **sí** (rechazada dispara subsanación) | acta de respuesta | legal | TRIVIAL |
| `finanzas.sif.evento_registrado` | 1 | A.7 | Pista B por cada RFA | **sí** | bitácora SIF encadenada | RRSIF | TRIVIAL |
| `finanzas.cobro.registrado` | 1 | A.8 | conforme llegue | no | — | — | TRIVIAL |
| `finanzas.cobro.conciliado` | 1 | A.9 | post-conciliación | no | — | — | TRIVIAL |
| `finanzas.caja.informe` | 1 | A.10 | diario/mensual | no | — | — | TRIVIAL |
| `finanzas.factura.anulada` | 1 | A.11 | bajo demanda | **sí** | encadenado; evento de anulación | legal | TRIVIAL |

### §5.B — Eventos que CONSUME

| Origen | Obligatorio | Modo degradado si ausente | Idempotencia |
|---|---|---|---|
| `comercial.pedido.atribuido` | **Sí** (Pista A: requisito, Pista B: requisito) | Sin él, no hay nada que liquidar o facturar → estado ESPERANDO_PEDIDOS | por `pedido_id` |
| `finanzas.cobro.registrado` (de sí mismo vía import) | No | → sin cobro confirmado, CUSTOMER queda en FACTURADO (V4 degradado) | por `cobro_id` |
| `plataforma.aprobacion.*` (D00) | **Sí** (Pista A: BAJA, Pista B: BAJA o lote según nivel) | → sin cola, Pista A opera en CERO (propone), Pista B se paraliza (no hay emisión sin aprobación) | por `aprobacion_id` |

### §5.C — Servicios que OFRECE

| Servicio | Firma | Degradado |
|---|---|---|
| `finanzas.consulta_liquidacion(tenant, periodo)` | → importe, comisión, desglose | lectura pura |
| `finanzas.consulta_factura(tenant, numero)` | → PDF + metadatos | lectura pura |
| `finanzas.verificar_huella(nif_obligado, numero_factura)` | → {integra, huella_reportada, huella_calculada} | — |

### §5.D — Catálogo de acciones — véase §6
### §5.E — Señal P8 — véase §8.2
### §5.F — Visibilidad de cliente — véase §10.3

---

## §6 — AUTONOMÍA Y VERIFICACIÓN APLICADAS: MATRIZ ACCIÓN × NIVEL

Contenido técnico de los Anexos III de los contratos (Laboratorio y tipo cliente). **FIJADO:** Pista A por defecto BAJA; Pista B bajo regulatorio es siempre aprobación humana pre-remisión (la ley exige quién es responsable de la emisión).

| Acción | Clase | CERO | BAJA (A: default; B: legal) | MEDIA | ALTA |
|---|---|---|---|---|---|
| Calcular liquidación mensual | TRIVIAL | propone | auto (determinista) | auto | auto |
| Aprobar liquidación | — | operador | **operador siempre** — sin excepción | — | — |
| Validar datos de factura (Pista B) | TRIVIAL | sistema (bloqueante) | sistema (bloqueante) | sistema (bloqueante) | sistema (bloqueante) |
| **Emitir factura** (Pista A: soft, B: legal) | IRR-EXT | no sale | aprobación **individual** | lote pre-aprobado (baja frecuencia típica) | no disponible en v1.0 |
| **Remitir a AEAT** (Pista B) | IRR-EXT legal | **automático en todos los niveles** — deber, no opción | **automático** | **automático** | **automático** |
| Procesar respuesta AEAT (Pista B) | TRIVIAL | sistema | sistema | sistema | sistema |
| Registrar cobro | REVERSIBLE | propone (import) | propone; operador confirma | import auto+verificación | — |
| Conciliar | REVERSIBLE | propone | propone; operador confirma | propone; auto si coincide dentro de tolerancia | — |
| Anular factura (Pista B) | IRR-INT | operador | operador | operador | operador — **jamás automático** |
| Rectificativa (Pista B) | IRR-EXT | no sale | aprobación individual | lote | — |
| Acceso partner (VeriGest) a datos del obligado | REV lectura | no acceso | acceso solo a sus obligados, solo lectura de estado y cobros | — | — |

**Sellado en diseño:** remisión AEAT es automática **en todos los niveles** (es deber legal, no decisión de autonomía).

---

## §7 — CUMPLIMIENTO INTEGRADO: RRSIF REGLA → CONTROL → TEST

P5 hecho tabla ejecutable. Cada fila termina en un test (FB0/FB1/FB2/FB3/FB4 la construyen; §13 las ataca).

| # | Regla (RRSIF/Orden) | Control determinista en el cubo | Test |
|---|---|---|---|
| 1 | Validación de NIF (art. 3 Orden) | Alta de obligado rechaza sin NIF válido vía DNI-e o algo equivalente validado | `test_nif_invalido_rechazado` |
| 2 | Registro de facturación de alta conforme (art. 4–6 Orden) | Serialización RFA contra esquema oficial; validación pre-huella; rechazo si incompleto | `test_rfa_incompleto_imposible` |
| 3 | Encadenamiento por SHA-256 (art. 7 Orden) | Huella anterior obligatoria; cálculo canónico; bitácora por NIF verificable | `test_cadena_verificable`, `test_alteracion_detectada` |
| 4 | Remisión inmediata a AEAT (art. 8 Orden) | Lanzamiento automático post-aprobación; reintento exponencial; acta de remisión | `test_remision_inmediata`, `test_reintento_exponencial` |
| 5 | Respuesta AEAT procesada (art. 9 Orden) | Parseo de códigos de aceptación/rechazo; rechazo = notificación al operador + cola de subsanación | `test_respuesta_aceptada_registrada`, `test_rechazo_subsanacion` |
| 6 | Sello temporal de la remisión (art. 10) | AEAT proporciona el sello en la respuesta; se registra en la bitácora SIF | se hereda del test de remisión + verificación de sello en bitácora |
| 7 | Anulación como nuevo registro (no borrado) | Única ruta de "anulación" = evento de anulación encadenado; `DELETE` bloqueado por construcción | `test_borrado_imposible`, `test_anulacion_registra` |
| 8 | Bitácora SIF con integridad verificable (art. 11 Orden) | Bitácora por NIF, ordenada por huella, exportable con checksums | `test_bitacora_sif_exportable`, `test_verificacion_huella_independiente` |
| 9 | QR tributario en factura (art. 12) | QR generado en tiempo real o estático según protocolo AEAT; incrustado en PDF antes de entrega | `test_qr_presente_en_pdf`, `test_qr_resuelve_a_aeat` |
| 10 | Leyenda de factura verificable (art. 13) | Leyenda estructurada incrustada en PDF; idioma según obligado; imposible de emitir sin ella | `test_leyenda_presente` |

---

## §8 — BUCLE DE DATOS (P8) Y SISTEMA DE REGISTRO (P9)

### §8.1 El cubo como sistema de registro — FIJADO
Liquidaciones, facturas, cobros y cadenas de integridad fiscal son **la verdad económica del tenant** (P9). Consecuencias: export completo a la baja incluye el registro SIF completo (Pista B); acceso partner a lectura de estado y cobros.

### §8.2 Señal P8 para el bucle — FIJADO
Por cada cobro registrado se captura:

```
(tenant, segmento_cliente, dias_a_cobro, medio_pago, importe, resultado: PAGADO|VENCIDO|RECHAZADO, ts)
```

Ajusta: scoring de segmentos por cobrabilidad, ciclo de tesorería por vertical. Frontera: disociación estricta — jamás nombres de clientes finales; solo agregados.

### §8.3 Entidades y propiedad
Liquidaciones, facturas, RFA, bitácora SIF, cobros → DATO_CLIENTE. Parametrizaciones (series por obligado, criterios de conciliación, comisiones base) → DATO_PLATAFORMA. Asientos P8 disociados → DATO_AGREGADO.

---

## §9 — ECONOMÍA DEL CUBO Y DEL MOTOR

### §9.1 Pista A — cero diferencia vs. hoy
El cubo sistematiza cálculos manuales y genera eventos para el bus; coste incremental de sustrato <<< coste del tiempo ahorrado al operador. Sin margen dedicado en v1.0: es amortización de infraestructura.

### §9.2 Pista B — VeriGest como línea separada
- **Comprador:** gestoría (canal). **Precio:** por obligado/mes (p. ej. 30€/obligado con acceso partner) **+** comisión sobre facturas emitidas (p. ej. 2–5% del importe, decisión de pricing tras VR-03).
- **Servicio:** motor SIF certificado, bitácora legal, remisión AEAT, acceso partner a estado de su cartera.
- **Margen:** el diferencial entre el coste de servir (sustrato + código SIF + AEAT) y el precio; medido en FA4.

### §9.3 Cifra ABIERTA nº 4 de la Tesis — ABIERTO (la abre FB0)
Coste mensual de operar la Pista B (certificación, AEAT, sustrato, horas) contra margen del partner. Cierra la viabilidad del canal.

---

## §10 — KITS DE DESPLIEGUE Y SUPERFICIES

### §10.1 Kit Pista A (pyme cliente directo)
1. **Alta administrativa:** ficha de tenant + mandato (series factura, plazo de cobro default, tolerancia de conciliación, comisión %).
2. **Parametrización:** costeo de Anexo I/II (el cliente se gasta 30 minutos rellenando costes — es su seriedad).
3. **Integración bancaria:** credenciales de acceso (seguro en D00); import CSV o conexión API si el banco lo soporta.
4. **Superficie:** acceso a liquidación + facturas + caja mensual.
5. **Smoke E2E:** liquidación de un pedido ficticio, cobro simulado, conciliación.

### §10.2 Kit Pista B (partner gestoría) — condicionado a FB0 ✓
1. **Acreditación:** acuerdo de partner + certificado de seguridad digital para firmas (si aplica).
2. **Alta de obligados bajo el partner:** ficha por NIF, serie de factura, responsable de emisión (quién firma).
3. **Bitácora pre-inaugural:** primer RFA de prueba encadenado manualmente si es necesario (bootstrap sin historial).
4. **Certificación RRSIF:** declaración responsable del partner + auditoría externa (FB0). Condición de puerta.
5. **Superficie partner:** panel de lectura solo a sus obligados, alertas de remisión fallida, export de bitácora SIF.

### §10.3 Superficie de cliente — FIJADO
- **Pista A (pyme):** liquidación mensual con desglose por pedido, facturas emitidas (número/PDF/estado), caja y aging.
- **Pista B (gestoría):** by obligado: estado de remisión a AEAT (aceptada/rechazada/reintentando), alertas de factura rechazada, export de RFA encadenado.

---

## §11 — ESTADO REAL VS. DOSSIER: DECLARACIÓN DE GREENFIELD HONESTO

### §11.1 Honestidad sobre Pista A
El 50/50 de Laboratorio se calcula **con papel y lápiz cada mes** (auditoría visual del operador sobre hojas de cálculo — Iván, manualmente). El cubo Comercial registra eventos, pero el cierre mensual no es sistémico: **Pista A es greenfield puro de software**. Cero deuda técnica porque cero código previo.

### §11.2 Honestidad sobre Pista B
**Motor SIF:** no existe. El código RRSIF es cero líneas. La Orden HAC/1177/2024 fue publicada el 12/06/2024; el dossier es del 08/07/2026. Existe legislación y existe la intención de cumplirla. **No existe prototipo, concepto, ni prueba de concepto.** FB0 empieza desde scratch. El reloj de Pista B es explícito: el motor se "come su propia comida" primero (obligado: la propia S.L. es el primer usuario; su fecha de obligación es 01-01-2027 para Sociedades, así que el motor debe estar firmemente antes). La puerta v1.0 no depende de que la S.L. haya emitido ya: depende de que exista la capacidad y que se haya verificado con un obligado sintético en VR-D04-03.

### §11.3 Tabla de divergencias esperadas
Ninguna: el dossier describe lo que no existe aún. **Divergencias nacerán en el código en construcción** (son esperadas, de libro). La única promesa viva es que cada bloque documenta su maridaje con el dossier y que cada test que existe en la auditoría respeta el dossier.

---

## §12 — PROGRAMA DE CONSTRUCCIÓN A v1.0: BLOQUES FA Y FB

Orden por dependencia: FA antes de FB (FA es infraestructura de FA + acuña la API que FB extiende). Ambos requieren D00-B1 ✓. Ciclo D00 §0.6; commit por bloque (R1); sin fechas.

### FA0 — Sistematización de liquidación (Pista A)
1. Inventario del proceso manual hoy (Laboratorio): pasos exactos, parámetros, salidas.
2. Liquidador como rol: calculador que recomputa = resultado idéntico.
3. Primeros datos en RUE: `finanzas.liquidacion.calculada`, `.aprobada`.
4. Smoke E2E: pedido ficticio → liquidación → verificación aritmética.
5. **Puerta FA0:** informe reproducible por tenant y mes; la recomputación sin cambios en parámetros = resultado idéntico (test universal).

### FA1 — Eventos de liquidación en el bus + inicio del libro de coste
1. Liquidador emite eventos contra RUE.
2. Comercial consume `finanzas.liquidacion.aprobada` para confirmar CUSTOMER (D01 V4).
3. Inicio del contador de coste integrado (D00 §6.1 está en sustrato; aquí nace la columna `coste_liqui` del libro).
4. **Puerta FA1:** liquidación de un mes real con Laboratorio consumida por el bus, Comercial avanza su vista de cliente.

### FA2 — Banca y conciliación
1. Import CSV/QIF; mapeo de campos.
2. Proposición determinista de matching; confirmación del operador.
3. Transición de factura FACTURADO → COBRADO (o VENCIDO).
4. P8: asiento de días-a-cobro por segmento.
5. **Puerta FA2:** mes real de Laboratorio reconciliado; aging generado.

### FA3 — Superficie de cliente (Pista A)
1. Panel de lectura: liquidación, facturas, caja.
2. **Puerta FA3:** Alejandro y otro tenant leyendo su estado desde el panel (sin edición).

### FA4 — Economía medida
1. Imputación completa de coste (sustrato + LLM + banca).
2. Informe de coste de servir para este cubo (cifra 4).
3. **Puerta FA4:** comparativa de margen contra banda de pricing (ABIERTO).

### Puerta intermedia FA1→FB0: **Laboratorio debe estar emitiendo facturas manualmente en su S.L.** (requisito para que FB0 tenga cliente real de entrada).

---

### FB0 — Certificación e inventario RRSIF (entrada de Pista B)
1. Lectura completa y checklist de la Orden HAC/1177/2024 contra §4–§7 de este dossier.
2. Mapeo de campos RFA contra anexos oficiales.
3. Simulación de encadenamiento (manual, para validar el algoritmo antes de codificar).
4. Búsqueda de certificación RRSIF (auditora externa, costo ~8–15k € según volumen esperado).
5. Auditoría de seguridad digital si se va a firmar (opcional en v1.0).
6. **Puerta FB0:** checklist RRSIF completado; certificador contratado; esquema RFA validado externamente; orden hecha.

### FB1 — Validador + Generador RFA + Encadenador + Remisor (el motor)
1. Validación estructural: NIF, serie, datos mínimos, IVA.
2. Serialización RFA conforme a Orden.
3. Encadenamiento SHA-256 por NIF.
4. Construcción de sobres SOAP; integración AEAT (protocolo, credenciales).
5. Parseo de respuestas AEAT (aceptada, aceptada-con-errores, rechazada).
6. Reintento exponencial con respeto a tiempos de AEAT.
7. **Puerta FB1:** obligado sintético emite 10 facturas en dry-run; 10 remisiones a AEAT; respuestas procesadas; bitácora SIF íntegra y verificable; ninguna factura borrada por construcción.

### FB2 — Generador de PDF + QR
1. Template PDF de factura.
2. Generación de QR tributario (URL a AEAT con token de verificación).
3. Incrustación de leyenda de factura verificable.
4. **Puerta FB2:** PDF con QR funcional resuelto a AEAT (test vivo).

### FB3 — Anulación y rectificativa
1. Evento de anulación encadenado (no borrado).
2. Factura rectificativa serie R encadenada.
3. Tests de imposibilidad de borrado.
4. **Puerta FB3:** anulación y rectificativa de facturas existentes; bitácora íntegra tras ambas; imposibilidad de DELETE.

### FB4 — Liquidación de partner (VeriGest)
1. Agregación de uso por obligado y partner.
2. Cálculo de comisión (fórmula ABIERTA: a fijar tras VR-03).
3. Facturación interna al partner.
4. **Puerta FB4:** primer informe de comisión generado (partners no tienen partners en v1.0, así que es simulado).

### Certificación final (antes de puerta v1.0): auditoría externa RRSIF sobre FB0–FB3.

---

## §13 — BATERÍA DE PRUEBAS DURAS

Umbrales binarios; herencia obligatoria: §13.0 = aislamiento de D00.

| # | Prueba | Montaje | Umbral |
|---|---|---|---|
| 13.1 | **Aislamiento de Pista A** | 2 tenants; liquidaciones paralelas; cero cruce de comisiones | fuga cero; liquidaciones reproducibles en paralelo |
| 13.2 | **Exactitud una sola vez (Pista B)** | Intento de emitir la misma factura dos veces (duplicado de entrada) | primera emite, segunda rechaza con código de duplicado; una sola RFA en bitácora |
| 13.3 | **Reloj monotónico de huella (Pista B)** | Emitir facturas en orden; mudar reloj atrás; retentar | huella_n siempre > huella_{n-1}; manipulación de ts rechazada |
| 13.4 | **Verificación de cadena independiente** | Bitácora SIF exportada; verificación de huellas sin la aplicación | 100% de huellas verificables fuera del programa (a mano si falta falta) |
| 13.5 | **Remisión fallida no pierde la factura** | AEAT timeout / 500 error; reintentos de remisión | factura válida emitida, reintento de remisión indefinido en background, documento no rechazado |
| 13.6 | **Rechazo AEAT → subsanación** | RFA incompleto enviado (campo faltante); rechazo de AEAT; generación de RFA subsanado | nuevo envío con campo corregido; ambas facturas en bitácora (original + subsanada); sistema no confunde la subsanación con el original |
| 13.7 | **Anulación imposibilita borrado** | Intento de `DELETE` sobre factura; intentto de `UPDATE` de RFA; intento de truncar bitácora | tres comandos bloqueados por construcción; única ruta válida es evento de anulación |
| 13.8 | **Liquidación reconciliable** | Liquidación de 10 pedidos; importación de 8 cobros parciales / 1 completo / 1 rechazado | estado correcto en panel; aging generado; nada auto-descartado |
| 13.9 | **QR funcional** | Extracción del QR de 5 facturas generadas; resolución a AEAT | todas resuelven (200 OK desde AEAT con respuesta de validez de factura) |
| 13.10 | **Leyenda incrustada** | PDF de 5 facturas; parseo de texto incrustado | leyenda presente y legible en todas |

---

## §14 — PRUEBAS DE VIDA REAL PRE-REGISTRADAS

### VR-D04-01 — Cierre de mes de Laboratorio (Pista A) — **Puerta FA3**
Pre-registro conforme a D00 Anexo II:
- **Tenant:** `laboratorio` · **Ventana:** 1 mes natural (30 días) · **Acciones:** ≥ 5 pedidos reales atribuidos en el mes.
- **Métricas y umbrales:**
  1. Liquidación mensual reproducible (recomputación = mismo resultado).
  2. Conciliación de ≥80% de los cobros esperados.
  3. Cliente viendo panel con liquidación + facturas + caja.
  4. Coste de servir de Pista A medido (cifra ABIERTA).
- **Fallo total:** cualquier liquidación no reproducible → aborta.

### VR-D04-02 — Rial o segundo tenant en Pista A (escala) — **Puerta FA4**
Mismo montaje que VR-01 con distinto tenant, cronometrado (infraestructura de FA reutilizable).

### VR-D04-03 — Motor SIF sintético (Pista B) — **Puerta FB3**
Pre-registro:
- **Obligado sintético:** NIF válido ficticio, serie de prueba de la Orden.
- **Ventana:** 2 semanas de operación.
- **Acciones:** N ≥ 20 facturas (mix: emitidas sin problema, incompletas rechazadas, rectificativas, anuladas).
- **Métricas:**
  1. 15 facturas emitidas sin rechazo de AEAT (aceptadas).
  2. 3 facturas incompletas: remisión rechazada, subsanación enviada y aceptada.
  3. 1 rectificativa encadenada correctamente.
  4. 1 anulación registrada, bitácora íntegra.
  5. Bitácora SIF exportada y verificada fuera del programa (§13.4).
  6. QR de todas resuelve a AEAT.
- **Fallo total:** cualquier factura borrada, cualquier huella saltada, cualquier QR inválido → aborta.

### VR-D04-04 — Partner gestoría (Pista B + VeriGest) — **Puerta FB4**
Condición: VR-03 ✓ + primer partner real (gestoría) interesada en probar. **No bloquea v1.0 si no hay partner en mesa en el momento.**

---

## §15 — RIESGOS DE SEGUNDO ORDEN

| Riesgo | Control | Evidencia |
|---|---|---|
| **Duplicado de emisión** (cliente clica "enviar" dos veces) | Deduplicación por event_id + claim atómico de aprobación | §13.2 |
| **Reloj adelantado o atrasado** | Validación de monotonía de huella; sello de AEAT como fuente de verdad | §13.3 |
| **Remisión fallida permanente** | Reintento indefinido sin bloqueo de factura (estados separados); alerta al operador | §13.5 + alertas en panel |
| **AEAT rechaza por error de formato** | Subsanación automática donde sea posible (codicioso), escalación a operador si no | §13.6 |
| **Manipulación de bitácora** | Encadenamiento verificable fuera del programa; imposibilidad de borrado | §13.4, §13.7 |
| **Responsabilidad legal confusa** | Declaración responsable del partner y acta de certificación exterior (Orden) | FB0 y puerta v1.0 |
| **Gestoría competencia** | Panel partner read-only + alertas + datos clean para que la gestoría trabaje mejor | §2.2, §10.2 |
| **Cobro rechazado post-conciliación** | Transición COBRADO ← VENCIDO con alerta; no auto-reintento, escalación | FA2 |
| **Comisión de partner discrepo** | Export auditado de uso + fórmula versionada + recomputación del operador | FB4 |

---

## §16 — PUERTAS v1.0: DoD COMERCIAL (PISTA A), LA-FIRMA-ES-LA-PUERTA (PISTA B), FALSACIÓN

### §16.1 Checklist Pista A — FA0–FA4 cruzados
- [ ] FA0–FA4 commits + actas de bloques.
- [ ] Batería §13.1–13.8 en verde.
- [ ] VR-D04-01 ✓ : Laboratorio con mes real closeable y reconciliable.
- [ ] VR-D04-02 ✓ : segundo tenant en Pista A.
- [ ] Panel de cliente funcional mostrando liquidación, facturas, caja.
- [ ] Laboratorio ve su 50/50 desglosado en panel (verificación visible aplicada al dinero).

### §16.2 Checklist Pista B — la firma del obligado es la puerta — **FIJADO**
Pista B no cruza su puerta v1.0 sin:

- [ ] Certificación RRSIF externa completada (auditoría de tercero de §7 + FB0).
- [ ] **Declaración responsable del obligado primero (tu S.L.):** acta datada y notarizada (o firmada por abogado asistido) afirmando que el motor conforme es el de este dossier, código hash del commit FB3, responsable de la emisión (Iván). **(No es papelería: es un acto vinculante que expone a sanciones del 201 bis LGT si mientes.)**
- [ ] VR-D04-03 ✓ : obligado sintético completo (20 facturas, mix, bitácora verificable).
- [ ] Bitácora SIF del obligado primero con ≥ 1 factura real emitida y cobrada (o ≥ 5 sintéticas en VR-03).
- [ ] Panel de partner funcional (lectura de estado por obligado).

### §16.3 Falsación — FIJADO
1. Liquidación de Pista A no reproducible (recomputación ≠ original) → rediseño de lógica antes de vender.
2. VR-03 falla dos veces por la misma causa (ej. encadenamiento roto) → Pista B vuelve a dossier (no proceder a certificación).
3. Motor SIF rechazado por auditoría externa (incumplimiento de Orden) → corregir before any sale.
4. Obligado primero (S.L.) rechaza la declaración responsable (miedo legal legítimo) → reconsiderar toda la Pista B.

---

## ANEXO A — ESQUEMAS DE PAYLOAD `finanzas.*` v1

- **A.1 `liquidacion.calculada`**: `{periodo: AAAA-MM, tenant_id, pedidos[{pedido_id, via, importe_bruto, costes_directos, beneficio_neto, comision}], total_comision, hash_pedidos, veredicto_recalculable, versionado_anexo}`
- **A.2 `liquidacion.aprobada`**: `{liquidacion_id, aprobacion_ref (D00), estado: APROBADA}`
- **A.3 `factura.emitida` (Pista A)**: `{numero_factura, fecha, nif_destinatario, importe_total, numero_liquidacion_ref, pdf_url, canal: EMAIL}`
- **A.4 `factura.emitida` (Pista B)**: `{numero_factura, fecha, nif_obligado, nif_destinatario, importe_total, numero_rfa_ref, rfa_canonico_hash, huella_esta_factura, huella_anterior, qr_url, estado: EMITIDA}`
- **A.5 `remision.enviada`**: `{rfa_ref, ts_envio, numero_intento}`
- **A.6 `remision.aceptada/rechazada`**: `{rfa_ref, codigo_respuesta_aeat, acta_respuesta_json, sello_temporal?}`
- **A.7 `sif.evento_registrado`**: `{rfa_ref, huella_esta, huella_anterior, ts_huella, acta_integridad}`
- **A.8 `cobro.registrado`**: `{factura_ref, medio_pago, importe, fecha_cobro, estado: COBRADO|RECHAZADO}`
- **A.9 `cobro.conciliado`**: `{cobro_ref, factura_ref, tolerancia_aplicada}`
- **A.10 `caja.informe`**: `{periodo, tenant_id, saldo_inicial, entradas, salidas, saldo_final, aging[{factura, dias_vencida}]}`
- **A.11 `factura.anulada`**: `{factura_ref, fecha_anulacion, motivo, huella_anulacion (nueva entrada encadenada)}`

---

## ANEXO B — CROSSWALK RRSIF → SECCIONES DE ESTE DOSSIER

(Referencia rápida para auditoría: cada artículo de la Orden y el RD 1007/2023 cita las secciones donde se implementa.)

| Artículo (Orden/RD) | Sección D04 |
|---|---|
| Art. 3 (Validación NIF) | §7 test 1, §3.2 |
| Art. 4–6 (RFA conforme) | §4.2, §3.3, §7 test 2 |
| Art. 7 (Encadenamiento) | §4.4, §3.4, §13.4 |
| Art. 8 (Remisión inmediata) | §3.5, §6 (automático), §7 test 4 |
| Art. 9 (Respuesta AEAT) | §3.5, §7 test 5 |
| Art. 10 (Sello temporal) | §3.5, §4.2 |
| Art. 11 (Bitácora íntegra) | §4.2, §4.4, §8.1, §13.4 |
| Art. 12 (QR tributario) | §3.6, §7 test 9 |
| Art. 13 (Leyenda) | §7 test 10, §3.6 |
| RD 1007 (Borrado imposible) | §4.3, §13.7 (constructor) |

---

*Fin de KAIZEN-D04 v1.0. Emitido el 2026-07-08 con la resolución un-motor-dos-caras. Pista A (Liquidación) empieza en FA0; Pista B (Motor SIF) empieza en FB0. Dependencia de arranque: D00-B1 ✓. Reloj externo real: obligados Sociedades desde 01-01-2027. Reloj del motor: quien lo fabrica; tu S.L. es el primer obligado; por eso la puerta B es "firma o no firma" — una responsabilidad legal incómoda que no se puede delegar en tests. Siguiente en la serie: D02 (Brand), si hay capacidad de paralelo, o D03 (Atención al Cliente) si la cartera expresa demanda. Por reloj de mercado, D04 es el dossier que más presión de fecha tiene: la ley manda y el calendario es implacable.*
