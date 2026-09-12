"""Router multi-modelo con fallback automático (port de Swarm IDE smart_router.py).

Cadena de 24 modelos de 8 proveedores. Si un modelo falla por crédito/rate-limit/billing,
se avanza al siguiente. Un modelo solo entra si su API key existe en el entorno.

Adaptaciones para KAIZEN (ver promp.txt):
- `build()` importa langchain de forma perezosa: la lógica del router se testea sin langchain;
  las llamadas reales necesitan `pip install langchain-anthropic langchain-openai langchain-groq`.
- `get_cheap_model`/`get_heavy_model` devuelven el ModelEntry (build perezoso al invocar).
- `advance(entry)` recibe y devuelve un cursor LOCAL a la llamada (el `ModelEntry` actual):
  no hay puntero global de módulo, así que dos especialistas concurrentes con fallos
  distintos no se pisan.
- Sin _routing_mode, set_model, ni nada de LangGraph/SSE.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Endpoints OpenAI-compatibles por proveedor.
_BASE_URLS = {
    "glm": "https://open.bigmodel.cn/api/paas/v4/",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "deepseek": "https://api.deepseek.com/v1",
    "huggingface": "https://router.huggingface.co/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


@dataclass
class ModelEntry:
    provider: str
    model_id: str
    display_name: str
    key_env: str
    is_free: bool = False

    def available(self) -> bool:
        return bool(os.getenv(self.key_env))

    def info(self) -> dict:
        return {"provider": self.provider, "model": self.model_id,
                "display": self.display_name, "available": self.available()}

    def build(self):
        """Instancia el LangChain LLM del proveedor. Import perezoso (langchain opcional)."""
        key = os.getenv(self.key_env)
        if self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=self.model_id, api_key=key, max_tokens=8192, temperature=0.5)
        if self.provider == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(model=self.model_id, api_key=key, temperature=0.5)
        from langchain_openai import ChatOpenAI
        if self.provider == "openai":
            return ChatOpenAI(model=self.model_id, api_key=key, temperature=0.5)
        # Resto de proveedores: OpenAI-compatible con base_url propia.
        kw = {"model": self.model_id, "api_key": key,
              "base_url": _BASE_URLS[self.provider], "temperature": 0.5}
        if self.provider == "openrouter":
            kw["default_headers"] = {"HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://kaizen.local"), "X-Title": "KAIZEN"}
        return ChatOpenAI(**kw)


CHAIN: list[ModelEntry] = [
    # 1. Anthropic
    ModelEntry("anthropic", "claude-opus-4-5",   "Claude Opus 4.5",   "ANTHROPIC_API_KEY"),
    ModelEntry("anthropic", "claude-sonnet-4-5", "Claude Sonnet 4.5", "ANTHROPIC_API_KEY"),
    ModelEntry("anthropic", "claude-haiku-4-5",  "Claude Haiku 4.5",  "ANTHROPIC_API_KEY"),
    # 2. OpenAI
    ModelEntry("openai", "gpt-4o",      "GPT-4o",      "OPENAI_API_KEY"),
    ModelEntry("openai", "gpt-4o-mini", "GPT-4o Mini", "OPENAI_API_KEY"),
    # 3. Groq
    ModelEntry("groq", "llama-3.3-70b-versatile", "Llama 3.3 70B", "GROQ_API_KEY"),
    ModelEntry("groq", "llama-3.1-8b-instant",    "Llama 3.1 8B",  "GROQ_API_KEY"),
    # 4. GLM / ZhipuAI
    ModelEntry("glm", "glm-4-plus",  "GLM-4 Plus",  "GLM_API_KEY"),
    ModelEntry("glm", "glm-4-air",   "GLM-4 Air",   "GLM_API_KEY"),
    ModelEntry("glm", "glm-4-flash", "GLM-4 Flash", "GLM_API_KEY"),
    # 5. Gemini
    ModelEntry("gemini", "gemini-2.5-flash", "Gemini 2.5 Flash", "GEMINI_API_KEY"),
    ModelEntry("gemini", "gemini-2.5-pro",   "Gemini 2.5 Pro",   "GEMINI_API_KEY"),
    ModelEntry("gemini", "gemini-2.0-flash", "Gemini 2.0 Flash", "GEMINI_API_KEY"),
    # 6. DeepSeek
    ModelEntry("deepseek", "deepseek-chat",     "DeepSeek V3", "DEEPSEEK_API_KEY"),
    ModelEntry("deepseek", "deepseek-reasoner", "DeepSeek R1", "DEEPSEEK_API_KEY"),
    # 7. HuggingFace
    ModelEntry("huggingface", "Qwen/Qwen2.5-Coder-32B-Instruct", "Qwen2.5 Coder 32B", "HF_TOKEN"),
    ModelEntry("huggingface", "Qwen/Qwen2.5-72B-Instruct",       "Qwen2.5 72B",       "HF_TOKEN"),
    ModelEntry("huggingface", "meta-llama/Llama-3.3-70B-Instruct", "Llama 3.3 70B HF", "HF_TOKEN"),
    # 8. OpenRouter — pagados
    ModelEntry("openrouter", "anthropic/claude-sonnet-4-5", "Claude Sonnet [OR]",  "OPENROUTER_API_KEY"),
    ModelEntry("openrouter", "google/gemini-2.5-pro",       "Gemini 2.5 Pro [OR]", "OPENROUTER_API_KEY"),
    ModelEntry("openrouter", "qwen/qwen3-235b-a22b",        "Qwen3 235B [OR]",     "OPENROUTER_API_KEY"),
    # 8b. OpenRouter — gratis (último recurso)
    ModelEntry("openrouter", "meta-llama/llama-3.3-70b-instruct:free", "Llama 3.3 Free",   "OPENROUTER_API_KEY", is_free=True),
    ModelEntry("openrouter", "meta-llama/llama-3.2-3b-instruct:free",  "Llama 3.2 3B Free", "OPENROUTER_API_KEY", is_free=True),
    ModelEntry("openrouter", "google/gemma-3-4b-it:free",             "Gemma 3 4B Free",   "OPENROUTER_API_KEY", is_free=True),
]

_RETRIABLE = frozenset([
    "429", "rate_limit_error", "rate limit exceeded", "insufficient_quota", "quota exceeded",
    "402", "credit balance", "billing_hard_limit", "insufficient balance", "no available balance",
    "1113", "1211",
    "context_length_exceeded", "maximum context length",
    "model_not_found", "model not found",
    "no endpoints found", "provider returned error",
])


def is_retriable(e: Exception) -> bool:
    msg = str(e).lower()
    return any(s in msg for s in _RETRIABLE)


_CHEAP_ORDER = ["groq", "deepseek", "glm", "huggingface"]
_HEAVY_ORDER = ["anthropic", "openai", "gemini"]


def _first_available(providers: list[str], free_ok: bool = True) -> ModelEntry | None:
    for prov in providers:
        for e in CHAIN:
            if e.provider == prov and e.available() and (free_ok or not e.is_free):
                return e
    return None


def get_cheap_model() -> ModelEntry | None:
    """Modelo barato más rápido disponible. Groq > DeepSeek > GLM > HF > OR free > cualquiera."""
    e = _first_available(_CHEAP_ORDER)
    if e:
        return e
    free = next((x for x in CHAIN if x.provider == "openrouter" and x.is_free and x.available()), None)
    if free:
        return free
    # Penúltimo recurso: si solo hay ANTHROPIC_API_KEY, usar el Anthropic más barato
    # (Haiku) en vez de caer directo al primero de la cadena, que es Opus (el más caro).
    barato_anthropic = next(
        (x for x in CHAIN if x.provider == "anthropic" and "haiku" in x.model_id and x.available()),
        None,
    )
    if barato_anthropic:
        return barato_anthropic
    return next((x for x in CHAIN if x.available()), None)


def get_heavy_model() -> ModelEntry | None:
    """Mejor modelo disponible. Anthropic > OpenAI > Gemini > cualquiera."""
    e = _first_available(_HEAVY_ORDER)
    return e or next((x for x in CHAIN if x.available()), None)


def advance(entry: ModelEntry) -> ModelEntry | None:
    """Siguiente modelo disponible después de `entry` en la cadena.

    Cursor LOCAL a la llamada (recibe y devuelve `entry`/`ModelEntry`, no muta estado
    de módulo): dos llamadas concurrentes a especialistas ya no comparten ni pisan un
    puntero global compartido. La posición se localiza por identidad (`is`), no por
    igualdad de dataclass, para que `entry` se ubique exactamente aunque hubiera dos
    ModelEntry con los mismos campos.
    """
    try:
        i = next(idx for idx, x in enumerate(CHAIN) if x is entry)
    except StopIteration:
        i = -1
    for x in CHAIN[i + 1:]:
        if x.available():
            return x
    return None


def all_info() -> list[dict]:
    return [e.info() for e in CHAIN]
