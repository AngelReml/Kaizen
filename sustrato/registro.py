"""Sistema de registro P9 (canonico seccion 5): la verdad comercial en SQLite.

DDL canonico aditivo (CREATE IF NOT EXISTS; nunca destruye). Toda transicion
de pipeline pasa por UNA sola funcion, transicionar(), que escribe
transiciones_pipeline, actualiza leads.estado/ts_estado y publica
kaizen.comercial.lead_actualizado.v1 EN LA MISMA transaccion SQLite.

Trigger de aplicacion (canonico 6.1, no trigger SQL): al insertar una
interaccion con argumento_id no nulo se inserta resultado_argumento con el
mapeo fijo, SOLO si la tabla del cubo P8 existe (sin importar codigo de
cubos: el sustrato jamas importa de un cubo).
"""
from __future__ import annotations

import sqlite3

from sustrato import bus
from sustrato.consola import ts_iso8601z

SEGMENTOS = ("cafeteria_especialidad", "restaurante_ticket_30_50", "hotel_boutique",
             "beach_club_tardeo", "otro")
PRIORIDADES = ("ALTA", "MEDIA", "BAJA", "DESCARTADO")
ESTADOS = ("COLD", "CONTACTADO", "INTERESADO", "COMPROMETIDO", "CLIENTE",
           "NO_LLAMAR", "DESCARTADO")

# Matriz cerrada de transiciones legales (canonico seccion 5).
TRANSICIONES_LEGALES: dict[str, tuple[str, ...]] = {
    "COLD": ("CONTACTADO", "NO_LLAMAR", "DESCARTADO"),
    "CONTACTADO": ("INTERESADO", "COLD", "NO_LLAMAR", "DESCARTADO"),
    "INTERESADO": ("COMPROMETIDO", "CONTACTADO", "NO_LLAMAR", "DESCARTADO"),
    "COMPROMETIDO": ("CLIENTE", "INTERESADO", "NO_LLAMAR", "DESCARTADO"),
    "CLIENTE": ("NO_LLAMAR",),
    "NO_LLAMAR": (),                    # terminal salvo orden de operador via CLI
    "DESCARTADO": (),                   # -> COLD solo via CLI de operador
}

# Mapeo fijo interacciones.resultado -> resultado_argumento.resultado (canonico 6.1)
MAPEO_RESULTADO_P8 = {
    "interes": "avanza", "compromiso": "avanza", "pedido": "avanza",
    "neutro": "neutro", "no_contesta": "neutro", "ocupado": "neutro",
    "numero_invalido": "neutro",
    "rechazo": "rechaza",
}

_DDL = """
CREATE TABLE IF NOT EXISTS leads (
  id            TEXT PRIMARY KEY,
  cliente_id    TEXT NOT NULL,
  nombre        TEXT NOT NULL,
  telefono      TEXT,
  municipio     TEXT,
  segmento      TEXT NOT NULL CHECK (segmento IN
    ('cafeteria_especialidad','restaurante_ticket_30_50','hotel_boutique','beach_club_tardeo','otro')),
  prioridad     TEXT NOT NULL CHECK (prioridad IN ('ALTA','MEDIA','BAJA','DESCARTADO')),
  estado        TEXT NOT NULL DEFAULT 'COLD' CHECK (estado IN
    ('COLD','CONTACTADO','INTERESADO','COMPROMETIDO','CLIENTE','NO_LLAMAR','DESCARTADO')),
  robinson_ok   INTEGER,
  ts_creacion   TEXT NOT NULL,
  ts_estado     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transiciones_pipeline (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id   TEXT NOT NULL REFERENCES leads(id),
  de        TEXT NOT NULL,
  a         TEXT NOT NULL,
  motivo    TEXT,
  ts        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interacciones (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id       TEXT NOT NULL REFERENCES leads(id),
  cliente_id    TEXT NOT NULL,
  canal         TEXT NOT NULL CHECK (canal IN
    ('llamada_manual','llamada_ia','email','whatsapp','visita','otro')),
  ts            TEXT NOT NULL,
  duracion_s    INTEGER,
  transcript_ref TEXT,
  resultado     TEXT NOT NULL CHECK (resultado IN
    ('no_contesta','ocupado','numero_invalido','rechazo','neutro','interes','compromiso','pedido')),
  argumento_id  TEXT,
  notas         TEXT
);

CREATE TABLE IF NOT EXISTS compromisos (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id       TEXT NOT NULL REFERENCES leads(id),
  tipo          TEXT NOT NULL CHECK (tipo IN
    ('callback','envio_muestras','reunion','pedido_pendiente','otro')),
  descripcion   TEXT NOT NULL,
  fecha_limite  TEXT NOT NULL,
  estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN
    ('pendiente','cumplido','incumplido','cancelado')),
  interaccion_origen INTEGER REFERENCES interacciones(id),
  ts_creacion   TEXT NOT NULL,
  ts_cierre     TEXT
);

CREATE TABLE IF NOT EXISTS pedidos (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id       TEXT NOT NULL REFERENCES leads(id),
  cliente_id    TEXT NOT NULL,
  descripcion   TEXT NOT NULL,
  importe_eur   REAL,
  ts            TEXT NOT NULL,
  interaccion_origen INTEGER REFERENCES interacciones(id)
);
"""


