# MOC — Arquitectura y decisiones

Índice del diseño del sistema. Ver también [[MOC_INFORMES]] y [[MOC_OPERACION]].

## Estado y plan vigentes (leer antes que los dossieres)

- [[ESTADO_REAL]] — el mapa del territorio: estado VERIFICADO del sistema (2026-07-20); ante divergencia con un dossier, manda esto
- [[ROADMAP_PRODUCCION]] — plan operativo a produccion y primera ejecucion real (Laboratorio), fechas duras 02-ago y 30-ago
- [[MAPA_VIVO]] — registro obligatorio de cada accion (hook pre-commit fail-closed; cronologia completa de commits y sesiones)
- [[CADENAS]] — registro de las 4 cadenas SHA-256 del sistema (regla: nueva cadena = nueva fila + verificador propio)

## Documentos canónicos

- [[KAIZEN_CORRECCIONES_AGENTE_v1_0]] — vinculante del agente; solo Iván lo modifica
- [[KAIZEN_ARQUITECTURA_CANONICA_v1_0]] — **sustituido por D00 como especificación de sustrato** (D00 §11.1); se conserva como histórico

## Serie D — dossieres departamentales (2026-07-08/09)

Ver [[SERIE_D]] para precedencia, hueco D03 y conflictos abiertos.

- [[KAIZEN_D00_SUSTRATO_Y_CONTRATOS_v1_0]] — sustrato y contratos comunes
- [[KAIZEN_D01_COMERCIAL_v1_0]] — cubo Comercial (plantilla de la serie)
- [[KAIZEN_D02_BRAND_v1_0]] — cubo Brand
- [[KAIZEN_D04_FINANZAS_VERIFACTU_v1_0]] — cubo Finanzas / motor SIF Verifactu
- [[KAIZEN_D05_OPERACIONES_v1_0]] — cubo Operaciones
- [[KAIZEN_D06_MARKETING_v1_0]] — cubo Marketing
- [[KAIZEN_D07_INTELIGENCIA_v1_0]] — cubo Inteligencia de Mercado
- [[KAIZEN_D08_CUMPLIMIENTO_v1_0]] — cubo Cumplimiento (Anexo B = placeholder, D09 GL-05)
- [[KAIZEN_D09_GUARDARRAILES_CONSTRUCCION_v1_0]] — erratas, resoluciones y disciplina del constructor (gana a D00–D08 v1.0)
- [[KAIZEN_D10_CENTRO_DE_MANDO_v0_2]] — Centro de Mando del operador (CANON: La Mañana + Sala de maquinas, mecha 60s, PARAR TODO; construccion pendiente de orden P0)
- [[KAIZEN_D10_CENTRO_DE_MANDO_v0_1_PROPUESTA]] — version inicial, superada por v0.2 (historico)

## Diseño técnico (docs/)

- [[ARQUITECTURA]]
- [[CASOS_DE_USO]]
- [[COMO_CREAR_UN_DEPARTAMENTO]]
- [[MODELO_DATOS_LEAD]]
- [[PLAN_VOZ_BIDIRECCIONAL]]
- [[PLAN_VOZ_CONVERSACIONAL]]
- [[SISTEMA_NERVIOSO]]
- [[SISTEMA_NERVIOSO_M8]]
- [[VALIDACION_V1_VOZ_BIDIRECCIONAL]]

## Sustrato y roles

- [[brand_strategist]]
- [[legal_checker]]
- [[risk_assessor]]
