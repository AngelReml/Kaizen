# ESPECIFICACIÓN R-TENANT — sacar a los clientes reales del producto

**Emitida:** 2026-08-04 · **Para:** Claude Code (on-machine) · **Autoriza:** Iván
**Decisiones tomadas por el operador en esta sesión:**
- Historia de git → **opción A, raya en la arena** (el repo actual con historia pasa a savepoint/archivo offline; el laboratorio arranca repo nuevo desde el árbol limpio).
- Ejecución → **Claude Code ejecuta, el agente Cowork especifica y verifica.**

---

## §0. LA REGLA (esto es lo que se está construyendo)

> **R-TENANT: el árbol del producto sabe QUÉ ES un tenant, jamás QUÉ tenant.**
>
> Prohibido en código, manifests, tests y documentación del producto: nombre de
> cliente real como valor por defecto, como `cliente_id` de manifest, como DEFAULT
> de DDL, o como texto literal. Los datos de cliente viven FUERA del árbol de git y
> entran por parámetro. Mezclarlos no es deuda técnica: es **brecha de seguridad**.

Precedente que justifica la regla (no es hipotética): `departments/comercial/brand_guardian.py:185-186`
documenta que un email de Segundo Tenant se evaluaba con la marca de Laboratorio. La fuga
entre tenants ya ocurrió una vez y se parcheó en un sitio, no en el origen.

---

## §1. PROHIBICIONES DURANTE TODA LA OPERACIÓN

1. **`rm` jamás.** Todo desalojo es `mv`. Nada se borra: se destierra.
2. **El savepoint no se toca.** Ni se abre para "comprobar una cosa".
3. **Nada de remotos.** DR-01 reforzada por Iván el 2026-08-04: sin GitHub, ni
   público ni privado, ni equivalente. El respaldo es copia externa que se mueve y
   se actualiza.
4. **E1 en cada escritura:** verificar con `sha256` o relectura. Este montaje ha
   corrompido ficheros en silencio.
5. **R6 adaptado:** romper en rama es legítimo; el merge a principal, solo en verde.
6. Si el agente Cowork participa: **jamás ejecuta git** (E1-BIS — el bridge no puede
   borrar `.git/index.lock` y deja el repo bloqueado en Windows).

---

## §2. ORDEN OBLIGATORIO — y por qué este orden

**La regla que evita el segundo follón: los datos se van AL FINAL, no al principio.**

Con los datos todavía presentes, los **63 ficheros de test que nombran un cliente
real** (de 115 totales) son un mapa de precisión: cada rojo señala exactamente dónde
el producto dependía de un cliente. Si se borran primero, se refactoriza a ciegas y
es imposible distinguir "lo he roto yo" de "falta el fichero".

| Fase | Qué | Puerta para pasar a la siguiente |
|---|---|---|
| **F0** | Desarmar la trampa del índice | `git status` limpio de falsas deleciones |
| **F1** | Verificar que el savepoint restaura | acta de restauración escrita |
| **F2** | Parametrizar DÓNDE viven los datos | suite en verde, datos aún en su sitio |
| **F3** | Completar el tenant sintético | `laboratorio` equivalente funcional a `laboratorio` |
| **F4** | Invertir QUÉ tenant por defecto | suite verde con `laboratorio` por defecto |
| **F5** | Desalojar los datos reales | suite verde SIN datos de cliente en el árbol |
| **F6** | Raya en la arena (repo nuevo) | primer commit limpio + acta |

---

## §3. F0 — DESARMAR LA TRAMPA DEL ÍNDICE (primero, sin excepción)

**Diagnóstico:** el índice de git está desincronizado. `git status` muestra 17
ficheros de E0-E1 como *borrados en stage* (D11 v0.1 y v0.2, INFORME_BUZZ,
INFORME_DETERMINISMO, `cubos/comercial/aiact_email_variantes.md`,
`herramientas/generar_tenant_laboratorio.py`, `empresas/laboratorio/**` completo y
los 4 ficheros de tests nuevos), más 9 con blobs viejos.

**Verificado por sha256: HEAD == disco en todo lo muestreado. No hay pérdida.**
Causa: el commit `83bfb6b` se hizo desde el espejo `GIT_DIR=/tmp`; se sincronizaron
objetos y HEAD, pero no el `.git/index` del disco.

