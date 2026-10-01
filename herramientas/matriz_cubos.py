"""Genera docs/MATRIZ_CUBOS.md desde los manifests, el catálogo y el árbol (capa 4: estado, se regenera).

Uso: python herramientas/matriz_cubos.py [--check]
Solo lectura sobre el producto; solo escribe docs/MATRIZ_CUBOS.md. Cada columna sale de una
fuente comprobable; lo que no se puede derivar aparece como «no determinado», nunca inventado.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Correspondencia dossier <-> cubo: explícita porque los nombres no coinciden (declarada, no derivada).
DOSSIER = {
    "comercial": "D01", "brand": "D02", "customer_success": "D03 (NO EXISTE)", "finanzas": "D04",
    "ops": "D05", "marketing": "D06", "inteligencia": "D07", "legal": "D08 (Cumplimiento, fusionado)",
    "qa": "— (sin dossier)", "rrhh": "— (sin dossier; D00 lo deja ABIERTO)",
}
# Nombre del cubo en catalogo.py cuando difiere del manifest.
CATALOGO_NOMBRE = {"ops": "operaciones", "inteligencia": "inteligencia_mercado", "qa": "opengravity"}


def _catalogo() -> dict:
    src = (RAIZ / "departments" / "catalogo.py").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'"name":\s*"([^"]+)".*?"estado":\s*"([^"]+)"', src):
        out[m.group(1)] = m.group(2)
    return out


def _n_herramientas(cubo: str) -> str:
    p = RAIZ / "panel_mando" / "herramientas" / f"{cubo}.py"
    if not p.exists():
        return "0"
    return str(len(re.findall(r"^\s+\"[a-z_]+\":\s*ToolSpec\(", p.read_text(encoding="utf-8"), re.M)))


def _n_py(cubo: str) -> int:
    d = RAIZ / "departments" / cubo
    return len(list(d.rglob("*.py"))) if d.exists() else 0


def _n_tests(cubo: str) -> int:
    pat = re.compile(rf"(departments[./]{cubo}\b|cubos[./]{cubo}\b|herramientas_{cubo}\b)")
    return sum(1 for f in (RAIZ / "tests").glob("test_*.py") if pat.search(f.read_text(encoding="utf-8", errors="ignore")))


def _consume_en_codigo_rrhh() -> list[str]:
    tree = ast.parse((RAIZ / "departments" / "rrhh" / "agente.py").read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "consume" for t in n.targets):
            return [ast.unparse(e).split(".")[-1] for e in n.value.elts]
    return []


def main() -> int:
    man = {p.parent.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted((RAIZ / "cubos").glob("*/manifest.json"))}
    cat = _catalogo()
    productores = {ev: c for c, m in man.items() for ev in m.get("produce", [])}
    consumidos = {ev for m in man.values() for ev in m.get("consume", [])}
    L = [f"# MATRIZ DE CUBOS — generada {date.today().isoformat()}",
         "",
         "**Tipo:** estado (capa 4, se regenera; no editar a mano) · **Fuente:** `cubos/*/manifest.json`, `departments/catalogo.py`, árbol y tests · **Generador:** `python herramientas/matriz_cubos.py`",
         "",
         "«Cableado» y «verificado en vida real» NO se pueden derivar de los manifests: aparecen como no determinado hasta que exista acta.",
         "",
         "## 1. Matriz", "",
         "| Cubo | Misión (manifest) | Dossier | Autonomía | Produce | Consume | Irreversibles | Catálogo | .py | Tests* | Herramientas panel |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, m in man.items():
        cn = CATALOGO_NOMBRE.get(c, c)
        est = cat.get(cn, "AUSENTE")
        flag = "" if cn == c else f" (`{cn}`)"
        irr = ", ".join(m.get("acciones_irreversibles", [])) or "—"
        L.append(f"| {c} | {m.get('descripcion','')} | {DOSSIER.get(c,'?')} | {m.get('nivel_autonomia_defecto')} | {len(m.get('produce',[]))} | {len(m.get('consume',[]))} | {irr} | {est}{flag} | {_n_py(c)} | {_n_tests(c)} | {_n_herramientas(c)} |")
    L += ["", "\\* ficheros de test que mencionan el cubo (heurística por texto; no es cobertura).", "",
          "## 2. Grafo de eventos (declarado en manifests)", "",
          "| Evento | Productor | Consumidores |", "|---|---|---|"]
    for ev, prod in sorted(productores.items()):
        cons = [c for c, m in man.items() if ev in m.get("consume", [])]
        L.append(f"| `{ev}` | {prod} | {', '.join(cons) or '**nadie**'} |")
    huerfanos = sorted(consumidos - set(productores))
    L += ["", f"Eventos consumidos sin productor declarado: {', '.join(huerfanos) or 'ninguno'}.", "",
          "## 3. Divergencias detectadas (estado real vs declarado)", ""]
    div = []
    for c, m in man.items():
        cn = CATALOGO_NOMBRE.get(c, c)
        if cn != c:
            div.append(f"- **Nombre doble:** el cubo `{c}` (manifest) es `{cn}` en el catálogo.")
    r = man.get("rrhh", {})
    if r.get("nota_estado") and cat.get("rrhh") == "construido":
        div.append(f"- **RRHH:** el manifest dice «{r['nota_estado']}» pero el catálogo lo marca `construido`.")
        ref = re.search(r"\((docs/[^)]+)\)", r["nota_estado"])
        if ref and not (RAIZ / ref.group(1)).exists():
            div.append(f"- **RRHH:** el documento citado `{ref.group(1)}` no existe en el repo.")
    if r.get("consume") == [] and _consume_en_codigo_rrhh():
        div.append(f"- **RRHH:** el manifest declara `consume: []`, pero el código consume {', '.join(_consume_en_codigo_rrhh())}.")
    for c, d in DOSSIER.items():
        if "NO EXISTE" in d:
            div.append(f"- **Dossier ausente:** `{c}` cita {d}; los otros dossiers lo mencionan como «siguiente de la serie».")
    sin = [ev for ev in productores if not any(ev in m.get("consume", []) for m in man.values())]
    div.append(f"- **Eventos sin ningún consumidor declarado:** {len(sin)} de {len(productores)} (ver tabla 2); solo {len(productores) - len(sin)} están cableados por contrato entre cubos.")
    L += div + ["", "## 4. No determinado desde el código", "",
                "Cableado en flujo real, verificación en vida real y salud viva por tenant: requieren acta o lectura del bus en ejecución.", ""]
    out = "\n".join(L)
    dest = RAIZ / "docs" / "MATRIZ_CUBOS.md"
    if "--check" in sys.argv:
        return 0 if dest.exists() and dest.read_text(encoding="utf-8").split("\n", 1)[1:] == out.split("\n", 1)[1:] else 1
    dest.write_text(out, encoding="utf-8")
    print(f"escrito {dest} ({len(out)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
