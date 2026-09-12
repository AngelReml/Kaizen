# -*- coding: utf-8 -*-
"""CENTINELA DE DATOS — guardia fail-closed que impide que datos de terceros,
PII o secretos entren en un commit.

Pieza 1 de R-REV-1 (KAIZEN_D11_UNIFICACION_Y_COLMENA_v0_2.md §1.4): mientras el
arbol de git siga mezclando codigo con `state/`, `data/`, `diario/` y
`empresas/`, el filtro manual en cada commit es un parche. Esto lo sustituye por
un guardia con test: escanea el STAGING antes de cada commit y lo ABORTA si
detecta datos de cliente, secretos o rutas prohibidas.

Uso (desde la raiz del repo, o desde cualquier subcarpeta):
    python -X utf8 herramientas/centinela_datos.py --staged          # modo hook
    python -X utf8 herramientas/centinela_datos.py --check <fichero|carpeta>...

Garantias:
- Solo stdlib (ADR-001: nada de Pydantic). Solo LECTURA de git y de disco.
  Jamas escribe nada, jamas toca la red.
- Fail-closed (GR-04): ante error, entrada no reconocida o duda razonable,
  BLOQUEA (exit != 0). Nunca permite por defecto.
- `escanear()` es PURA: recibe (ruta, contenido) ya leidos, no toca git ni
  disco. Todo el criterio vive ahi y por eso es testeable sin repositorio.

Override del operador (la casa: endurecer es programatico, relajar es humano y
con motivo). Con la variable de entorno CENTINELA_OVERRIDE=<motivo no vacio> el
centinela PERMITE, pero imprime el motivo y todas las violaciones omitidas, de
modo que quedan en el log del commit. Sin motivo NO hay bypass.
"""
import fnmatch
import os
import re
import subprocess
import sys

# --- ALLOWLIST: tiene prioridad sobre cualquier regla de RUTA -----------------
# 'laboratorio' es el tenant SINTETICO (R-REV-3): 50 negocios inventados con
# correos .invalid. Es ficcion escrita para commitearse; no hay tercero detras.
ALLOWLIST = ("empresas/laboratorio/", "empresas/tenants.laboratorio.json",
             "diario/laboratorio/")

# --- Reglas de RUTA ----------------------------------------------------------
CARPETAS_PROHIBIDAS = ("state", "data", "diario", "bitacora")
FICHEROS_PROHIBIDOS = (".kaizen_cost.json",)
PATRONES_PROHIBIDOS = ("*keys*.txt", "*secret*.txt")
ENV_PERMITIDO = (".env.example",)

_RE_BRAND = re.compile(r"^empresas/[^/]+/brand/", re.I)
_RE_ARGUMENTARIO = re.compile(r"^empresas/[^/]+/argumentario\.json$", re.I)

# --- R-TENANT: ningun nombre de cliente real en el arbol del producto ---------
# "El arbol del producto sabe QUE ES un tenant, jamas QUE tenant."
#
# La lista de nombres vetados NO puede vivir aqui: escribir 'X' en este fichero
# para prohibir 'X' seria la propia violacion que se persigue. Por eso se DERIVA
# de la raiz de datos (ids y razones sociales del registro de tenants, mas los
# nombres de directorio bajo empresas/), que vive fuera del arbol.
#
# Si la raiz de datos no es accesible, la comprobacion no puede hacerse. Eso NO
# bloquea: la referencia vive legitimamente fuera y, tras F5, lo normal en una
# maquina sin el disco de datos es no tenerla. Bloquear ahi dejaria el repo
# incommiteable. Se informa en claro para que la ausencia no pase por silencio.
TENANTS_SINTETICOS = ("laboratorio",)

