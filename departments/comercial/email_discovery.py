"""Descubrimiento de email del decisor desde la web del lead (Fase 1.5).

Los 422 leads enriquecidos vienen de Google Places, que NO devuelve email. Esta capa
rellena ese hueco haciendo fetch real de la web del lead y extrayendo el correo más
plausible para contacto comercial.

Heurística (sin LLM, regex + ranking):
  1. Saltamos URLs de redes sociales (facebook/instagram/twitter/x/tiktok) donde el email
     no está expuesto en HTML.
  2. Probamos la URL principal y, si no aparece email, los habituales `/contacto` y
     `/contact`.
  3. Filtramos emails "técnicos" (noreply, postmaster, webmaster, abuse, newsletter…).
  4. Preferimos prefijos de contacto comercial (contacto@, info@, hola@, reservas@,
     comercial@, ventas@) si están disponibles; si no, el primero que aparece.

Persiste el email descubierto en `lead.contacto.email` y deja una traza en
`lead.email_discovery` con la fuente y el método.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urlparse

from agentes import _extract_emails, _fetch_page
from departments.comercial.lifecycle import EstadoLead, LeadStore

REDES_SOCIALES = ("facebook.com", "instagram.com", "twitter.com", "x.com",
                  "tiktok.com", "linkedin.com", "youtube.com", "pinterest.com")
PREFIJOS_PREFERIDOS = ("contacto@", "info@", "hola@", "reservas@", "comercial@",
                       "ventas@", "atencion@", "buzon@", "administracion@", "direccion@")
PREFIJOS_DESCARTAR = ("noreply", "no-reply", "newsletter", "postmaster", "webmaster",
                      "abuse", "spam", "unsubscribe", "feedback@elemu", "support@wix")


@dataclass
class ResultadoDescubrimiento:
    procesados: int = 0
    con_email_previo: int = 0
    descubiertos: int = 0
    sin_web: int = 0
    web_solo_social: int = 0
    no_encontrado: int = 0
    errores: int = 0
    detalle: list[dict] = field(default_factory=list)


def _es_social(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(s in host for s in REDES_SOCIALES)


def _filtrar_y_rankear(emails: list[str]) -> str | None:
    """Devuelve el email "más comercial" de la lista, o None si todos son descartables."""
    candidatos = []
    for e in emails:
        low = e.lower()
        if any(d in low for d in PREFIJOS_DESCARTAR):
            continue
        candidatos.append(e)
    if not candidatos:
        return None
    # Preferimos prefijos comerciales sobre genéricos.
    for prefijo in PREFIJOS_PREFERIDOS:
        for c in candidatos:
            if c.lower().startswith(prefijo):
                return c
    return candidatos[0]


def descubrir_email_de_web(web_url: str, *, timeout: int = 8,
                            fetcher=_fetch_page) -> tuple[str | None, str]:
    """Devuelve (email | None, motivo). `fetcher` es inyectable para tests."""
    if not web_url or not web_url.startswith(("http://", "https://")):
        return None, "sin_web"
    if _es_social(web_url):
        return None, "web_solo_social"
    base = web_url.rstrip("/")
    paginas = [web_url, f"{base}/contacto", f"{base}/contact"]
    for url in paginas:
        try:
            texto = fetcher(url, timeout=timeout) if fetcher is _fetch_page else fetcher(url)
        except Exception:
            continue
        if not texto:
            continue
        encontrados = _extract_emails(texto)
        if not encontrados:
            continue
        elegido = _filtrar_y_rankear(encontrados)
        if elegido:
            return elegido, f"web:{urlparse(url).path or '/'}"
    return None, "no_encontrado"


def descubrir_emails(lead_store: LeadStore, *, limite: int | None = None,
                     lead_id: str | None = None, max_workers: int = 6,
                     fetcher=_fetch_page, verbose: bool = True) -> ResultadoDescubrimiento:
    """Recorre leads ENRIQUECIDOS sin email, intenta descubrir y persiste."""
    if lead_id:
        lead = lead_store.get(lead_id)
        leads = [lead] if lead else []
    else:
        leads = lead_store.listar(EstadoLead.ENRIQUECIDO)
    if limite:
        leads = leads[:limite]
    res = ResultadoDescubrimiento()

    def procesar(l: dict) -> tuple[str, str | None, str]:
        contacto = l.get("contacto") or {}
        if contacto.get("email"):
            return l["id"], None, "ya_tenia"
        web = contacto.get("web")
        if not web:
            return l["id"], None, "sin_web"
        email, motivo = descubrir_email_de_web(web, fetcher=fetcher)
        return l["id"], email, motivo

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(procesar, l): l for l in leads}
        for f in as_completed(futs):
            l = futs[f]
            try:
                lead_id_r, email, motivo = f.result()
            except Exception as e:
                res.errores += 1
                res.detalle.append({"lead": l["id"], "error": str(e)})
                continue
            res.procesados += 1
            if motivo == "ya_tenia":
                res.con_email_previo += 1
                continue
            if motivo == "sin_web":
                res.sin_web += 1
                continue
            if motivo == "web_solo_social":
                res.web_solo_social += 1
                continue
            if email:
                res.descubiertos += 1
                # Persistir el email + traza
                nodo = lead_store.get(lead_id_r)
                if nodo is None:
                    continue
                nodo.setdefault("contacto", {})["email"] = email
                nodo["email_discovery"] = {"email": email, "fuente": motivo, "metodo": "regex"}
                lead_store.k.add(lead_store.company, lead_store.TIPO, lead_id_r, nodo)
                res.detalle.append({"lead": lead_id_r, "email": email, "fuente": motivo})
            else:
                res.no_encontrado += 1

    if verbose:
        print(f"[email_discovery] procesados={res.procesados} "
              f"descubiertos={res.descubiertos} "
              f"ya_tenían={res.con_email_previo} "
              f"sin_web={res.sin_web} solo_social={res.web_solo_social} "
              f"no_encontrado={res.no_encontrado} errores={res.errores}")
    return res
