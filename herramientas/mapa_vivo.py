# -*- coding: utf-8 -*-
"""MAPA VIVO — registro obligatorio de cada accion sobre el repo KAIZEN.

Regenera docs/MAPA_VIVO.md desde la historia git COMPLETA
(--all), el estado del arbol de trabajo y un bloque de sesiones manual que
se preserva entre regeneraciones. Pensado para el hook pre-commit
fail-closed: ningun commit entra sin actualizar el mapa (L2 "nada
invisible", D00 §8.2).

Uso (desde la raiz del repo, o desde cualquier subcarpeta):
    python -X utf8 herramientas/mapa_vivo.py --generar     # regenerar entero
    python -X utf8 herramientas/mapa_vivo.py --pre-commit  # modo hook: añade el commit en curso
    python -X utf8 herramientas/mapa_vivo.py --verificar   # cobertura 100% de commits o exit 1
    python -X utf8 herramientas/mapa_vivo.py --linea-base  # imprime solo "N passed / M skipped" vigente

Garantias:
- Solo stdlib. Solo LECTURA de git. El unico fichero que escribe es docs/MAPA_VIVO.md.
- Jamas toca la red (R1 de CORRECCIONES).
- Un commit hecho saltandose el hook (--no-verify, espejo de sandbox) queda
  sellado RETROACTIVAMENTE en la siguiente regeneracion: sale de git log,
  no de la buena voluntad de nadie. --verificar detecta cualquier hueco.
"""
import os
import re
import subprocess
import sys
from datetime import datetime

FICHERO = "docs/MAPA_VIVO.md"
MARCA_INI = "<!-- SESIONES:INICIO (bloque manual: el generador lo preserva) -->"
MARCA_FIN = "<!-- SESIONES:FIN -->"
SEP_REG = "\x1e"
SEP_CAMPO = "\x1f"