**Peligro:** ejecutar `COMMIT LOCAL.cmd` tal cual produce un commit que **borra
E0-E1 del árbol** (−2.230 líneas).

**Acción (desde Windows, no desde el bridge):**

```
git reset
git status
```

`git reset` (mixed, sin argumentos) reescribe el índice desde HEAD. **No toca ningún
fichero de trabajo.** Tras él solo deben quedar los cambios reales de worktree.

**Limpieza asociada:** borrar `_locks_apartados/` (locks huérfanos que dejó la
auditoría del bridge; desde Windows sí se pueden borrar).

---

## §4. F1 — VERIFICAR EL SAVEPOINT ANTES DE DESALOJAR NADA

Ahora mismo el savepoint es la **única copia de la historia con clientes dentro**.
Un savepoint que nunca se ha probado a restaurar es una esperanza, no un punto de
retorno (D11 §7).

1. Montar el disco externo, copiar el savepoint a una carpeta temporal distinta.
2. Ejecutar la suite ahí. Registrar la cifra.
3. Escribir acta de una línea con fecha, cifra y sha256 de un fichero testigo.

**Puerta:** si el savepoint no restaura, **la operación se detiene aquí** y el
problema pasa a ser el backup, no el refactor.

---

## §5. F2 — PARAMETRIZAR DÓNDE VIVEN LOS DATOS

**Buena noticia medida:** esto NO son 43 sitios. La ruta de datos se construye en
muy pocos puntos, y el patrón `base_dir` **ya existe** en el código:

```
core/argumentario.py:30,45,74,81,86   cargar_argumentario(company, base_dir=None)  → raiz = base_dir or _RAIZ_REPO
core/argumentario.py:35               raiz / "empresas" / company / "argumentario.json"
core/empresa.py:17,25-26              cargar_perfil_empresa(company, base_dir=None) → raiz / "empresas" / company / "perfil.json"
core/opengravity/department.py:70     _RAIZ / "empresas" / company / "opengravity.json"
core/lead_schema.py:119               empresas/<empresa>/politica_reintentos.json
core/tenants.py:20                    RUTA_REGISTRO = ... / "empresas" / "tenants.json"   ← constante de módulo, es la que peor está
```

**Cambio pedido:** un único punto de verdad para la raíz de datos.

1. Crear `core/rutas.py` con:
   ```python
   def raiz_datos() -> Path:
       """Raíz de los datos de tenant. FUERA del árbol de git por defecto."""
       # env KAIZEN_DATOS > valor por defecto (directorio hermano del repo)
   ```
2. Sustituir en los puntos de arriba `base_dir or _RAIZ_REPO` por `base_dir or raiz_datos()`.
3. `core/tenants.py:20`: `RUTA_REGISTRO` deja de ser constante de módulo y pasa a
   función/propiedad que consulta `raiz_datos()`. **Es el peor de los seis** porque
   se evalúa en import y hace imposible testear con otra raíz.

**Puerta F2:** suite verde con los datos **todavía en `empresas/`** (apuntando
`KAIZEN_DATOS` a la ruta actual). Si aquí hay rojos, son del refactor, no de la falta
de datos — arreglarlos antes de seguir.

---

## §6. F3 — COMPLETAR EL TENANT SINTÉTICO

`empresas/laboratorio/` ya existe (E0.2) y es **casi** un drop-in de `laboratorio`:

| | laboratorio | laboratorio |
|---|---|---|
| `perfil.json` | ✔ (8 claves) | ✔ (mismas 8 + `sintetico`) |
| `politica_reintentos.json` | ✔ | ✔ |
| `brand/` (5 ficheros) | ✔ | ✔ |
| **`argumentario.json`** | ✔ **6.268 bytes** | ✘ **NO EXISTE** |

**Esta es la pieza que falta y es la causa de los 16 rojos que aparecen al excluir
los datos de cliente por R1.**

**Cambio pedido:** que `herramientas/generar_tenant_laboratorio.py` emita también un
`argumentario.json` sintético con **el mismo esquema** que el de laboratorio (leer el
esquema, no el contenido; el contenido se inventa). Determinista, como el resto del
generador.

**Puerta F3:** ejecutar el generador y comprobar que `laboratorio` tiene los mismos
ficheros que `laboratorio`, con las mismas claves de nivel superior.

---

## §7. F4 — INVERTIR QUÉ TENANT POR DEFECTO

Tres bloques. **Ninguno mueve datos todavía.**

