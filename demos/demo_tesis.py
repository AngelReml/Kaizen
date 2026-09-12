"""Demo end-to-end de la tesis Kaizen v1.1 — la plataforma modular funcionando.

Recorre, sin tocar la red (comité simulado a temperatura 0), las propiedades que la tesis
diseñaba y que ahora están implementadas:

  §7.1  Sin dependencia de arranque   — arrancamos cubos sueltos y la matriz de combinaciones.
  §6    Verificación por comité        — OpenGravity compone comité, vota 3 pasadas, sella.
  §6.5  Preventivo vs forense          — el clasificador decide bloquear o auditar.
  §6.3  Candado de umbrales            — un sub-agente no puede relajar la seguridad.
  §6.4  Brand levanta comité           — el segundo cubo valida una campaña por contrato.
  §7.2  Degradación elegante           — con OpenGravity apagado, Brand sale con bandera.
  §7.4  Umbral de migración            — salud del bus SQLite y cuándo ABRIR la migración.

Ejecutar:  python demos/demo_tesis.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La consola de Windows usa cp1252 por defecto; forzamos UTF-8 para los caracteres del demo.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from core.bus import InMemoryBus
from core.bus_sqlite import SQLitePersistentBus
from core.events import Event, EventType
from core.opengravity.committee import Committee
from core.opengravity.vote_history import VoteHistory
from core.opengravity.sealing import HashChain
from core.opengravity.department import OpenGravity
from core.opengravity.thresholds import Umbrales, resolver_umbrales
from core.resiliencia.arranque import Cubo, verificar_combinaciones, CUBOS_CATALOGO
from core.migracion_bus import MonitorMigracion, UMBRALES
from departments.brand.brand_guardian import BrandGuardian
from departments.brand.director import DirectorBrand


def titulo(t: str) -> None:
    print("\n" + "═" * 78 + f"\n  {t}\n" + "═" * 78)


def comite_simulado(verdict: str = "PASS", conf: float = 0.93):
    def chat(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
        assert temperature == 0, "el comité debe correr a temperatura 0 (§6.2)"
        if "Chair" in system:
            return "El comité alcanza consenso y sintetiza el dictamen."
        findings = [] if verdict == "PASS" else [{"severity": "block", "text": "riesgo detectado"}]
        return json.dumps({"verdict": verdict, "confidence": conf, "risk_level": "low",
                           "findings": findings, "rationale": "coherente con el contexto"})
    return chat


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    empresa = "laboratorio"

    # ── §7.1 Sin dependencia de arranque ─────────────────────────────────────
    titulo("§7.1 · Sin dependencia de arranque — un cubo arranca sin conocer a los demás")
    bus = InMemoryBus()
    arrancados = []
    bus.subscribe(lambda e: arrancados.append(e.payload["cube"]), types=[EventType.CUBE_STARTED])

    class CuboDemo(Cubo):
        def __init__(self, name, bus, company):
            super().__init__(bus, company); self.name = name

    for solo in ("legal", "brand", "finanzas"):
        CuboDemo(solo, bus, empresa).arrancar()
    print(f"  Cubos arrancados en solitario, sin error: {arrancados}")

    fabricas = {n: (lambda b, c, n=n: CuboDemo(n, b, c)) for n in CUBOS_CATALOGO[:6]}
    fallidas = verificar_combinaciones(fabricas, lambda: InMemoryBus())
    print(f"  Matriz de combinaciones de 6 cubos (63 combos) — fallidas: {len(fallidas)} ✓")

    # ── §6 Verificación por comité (preventivo, R1) ──────────────────────────
    titulo("§6 · OpenGravity compone un comité, vota a temperatura 0 y sella el veredicto")
    bus = InMemoryBus()
    eventos = {"completed": [], "escalation": []}
    bus.subscribe(lambda e: eventos["completed"].append(e), types=[EventType.OPENGRAVITY_REVIEW_COMPLETED])
    bus.subscribe(lambda e: eventos["escalation"].append(e), types=[EventType.OPENGRAVITY_ESCALATION_REQUESTED])
    og = OpenGravity(bus, committee=Committee(chat=comite_simulado()),
                     vote_history=VoteHistory(base_dir=tmp), chain=HashChain(base_dir=tmp),
                     contexto_loader=lambda c: "Repostería artesanal centenaria de Cieza.")

    ver = og.revisar(
        artifact=("Propuesta de distribución para el Hotel La Parra: descuento del 8% y "
                  "cláusula RGPD de confidencialidad. Total a pagar 4.500 EUR. Requiere firma."),
        company=empresa, domain="comercial")
    print(f"  Modo (clasificado): {ver.mode}  ← {ver.clasificacion['motivo']} "
          f"(regla {ver.clasificacion['regla_dura']})")
    print(f"  Comité: {[m['role_id'] for m in ver.payload['members']]}")
    print(f"  Veredicto: {ver.verdict} · consenso {ver.consensus} · confianza {ver.confidence}")
    print(f"  Sellado SHA-256: {ver.trace['hash'][:24]}…  (encadenado con {ver.trace['chain_prev_hash'][:12]}…)")
    print(f"  review_completed emitido: {len(eventos['completed'])} · ejecutable: {ver.ejecutable}")

    # ── §6 Escalado por disenso ──────────────────────────────────────────────
    titulo("§6 · Disenso: un comité dividido NO ejecuta, escala al operador")
    bus2 = InMemoryBus()
    esc = []
    bus2.subscribe(lambda e: esc.append(e), types=[EventType.OPENGRAVITY_ESCALATION_REQUESTED])
    # Comité dividido DETERMINISTA: los roles legales aprueban, los demás rechazan.
    def chat_dividido(messages, *, system="", model="", max_tokens=0, company="", temperature=None):
        if "Chair" in system: return "comité dividido"
        if "Mediador" in system: return "ESCALATE"
        v = "PASS" if ("Legal" in system or "Cumplimiento" in system or "Riesgo" in system) else "FAIL"
        f = [] if v == "PASS" else [{"severity": "block", "text": "x"}]
        return json.dumps({"verdict": v, "confidence": 0.9, "risk_level": "medium",
                           "findings": f, "rationale": "r"})
    og2 = OpenGravity(bus2, committee=Committee(chat=chat_dividido),
                      vote_history=VoteHistory(base_dir=tmp / "b"), chain=HashChain(base_dir=tmp / "b"),
                      contexto_loader=lambda c: "ctx")
    ver2 = og2.revisar(artifact="Contrato firmable con cláusula RGPD, propuesta con descuento y forecast de margen",
                       company=empresa, mode="preventive", voting_runs=1)
    print(f"  Veredicto: {ver2.verdict} · consenso {ver2.consensus} · escalado: {ver2.escalation_reason}")
    print(f"  escalation_requested emitido: {len(esc)} · ejecutable: {ver2.ejecutable} (bloqueado) ")

    # ── §6.3 Candado de umbrales ─────────────────────────────────────────────
    titulo("§6.3 · Candado de umbrales — un sub-agente puede endurecer, nunca relajar")
    floor = Umbrales(0.66, 0.70)
    relaja = resolver_umbrales(floor, Umbrales(0.40, 0.40))
    endurece = resolver_umbrales(floor, Umbrales(0.85, 0.90))
    print(f"  Sub-agente intenta relajar a 0.40 → efectivo {relaja.efectivos.consensus_min} "
          f"(bloqueado: {relaja.relajacion_bloqueada})")
    print(f"  Sub-agente endurece a 0.85 → efectivo {endurece.efectivos.consensus_min} "
          f"(bloqueado: {endurece.relajacion_bloqueada})")

    # ── §6.4 Brand levanta comité para una campaña ───────────────────────────
    titulo("§6.4 · El cubo Brand valida una campaña levantando un comité (por contrato)")
    bus3 = InMemoryBus()
    OpenGravity(bus3, committee=Committee(chat=comite_simulado()),
                vote_history=VoteHistory(base_dir=tmp / "c"), chain=HashChain(base_dir=tmp / "c"),
                contexto_loader=lambda c: "Repostería.")
    director = DirectorBrand(bus3, empresa, guardian=BrandGuardian(empresa, semantic_evaluator=None))
    cuerpo = ("Hola, somos Repostería Laboratorio, un obrador familiar con más de un siglo de historia "
              "en Cieza. Elaboramos repostería artesanal con recetas centenarias que han pasado de "
              "generación en generación, y nos encantaría que la conocierais en vuestro "
              "establecimiento. Si os encaja, podemos enviaros una pequeña muestra sin ningún "
              "compromiso para que la probéis con calma y nos digáis qué os parece. "
              "Un saludo cordial, Iván Carbonell — Repostería Laboratorio")
    res = director.revisar(asunto="Repostería artesanal de Cieza con un siglo de historia",
                           cuerpo=cuerpo, artifact_type="campana", usar_llm=False)
    print(f"  Brand Guardian aprueba: {res['aprobado']} · comité: {res['comite']['verdict']} "
          f"(consenso {res['comite']['consensus']})")

    # ── §7.2 Degradación elegante (OpenGravity apagado) ──────────────────────
    titulo("§7.2 · Degradación elegante — con OpenGravity apagado, Brand sale con bandera")
    bus4 = InMemoryBus()   # SIN OpenGravity suscrito
    director2 = DirectorBrand(bus4, empresa, guardian=BrandGuardian(empresa, semantic_evaluator=None))
    res2 = director2.revisar(asunto="Repostería de Cieza", cuerpo=cuerpo,
                             artifact_type="campana", usar_llm=False)
    print(f"  aprobado (reglas locales): {res2['aprobado']} · degradado: {res2['degradado']} "
          f"· razón: {res2.get('degraded_reason')} · comité: {res2['comite']}")

    # ── §7.4 Umbral de migración del bus ─────────────────────────────────────
    titulo("§7.4 · Salud del sistema nervioso (SQLite) y umbral de migración a Redis")
    sn = SQLitePersistentBus(db_path=tmp / "sn.db")
    for i in range(5):
        sn.publish(Event(EventType.COST_RECORDED, source="demo", company=empresa))
    print(f"  Eventos persistidos en SQLite: {len(sn.history(empresa))} · "
          f"latencia escritura p95 ≈ {max(sn.latencias_escritura()):.2f} ms")
    monitor = MonitorMigracion(base_dir=tmp / "mig")
    alto = {k: v * 2 for k, v in UMBRALES.items()}
    for d in ("2026-05-27", "2026-05-28", "2026-05-29"):
        monitor.registrar_dia(alto, dia=d)
    print(f"  Tres días de métricas altas simuladas → decisión de migración ABIERTA: "
          f"{monitor.decision_abierta()} (el operador decide; el sistema sigue sobre SQLite)")
    sn.cerrar()

    # ── §3 Catálogo completo y cuadrado mínimo viable ────────────────────────
    titulo("§3 · Los diez cubos del catálogo y el cuadrado mínimo viable de una empresa")
    from departments import catalogo
    from core.resiliencia.arranque import Orquestador
    for c in catalogo.info():
        print(f"  {c['orden']:>2}. {c['titulo']:<34} [{c['estado']}]")
    bus5 = InMemoryBus()
    started5 = []
    bus5.subscribe(lambda e: started5.append(e.payload.get("cube")), types=[EventType.CUBE_STARTED])
    orq = Orquestador(bus5)
    combo = ["brand", "marketing", "customer_success", "rrhh", "opengravity"]
    catalogo.registrar_en_orquestador(orq, solo=combo)
    orq.arrancar(empresa, combo)
    print(f"\n  Orquestador arrancó {len(set(started5) & set(combo))} cubos autocontenidos: "
          f"{sorted(set(started5) & set(combo))}")
    print(f"  Cuadrado mínimo viable (§3.11): {' → '.join(catalogo.CUADRADO_MINIMO)}")

    # ── §3.9 RRHH mapea el sistema sobre sí mismo ────────────────────────────
    titulo("§3.9 · RRHH mapea las capacidades del sistema por introspección del bus")
    from departments.rrhh.agente import RRHHDepartment
    bus6 = InMemoryBus()
    rrhh = RRHHDepartment(bus6, empresa)
    for cube in ("comercial", "brand", "marketing", "customer_success", "opengravity"):
        bus6.publish(Event(EventType.CUBE_STARTED, source=cube, payload={"cube": cube}, company=empresa))
    mapa = rrhh.mapa()
    print(f"  Cobertura del catálogo: {int(mapa['cobertura']*100)}%  ·  "
          f"presentes: {len(mapa['presentes'])}/10")
    print(f"  Faltan por activar: {mapa['faltantes']}")
    for p in rrhh.propuestas():
        print(f"  → {p}")

    print("\n" + "改善 " * 6)
    print("El jardín nunca termina de crecer.\n")


if __name__ == "__main__":
    main()
