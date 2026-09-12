"""Autonomia graduada, gates preventivos y candado del operador (canonico 7).

- Niveles: CERO < BAJA < MEDIA < ALTA. Nivel vigente por cubo en
  config_autonomia (inicial comercial: BAJA).
- gate_preventivo(): unica puerta. Nivel insuficiente -> FAIL sin convocar
  comite (no gastar tokens en lo prohibido). Accion irreversible con nivel
  suficiente -> comite (3 roles x 3 pasadas). SIEMPRE escribe en
  verificaciones (cadena de hash propia) antes de devolver. FAIL-SAFE:
  cualquier excepcion interna => FAIL error_interno, jamas PASS por defecto.
- Candado: endurecer (bajar nivel / bajar limite) es programatico; RELAJAR
  es exclusivo del operador via CLI con --motivo, y queda en
  decisiones_operador con cadena de hash propia.
- Prometer condiciones/precios a un cliente: accion INEXISTENTE en el
  sistema (canonico 7.2): AccionInexistente.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from sustrato import bus, coste, hashchain
from sustrato.consola import log, ts_iso8601z

NIVELES = ("CERO", "BAJA", "MEDIA", "ALTA")
_IDX = {n: i for i, n in enumerate(NIVELES)}

NOMBRE_AIACT_VOZ = "aiact_primeros_mensajes.md"


def ruta_aiact_voz(empresa: str) -> Path:
    """Fichero de primeros mensajes AI Act del tenant.

    R-TENANT: el saludo de apertura nombra a la empresa emisora y a quien firma
    la voz — es contenido de tenant. Vive en su ficha, fuera del arbol de git.
    Antes era una ruta fija del repo: un solo guion para todos los clientes.
    """
    from core.rutas import dir_empresa
    return dir_empresa(empresa) / NOMBRE_AIACT_VOZ

# Una variante aprobada = un bloque que empieza por "<n>. " y llega hasta la
# siguiente linea en blanco. La numeracion es la del fichero de runtime.
_RE_VARIANTE = re.compile(r"^\s*\d+\.\s+(.+?)(?=\n\s*\n|\Z)", re.M | re.S)


def _norm(texto: str) -> str:
    """Normaliza espacio en blanco: los saltos de linea del snapshot Python no
    cuentan como diferencia frente al fichero .md."""
    return " ".join((texto or "").split())


def variantes_aprobadas(ruta: Path) -> list[str]:
    """Lista normalizada de las variantes aprobadas del fichero de runtime.

    Se extraen SOLO los bloques numerados: la prosa de cabecera del fichero
    (titulo, nota de aprobacion del operador) NO es una variante y no debe
    poder validar un primer mensaje.

    Compatibilidad: un fichero sin bloques numerados se interpreta como una
    unica variante con todo su contenido (formato usado por algunos tests y
    por ficheros de una sola variante).
    """
    contenido = ruta.read_text(encoding="utf-8")
    variantes = [_norm(v) for v in _RE_VARIANTE.findall(contenido)]
    variantes = [v for v in variantes if v]
    if variantes:
        return variantes
    entero = _norm(contenido)
    return [entero] if entero else []

# Matriz accion -> (nivel minimo, requiere gate/comite) (canonico 7.2, cerrada)
MATRIZ_ACCIONES: dict[str, tuple[str, bool]] = {
    "leer_registro": ("CERO", False),
    "generar_briefing": ("CERO", False),
    "rankear_p8": ("CERO", False),
    "escribir_registro_interno": ("BAJA", False),
    "crear_compromiso_interno": ("BAJA", False),
    "envio_email_real": ("ALTA", True),
    "contacto_saliente_ia": ("ALTA", True),
    "compromiso_ante_cliente": ("ALTA", True),  # fila mas restrictiva aplicable
}
ACCIONES_INEXISTENTES = ("prometer_condiciones_precios", "prometer_precio",
                         "prometer_condiciones")

_DDL = """
CREATE TABLE IF NOT EXISTS config_autonomia (
  cubo  TEXT PRIMARY KEY,
  nivel TEXT NOT NULL,
  ts    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config_valores (
  clave TEXT PRIMARY KEY,
  valor TEXT NOT NULL,
  ts    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisiones_operador (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, tipo TEXT NOT NULL, detalle TEXT NOT NULL,
  hash_prev TEXT NOT NULL, hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS verificaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('preventiva','forense')),
  cubo TEXT NOT NULL,
  accion TEXT NOT NULL,
  veredicto TEXT NOT NULL CHECK (veredicto IN ('PASS','FAIL','ESCALADO')),
  confianza REAL,
  detalle TEXT NOT NULL,
  hash_prev TEXT NOT NULL,
  hash TEXT NOT NULL UNIQUE
);
"""



def _irreversibles_de_manifests() -> set:
    """Acciones irreversibles declaradas por los manifests de cubos/ instalados."""
    import json as _json
    out = set()
    try:
        for ruta in (Path(__file__).resolve().parent.parent / "cubos").glob("*/manifest.json"):
            try:
                out.update(_json.loads(ruta.read_text(encoding="utf-8"))
                           .get("acciones_irreversibles", []))
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return out

def matriz_efectiva() -> dict[str, tuple[str, bool]]:
    """Matriz base + acciones irreversibles declaradas por los manifests, como
    valor NUEVO en cada llamada.

    Antes se hacia `MATRIZ_ACCIONES[accion] = ("ALTA", True)` dentro del gate: el
    diccionario global se mutaba en el camino critico, asi que el comportamiento
    del control dependia del historial del proceso (que acciones se habian pedido
    antes) y un test contaminaba a los siguientes. La mutacion iba siempre hacia
    MAS restrictivo, asi que no abria la puerta — pero un control de seguridad
    tiene que ser reproducible y auditable (auditoria 2026-08-02, G-07).

    La matriz base (canonico 7.2) es cerrada y no se toca: lo que anaden los
    manifests entra siempre como fila mas restrictiva (ALTA + comite) y nunca
    puede rebajar una fila existente.
    """
    matriz = dict(MATRIZ_ACCIONES)
    for accion in _irreversibles_de_manifests():
        matriz.setdefault(accion, ("ALTA", True))
    return matriz


class AccionInexistente(RuntimeError):
    """Prometer condiciones/precios: solo humano; no existe en el sistema."""


class OperacionReservadaAlOperador(PermissionError):
    pass


@dataclass
class Veredicto:
    veredicto: str                      # PASS | FAIL | ESCALADO
    motivo: str
    confianza: float | None = None
    detalle: dict = field(default_factory=dict)

    @property
    def pasa(self) -> bool:
        return self.veredicto == "PASS"


def instalar(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


# ------------------------------------------------------------- cadenas propias
def _ultima(conn: sqlite3.Connection, tabla: str) -> str:
    fila = conn.execute(f"SELECT hash FROM {tabla} ORDER BY id DESC LIMIT 1").fetchone()
    return fila[0] if fila else hashchain.GENESIS


def registrar_verificacion_en_tx(conn: sqlite3.Connection, tipo: str, cubo: str, accion: str,
                                 veredicto: str, confianza: float | None, detalle: dict) -> int:
    """Escribe la verificacion SIN abrir transaccion propia: el llamante es dueno
    de la transaccion (mismo patron que registrar_decision_operador_en_tx)."""
    ts = ts_iso8601z()
    cuerpo = bus.payload_canonico(detalle)
    hash_prev = _ultima(conn, "verificaciones")
    h = hashchain.calcular(hash_prev, f"verificacion.{tipo}.{accion}", cuerpo, ts)
    cur = conn.execute(
        "INSERT INTO verificaciones (ts, tipo, cubo, accion, veredicto, confianza, "
        "detalle, hash_prev, hash) VALUES (?,?,?,?,?,?,?,?,?)",
        (ts, tipo, cubo, accion, veredicto, confianza, cuerpo, hash_prev, h))
    return int(cur.lastrowid)


def registrar_verificacion(conn: sqlite3.Connection, tipo: str, cubo: str, accion: str,
                           veredicto: str, confianza: float | None, detalle: dict) -> int:
    with bus.transaccion(conn):   # BEGIN IMMEDIATE: protege el hash_prev (G-08)
        return registrar_verificacion_en_tx(conn, tipo, cubo, accion, veredicto, confianza,
                                            detalle)


def registrar_decision_operador_en_tx(conn: sqlite3.Connection, tipo: str,
                                       detalle: dict) -> int:
    """Escribe la decision SIN abrir transaccion propia: el llamante es dueno de
    la transaccion (mismo patron que bus.publicar_en_tx). Necesario para que una
    excepcion de operador y su registro auditado sean atomicos."""
    ts = ts_iso8601z()
    cuerpo = bus.payload_canonico(detalle)
    hash_prev = _ultima(conn, "decisiones_operador")
    h = hashchain.calcular(hash_prev, f"decision.{tipo}", cuerpo, ts)
    cur = conn.execute(
        "INSERT INTO decisiones_operador (ts, tipo, detalle, hash_prev, hash) "
        "VALUES (?,?,?,?,?)", (ts, tipo, cuerpo, hash_prev, h))
    return int(cur.lastrowid)


def registrar_decision_operador(conn: sqlite3.Connection, tipo: str, detalle: dict) -> int:
    with bus.transaccion(conn):   # BEGIN IMMEDIATE: protege el hash_prev (G-08)
        return registrar_decision_operador_en_tx(conn, tipo, detalle)


def verificar_cadena(conn: sqlite3.Connection, tabla: str) -> str:
    """Verifica la cadena de verificaciones o decisiones_operador."""
    if tabla == "verificaciones":
        filas = conn.execute(
            "SELECT id, 'verificacion.' || tipo || '.' || accion, detalle, ts, hash_prev, hash "
            "FROM verificaciones ORDER BY id").fetchall()
    elif tabla == "decisiones_operador":
        filas = conn.execute(
            "SELECT id, 'decision.' || tipo, detalle, ts, hash_prev, hash "
            "FROM decisiones_operador ORDER BY id").fetchall()
    else:
        raise ValueError(tabla)
    intacta, n, corrupto = hashchain.verificar(filas)
    return (f"CADENA INTACTA ({n} eventos)" if intacta
            else f"CADENA CORRUPTA: primer id corrupto = {corrupto} (verificados {n})")


# ------------------------------------------------------------------ autonomia
def _nivel_defecto_manifest(cubo: str) -> str:
    """Nivel por defecto del cubo cuando aun no hay fila en config_autonomia.

    Antes se devolvia "BAJA" fijo para CUALQUIER cubo: rrhh/qa/legal/inteligencia
    declaran "CERO" en su manifest.json (departamentos que NO deben actuar sin
    configuracion explicita del operador) y el fallback global se lo saltaba,
    dandoles de facto el nivel de comercial. Se lee solo el JSON del manifest
    (sin importar codigo de cubos/departments) para no acoplar sustrato a la
    logica de negocio de los cubos.
    """
    try:
        from cubos.base import manifiestos_instalados
        ruta = manifiestos_instalados().get(cubo)
        if ruta is not None:
            manifest = json.loads(ruta.read_text(encoding="utf-8"))
            nivel = manifest.get("nivel_autonomia_defecto")
            if nivel in NIVELES:
                return nivel
    except Exception:
        pass
    return "BAJA"  # sin manifest legible: valor historico del cubo comercial (7.1)


def nivel_vigente(conn: sqlite3.Connection, cubo: str = "comercial") -> str:
    fila = conn.execute("SELECT nivel FROM config_autonomia WHERE cubo=?", (cubo,)).fetchone()
    return fila[0] if fila else _nivel_defecto_manifest(cubo)


def set_autonomia(conn: sqlite3.Connection, cubo: str, nivel: str, motivo: str = "",
                  es_operador: bool = False) -> None:
    if nivel not in NIVELES:
        raise ValueError(f"nivel desconocido: {nivel}")
    actual = nivel_vigente(conn, cubo)
    if _IDX[nivel] > _IDX[actual]:  # RELAJAR: solo operador con motivo
        if not es_operador:
            raise OperacionReservadaAlOperador(
                f"subir autonomia {actual} -> {nivel} exige CLI de operador (canonico 7.4)")
        if not motivo.strip():
            raise ValueError("--motivo no puede estar vacio para relajar")
        with bus.transaccion(conn):  # decision + aplicacion: atomicas (G-08)
            registrar_decision_operador_en_tx(conn, "set_autonomia",
                                              {"cubo": cubo, "de": actual, "a": nivel,
                                               "motivo": motivo})
            conn.execute(
                "INSERT INTO config_autonomia (cubo, nivel, ts) VALUES (?,?,?) "
                "ON CONFLICT(cubo) DO UPDATE SET nivel=excluded.nivel, ts=excluded.ts",
                (cubo, nivel, ts_iso8601z()))
    else:
        with bus.transaccion(conn):
            conn.execute(
                "INSERT INTO config_autonomia (cubo, nivel, ts) VALUES (?,?,?) "
                "ON CONFLICT(cubo) DO UPDATE SET nivel=excluded.nivel, ts=excluded.ts",
                (cubo, nivel, ts_iso8601z()))
    log("INFO", "gates", "autonomia actualizada", cubo=cubo, de=actual, a=nivel)


def set_limite_coste(conn: sqlite3.Connection, eur: float, motivo: str = "",
                     es_operador: bool = False) -> None:
    from sustrato import config
    fila = conn.execute(
        "SELECT valor FROM config_valores WHERE clave='LIMITE_COSTE_DIARIO_EUR'").fetchone()
    actual = float(fila[0]) if fila else config.limite_coste_diario_eur()
    if float(eur) > actual:  # RELAJAR: solo operador con motivo
        if not es_operador:
            raise OperacionReservadaAlOperador(
                f"subir limite {actual:.2f} -> {float(eur):.2f} EUR exige CLI de operador")
        if not motivo.strip():
            raise ValueError("--motivo no puede estar vacio para relajar")
        with bus.transaccion(conn):  # decision + aplicacion: atomicas (G-08)
            registrar_decision_operador_en_tx(conn, "set_limite_coste",
                                              {"de": round(actual, 2), "a": round(float(eur), 2),
                                               "motivo": motivo})
            conn.execute(
                "INSERT INTO config_valores (clave, valor, ts) VALUES "
                "('LIMITE_COSTE_DIARIO_EUR',?,?) "
                "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor, ts=excluded.ts",
                (f"{float(eur):.4f}", ts_iso8601z()))
    else:
        with bus.transaccion(conn):
            conn.execute(
                "INSERT INTO config_valores (clave, valor, ts) VALUES "
                "('LIMITE_COSTE_DIARIO_EUR',?,?) "
                "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor, ts=excluded.ts",
                (f"{float(eur):.4f}", ts_iso8601z()))
    log("INFO", "gates", "limite de coste actualizado", de=f"{actual:.2f}",
        a=f"{float(eur):.2f}")


# --------------------------------------------------------------- gate central
def gate_preventivo(conn: sqlite3.Connection, accion: str, contexto: dict,
                    cubo: str = "comercial", llm=None) -> Veredicto:
    """Unica funcion de entrada (canonico 7.3). El llamante SOLO ejecuta la
    accion si el veredicto devuelto es PASS."""
    if accion in ACCIONES_INEXISTENTES:
        raise AccionInexistente(
            "prometer condiciones/precios a un cliente es accion exclusiva de un humano; "
            "no existe en el sistema (canonico 7.2)")
    try:
        matriz = matriz_efectiva()
        if accion not in matriz:
            v = Veredicto("FAIL", "accion_desconocida",
                          detalle={"accion": accion,
                                   "nota": "no listada en matriz 7.2; fila mas restrictiva"})
            registrar_verificacion(conn, "preventiva", cubo, accion, v.veredicto, None,
                                   {"motivo": v.motivo, **v.detalle})
            return v
        minimo, requiere_comite = matriz[accion]
        vigente = nivel_vigente(conn, cubo)
        if _IDX[vigente] < _IDX[minimo]:
            v = Veredicto("FAIL", "nivel_insuficiente",
                          detalle={"nivel_vigente": vigente, "nivel_minimo": minimo})
            registrar_verificacion(conn, "preventiva", cubo, accion, v.veredicto, None,
                                   {"motivo": v.motivo, **v.detalle})
            return v
        if not requiere_comite:
            v = Veredicto("PASS", "nivel_suficiente_sin_comite",
                          detalle={"nivel_vigente": vigente})
            registrar_verificacion(conn, "preventiva", cubo, accion, v.veredicto, None,
                                   {"motivo": v.motivo, **v.detalle})
            return v
        from sustrato import comite
        dictamen = comite.convocar(conn, accion, contexto, llm=llm)
        v = Veredicto(dictamen["veredicto"], "dictamen_comite",
                      confianza=dictamen["confianza"], detalle=dictamen)
        registrar_verificacion(conn, "preventiva", cubo, accion, v.veredicto,
                               v.confianza, dictamen)
        return v
    except AccionInexistente:
        raise
    except Exception as exc:  # FAIL-SAFE (canonico 7.3): jamas PASS por defecto
        v = Veredicto("FAIL", "error_interno", detalle={"error": type(exc).__name__,
                                                        "texto": str(exc)[:200]})
        try:
            registrar_verificacion(conn, "preventiva", cubo, accion, "FAIL", None,
                                   {"motivo": "error_interno", "error": type(exc).__name__})
        except Exception:
            log("CRITICAL", "gates", "no se pudo registrar la verificacion del fail-safe",
                accion=accion)
        return v


# ------------------------------------------------------- compliance pre-flight
def preflight_llamada(conn: sqlite3.Connection, lead_id: str,
                      primer_mensaje: str | None = None,
                      ruta_aiact: Path | None = None,
                      *, empresa: str | None = None) -> Veredicto:
    """Robinson (canonico 10.2) + AI Act art. 50 para canal llamada_ia.

    El sistema EXIGE robinson_ok informado; la comprobacion real contra la
    Lista Robinson es proceso del operador en esta fase.
    """
    def _reg(v: Veredicto) -> Veredicto:
        registrar_verificacion(conn, "preventiva", "comercial", "preflight_llamada",
                               v.veredicto, None, {"lead_id": lead_id, "motivo": v.motivo})
        return v

    fila = conn.execute("SELECT robinson_ok FROM leads WHERE id=?", (lead_id,)).fetchone()
    if fila is None:
        return _reg(Veredicto("FAIL", "lead_inexistente"))
    robinson = fila[0]
    if robinson is None:
        return _reg(Veredicto("FAIL", "robinson_sin_comprobar"))
    if int(robinson) == 0:
        try:
            from sustrato import registro
            registro.transicionar(conn, lead_id, "NO_LLAMAR", "lista Robinson (robinson_ok=0)")
        except Exception:
            pass  # p.ej. ya era terminal; el FAIL se mantiene igualmente
        return _reg(Veredicto("FAIL", "en_lista_robinson_no_llamar"))
    # R-TENANT, fail-closed: `ruta_aiact` explicita manda; si no, se resuelve
    # desde el tenant. Sin ninguna de las dos NO se adivina un tenant — un
    # preflight de cumplimiento sin declarar POR QUIEN se llama no es valido.
    if ruta_aiact is not None:
        ruta = Path(ruta_aiact)
    elif empresa:
        ruta = ruta_aiact_voz(empresa)
    else:
        return _reg(Veredicto("FAIL", "tenant_no_declarado",
                              detalle={"nota": "preflight sin empresa ni ruta_aiact "
                                               "(R-TENANT: el producto no adivina "
                                               "de quien es la llamada)"}))
    if not ruta.exists():
        return _reg(Veredicto("FAIL", "fichero_aiact_ausente",
                              detalle={"ruta": str(ruta),
                                       "nota": "variantes pendientes de aprobacion del operador"}))
    if primer_mensaje is None:
        return _reg(Veredicto("FAIL", "primer_mensaje_no_configurado"))
    # Literalidad = IGUALDAD con una variante aprobada, no "estar contenido en el
    # fichero". Con `in` bastaba un fragmento para validar: "Hola, buenos dias.",
    # "Buenos dias." o incluso texto de la cabecera ("APROBADAS LAS 20") pasaban el
    # candado sin identificar que habla una IA (auditoria 2026-08-02, G-03).
    aprobadas = variantes_aprobadas(ruta)
    if not aprobadas:
        return _reg(Veredicto("FAIL", "fichero_aiact_sin_variantes",
                              detalle={"ruta": str(ruta)}))
    mensaje_norm = _norm(primer_mensaje)
    if mensaje_norm and mensaje_norm in aprobadas:
        return _reg(Veredicto("PASS", "robinson_ok_y_aiact_literal",
                              detalle={"variante": aprobadas.index(mensaje_norm) + 1}))
    return _reg(Veredicto("FAIL", "primer_mensaje_no_literal_del_fichero",
                          detalle={"variantes_disponibles": len(aprobadas)}))
