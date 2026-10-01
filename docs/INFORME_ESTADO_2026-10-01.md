# Informe de estado — 2026-10-01

Rama: `claude/clever-wozniak-p7mins`. Todo lo hecho está **commiteado y subido** (nada queda sin guardar en la nube).
Importante: **tu PC no lo tiene hasta que hagas `git pull` de esta rama (o aceptes el PR) y reinicies el panel.** Por eso no ves «Nichos».

## VERIFICADO (con prueba ejecutada, modelo y búsqueda simulados)
| Qué | Evidencia |
|---|---|
| Niveles de autonomía; ALTA bloqueada; bajan solos con 3 denegadas seguidas o sello roto; solo el operador sube | Suite 1778 pasadas / 8 omitidas / 0 fallos (código de salida 0) |
| Estados de apuesta K1, dosier de 7 campos, evidencia VERIFICADA/RECORDADA/SUPUESTO, vetos, control de novedad, cuotas | Tests + pruebas de mutación (se rompe a propósito y el test falla) |
| Tanda con frenos (PARAR TODO, tope de horas, nivel CERO, atasco, tope del proveedor) e informe | Tests; PARAR TODO pulsado en plena tanda la detiene |
| Una sola búsqueda a la vez, reserva con sello, descarte de reservas huérfanas | Tests (incluye 12 hilos simultáneos) |
| El director de Inteligencia: `ver_nichos`, `leer_nicho` (datos reales), `buscar_nichos` solo con tu SÍ; tarjeta ANULADA muestra el motivo | Tests |
| Pestaña «Nichos» en el Mundo: buscar, leer dosier, elegir→prueba→medir→podar, texto hostil mostrado literal, sello íntegro | Navegador real contra el backend real: e2e 21 de 21 |
| Revisión independiente (2 rondas): hallazgos verificados y corregidos | Ver `PLAN_IMPLEMENTACION_APUESTAS_v0.md` |

## POR VERIFICAR (no probado; no lo afirmo)
1. **Modelos reales de WebLLM**: nunca se ha hablado con uno de verdad. Calidad de las ideas: desconocida.
2. **Búsqueda web real (`ddgs`)**: desde la nube no hay salida a DuckDuckGo. Sin ella el sistema rebaja la evidencia a RECORDADA, nunca inventa fuentes.
3. **Ejecución en Windows** (`NICHOS.cmd`, `MUNDO.cmd`): no se ha ejecutado en Windows.
4. **Umbrales sin calibrar**: similitud 0,5, cuotas, 10 lentes, 3 lentes por ciclo.
5. **Puerta externa de WebLLM**: hay que activarla en tu PC y poner el token en `.env` (nunca en un chat).
6. **Aspecto visual de la pestaña** en tu pantalla: probado por comportamiento, no revisado a ojo por ti.
7. Si reinicias el panel a mitad de búsqueda, esa búsqueda se pierde (el botón no queda bloqueado).
8. Chat del director dentro del Mundo: no existe; «Hablar con el director» abre el chat en otra pestaña.
9. Tareas antiguas abiertas del Mundo (verificación visual 3.4, retirar el modo demo 5.3): siguen pendientes.

## Cómo verlo en tu PC
1. En la carpeta de Kaizen: `git fetch origin` y `git checkout claude/clever-wozniak-p7mins` y `git pull`.
2. Cierra el panel y el Mundo y ábrelos de nuevo (`MUNDO.cmd`). En el navegador, recarga forzada (Ctrl+F5).
3. Pestaña **Nichos** (a la derecha de «Registro»). Sin token de WebLLM, el botón te dirá qué falta; no inventa nada.

## Prompt para Claude Code (pégalo tal cual en Claude Code abierto en la carpeta de Kaizen)
```
Estás en la carpeta del repositorio Kaizen en mi PC (Windows). Quiero ver en el Mundo la pestaña "Nichos".
1. Ejecuta `git status`. Si hay cambios sin guardar, NO los borres ni los descartes: dímelos y espera.
2. Si está limpio: `git fetch origin`, `git checkout claude/clever-wozniak-p7mins`, `git pull`.
3. Lee docs/INFORME_ESTADO_2026-10-01.md y docs/APUESTAS_Y_DOSIER_v0.md §13.
4. Instala dependencias si faltan (`pip install -r requirements.txt`, y `ddgs`) y ejecuta `python -m pytest -q`; dime el resultado real y el código de salida.
5. Arranca el Mundo con lanzadores\MUNDO.cmd y confirma que la pestaña "Nichos" aparece. Si no aparece, averigua por qué (¿otro proceso viejo ocupando el puerto 8600? ¿caché?) sin tocar nada más.
6. Ayúdame a activar la puerta externa de WebLLM: en la carpeta de WebLLM `python -m scripts.external_api_admin enable`. El token que imprima va SOLO al fichero .env como KAIZEN_WEBLLM_TOKEN=...; no lo escribas en el chat ni en ningún commit.
7. Prueba una búsqueda real desde el botón "Buscar nichos" con 1 vuelta. Cuéntame honestamente qué funcionó y qué falló (modelo real, búsqueda real ddgs, calidad de los dosieres). No inventes resultados ni ocultes errores.
No hagas push ni cambies de rama sin pedírmelo. Responde en español sencillo, sin jerga.
```
