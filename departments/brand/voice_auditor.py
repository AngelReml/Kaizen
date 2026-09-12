"""Voice Auditor — evalúa los turnos del agente en una llamada cerrada (tesis §6.4).

Heredado del Comercial (`analizar_tono_conversacional`). Aquí vive auto-contenido en el
cubo Brand: NO importa código del Comercial (regla de §7.1 — un cubo no importa de otro;
lo compartido vive en core/). Define su propia forma de dictamen.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from departments.brand import config as brand_cfg


@dataclass
class DictamenTono:
    ok: bool
    problemas: list[str] = field(default_factory=list)
    sugerencias: list[str] = field(default_factory=list)
    dictamen_llm: str = ""


_SYSTEM = """Eres el Voice Auditor del cubo Brand. Analizas una llamada telefónica ya
cerrada y evalúas SOLO los turnos del agente (no el cliente), contra la guía de marca.

Rechaza si: sonó a IA genérica o plantilla; usó jerga corporativa anglosajona; prometió
descuentos; presionó tras una negativa; monopolizó la conversación; no personalizó al
lead; no respetó un opt-out insinuado.
Acepta si: sonó humano y con historia; personalizó; preguntó y escuchó; cerró con respeto.

Devuelve EXACTAMENTE JSON sin markdown:
{"ok": true|false, "problemas": ["..."], "sugerencias": ["..."]}"""


class VoiceAuditor:
    def __init__(self, empresa: str = "laboratorio", *, chat=None) -> None:
        self.empresa = empresa
        self.contexto_marca = brand_cfg.contexto_marca(empresa)
        if chat is None:
            import claude_client
            chat = claude_client.chat
        self.chat = chat

    def auditar(self, texto_agente: str, *, lead: dict | None = None) -> DictamenTono:
        if not texto_agente.strip():
            return DictamenTono(ok=False, problemas=["transcript del agente vacío"])
        info = ""
        if lead:
            info = f"\nLead: {lead.get('nombre','?')}"
        user = (f"=== GUÍA DE MARCA ===\n{self.contexto_marca}\n\n"
                f"=== TURNOS DEL AGENTE ==={info}\n{texto_agente}\n")
        try:
            r = self.chat([{"role": "user", "content": user}], system=_SYSTEM,
                          model="claude-sonnet-4-6", max_tokens=400,
                          company=self.empresa, temperature=0)
        except Exception as e:  # noqa: BLE001
            return DictamenTono(ok=False, problemas=[f"LLM falló: {e}"])
        m = re.search(r"\{[\s\S]*\}", r or "")
        if not m:
            return DictamenTono(ok=False, problemas=[f"LLM no devolvió JSON: {(r or '')[:80]}"],
                                dictamen_llm=r or "")
        try:
            data = json.loads(m.group(0))
        except Exception as e:  # noqa: BLE001
            return DictamenTono(ok=False, problemas=[f"JSON inválido: {e}"], dictamen_llm=r)
        return DictamenTono(ok=bool(data.get("ok", False)),
                            problemas=list(data.get("problemas", [])),
                            sugerencias=list(data.get("sugerencias", [])),
                            dictamen_llm=r)
