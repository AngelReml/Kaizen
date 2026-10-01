# -*- coding: utf-8 -*-
"""Cliente de modelo LOCAL (LM Studio u otro con API tipo OpenAI). Servidor HTTP local simulado."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core import exploracion_modelos as M

CLAVE = "clave-LOCAL-SECRETA-123"


class Local:
    def __init__(self, modelos=("modelo-a", "modelo-b"), guion=None):
        self.modelos, self.guion, self.posts, self.gets = list(modelos), list(guion or []), [], []
        outer = self

        class H(BaseHTTPRequestHandler):
            def _enviar(self, st, obj):
                d = json.dumps(obj).encode()
                self.send_response(st); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)

            def do_GET(self):
                outer.gets.append(self.path)
                self._enviar(200, {"data": [{"id": m} for m in outer.modelos]})

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                outer.posts.append({"path": self.path, "auth": self.headers.get("Authorization"),
                                    "json": json.loads(self.rfile.read(n) or b"{}")})
                st, txt = outer.guion.pop(0) if outer.guion else (200, "respuesta-local")
                self._enviar(st, {"choices": [{"message": {"content": txt}}]} if st == 200 else {"error": txt})

            def log_message(self, *a):
                pass
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        threading.Thread(target=lambda: self.httpd.serve_forever(poll_interval=0.01), daemon=True).start()

    def cerrar(self):
        self.httpd.shutdown(); self.httpd.server_close()


@pytest.fixture()
def srv():
    s = Local()
    yield s
    s.cerrar()


def test_pregunta_con_el_primer_modelo_cargado_y_formato_estandar(srv):
    c = M.ClienteLocal(url=srv.url)
    assert c.preguntar("eres un analista", "hola") == "respuesta-local"
    p = srv.posts[0]
    assert p["path"] == "/v1/chat/completions" and p["auth"] is None
    assert p["json"]["model"] == "modelo-a" and p["json"]["stream"] is False
    assert p["json"]["messages"] == [{"role": "system", "content": "eres un analista"}, {"role": "user", "content": "hola"}]
    c.preguntar("", "otra")                                              # el modelo se descubre UNA vez y sin system no se manda
    assert len(srv.gets) == 1 and srv.posts[1]["json"]["messages"] == [{"role": "user", "content": "otra"}]
    assert c.ultimo_modelo == "modelo-a" and c.preguntas == 2


def test_modelo_fijado_por_entorno_no_pregunta_la_lista(srv, monkeypatch):
    monkeypatch.setenv("KAIZEN_LOCAL_MODELO", "mi-modelo")
    c = M.ClienteLocal(url=srv.url)
    c.preguntar("s", "u")
    assert srv.gets == [] and srv.posts[0]["json"]["model"] == "mi-modelo"


def test_la_clave_va_solo_en_la_cabecera_y_nunca_se_imprime(srv):
    c = M.ClienteLocal(url=srv.url, clave=CLAVE)
    c.preguntar("s", "u")
    assert srv.posts[0]["auth"] == f"Bearer {CLAVE}"
    assert CLAVE not in repr(c) and CLAVE not in str(c) and CLAVE not in json.dumps(srv.posts[0]["json"])


def test_se_descarta_el_razonamiento_en_voz_alta(srv):
    srv.guion = [(200, "<think>pienso {\"x\": 1} mucho</think>\n{\"candidatos\": []}")]
    assert M.ClienteLocal(url=srv.url).preguntar("s", "u") == '{"candidatos": []}'


def test_respuesta_vacia_o_solo_razonamiento_es_invalida(srv):
    for txt in ("", "   ", "<think>solo pienso</think>"):
        srv.guion = [(200, txt)]
        with pytest.raises(M.RespuestaInvalida):
            M.ClienteLocal(url=srv.url).preguntar("s", "u")


@pytest.mark.parametrize("status,clase", [(401, M.ApagadaOSinToken), (403, M.ApagadaOSinToken), (429, M.CapAgotado), (500, M.ErrorModelo), (400, M.ErrorModelo)])
def test_errores_http_con_su_clase(srv, status, clase):
    srv.guion = [(status, "fallo")]
    with pytest.raises(clase) as e:
        M.ClienteLocal(url=srv.url, clave=CLAVE).preguntar("s", "u")
    assert CLAVE not in str(e.value)


def test_sin_servidor_el_mensaje_dice_que_encender_y_no_lleva_clave():
    c = M.ClienteLocal(url="http://127.0.0.1:9/v1", clave=CLAVE, modelo="m", timeout=2)
    with pytest.raises(M.ErrorModelo, match="LM Studio") as e:
        c.preguntar("s", "u")
    assert CLAVE not in str(e.value)
    with pytest.raises(M.ErrorModelo, match="LM Studio"):                 # y al descubrir el modelo tambien
        M.ClienteLocal(url="http://127.0.0.1:9/v1").preguntar("s", "u")


def test_servidor_sin_modelos_cargados_lo_dice():
    s = Local(modelos=())
    try:
        with pytest.raises(M.ErrorModelo, match="ningun modelo cargado"):
            M.ClienteLocal(url=s.url).preguntar("s", "u")
    finally:
        s.cerrar()


def test_pregunta_vacia_no_sale():
    with pytest.raises(M.ErrorModelo, match="vacia"):
        M.ClienteLocal(url="http://127.0.0.1:9/v1", modelo="m").preguntar("s", "  ")


@pytest.mark.parametrize("url", ["http://ejemplo.com:1234/v1", "http://192.168.1.5:1234/v1", "ftp://127.0.0.1/v1", "no-es-url"])
def test_solo_en_esta_maquina_salvo_permiso_explicito(url, monkeypatch):
    with pytest.raises(M.ErrorModelo):
        M.ClienteLocal(url=url)
    monkeypatch.setenv("KAIZEN_LOCAL_PERMITIR_REMOTO", "1")
    if url.startswith("http://"):
        M.ClienteLocal(url=url)


def test_clave_con_espacios_o_saltos_se_rechaza():
    with pytest.raises(M.ErrorModelo):
        M.ClienteLocal(url="http://127.0.0.1:1234/v1", clave="a b\nc")


def test_la_seleccion_por_entorno_y_los_valores_desconocidos(monkeypatch):
    monkeypatch.setenv("KAIZEN_EXPLORACION_MODELO", "local")
    assert isinstance(M.cliente_desde_entorno("e"), M.ClienteLocal)
    monkeypatch.setenv("KAIZEN_EXPLORACION_MODELO", "otro")
    with pytest.raises(M.ErrorModelo, match="local"):
        M.cliente_desde_entorno("e")


def test_el_cliente_no_usa_el_proxy_del_entorno(srv, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9"); monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    assert M.ClienteLocal(url=srv.url, clave=CLAVE).preguntar("s", "u") == "respuesta-local"
