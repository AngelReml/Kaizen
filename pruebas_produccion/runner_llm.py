# -*- coding: utf-8 -*-
"""Runner de pruebas de produccion CON LLM real (C-1, S-2). Ejecutar en la maquina
del operador (necesita su .env). Hard stop DELANTE de cada llamada contra el tope
de sesion aprobado (10 EUR, state/presupuesto/sesion_20260710.json). Coste cargado
por estimacion CONSERVADORA fija por llamada (sobreestima; se anota en el acta).

Uso:  python pruebas_produccion/runner_llm.py c1   (detector vs corpus congelado)
      python pruebas_produccion/runner_llm.py s2   (brand LLM real sobre mensajes AIACT)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

EST_DETECTOR_EUR = 0.012   # por caso (conservador, clase ESTANDAR)
EST_BRAND_EUR = 0.008      # por pieza (Haiku)
PRES = RAIZ / "state" / "presupuesto" / "sesion_20260710.json"


def presupuesto():
    return json.loads(PRES.read_text(encoding="utf-8"))


def cobrar(est: float) -> None:
    """Hard stop DELANTE (R2/B4): si no cabe, NO se llama."""
    p = presupuesto()
    if p["gastado_eur"] + est > p["tope_eur"]:
        raise SystemExit(f"HARD STOP: {p['gastado_eur']:.3f} + {est:.3f} > tope {p['tope_eur']} EUR")
    p["gastado_eur"] = round(p["gastado_eur"] + est, 6)
    PRES.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


def _requiere_env():
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    import os
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")):
        raise SystemExit("Falta .env con clave (ejecutar en la maquina del operador). Nada gastado.")


def c1():
    """C-1: DetectorCompromisos REAL contra el corpus congelado (34 casos)."""
    _requiere_env()
    from core.compromisos import DetectorCompromisos
    corpus = json.loads((RAIZ / "docs" / "corpus_compromisos_c0_v1.json").read_text(encoding="utf-8"))
    casos = corpus["casos"]
    res, criticos = [], []
    tp = fp = fn = 0
    for c in casos:
        cobrar(EST_DETECTOR_EUR)
        det = DetectorCompromisos(fecha_referencia_utc=datetime.fromisoformat(c["fecha_referencia"]))
        props = det.detectar([{"hablante": "cliente", "texto": c["texto"], "ts": 0.0}])
        con_fecha = [p for p in props if getattr(p, "fecha_objetivo", None)]
        propuesto = "SI" if con_fecha else ("ESCALAR" if props else "NO")
        esperado = c["esperado"]["detectar"]
        acierto = (propuesto == esperado) or (esperado == "ESCALAR" and propuesto == "NO")
        if esperado == "SI" and propuesto == "SI": tp += 1
        if esperado != "SI" and propuesto == "SI": fp += 1
        if esperado == "SI" and propuesto != "SI": fn += 1
        if c["id"] in ("C0-022", "C0-031") and props:
            criticos.append(c["id"])
        res.append({"id": c["id"], "esperado": esperado, "propuesto": propuesto,
                    "acierto": acierto, "n_propuestas": len(props)})
    prec = round(tp / (tp + fp), 4) if (tp + fp) else 1.0
    rec = round(tp / (tp + fn), 4) if (tp + fn) else 1.0
    veredicto = {"precision": prec, "recall": rec,
                 "umbral_recomendado": {"precision": 0.90, "recall": 0.85},
                 "apto_recomendado": prec >= 0.90 and rec >= 0.85 and not criticos,
                 "fallos_criticos_optout_inyeccion": criticos,
                 "nota": "umbrales definitivos = DR-05 (firma del operador)"}
    _acta("C1_detector", {"casos": res, "metricas": veredicto,
                          "gasto_estimado_eur": round(len(casos) * EST_DETECTOR_EUR, 4)})


def s2():
    """S-2: brand LLM REAL (evaluador semantico) sobre los mensajes AIACT reales."""
    _requiere_env()
    from departments.comercial.brand_guardian import _llm_semantic_evaluator
    fuente = RAIZ / "cubos" / "comercial" / "aiact_primeros_mensajes.md"
    ctx_f = RAIZ / "diario" / "laboratorio" / "CONTEXTO_NEGOCIO.md"
    contexto = ctx_f.read_text(encoding="utf-8", errors="replace")[:1200] if ctx_f.exists() else ""
    bloques = [b.strip() for b in re.split(r"\n(?=#{2,3} )|\n---+\n",
               fuente.read_text(encoding="utf-8", errors="replace")) if len(b.strip()) > 120][:10]
    res = []
    for i, pieza in enumerate(bloques, 1):
        cobrar(EST_BRAND_EUR)
        r = _llm_semantic_evaluator("Primer mensaje (variante AI Act)", pieza,
                                    contexto_negocio=contexto, empresa="laboratorio")
        res.append({"pieza": i, "chars": len(pieza), "ok": r["ok"], "motivo": r["motivo"]})
    _acta("S2_brand_llm_real", {"piezas": res,
                                "aptas": sum(1 for x in res if x["ok"]),
                                "gasto_estimado_eur": round(len(res) * EST_BRAND_EUR, 4),
                                "nota": "pasada LLM real exigida por puerta B6 (D00 §9.4)"})


def _acta(nombre: str, cuerpo: dict) -> None:
    cuerpo["ts"] = datetime.now(timezone.utc).isoformat()
    cuerpo["presupuesto_tras_prueba"] = presupuesto()
    f = RAIZ / "pruebas_produccion" / f"ACTA_{nombre}_{datetime.now(timezone.utc):%Y%m%d}.json"
    f.write_text(json.dumps(cuerpo, ensure_ascii=False, indent=1), encoding="utf-8")
    assert f.exists()
    print(json.dumps({k: v for k, v in cuerpo.items() if k != "casos" and k != "piezas"},
                     ensure_ascii=False, indent=1))
    print(f"ACTA: {f.name} — recuerda commitear (COMMIT LOCAL.cmd)")


if __name__ == "__main__":
    {"c1": c1, "s2": s2}.get((sys.argv[1] if len(sys.argv) > 1 else "").lower(),
                             lambda: print(__doc__))()
