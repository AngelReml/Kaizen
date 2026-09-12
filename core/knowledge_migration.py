"""Migración del knowledge al esquema unificado del sistema nervioso (ADR-007).

Toma cada lead de `state/knowledge.json`, lo pasa por `LeadDoc.from_dict()` (rellena
defaults + preserva extras) y `to_dict()` (vuelve a dict plano), y lo re-persiste.

Garantías:
- **No destructiva.** Hace backup automático antes de tocar nada
  (`knowledge.json.bak.<timestamp>`).
- **Idempotente.** Si se ejecuta dos veces, el resultado es idéntico
  (los leads ya migrados no cambian).
- **Tolerante a leads con esquema antiguo.** Cualquier campo desconocido se
  preserva en `metadatos_extra` (se desempaqueta al re-serializar).
- **Atómica al escribir.** Escribe a un fichero temporal y `os.replace` —
  un crash a media escritura no corrompe el JSON.

Esta función no toca otros tipos del knowledge (`llamada`, `email_pendiente_*`,
`analisis_llamada`, etc.) — solo `lead`. Si se necesita migrar otros tipos en
el futuro, se añade aquí sin breaking changes.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.lead_schema import LeadDoc, SCHEMA_VERSION

TIPO_LEAD = "lead"


@dataclass
class ResultadoMigracion:
    leads_total: int = 0
    leads_migrados: int = 0
    leads_ya_al_dia: int = 0
    leads_con_error: int = 0
    errores: list[str] = field(default_factory=list)
    backup_path: Optional[Path] = None


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def migrar(*, knowledge_path: Path, company: str = "laboratorio",
           hacer_backup: bool = True, dry_run: bool = False) -> ResultadoMigracion:
    """Migra los leads de `knowledge_path` para una empresa.

    `dry_run=True` no escribe nada (útil en tests y para inspeccionar antes).
    `hacer_backup=False` solo para tests; en producción siempre True.
    """
    res = ResultadoMigracion()
    if not knowledge_path.exists():
        res.errores.append(f"knowledge no existe en {knowledge_path}")
        return res

    raw = json.loads(knowledge_path.read_text(encoding="utf-8"))
    leads_dict = raw.get(company, {}).get(TIPO_LEAD, {}) or {}
    res.leads_total = len(leads_dict)
    if not leads_dict:
        return res

    if hacer_backup and not dry_run:
        bak = knowledge_path.with_suffix(f".json.bak.{_ts()}")
        shutil.copy2(knowledge_path, bak)
        res.backup_path = bak

    migrados: dict[str, dict] = {}
    for lead_id, lead_raw in leads_dict.items():
        try:
            # Garantizar campos críticos (algunos leads viejos pueden no tenerlos).
            lead_raw.setdefault("id", lead_id)
            lead_raw.setdefault("company", company)
            doc = LeadDoc.from_dict(lead_raw)
            migrado = doc.to_dict()
            # Si ya estaba al día, _schema_version coincide y no hay diferencia
            # estructural. Lo seguimos pasando por la rejilla — la idempotencia
            # se demuestra en tests.
            if lead_raw.get("_schema_version", 0) >= SCHEMA_VERSION:
                res.leads_ya_al_dia += 1
            else:
                res.leads_migrados += 1
            migrados[lead_id] = migrado
        except Exception as e:                                  # noqa: BLE001
            res.leads_con_error += 1
            res.errores.append(f"{lead_id}: {e}")
            # Conservamos el lead original sin tocar — política no destructiva.
            migrados[lead_id] = lead_raw

    if dry_run:
        return res

    # Update raw con los leads migrados (resto del knowledge intacto)
    raw.setdefault(company, {})[TIPO_LEAD] = migrados
    # Escritura atómica
    tmp = knowledge_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, knowledge_path)
    return res
