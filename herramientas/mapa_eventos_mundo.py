"""Genera docs/MAPA_EVENTOS_MUNDO.md: que hace el Mundo con cada familia de eventos del registro (RUE).

Fuente unica: `eventos.json` (los tipos) y `panel_mando/mundo.py` (a que cubo pertenece cada
prefijo). Uso: python herramientas/mapa_eventos_mundo.py [--check]. Solo lee; escribe un fichero.
"""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Gestos que el cliente (mundo/index.html) hace ademas del generico. Declarado aqui a proposito: si el cliente
# cambia, este documento se revisa (el generador comprueba que cada tipo citado exista en eventos.json).
ESPECIALES = OrderedDict([
    ("plataforma.aprobacion.solicitada", "aparece la tarjeta en la ventanilla"),
    ("plataforma.aprobacion.concedida", "la ventanilla se refresca (la tarjeta pasa a mecha o se ejecuta)"),
    ("plataforma.aprobacion.denegada", "la ventanilla se refresca (la tarjeta desaparece)"),
    ("plataforma.aprobacion.revocada", "la ventanilla se refresca (deshecho a tiempo)"),
    ("plataforma.aprobacion.caducada", "la ventanilla se refresca (caducada)"),
    ("plataforma.panico.activado", "el mundo se congela y dice TODO PARADO"),
    ("plataforma.panico.desactivado", "el mundo se reanuda"),
    ("plataforma.coste.techo_alcanzado", "modo ahorro: el gasto se marca y los directores lo dicen"),
    ("comercial.pedido.atribuido", "fuegos artificiales (hanabi) al caer la noche"),
    ("finanzas.cobro.registrado", "fuegos artificiales (hanabi) al caer la noche"),
])


def generar() -> str:
    from panel_mando.mundo import CUBO_POR_PREFIJO_RUE
    tipos = list(json.loads((RAIZ / "eventos.json").read_text(encoding="utf-8"))["tipos"])
    fam = OrderedDict()
    for t in tipos:
        fam.setdefault(t.split(".")[0], []).append(t)
    faltan = [t for t in ESPECIALES if t not in tipos]
    assert not faltan, f"gestos declarados para tipos que no existen: {faltan}"
    L = [f"# MAPA DE EVENTOS DEL MUNDO — generado {date.today().isoformat()}", "",
         "**Tipo:** estado (capa 4, se regenera; no editar a mano) · **Fuente:** `eventos.json` y `panel_mando/mundo.py` · "
         "**Generador:** `python herramientas/mapa_eventos_mundo.py`", "",
         "Regla del juego: **lo que se ve es real**. El Mundo no dibuja nada que no venga de un evento sellado o de la foto "
         "del backend (`docs/CONTRATO_MUNDO.md`). Todo evento con cubo hace lo mismo: el director de ese cubo dice la frase "
         "(la misma que el panel) y una gota de tinta viaja al Registro, que la sella y hace crecer el bambú. Un evento sin cubo "
         "solo hace la gota. Los eventos del bus del sustrato (`kaizen.<cubo>.…`) y del chat de la Colmena entran por el mismo "
         "canal (ver el contrato).", "",
         "## 1. Familias y cubo", "",
         "| Familia (prefijo) | Cubo | Tipos | Gesto |", "|---|---|---|---|"]
    for f, ts in fam.items():
        cubo = CUBO_POR_PREFIJO_RUE.get(f)
        L.append(f"| `{f}` | {cubo or '— (plataforma: sin director)'} | {len(ts)} | "
                 f"{'el director de ese cubo habla + gota al Registro' if cubo else 'gota al Registro'} |")
    L += ["", f"Total: {len(tipos)} tipos en {len(fam)} familias.", "",
          "## 2. Gestos propios (además del genérico)", "", "| Tipo | Gesto |", "|---|---|"]
    L += [f"| `{t}` | {g} |" for t, g in ESPECIALES.items()]
    sin_cubo = [f for f in fam if f not in CUBO_POR_PREFIJO_RUE]
    L += ["", "## 3. Lo que este documento NO afirma", "",
          "- No dice que cada tipo tenga hoy un productor real en el backend: **no se ha auditado tipo a tipo**. Un tipo sin "
          "productor simplemente nunca dispara nada, y el juego no lo simula.",
          "- Familias sin prefijo en el mapa (`CUBO_POR_PREFIJO_RUE`): " + (", ".join(f"`{f}`" for f in sin_cubo) or "ninguna") + ".", ""]
    return "\n".join(L)


def main() -> int:
    salida = RAIZ / "docs" / "MAPA_EVENTOS_MUNDO.md"
    txt = generar()
    if "--check" in sys.argv:
        return 0 if salida.exists() and salida.read_text(encoding="utf-8").split("\n", 1)[1:] == txt.split("\n", 1)[1:] else 1
    salida.write_text(txt, encoding="utf-8"); print(f"escrito {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