# Se vetan el ID del tenant y su razon social COMPLETA, nunca las palabras
# sueltas de esta. Trocear una razon social del tipo "<Oficio> <Apellido>" vetaba
# tambien el nombre del oficio —un sustantivo comun del dominio— y bloqueaba
# texto legitimo del producto. El id ya caza cualquier mencion real.
# (Este fichero no puede escribir un nombre vetado ni como ejemplo: seria la
#  propia violacion. El guardia se aplica a si mismo.)
MIN_LONGITUD_NOMBRE = 4


def nombres_vetados(raiz_datos=None):
    """Nombres de cliente real derivados de la raiz de datos. `None` si no se puede.

    `None` significa "no he podido comprobarlo", que es distinto de "no hay
    ninguno": el que llama debe distinguirlos.
    """
    import json
    if raiz_datos is None:
        raiz_datos = os.environ.get("KAIZEN_DATOS", "").strip()
        if not raiz_datos:
            aqui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            raiz_datos = os.path.join(os.path.dirname(aqui), "KAIZEN_DATOS")
    dir_empresas = os.path.join(str(raiz_datos), "empresas")
    if not os.path.isdir(dir_empresas):
        return None
    nombres = set()
    for nombre in os.listdir(dir_empresas):
        if os.path.isdir(os.path.join(dir_empresas, nombre)):
            if nombre.lower() not in TENANTS_SINTETICOS:
                nombres.add(nombre.lower())
    registro = os.path.join(dir_empresas, "tenants.json")
    if os.path.isfile(registro):
        try:
            with open(registro, "rb") as fh:
                datos = json.loads(fh.read().decode("utf-8"))
            for t in datos.get("tenants", []):
                tid = str(t.get("id", "")).lower()
                if tid and tid not in TENANTS_SINTETICOS:
                    nombres.add(tid)
                    razon = " ".join(str(t.get("razon_social", "")).split()).lower()
                    if len(razon) >= MIN_LONGITUD_NOMBRE:
                        nombres.add(razon)
        except Exception:  # noqa: BLE001 — fichero ilegible: no inventamos la lista
            pass
    return {n for n in nombres if len(n) >= MIN_LONGITUD_NOMBRE}

# --- Reglas de CONTENIDO -----------------------------------------------------
# Nombres de variable que designan una credencial REAL de un proveedor concreto.
_PREFIJOS = ("ANTHROPIC", "OPENAI", "GROQ", "GEMINI", "DEEPSEEK", "GLM", "HF",
             "OPENROUTER", "ELEVENLABS", "TWILIO", "GOOGLE_MAPS")
_SUFIJOS = ("API_KEY", "TOKEN", "SECRET", "SID")
_RE_ASIGNACION = re.compile(
    r"(?i)\b(?P<var>(?:%s)[A-Z0-9_]*_(?:%s))\s*[:=]\s*(?P<val>\S*)"
    % ("|".join(_PREFIJOS), "|".join(_SUFIJOS)))

# Formas de clave sueltas: aparezcan donde aparezcan, no hay lectura inocente.
_RE_CLAVE_SUELTA = (
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "clave Anthropic (sk-ant-...)"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "clave tipo OpenAI (sk-...)"),
)

# Un valor mas corto que esto no puede ser una credencial de ningun proveedor
# (la mas corta en uso, TWILIO_ACCOUNT_SID, tiene 34 caracteres). Es el unico
# umbral del centinela y esta documentado a proposito: por debajo se considera
# ruido de prosa o de codigo, no secreto.
MIN_LONGITUD_VALOR = 8

# Marcas de que el valor es una REFERENCIA de codigo, no un literal incrustado
# (os.getenv("X"), ${VAR}, .startswith("X="), etc.).
_MARCAS_CODIGO = ("(", ")", "{", "}", "[", "]", "$", "getenv", "environ")

# Una tabla de variables alineada por columnas (`FOO_API_KEY=    BAR_TOKEN=`)
# hace que el "valor" capturado sea en realidad el NOMBRE de la variable
# siguiente. Un identificador desnudo que termina en '=' nunca es una
# credencial: es la cabecera de otra asignacion vacia.
_RE_OTRA_ASIGNACION = re.compile(r"[A-Za-z][A-Za-z0-9_]*=$")

