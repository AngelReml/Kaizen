"""Cubo Brand segun KAIZEN-D02 (bloques D2.0/D2.1) + R-02/R-03 de D09.

Brand NO expone endpoint propio (R-03): es PROVEEDOR del paquete 'brand' del
servicio del sustrato `verificacion.validar_borrador`. Aqui viven: directrices
ejecutables por tenant (D02 §4.2), su maquina de estados y versionado (§4.1/§4.3),
el validador categorizado {APTO, NO_APTO_POR_MARCA, NO_APTO_POR_POLITICA, AMBIGUO}
con razones itemizadas, y el analizador de validaciones (D2.2, señal P8).
Determinista puro: sin LLM (la capa semantica opcional es inyectable).
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.rue import Sobre
from core import verificacion as V

ESTADOS_DIRECTRIZ = ("BORRADOR", "ACTIVA", "SUSPENDIDA", "DEPRECADA", "ARCHIVADA", "CANCELADA")
TRANSICIONES_DIRECTRIZ = {
    "BORRADOR": {"ACTIVA", "CANCELADA"},
    "ACTIVA": {"DEPRECADA", "SUSPENDIDA", "ARCHIVADA"},
    "SUSPENDIDA": {"ACTIVA", "DEPRECADA"},
    "DEPRECADA": {"ARCHIVADA"},
    "ARCHIVADA": set(),
    "CANCELADA": {"ARCHIVADA"},
}
CATEGORIAS = ("MARCA_CRITICA", "LEGAL", "DIFERENCIACION", "MARCA_IMPORTANTE")
ACCIONES = ("NO_APTO_POR_MARCA", "NO_APTO_POR_POLITICA", "APTO", "AMBIGUO")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class DirectrizInvalida(ValueError):
    pass


class CuboBrand:
    """Gestor de directrices + validador por tenant, sobre KnowledgeStore."""

    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora

    # ── directrices ──
    def alta_directriz(self, d: dict) -> dict:
        for campo in ("id", "regla", "categoria", "accion"):
            if not d.get(campo):
                raise DirectrizInvalida(f"directriz sin {campo}")
        if d["categoria"] not in CATEGORIAS or d["accion"] not in ACCIONES:
            raise DirectrizInvalida("categoria o accion fuera de catalogo")
        d = dict(d)
        d.setdefault("estado", "BORRADOR")
        d.setdefault("version", 1)
        d.setdefault("palabras_prohibidas", [])
        d.setdefault("requiere_alguna", [])       # si prohibidas presentes, exige contexto
        self.k.add(self.tenant, "directriz", d["id"], d)
        return d

    def transicionar_directriz(self, d_id: str, a: str, *, por: str, motivo: str = "") -> dict:
        d = self.k.get(self.tenant, "directriz", d_id)
        if d is None:
            raise DirectrizInvalida(f"directriz inexistente: {d_id}")
        if a not in TRANSICIONES_DIRECTRIZ[d["estado"]]:
            raise DirectrizInvalida(f"transicion {d['estado']}→{a} no permitida (ARCHIVADA es inmutable)")
        d = dict(d); d["estado"] = a
        self.k.add(self.tenant, "directriz", d_id, d)
        return d

    def actualizar_directriz(self, d_id: str, cambios: dict, *, por: str,
                             disruptivo: bool = False) -> dict:
        """Versionado §4.3: aditivo = +0.1 (minor, entero: version+1 par/impar simplificado
        a version+1 con flag); disruptivo exige deprecar la anterior (sin cambios silenciosos)."""
        d = self.k.get(self.tenant, "directriz", d_id)
        if d is None:
            raise DirectrizInvalida(f"directriz inexistente: {d_id}")
        anterior = d["version"]
        nueva = dict(d); nueva.update(cambios)
        nueva["version"] = anterior + 1
        if disruptivo:
            self.transicionar_directriz(d_id, "DEPRECADA", por=por)
            nueva["id"] = f"{d_id}_v{nueva['version']}"
            nueva["estado"] = "ACTIVA"
            self.k.add(self.tenant, "directriz", nueva["id"], nueva)
        else:
            self.k.add(self.tenant, "directriz", d_id, nueva)
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo="brand.directriz.actualizada",
                                  payload={"directriz_ref": d_id, "version_anterior": anterior,
                                           "version_nueva": nueva["version"], "por": por,
                                           "disruptivo": disruptivo},
                                  origen="brand.gestor"))
        return nueva

    def directrices_activas(self) -> list[dict]:
        return sorted((d for d in self.k.all(self.tenant, "directriz").values()
                       if d["estado"] == "ACTIVA"), key=lambda d: d["id"])

    def version_directrices(self) -> str:
        return "|".join(f"{d['id']}:{d['version']}" for d in self.directrices_activas()) or "sin-directrices"

    # ── validador categorizado (determinista) ──
    def validar(self, texto: str) -> dict:
        low = texto.lower()
        razones = []
        peor = "APTO"
        orden = {"APTO": 0, "AMBIGUO": 1, "NO_APTO_POR_MARCA": 2, "NO_APTO_POR_POLITICA": 3}
        for d in self.directrices_activas():
            golpeada = False
            for palabra in d.get("palabras_prohibidas", []):
                if palabra.lower() in low:
                    contexto_ok = any(r.lower() in low for r in d.get("requiere_alguna", []))
                    if not contexto_ok:
                        golpeada = True
                        razones.append({"regla_id": d["id"], "descripcion":
                                        f"'{palabra}' sin el contexto exigido ({d['regla']})"})
            for req in d.get("requeridas", []):
                if req.lower() not in low:
                    golpeada = True
                    razones.append({"regla_id": d["id"], "descripcion": f"falta requerido: '{req}'"})
            if golpeada and orden[d["accion"]] > orden[peor]:
                peor = d["accion"]
        return {"veredicto": peor, "razones": razones,
                "version_directrices": self.version_directrices()}

    # ── proveedor del paquete 'brand' para el sustrato (R-03) ──
    def proveedor_paquete(self):
        def _proveedor(tenant_id: str, tipo_contenido: str, contenido: str) -> dict:
            # R-03/fuga-de-tenant: el registro en el sustrato es GLOBAL (un unico
            # proveedor para "brand"), asi que hay que resolver con el tenant_id
            # RECIBIDO en cada llamada, no con self.tenant de la instancia que
            # se registro — si no, un tenant hereda las directrices de otro.
            r = CuboBrand(self.k, tenant_id).validar(contenido)
            return {"veredicto": "APTO" if r["veredicto"] == "APTO" else "NO_APTO",
                    "razones": [x["descripcion"] for x in r["razones"]],
                    "version": r["version_directrices"],
                    "categoria": r["veredicto"]}
        return _proveedor

    def registrar_en_sustrato(self) -> None:
        V.registrar_paquete("brand", self.proveedor_paquete())

    # ── D2.2: analizador de validaciones (señal P8) ──
    def analizar_periodo(self, veredictos: list[dict], *, umbral_no_apto: float = 0.5) -> dict:
        total = len(veredictos)
        no_aptos = sum(1 for v in veredictos if v["veredicto"] != "APTO")
        tasa = round(no_aptos / total, 4) if total else 0.0
        return {"total": total, "no_aptos": no_aptos, "tasa_no_apto": tasa,
                "alerta": tasa >= umbral_no_apto}