def _git(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("git %s -> rc=%d: %s" % (" ".join(args), r.returncode,
                                                    (r.stderr or "").strip()[:300]))
    return r.stdout


def ir_a_raiz():
    raiz = _git("rev-parse", "--show-toplevel").strip()
    os.chdir(raiz)
    return raiz


def historial():
    """Todos los commits de todas las ramas, mas reciente primero, con ficheros."""
    crudo = _git("log", "--all", "--date=short", "--name-only",
                 "--format=%s%%H%s%%h%s%%ad%s%%an%s%%s" % (SEP_REG, SEP_CAMPO, SEP_CAMPO, SEP_CAMPO, SEP_CAMPO))
    commits, vistos = [], set()
    for bloque in crudo.split(SEP_REG):
        bloque = bloque.strip("\n")
        if not bloque.strip():
            continue
        lineas = bloque.split("\n")
        campos = lineas[0].split(SEP_CAMPO)
        if len(campos) < 5:
            continue
        completo, corto, fecha, autor, msj = campos[0], campos[1], campos[2], campos[3], campos[4]
        if completo in vistos:
            continue
        vistos.add(completo)
        ficheros = [l for l in lineas[1:] if l.strip()]
        commits.append({"hash": corto, "completo": completo, "fecha": fecha,
                        "autor": autor, "msj": msj, "ficheros": ficheros})
    return commits


def ramas():
    salida = _git("branch", "--format=%(refname:short) %(objectname:short)")
    return [l.strip() for l in salida.strip().split("\n") if l.strip()]


def linea_base():
    try:
        with open("docs/LINEA_BASE.md", encoding="utf-8") as f:
            filas = re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|", f.read(), re.M)
        if filas:
            # La tabla es un historial en orden de insercion (R6: "solo puede
            # subir"), no un conjunto ordenable solo por fecha: varios dias
            # tienen mas de una fila (p.ej. tres el 2026-08-07). La vigente es
            # la ULTIMA fila del fichero, no la de "max fecha" (con empate,
            # max() se queda con la primera que ve, no con la mas reciente).
            vigente = filas[-1]
            return "%s (%s)" % (vigente[1], vigente[0])
    except OSError:
        pass
    return "docs/LINEA_BASE.md no legible"


def cifra_vigente():
    """Solo la cifra "N passed / M skipped" de la fila vigente (fecha maxima),
    sin el resto de la descripcion ni marcado markdown. Usado por los
    lanzadores .cmd (COMMIT LOCAL, INSTALACION LIMPIA) para no incrustar un
    literal desfasado."""
    texto = linea_base()
    m = re.search(r"(\d+)\s*passed\s*/\s*(\d+)\s*skipped", texto)
    if m:
        return "%s passed / %s skipped" % (m.group(1), m.group(2))
    return texto


def pendientes():
    salida = _git("status", "--porcelain")
    return [l for l in salida.rstrip("\n").split("\n") if l.strip()]


def staged():
    salida = _git("diff", "--cached", "--name-status")
    return [l for l in salida.rstrip("\n").split("\n") if l.strip()]


def bloque_sesiones():
    if os.path.exists(FICHERO):
        with open(FICHERO, encoding="utf-8") as f:
            texto = f.read()
        i, j = texto.find(MARCA_INI), texto.find(MARCA_FIN)
        if i != -1 and j != -1 and j > i:
            return texto[i + len(MARCA_INI):j].strip("\n")
    return "(sin entradas manuales todavia — cada sesion de trabajo añade aqui su linea: fecha, que se hizo, acta/informe, gasto)"


def construir(modo):
    commits = historial()
    head = _git("rev-parse", "--short", "HEAD").strip()
    rama = _git("rev-parse", "--abbrev-ref", "HEAD").strip()
    pend = pendientes()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    sesiones = bloque_sesiones()

    p = []
    p.append("# MAPA VIVO — registro obligatorio de cada accion sobre KAIZEN")
    p.append("")
    p.append("> AUTOGENERADO por `herramientas/mapa_vivo.py`. No editar a mano salvo el bloque")
    p.append("> de sesiones (§4). Ultima regeneracion: **%s** · HEAD: `%s` (%s) ·" % (ahora, head, rama))
    p.append("> commits cubiertos: **%d/%d** (todas las ramas)." % (len(commits), len(commits)))
    p.append("")
    p.append("## §0. Regla de obligatoriedad (L2: nada invisible)")
    p.append("")
    p.append("Cada commit DEBE llevar este mapa actualizado. Lo garantiza el hook")
    p.append("`.git/hooks/pre-commit` (fail-closed: si la regeneracion falla, el commit se")
    p.append("aborta). Instalacion/reparacion con doble clic: `MAPA VIVO.cmd` (tambien lo")
    p.append("hace `COMMIT LOCAL.cmd` antes de cada commit). Un commit que entrara por otra")
    p.append("via (espejo del sandbox, --no-verify) queda sellado RETROACTIVAMENTE en la")
    p.append("siguiente regeneracion, porque la fuente es `git log --all`, no la memoria de")
    p.append("nadie. Verificacion de cobertura: `python -X utf8 herramientas/mapa_vivo.py --verificar`")
    p.append("(exit 1 si falta cualquier commit en este fichero).")
    p.append("")
    p.append("El hash del commit en curso no puede figurar dentro de si mismo (el hash se")
    p.append("calcula despues): entra como \"commit en curso\" con sus ficheros y queda")
    p.append("sellado con hash en la primera regeneracion posterior. Por induccion, el mapa")
    p.append("de HEAD siempre cubre la historia completa.")
    p.append("")
    p.append("## §1. Estado vigente")
    p.append("")
    p.append("- Rama: **%s** · HEAD: `%s`" % (rama, head))
    p.append("- Linea base de tests (R6, solo sube): **%s**" % linea_base())
    p.append("- Ramas locales: %s" % ("; ".join("`%s`" % r for r in ramas()) or "(solo master)"))
    if pend:
        p.append("- Cambios SIN commit ahora mismo (%d):" % len(pend))
        for l in pend[:40]:
            p.append("    - `%s`" % l.strip())
        if len(pend) > 40:
            p.append("    - ... y %d mas (git status)" % (len(pend) - 40))
    else:
        p.append("- Cambios sin commit: ninguno (arbol limpio).")
    p.append("")
    if modo == "pre-commit":
        s = staged()
        p.append("## §2. Commit EN CURSO (se sella con hash en la proxima regeneracion)")
        p.append("")
        p.append("- Momento: %s · ficheros staged (%d):" % (ahora, len(s)))
        for l in s:
            p.append("    - `%s`" % l.strip())
        p.append("")
    p.append("## §3. Cronologia completa de commits (mas reciente primero)")
    p.append("")
    for c in commits:
        p.append("- **%s** · `%s` · %s" % (c["fecha"], c["hash"], c["msj"]))
        if c["ficheros"]:
            p.append("    - %d fichero(s): %s" % (len(c["ficheros"]),
                     ", ".join("`%s`" % f for f in c["ficheros"])))
    p.append("")
    p.append("## §4. Sesiones y acciones fuera de git (bloque manual preservado)")
    p.append("")
    p.append(MARCA_INI)
    p.append(sesiones)
    p.append(MARCA_FIN)
    p.append("")
    p.append("## §5. Cobertura")
    p.append("")
    p.append("- Commits en git (todas las ramas): %d · registrados en este mapa: %d · huecos: 0." % (len(commits), len(commits)))
    p.append("- Verificar en cualquier momento: `python -X utf8 herramientas/mapa_vivo.py --verificar`")
    p.append("")
    p.append("Relacionados: [[LINEA_BASE]]")
    p.append("")
    return "\n".join(p)


def generar(modo):
    contenido = construir(modo)
    with open(FICHERO, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)
    n = len(historial())
    print("[MAPA VIVO] OK: %s regenerado, %d commits registrados (modo %s)." % (FICHERO, n, modo))
    return 0


def verificar():
    if not os.path.exists(FICHERO):
        print("[MAPA VIVO] FALLO: no existe %s. Ejecuta --generar." % FICHERO)
        return 1
    with open(FICHERO, encoding="utf-8") as f:
        texto = f.read()
    registrados = set(re.findall(r"`([0-9a-f]{7,40})`", texto))
    head = _git("rev-parse", "--short", "HEAD").strip()
    head_completo = _git("rev-parse", "HEAD").strip()
    commits = historial()
    faltan, head_pendiente = [], False
    for c in commits:
        if c["hash"] in registrados or c["completo"] in registrados:
            continue
        if c["completo"] == head_completo:
            # Invariante del diseño: HEAD entra como "commit en curso" sin hash
            # (un commit no puede contener su propio hash) y se sella en la
            # siguiente regeneracion. Solo HEAD tiene esta gracia.
            head_pendiente = True
            continue
        faltan.append("%s %s (%s)" % (c["hash"], c["msj"][:60], c["fecha"]))
    if faltan:
        print("[MAPA VIVO] FALLO: %d commit(s) SIN registrar en %s:" % (len(faltan), FICHERO))
        for l in faltan[:20]:
            print("  - %s" % l)
        print("[MAPA VIVO] Ejecuta: python -X utf8 herramientas/mapa_vivo.py --generar")
        return 1
    if head_pendiente:
        print("[MAPA VIVO] OK: cobertura completa (%d commits; HEAD %s como commit-en-curso, se sella en la proxima regeneracion)." % (len(commits), head))
    else:
        print("[MAPA VIVO] OK: cobertura completa (%d commits, HEAD %s sellado)." % (len(commits), head))
    return 0


def main():
    modo = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else "generar"
    try:
        ir_a_raiz()
    except Exception as e:
        print("[MAPA VIVO] FALLO: no estoy dentro de un repo git (%s)." % e)
        return 1
    try:
        if modo == "verificar":
            return verificar()
        if modo in ("generar", "pre-commit"):
            return generar(modo)
        if modo == "linea-base":
            print(cifra_vigente())
            return 0
        print("[MAPA VIVO] modo desconocido: %s (usa --generar | --pre-commit | --verificar | --linea-base)" % modo)
        return 2
    except Exception as e:
        print("[MAPA VIVO] FALLO: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
