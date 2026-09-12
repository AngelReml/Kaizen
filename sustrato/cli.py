"""CLI del sustrato. Se engancha a kaizen.py de forma aditiva via
comandos_para_kaizen(). Uso directo: python -m sustrato.cli <grupo> <cmd>
"""
from __future__ import annotations

import os

os.environ.setdefault("PYTHONUTF8", "1")

import click

from sustrato import bus as bus_mod
from sustrato.consola import safe_print


@click.group()
def cli() -> None:
    """Sustrato Kaizen."""


# ---------------------------------------------------------------- grupo bus
@cli.group()
def bus() -> None:
    """Bus de eventos del sustrato (data/kaizen.db)."""


@bus.command(name="verificar-cadena")
def bus_verificar_cadena() -> None:
    """Recorre bus_eventos y verifica la cadena de hash (canonico 4.4)."""
    conn = bus_mod.conexion()
    bus_mod.instalar(conn)
    safe_print(bus_mod.verificar_cadena(conn))


@bus.command(name="reintentar")
@click.argument("evento_id", type=int)
@click.argument("consumidor")
def bus_reintentar(evento_id: int, consumidor: str) -> None:
    """Reintento manual de un consumo en ERROR (canonico 4.3)."""
    conn = bus_mod.conexion()
    bus_mod.instalar(conn)
    safe_print(f"resultado: {bus_mod.reintentar(conn, evento_id, consumidor)}")


@bus.command(name="metrica-diaria")
def bus_metrica_diaria() -> None:
    """Registra y muestra la metrica diaria del bus (canonico 4.5)."""
    conn = bus_mod.conexion()
    bus_mod.instalar(conn)
    safe_print(bus_mod.metrica_diaria(conn))


# ------------------------------------------------------------ grupo registro
@cli.group()
def registro() -> None:
    """Registro P9: la verdad comercial (canonico seccion 5)."""


@registro.command(name="migrar")
@click.option("--desde", default=None, help="ruta a knowledge.json (defecto: state/knowledge.json)")
@click.option("--cliente", default="laboratorio", show_default=True)
def registro_migrar(desde, cliente):
    """Migra leads reales de knowledge.json a la tabla leads (aditivo, con
    copia previa de la BD si existe; jamas toca knowledge.json)."""
    from pathlib import Path
    from cubos.comercial import adaptador
    conn = bus_mod.conexion()
    ruta_db = Path(os.environ.get("KAIZEN_DB_PATH") or bus_mod.ruta_db_defecto())
    resumen = adaptador.migrar_desde_knowledge(
        conn, Path(desde) if desde else None, cliente_id=cliente,
        ruta_db_para_backup=ruta_db)
    safe_print(f"migracion: {resumen}")


@registro.command(name="sync")
@click.option("--desde", default=None, help="ruta a knowledge.json (defecto: state/knowledge.json)")
def registro_sync(desde):
    """Sincroniza TODAS las empresas del knowledge al registro P9 (D11 E1.3).

    Idempotente (INSERT OR IGNORE, jamas toca knowledge.json). Pensado para
    REVISION DIARIA: el registro vacio del 2026-08-02 no puede volver a pasar."""
    import json as _json
    from pathlib import Path
    from cubos.comercial import adaptador
    conn = bus_mod.conexion()
    ruta = Path(desde) if desde else Path(adaptador.ruta_knowledge_defecto())
    if not ruta.exists():
        safe_print(f"SIN KNOWLEDGE: {ruta} no existe; nada que sincronizar.")
        return
    datos = _json.loads(ruta.read_text(encoding="utf-8"))
    empresas = sorted(c for c, v in datos.items()
                      if isinstance(v, dict) and v.get("lead"))
    if not empresas:
        safe_print("knowledge sin empresas con leads; nada que sincronizar.")
        return
    total_nuevos = 0
    for c in empresas:
        resumen = adaptador.migrar_desde_knowledge(conn, ruta, cliente_id=c,
                                                   ruta_db_para_backup=None)
        total_nuevos += resumen["insertados"]
        safe_print(f"{c:<18} insertados={resumen['insertados']} "
                   f"ya_existian={resumen['ya_existian']} corpus={resumen['total_corpus']}")
    safe_print(f"sync OK: {len(empresas)} empresa(s), {total_nuevos} lead(s) nuevos")


@registro.command(name="transicionar")
@click.argument("lead_id")
@click.argument("a")
@click.option("--motivo", required=True, help="motivo de la transicion")
@click.option("--operador", is_flag=True, default=False,
              help="habilita las excepciones reservadas al operador")
def registro_transicionar(lead_id, a, motivo, operador):
    """Transicion de pipeline via la UNICA puerta (canonico seccion 5)."""
    from sustrato import registro as registro_mod
    conn = bus_mod.conexion()
    registro_mod.instalar(conn)
    registro_mod.transicionar(conn, lead_id, a, motivo, _forzar_operador=operador)
    safe_print(f"OK: {lead_id} -> {a}")