_INICIOS_PLACEHOLDER = ("your", "tu_", "tu-", "changeme", "cambiame", "pon-aqui",
                        "pon_aqui", "placeholder", "rellena", "ejemplo", "example",
                        "dummy", "fake", "none", "null", "todo", "abc123")


def normalizar(ruta):
    """Ruta relativa canonica: separadores posix, sin './' ni '/' inicial."""
    r = str(ruta).replace("\\", "/").strip()
    while r.startswith("./"):
        r = r[2:]
    return r.lstrip("/")


def _en_allowlist(ruta):
    b = normalizar(ruta).lower()
    return any(b.startswith(a) or b == a.rstrip("/") for a in ALLOWLIST)


def _violaciones_ruta(ruta):
    """Reglas por ruta. La ALLOWLIST ya se ha comprobado antes de llamar aqui."""
    r = normalizar(ruta)
    b = r.lower()
    base = b.rsplit("/", 1)[-1]
    fallos = []

    segmentos = b.split("/")[:-1]
    for carpeta in CARPETAS_PROHIBIDAS:
        if carpeta in segmentos:
            fallos.append("ruta bajo '%s/' — datos de terceros o estado local, "
                          "no entra en git" % carpeta)

    if _RE_BRAND.match(r):
        fallos.append("brand de una empresa real — biblia de marca de un cliente")
    if _RE_ARGUMENTARIO.match(r):
        fallos.append("argumentario de una empresa real — material de cliente")

    if base == ".env" or (base.startswith(".env.") and base not in ENV_PERMITIDO):
        fallos.append("fichero de entorno con credenciales reales (.env*)")

    for patron in PATRONES_PROHIBIDOS:
        if fnmatch.fnmatch(base, patron):
            fallos.append("nombre de fichero de secretos (%s)" % patron)

    if base in FICHEROS_PROHIBIDOS:
        fallos.append("contador de gasto local (%s), no es codigo" % base)

    return fallos


def _es_placeholder(valor):
    v = valor.strip().strip("'\"`,;").strip()
    if not v:
        return True
    b = v.lower()
    if "..." in b:                                   # sk-ant-...  /  SMTP_PASS=...
        return True
    if b.startswith("<") and b.endswith(">"):        # <tu-clave>
        return True
    if re.fullmatch(r"[x_\-*#?]{2,}", b):            # xxx, ----, ****
        return True
    return any(b.startswith(m) for m in _INICIOS_PLACEHOLDER)


def _valor_es_secreto(valor):
    """True si el valor asignado parece una credencial REAL.

    Fail-closed: si el valor no es reconocible ni como placeholder ni como
    referencia de codigo, se considera secreto y se bloquea para revision.
    """
    v = valor.strip().strip("'\"`,;").strip()
    if _es_placeholder(v):
        return False
    if _RE_OTRA_ASIGNACION.fullmatch(v):
        return False
    if any(m in v for m in _MARCAS_CODIGO):
        return False
    if len(v) < MIN_LONGITUD_VALOR:
        return False
    return True


def _texto(contenido):
    """Decodifica para inspeccion. Binario -> ruido, nunca excepcion."""
    if isinstance(contenido, str):
        return contenido
    return contenido.decode("utf-8", errors="replace")


def _violaciones_tenant(contenido, vetados):
    """R-TENANT: nombre de cliente real dentro de un fichero del arbol."""
    if not vetados:
        return []
    fallos = []
    vistos = set()
    for n, linea in enumerate(_texto(contenido).splitlines(), 1):
        bajo = linea.lower()
        for nombre in vetados:
            if nombre in vistos:
                continue
            if re.search(r"\b%s\b" % re.escape(nombre), bajo):
                vistos.add(nombre)
                fallos.append("linea %d: nombre de cliente real '%s' en el arbol del "
                              "producto (R-TENANT: el producto sabe QUE ES un tenant, "
                              "jamas QUE tenant)" % (n, nombre))
    return fallos


