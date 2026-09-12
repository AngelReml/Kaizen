"""Entregabilidad de email (E3) — herramientas hasta la frontera del dominio.

CORRECCIONES E3 y roadmap F4: antes del primer envio a terceros hacen falta (1) SPF/DKIM/
DMARC verificados con `dig`, (2) rampa <=10/dia documentada, (3) test de bandeja a cuentas
propias, y (4) dominio frio o no autenticado = PARAR y reportar. La DECISION del dominio
emisor es de Ivan (DR-10) y no se puede inventar (R3): este modulo deja lista TODA la
maquinaria que no depende del dominio, para que el dia que Ivan lo decida sea ejecutar, no
construir.

Diseño:
  - `comandos_dig(dominio, selector)` documenta los comandos EXACTOS (no ejecuta red aqui;
    R1/no-red). El operador (o el agente en la maquina de Ivan) los corre y pega la salida.
  - `analizar_dns(spf_txt, dmarc_txt, dkim_txt)` es LOGICA PURA que juzga esa salida: SPF,
    DMARC y DKIM presentes y bien formados → verde; algo falta → dominio frio = PARAR.
  - `RampaEnvio` es el contador persistente <=N/dia (fail-closed si el fichero se corrompe).
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MAX_DIA_DEFECTO = 10          # E3.2: rampa inicial <=10/dia


def _hoy() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── 1 · Comandos dig documentados (el operador los corre contra el dominio real) ──

def comandos_dig(dominio: str, selector: str = "default") -> dict:
    """Los comandos EXACTOS a documentar en el informe (E3.1). No ejecutan red aqui."""
    return {
        "spf":   f"dig +short TXT {dominio}",
        "dmarc": f"dig +short TXT _dmarc.{dominio}",
        "dkim":  f"dig +short TXT {selector}._domainkey.{dominio}",
    }


# ── 2 · Analisis puro de la salida dig (juzga; no consulta) ───────────────────

@dataclass
class DNSVeredicto:
    dominio: str
    spf_ok: bool = False
    dmarc_ok: bool = False
    dkim_ok: bool = False
    dmarc_politica: str = ""
    problemas: list[str] = field(default_factory=list)

    @property
    def autenticado(self) -> bool:
        return self.spf_ok and self.dmarc_ok and self.dkim_ok

    @property
    def dominio_frio(self) -> bool:
        """E3.4: frio o no autenticado = PARAR."""
        return not self.autenticado


def analizar_dns(dominio: str, *, spf_txt: str = "", dmarc_txt: str = "",
                 dkim_txt: str = "") -> DNSVeredicto:
    """Juzga la salida de los tres `dig`. Logica pura, testeable sin red."""
    v = DNSVeredicto(dominio=dominio)

    if re.search(r"v=spf1", spf_txt, re.I):
        v.spf_ok = True
        if not re.search(r"[-~]all", spf_txt, re.I):
            v.problemas.append("SPF sin mecanismo -all/~all (demasiado permisivo)")
    else:
        v.problemas.append("SPF ausente (no hay registro v=spf1)")

    if re.search(r"v=DMARC1", dmarc_txt, re.I):
        v.dmarc_ok = True
        m = re.search(r"\bp=(none|quarantine|reject)\b", dmarc_txt, re.I)
        v.dmarc_politica = (m.group(1).lower() if m else "")
        if v.dmarc_politica in ("", "none"):
            v.problemas.append("DMARC en p=none (monitor): subir a quarantine/reject tras warm-up")
    else:
        v.problemas.append("DMARC ausente (_dmarc sin v=DMARC1)")

    if re.search(r"v=DKIM1", dkim_txt, re.I) and re.search(r"p=[A-Za-z0-9+/]{20,}", dkim_txt):
        v.dkim_ok = True
    else:
        v.problemas.append("DKIM ausente o sin clave publica (selector incorrecto?)")

    return v


class DominioFrio(RuntimeError):
    """E3.4: el dominio no esta autenticado; PARAR y reportar (no quemar el principal)."""


def exigir_dominio_apto(veredicto: DNSVeredicto) -> None:
    if veredicto.dominio_frio:
        raise DominioFrio(
            f"dominio {veredicto.dominio!r} NO apto para envio: "
            + "; ".join(veredicto.problemas)
            + ". PARAR (E3.4): calentar un subdominio dedicado, jamas quemar el principal.")


# ── 3 · Rampa persistente <=N/dia (fail-closed) ───────────────────────────────

_lock = threading.Lock()


class RampaEnvio:
    def __init__(self, ruta: Path | str, *, max_dia: int | None = None) -> None:
        self.ruta = Path(ruta)
        self.max_dia = max_dia if max_dia is not None else int(
            os.environ.get("KAIZEN_RAMPA_MAX_DIA", str(MAX_DIA_DEFECTO)))

    def _leer(self) -> int:
        if not self.ruta.exists():
            return 0
        try:
            d = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.max_dia          # fail-closed: contador ilegible = cupo agotado
        return int(d.get("n", 0)) if d.get("dia") == _hoy() else 0

    def enviados_hoy(self) -> int:
        return self._leer()

    def restantes_hoy(self) -> int:
        return max(0, self.max_dia - self._leer())

    def puede_enviar(self) -> bool:
        return self.restantes_hoy() > 0

    def registrar_envio(self) -> int:
        """Incrementa el contador del dia. Llamar SOLO tras un envio real. E1 al escribir."""
        with _lock:
            n = self._leer() + 1
            if n > self.max_dia:
                raise RampaAgotada(
                    f"rampa diaria agotada ({self.max_dia}/dia): no se envia mas hoy (E3.2)")
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            contenido = json.dumps({"dia": _hoy(), "n": n}, ensure_ascii=False, sort_keys=True)
            tmp = self.ruta.with_suffix(".tmp")
            tmp.write_text(contenido, encoding="utf-8")
            os.replace(tmp, self.ruta)
            if self.ruta.read_text(encoding="utf-8") != contenido:      # E1
                raise IOError(f"E1: desfase al escribir la rampa en {self.ruta}")
            return n


class RampaAgotada(RuntimeError):
    """E3.2: se alcanzo el tope diario de la rampa de calentamiento."""


# ── 4 · Test de bandeja (a cuentas propias) — plan documentado ────────────────

def plan_test_bandeja(dominio: str, cuentas_propias: list[str]) -> dict:
    """E3.3: el test de colocacion se hace a cuentas PROPIAS (nunca a leads) antes de tocar
    los 466. Devuelve el plan; el envio real lo dispara el operador con el ejecutor F3."""
    return {
        "objetivo": "verificar carpeta de llegada (bandeja, no spam) antes de tocar leads",
        "destinos": [c for c in cuentas_propias if "@" in c] or ["<pon aqui tus cuentas Gmail/Outlook>"],
        "criterio_verde": "los 3 llegan a Bandeja de entrada (no Spam/Promociones)",
        "si_cae_en_spam": ("si algun mensaje cae en Spam: PARAR: revisar SPF/DKIM/DMARC y "
                           "reputacion; no seguir con leads"),
        "dominio": dominio,
    }