### 7.1 Los 43 valores por defecto `= "laboratorio"`

Criterio: **parámetro obligatorio donde el llamador siempre lo sabe**; `"laboratorio"`
solo donde un defecto es imprescindible (CLI interactiva).

```
core/compromisos.py:99                                   core/knowledge_migration.py:49
sustrato/cli.py:61, 308                                  sustrato/propuestas.py:54, 70, 102
sustrato/registro.py:126, 228, 269
departments/brand/asset_manager.py:13                    departments/brand/brand_guardian.py:38
departments/brand/brand_strategist.py:16                 departments/brand/director.py:30
departments/brand/voice_auditor.py:37
departments/comercial/brand_guardian.py:48, 223, 278     departments/comercial/dashboard_director.py:39
departments/comercial/director.py:47                     departments/comercial/email_composer.py:35
departments/comercial/icp.py:40                          departments/comercial/sdr/compromiso.py:70
departments/comercial/sdr/voz_conversacional/analisis_calidad.py:142
departments/comercial/sdr/voz_conversacional/post_call.py:42
departments/comercial/sdr/voz_play/composer.py:88, 128
cubos/comercial/adaptador.py:48, 113                     cubos/comercial/ritual_manana.py:39, 99
agentes.py:130, 204, 358, 385, 492, 543                  diario_ops.py:15 (DEFAULT_COMPANY)
kaizen.py:291, 1344, 1376, 1421, 1468
```

### 7.2 El DDL del sustrato

`sustrato/propuestas.py:22` → `cliente_id TEXT NOT NULL DEFAULT 'laboratorio'`
**Quitar el DEFAULT.** La columna sigue siendo `NOT NULL`: quien inserta declara el
tenant. *(Nota: ESTADO_REAL da R-18 por cerrado en F2 del 2026-07-20 — se cerró en el
otro árbol. Este sigue vivo. Síntoma de los tres árboles.)*

### 7.3 Los 10 manifests de cubo

Los diez llevan `"cliente_id": "laboratorio"` en la línea 4 — incluidos `legal` y `rrhh`,
que jamás han tocado a ese cliente. Un manifest de **producto** no lleva cliente.

```
cubos/{brand,comercial,customer_success,finanzas,inteligencia,legal,marketing,ops,qa,rrhh}/manifest.json:4
```

**Antes de quitarlo:** comprobar si `config.validar_manifest()` (invocado en
`cubos/base.py:34`) exige la clave en su esquema. Búsqueda rápida: nadie lee
`cliente_id` en `cubos/base.py`, `departments/cubo.py` ni `departments/catalogo.py`
— apunta a metadato muerto. Si el validador la exige, quitarla también del esquema.

### 7.4 Los literales de marca en el producto

- `kaizen.py:2, 30, 32, 85` — docstring, BANNER y SESSION_SYSTEM presentan la CLI como
  "Asistente operativo para Repostería Laboratorio". El producto se llama Kaizen.
- `sustrato/cli.py:270` — **cuerpo de email de venta de Laboratorio incrustado dentro del
  sustrato**. Sale de ahí: es contenido de tenant, no de plataforma.
- `core/compromisos.py:32`, `core/rue.py:68`, `departments/brand/config.py:6`,
  `departments/comercial/account_executive.py:6`, `departments/comercial/brand_guardian.py:1,22,151`
  — comentarios y prompts con el cliente dentro.

**Puerta F4:** suite verde con `laboratorio` como tenant por defecto y los datos de
cliente **todavía presentes**. Los 63 ficheros de test son el mapa: cada rojo es un
sitio donde el producto dependía del cliente. Ninguno se silencia; se arregla o se
apunta al tenant sintético.

---

## §8. F5 — DESALOJAR LOS DATOS REALES (solo con F4 en verde)

`mv`, nunca `rm`. Destino: `KAIZEN_DATOS/` (directorio hermano, fuera del árbol de
git), con su propio backup externo.

```
empresas/laboratorio/            empresas/segundo_tenant/       empresas/tenants.json  (3 razones sociales reales)
diario/laboratorio/              diario/segundo_tenant/         diario/verigest/
data/                        state/                        bitacora/
docs/ARGUMENTARIO_LABORATORIO.md                               departments/comercial/datos/icp_laboratorio.json
Revision_Llamada_60.{md,csv,docx}   (revisión de llamada real)
CONTEXTO_TOTAL.txt                  (1,1 MB — contiene terceros por declaración propia)
_workspace/cadena_laboratorio.jsonl     _workspace/cualificados_sin_enriquecer.json
```