class TransicionIlegal(ValueError):
    pass


class LeadInexistente(KeyError):
    pass


def instalar(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def insertar_lead(conn: sqlite3.Connection, id: str, nombre: str, segmento: str,
                  prioridad: str, cliente_id: str = "laboratorio", telefono: str | None = None,
                  municipio: str | None = None, estado: str = "COLD",
                  robinson_ok: int | None = None, ts_creacion: str | None = None,
                  ts_estado: str | None = None) -> bool:
    """INSERT OR IGNORE (idempotente). Devuelve True si inserto."""
    ahora = ts_iso8601z()
    with conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO leads (id, cliente_id, nombre, telefono, municipio, "
            "segmento, prioridad, estado, robinson_ok, ts_creacion, ts_estado) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (id, cliente_id, nombre, telefono, municipio, segmento, prioridad,
             estado, robinson_ok, ts_creacion or ahora, ts_estado or ahora))
    return cur.rowcount > 0


# Excepciones reservadas al CLI de operador (canonico 5). Cerradas por ORIGEN y
# por DESTINO: salir de NO_LLAMAR solo devuelve el lead a COLD, nunca directamente
# a un estado de contacto. NO_LLAMAR es opt-out/Robinson; reabrirlo a CONTACTADO de
# un salto era un agujero RGPD/LSSI (auditoria 2026-08-02, G-04).
EXCEPCIONES_OPERADOR: dict[str, tuple[str, ...]] = {
    "NO_LLAMAR": ("COLD",),
    "DESCARTADO": ("COLD",),
}


def transicionar(conn: sqlite3.Connection, lead_id: str, a: str, motivo: str | None = None,
                 _forzar_operador: bool = False) -> None:
    """UNICA puerta de cambio de estado (canonico seccion 5).

    Escribe transiciones_pipeline + actualiza leads + publica
    kaizen.comercial.lead_actualizado.v1, todo en la MISMA transaccion.

    `_forzar_operador` habilita las excepciones reservadas al CLI de operador
    (EXCEPCIONES_OPERADOR: NO_LLAMAR -> COLD y DESCARTADO -> COLD). Exige
    `motivo` no vacio y deja la decision en `decisiones_operador` con su cadena
    de hash, dentro de la MISMA transaccion: o se registran las dos cosas o no
    se hace ninguna.
    """
    if a not in ESTADOS:
        raise TransicionIlegal(f"estado destino desconocido: {a}")
    if _forzar_operador and not (motivo or "").strip():
        raise ValueError(
            "una excepcion de operador exige --motivo no vacio: queda en "
            "decisiones_operador con cadena de hash (canonico 7.4)")

    # La tabla de decisiones vive en gates; asegurarla ANTES de abrir la
    # transaccion (executescript hace COMMIT implicito y la romperia).
    if _forzar_operador:
        from sustrato import gates
        gates.instalar(conn)

    with bus.transaccion(conn):   # BEGIN IMMEDIATE: protege el hash_prev (G-08)
        fila = conn.execute("SELECT estado FROM leads WHERE id=?", (lead_id,)).fetchone()
        if fila is None:
            raise LeadInexistente(lead_id)
        de = fila[0]
        legales = TRANSICIONES_LEGALES.get(de, ())
        excepcion_aplicada = False
        if a not in legales:
            if not (_forzar_operador and a in EXCEPCIONES_OPERADOR.get(de, ())):
                permitido = EXCEPCIONES_OPERADOR.get(de, ())
                extra = (f"; con --operador solo {de} -> {'/'.join(permitido)}"
                         if permitido else "")
                raise TransicionIlegal(
                    f"{de} -> {a} no esta en la matriz cerrada{extra}")
            excepcion_aplicada = True
        ts = ts_iso8601z()
        if excepcion_aplicada:
            from sustrato import gates
            gates.registrar_decision_operador_en_tx(
                conn, "transicion_excepcional",
                {"lead_id": lead_id, "de": de, "a": a, "motivo": motivo})
        conn.execute(
            "INSERT INTO transiciones_pipeline (lead_id, de, a, motivo, ts) VALUES (?,?,?,?,?)",
            (lead_id, de, a, motivo, ts))
        conn.execute("UPDATE leads SET estado=?, ts_estado=? WHERE id=?", (a, ts, lead_id))
        bus.publicar_en_tx(conn, "kaizen.comercial.lead_actualizado.v1", "registro",
                           {"lead_id": lead_id, "de": de, "a": a, "motivo": motivo,
                            "excepcion_operador": excepcion_aplicada})


