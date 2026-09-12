# Registro de cadenas de sellado (SHA-256) — Kaizen

Este repositorio tiene **cuatro cadenas de hash independientes**, cada una con su
propio dueño, propósito y verificador. Ninguna reimplementa a otra: existen
porque cubren dominios distintos. Regla vigente:

> **Nueva cadena de sellado = nueva fila en esta tabla + verificador propio.**
> **Duplicar la canonicalización de una cadena ya existente está prohibido** — si
> otro subsistema necesita encadenar eventos con las mismas garantías, importa el
> módulo dueño; no reescribe `_canon()`/`_sha()` por su cuenta.

| # | Cadena | Módulo dueño | Verificador independiente | Dominio / propósito | Génesis |
|---|---|---|---|---|---|
| 1 | Bitácora canónica D00 §3 | `core/rue.py` (`Bitacora`) | `_workspace/verificar_cadena_real.py` (ad hoc, reimplementa sin importar el módulo) | Eventos por tenant: comercial, plataforma, brand, ops, finanzas, marketing, inteligencia, cumplimiento. La que lee `panel_mando` / la Sala. | `sha256(tenant + "\|\|" + fecha_alta)` — `fecha_alta` real por tenant en `empresas/tenants.json` |
| 2 | Bus/gates/comité (legado) | `sustrato/hashchain.py` | — (pendiente; no se le conoce verificador independiente hoy) | Subsistema `sustrato/` + `cubos/` + `mesa_jefe.py` + `panel/director.py` (arquitectura pre-D10). **Vivo**: `kaizen.py` lo usa vía `sustrato.cli`. | `GENESIS = "0"*64` fijo, sin variar por tenant |
| 3 | Veredictos OpenGravity | `core/opengravity/sealing.py` (`HashChain`, `hash_canonico`) | tests en `tests/test_opengravity_*.py` | Cadena de veredictos del comité QA/LLM, un head por empresa (`opengravity_chain.json`). | `GENESIS = "0"*64`, head persistido por empresa |
| 4 | VeriFactu (FB1/FB3) | `departments/finanzas/cubo_serie_d.py` | recómputo manual en `pruebas_produccion/tanda2_f3_q1_q2.py` (D04 §13.4) | Cadena de facturación **por NIF del obligado**, formato exigido por AEAT (Ley VeriFactu) — no es sustituible por una cadena por tenant. | `sha256("SIF\|\|" + NIF)` |

## Divergencia abierta (DECISIÓN REQUERIDA a Iván)

`sustrato/hashchain.py` (cadena #2) sigue teniendo consumidores reales en
producción, confirmado por grep el 2026-07-12:

- `cubos/base.py`, `cubos/comercial/adaptador.py`, `cubos/comercial/ritual_manana.py`
- `mesa_jefe.py`, `panel/director.py` (panel pre-D10)
- `kaizen.py:1573` vía `sustrato.cli` — el CLI que lanzan `Kaizen.cmd` / `Kaizen-REAL.cmd`
- dentro de `sustrato/`: `bus.py`, `comite.py`, `gates.py`

No se archiva. Queda pendiente decidir si `sustrato/` + `cubos/` + `panel/` es
legado en retirada (sustituido por `core/` + `departments/` + `panel_mando/`) o
subsistema activo en paralelo por diseño. Mientras no se decida, ambas cadenas
coexisten legítimamente — ninguna corrompe a la otra, cada una opera en su
propio namespace de tenant/knowledge.

## Historial

- 2026-07-12: primer registro, tras el diagnóstico de la falsa ruptura del sello
  en la Sala de laboratorio (causa real: `fecha_alta` por defecto en
  `panel_mando/app.py`, no corrupción de cadena — ver `INFORME_CIERRE_P0_SALA.md`).
