# Autonomía — v0

Estado: **decidido por Ángel** (2026-10-01): F1 G1 H1 I1 J1. Plan de ejecución: `docs/PLAN_IMPLEMENTACION_AUTONOMIA_v0.md`.
Marco: `docs/SUELO_Y_VOCABULARIO_v0.md` (firmado). Principio: exploración libre, acción por puertas.

## 1. Clases de acción (sin cambios)

| Clase | Qué es | Quién la ejecuta |
|---|---|---|
| REVERSIBLE | Interna y deshacible (borrador, informe, prueba local). | El agente, si su nivel lo permite. |
| IRREVERSIBLE-INTERNA | Afecta a sistemas compartidos. | Tarjeta que aprueba Ángel. |
| IRREVERSIBLE-EXTERNA | Sale del sistema (publicar, enviar, pagar, contratar). | **Ángel** (decisión C1): el agente prepara, Ángel ejecuta y confirma. |

Lectura es libre en todos los niveles.

## 2. Niveles (F1)

| Nivel | Qué puede hacer | Estado real hoy |
|---|---|---|
| CERO | Solo lee y analiza. No propone tarjetas. | Activo. Calidad y RRHH. |
| BAJA | Escribe borradores internos reversibles y propone tarjetas. | Activo. El resto de cubos, e Inteligencia desde J1. |
| MEDIA | (Reservado) correr ciclos propios dentro de un tope. | **Sin mecanismo.** En la Colmena se comporta como BAJA. Nadie lo tiene. |
| ALTA | (Reservado) aprobaciones automáticas de categorías pequeñas ya firmadas. | **Bloqueado esta temporada** en el código nuevo. |

Nota de exactitud: en el camino legado `sustrato/gates` (Comercial), ALTA es el nivel mínimo para email real, contacto
saliente y compromiso ante cliente, siempre con comité. Ahí el operador todavía puede fijarlo. Es un límite abierto,
no resuelto: se documenta aquí y se decide aparte.

## 3. Quién sube y baja el nivel (G1)

- **Subir:** solo Ángel, con la ficha del cubo delante (acierto, ROI). Ningún agente puede relajar su propio nivel.
- **Bajar automáticamente un nivel, y queda sellado en la bitácora:**
  1. Tres tarjetas seguidas del mismo cubo denegadas por Ángel → baja ese cubo.
  2. Sello de la bitácora roto → bajan todos los cubos de esa empresa.
- **Tope de gasto superado:** no se duplica. Ya lo gestiona `core/techos.py` con su escalera de degradación. El monedero de
  50 € todavía no existe y su control llegará con la capa de financiación.
- Un incidente baja una sola vez. Tras restaurar el nivel, hace falta un incidente nuevo para volver a bajar.
- Nunca se baja de CERO.

## 4. Ciclos de exploración (H1)

El ciclo 0 lo lanza Ángel a mano. Aún **no implementado**: necesita el formato de dosier y los estados de una apuesta
(capas siguientes). Cuando haya datos de coste y calidad, Ángel decide si pasa a semanal con un tope de cómputo.

## 5. Cómo se ejecuta lo externo (I1)

Sin clase nueva. Toda IRREVERSIBLE-EXTERNA sigue: tarjeta → lista de pasos → Ángel ejecuta → marca "hecho" con evidencia →
sellado. En la cola esto son los pasos `APROBADA → EN_MANOS → HECHA`. Pantalla y lista de pasos quedan para cuando exista
el formato de dosier.

## 6. Inteligencia (J1)

Inteligencia pasa de CERO a BAJA para poder escribir los dosieres del ciclo 0. Calidad y RRHH siguen en CERO.

## 7. Lo que no depende del nivel

Los vetos del Suelo valen siempre: nada de mentiras, spam, reseñas falsas ni dinero político.

## 8. Límites conocidos

- La autonomía vive en dos sitios (`core/aprobaciones` y `sustrato/gates`) con los niveles definidos en cinco módulos.
  No se unifican ahora.
- El nivel que usa la Colmena era solo el valor por defecto del manifest; el nivel efectivo por empresa y cubo se crea en F3.
- Todo lo nuevo está probado en Linux; no verificado en Windows.
