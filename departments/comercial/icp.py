"""Filtro de Cliente Ideal — data-driven, por empresa.

Implementa §5.2 / §5.3 del v0.2: distingue una marca excluida de un hotel boutique
(incluido) sin que el LLM lo invente. Los datos viven en la ficha del tenant,
`empresas/<empresa>/icp.json`, para que se editen sin tocar código.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent
DATOS = ROOT / "datos"


def _norm(texto: str) -> str:
    """Normaliza para comparación: minúsculas + sin acentos + colapsa espacios."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


@dataclass
class DecisionICP:
    aceptado: bool
    razones: list[str] = field(default_factory=list)
    categoria: str | None = None
    prioridad: str | None = None    # ALTA / MEDIA / BAJA
    # I-3 (D11 E1): la señal y el peso del match viajan con la decisión para
    # persistirse con el lead — una decisión sin sus insumos no es re-derivable.
    senal: str | None = None        # 'place_type' (fuerte) | 'keyword' (débil) | None
    peso: int = 0                   # 2=place_type, 1=keyword, 0=rechazo


class FiltroICP:
    """Carga el ICP de una empresa desde JSON y evalúa leads contra él."""

    def __init__(self, empresa: str = "laboratorio", ruta_datos: Path | None = None) -> None:
        # R-TENANT: el ICP es DATO del tenant y vive con el resto de su ficha,
        # no dentro del arbol del producto (antes: departments/comercial/datos/
        # icp_<empresa>.json, un fichero por cliente incrustado en el codigo).
        from core.rutas import dir_empresa
        ruta = ruta_datos or (dir_empresa(empresa) / "icp.json")
        if not ruta.exists():
            raise FileNotFoundError(f"No encuentro datos del ICP para '{empresa}' en {ruta}")
        self.data: dict = json.loads(ruta.read_text(encoding="utf-8"))
        self.empresa = empresa
        # Pre-cómputo: pares (original, normalizado) para mantener el nombre legible en
        # los mensajes de razón ("Marca excluida: 'Ballester'" en vez de "'ballester'").
        self._marcas_excluidas: list[tuple[str, str]] = [
            (m, _norm(m)) for m in self.data.get("marcas_excluidas", [])
        ]
        self._tipos_excluidos = self.data.get("tipos_excluidos", [])
        self._tipos_incluidos = self.data.get("tipos_incluidos", [])
        self._patrones_excluidos = [re.compile(p["patron"], re.IGNORECASE)
                                    for p in self.data.get("exclusiones_por_patron", [])]

    @property
    def origen(self) -> dict:
        return self.data.get("geografia", {}).get("origen", {})

    @property
    def max_anillo(self) -> int:
        return int(self.data.get("geografia", {}).get("max_anillo_activo", 1))

    def evaluar(self, lead: dict) -> DecisionICP:
        """Devuelve DecisionICP. El lead debe traer al menos `nombre`; idealmente también
        `place_types` (lista) y `descripcion` (texto libre con palabras del establecimiento)."""
        nombre = lead.get("nombre", "")
        nombre_n = _norm(nombre)
        descripcion = lead.get("descripcion", "") or ""
        texto_n = _norm(nombre + " " + descripcion)
        place_types = [pt.lower() for pt in (lead.get("place_types") or [])]

        # 1) Marca excluida explícita (Ballester, Berlys, Mercadona, NH Hoteles...).
        for marca_original, marca_n in self._marcas_excluidas:
            if marca_n and self._palabra_en(marca_n, nombre_n):
                return DecisionICP(False, [f"Marca excluida: '{marca_original}'"], None, None)

        # 2) Tipos excluidos (panadería propia, cadena nacional...).
        for tipo in self._tipos_excluidos:
            if any(pt in place_types for pt in tipo.get("place_types", [])):
                return DecisionICP(False, [f"Tipo excluido: {tipo['categoria']} ({tipo['razon']})"],
                                   None, None)
            for kw in tipo.get("keywords", []):
                if _norm(kw) in texto_n:
                    return DecisionICP(False, [f"Keyword excluida '{kw}' ({tipo['categoria']})"],
                                       None, None)

        # 3) Patrones excluidos (regex).
        for patron in self._patrones_excluidos:
            if patron.search(nombre) or patron.search(descripcion):
                return DecisionICP(False, [f"Patrón excluido: {patron.pattern}"], None, None)

        # 4) Tipos incluidos. Coincidencia por place_type o por keyword.
        # Desempate: (prioridad ALTA > MEDIA > BAJA), y a igual prioridad, place_type gana
        # sobre keyword (place_type es señal más fuerte que palabra suelta en descripción).
        prioridad_orden = {"ALTA": 3, "MEDIA": 2, "BAJA": 1}
        mejor: tuple[int, int, dict, str] | None = None     # (peso_prio, peso_match, tipo, razon)
        for tipo in self._tipos_incluidos:
            razon = None
            peso_match = 0
            interseccion = set(place_types) & set(tipo.get("place_types", []))
            if interseccion:
                razon = f"place_type match {interseccion}"
                peso_match = 2
            else:
                for kw in tipo.get("keywords", []):
                    if _norm(kw) in texto_n:
                        razon = f"keyword '{kw}'"
                        peso_match = 1
                        break
            if razon:
                peso_prio = prioridad_orden.get(tipo["prioridad"], 0)
                cand = (peso_prio, peso_match, tipo, razon)
                if mejor is None or (cand[0], cand[1]) > (mejor[0], mejor[1]):
                    mejor = cand

        if mejor:
            _, peso_match_ganador, tipo, razon = mejor
            return DecisionICP(
                aceptado=True,
                razones=[f"Encaja en {tipo['categoria']} ({tipo['prioridad']}): {razon}"],
                categoria=tipo["categoria"],
                prioridad=tipo["prioridad"],
                senal="place_type" if peso_match_ganador == 2 else "keyword",
                peso=peso_match_ganador,
            )

        # 5) Default: sin encaje → fuera.
        return DecisionICP(False, ["No encaja en ninguna categoría incluida"], None, None)

    @staticmethod
    def _palabra_en(token_norm: str, texto_norm: str) -> bool:
        """Match por límite de palabra: 'ballester' matchea en 'panadería ballester sl' pero no
        en 'caballestería'. Evita falsos positivos por substring."""
        if not token_norm:
            return False
        return bool(re.search(rf"(?:^|\W){re.escape(token_norm)}(?:\W|$)", texto_norm))