# ------------------------------------------------------------ comando director
@cli.command(name="director")
@click.option("--html", "como_html", is_flag=True, default=False,
              help="genera panel/director.html estatico")
def director_cmd(como_html):
    """Panel del Director, solo lectura (canonico seccion 8)."""
    from panel import director as panel_director
    conn = bus_mod.conexion()
    if como_html:
        destino = panel_director.render_html(conn)
        safe_print(f"HTML generado: {destino}")
    else:
        panel_director.render_cli(conn)


# ---------------------------------------------------------------- grupo p8
@cli.group()
def p8() -> None:
    """Bucle de datos vertical P8 (canonico seccion 6)."""


@p8.command(name="ranking")
@click.option("--segmento", default=None, help="filtra por segmento canonico")
def p8_ranking(segmento):
    """Tabla argumento | segmento | n | tasa_avance | ranking."""
    from cubos.comercial import p8_bucle
    conn = bus_mod.conexion()
    p8_bucle.instalar(conn)
    safe_print(p8_bucle.tabla_cli(conn, segmento))


# ------------------------------------------------------------ grupo operador
@cli.group()
def operador() -> None:
    """Candado del operador (canonico 7.4): relajar es solo humano."""


@operador.command(name="set-autonomia")
@click.argument("cubo")
@click.argument("nivel")
@click.option("--motivo", required=True, help="motivo no vacio (queda con hash)")
def operador_set_autonomia(cubo, nivel, motivo):
    """Fija el nivel de autonomia de un cubo (CERO|BAJA|MEDIA|ALTA)."""
    from sustrato import gates
    conn = bus_mod.conexion()
    gates.instalar(conn)
    gates.set_autonomia(conn, cubo, nivel, motivo, es_operador=True)
    safe_print(f"autonomia de {cubo}: {gates.nivel_vigente(conn, cubo)}")


@operador.command(name="set-limite-coste")
@click.argument("eur", type=float)
@click.option("--motivo", required=True, help="motivo no vacio (queda con hash)")
def operador_set_limite(eur, motivo):
    """Fija el limite diario de coste en EUR."""
    from sustrato import gates
    conn = bus_mod.conexion()
    gates.instalar(conn)
    gates.set_limite_coste(conn, eur, motivo, es_operador=True)
    safe_print(f"limite diario: {eur:.2f} EUR")


@operador.command(name="verificar-cadenas")
def operador_verificar_cadenas():
    """Verifica las cadenas de hash de verificaciones y decisiones."""
    from sustrato import gates
    conn = bus_mod.conexion()
    gates.instalar(conn)
    safe_print(f"verificaciones: {gates.verificar_cadena(conn, 'verificaciones')}")
    safe_print(f"decisiones_operador: {gates.verificar_cadena(conn, 'decisiones_operador')}")


# ------------------------------------------------------------- grupo forense
@cli.group()
def forense() -> None:
    """Verificacion forense (canonico 7.6)."""


@forense.command(name="diario")
def forense_diario():
    """Compromisos vencidos + integridad de las 3 cadenas + coste vs limite."""
    import json as _json
    from sustrato import coste as coste_mod
    from sustrato import forense as forense_mod
    from sustrato import gates as gates_mod
    from sustrato import registro as registro_mod
    conn = bus_mod.conexion()
    bus_mod.instalar(conn); registro_mod.instalar(conn)
    gates_mod.instalar(conn); coste_mod.instalar(conn)
    r = forense_mod.diario(conn)
    safe_print(_json.dumps(r, ensure_ascii=False, indent=2))


# --------------------------------------------------------------- grupo cubos
@cli.group()
def cubos() -> None:
    """Catalogo de cubos con contrato canonico (seccion 3)."""


@cubos.command(name="estado")
def cubos_estado():
    """Salud de TODOS los cubos instalados (arranque sin pares garantizado)."""
    from cubos import base as cubos_base
    conn = bus_mod.conexion()
    bus_mod.instalar(conn)
    for nombre in cubos_base.manifiestos_instalados():
        cubo = cubos_base.construir(nombre, conn=conn)
        cubo.instalar(); cubo.arrancar()
        s = cubo.salud()
        c = s["contadores"]
        contadores = " ".join(f"{k}={v}" for k, v in c.items())
        safe_print(f"{s['cubo']:<17} {s['estado']:<9} {s['detalle'][:46]:<46} {contadores}")
        cubo.parar()


@cubos.command(name="validar")
def cubos_validar():
    """Valida el manifest de cada cubo instalado."""
    from sustrato.config import validar_manifest
    from cubos import base as cubos_base
    for nombre, ruta in cubos_base.manifiestos_instalados().items():
        validar_manifest(ruta)
        safe_print(f"{nombre:<17} manifest VALIDO")


# ----------------------------------------------------------------- grupo mesa
@cli.group()
def mesa() -> None:
    """Mesa del Jefe: la bandeja de decisiones (propuestas)."""


