"""Consulta natural sobre el knowledge (Módulo 6 del sistema nervioso).

Text-to-filter, no text-to-SQL. ADR-005. Ver `docs/CONSULTA_NATURAL.md`.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import claude_client as ai
from core.lead_schema import LeadDoc
from core.briefing import _ciudad_desde_direccion, _parsear_ts


CAMPOS_CONSULTABLES = {
    "estado_pipeline":              {"eq", "neq"},
    "categoria_icp":                {"eq", "neq", "contains"},
    "prioridad_icp":                {"eq", "neq"},
    "anillo":                       {"eq", "gte", "lte"},
    "intentos_realizados":          {"eq", "gte", "lte"},
    "do_not_call":                  {"eq"},
    "ciudad":                       {"eq", "contains"},
    "tiene_compromiso":             {"tiene"},
    "dias_desde_ultima_interaccion": {"gte", "lte"},
    "tipo_detectado":               {"eq", "contains"},
}

TIPOS_RESPUESTA = {"count", "list", "summary"}


@dataclass
class FiltroConsulta:
    campo: str
    op: str
    valor: Any


@dataclass
class Consulta:
    filtros: list[FiltroConsulta] = field(default_factory=list)
    tipo_respuesta: str = "count"
    limite: int = 20
    agrupar_por: Optional[str] = None
    error: str = ""


_SYSTEM = """Eres un asistente que convierte preguntas en lenguaje natural sobre una
base de datos de leads comerciales en un FILTRO ESTRUCTURADO en JSON. NUNCA generes
código ni SQL. Solo eliges qué filtros aplicar y cómo presentar el resultado.

CAMPOS CONSULTABLES (lista cerrada, no inventes):
- estado_pipeline: cold | queued | contacting | no_answer | contacted | engaged
  | sample_requested | sample_sent | trial | customer | lost | do_not_call
- categoria_icp: hotel_boutique_con_desayuno | panaderia_pasteleria | etc.
- prioridad_icp: ALTA | MEDIA | BAJA
- anillo: int (0=zona Caudete, 1=primer anillo, etc.)
- intentos_realizados: int (cuántas veces se ha intentado llamar)
- do_not_call: true | false
- ciudad: string (ej. "Murcia", "Albacete")
- tiene_compromiso: "callback" | "muestra" | "email_info" | "referido" | "visita" | "*"
- dias_desde_ultima_interaccion: int
- tipo_detectado: hotel | restaurante | cafeteria | etc.

OPERADORES (lista cerrada):
- eq: igual
- neq: distinto
- gte / lte: numérico
- contains: substring case-insensitive (solo strings)
- tiene: para tiene_compromiso

TIPO DE RESPUESTA:
- "count": el usuario quiere un número ("¿cuántos…?")
- "list": el usuario quiere ver los leads ("¿qué leads…?", "dame la lista de…")
- "summary": el usuario quiere un breakdown agrupado ("desglosa por…")

Devuelve JSON EXACTO con esta forma (sin markdown, sin texto alrededor):

{
  "filtros": [{"campo": "estado_pipeline", "op": "eq", "valor": "queued"}],
  "tipo_respuesta": "count",
  "limite": 20,
  "agrupar_por": null
}

Si la pregunta NO es interpretable con este schema, devuelve:
{"error": "no_interpretable", "razon": "explicación breve"}

EJEMPLOS:

Pregunta: "¿cuántos hoteles boutique tengo en queued?"
→ {"filtros":[{"campo":"categoria_icp","op":"eq","valor":"hotel_boutique_con_desayuno"},
              {"campo":"estado_pipeline","op":"eq","valor":"queued"}],
   "tipo_respuesta":"count","limite":20,"agrupar_por":null}

Pregunta: "dame los leads en Murcia con compromiso de callback pendiente"
→ {"filtros":[{"campo":"ciudad","op":"contains","valor":"Murcia"},
              {"campo":"tiene_compromiso","op":"tiene","valor":"callback"}],
   "tipo_respuesta":"list","limite":20,"agrupar_por":null}

