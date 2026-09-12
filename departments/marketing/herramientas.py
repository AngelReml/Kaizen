"""Herramientas deterministas del Departamento Marketing (tesis §3.3).

Operan sobre el knowledge store (estado propio del cubo, aislado por empresa). Sin LLM:
la redacción creativa la hace el especialista Redactor; aquí vive la lógica auditable.

tipos de knowledge usados: "contenido_mkt" (piezas: lo lee `piezas()`/`metricas_alcance()`,
lo escribe CuboMarketing.crear_contenido en departments/marketing/cubo_serie_d.py) y
"lead_inbound" (leads que entran por contenido, para alimentar al Comercial).
`registrar_pieza()` (usado por `publicar_pieza()` del agente legacy, sin llamador real
en produccion) sigue escribiendo en el tipo "contenido", separado adrede: no tiene
lector real hoy y no se ha migrado (AUDITORIA G4).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def planificar_contenido(posicionamiento: str, objeciones: list[str], *, n: int = 5) -> list[dict]:
    """Plan editorial heurístico: convierte posicionamiento + objeciones del Comercial en
    ideas de pieza. Cada objeción real es una idea de contenido que la responde."""
    ideas: list[dict] = []
    base = (posicionamiento or "").strip()
    if base:
        ideas.append({"angulo": "posicionamiento", "tema": base[:120],
                      "formato": "post", "objetivo": "presencia"})
    for obj in (objeciones or []):
        ideas.append({"angulo": "objecion", "tema": f"Responder: {obj}"[:120],
                      "formato": "articulo", "objetivo": "inbound"})
    # Rellena hasta n con formatos variados si faltan ideas.
    formatos = ["post", "email", "articulo", "anuncio", "landing"]
    while len(ideas) < n:
        ideas.append({"angulo": "alcance", "tema": f"{base[:60]} · enfoque {len(ideas)+1}",
                      "formato": formatos[len(ideas) % len(formatos)], "objetivo": "alcance"})
    return ideas[:n]


def palabras_clave(texto: str, *, n: int = 8) -> list[str]:
    """SEO/SEM determinista: términos relevantes por frecuencia, sin stopwords básicas."""
    stop = {"de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "con", "por",
            "para", "que", "del", "su", "se", "no", "es", "más", "como", "o"}
    palabras = [w for w in re.findall(r"[a-záéíóúñ]{3,}", (texto or "").lower())
                if w not in stop]
    frec: dict[str, int] = {}
    for w in palabras:
        frec[w] = frec.get(w, 0) + 1
    return [w for w, _ in sorted(frec.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def registrar_pieza(knowledge, company: str, *, tema: str, formato: str, canal: str,
                    cuerpo: str = "", estado: str = "publicada") -> dict:
    pieza_id = uuid.uuid4().hex[:12]
    pieza = {"id": pieza_id, "tema": tema, "formato": formato, "canal": canal,
             "cuerpo": cuerpo, "estado": estado, "ts": _ahora(),
             "keywords": palabras_clave(f"{tema} {cuerpo}")}
    knowledge.add(company, "contenido", pieza_id, pieza)
    return pieza


def piezas(knowledge, company: str, *, estado: str | None = None) -> list[dict]:
    # El productor real es CuboMarketing.crear_contenido (departments/marketing/
    # cubo_serie_d.py), que escribe en "contenido_mkt". "contenido" es el tipo del
    # legacy registrar_pieza()/publicar_pieza(), sin llamador real en produccion
    # (AUDITORIA G4): leer de "contenido" dejaba esta funcion ciega a todo lo que
    # el sistema realmente escribe.
    items = list(knowledge.all(company, "contenido_mkt").values())
    if estado:
        items = [p for p in items if p.get("estado") == estado]
    return sorted(items, key=lambda p: p.get("ts", ""))


def registrar_lead_inbound(knowledge, company: str, *, nombre: str, canal: str,
                           origen_pieza: str | None = None, contacto: dict | None = None) -> dict:
    lead_id = uuid.uuid4().hex[:12]
    lead = {"id": lead_id, "nombre": nombre, "canal": canal, "origen_pieza": origen_pieza,
            "contacto": contacto or {}, "fuente": "inbound", "ts": _ahora()}
    knowledge.add(company, "lead_inbound", lead_id, lead)
    return lead


def metricas_alcance(knowledge, company: str) -> dict:
    pubs = piezas(knowledge, company, estado="publicada")
    inbound = list(knowledge.all(company, "lead_inbound").values())
    por_canal: dict[str, int] = {}
    for p in pubs:
        por_canal[p.get("canal", "?")] = por_canal.get(p.get("canal", "?"), 0) + 1
    return {"piezas_publicadas": len(pubs), "leads_inbound": len(inbound),
            "por_canal": por_canal,
            "tasa_conversion_pieza_lead": round(len(inbound) / len(pubs), 3) if pubs else 0.0}
