"""Herramientas de Ops (Fase 5.2). Deterministas, sobre el KnowledgeStore."""
from __future__ import annotations

import uuid

from core.knowledge import KnowledgeStore


def _pedidos(knowledge: KnowledgeStore, company: str) -> list[dict]:
    return list(knowledge.all(company, "pedido").values())


def consultar_capacidad(knowledge, company: str, fecha: str, capacidad_diaria: int = 10) -> dict:
    ocupada = sum(1 for p in _pedidos(knowledge, company) if p.get("fecha") == fecha)
    pct = ocupada / capacidad_diaria if capacidad_diaria else 0
    return {
        "fecha": fecha, "ocupada": ocupada, "libre": max(capacidad_diaria - ocupada, 0),
        "ocupada_pct": round(pct, 3), "capacidad_diaria": capacidad_diaria,
    }


def agendar_pedido(knowledge, company: str, cliente: str, productos, fecha: str,
                   capacidad_diaria: int = 10) -> dict:
    cap = consultar_capacidad(knowledge, company, fecha, capacidad_diaria)
    if cap["ocupada"] >= capacidad_diaria:
        return {"ok": False, "conflicto": f"Capacidad llena el {fecha} ({cap['ocupada']}/{capacidad_diaria})"}
    pid = f"ped_{fecha}_{uuid.uuid4().hex[:6]}"
    knowledge.add(company, "pedido", pid, {
        "id": pid, "cliente": cliente, "productos": productos, "fecha": fecha,
        "estado": "agendado", "company": company,
    })
    return {"ok": True, "fecha_confirmada": fecha, "pedido_id": pid}


def alerta_stock(knowledge, company: str) -> list[dict]:
    return [
        {"material": i["material"], "stock": i["stock"], "seguridad": i["stock_seguridad"]}
        for i in knowledge.all(company, "inventario").values()
        if i["stock"] < i["stock_seguridad"]
    ]
