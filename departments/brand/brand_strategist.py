"""Brand Strategist — define posicionamiento, tono y valores (tesis §6.4, rol nuevo).

Mantiene la guía de marca viva y decide cuando hay duda interpretativa: ¿esto encaja con
la marca? Es el rol que el Brand Guardian consulta cuando una decisión no es mecánica.

v1.0: responde sobre la guía declarativa cargada (`empresas/<empresa>/brand/guia.json`) y,
opcionalmente, razona con LLM una duda interpretativa concreta. No reescribe la guía: eso
es una decisión del operador.
"""
from __future__ import annotations

from departments.brand import config as brand_cfg


class BrandStrategist:
    def __init__(self, empresa: str = "laboratorio", *, chat=None) -> None:
        self.empresa = empresa
        self.guia = brand_cfg.cargar_guia(empresa)
        self.contexto_marca = brand_cfg.contexto_marca(empresa)
        if chat is None:
            import claude_client
            chat = claude_client.chat
        self.chat = chat

    def posicionamiento(self) -> str:
        return self.guia.get("posicionamiento", "")

    def tono(self) -> dict:
        return dict(self.guia.get("tono", {}))

    def valores(self) -> list[str]:
        return list(self.guia.get("valores", []))

    def encaja(self, propuesta: str, *, usar_llm: bool = True) -> dict:
        """Resuelve una duda interpretativa: ¿`propuesta` encaja con la marca?

        Devuelve `{encaja: bool, motivo: str}`. Sin LLM, hace una comprobación heurística
        contra el `que_no_decir`; con LLM, razona contra la guía completa.
        """
        prop_lower = propuesta.lower()
        for veto in self.guia.get("que_no_decir", []):
            # heurística simple: palabras clave del veto presentes
            claves = [w for w in veto.lower().split() if len(w) > 5][:3]
            if claves and all(c in prop_lower for c in claves):
                return {"encaja": False, "motivo": f"Contradice la guía: «{veto}»"}

        if not usar_llm:
            return {"encaja": True, "motivo": "Sin conflicto heurístico con la guía."}

        system = (f"Eres el Brand Strategist de {self.empresa}. Decides si una propuesta "
                  f"encaja con la marca.\n\n=== GUÍA DE MARCA ===\n{self.contexto_marca}\n\n"
                  "Responde EXACTAMENTE dos líneas:\nENCAJA|NO_ENCAJA\n<motivo en una frase>")
        try:
            r = self.chat([{"role": "user", "content": f"Propuesta: {propuesta}"}],
                          system=system, model="claude-haiku-4-5-20251001",
                          max_tokens=80, company=self.empresa, temperature=0)
        except Exception as e:  # noqa: BLE001
            return {"encaja": True, "motivo": f"LLM no disponible ({e}); sin veto heurístico."}
        lineas = [l.strip() for l in (r or "").splitlines() if l.strip()]
        veredicto = (lineas[0] if lineas else "").upper()
        motivo = lineas[1] if len(lineas) > 1 else ""
        return {"encaja": veredicto.startswith("ENCAJA"), "motivo": motivo}