@mesa.command(name="proponer-demo")
@click.option("--n", default=2, show_default=True, help="numero de tarjetas de demo")
@click.option("--cliente", default="laboratorio", show_default=True)
def mesa_proponer_demo(n, cliente):
    """Crea tarjetas de DEMO con leads reales y texto de plantilla (sin IA).

    Sirve para ver la Mesa funcionando HOY. Las tarjetas van marcadas como
    [DEMO]; el ritual real con IA las sustituira (S2 del plan)."""
    from sustrato import propuestas as prop
    from sustrato import registro as reg
    conn = bus_mod.conexion()
    bus_mod.instalar(conn); reg.instalar(conn); prop.instalar(conn)
    # R-TENANT: sin filtro por cliente_id esto seleccionaba leads de CUALQUIER
    # tenant y creaba la tarjeta sin declarar de quien era.
    leads = conn.execute(
        "SELECT id, nombre, segmento FROM leads WHERE cliente_id=? AND estado='COLD' "
        "AND prioridad='ALTA' ORDER BY id LIMIT ?", (cliente, n)).fetchall()
    if not leads:
        safe_print(f"SIN DATOS: no hay leads COLD de prioridad ALTA para '{cliente}' "
                   f"(ejecuta registro migrar).")
        return
    # R-TENANT: el sustrato no lleva dentro el texto de venta de ningun cliente.
    # Los datos del remitente salen del perfil y la firma del tenant; si no hay
    # perfil, la plantilla queda generica en vez de inventar una identidad.
    from core.empresa import cargar_perfil_empresa
    from departments.brand import config as brand_cfg
    perfil = cargar_perfil_empresa(cliente)
    firma = brand_cfg.cargar_firma(cliente)
    emisor = perfil.get("nombre") or cliente
    quien = firma.get("remitente_nombre") or "el responsable comercial"
    for lid, nombre, segmento in leads:
        cuerpo = (f"Buenos dias. Le escribo desde {emisor}. "
                  f"Trabajamos con negocios como {nombre} y creo que lo nuestro "
                  f"puede encajar con su carta. Sin compromiso, me gustaria "
                  f"enviarle informacion y, si le interesa, unas muestras.\n\n"
                  f"Un saludo cordial,\n{quien}\n\n"
                  f"[DEMO: texto de plantilla; el definitivo lo escribira el departamento "
                  f"con el argumentario y lo filtrara brand antes de llegar aqui]")
        pid = prop.crear(conn, "comercial", "email_presentacion",
                         f"Presentarnos a {nombre}",
                         f"Primer contacto por email con {nombre} ({segmento}). "
                         f"Sin precios, sin promesas; solo presentacion y ofrecer muestras.",
                         cuerpo, lead_id=lid, cliente_id=cliente)
        safe_print(f"tarjeta creada #{pid}: {nombre}")
    safe_print("Abre la Mesa (doble clic en 'MESA DEL JEFE.cmd') para decidir.")


@mesa.command(name="estado")
def mesa_estado():
    """Cuantas propuestas hay en cada estado."""
    from sustrato import propuestas as prop
    conn = bus_mod.conexion()
    bus_mod.instalar(conn); prop.instalar(conn)
    filas = conn.execute(
        "SELECT estado, COUNT(*) FROM propuestas GROUP BY estado ORDER BY estado").fetchall()
    if not filas:
        safe_print("(sin propuestas todavia)")
    for estado, cuenta in filas:
        safe_print(f"{estado:<10} {cuenta}")


# ---------------------------------------------------------------- grupo ritual
@cli.group()
def ritual() -> None:
    """Rituales de los cubos (S2: la manana comercial)."""


@ritual.command(name="manana")
@click.option("--n", default=3, show_default=True, help="tarjetas a intentar (max 5)")
@click.option("--cliente", default="laboratorio", show_default=True)
def ritual_manana_cmd(n, cliente):
    """Fabrica tarjetas REALES para la Mesa: seleccion + IA + brand guardian.

    Usa el modelo real (gasta dinero, con hard stop delante). No envia nada:
    las tarjetas esperan el SI del jefe."""
    from sustrato import coste as coste_mod
    from sustrato import registro as reg
    from cubos.comercial import ritual_manana
    conn = bus_mod.conexion()
    bus_mod.instalar(conn); reg.instalar(conn); coste_mod.instalar(conn)
    r = ritual_manana.generar(conn, n=n, cliente_id=cliente)
    safe_print(f"seleccionados={r['seleccionados']} creadas={r['creadas']} "
               f"descartadas={r['descartadas']}")
    for m in r["motivos"]:
        safe_print(f"  descartado: {m}")
    gastado = coste_mod.comprobar_limite(conn)
    safe_print(f"gasto del dia: {gastado:.2f} EUR (limite {coste_mod.limite_vigente(conn):.2f})")


# ------------------------------------------------------- integracion kaizen.py
def comandos_para_kaizen() -> list:
    """Comandos/grupos que kaizen.py registra de forma aditiva."""
    return [bus, registro, director_cmd, p8, operador, forense, cubos, mesa, ritual]


if __name__ == "__main__":
    cli()
