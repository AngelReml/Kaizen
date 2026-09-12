"""Herramientas deterministas de Atención al Cliente / Customer Success (tesis §3.4).

Estado propio (knowledge), aislado por empresa:
  "cliente_cs"  — ficha de cliente en postventa: salud, último contacto, NPS, estado.
  "ticket"      — incidencias de soporte.

La detección de churn y de upsell es heurística y auditable; la respuesta empática del
Support Agent es la única parte con LLM (en el especialista).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _ahora().isoformat()


# Umbrales (estimación, recalibrable como en §7.4). Días sin contacto que marcan riesgo.
DIAS_RIESGO_CHURN = 45
NPS_RIESGO = 6          # NPS <= 6 (detractor) es señal de churn


def alta_cliente(knowledge, company: str, *, nombre: str, valor_mensual: float = 0.0,
                 origen: str = "comercial") -> dict:
    cid = uuid.uuid4().hex[:12]
    ficha = {"id": cid, "nombre": nombre, "valor_mensual": valor_mensual, "origen": origen,
             "ultimo_contacto": _iso(), "nps": None, "estado": "activo",
             "renovaciones": 0, "ts_alta": _iso()}
    knowledge.add(company, "cliente_cs", cid, ficha)
    return ficha


def registrar_contacto(knowledge, company: str, cliente_id: str, *, nps: int | None = None,
                       nota: str = "") -> dict | None:
    ficha = knowledge.get(company, "cliente_cs", cliente_id)
    if not ficha:
        return None
    ficha["ultimo_contacto"] = _iso()
    if nps is not None:
        ficha["nps"] = int(nps)
    if nota:
        ficha["ultima_nota"] = nota
    knowledge.add(company, "cliente_cs", cliente_id, ficha)
    return ficha


def abrir_ticket(knowledge, company: str, cliente_id: str, *, asunto: str,
                 prioridad: str = "media") -> dict:
    tid = uuid.uuid4().hex[:12]
    ticket = {"id": tid, "cliente_id": cliente_id, "asunto": asunto, "prioridad": prioridad,
              "estado": "abierto", "ts": _iso()}
    knowledge.add(company, "ticket", tid, ticket)
    return ticket


def _dias_sin_contacto(ficha: dict) -> int:
    try:
        ultimo = datetime.fromisoformat(ficha.get("ultimo_contacto", ""))
    except ValueError:
        return 9999
    return (_ahora() - ultimo).days


def detectar_churn(knowledge, company: str) -> list[dict]:
    """Clientes en riesgo: inactividad prolongada o NPS de detractor. Señal, no sentencia."""
    riesgo = []
    for ficha in knowledge.all(company, "cliente_cs").values():
        if ficha.get("estado") != "activo":
            continue
        dias = _dias_sin_contacto(ficha)
        nps = ficha.get("nps")
        motivos = []
        if dias >= DIAS_RIESGO_CHURN:
            motivos.append(f"{dias} días sin contacto")
        if nps is not None and nps <= NPS_RIESGO:
            motivos.append(f"NPS {nps} (detractor)")
        if motivos:
            riesgo.append({"cliente_id": ficha["id"], "nombre": ficha["nombre"],
                           "valor_mensual": ficha.get("valor_mensual", 0.0),
                           "motivos": motivos})
    return sorted(riesgo, key=lambda r: r["valor_mensual"], reverse=True)


def detectar_upsell(knowledge, company: str) -> list[dict]:
    """Oportunidades de crecimiento: clientes contentos (NPS alto) y con renovaciones."""
    ops = []
    for ficha in knowledge.all(company, "cliente_cs").values():
        if ficha.get("estado") == "activo" and (ficha.get("nps") or 0) >= 9:
            ops.append({"cliente_id": ficha["id"], "nombre": ficha["nombre"],
                        "razon": f"NPS {ficha.get('nps')} · {ficha.get('renovaciones',0)} renovaciones"})
    return ops


def registrar_renovacion(knowledge, company: str, cliente_id: str) -> dict | None:
    ficha = knowledge.get(company, "cliente_cs", cliente_id)
    if not ficha:
        return None
    ficha["renovaciones"] = ficha.get("renovaciones", 0) + 1
    ficha["ultimo_contacto"] = _iso()
    knowledge.add(company, "cliente_cs", cliente_id, ficha)
    return ficha


def salud_cartera(knowledge, company: str) -> dict:
    fichas = list(knowledge.all(company, "cliente_cs").values())
    activos = [f for f in fichas if f.get("estado") == "activo"]
    en_riesgo = detectar_churn(knowledge, company)
    npss = [f["nps"] for f in activos if f.get("nps") is not None]
    return {"clientes_activos": len(activos), "en_riesgo": len(en_riesgo),
            "nps_medio": round(sum(npss) / len(npss), 1) if npss else None,
            "valor_en_riesgo": round(sum(r["valor_mensual"] for r in en_riesgo), 2)}