def _violaciones_contenido(contenido):
    """Reglas por contenido. Se aplican a TODOS los ficheros, incluida la
    allowlist: un tenant sintetico tampoco puede llevar una clave real dentro."""
    fallos = []
    for n, linea in enumerate(_texto(contenido).splitlines(), 1):
        for m in _RE_ASIGNACION.finditer(linea):
            if _valor_es_secreto(m.group("val")):
                fallos.append("linea %d: asignacion de secreto real a %s"
                              % (n, m.group("var").upper()))
        for rx, etiqueta in _RE_CLAVE_SUELTA:
            if rx.search(linea):
                fallos.append("linea %d: %s incrustada en el fichero" % (n, etiqueta))
                break
    return fallos


def escanear(entradas, vetados=None):
    """Funcion PURA. entradas: lista de (ruta_relativa: str, contenido: bytes|None).

    `vetados`: nombres de cliente real que no pueden aparecer en el arbol
    (R-TENANT). `None` o vacio desactiva esa regla concreta; el resto siguen.

    Devuelve [{"ruta": str, "motivo": str}, ...]. Vacia = limpio.
    contenido None significa "no he podido leerlo": fail-closed, se bloquea.
    """
    violaciones = []
    for entrada in entradas:
        try:
            ruta, contenido = entrada
        except (TypeError, ValueError):
            violaciones.append({"ruta": repr(entrada),
                                "motivo": "entrada no reconocida (fail-closed)"})
            continue
        r = normalizar(ruta)
        if not r:
            violaciones.append({"ruta": repr(ruta),
                                "motivo": "ruta vacia o no reconocida (fail-closed)"})
            continue
        if not _en_allowlist(r):
            for motivo in _violaciones_ruta(r):
                violaciones.append({"ruta": r, "motivo": motivo})
        if contenido is None:
            violaciones.append({"ruta": r, "motivo": "contenido ilegible o no "
                                "disponible — revision humana (fail-closed)"})
            continue
        for motivo in _violaciones_contenido(contenido):
            violaciones.append({"ruta": r, "motivo": motivo})
        for motivo in _violaciones_tenant(contenido, vetados):
            violaciones.append({"ruta": r, "motivo": motivo})
    return violaciones


def motivo_override(entorno=None):
    """Motivo de override del operador, o None si no lo hay.

    Solo un motivo NO VACIO habilita el bypass; la variable a secas no basta.
    """
    ent = os.environ if entorno is None else entorno
    return (ent.get("CENTINELA_OVERRIDE") or "").strip() or None


def informe(violaciones, motivo=None):
    """(lineas_a_imprimir, codigo_de_salida). Puro: no imprime ni sale."""
    motivo = (motivo or "").strip() or None    # un motivo en blanco NO es override
    if not violaciones:
        return (["[CENTINELA] OK: nada que bloquear (0 violaciones)."], 0)
    cabecera = "[CENTINELA] %d violacion(es):" % len(violaciones)
    detalle = ["  - %s\n      %s" % (v["ruta"], v["motivo"]) for v in violaciones]
    if motivo:
        return ([cabecera] + detalle + [
            "[CENTINELA] OVERRIDE DEL OPERADOR — motivo: %s" % motivo,
            "[CENTINELA] PERMITIDO bajo tu firma. %s de arriba queda%s"
            " registrada%s en el log del commit." % (
                "La violacion" if len(violaciones) == 1
                else "Las %d violaciones" % len(violaciones),
                "" if len(violaciones) == 1 else "n",
                "" if len(violaciones) == 1 else "s")], 0)
    return ([cabecera] + detalle + [
        "[CENTINELA] COMMIT BLOQUEADO (fail-closed). Saca esos ficheros del",
        "[CENTINELA] indice (git restore --staged <ruta>) o, si estas seguro,",
        "[CENTINELA] repite con CENTINELA_OVERRIDE=\"motivo\" y quedara en el log."], 1)