**Se queda en el árbol:** `empresas/laboratorio/` (sintético) y
`CONTEXTO_TOTAL_SIN_TERCEROS.txt` (regenerable).

**`.gitignore` blindado:** `empresas/` salvo `laboratorio/`, `diario/`, `data/`,
`state/`, `bitacora/`.

**El centinela pre-commit gana un check nuevo:** ningún nombre de cliente real en el
árbol del producto. Ya existe el hook fail-closed en `.git/hooks/pre-commit`; esto es
una regla más, y es la que hace que R-TENANT no dependa de la memoria de nadie.

**Puerta F5:** suite verde **sin datos de cliente en el árbol**. Ésta es la prueba de
que Kaizen es un producto y no la herramienta de un cliente.

---

## §9. F6 — LA RAYA EN LA ARENA

Decisión del operador: **no se reescribe la historia.** `filter-repo` rompería
`MAPA_VIVO` (registra por hash y su verificador es fail-closed), las referencias de
`CADENAS.md` y los sha256 congelados de la serie D.

**Procedimiento:**

1. El repo actual, con sus ~119 commits y los datos dentro, **pasa a ser
   savepoint/archivo offline**. No se publica, no se toca, no sale de la máquina.
   Verificado hoy: `.git/config` no tiene sección `[remote]` y no existe
   `.git/refs/remotes/` — la historia no ha salido por ahí.
2. El laboratorio arranca **repo nuevo** (`git init`) sobre el árbol ya limpio.
3. `MAPA_VIVO.md` se cierra con un acta: "mapa v1 cerrado en `83bfb6b`; la historia
   con datos de cliente queda en el archivo offline; mapa v2 arranca limpio por
   R-TENANT". La cronología en prosa se conserva; los hashes viejos apuntan al
   archivo.
4. Primer commit del repo nuevo: el árbol limpio, con la suite verde registrada como
   nueva línea base.

---

## §10. DEUDA DE WIKI QUE HAY QUE CERRAR EN EL MISMO ACTO

Por su propia regla (`ESTADO_REAL` §8, `_CONTEXTO_IA` §2), un estado con fecha vieja
es contexto envenenado:

- `MAPA_VIVO.md` — última sesión registrada 2026-07-20; declara "68 commits, 0 huecos"
  cuando HEAD es del 3-ago. **El hook del mapa es fail-closed: puede abortar el
  próximo commit legítimo.** Regenerar con `MAPA VIVO.cmd`.
- `ESTADO_REAL.md` y `LINEA_BASE.md` — siguen en 857/7; la suite real en la máquina de
  Iván es **939/0/7**.
- `ESTADO_REAL` §4 debe recoger que D02 Brand deja de estar clavado a un cliente.

---

## §11. LO QUE SIGUE PENDIENTE DE IVÁN

1. ~~**¿Hubo push real a GitHub, o solo el remoto configurado?**~~ **RESUELTO
   2026-08-04.** Sí hubo push: 22 pushes a `github.com/AngelReml/Kaizen` entre el
   26 y el 28 de mayo de 2026, repositorio **PRIVADO**, borrado a mano después.
   Salieron el argumentario, el diario y el ICP del tenant, con 3 correos y 6
   teléfonos de terceros. **NO salieron** `.env` (cero secretos verificados con el
   propio centinela sobre el árbol publicado) ni `state/` (los 463 leads nunca
   dejaron la máquina). Al ser privado, no hay archivado por terceros y no consta
   acceso no autorizado: queda como **riesgo interno**, no como brecha.
   Ver `INFORME_EXPOSICION_GIT_2026-08-04.md`. El remoto residual que aún tenía
   `D:\angel\KAIZEN` se ha eliminado.
2. Texto AI Act para email (sigue cerrando el candado del canal).
3. R-REV-2: cifra mensual del laboratorio (sin cifra, 0 €).
4. DR-06: cifras de mandato de los tenants (hoy PROVISIONALES).

---

*Especificación emitida por el agente Cowork tras auditoría de solo lectura del
2026-08-04. Gasto: 0,00 €. Toda cifra de este documento está medida sobre el árbol
real, no estimada. Si algo aquí contradice al código, gana el código.*
