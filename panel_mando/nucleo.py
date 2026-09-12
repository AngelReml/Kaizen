# -*- coding: utf-8 -*-
"""Nucleo del Centro de Mando (D10 v0.2). El panel es PROYECCION (L1): aqui no hay
almacen propio; solo lectura de primitivas, narracion en cristiano (L4), mechas
deterministas y el escudo de errores.

Mechas ya NO asume "sin hilos" (excelencia Fase 4, Fase 1 del plan): las
herramientas de Colmena se invocan via asyncio.to_thread para no bloquear el
event loop, así que Mechas puede tocarse desde mas de un hilo a la vez —
lleva su propio candado."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone, timedelta

from core.rue import cargar_rue

TEMA_DEFECTO = "hiru"          # §11.1 — facil de cambiar
TEMAS_VALIDOS = ("hiru", "yoru")  # whitelist cerrada: `tema` es query param de usuario
MECHA_SEGUNDOS = 60            # §4 — por clase; 0 = sin mecha (interno)

# ── L4: diccionario de idioma (canon → pantalla). Prohibidas siglas en nivel 1 ──
PROHIBIDAS_NIVEL1 = ("tenant", "IRR-EXT", "IRREVERSIBLE-EXTERNA", "RUE",
                     "bitacora", "claim", "outbox", "seq", "hash_prev")

CLASE_HUMANA = {"IRREVERSIBLE-EXTERNA": "sale al mundo",
                "IRREVERSIBLE-INTERNA": "cambia cosas dentro",
                "REVERSIBLE": "interna y deshacible"}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Renderers: tipo de evento → frase humana. Generico SIEMPRE cubre (L2) ──

def _f_generico(e: dict) -> str:
    return f"({e['tipo']}) actividad registrada"


FRASES = {
    "comercial.lead.descubierto": lambda e: "encontre un negocio candidato y lo apunte con su procedencia",
    "comercial.contacto.enviado": lambda e: f"se envio un mensaje ({e['payload'].get('secuencia', '').lower() or 'contacto'})",
    "comercial.pipeline.transicion": lambda e: (
        f"el candidato paso de {e['payload'].get('de','?')} a {e['payload'].get('a','?')}"
        if e['payload'].get('veredicto') == 'APLICADA'
        else "intento de cambio de etapa rechazado (y registrado)"),
    "comercial.compromiso.detectado": lambda e: "detecte un posible compromiso; espera confirmacion humana",
    "comercial.compromiso.creado": lambda e: "compromiso confirmado y agendado",
    "comercial.pedido.atribuido": lambda e: f"pedido atribuido ({e['payload'].get('via','').lower()})",
    "plataforma.aprobacion.solicitada": lambda e: f"pedi permiso para: {e['payload'].get('accion','una accion')}",
    "plataforma.aprobacion.concedida": lambda e: "recibi tu SI" + (" y lo ejecute" if e['payload'].get('hito') else ""),
    "plataforma.aprobacion.denegada": lambda e: "recibi tu NO; no se hizo nada",
    "plataforma.aprobacion.revocada": lambda e: "deshecho a tiempo: no salio nada",
    "plataforma.aprobacion.caducada": lambda e: "caduco sin respuesta; se aborto",
    "plataforma.coste.techo_alcanzado": lambda e: "modo ahorro: se alcanzo el tope del dia",
    "plataforma.panico.activado": lambda e: "TODO PARADO por orden del operador",
    "plataforma.panico.desactivado": lambda e: "reanudado por el operador",
    "plataforma.verificacion.emitida": lambda e: f"verificacion de contenido: {e['payload'].get('veredicto','')}",
    "brand.directriz.actualizada": lambda e: "una regla de marca cambio de version",
    "operacion.pedido.confirmado": lambda e: "pedido confirmado en el plan",
    "operacion.pedido.rechazado": lambda e: "pedido sin hueco: propuse otra fecha",
    "operacion.capacidad.saturada": lambda e: "capacidad llena o sin declarar: protegi el plan",
    "operacion.pedido.hito": lambda e: f"avance registrado: {e['payload'].get('tipo_hito','hito').replace('_',' ').lower()}",
    "cumplimiento.alerta.plazo": lambda e: f"plazo cerca: quedan {e['payload'].get('dias_restantes','?')} dias",
    "cumplimiento.obligacion.incumplida": lambda e: "un plazo vencio sin cumplirse: atencion",
    "inteligencia.alerta.emitida": lambda e: f"aviso {e['payload'].get('severidad','').lower()}: {e['payload'].get('metrica','')} fuera de lo normal",
    "marketing.campana.ajustada": lambda e: "campaña pausada por presupuesto (te protegi)",
}


def _municipio_de_direccion(direccion: str) -> str:
    """Extrae el municipio de una direccion tipo 'calle X, 30009 Murcia'."""
    if not direccion:
        return ""
    cola = direccion.split(",")[-1].strip()
    return re.sub(r"^\d{5}\s*", "", cola)


def _frase_lead_descubierto(evento: dict, knowledge, empresa: str) -> str | None:
    """Interpola nombre/municipio/fuente reales del lead (D09 §14). None si no hay
    referencia resoluble: el llamador cae al genero de FRASES."""
    lead_ref = (evento.get("payload") or {}).get("lead_ref")
    if not lead_ref:
        return None
    lead = knowledge.get(empresa, "lead", lead_ref)
    if not lead:
        return None
    nombre = lead.get("nombre") or lead_ref
    municipio = _municipio_de_direccion((lead.get("ubicacion") or {}).get("direccion", ""))
    fuente = (lead.get("contacto") or {}).get("fuente_descubrimiento") or ""
    frase = f"encontre a {nombre}"
    if municipio:
        frase += f" en {municipio}"
    frase += f" via {fuente}" if fuente else " (migracion de datos existentes)"
    return frase


def render(evento: dict, knowledge=None, empresa: str | None = None) -> str:
    tipo = evento.get("tipo")
    if tipo == "comercial.lead.descubierto" and knowledge is not None and empresa:
        frase = _frase_lead_descubierto(evento, knowledge, empresa)
        if frase:
            return frase
    return FRASES.get(tipo, _f_generico)(evento)


def cobertura_renderers() -> dict:
    """L2: todo tipo del RUE tiene frase propia o generico. Devuelve el censo."""
    tipos = list(cargar_rue()["tipos"].keys())
    return {"total": len(tipos), "con_frase_propia": sum(1 for t in tipos if t in FRASES),
            "cubiertos": len(tipos)}          # el generico cubre siempre


# ── Historias: eventos agrupados por hilo y narrados (P3) ──

def historias(knowledge, empresa: str, *, limite: int = 20) -> list[dict]:
    hilos: dict[str, list] = {}
    for clave, e in sorted(knowledge.all(empresa, "evento").items()):
        hilo = e.get("correlacion_id") or f"suelto-{e.get('tipo','')}"
        hilos.setdefault(hilo, []).append((clave, e))
    out = []
    for hilo, evs in hilos.items():
        ult_clave, ult = evs[-1]
        out.append({"hilo": hilo, "pasos": len(evs), "ultimo": render(ult, knowledge, empresa),
                    "ultimo_ts": ult.get("ts", ""), "ultima_clave": ult_clave,
                    "frases": [render(e, knowledge, empresa) for _, e in evs[-6:]]})
    out.sort(key=lambda h: h["ultimo_ts"], reverse=True)
    return out[:limite]


# ── Dinero humano (P3/§E7) ──

def dinero_humano(eur: float) -> str:
    if eur < 1.0:
        c = round(eur * 100)
        return "0 €" if c == 0 else f"{c} centimo{'s' if c != 1 else ''}"
    return f"{eur:.2f} €".replace(".", ",")


# ── Escudo de errores (§6): que NO paso · por que · que puedes hacer ──

def escudo(exc: Exception) -> dict:
    m = str(exc)
    tipo = type(exc).__name__
    base = {"escudo": True, "que_no_paso": "La accion no se ejecuto.",
            "por_que": "Una proteccion de Kaizen la detuvo.",
            "que_puedes_hacer": "Revisa el detalle o pide ayuda; nada se ha roto."}
    if "S5" in m or "tercer" in m.lower():
        base.update(por_que="Este contacto ya recibio sus 2 mensajes permitidos (la ley marca el limite).",
                    que_puedes_hacer="Nada que hacer: Kaizen te protegio.")
    elif "S4" in m or "exclusion" in m.lower():
        base.update(por_que="Esa persona pidio no recibir mensajes; su decision se respeta siempre.",
                    que_puedes_hacer="Nada que hacer: es su derecho.")
    elif "S3" in m or "bloques" in m.lower():
        base.update(por_que="Al mensaje le faltan los bloques legales (quien eres, como darse de baja, sus derechos).",
                    que_puedes_hacer="Corrige el borrador y vuelve a intentarlo.")
    elif tipo == "TechoAlcanzado":
        base.update(por_que="Se alcanzo el tope de gasto del dia (modo ahorro).",
                    que_puedes_hacer="Lo urgente ya aprobado se completara; el resto espera a mañana o sube el tope en Ajustes.")
    elif tipo == "PanicoActivo":
        base.update(por_que="TODO PARADO esta activo: nada sale de Kaizen.",
                    que_puedes_hacer="Cuando quieras, pulsa Reanudar; no se ha perdido nada.")
    elif tipo == "PalancaCerrada":
        base.update(por_que="Ese tipo de accion esta apagado con su interruptor.",
                    que_puedes_hacer="Puedes encenderlo en Ajustes si de verdad lo quieres.")
    elif tipo == "TransicionAprobacionInvalida":
        base.update(por_que="Esa tarjeta ya no esta en un estado que permita ese gesto (quiza ya se decidio).",
                    que_puedes_hacer="Refresca La Mañana y mira su estado actual.")
    elif "identidad" in m.lower() or "quien" in m.lower():
        base.update(por_que="Falto decir quien da la orden.",
                    que_puedes_hacer="Vuelve a intentarlo desde el panel (firma automatica).")
    base["detalle_tecnico"] = f"{tipo}: {m}"     # solo visible al expandir
    return base


# ── Mechas deterministas (§4): el pulso del panel las quema ──

class Mechas:
    """Candado propio (Fase 1 de excelencia): con to_thread en juego, mas de
    un hilo puede armar/consumir/leer mechas casi a la vez. `encendidas()`
    era el punto mas fragil — iteraba `self._arm.values()` sin copiar antes
    de `sorted()`, y un armar/consumir concurrente podia lanzar
    `RuntimeError: dictionary changed size during iteration`."""

    def __init__(self, segundos: int = MECHA_SEGUNDOS) -> None:
        self.segundos = segundos
        self._arm: dict[str, dict] = {}
        self._lock = threading.Lock()

    def armar(self, ap_id: str, empresa: str, *, ahora: datetime | None = None) -> dict:
        ahora = ahora or datetime.now(timezone.utc)
        m = {"aprobacion": ap_id, "empresa": empresa,
             "enciende": ahora.isoformat(),
             "dispara": (ahora + timedelta(seconds=self.segundos)).isoformat()}
        with self._lock:
            self._arm[ap_id] = m
        return m

    def desarmar(self, ap_id: str) -> bool:
        with self._lock:
            return self._arm.pop(ap_id, None) is not None

    def encendidas(self) -> list[dict]:
        with self._lock:
            return sorted(self._arm.values(), key=lambda m: m["dispara"])

    def vencidas(self, *, ahora: datetime | None = None) -> list[dict]:
        ahora = ahora or datetime.now(timezone.utc)
        with self._lock:
            return [m for m in self._arm.values()
                    if datetime.fromisoformat(m["dispara"]) <= ahora]

    def consumir(self, ap_id: str) -> None:
        with self._lock:
            self._arm.pop(ap_id, None)


# ── Resumen de La Mañana (P2): plantillas deterministas, cada frase con fuente ──

def resumen_manana(knowledge, empresa: str, *, cola=None, libro=None,
                   pendientes: int = 0, ahora: datetime | None = None) -> list[dict]:
    ahora = ahora or datetime.now(timezone.utc)
    frases = []
    if pendientes:
        frases.append({"texto": f"Hay {pendientes} accion{'es' if pendientes != 1 else ''} esperando tu SI.",
                       "fuente": "#tarjetas"})
    else:
        frases.append({"texto": "Nada espera tu decision ahora mismo.", "fuente": "#tarjetas"})
    if libro is not None:
        gasto = libro.gasto_dia(empresa)
        try:
            tope = libro._techo_tenant(empresa)
        except Exception:                          # noqa: BLE001
            tope = 0.0
        frases.append({"texto": f"Gastado hoy: {dinero_humano(gasto)}"
                                + (f" de {dinero_humano(tope)}." if tope else "."),
                       "fuente": "/sala#dinero"})
    plazos = []
    for o in knowledge.all(empresa, "obligacion").values():
        if o.get("estado") in ("CUMPLIDA", "AUDITADA", "CERRADA", "RECHAZADA"):
            continue
        try:
            limite = datetime.fromisoformat(o["fecha_limite"])
            if limite.tzinfo is None:
                limite = limite.replace(tzinfo=timezone.utc)
            dias = (limite - ahora).days
        except Exception:                          # noqa: BLE001
            continue
        if dias <= 30:
            plazos.append((dias, o["nombre"]))
    for dias, nombre in sorted(plazos)[:3]:
        frases.append({"texto": f"Plazo cerca: {nombre} (quedan {dias} dias).",
                       "fuente": "/sala#cubos"})
    criticas = [a for a in knowledge.all(empresa, "alerta").values()
                if a.get("severidad") == "CRITICA" and a.get("estado") == "EMITIDA"]
    if criticas:
        frases.append({"texto": f"{len(criticas)} aviso(s) importantes de Inteligencia por revisar.",
                       "fuente": "/sala#cubos"})
    return frases
