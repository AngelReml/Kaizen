# MAPA DE EVENTOS DEL MUNDO — generado 2026-10-01

**Tipo:** estado (capa 4, se regenera; no editar a mano) · **Fuente:** `eventos.json` y `panel_mando/mundo.py` · **Generador:** `python herramientas/mapa_eventos_mundo.py`

Regla del juego: **lo que se ve es real**. El Mundo no dibuja nada que no venga de un evento sellado o de la foto del backend (`docs/CONTRATO_MUNDO.md`). Todo evento con cubo hace lo mismo: el director de ese cubo dice la frase (la misma que el panel) y una gota de tinta viaja al Registro, que la sella y hace crecer el bambú. Un evento sin cubo solo hace la gota. Los eventos del bus del sustrato (`kaizen.<cubo>.…`) y del chat de la Colmena entran por el mismo canal (ver el contrato).

## 1. Familias y cubo

| Familia (prefijo) | Cubo | Tipos | Gesto |
|---|---|---|---|
| `plataforma` | — (plataforma: sin director) | 24 | gota al Registro |
| `comercial` | comercial | 12 | el director de ese cubo habla + gota al Registro |
| `brand` | brand | 4 | el director de ese cubo habla + gota al Registro |
| `finanzas` | finanzas | 12 | el director de ese cubo habla + gota al Registro |
| `operacion` | ops | 12 | el director de ese cubo habla + gota al Registro |
| `marketing` | marketing | 11 | el director de ese cubo habla + gota al Registro |
| `inteligencia` | inteligencia | 18 | el director de ese cubo habla + gota al Registro |
| `cumplimiento` | legal | 12 | el director de ese cubo habla + gota al Registro |

Total: 105 tipos en 8 familias.

## 2. Gestos propios (además del genérico)

| Tipo | Gesto |
|---|---|
| `plataforma.aprobacion.solicitada` | aparece la tarjeta en la ventanilla |
| `plataforma.aprobacion.concedida` | la ventanilla se refresca (la tarjeta pasa a mecha o se ejecuta) |
| `plataforma.aprobacion.denegada` | la ventanilla se refresca (la tarjeta desaparece) |
| `plataforma.aprobacion.revocada` | la ventanilla se refresca (deshecho a tiempo) |
| `plataforma.aprobacion.caducada` | la ventanilla se refresca (caducada) |
| `plataforma.aprobacion.en_manos` | la ventanilla se refresca (la tarjeta pasa a tus manos) |
| `plataforma.aprobacion.hecha` | la ventanilla se refresca (confirmada como hecha) |
| `plataforma.aprobacion.no_hecha` | la ventanilla se refresca (anulada por ti) |
| `plataforma.panico.activado` | el mundo se congela y dice TODO PARADO |
| `plataforma.panico.desactivado` | el mundo se reanuda |
| `plataforma.coste.techo_alcanzado` | modo ahorro: el gasto se marca y los directores lo dicen |
| `comercial.pedido.atribuido` | fuegos artificiales (hanabi) al caer la noche |
| `finanzas.cobro.registrado` | fuegos artificiales (hanabi) al caer la noche |

## 3. Lo que este documento NO afirma

- No dice que cada tipo tenga hoy un productor real en el backend: **no se ha auditado tipo a tipo**. Un tipo sin productor simplemente nunca dispara nada, y el juego no lo simula.
- Familias sin prefijo en el mapa (`CUBO_POR_PREFIJO_RUE`): ninguna.