def _p8_trigger_aplicacion(conn: sqlite3.Connection, interaccion_id: int,
                           lead_id: str, resultado: str, argumento_id: str | None) -> None:
    """Trigger de aplicacion del bucle P8 (canonico 6.1). Sin imports de cubos:
    solo actua si la tabla resultado_argumento existe (la instala el cubo)."""
    if not argumento_id:
        return
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='resultado_argumento'"
    ).fetchone()
    if not existe:
        return
    seg = conn.execute("SELECT segmento FROM leads WHERE id=?", (lead_id,)).fetchone()
    segmento = seg[0] if seg else "otro"
    conn.execute(
        "INSERT OR IGNORE INTO resultado_argumento "
        "(argumento_id, segmento, interaccion_id, resultado, ts) VALUES (?,?,?,?,?)",
        (argumento_id, segmento, interaccion_id, MAPEO_RESULTADO_P8[resultado], ts_iso8601z()))


def insertar_interaccion(conn: sqlite3.Connection, lead_id: str, canal: str, resultado: str,
                         cliente_id: str = "laboratorio", duracion_s: int | None = None,
                         transcript_ref: str | None = None, argumento_id: str | None = None,
                         notas: str | None = None) -> int:
    """Inserta interaccion + evento + trigger P8, misma transaccion."""
    with bus.transaccion(conn):
        cur = conn.execute(
            "INSERT INTO interacciones (lead_id, cliente_id, canal, ts, duracion_s, "
            "transcript_ref, resultado, argumento_id, notas) VALUES (?,?,?,?,?,?,?,?,?)",
            (lead_id, cliente_id, canal, ts_iso8601z(), duracion_s, transcript_ref,
             resultado, argumento_id, notas))
        interaccion_id = int(cur.lastrowid)
        _p8_trigger_aplicacion(conn, interaccion_id, lead_id, resultado, argumento_id)
        bus.publicar_en_tx(conn, "kaizen.comercial.interaccion_registrada.v1", "registro",
                           {"interaccion_id": interaccion_id, "lead_id": lead_id,
                            "canal": canal, "resultado": resultado})
    return interaccion_id


def crear_compromiso(conn: sqlite3.Connection, lead_id: str, tipo: str, descripcion: str,
                     fecha_limite: str, interaccion_origen: int | None = None) -> int:
    with bus.transaccion(conn):
        cur = conn.execute(
            "INSERT INTO compromisos (lead_id, tipo, descripcion, fecha_limite, "
            "interaccion_origen, ts_creacion) VALUES (?,?,?,?,?,?)",
            (lead_id, tipo, descripcion, fecha_limite, interaccion_origen, ts_iso8601z()))
        cid = int(cur.lastrowid)
        bus.publicar_en_tx(conn, "kaizen.comercial.compromiso_creado.v1", "registro",
                           {"compromiso_id": cid, "lead_id": lead_id, "tipo": tipo,
                            "fecha_limite": fecha_limite})
    return cid


def cerrar_compromiso(conn: sqlite3.Connection, compromiso_id: int, estado: str) -> None:
    if estado not in ("cumplido", "incumplido", "cancelado"):
        raise ValueError(f"estado de cierre invalido: {estado}")
    with conn:
        conn.execute("UPDATE compromisos SET estado=?, ts_cierre=? WHERE id=?",
                     (estado, ts_iso8601z(), compromiso_id))


def registrar_pedido(conn: sqlite3.Connection, lead_id: str, descripcion: str,
                     importe_eur: float | None = None, cliente_id: str = "laboratorio",
                     interaccion_origen: int | None = None) -> int:
    with bus.transaccion(conn):
        cur = conn.execute(
            "INSERT INTO pedidos (lead_id, cliente_id, descripcion, importe_eur, ts, "
            "interaccion_origen) VALUES (?,?,?,?,?,?)",
            (lead_id, cliente_id, descripcion, importe_eur, ts_iso8601z(), interaccion_origen))
        pid = int(cur.lastrowid)
        bus.publicar_en_tx(conn, "kaizen.comercial.pedido_registrado.v1", "registro",
                           {"pedido_id": pid, "lead_id": lead_id,
                            "importe_eur": importe_eur})
    return pid
