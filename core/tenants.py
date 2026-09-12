"""Registro de tenants y primitivas de datos del sustrato — D00 §2.3, §2.4, §9.3 (bloque B2).

Cinco primitivas, cinco tests: exportar_tenant, borrar_dato_cliente (con acta),
snapshot, retencion, y la verificacion de registro. Reglas duras:

  - Ningun tenant opera sin ficha; ninguna ficha sin mandato (D00 §2.3).
  - El borrado es IRREVERSIBLE-INTERNA: exige export previo (manifest) y
    confirmar=True; por defecto todo es dry-run (fail-safe GR-04).
  - Toda accion destructiva deja acta JSON con sha256 del contenido exportado.
  - I1: estas primitivas operan SOLO sobre el tenant pedido; los tests de
    aislamiento adversario lo atacan.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from core.rutas import ruta_registro_tenants


class TenantInvalido(ValueError):
    """Ficha ausente o malformada: el tenant no puede operar (D00 §2.3)."""


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1)


# ── Registro ─────────────────────────────────────────────────────────────────

def cargar_registro(ruta: Path | None = None) -> dict:
    """Carga y VALIDA el registro. Ficha sin id/mandato/estado = registro invalido."""
    ruta = ruta or ruta_registro_tenants()
    data = json.loads(Path(ruta).read_text(encoding="utf-8"))
    tenants = data.get("tenants", [])
    if not tenants:
        raise TenantInvalido("registro sin tenants")
    vistos = set()
    for t in tenants:
        tid = t.get("id", "")
        if not tid or tid != tid.lower() or not tid.isascii():
            raise TenantInvalido(f"id de tenant invalido: {tid!r} (minuscula ASCII estable)")
        if tid in vistos:
            raise TenantInvalido(f"id duplicado: {tid}")
        vistos.add(tid)
        if t.get("estado") not in ("activo", "pausado", "baja"):
            raise TenantInvalido(f"{tid}: estado invalido {t.get('estado')!r}")
        m = t.get("mandato")
        if not m or "nivel_por_defecto" not in m:
            raise TenantInvalido(f"{tid}: ficha sin mandato (D00 §2.3: ninguna ficha sin mandato)")
        if m["nivel_por_defecto"] not in ("CERO", "BAJA", "MEDIA", "ALTA"):
            raise TenantInvalido(f"{tid}: nivel de autonomia invalido {m['nivel_por_defecto']!r}")
    return data


def get_tenant(tenant_id: str, ruta: Path | None = None) -> dict:
    for t in cargar_registro(ruta)["tenants"]:
        if t["id"] == tenant_id:
            return t
    raise TenantInvalido(f"tenant sin ficha: {tenant_id!r} — no puede operar")


def mandato(tenant_id: str, ruta: Path | None = None) -> dict:
    return get_tenant(tenant_id, ruta)["mandato"]


# ── Primitivas de datos (D00 §9.3) ───────────────────────────────────────────

def exportar_tenant(knowledge, tenant_id: str, destino: Path) -> dict:
    """Export completo del DATO_CLIENTE de un tenant (cl. 9 del contrato tipo).

    Escribe <destino>/<tenant>_export.json y devuelve el manifest con sha256.
    Solo lee del tenant pedido: nada de otros tenants entra en el paquete.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    paquete = {"tenant": tenant_id, "exportado_en": _ts(),
               "datos": knowledge.all(tenant_id)}
    contenido = _canon(paquete)
    fichero = destino / f"{tenant_id}_export.json"
    fichero.write_text(contenido, encoding="utf-8")
    releido = fichero.read_text(encoding="utf-8")          # E1: verificar escritura
    if releido != contenido:
        raise IOError(f"E1: desfase al escribir {fichero}")
    manifest = {"tenant": tenant_id, "fichero": str(fichero),
                "sha256": _sha(contenido), "ts": paquete["exportado_en"],
                "tipos": {t: len(v) for t, v in paquete["datos"].items()}}
    return manifest


def borrar_dato_cliente(knowledge, tenant_id: str, *, export_manifest: dict | None = None,
                        confirmar: bool = False, acta_dir: Path | None = None) -> dict:
    """Borrado verificable del DATO_CLIENTE (D00 §2.4). Secuencia obligatoria:
    export previo (manifest) → borrado → acta. Sin confirmar: dry-run (lista, cero efectos).
    """
    datos = knowledge.all(tenant_id)
    plan = {t: sorted(v.keys()) for t, v in datos.items()}
    if not confirmar:
        return {"dry_run": True, "tenant": tenant_id, "plan_borrado": plan}
    if not export_manifest or export_manifest.get("tenant") != tenant_id:
        raise TenantInvalido("borrado sin export previo del MISMO tenant (D00 §2.4)")
    borrados = 0
    for tipo, claves in plan.items():
        for k in claves:
            if knowledge.delete(tenant_id, tipo, k):
                borrados += 1
    acta = {"accion": "plataforma.datos.borrados", "tenant": tenant_id, "ts": _ts(),
            "borrados": borrados, "export_sha256": export_manifest["sha256"],
            "plan": plan}
    acta["hash_acta"] = _sha(_canon({k: v for k, v in acta.items() if k != "hash_acta"}))
    if acta_dir:
        p = Path(acta_dir); p.mkdir(parents=True, exist_ok=True)
        f = p / f"acta_borrado_{tenant_id}.json"
        f.write_text(_canon(acta), encoding="utf-8")
        if f.read_text(encoding="utf-8") != _canon(acta):
            raise IOError(f"E1: desfase al escribir {f}")
    return acta


def snapshot(knowledge, tenant_id: str, destino: Path) -> dict:
    """Copia datada del estado del tenant con hash verificable (D00 §8.5)."""
    destino = Path(destino); destino.mkdir(parents=True, exist_ok=True)
    contenido = _canon({"tenant": tenant_id, "datos": knowledge.all(tenant_id)})
    dia = datetime.now(timezone.utc).strftime("%Y%m%d")
    f = destino / f"snapshot_{tenant_id}_{dia}.json"
    f.write_text(contenido, encoding="utf-8")
    if f.read_text(encoding="utf-8") != contenido:
        raise IOError(f"E1: desfase al escribir {f}")
    return {"fichero": str(f), "sha256": _sha(contenido)}


def retencion(knowledge, tenant_id: str, *, dias: int = 365, ahora: datetime | None = None,
              confirmar: bool = False) -> dict:
    """LIA §3.8: leads sin transicion en <dias> → candidatos a supresion.
    Dry-run por defecto; el borrado real exige confirmar y deja acta implicita en el retorno."""
    ahora = ahora or datetime.now(timezone.utc)
    candidatos = []
    for lead_id, lead in knowledge.all(tenant_id, "lead").items():
        ult = lead.get("fecha_ultima_transicion") or lead.get("actualizado_en") or ""
        try:
            dt = datetime.fromisoformat(ult)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if (ahora - dt).days > dias:
            candidatos.append(lead_id)
    resultado = {"tenant": tenant_id, "dias": dias, "candidatos": sorted(candidatos),
                 "dry_run": not confirmar, "ts": _ts()}
    if confirmar:
        for lid in candidatos:
            knowledge.delete(tenant_id, "lead", lid)
        resultado["accion"] = "plataforma.retencion.ejecutada"
    return resultado
