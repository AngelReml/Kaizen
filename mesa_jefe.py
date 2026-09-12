"""MESA DEL JEFE — la pagina de Alejandro. Ultra simple: saludo, resumen,
tarjetas SI/NO. Nada mas. Se sirve desde el PC del operador (127.0.0.1:8700);
para el movil de Alejandro se expone por tunel seguro con PIN (MESA_PIN en
.env). Sin PIN configurado, solo aconsejable en local.

Arrancar: doble clic en "MESA DEL JEFE.cmd" -> http://127.0.0.1:8700
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from sustrato import bus, propuestas

RAIZ = Path(__file__).resolve().parent
app = FastAPI(title="Mesa del Jefe", docs_url=None, redoc_url=None)


def _pin_configurado() -> str | None:
    pin = os.environ.get("MESA_PIN")
    if pin:
        return pin
    env = RAIZ / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if linea.strip().startswith("MESA_PIN="):
                v = linea.split("=", 1)[1].strip()
                return v or None
    return None


def _exigir_pin(request: Request) -> None:
    pin = _pin_configurado()
    if pin is None:
        return  # solo local; el tunel NO debe abrirse sin PIN (aviso en manual)
    if request.query_params.get("pin") != pin and request.cookies.get("mesa_pin") != pin:
        raise HTTPException(401, "PIN incorrecto o ausente")


@app.get("/api/tarjetas")
def api_tarjetas(request: Request):
    _exigir_pin(request)
    conn = bus.conexion()
    bus.instalar(conn)
    propuestas.instalar(conn)
    return {"resumen": propuestas.resumen_ayer(conn),
            "tarjetas": propuestas.pendientes(conn)}


class Decision(BaseModel):
    id: int
    aprobar: bool


@app.post("/api/decidir")
def api_decidir(d: Decision, request: Request):
    _exigir_pin(request)
    conn = bus.conexion()
    bus.instalar(conn)
    propuestas.instalar(conn)
    try:
        estado = propuestas.decidir(conn, d.id, d.aprobar, quien="alejandro")
    except propuestas.PropuestaYaDecidida as exc:
        raise HTTPException(409, str(exc))
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"ok": True, "estado": estado}


_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mesa del Jefe</title>
<style>
body{background:#F5F1E8;color:#1A1A1A;font-family:Georgia,serif;max-width:560px;
     margin:0 auto;padding:1rem}
h1{font-size:1.5rem;border-bottom:3px solid #C09244;padding-bottom:.3rem}
.resumen{font-size:1.05rem;color:#444;margin:.6rem 0 1.2rem}
.tarjeta{background:#fff;border:1px solid #1A1A1A;border-radius:.6rem;
     padding:1rem;margin:0 0 1rem;box-shadow:2px 2px 0 #C09244}
.dep{font-size:.8rem;letter-spacing:.06em;color:#8a6d00;text-transform:uppercase}
.titulo{font-size:1.15rem;font-weight:bold;margin:.25rem 0}
.resumen-t{margin:.3rem 0 .6rem}
details{margin:.4rem 0}summary{cursor:pointer;color:#8a6d00}
pre{white-space:pre-wrap;font-family:inherit;background:#F5F1E8;padding:.6rem;
     border:1px dashed #999;font-size:.95rem}
.botones{display:flex;gap:.8rem;margin-top:.6rem}
button{flex:1;font:inherit;font-size:1.2rem;font-weight:bold;padding:.8rem;
     border:none;border-radius:.5rem;cursor:pointer}
.si{background:#1c6b2a;color:#fff}.no{background:#8a1c1c;color:#fff}
.vacio{font-style:italic;color:#555;text-align:center;margin-top:2rem}
.hecho{opacity:.45;pointer-events:none}
</style></head><body>
<h1>MESA DEL JEFE</h1>
<div class="resumen" id="resumen">Cargando...</div>
<div id="tarjetas"></div>
<script>
const pin = new URLSearchParams(location.search).get('pin') || '';
if(pin) document.cookie = 'mesa_pin='+pin+';path=/;max-age=2592000';
async function cargar(){
  const r = await fetch('/api/tarjetas'+(pin?('?pin='+pin):''));
  if(!r.ok){document.getElementById('resumen').textContent='PIN incorrecto.';return}
  const d = await r.json();
  const s = d.resumen;
  document.getElementById('resumen').textContent =
    (s.pendientes_hoy===null) ? 'Sin datos todavia.'
    : `Ayer: ${s.movimientos_ayer} movimientos y ${s.decisiones_ayer} decisiones tuyas. `+
      `Hoy te pido ${s.pendientes_hoy} ${s.pendientes_hoy===1?'decision':'decisiones'}.`;
  const cont = document.getElementById('tarjetas'); cont.innerHTML='';
  if(!d.tarjetas.length){cont.innerHTML='<p class="vacio">Nada pendiente. Buen dia, jefe.</p>';return}
  for(const t of d.tarjetas){
    const el = document.createElement('div'); el.className='tarjeta'; el.id='t'+t.id;
    el.innerHTML = `<div class="dep">${t.cubo} · ${t.tipo.replaceAll('_',' ')}</div>
      <div class="titulo">${t.titulo}</div>
      <div class="resumen-t">${t.resumen}</div>
      <details><summary>ver texto completo</summary><pre>${t.cuerpo
        .replaceAll('&','&amp;').replaceAll('<','&lt;')}</pre></details>
      <div class="botones">
        <button class="si" onclick="decidir(${t.id},true)">SI</button>
        <button class="no" onclick="decidir(${t.id},false)">NO</button>
      </div>`;
    cont.appendChild(el);
  }
}
async function decidir(id,aprobar){
  const el = document.getElementById('t'+id); el.classList.add('hecho');
  const r = await fetch('/api/decidir'+(pin?('?pin='+pin):''),{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({id,aprobar})});
  if(!r.ok){el.classList.remove('hecho');alert('No se pudo registrar. Reintenta.');return}
  setTimeout(cargar, 350);
}
cargar();
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def portada(request: Request):
    _exigir_pin(request)
    return _HTML


if __name__ == "__main__":
    import socket
    import webbrowser

    import uvicorn

    url = "http://127.0.0.1:8700"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        ya_corre = s.connect_ex(("127.0.0.1", 8700)) == 0
    if ya_corre:
        print("Mesa del Jefe ya corre en 8700; abro el navegador.")
        webbrowser.open(url)
    else:
        print("Mesa del Jefe -> %s  (Ctrl+C para salir)" % url)
        uvicorn.run(app, host="127.0.0.1", port=8700, log_level="warning")
