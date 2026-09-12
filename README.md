# Kaizen

Sistema de agentes que automatiza tareas de un departamento comercial B2B
(sector HORECA): busca candidatos, los cualifica contra un perfil (ICP),
redacta el primer contacto y hace seguimiento. Multi-tenant: la
configuración de cada cliente vive en `empresas/<tenant>/` y `diario/<tenant>/`,
fuera del código. El repositorio no contiene datos de ningún cliente real —
solo un tenant sintético, `laboratorio`, con datos ficticios, para poder
instalar y probar el sistema sin depender de datos de terceros.

Antes de cualquier envío real (email, llamada) se exige de forma explícita:
una variable de entorno de activación, un token de aprobación generado por
`departments/comercial/cola_aprobacion.py`, y un flag en el comando. Si falta
cualquiera de los tres, el sistema no envía nada. Esto está en el código
(`core/ejecutor.py`, `cola_aprobacion.py`), no es una convención.

## Arrancar desde cero

Requiere Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
```

Edita `.env` y rellena al menos `ANTHROPIC_API_KEY` (obligatoria para las
funciones que usan LLM). El resto de variables de `.env.example` son
opcionales — el sistema arranca sin ellas y cada función que las necesite
lo indica al usarla.

```bash
python kaizen.py --help
```

Sin ningún backend adicional instalado (Redis/Neo4j/Postgres), el sistema
corre en memoria. `docker-compose.yml` levanta esos tres backends si se
quieren probar (`docker compose up -d`).

Lanzadores de doble clic (Windows, sin terminal, en `lanzadores/`):
`lanzadores\Kaizen.cmd` (panel en modo simulación, sin coste),
`lanzadores\Kaizen-REAL.cmd` (panel en modo real, con coste),
`lanzadores\CENTRO DE MANDO.cmd`, `lanzadores\COLMENA.cmd`,
`lanzadores\MESA DEL JEFE.cmd`,
`lanzadores\COMMIT LOCAL.cmd` (ejecuta la suite y comitea si pasa),
`lanzadores\INSTALACION LIMPIA.cmd` (crea un entorno virtual nuevo, instala
y corre la suite — verificación local de instalación limpia). Detalle de
cómo crear el acceso directo de escritorio en
[`lanzadores/LAUNCHER.md`](lanzadores/LAUNCHER.md).

## Comandos

Verificado ejecutando `python kaizen.py --help` hoy:

```
bitacora          Bitacora encadenada por tenant.
bus               Bus de eventos del sustrato (data/kaizen.db).
catalogo          Muestra los diez cubos del catálogo, su orden y su estado.
clientes          Lista los clientes y leads en el Diario.
comercial         Departamento Comercial sintético (cazador + agricultor).
consolidar        Actualiza el Diario y hace commit de Git al final del día.
coste             Muestra el coste de la sesión actual y el acumulado.
cubos             Catalogo de cubos con contrato canonico.
director          Panel del Director, solo lectura.
export-context    Genera el bloque de arranque para pegar en una sesión nueva.
forense           Verificación forense.
mesa              Mesa del Jefe: bandeja de decisiones (propuestas).
migrar-knowledge  Migra los leads del knowledge al esquema unificado.
opengravity       Verificación por comité multi-agente y salud del sistema.
operador          Candado del operador: relajar barreras es decisión humana.
p8                Bucle de datos vertical P8.
pregunta          Consulta natural sobre los leads (NLQ).
prospectar PERFIL Busca candidatos B2B para el tenant activo según PERFIL.
redactar          Genera un borrador de primer contacto para un cliente.
registro          Registro P9: la verdad comercial.
ritual            Rituales de los cubos (p.ej. la mañana comercial).
test              Comandos de prueba (diagnóstico de canales).
ver               Muestra la ficha de un cliente del Diario.
```

Ejemplo real: `python kaizen.py prospectar "hoteles boutique Región de Murcia"`.
`comercial` tiene sus propios subcomandos (`comercial --help`): `dashboard`,
`fase0` (pasada completa de researcher + enriquecimiento), `fase1` (SDR
multicanal — compone y encola, no envía sin aprobación).

## Estructura

```
kaizen.py, mesa_jefe.py, centro_mando.py   # puntos de entrada CLI
api/server.py                              # backend FastAPI del panel (modo real)
panel_mando/                               # backend FastAPI del panel + Colmena (chat de directores)
core/                                      # bus de eventos, memoria, modelos, barreras de seguridad
departments/                               # un paquete por departamento (comercial, brand, finanzas, ...)
cubos/                                     # capa de contrato/salud sobre cada departamento
sustrato/                                  # CLI, config, comité de verificación, coste
empresas/laboratorio/, diario/laboratorio/ # único tenant versionado (sintético, sin datos reales)
lanzadores/                                # lanzadores de doble clic (.cmd) e icono/guía del acceso directo
herramientas/                              # utilidades de mantenimiento del propio repo
  centinela_datos.py                       #   guardia pre-commit: bloquea nombres de cliente real
  mapa_vivo.py                             #   regenera docs/MAPA_VIVO.md en cada commit (hook instalado)
tests/                                     # suite de pytest (única carpeta que pytest recorre)
pruebas_produccion/                        # scripts y actas de ejecuciones reales contra LLM (con coste)
demos/                                     # demo_tesis.py, ejecutable, sin dependencias de producto
conceptos/, docs/                          # documentación de arquitectura, conceptos y especificaciones
.github/workflows/tests.yml                # CI: instala dependencias y corre la suite en cada push/PR
```

Los datos de clientes reales (si los hay) viven fuera de este repositorio,
en un directorio hermano que resuelve `core/rutas.py`; nunca se commitean.

## Tests

```bash
pytest -q
```

Medido hoy: **1344 passed, 7 skipped, 0 failed**, ~23 s. Los 7 saltados
requieren credenciales LLM reales (`ANTHROPIC_API_KEY` + `KAIZEN_TEST_LLM_REAL=1`)
o backends reales (`REDIS_URL`/`NEO4J_URI`/`DATABASE_URL`) no configurados por
defecto. `pytest.ini` limita la recolección a `tests/`.

`.github/workflows/tests.yml` corre exactamente esta misma suite en cada
`push`/`pull request` — instala dependencias en limpio y ejecuta `pytest -q`
en una máquina que no es la del operador.

## Control de versiones

Cada commit pasa por un hook `pre-commit` que bloquea si detecta el nombre
de un cliente real en el árbol (`herramientas/centinela_datos.py`) y
regenera `docs/MAPA_VIVO.md`, el registro de todos los commits.

Este repositorio público se abre en el primer commit con el árbol ya
saneado: el desarrollo previo se hizo en un repositorio privado cuyo
historial contiene material de clientes reales y por eso no se publica.
Lo que hay aquí es el producto, no el cuaderno de trabajo.

## Documentación

- [`docs/DOSSIER_FUNCIONAMIENTO_INTERNO.md`](docs/DOSSIER_FUNCIONAMIENTO_INTERNO.md) — cómo funciona el sistema por dentro.
- [`docs/DECISIONES_ARQUITECTONICAS.md`](docs/DECISIONES_ARQUITECTONICAS.md) — decisiones de diseño documentadas.
- [`docs/TODO.md`](docs/TODO.md) — deuda técnica conocida.
- [`docs/LINEA_BASE.md`](docs/LINEA_BASE.md) — histórico de la cifra de tests, commit a commit.

## Licencia

Código abierto a la lectura, propietario en el uso: se publica para que
pueda leerse, clonarse y ejecutarse con fines de evaluación, no para
explotarlo comercialmente. Condiciones completas en [`LICENSE`](LICENSE).
