"""Apuestas: hipotesis de nicho con su dosier, su prueba barata y lo aprendido.

Concepto firmado por el operador: docs/APUESTAS_Y_DOSIER_v0.md (K1 L1 M1 N1). Aqui vive el
almacen, la maquina de estados, la validacion DETERMINISTA del dosier, el control de novedad y la
seleccion por cuotas. Nada de esto usa un modelo para decidir: las puertas son codigo.

    BORRADOR -> DOSIER -> ELEGIDA -> EN_PRUEBA -> MEDIDA -> CRECE (-> EN_PRUEBA, nueva ronda)
        |          |         |                         \\-> PODADA
        +----------+---------+-----------> DESCARTADA

- BORRADOR y DOSIER los mueve Inteligencia; todo lo demas lo decide el OPERADOR (la regla solo
  PROPONE CRECE/PODADA al medir; nada se poda ni crece solo).
- Cerrar (PODADA, DESCARTADA o paso a CRECE) exige un APRENDIZAJE: es el abono del jardin.
- Cada transicion se sella en la bitacora (`inteligencia.apuesta.*`) con ids, estados y huellas:
  NUNCA el texto del dosier. El sellado va FUERA del candado de datos (el orden de candados de la
  bitacora es el inverso; hacerlo dentro produjo un interbloqueo real en core/autonomia.py).
- N1: mientras no exista el flujo de financiacion, una prueba solo admite coste maximo 0 EUR.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from core.rue import Sobre, nuevo_id

COLECCION = "apuesta"

ESTADOS = ("BORRADOR", "DOSIER", "ELEGIDA", "EN_PRUEBA", "MEDIDA", "CRECE", "PODADA", "DESCARTADA")
TRANSICIONES = {
    "BORRADOR": {"DOSIER", "DESCARTADA"},
    "DOSIER": {"ELEGIDA", "DESCARTADA"},
    "ELEGIDA": {"EN_PRUEBA", "DESCARTADA"},
    "EN_PRUEBA": {"MEDIDA"},
    "MEDIDA": {"CRECE", "PODADA"},
    "CRECE": {"EN_PRUEBA"},          # nueva ronda, con su propio criterio
    "PODADA": set(),
    "DESCARTADA": set(),
}
TERMINALES = frozenset({"PODADA", "DESCARTADA"})

# ── vocabularios cerrados de las coordenadas (docs/APUESTAS_Y_DOSIER_v0.md §6) ──
MODELOS_INGRESO = ("servicio_por_encargo", "producto_digital", "microsuscripcion", "contenido_audiencia",
                   "afiliacion", "intermediacion", "automatizacion_como_servicio", "datos_informes", "otro")
CLIENTES = ("particular", "autonomo", "pyme", "empresa_grande", "comunidad_aficionados")
CANALES = ("busqueda_organica", "redes_sociales", "comunidades_foros", "contacto_directo", "alianzas",
           "marketplace_existente", "boca_a_boca")
MERCADOS = ("es_ES", "es_LATAM", "en", "otro")
COSTES_INICIALES = ("0", "<=15", "<=50", ">50")
TIEMPOS_SENAL = ("<=7d", "<=30d", ">30d")
ETIQUETAS = ("VERIFICADA", "RECORDADA", "SUPUESTO")
RIESGOS = ("bajo", "medio", "alto")
COMPARADORES = (">=", "<=")

MAX_TXT = 1200          # tope de cualquier texto libre
MAX_ITEM = 300          # tope de cada elemento de una lista
MAX_LISTA = 12
PLAZO_MAX_DIAS = 180
UMBRAL_SIMILITUD = 0.5  # (propuesta) Jaccard de palabras por encima del cual un borrador es "el mismo"
UMBRAL_SECTOR = 0.6

CUOTAS = {"max_mismo_cliente": 2, "max_mismo_canal": 2, "min_modelos": 3,
          "min_coste0_senal7": 1, "min_fuera_capacidades": 1}


class ApuestaInvalida(ValueError):
    """Entrada o transicion rechazada; el mensaje dice por que (se muestra, no se oculta)."""


class TransicionInvalida(ApuestaInvalida):
    pass


class Repetida(ApuestaInvalida):
    def __init__(self, razon: str, similar_a: str = "") -> None:
        super().__init__(razon)
        self.razon = razon
        self.similar_a = similar_a


# ── texto: limpieza y normalizacion ─────────────────────────────────────────

def _txt(v, maximo: int = MAX_TXT) -> str:
    """Texto acotado y sin caracteres de control. Lo que no es str vale ''."""
    if not isinstance(v, str):
        return ""
    v = unicodedata.normalize("NFC", v)
    v = "".join(" " if (unicodedata.category(c) == "Cc" and c not in "\n\t") else c for c in v)
    return v.strip()[:maximo]


def _lista(v, maximo: int = MAX_LISTA, largo: int = MAX_ITEM) -> list[str]:
    if not isinstance(v, (list, tuple)):
        return []
    return [t for t in (_txt(x, largo) for x in v[:maximo]) if t]


def _sin_acentos(s: str) -> str:
    """Minusculas, sin acentos ni caracteres de formato invisibles (Cf: ancho cero, etc.) que servirian
    para partir una palabra vetada y esquivar la comprobacion."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower())
                   if not unicodedata.combining(c) and unicodedata.category(c) != "Cf")


