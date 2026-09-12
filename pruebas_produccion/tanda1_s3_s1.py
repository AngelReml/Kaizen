# -*- coding: utf-8 -*-
"""Tanda autonoma 1 (presupuesto aprobado 10 EUR; esta tanda: 0 EUR, sin LLM).
S-3: backup verificado de los tenants reales (GR-10). S-1: migracion LECTURA de los
leads reales al pipeline canonico con bitacora encadenada. Todo con verificacion E1."""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from core.knowledge import InMemoryKnowledge  # noqa: E402
from core.rue import Bitacora, Sobre  # noqa: E402
from departments.comercial.cubo_serie_d import MAPEO_REAL_A_CANON  # noqa: E402

TS = datetime.now(timezone.utc).isoformat()
DIA = datetime.now(timezone.utc).strftime("%Y%m%d")
BACK = RAIZ / "_workspace" / "backups"
BACK.mkdir(parents=True, exist_ok=True)
KPATH = RAIZ / "state" / "knowledge.json"


def sha_fichero(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


acta = {"tanda": "S-3 + S-1", "ts": TS, "gasto_eur": 0.0, "pasos": []}

# ── 0. presupuesto de sesion (tope aprobado por el operador) ──
pres_dir = RAIZ / "state" / "presupuesto"
pres_dir.mkdir(parents=True, exist_ok=True)
pres = {"tope_eur": 10.0, "aprobado_por": "operador (orden en sesion, 2026-07-10)",
        "gastado_eur": 0.0, "nota": "hard stop DELANTE de cada llamada (R2/B4)"}
pf = pres_dir / "sesion_20260710.json"
pf.write_text(json.dumps(pres, ensure_ascii=False, indent=1), encoding="utf-8")
assert json.loads(pf.read_text(encoding="utf-8"))["tope_eur"] == 10.0  # E1
acta["pasos"].append({"paso": "presupuesto", "tope_eur": 10.0, "fichero": str(pf.name)})

# ── S-3a. backup crudo del store ANTES de tocar nada ──
crudo = BACK / f"knowledge_pre_migracion_{DIA}.json"
shutil.copyfile(KPATH, crudo)
h_orig, h_copia = sha_fichero(KPATH), sha_fichero(crudo)
assert h_orig == h_copia, "E1: backup crudo no coincide"
acta["pasos"].append({"paso": "S-3a backup crudo", "sha256": h_copia, "bytes": crudo.stat().st_size})

# ── carga real (LECTURA) ──
store = json.loads(KPATH.read_text(encoding="utf-8"))

# ── S-3b. snapshots datados por tenant con hash (primitiva B2) ──
for tenant in sorted(store.keys()):
    contenido = json.dumps({"tenant": tenant, "datos": store[tenant]},
                           ensure_ascii=False, sort_keys=True, indent=1)
    f = BACK / f"snapshot_{tenant}_{DIA}.json"
    f.write_text(contenido, encoding="utf-8")
    assert f.read_text(encoding="utf-8") == contenido, f"E1: snapshot {tenant}"
    acta["pasos"].append({"paso": f"S-3b snapshot {tenant}",
                          "sha256": hashlib.sha256(contenido.encode()).hexdigest(),
                          "tipos": {t: len(v) for t, v in store[tenant].items()}})

# ── S-1. migracion al canon con cadena (en memoria; UNA escritura al final) ──
resumen_migracion = {}
for tenant in sorted(store.keys()):
    leads = store[tenant].get("lead", {})
    if not leads:
        continue
    mem = InMemoryKnowledge()
    bit = Bitacora(mem, tenant, fecha_alta="2026-05-24")
    stats = {"total": len(leads), "con_procedencia_completa": 0, "sin_procedencia": 0,
             "por_estado_canon": {}}
    for lid, lead in sorted(leads.items()):
        real = (lead.get("estado_pipeline") or lead.get("estado") or "cold").lower()
        canon = MAPEO_REAL_A_CANON.get(real, "COLD")
        fuentes = lead.get("fuentes") or []
        completa = any(isinstance(f, dict) and f.get("url") and (f.get("fecha") or f.get("ts"))
                       for f in fuentes)
        stats["con_procedencia_completa" if completa else "sin_procedencia"] += 1
        stats["por_estado_canon"][canon] = stats["por_estado_canon"].get(canon, 0) + 1
        mem.add(tenant, "lead_canon", lid, {
            "id": lid, "estado": canon, "estado_real_origen": real,
            "correlacion_id": f"mig-{lid}", "migrado_en": TS,
            "procedencia_completa": completa,
            "contactos_enviados": 0, "nota": "migracion LECTURA S-1; el lead real NO se toca"})
        bit.publicar(Sobre(tenant_id=tenant, tipo="comercial.lead.descubierto",
                           payload={"lead_ref": lid, "migracion": True,
                                    "estado_canon": canon,
                                    "procedencia_completa": completa},
                           origen="comercial.migracion", correlacion_id=f"mig-{lid}"))
    v = bit.verificar()
    assert v["integra"] and v["eventos"] == len(leads), f"cadena rota en {tenant}: {v}"
    store[tenant]["lead_canon"] = mem.all(tenant, "lead_canon")
    store[tenant]["evento"] = mem.all(tenant, "evento")
    stats["cadena"] = v
    resumen_migracion[tenant] = stats

# ── escritura UNICA + verificacion E1 + verificacion de cadena releyendo del disco ──
nuevo = json.dumps(store, ensure_ascii=False, indent=1)
KPATH.write_text(nuevo, encoding="utf-8")
releido = json.loads(KPATH.read_text(encoding="utf-8"))
assert json.dumps(releido, ensure_ascii=False, indent=1) == nuevo, "E1: knowledge.json"
for tenant, stats in resumen_migracion.items():
    mem2 = InMemoryKnowledge()
    for k_, v_ in releido[tenant]["evento"].items():
        mem2.add(tenant, "evento", k_, v_)
    v2 = Bitacora(mem2, tenant, fecha_alta="2026-05-24").verificar()
    assert v2["integra"], f"cadena rota TRAS persistir en {tenant}: {v2}"
    stats["cadena_tras_persistir"] = v2
    assert len(releido[tenant]["lead"]) == stats["total"], "los leads originales NO se tocan"
acta["pasos"].append({"paso": "S-1 migracion", "resumen": resumen_migracion,
                      "sha256_post": sha_fichero(KPATH)})

af = RAIZ / "_workspace" / "pruebas" / f"ACTA_TANDA1_{DIA}.json"
af.write_text(json.dumps(acta, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"S3_snapshots": len(store), "S1": {t: {kk: s[kk] for kk in
      ("total", "con_procedencia_completa", "sin_procedencia", "cadena_tras_persistir")}
      for t, s in resumen_migracion.items()}, "acta": af.name}, ensure_ascii=False, indent=1))
