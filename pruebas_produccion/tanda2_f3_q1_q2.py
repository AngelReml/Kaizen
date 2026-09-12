# -*- coding: utf-8 -*-
"""Tanda autonoma 2 (0 EUR): F-3 motor SIF sintetico E2E (VR-D04-03 recortado),
Q-1 obligaciones internas reales (AIACT-GATE con alertas YA en ventana),
Q-2 expediente probatorio de la construccion serie D con defensa compilada."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from core.knowledge import InMemoryKnowledge, JsonKnowledge  # noqa: E402
from core.rue import Bitacora  # noqa: E402
from departments.finanzas.cubo_serie_d import MotorSIF, AEATSimulador  # noqa: E402
from departments.cumplimiento.cubo_serie_d import CuboCumplimiento  # noqa: E402

TS = datetime.now(timezone.utc).isoformat()
DIA = datetime.now(timezone.utc).strftime("%Y%m%d")
PR = RAIZ / "_workspace" / "pruebas"
acta = {"tanda": "F-3 + Q-1 + Q-2", "ts": TS, "gasto_eur": 0.0}

# ── F-3: 20 facturas sinteticas E2E con persistencia real dedicada ──
kf = JsonKnowledge(PR / "sif_sintetico.json")
sif = MotorSIF(kf, "prueba_sif", remisor=AEATSimulador())
NIF = "SINTETICO-VR03"
emitidas = [sif.emitir(nif_obligado=NIF, nif_destinatario=f"SINTETICO-D{i:02d}",
                       serie="PRB", importe_neto=50.0 + i, descripcion=f"lote sintetico {i}")
            for i in range(15)]
rechazos = 0
for serie_mala, imp in (("", 10.0), ("PRB", 0.0), ("PRB", -5.0)):
    try:
        sif.emitir(nif_obligado=NIF, nif_destinatario="SINTETICO-X", serie=serie_mala,
                   importe_neto=imp)
    except ValueError:
        rechazos += 1
rect = sif.emitir(nif_obligado=NIF, nif_destinatario="SINTETICO-D01", serie="PRB-R",
                  importe_neto=-0.0 + 12.0, descripcion="rectificativa de la 000002")
anu = sif.anular(emitidas[2]["rfa_ref"], motivo="prueba de anulacion VR-03", por="operador")
v_sif = sif.verificar_cadena(NIF)
# verificacion INDEPENDIENTE (recomputo manual fuera de la clase, D04 13.4)
regs = sorted((k, r) for k, r in kf.all("prueba_sif", "sif_registro").items()
              if r["nif_obligado"] == NIF)
prev = hashlib.sha256(f"SIF||{NIF}".encode()).hexdigest()
indep = True
for k_, r in regs:
    cuerpo = {a: b for a, b in r.items() if a not in ("huella_anterior", "huella")}
    canon = json.dumps(cuerpo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if r["huella"] != hashlib.sha256((prev + "||" + canon).encode()).hexdigest():
        indep = False
        break
    prev = r["huella"]
acta["F3"] = {"emitidas_ok": len(emitidas) + 1, "invalidas_rechazadas": rechazos,
              "anulaciones": 1, "cadena_clase": v_sif, "verificacion_independiente": indep,
              "registros_totales": len(regs), "almacen": "sif_sintetico.json"}
assert v_sif["integra"] and indep and rechazos == 3

# ── Q-1: obligaciones INTERNAS reales (sin gestoria: tipo INTERNA/CONTRACTUAL propio) ──
kq = JsonKnowledge(RAIZ / "state" / "cumplimiento_plataforma.json")
bq = Bitacora(kq, "plataforma", fecha_alta="2026-07-10")
cc = CuboCumplimiento(kq, "plataforma", bitacora=bq)
o1 = cc.registrar(nombre="AIACT-GATE art.50: variantes de transparencia aprobadas y candado activo",
                  tipo="INTERNA", fecha_limite="2026-08-02", area="comercial/direccion")
cc.asignar(o1["id"], "operador")
o2 = cc.registrar(nombre="Validacion R9 del ritual de la manana en maquina del operador",
                  tipo="INTERNA", fecha_limite="2026-08-30", area="direccion")
cc.asignar(o2["id"], "operador")
o3 = cc.registrar(nombre="Copia fisica externa del repo (GR-10; git es SOLO local por DR-01)",
                  tipo="INTERNA", fecha_limite="2026-07-24", area="infraestructura")
cc.asignar(o3["id"], "operador")
avisos = cc.barrer_plazos()
acta["Q1"] = {"obligaciones": 3, "alertas_emitidas_hoy": avisos,
              "bitacora": bq.verificar()}

# ── Q-2: expediente probatorio de la construccion (evidencias = actas+commits reales) ──
o4 = cc.registrar(nombre="Custodia probatoria del desarrollo serie D (memoria I+D/NEOTEC)",
                  tipo="INTERNA", fecha_limite="2027-06-30", area="direccion")
cc.asignar(o4["id"], "operador")
git_log = subprocess.run(["git", "log", "--format=%H %ad %s", "--date=short"],
                         capture_output=True, text=True, cwd=RAIZ).stdout
cc.aportar_evidencia(o4["id"], nombre_fichero="git_log_completo.txt",
                     contenido=git_log.encode("utf-8"), firmante="agente")
for f in ("AUDITORIA_CONSTRUCCION_SERIE_D.md", "AUDITORIA_D00.md", "AUDITORIA_D01.md",
          "AUDITORIA_SERIE_D_ESTADO_REAL.md", "LINEA_BASE.md",
          "docs/corpus_compromisos_c0_v1.json"):
    cc.aportar_evidencia(o4["id"], nombre_fichero=f, contenido=(RAIZ / f).read_bytes(),
                         firmante="agente")
cc.cumplir(o4["id"], por="operador-delegado-en-sesion")
val = cc.validar_expediente(o4["id"])
aud = cc.auditar()
defensa = cc.compilar_defensa()
df = PR / f"DEFENSA_SERIE_D_{DIA}.json"
df.write_text(json.dumps(defensa, ensure_ascii=False, indent=1), encoding="utf-8")
assert df.exists() and defensa["integro"]
acta["Q2"] = {"expediente": val["veredicto"], "piezas_defensa": len(defensa["piezas"]),
              "hash_manifest": defensa["hash_manifest"],
              "hallazgos_auditoria": len(aud["hallazgos"]), "fichero": df.name}

af = PR / f"ACTA_TANDA2_{DIA}.json"
af.write_text(json.dumps(acta, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(acta, ensure_ascii=False, indent=1)[:1500])