_PALABRAS_VACIAS = frozenset(
    "para como pero porque cuando donde quien quienes cual cuales este esta esto estos estas ese esa eso "
    "esos esas aquel aquella con sin sobre entre desde hasta hacia segun durante mediante tras ante bajo "
    "los las unos unas del por que una uno son ser han has hay mas muy tan tambien solo cada todo toda "
    "todos todas sus mis tus nuestro nuestra otros otras otro otra puede pueden debe deben hacer hace "
    "tiene tienen tener ser ver sea sean the and for with that this from".split())


def palabras(texto: str, minimo: int = 3) -> frozenset[str]:
    """Conjunto de palabras significativas (sin acentos, sin vacias, `minimo` o mas letras/cifras de CUALQUIER
    alfabeto: el cirilico o el griego tambien cuentan, no solo el latino)."""
    return frozenset(t for t in re.findall(r"[^\W_]{%d,}" % minimo, _sin_acentos(texto or ""))
                     if t not in _PALABRAS_VACIAS)


def similitud(a: str, b: str) -> float:
    """Jaccard de palabras significativas: 0 = nada en comun, 1 = lo mismo."""
    pa, pb = palabras(a), palabras(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


# ── vetos (Suelo §5): lista MINIMA y explicita; lo demas lo ve el operador ──

VETOS = {
    "resenas_falsas": r"resenas? (falsas?|compradas?|inventadas?)|opiniones (falsas|compradas)|fake reviews?|comprar resenas?",
    "spam": r"\bspam\b|(correos?|emails?|mensajes?) masivos? (no solicitados?|sin consentimiento)|envios? masivos? sin consentimiento",
    "engano": r"\bestafas?\b|esquema piramidal|\bponzi\b|\bphishing\b|suplantacion de identidad|suplantar (la )?identidad",
    "dinero_politico": r"dinero politico|financiacion politica|campanas? electoral(es)?|donacion(es)? a partidos?",
    "ilegal": r"\bmalware\b|\bransomware\b|venta de drogas|armas? ilegal(es)?|pornograf",
}
_VETOS_RE = {k: re.compile(v) for k, v in VETOS.items()}


def _textos(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _textos(v)]
    if isinstance(obj, (list, tuple)):
        return [t for v in obj for t in _textos(v)]
    return []


def sin_fuentes(dosier: dict) -> dict:
    """El dosier sin los extractos de fuentes externas: los vetos juzgan lo que ESCRIBE el modelo, no un
    articulo legitimo sobre, p. ej., como evitar una estafa (que el modelo no podria "arreglar")."""
    d = dict(dosier)
    d["evidencia"] = [{k: v for k, v in it.items() if k != "fuente"} if isinstance(it, dict) else it
                      for it in dosier.get("evidencia", [])]
    return d


def comprobar_vetos(obj) -> list[str]:
    """['veto <categoria>: «frase»', ...] si algun texto cae en una categoria vetada."""
    hallados = []
    for t in _textos(obj):
        n = _sin_acentos(t)
        for cat, rx in _VETOS_RE.items():
            m = rx.search(n)
            if m:
                hallados.append(f"veto {cat}: «{m.group(0)}»")
    return sorted(set(hallados))


# ── borrador, coordenadas, dosier ───────────────────────────────────────────

def limpiar_borrador(b) -> dict:
    b = b if isinstance(b, dict) else {}
    return {"titulo": _txt(b.get("titulo"), 120), "problema": _txt(b.get("problema"), 600),
            "publico": _txt(b.get("publico"), 300), "por_que_ahora": _txt(b.get("por_que_ahora"), 400)}


def validar_borrador(b: dict) -> list[str]:
    e = []
    if len(b["titulo"]) < 5:
        e.append("titulo: minimo 5 caracteres")
    for campo in ("problema", "publico"):
        if len(b[campo]) < 10:
            e.append(f"{campo}: minimo 10 caracteres")
    return e


def limpiar_coordenadas(c) -> dict:
    c = c if isinstance(c, dict) else {}
    return {"modelo_ingreso": _txt(c.get("modelo_ingreso"), 40), "cliente": _txt(c.get("cliente"), 40),
            "canal": _txt(c.get("canal"), 40), "mercado": _txt(c.get("mercado"), 20),
            "coste_inicial": _txt(c.get("coste_inicial"), 10), "tiempo_senal": _txt(c.get("tiempo_senal"), 10),
            "sector": _txt(c.get("sector"), 60)}


def validar_coordenadas(c: dict) -> list[str]:
    e = []
    for campo, vocab in (("modelo_ingreso", MODELOS_INGRESO), ("cliente", CLIENTES), ("canal", CANALES),
                         ("mercado", MERCADOS), ("coste_inicial", COSTES_INICIALES),
                         ("tiempo_senal", TIEMPOS_SENAL)):
        if c[campo] not in vocab:
            e.append(f"coordenadas.{campo}: {c[campo]!r} no esta en {list(vocab)}")
    if len(c["sector"]) < 2:
        e.append("coordenadas.sector: minimo 2 caracteres")
    return e


def _num(v):
    """Numero finito (no bool) o None. Un entero gigante o un valor raro NO lanza: es simplemente invalido."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        return float(v) if math.isfinite(v) else None
    except (OverflowError, ValueError):
        return None


def _fecha_iso(v) -> str:
    v = _txt(v, 10)
    try:
        return datetime.strptime(v, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def _url_http(v) -> str:
    v = _txt(v, 500)
    return v if re.match(r"^https?://[^\s]+$", v) else ""


def limpiar_dosier(d) -> dict:
    """Copia con SOLO los campos conocidos, textos acotados y tipos coherentes (nada del modelo
    entra tal cual). La validez se comprueba aparte, en `validar_dosier`."""
    d = d if isinstance(d, dict) else {}
    nicho = d.get("nicho") if isinstance(d.get("nicho"), dict) else {}
    coste = d.get("coste") if isinstance(d.get("coste"), dict) else {}
    senal = d.get("senal") if isinstance(d.get("senal"), dict) else {}
    cap = d.get("capacidades") if isinstance(d.get("capacidades"), dict) else {}
    real = d.get("senal_real") if isinstance(d.get("senal_real"), dict) else {}
    riesgo = d.get("riesgo_legal") if isinstance(d.get("riesgo_legal"), dict) else {}
    evid = []
    for it in (d.get("evidencia") if isinstance(d.get("evidencia"), list) else [])[:MAX_LISTA]:
        if not isinstance(it, dict):
            continue
        item = {"afirmacion": _txt(it.get("afirmacion"), 500), "etiqueta": _txt(it.get("etiqueta"), 12).upper()}
        f = it.get("fuente")
        if isinstance(f, dict):
            item["fuente"] = {"url": _url_http(f.get("url")), "fecha": _fecha_iso(f.get("fecha")),
                              "extracto": _txt(f.get("extracto"), 600)}
        if _txt(it.get("nota"), 200):
            item["nota"] = _txt(it.get("nota"), 200)
        evid.append(item)
    plazo = senal.get("plazo_dias")
    return {
        "nicho": {"problema": _txt(nicho.get("problema"), 600), "publico": _txt(nicho.get("publico"), 300),
                  "por_que_ahora": _txt(nicho.get("por_que_ahora"), 400)},
        "evidencia": evid,
        "coste": {"importe_eur": _num(coste.get("importe_eur")), "concepto": _txt(coste.get("concepto"), 200),
                  "alternativa_gratuita": _txt(coste.get("alternativa_gratuita"), 400)},
        "senal": {"que_se_mide": _txt(senal.get("que_se_mide"), 300), "umbral": _num(senal.get("umbral")),
                  "comparador": _txt(senal.get("comparador"), 2), "plazo_dias": plazo if isinstance(plazo, int)
                  and not isinstance(plazo, bool) else None, "fuente_dato": _txt(senal.get("fuente_dato"), 300)},
        "capacidades": {"necesarias": _lista(cap.get("necesarias")), "tiene": _lista(cap.get("tiene")),
                        "faltan": _lista(cap.get("faltan"))},
        "necesita_del_operador": _lista(d.get("necesita_del_operador")),
        "senal_real": {"que_personas": _txt(real.get("que_personas"), 300),
                       "como_se_obtiene": _txt(real.get("como_se_obtiene"), 400)},
        "primer_paso_gratuito": _txt(d.get("primer_paso_gratuito"), 400),
        "riesgo_legal": {"nivel": _txt(riesgo.get("nivel"), 10).lower(), "por_que": _txt(riesgo.get("por_que"), 300)},
    }


def validar_dosier(d: dict) -> list[str]:
    """Errores del dosier LIMPIO (lista vacia = valido). Todo comprobable por codigo."""
    e = []
    n = d["nicho"]
    for campo, minimo in (("problema", 10), ("publico", 5), ("por_que_ahora", 5)):
        if len(n[campo]) < minimo:
            e.append(f"nicho.{campo}: minimo {minimo} caracteres")
    ev = d["evidencia"]
    if len(ev) < 2:
        e.append("evidencia: minimo 2 afirmaciones")
    for i, it in enumerate(ev):
        if len(it["afirmacion"]) < 5:
            e.append(f"evidencia[{i}].afirmacion: minimo 5 caracteres")
        if it["etiqueta"] not in ETIQUETAS:
            e.append(f"evidencia[{i}].etiqueta: debe ser una de {list(ETIQUETAS)}")
        elif it["etiqueta"] == "VERIFICADA":
            f = it.get("fuente") or {}
            if not (f.get("url") and f.get("fecha") and len(f.get("extracto", "")) >= 10):
                e.append(f"evidencia[{i}]: VERIFICADA exige fuente con url http(s), fecha y extracto")
    c = d["coste"]
    if c["importe_eur"] is None or not (0 <= c["importe_eur"] <= 100000):
        e.append("coste.importe_eur: numero entre 0 y 100000")
    if len(c["alternativa_gratuita"]) < 5:
        e.append("coste.alternativa_gratuita: obligatoria (que se puede hacer sin gastar)")
    s = d["senal"]
    if len(s["que_se_mide"]) < 5:
        e.append("senal.que_se_mide: minimo 5 caracteres")
    if s["umbral"] is None:
        e.append("senal.umbral: numero")
    if s["comparador"] not in COMPARADORES:
        e.append(f"senal.comparador: uno de {list(COMPARADORES)}")
    if s["plazo_dias"] is None or not (1 <= s["plazo_dias"] <= PLAZO_MAX_DIAS):
        e.append(f"senal.plazo_dias: entero entre 1 y {PLAZO_MAX_DIAS}")
    if len(s["fuente_dato"]) < 5:
        e.append("senal.fuente_dato: obligatoria (sin fuente de datos no hay KPI)")
    if not d["capacidades"]["necesarias"]:
        e.append("capacidades.necesarias: al menos una")
    if not d["necesita_del_operador"]:
        e.append("necesita_del_operador: al menos un paso")
    r = d["senal_real"]
    if len(r["que_personas"]) < 5 or len(r["como_se_obtiene"]) < 5:
        e.append("senal_real: debe decir que personas y como se obtiene la senal (sin ella no es valido)")
    if len(d["primer_paso_gratuito"]) < 5:
        e.append("primer_paso_gratuito: obligatorio (la verificacion gratuita que ejecuta el operador)")
    if d["riesgo_legal"]["nivel"] not in RIESGOS or len(d["riesgo_legal"]["por_que"]) < 3:
        e.append(f"riesgo_legal: nivel {list(RIESGOS)} y por_que")
    return e


def huella(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ── novedad y cuotas ────────────────────────────────────────────────────────

def _misma_zona(c1: dict, c2: dict) -> bool:
    if (c1["modelo_ingreso"], c1["cliente"], c1["canal"]) != (c2["modelo_ingreso"], c2["cliente"], c2["canal"]):
        return False
    a, b = palabras(c1["sector"], 2), palabras(c2["sector"], 2)         # "IA", "TI"... tambien son sectores
    return bool(a and b) and len(a & b) / len(a | b) >= UMBRAL_SECTOR


def _texto_comparable(b: dict) -> str:
    return f"{b['titulo']} {b['problema']} {b['publico']}"


def comprobar_novedad(borrador: dict, coordenadas: dict, existentes: list[dict], *,
                      variacion_de: str | None = None) -> tuple[bool, str, str]:
    """(ok, razon, similar_a). Se compara con TODAS las apuestas (tambien PODADA y DESCARTADA: ya
    probadas o rechazadas). Una variacion de una apuesta CRECE no se compara con su padre por texto,
    pero debe cambiar al menos una coordenada."""
    for ex in existentes:
        eb, ec = ex.get("borrador"), ex.get("coordenadas")
        if not eb or not ec:
            continue
        if variacion_de and ex["id"] == variacion_de:
            if all(coordenadas[k] == ec[k] for k in ("modelo_ingreso", "cliente", "canal", "mercado")) \
                    and palabras(coordenadas["sector"], 2) == palabras(ec["sector"], 2):
                return False, "variacion_sin_cambio: no cambia ninguna coordenada de su apuesta madre", ex["id"]
            continue
        s = similitud(_texto_comparable(borrador), _texto_comparable(eb))
        if s >= UMBRAL_SIMILITUD:
            return False, f"demasiado_parecida (similitud {s:.2f})", ex["id"]
        if _misma_zona(coordenadas, ec):
            return False, "mismas_coordenadas (modelo, cliente, canal y sector)", ex["id"]
    return True, "", ""


def cuotas_incumplidas(elegidos: list[dict], *, exige_variacion: bool = False) -> list[str]:
    """Codigos de las cuotas del ciclo que NO se cumplen (docs §6.3). Cada elegido lleva
    `coordenadas`, `fuera_de_capacidades` y opcionalmente `variacion_de`."""
    fallos = []
    if len({x["coordenadas"]["modelo_ingreso"] for x in elegidos}) < CUOTAS["min_modelos"]:
        fallos.append("min_modelos")
    for eje, tope, codigo in (("cliente", CUOTAS["max_mismo_cliente"], "max_mismo_cliente"),
                              ("canal", CUOTAS["max_mismo_canal"], "max_mismo_canal")):
        cuenta: dict[str, int] = {}
        for x in elegidos:
            cuenta[x["coordenadas"][eje]] = cuenta.get(x["coordenadas"][eje], 0) + 1
        if cuenta and max(cuenta.values()) > tope:
            fallos.append(codigo)
    if sum(1 for x in elegidos if x["coordenadas"]["coste_inicial"] == "0"
           and x["coordenadas"]["tiempo_senal"] == "<=7d") < CUOTAS["min_coste0_senal7"]:
        fallos.append("min_coste0_senal7")
    if sum(1 for x in elegidos if x.get("fuera_de_capacidades")) < CUOTAS["min_fuera_capacidades"]:
        fallos.append("min_fuera_capacidades")
    if exige_variacion and not any(x.get("variacion_de") for x in elegidos):
        fallos.append("variacion")
    return fallos


def seleccionar(candidatos: list[dict], n: int = 5, *, exige_variacion: bool = False) -> tuple[list[dict], list[str]]:
    """Elige hasta `n` candidatos maximizando la cobertura bajo los topes por cliente y canal.
    Determinista (empates: orden de entrada). Devuelve (elegidos, cuotas_incumplidas)."""
    elegidos: list[dict] = []
    restantes = list(candidatos)
    while restantes and len(elegidos) < n:
        modelos = {x["coordenadas"]["modelo_ingreso"] for x in elegidos}
        mejor, mejor_pts = None, None
        for c in restantes:
            co = c["coordenadas"]
            if sum(1 for x in elegidos if x["coordenadas"]["cliente"] == co["cliente"]) >= CUOTAS["max_mismo_cliente"]:
                continue
            if sum(1 for x in elegidos if x["coordenadas"]["canal"] == co["canal"]) >= CUOTAS["max_mismo_canal"]:
                continue
            pts = 0
            pts += 3 if co["modelo_ingreso"] not in modelos else 0
            pts += 2 if (co["coste_inicial"] == "0" and co["tiempo_senal"] == "<=7d"
                         and not any(x["coordenadas"]["coste_inicial"] == "0"
                                     and x["coordenadas"]["tiempo_senal"] == "<=7d" for x in elegidos)) else 0
            pts += 2 if c.get("fuera_de_capacidades") and not any(x.get("fuera_de_capacidades") for x in elegidos) else 0
            pts += 3 if exige_variacion and c.get("variacion_de") and not any(x.get("variacion_de") for x in elegidos) else 0
            if mejor is None or pts > mejor_pts:
                mejor, mejor_pts = c, pts
        if mejor is None:
            break
        elegidos.append(mejor)
        restantes.remove(mejor)
    return elegidos, cuotas_incumplidas(elegidos, exige_variacion=exige_variacion)


# ── aprendizaje, criterio, medicion ─────────────────────────────────────────

def limpiar_aprendizaje(a) -> dict:
    a = a if isinstance(a, dict) else {}
    return {"esperaba": _txt(a.get("esperaba"), 600), "paso": _txt(a.get("paso"), 600),
            "haria_distinto": _txt(a.get("haria_distinto"), 600)}


def validar_aprendizaje(a: dict) -> list[str]:
    return [f"aprendizaje.{k}: obligatorio (minimo 3 caracteres)" for k, v in a.items() if len(v) < 3]


def limpiar_criterio(c, dosier: dict | None) -> dict:
    """Criterio de muerte. Lo que el operador no dice se hereda de la senal del dosier."""
    c = c if isinstance(c, dict) else {}
    base = (dosier or {}).get("senal") or {}
    pl = c.get("plazo_dias", base.get("plazo_dias"))
    return {"senal": _txt(c.get("senal"), 300) or base.get("que_se_mide", ""),
            "umbral": _num(c.get("umbral")) if c.get("umbral") is not None else base.get("umbral"),
            "comparador": _txt(c.get("comparador"), 2) or base.get("comparador", ""),
            "plazo_dias": pl if isinstance(pl, int) and not isinstance(pl, bool) else None,
            "fuente_dato": _txt(c.get("fuente_dato"), 300) or base.get("fuente_dato", ""),
            "coste_max_eur": _num(c.get("coste_max_eur")) if c.get("coste_max_eur") is not None else 0.0}


def validar_criterio(c: dict) -> list[str]:
    e = []
    if len(c["senal"]) < 5:
        e.append("criterio.senal: minimo 5 caracteres")
    if c["umbral"] is None:
        e.append("criterio.umbral: numero")
    if c["comparador"] not in COMPARADORES:
        e.append(f"criterio.comparador: uno de {list(COMPARADORES)}")
    if c["plazo_dias"] is None or not (1 <= c["plazo_dias"] <= PLAZO_MAX_DIAS):
        e.append(f"criterio.plazo_dias: entero entre 1 y {PLAZO_MAX_DIAS}")
    if len(c["fuente_dato"]) < 5:
        e.append("criterio.fuente_dato: obligatoria (sin fuente de datos no hay KPI)")
    if c["coste_max_eur"] is None or c["coste_max_eur"] != 0:
        e.append("criterio.coste_max_eur: debe ser 0 (N1: el gasto llega con el flujo de financiacion)")
    return e


# ── el almacen ──────────────────────────────────────────────────────────────

def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Apuestas:
    def __init__(self, knowledge, tenant: str, *, bitacora=None, reloj=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.bitacora = bitacora
        self._reloj = reloj or _ahora_utc

    # lectura ---------------------------------------------------------------
    def obtener(self, ap_id: str) -> dict | None:
        r = self.k.get(self.tenant, COLECCION, ap_id)
        return copy.deepcopy(r) if r else None

    def listar(self, estado: str | None = None) -> list[dict]:
        xs = [copy.deepcopy(x) for x in self.k.all(self.tenant, COLECCION).values()]
        xs = [x for x in xs if estado is None or x["estado"] == estado]
        return sorted(xs, key=lambda x: (x["creada_en"], x["id"]))

    def conteo_por_estado(self) -> dict[str, int]:
        c = {e: 0 for e in ESTADOS}
        for x in self.k.all(self.tenant, COLECCION).values():
            if x.get("estado") in c:
                c[x["estado"]] += 1
        return c

    def pide_medicion(self) -> list[str]:
        """Ids de apuestas EN_PRUEBA cuyo plazo ya vencio (solo AVISO: no cambia el estado)."""
        hoy = self._reloj().date().isoformat()
        return [x["id"] for x in self.listar("EN_PRUEBA")
                if x.get("criterio") and x["criterio"].get("fecha_limite", "9999") < hoy]

    # infraestructura -------------------------------------------------------
    def _tx(self):
        tx = getattr(self.k, "transaccion", None)
        return tx() if tx else contextlib.nullcontext()

    def _sellar(self, tipo: str, payload: dict) -> None:
        if self.bitacora is not None:
            self.bitacora.publicar(Sobre(tenant_id=self.tenant, tipo=tipo, payload=payload,
                                         origen="inteligencia.apuestas"))

    def _ts(self) -> str:
        return self._reloj().isoformat()

    def _guardar(self, r: dict) -> None:
        r["actualizada_en"] = self._ts()
        self.k.add(self.tenant, COLECCION, r["id"], r)

    def _transitar(self, ap_id: str, a: str, *, actor: str, por: str, mutar, razon: str = "") -> tuple[dict, dict]:
        """Decide y guarda BAJO el candado; devuelve (apuesta, payload_del_evento) para sellar FUERA."""
        with self._tx():
            r = self.k.get(self.tenant, COLECCION, ap_id)
            if r is None:
                raise ApuestaInvalida(f"apuesta inexistente: {ap_id}")
            r = copy.deepcopy(r)
            de = r["estado"]
            if a not in TRANSICIONES.get(de, set()):
                raise TransicionInvalida(f"{de} -> {a} no esta permitido"
                                         + (" (estado terminal)" if de in TERMINALES else ""))
            if actor == "operador" and not _txt(por, 80):
                raise ApuestaInvalida("falta quien decide (por)")
            extra = mutar(r) or {}
            r["estado"] = a
            r["historial"].append({"ts": self._ts(), "de": de, "a": a, "actor": actor,
                                   **({"por": _txt(por, 80)} if por else {}),
                                   **({"razon": _txt(razon, 400)} if razon else {})})
            self._guardar(r)
        payload = {"apuesta_ref": ap_id, "de": de, "a": a, "actor": actor, "ronda": r["ronda"], **extra}
        return copy.deepcopy(r), payload

    # transiciones de Inteligencia -----------------------------------------
    def crear_borrador(self, borrador, coordenadas, *, ciclo: dict | None = None,
                       variacion_de: str | None = None) -> dict:
        b, c = limpiar_borrador(borrador), limpiar_coordenadas(coordenadas)
        errores = validar_borrador(b) + validar_coordenadas(c) + comprobar_vetos([b, c["sector"]])
        if errores:
            raise ApuestaInvalida("; ".join(errores))
        with self._tx():
            existentes = self.listar()
            if variacion_de and not any(x["id"] == variacion_de and x["estado"] == "CRECE" for x in existentes):
                raise ApuestaInvalida("variacion_de: debe ser una apuesta en estado CRECE")
            ok, razon, similar = comprobar_novedad(b, c, existentes, variacion_de=variacion_de)
            if not ok:
                raise Repetida(razon, similar)
            ahora = self._ts()
            r = {"id": nuevo_id(), "tenant": self.tenant, "estado": "BORRADOR", "ronda": 1,
                 "creada_en": ahora, "actualizada_en": ahora, "borrador": b, "coordenadas": c,
                 "variacion_de": variacion_de, "ciclo": ciclo or {}, "dosier": None, "dosier_sha256": None,
                 "criterio": None, "medicion": None, "propuesta_regla": None, "aprendizaje": None,
                 "rondas_previas": [], "historial": [{"ts": ahora, "de": None, "a": "BORRADOR",
                                                      "actor": "inteligencia"}]}
            self.k.add(self.tenant, COLECCION, r["id"], r)
        self._sellar("inteligencia.apuesta.creada",
                     {"apuesta_ref": r["id"], "de": None, "a": "BORRADOR", "actor": "inteligencia", "ronda": 1,
                      "modelo_ingreso": c["modelo_ingreso"], "cliente": c["cliente"], "canal": c["canal"]})
        return copy.deepcopy(r)

    def completar_dosier(self, ap_id: str, dosier) -> dict:
        d = limpiar_dosier(dosier)
        errores = validar_dosier(d) + comprobar_vetos(sin_fuentes(d))
        if errores:
            raise ApuestaInvalida("; ".join(errores))
        h = huella(d)

        def mutar(r):
            r["dosier"], r["dosier_sha256"] = d, h
            return {"dosier_sha256": h}
        r, payload = self._transitar(ap_id, "DOSIER", actor="inteligencia", por="", mutar=mutar)
        self._sellar("inteligencia.apuesta.dosier_completado", payload)
        return r

    # decisiones del OPERADOR ----------------------------------------------
    def elegir(self, ap_id: str, *, por: str) -> dict:
        r, p = self._transitar(ap_id, "ELEGIDA", actor="operador", por=por, mutar=lambda r: None)
        self._sellar("inteligencia.apuesta.elegida", p)
        return r

    def iniciar_prueba(self, ap_id: str, *, por: str, criterio=None) -> dict:
        """ELEGIDA -> EN_PRUEBA (o CRECE -> EN_PRUEBA: nueva ronda). Fija el criterio de muerte."""
        def mutar(r):
            if criterio is not None and not isinstance(criterio, dict):
                raise ApuestaInvalida("criterio: debe ser un objeto (o vacio para heredar el del dosier)")
            c = limpiar_criterio(criterio, r.get("dosier"))
            errores = validar_criterio(c)
            if errores:
                raise ApuestaInvalida("; ".join(errores))
            c["fecha_inicio"] = self._reloj().date().isoformat()
            c["fecha_limite"] = (self._reloj().date() + timedelta(days=c["plazo_dias"])).isoformat()
            if r["estado"] == "CRECE":                      # nueva ronda: la anterior queda archivada
                r["rondas_previas"].append({"ronda": r["ronda"], "criterio": r["criterio"],
                                            "medicion": r["medicion"], "propuesta_regla": r["propuesta_regla"],
                                            "aprendizaje": r["aprendizaje"]})
                r["ronda"] += 1
                r["medicion"], r["propuesta_regla"], r["aprendizaje"] = None, None, None
            r["criterio"] = c
        r, p = self._transitar(ap_id, "EN_PRUEBA", actor="operador", por=por, mutar=mutar)
        self._sellar("inteligencia.apuesta.en_prueba", p)
        return r

    def registrar_medicion(self, ap_id: str, *, por: str, valor, referencia: str) -> dict:
        """EN_PRUEBA -> MEDIDA. Guarda el numero real y calcula la PROPUESTA de la regla (solo propone)."""
        def mutar(r):
            v, ref = _num(valor), _txt(referencia, 300)
            if v is None:
                raise ApuestaInvalida("medicion: el valor debe ser un numero")
            if len(ref) < 3:
                raise ApuestaInvalida("medicion: falta la referencia (de donde sale el numero)")
            c = r["criterio"]
            cumple = v >= c["umbral"] if c["comparador"] == ">=" else v <= c["umbral"]
            hoy = self._reloj().date().isoformat()
            r["medicion"] = {"valor": v, "referencia": ref, "fecha": hoy, "a_tiempo": hoy <= c["fecha_limite"]}
            r["propuesta_regla"] = {"decision": "CRECE" if cumple else "PODADA", "valor": v,
                                    "umbral": c["umbral"], "comparador": c["comparador"]}
            return {"propuesta": r["propuesta_regla"]["decision"]}
        r, p = self._transitar(ap_id, "MEDIDA", actor="operador", por=por, mutar=mutar)
        self._sellar("inteligencia.apuesta.medida", p)
        return r

    def cerrar(self, ap_id: str, decision: str, *, por: str, aprendizaje) -> dict:
        """MEDIDA -> CRECE | PODADA. La decision es del operador; si va contra la regla queda anotado."""
        if decision not in ("CRECE", "PODADA"):
            raise ApuestaInvalida("decision: CRECE o PODADA")
        ap = limpiar_aprendizaje(aprendizaje)
        errores = validar_aprendizaje(ap)
        if errores:
            raise ApuestaInvalida("; ".join(errores))

        def mutar(r):
            r["aprendizaje"] = ap
            return {"contra_la_regla": decision != r["propuesta_regla"]["decision"]}
        r, p = self._transitar(ap_id, decision, actor="operador", por=por, mutar=mutar)
        self._sellar("inteligencia.apuesta.crece" if decision == "CRECE" else "inteligencia.apuesta.podada", p)
        return r

    def descartar(self, ap_id: str, *, por: str, razon: str, aprendizaje) -> dict:
        razon = _txt(razon, 400)
        ap = limpiar_aprendizaje(aprendizaje)
        errores = ([] if len(razon) >= 5 else ["razon: obligatoria (minimo 5 caracteres)"]) + validar_aprendizaje(ap)
        if errores:
            raise ApuestaInvalida("; ".join(errores))

        def mutar(r):
            r["aprendizaje"] = ap
        r, p = self._transitar(ap_id, "DESCARTADA", actor="operador", por=por, mutar=mutar, razon=razon)
        self._sellar("inteligencia.apuesta.descartada", p)
        return r