# --- Acceso a git y a disco (fuera de la parte pura) -------------------------

def _git_texto(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s -> rc=%d: %s" % (
            " ".join(args), r.returncode,
            r.stderr.decode("utf-8", errors="replace").strip()[:300]))
    return r.stdout.decode("utf-8", errors="replace")


def _git_bytes(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout


def ir_a_raiz():
    os.chdir(_git_texto("rev-parse", "--show-toplevel").strip())


def entradas_staged():
    """Rutas + contenido STAGED. Las borradas se excluyen (--diff-filter=ACMR):
    un borrado no puede filtrar nada, y no tiene blob que leer."""
    crudo = _git_texto("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    rutas = [r for r in crudo.split("\0") if r.strip()]
    return [(r, _git_bytes("show", ":%s" % r)) for r in rutas]


def entradas_disco(objetivos, raiz=None):
    """Rutas + contenido del arbol de trabajo (uso manual). Recorre carpetas.

    `objetivos` deben venir ya en absoluto (se resuelven contra el cwd del
    operador ANTES de saltar a la raiz del repo); las rutas del informe salen
    relativas a la raiz, que es como las nombra git.
    """
    raiz = raiz or os.getcwd()
    omitir = {".git", "__pycache__", ".venv", ".pytest_cache", "node_modules"}
    ficheros = []
    for objetivo in objetivos:
        if os.path.isdir(objetivo):
            for base, dirs, nombres in os.walk(objetivo):
                dirs[:] = [d for d in dirs if d not in omitir]
                ficheros.extend(os.path.join(base, n) for n in nombres)
        else:
            ficheros.append(objetivo)
    entradas = []
    for f in ficheros:
        try:
            with open(f, "rb") as fh:
                contenido = fh.read()
        except OSError:
            contenido = None          # fail-closed: lo resuelve escanear()
        try:
            nombre = os.path.relpath(f, raiz)
        except ValueError:            # otra unidad de disco en Windows
            nombre = f
        entradas.append((nombre, contenido))
    return entradas


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if not argv:
            print("[CENTINELA] falta modo: --staged | --check <fichero|carpeta>...")
            return 2
        modo, resto = argv[0], argv[1:]
        # Los objetivos de --check se resuelven contra el cwd del operador
        # ANTES de saltar a la raiz del repo.
        objetivos = [os.path.abspath(r) for r in resto]
        ir_a_raiz()
        if modo == "--staged":
            entradas = entradas_staged()
            if not entradas:
                print("[CENTINELA] OK: staging vacio, nada que revisar.")
                return 0
        elif modo == "--check":
            if not objetivos:
                print("[CENTINELA] --check necesita al menos un fichero o carpeta.")
                return 2
            entradas = entradas_disco(objetivos)
        else:
            print("[CENTINELA] modo desconocido: %s (usa --staged | --check)" % modo)
            return 2
        vetados = nombres_vetados()
        if vetados is None:
            print("[CENTINELA] AVISO: raiz de datos no accesible; R-TENANT (nombres de")
            print("[CENTINELA] cliente en el arbol) NO se ha podido comprobar en esta")
            print("[CENTINELA] pasada. El resto de reglas si se han aplicado.")
            vetados = set()
        lineas, codigo = informe(escanear(entradas, vetados), motivo_override())
        for l in lineas:
            print(l)
        return codigo
    except Exception as e:                       # fail-closed: cualquier fallo bloquea
        print("[CENTINELA] FALLO: %s: %s" % (type(e).__name__, e))
        print("[CENTINELA] BLOQUEADO por precaucion (fail-closed).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