Pregunta: "desglosa los leads por estado del pipeline"
→ {"filtros":[],"tipo_respuesta":"summary","limite":20,"agrupar_por":"estado_pipeline"}
"""


def _aplicar_filtro(lead: LeadDoc, f: FiltroConsulta, ahora_utc: datetime) -> bool:
    campo, op, valor = f.campo, f.op, f.valor

    if campo == "ciudad":
        direccion = lead.ubicacion.direccion if lead.ubicacion else ""
        v = _ciudad_desde_direccion(direccion or "")
        return _comparar_str(v, op, str(valor))

    if campo == "intentos_realizados":
        v = lead.reintentos.intentos_realizados if lead.reintentos else 0
        return _comparar_num(v, op, valor)

    if campo == "anillo":
        return _comparar_num(int(lead.anillo or 0), op, valor)

    if campo == "do_not_call":
        return bool(lead.do_not_call) == bool(valor)

    if campo == "tiene_compromiso":
        pendientes = [c for c in (lead.compromisos or []) if not c.cumplido]
        v = str(valor).lower()
        if v == "*":
            return len(pendientes) > 0
        return any(c.tipo == v for c in pendientes)

    if campo == "dias_desde_ultima_interaccion":
        if not lead.interacciones:
            return False
        ts = _parsear_ts(lead.interacciones[-1].ts)
        if not ts:
            return False
        dias = (ahora_utc - ts).total_seconds() / 86400
        return _comparar_num(int(dias), op, valor)

    # Campos simples: estado_pipeline, categoria_icp, prioridad_icp, tipo_detectado
    if campo == "estado_pipeline":
        return _comparar_str(lead.estado_pipeline or "", op, str(valor))
    if campo == "categoria_icp":
        return _comparar_str(lead.categoria_icp or "", op, str(valor))
    if campo == "prioridad_icp":
        return _comparar_str(lead.prioridad_icp or "", op, str(valor))
    if campo == "tipo_detectado":
        return _comparar_str(lead.tipo_detectado or "", op, str(valor))

    return False


def _comparar_str(actual: str, op: str, valor: str) -> bool:
    if op == "eq":       return (actual or "").lower() == valor.lower()
    if op == "neq":      return (actual or "").lower() != valor.lower()
    if op == "contains": return valor.lower() in (actual or "").lower()
    return False


def _comparar_num(actual: float, op: str, valor: Any) -> bool:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return False
    if op == "eq":  return actual == v
    if op == "gte": return actual >= v
    if op == "lte": return actual <= v
    return False


class ConsultaNatural:
    """Pipeline NLQ. `chat` y `knowledge_loader` inyectables."""

    def __init__(self, chat: Optional[Callable] = None,
                 knowledge_loader: Optional[Callable[[], list[LeadDoc]]] = None,
                 company: str = "default",
                 clock: Optional[Callable[[], datetime]] = None) -> None:
        self.chat = chat or ai.chat
        self.knowledge_loader = knowledge_loader
        self.company = company
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Interpretar (LLM) ----

    def interpretar(self, pregunta: str) -> Consulta:
        if not pregunta or not pregunta.strip():
            return Consulta(error="pregunta_vacia")
        try:
            salida = self.chat(
                [{"role": "user", "content": pregunta.strip()}],
                system=_SYSTEM,
                model="claude-sonnet-4-6",
                max_tokens=600,
                company=self.company,
            )
        except Exception as e:
            print(f"[consulta] LLM falló: {e}", file=sys.stderr)
            return Consulta(error=f"llm_falló: {e}")
        return self._parsear_consulta(salida or "")

    @staticmethod
    def _parsear_consulta(salida_llm: str) -> Consulta:
        m = re.search(r"\{[\s\S]*\}", salida_llm or "")
        if not m:
            return Consulta(error="no_json_en_respuesta")
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            return Consulta(error=f"json_invalido: {e}")
        if data.get("error"):
            return Consulta(error=str(data["error"]) + ": " + str(data.get("razon", "")))
        filtros = []
        for raw in data.get("filtros") or []:
            campo = raw.get("campo", "")
            op = raw.get("op", "")
            if campo not in CAMPOS_CONSULTABLES:
                print(f"[consulta] campo desconocido '{campo}' descartado",
                      file=sys.stderr)
                continue
            if op not in CAMPOS_CONSULTABLES[campo]:
                print(f"[consulta] op '{op}' inválido para campo '{campo}'",
                      file=sys.stderr)
                continue
            filtros.append(FiltroConsulta(campo=campo, op=op, valor=raw.get("valor")))
        tipo = data.get("tipo_respuesta", "count")
        if tipo not in TIPOS_RESPUESTA:
            tipo = "count"
        return Consulta(
            filtros=filtros,
            tipo_respuesta=tipo,
            limite=int(data.get("limite", 20) or 20),
            agrupar_por=data.get("agrupar_por") or None,
        )

    # --- Aplicar (puro, sin LLM) ----

    def aplicar(self, consulta: Consulta, leads: list[LeadDoc]) -> dict:
        if consulta.error:
            return {"error": consulta.error}
        ahora = self.clock()
        filtrados = [
            ld for ld in leads
            if all(_aplicar_filtro(ld, f, ahora) for f in consulta.filtros)
        ]
        if consulta.tipo_respuesta == "count":
            return {
                "tipo": "count",
                "total": len(filtrados),
                "muestra": [self._snapshot(ld) for ld in filtrados[:3]],
            }
        if consulta.tipo_respuesta == "list":
            return {
                "tipo": "list",
                "total": len(filtrados),
                "items": [self._snapshot(ld) for ld in filtrados[:consulta.limite]],
            }
        if consulta.tipo_respuesta == "summary":
            buckets: dict[str, int] = {}
            campo = consulta.agrupar_por or "estado_pipeline"
            for ld in filtrados:
                clave = self._campo_para_groupby(ld, campo) or "(vacío)"
                buckets[clave] = buckets.get(clave, 0) + 1
            return {
                "tipo": "summary",
                "agrupar_por": campo,
                "total": len(filtrados),
                "buckets": dict(sorted(buckets.items(), key=lambda kv: -kv[1])),
            }
        return {"error": f"tipo_respuesta_desconocido: {consulta.tipo_respuesta}"}

    @staticmethod
    def _campo_para_groupby(lead: LeadDoc, campo: str) -> str:
        if campo == "ciudad":
            return _ciudad_desde_direccion(
                lead.ubicacion.direccion if lead.ubicacion else "")
        if campo == "intentos_realizados":
            return str(lead.reintentos.intentos_realizados if lead.reintentos else 0)
        if campo == "do_not_call":
            return "true" if lead.do_not_call else "false"
        return str(getattr(lead, campo, "") or "")

    @staticmethod
    def _snapshot(lead: LeadDoc) -> dict:
        return {
            "id": lead.id,
            "nombre": lead.nombre or "",
            "estado": lead.estado_pipeline or "",
            "ciudad": _ciudad_desde_direccion(
                lead.ubicacion.direccion if lead.ubicacion else ""),
            "categoria": lead.categoria_icp or "",
            "intentos": lead.reintentos.intentos_realizados if lead.reintentos else 0,
        }

    # --- Formatear (para humano) ----

    def formatear(self, resultado: dict, consulta: Consulta) -> str:
        if resultado.get("error"):
            return f"❌ {resultado['error']}"
        if resultado["tipo"] == "count":
            L = [f"**Total: {resultado['total']} lead(s)**"]
            if resultado["total"] > 0 and resultado["muestra"]:
                L.append("")
                L.append("Muestra:")
                for s in resultado["muestra"]:
                    L.append(f"- {s['nombre']} ({s['ciudad']}) — {s['estado']}")
            return "\n".join(L)
        if resultado["tipo"] == "list":
            L = [f"**{resultado['total']} lead(s)** (mostrando {len(resultado['items'])}):"]
            L.append("")
            for s in resultado["items"]:
                L.append(f"- **{s['nombre']}** — {s['categoria']} · "
                         f"{s['ciudad']} · {s['estado']} · {s['intentos']} intento(s)")
            return "\n".join(L)
        if resultado["tipo"] == "summary":
            L = [f"**Desglose por {resultado['agrupar_por']}** "
                 f"({resultado['total']} leads totales):"]
            L.append("")
            for clave, n in resultado["buckets"].items():
                L.append(f"- {clave}: {n}")
            return "\n".join(L)
        return str(resultado)

    # --- Punto de entrada de alto nivel ----

    def responder(self, pregunta: str,
                  leads: Optional[list[LeadDoc]] = None) -> str:
        consulta = self.interpretar(pregunta)
        if consulta.error:
            return f"❌ No entendí la pregunta: {consulta.error}"
        if leads is None:
            if self.knowledge_loader is None:
                return "❌ No tengo knowledge_loader configurado y no se pasaron leads."
            leads = self.knowledge_loader()
        resultado = self.aplicar(consulta, leads)
        return self.formatear(resultado, consulta)
