"""Lanzador de la exploracion de nichos: tanda, listar, ver y decidir (A6 del plan de apuestas).

Uso (desde la raiz del repo; en Windows, mejor con lanzadores\\NICHOS.cmd):

    python -X utf8 herramientas/apuestas.py tanda [--ciclos 3] [--horas 8] [--empresa EMPRESA]
    python -X utf8 herramientas/apuestas.py listar [--estado DOSIER]
    python -X utf8 herramientas/apuestas.py ver ID
    python -X utf8 herramientas/apuestas.py elegir ID
    python -X utf8 herramientas/apuestas.py descartar ID [--razon ...]
    python -X utf8 herramientas/apuestas.py probar ID [--umbral N] [--plazo DIAS]
    python -X utf8 herramientas/apuestas.py medir ID --valor N --ref "de donde sale"
    python -X utf8 herramientas/apuestas.py cerrar ID CRECE|PODADA

ID puede ser el identificador completo o los ultimos 6+ caracteres (si es unico). Lo que falte se pregunta.
DECIDE SIEMPRE EL OPERADOR: la regla solo propone. La tanda es UNA orden acotada: no deja nada programado.
Modelo: KAIZEN_EXPLORACION_MODELO=webllm (defecto, gratuito; necesita KAIZEN_WEBLLM_TOKEN en .env) | claude.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import apuestas as A                                   # noqa: E402
from core import exploracion as E                                # noqa: E402
from core.exploracion_busqueda import buscar_ddgs                # noqa: E402
from core.exploracion_modelos import ErrorModelo, cliente_desde_entorno   # noqa: E402

COD_OK, COD_ERROR = 0, 2


class Salida:
    """E/S inyectable para poder probar el lanzador sin consola."""

    def __init__(self, imprimir=print, preguntar=input) -> None:
        self.imprimir = imprimir
        self._preguntar = preguntar

    def pedir(self, texto: str, actual=None) -> str:
        if actual not in (None, ""):
            return str(actual)
        try:
            return (self._preguntar(texto + " ") or "").strip()
        except EOFError:
            return ""


def _dependencias(empresa: str | None) -> dict:
    """Lo REAL: mismo almacen, misma bitacora (mismo genesis) y mismo estado de PARAR TODO que el panel."""
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    from core import rutas as R
    from core import tenants as T
    from core.knowledge import get_knowledge
    from core.panico import Panico
    from core.rue import Bitacora
    k = get_knowledge()
    empresa = empresa or os.environ.get("KAIZEN_EMPRESA") or (sorted(set(k.companies()) - {"plataforma"}) or ["laboratorio"])[0]
    try:
        fecha_alta = T.get_tenant(empresa)["fecha_alta"]
    except Exception:                                            # noqa: BLE001 — igual que el panel
        fecha_alta = ""
    ruta_panico = R.dir_state() / "panico" / "estado.json"
    from core.autonomia import AutonomiaCubos
    from cubos.base import manifiestos_instalados

    def nivel_inteligencia() -> str:
        """Nivel VIGENTE de Inteligencia (override de la empresa o, si no hay, el defecto de su manifest)."""
        import json as _json
        try:
            defecto = _json.loads(manifiestos_instalados()["inteligencia"].read_text(encoding="utf-8")).get("nivel_autonomia_defecto", "CERO")
        except Exception:                                        # noqa: BLE001 — sin manifest legible: lo prudente
            defecto = "CERO"
        return AutonomiaCubos(k, empresa).nivel("inteligencia", defecto)
    return {"k": k, "empresa": empresa, "bitacora": Bitacora(k, empresa, fecha_alta=fecha_alta),
            "nivel_autonomia": nivel_inteligencia,
            "parar": lambda: Panico(ruta_estado=ruta_panico).activo,    # se relee en cada comprobacion
            "informes": R.dir_empresa(empresa) / "exploracion", "cliente": None, "buscar": buscar_ddgs}


def resolver_id(ap: A.Apuestas, texto: str) -> str:
    """Id completo, o el unico id que empiece o acabe por `texto` (minimo 6 caracteres)."""
    texto = (texto or "").strip()
    ids = [x["id"] for x in ap.listar()]
    if texto in ids:
        return texto
    if len(texto) >= 6:
        c = [i for i in ids if i.startswith(texto) or i.endswith(texto)]
        if len(c) == 1:
            return c[0]
        if len(c) > 1:
            raise A.ApuestaInvalida(f"el id {texto!r} es ambiguo ({len(c)} coincidencias): escribe mas caracteres")
    raise A.ApuestaInvalida(f"no hay ninguna apuesta con el id {texto!r} (usa `listar`)")


def _aprendizaje(args, out: Salida) -> dict:
    return {"esperaba": out.pedir("¿Que esperabas que pasara?", args.esperaba),
            "paso": out.pedir("¿Que paso de verdad?", args.paso),
            "haria_distinto": out.pedir("¿Que harias distinto?", args.haria_distinto)}


def _tanda(args, d: dict, out: Salida) -> int:
    cliente = d.get("cliente") or cliente_desde_entorno(d["empresa"])
    ap = A.Apuestas(d["k"], d["empresa"], bitacora=d["bitacora"])
    ctx = E.Contexto(k=d["k"], empresa=d["empresa"], apuestas=ap, cliente=cliente, buscar=d["buscar"],
                     bitacora=d["bitacora"], reloj=d.get("reloj"))
    out.imprimir(f"Tanda de exploracion en «{d['empresa']}»: hasta {args.ciclos} ciclos, {args.horas} h como maximo. "
                 f"Modelo: {getattr(cliente, 'nombre', '?')}.")
    out.imprimir("Puedes parar con PARAR TODO en el panel; se comprueba entre ciclos.")

    def progreso(r: dict) -> None:
        out.imprimir(f"  ciclo {r['ciclo']}: {len(r['dosieres'])} dosieres, {len(r['rechazos'])} rechazados "
                     f"({r['rechazados_por_repeticion']} por repeticion), {r['preguntas_modelo']} preguntas al modelo"
                     + (f"  [PARADA: {r['parar_por']}]" if r["parar_por"] else ""))
    t = E.ejecutar_tanda(ctx, ciclos=args.ciclos, horas_max=args.horas, parar=d["parar"],
                         sello_integro=lambda: d["bitacora"].verificar().get("integra", False),
                         nivel_autonomia=d.get("nivel_autonomia"), al_terminar_ciclo=progreso)
    carpeta = Path(args.informe_dir) if args.informe_dir else Path(d["informes"])
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ruta = carpeta / f"informe_{marca}_{t['tanda_id']}.md"
    ruta.write_text(E.generar_informe(ctx, t), encoding="utf-8")
    out.imprimir(f"\nTerminada: {t['motivo']}. {t['dosieres']} dosieres completos en {t['ciclos_hechos']} ciclos.")
    if t["error"]:
        out.imprimir(f"Aviso: {t['error']}")
    out.imprimir(f"Informe: {ruta}")
    out.imprimir("Siguiente paso: `listar` y `ver ID`; elige con `elegir ID` o descarta con `descartar ID`.")
    return COD_OK


def _listar(args, d: dict, out: Salida) -> int:
    xs = A.Apuestas(d["k"], d["empresa"]).listar(args.estado.upper() if args.estado else None)
    if not xs:
        out.imprimir("No hay apuestas" + (f" en estado {args.estado.upper()}" if args.estado else "") + " todavia.")
        return COD_OK
    for x in xs:
        c = x["coordenadas"]
        out.imprimir(f"{x['id'][-8:]}  {x['estado']:<10} {x['borrador']['titulo'][:70]}  [{c['modelo_ingreso']}/{c['cliente']}/{c['canal']}]")
    out.imprimir("(el id corto son los ultimos 8 caracteres; vale para `ver`, `elegir`, etc.)")
    return COD_OK


def _con_apuesta(args, d: dict, out: Salida, accion) -> int:
    ap = A.Apuestas(d["k"], d["empresa"], bitacora=d["bitacora"])
    r = accion(ap, resolver_id(ap, args.id))
    out.imprimir(f"{r['id'][-8:]}: ahora esta en {r['estado']}.")
    return COD_OK


def _ver(args, d: dict, out: Salida) -> int:
    ap = A.Apuestas(d["k"], d["empresa"])
    x = ap.obtener(resolver_id(ap, args.id))
    out.imprimir("\n".join(E.ficha_markdown(x)))
    return COD_OK


def _elegir(args, d, out):
    return _con_apuesta(args, d, out, lambda ap, i: ap.elegir(i, por=args.por))


def _descartar(args, d, out):
    razon = out.pedir("¿Por que la descartas?", args.razon)
    return _con_apuesta(args, d, out, lambda ap, i: ap.descartar(i, por=args.por, razon=razon, aprendizaje=_aprendizaje(args, out)))


def _probar(args, d, out):
    crit = {k: v for k, v in (("umbral", args.umbral), ("plazo_dias", args.plazo), ("comparador", args.comparador),
                              ("senal", args.senal), ("fuente_dato", args.fuente)) if v is not None}
    return _con_apuesta(args, d, out, lambda ap, i: ap.iniciar_prueba(i, por=args.por, criterio=crit or None))


def _medir(args, d, out):
    valor = out.pedir("Valor medido (un numero):", args.valor)
    ref = out.pedir("¿De donde sale ese numero?", args.ref)
    try:
        v = float(str(valor).replace(",", "."))
    except ValueError:
        raise A.ApuestaInvalida("el valor debe ser un numero") from None

    def hacer(ap, i):
        r = ap.registrar_medicion(i, por=args.por, valor=v, referencia=ref)
        p = r["propuesta_regla"]
        out.imprimir(f"La regla propone {p['decision']} ({p['valor']} {p['comparador']} {p['umbral']}). Decides tu con `cerrar`.")
        return r
    return _con_apuesta(args, d, out, hacer)


def _cerrar(args, d, out):
    return _con_apuesta(args, d, out, lambda ap, i: ap.cerrar(i, args.decision.upper(), por=args.por, aprendizaje=_aprendizaje(args, out)))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="apuestas", description=__doc__.split("\n")[0])
    p.add_argument("--empresa", default=None)
    p.add_argument("--por", default=os.environ.get("KAIZEN_OPERADOR", "operador"), help="quien decide (queda registrado)")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tanda"); t.add_argument("--ciclos", type=int, default=3); t.add_argument("--horas", type=float, default=8.0)
    t.add_argument("--informe-dir", default=None); t.set_defaults(f=_tanda)
    l = sub.add_parser("listar"); l.add_argument("--estado", default=None); l.set_defaults(f=_listar)
    for nombre, f in (("ver", _ver), ("elegir", _elegir), ("descartar", _descartar), ("probar", _probar), ("medir", _medir), ("cerrar", _cerrar)):
        s = sub.add_parser(nombre); s.add_argument("id"); s.set_defaults(f=f)
        if nombre in ("descartar", "cerrar"):
            s.add_argument("--esperaba"); s.add_argument("--paso"); s.add_argument("--haria-distinto", dest="haria_distinto")
        if nombre == "descartar":
            s.add_argument("--razon")
        if nombre == "probar":
            s.add_argument("--umbral", type=float); s.add_argument("--plazo", type=int)
            s.add_argument("--comparador"); s.add_argument("--senal"); s.add_argument("--fuente")
        if nombre == "medir":
            s.add_argument("--valor"); s.add_argument("--ref")
        if nombre == "cerrar":
            s.add_argument("decision", choices=["CRECE", "PODADA", "crece", "podada"])
    return p


def main(argv=None, *, deps: dict | None = None, out: Salida | None = None) -> int:
    out = out or Salida()
    args = _parser().parse_args(argv)
    try:
        d = deps or _dependencias(args.empresa)
        d.setdefault("empresa", args.empresa or "laboratorio")
        return args.f(args, d, out)
    except (A.ApuestaInvalida, ErrorModelo) as e:
        out.imprimir(f"No se pudo: {e}")
        return COD_ERROR
    except KeyboardInterrupt:
        out.imprimir("Interrumpido. Lo ya hecho queda guardado.")
        return COD_ERROR


if __name__ == "__main__":
    sys.exit(main())
