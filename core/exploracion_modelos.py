"""Clientes de modelo para la exploracion de nichos (A3 del plan de apuestas).

Contrato unico que usa `core/exploracion.py`:

    cliente.preguntar(sistema: str, usuario: str, *, modelo: str | None = None,
                      max_tokens: int | None = None) -> str
    cliente.preguntas            # contador de preguntas hechas (exitosas o no)

- `ClienteWebllm`: puerta externa de WebLLM (`/external/v1/chat/completions`, OpenAI-compatible) que
  corre en el PC del operador. Modelos gratuitos por API (zai, groq, nemotron) con tope diario propio.
  Se rotan entre preguntas: cada modelo tiene sesgos distintos y eso tambien diversifica.
- `ClienteClaude`: adaptador de `claude_client.chat` (de pago, con su freno de coste).

Reglas de seguridad:
- el token SOLO viaja en la cabecera Authorization: jamas en la URL, en un mensaje de error, en un
  `repr` ni en un log;
- WebLLM es local por diseno: la URL debe apuntar a esta maquina (127.0.0.1, localhost, ::1); un token
  no se envia a otro host salvo orden explicita (KAIZEN_WEBLLM_PERMITIR_REMOTO=1);
- lo que devuelve un modelo es DATO no fiable: aqui solo se extrae el texto (acotado); validarlo es
  cosa del llamador.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from urllib.parse import urlsplit

URL_DEFECTO = "http://127.0.0.1:20130"
MODELOS_DEFECTO = ("zai", "groq", "nemotron")
MAX_RESPUESTA = 30000           # caracteres que se aceptan de una respuesta
_LOCALES = {"127.0.0.1", "localhost", "::1"}


class ErrorModelo(RuntimeError):
    """Fallo al preguntar a un modelo. El mensaje dice que hacer; nunca lleva el token."""


class CapAgotado(ErrorModelo):
    """El tope diario del proveedor (429) o el presupuesto de coste se agoto: parar la tanda."""


class ApagadaOSinToken(ErrorModelo):
    """401/403 o falta el token: no se puede seguir sin una accion del operador."""


class ModeloNoDisponible(ErrorModelo):
    """404: ese modelo no esta en la lista permitida; se retira de la rotacion."""


class RespuestaInvalida(ErrorModelo):
    pass


def _es_local(url: str) -> bool:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return False
    return host in _LOCALES


class _HttpDirecto:
    """HTTP SIN proxies del entorno (trust_env=False). WebLLM es local: con HTTP_PROXY definido (o el proxy
    del sistema en Windows) httpx mandaria la peticion —y la cabecera Authorization— al proxy."""

    def post(self, url, *, headers, json, timeout):
        import httpx
        with httpx.Client(trust_env=False, timeout=timeout) as c:
            return c.post(url, headers=headers, json=json)

    def get(self, url, *, headers, timeout):
        import httpx
        with httpx.Client(trust_env=False, timeout=timeout) as c:
            return c.get(url, headers=headers)


class ClienteWebllm:
    nombre = "webllm"

    def __init__(self, *, url: str | None = None, token: str | None = None,
                 modelos: tuple[str, ...] | list[str] | None = None, timeout: float = 180.0,
                 reintentos: int = 2, http=None, pausa=time.sleep) -> None:
        url = (url or os.environ.get("KAIZEN_WEBLLM_URL") or URL_DEFECTO).rstrip("/")
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ErrorModelo(f"KAIZEN_WEBLLM_URL no es una URL http(s) valida: {url!r}")
        if not _es_local(url) and os.environ.get("KAIZEN_WEBLLM_PERMITIR_REMOTO") != "1":
            raise ErrorModelo("WebLLM es local: KAIZEN_WEBLLM_URL debe apuntar a esta maquina "
                              "(127.0.0.1). El token no se envia a otro host.")
        token = token if token is not None else os.environ.get("KAIZEN_WEBLLM_TOKEN", "")
        if not token or not token.strip():
            raise ApagadaOSinToken(
                "Falta KAIZEN_WEBLLM_TOKEN. En el PC: 1) en la carpeta de webllm ejecuta "
                "`python -m scripts.external_api_admin enable` (imprime el token UNA vez), "
                "2) escribe el token en el fichero .env de Kaizen como KAIZEN_WEBLLM_TOKEN=... "
                "(no lo pegues en ningun chat).")
        token = token.strip()
        if any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in token):
            raise ErrorModelo("KAIZEN_WEBLLM_TOKEN tiene caracteres no validos (espacios o saltos de linea)")
        self._url = url
        self._token = token
        self._modelos = deque(modelos or MODELOS_DEFECTO)     # cola circular: retirar uno no salta a otro
        if not self._modelos:
            raise ErrorModelo("lista de modelos vacia")
        self._timeout = timeout
        self._reintentos = max(0, int(reintentos))
        self._pausa = pausa
        self._http = http
        self._lock = threading.Lock()
        self.preguntas = 0
        self.por_modelo: dict[str, int] = {}
        self.errores = 0
        self.ultimo_modelo: str | None = None          # el que contesto la ultima pregunta con exito

    def __repr__(self) -> str:                                  # el token nunca se imprime
        return f"ClienteWebllm(url={self._url!r}, modelos={self._modelos!r}, preguntas={self.preguntas})"

    __str__ = __repr__

    @property
    def modelos(self) -> list[str]:
        with self._lock:
            return list(self._modelos)

    def _siguiente(self) -> str:
        with self._lock:
            if not self._modelos:
                raise ErrorModelo("no queda ningun modelo disponible en la rotacion")
            m = self._modelos[0]
            self._modelos.rotate(-1)
            return m

    def _retirar(self, modelo: str) -> None:
        with self._lock:
            if modelo in self._modelos:
                self._modelos.remove(modelo)

    def _cliente_http(self):
        return self._http if self._http is not None else _HttpDirecto()

    def preguntar(self, sistema: str, usuario: str, *, modelo: str | None = None,
                  max_tokens: int | None = None) -> str:
        """Una pregunta. Sin `modelo`, rota. 429 -> CapAgotado; 401/403 -> ApagadaOSinToken;
        404 -> retira ese modelo y reintenta con otro; 5xx/red -> reintenta con espera."""
        if not (usuario or "").strip():
            raise ErrorModelo("pregunta vacia")
        intentos_modelo = 0
        while True:
            m = modelo or self._siguiente()
            try:
                return self._una_vez(m, sistema, usuario, max_tokens)
            except ModeloNoDisponible:
                self._retirar(m)
                intentos_modelo += 1
                if modelo is not None or not self.modelos or intentos_modelo > len(MODELOS_DEFECTO) + 3:
                    raise

    def _una_vez(self, modelo: str, sistema: str, usuario: str, max_tokens: int | None) -> str:
        cuerpo = {"model": modelo, "stream": False,
                  "messages": ([{"role": "system", "content": sistema}] if sistema else [])
                  + [{"role": "user", "content": usuario}]}
        if max_tokens:
            cuerpo["max_tokens"] = int(max_tokens)
        cab = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        ultimo = ""
        for intento in range(self._reintentos + 1):
            with self._lock:
                self.preguntas += 1
                self.por_modelo[modelo] = self.por_modelo.get(modelo, 0) + 1
            try:
                r = self._cliente_http().post(f"{self._url}/external/v1/chat/completions", headers=cab,
                                              json=cuerpo, timeout=self._timeout)
            except Exception as e:                              # noqa: BLE001 — red/timeout: se reintenta
                self.errores += 1
                ultimo = f"sin conexion con WebLLM ({type(e).__name__})"
                if intento < self._reintentos:
                    self._pausa(2 ** intento)
                continue
            st = r.status_code
            if st == 200:
                texto = self._texto(r)
                self.ultimo_modelo = modelo
                return texto
            self.errores += 1
            if st == 401:
                raise ApagadaOSinToken("WebLLM rechazo el token (401). Rotalo con "
                                       "`python -m scripts.external_api_admin rotate` y actualiza .env.")
            if st == 403:
                raise ApagadaOSinToken("La API externa de WebLLM esta apagada (403). Enciendela con "
                                       "`python -m scripts.external_api_admin enable`.")
            if st == 404:
                raise ModeloNoDisponible(f"el modelo {modelo!r} no esta permitido en WebLLM (404)")
            if st == 429:
                raise CapAgotado("WebLLM: tope diario de preguntas alcanzado (429). Se retoma manana "
                                 "o subiendo el tope en WebLLM.")
            if st == 400:
                raise ErrorModelo(f"WebLLM rechazo la peticion (400): {self._cola(r)}")
            ultimo = f"WebLLM respondio {st}"
            if st >= 500 and intento < self._reintentos:
                self._pausa(2 ** intento)
                continue
            break
        raise ErrorModelo(ultimo or "fallo desconocido al preguntar")

    @staticmethod
    def _cola(r) -> str:
        try:
            return (r.text or "")[:200].replace("\n", " ")
        except Exception:                                       # noqa: BLE001
            return ""

    @staticmethod
    def _texto(r) -> str:
        try:
            j = r.json()
            t = j["choices"][0]["message"]["content"]
        except Exception as e:                                  # noqa: BLE001
            raise RespuestaInvalida(f"respuesta de WebLLM ilegible ({type(e).__name__})") from None
        if not isinstance(t, str) or not t.strip():
            raise RespuestaInvalida("WebLLM devolvio una respuesta vacia")
        return t[:MAX_RESPUESTA]


URL_LOCAL_DEFECTO = "http://127.0.0.1:1234/v1"      # LM Studio


class ClienteLocal:
    """Un servidor LOCAL con la API estandar tipo OpenAI (LM Studio, enrutadores locales...): sin navegador,
    sin tope diario, sin token obligatorio. Solo en esta maquina (loopback) salvo permiso explicito.
    La calidad depende del modelo cargado: si no devuelve el JSON pedido, la tanda lo cuenta como rechazo."""
    nombre = "local"

    def __init__(self, *, url: str | None = None, modelo: str | None = None, clave: str | None = None,
                 timeout: float = 300.0, http=None) -> None:
        url = (url or os.environ.get("KAIZEN_LOCAL_URL") or URL_LOCAL_DEFECTO).rstrip("/")
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ErrorModelo(f"KAIZEN_LOCAL_URL no es una URL http(s) valida: {url!r}")
        if not _es_local(url) and os.environ.get("KAIZEN_LOCAL_PERMITIR_REMOTO") != "1":
            raise ErrorModelo("El modelo local debe estar en esta maquina (127.0.0.1): KAIZEN_LOCAL_URL apunta fuera.")
        clave = clave if clave is not None else os.environ.get("KAIZEN_LOCAL_CLAVE", "")
        clave = (clave or "").strip()
        if clave and any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in clave):
            raise ErrorModelo("KAIZEN_LOCAL_CLAVE tiene caracteres no validos")
        self._url, self._clave = url, clave
        self._modelo = (modelo or os.environ.get("KAIZEN_LOCAL_MODELO") or "").strip() or None
        self._timeout = timeout
        self._http = http
        self._lock = threading.Lock()
        self.preguntas = 0
        self.errores = 0
        self.por_modelo: dict[str, int] = {}
        self.ultimo_modelo: str | None = None

    def __repr__(self) -> str:                                  # la clave nunca se imprime
        return f"ClienteLocal(url={self._url!r}, modelo={self._modelo!r}, preguntas={self.preguntas})"

    __str__ = __repr__

    def _cab(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._clave:
            h["Authorization"] = f"Bearer {self._clave}"
        return h

    def _http_(self):
        return self._http if self._http is not None else _HttpDirecto()

    def _elegir_modelo(self) -> str:
        """Sin KAIZEN_LOCAL_MODELO: el primero que el servidor diga tener cargado."""
        if self._modelo:
            return self._modelo
        try:
            r = self._http_().get(f"{self._url}/models", headers=self._cab(), timeout=15.0)
            ids = [m["id"] for m in r.json()["data"] if isinstance(m, dict) and isinstance(m.get("id"), str)]
        except Exception as e:                                  # noqa: BLE001
            raise ErrorModelo(f"no pude hablar con el servidor local en {self._url} ({type(e).__name__}). "
                              "Comprueba que LM Studio (u otro) esta abierto con su servidor local encendido.") from None
        if not ids:
            raise ErrorModelo("el servidor local no tiene ningun modelo cargado: carga uno o fija KAIZEN_LOCAL_MODELO.")
        with self._lock:
            self._modelo = ids[0]
        return ids[0]

    def preguntar(self, sistema: str, usuario: str, *, modelo: str | None = None,
                  max_tokens: int | None = None) -> str:
        if not (usuario or "").strip():
            raise ErrorModelo("pregunta vacia")
        m = modelo or self._elegir_modelo()
        cuerpo = {"model": m, "stream": False,
                  "messages": ([{"role": "system", "content": sistema}] if sistema else [])
                  + [{"role": "user", "content": usuario}]}
        if max_tokens:
            cuerpo["max_tokens"] = int(max_tokens)
        with self._lock:
            self.preguntas += 1
            self.por_modelo[m] = self.por_modelo.get(m, 0) + 1
        try:
            r = self._http_().post(f"{self._url}/chat/completions", headers=self._cab(), json=cuerpo,
                                   timeout=self._timeout)
        except Exception as e:                                  # noqa: BLE001
            self.errores += 1
            raise ErrorModelo(f"sin conexion con el servidor local ({type(e).__name__}): "
                              "esta encendido el servidor de LM Studio?") from None
        st = r.status_code
        if st != 200:
            self.errores += 1
            if st in (401, 403):
                raise ApagadaOSinToken(f"el servidor local rechazo la clave ({st}): revisa KAIZEN_LOCAL_CLAVE.")
            if st == 429:
                raise CapAgotado("el servidor local dijo 429 (demasiadas peticiones).")
            cola = ""
            try:
                cola = (r.text or "")[:200].replace("\n", " ")
            except Exception:                                   # noqa: BLE001
                pass
            raise ErrorModelo(f"el servidor local respondio {st}: {cola}")
        try:
            t = r.json()["choices"][0]["message"]["content"]
        except Exception as e:                                  # noqa: BLE001
            raise RespuestaInvalida(f"respuesta del servidor local ilegible ({type(e).__name__})") from None
        if isinstance(t, str):                                  # modelos que razonan en voz alta: se descarta el razonamiento
            t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
        if not isinstance(t, str) or not t.strip():
            raise RespuestaInvalida("el servidor local devolvio una respuesta vacia")
        self.ultimo_modelo = m
        return t[:MAX_RESPUESTA]


class ClienteClaude:
    """Adaptador de `claude_client.chat` (de pago): mismo contrato, con su freno de coste."""
    nombre = "claude"

    def __init__(self, empresa: str, *, modelo: str = "claude-haiku-4-5-20251001", chat=None) -> None:
        self._empresa = empresa
        self._modelo = modelo
        self._chat = chat
        self.preguntas = 0
        self.errores = 0
        self.ultimo_modelo: str | None = None

    def preguntar(self, sistema: str, usuario: str, *, modelo: str | None = None,
                  max_tokens: int | None = None) -> str:
        if not (usuario or "").strip():
            raise ErrorModelo("pregunta vacia")
        chat = self._chat
        if chat is None:
            import claude_client
            chat = claude_client.chat
        self.preguntas += 1
        try:
            t = chat([{"role": "user", "content": usuario}], model=modelo or self._modelo,
                     system=sistema or None, max_tokens=max_tokens or 2048, company=self._empresa)
        except RuntimeError as e:
            self.errores += 1
            if "ANTHROPIC_API_KEY" in str(e):
                raise ApagadaOSinToken("Falta ANTHROPIC_API_KEY en .env (o usa WebLLM).") from None
            raise CapAgotado(f"limite de coste de Claude: {str(e)[:150]}") from None
        if not isinstance(t, str) or not t.strip():
            raise RespuestaInvalida("Claude devolvio una respuesta vacia")
        self.ultimo_modelo = modelo or self._modelo
        return t[:MAX_RESPUESTA]


def cliente_desde_entorno(empresa: str):
    """KAIZEN_EXPLORACION_MODELO = webllm (defecto, gratuito) | local (LM Studio u otro servidor local) | claude (de pago)."""
    modo = (os.environ.get("KAIZEN_EXPLORACION_MODELO") or "webllm").strip().lower()
    if modo == "claude":
        return ClienteClaude(empresa)
    if modo == "local":
        return ClienteLocal()
    if modo != "webllm":
        raise ErrorModelo(f"KAIZEN_EXPLORACION_MODELO desconocido: {modo!r} (webllm | local | claude)")
    return ClienteWebllm()
