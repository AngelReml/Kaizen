"""CENTRO DE MANDO KAIZEN — web LOCAL del operador (multi-empresa).

Un desplegable por empresa (cada empresa = una instancia/carpeta Kaizen
registrada en centro_instancias.json). Para la empresa elegida: los 10
departamentos con su salud, autonomia y si estan contratados; pipeline,
coste del dia y ultimas verificaciones. Acciones del operador: subir/bajar
autonomia, cambiar limite de gasto, contratar/descontratar departamentos,
lanzar forense y regenerar el panel HTML del cliente.

Principios:
- LECTURAS por SQL directo sobre la BD de cada instancia (solo lectura).
- ACCIONES via el CLI de la PROPIA instancia (subprocess): asi el candado
  del operador y las cadenas de hash de esa instancia siguen mandando.
- SOLO escucha en 127.0.0.1. No exponer a internet.
- Honestidad: sin BD o sin tabla -> SIN DATOS, jamas ceros fingidos.

Arrancar:  python centro_mando.py   ->  http://127.0.0.1:8600
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent
RUTA_REGISTRO = RAIZ / "centro_instancias.json"
NIVELES = ("CERO", "BAJA", "MEDIA", "ALTA")
ACCIONES_PERMITIDAS = ("set_autonomia", "set_limite", "contratar", "descontratar",
                       "forense", "director_html")

app = FastAPI(title="Centro de Mando Kaizen", docs_url=None, redoc_url=None)

# Inyectable en tests para no ejecutar procesos reales.
def _ejecutar_cli(instancia_ruta: Path, argumentos: list[str]) -> str:
    r = subprocess.run([sys.executable, "kaizen.py", *argumentos],
                       cwd=str(instancia_ruta), capture_output=True, text=True,
                       timeout=120)
    salida = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
    return salida.strip()[:4000]

EJECUTOR = _ejecutar_cli


def instancias() -> dict[str, Path]:
    datos = json.loads(RUTA_REGISTRO.read_text(encoding="utf-8"))
    out = {}
    for it in datos:
        ruta = (RAIZ / it["ruta"]).resolve() if not Path(it["ruta"]).is_absolute() \
            else Path(it["ruta"])
        out[it["nombre"]] = ruta
    return out


def _instancia_o_404(nombre: str) -> Path:
    reg = instancias()
    if nombre not in reg:            # unica via: el registro. Sin rutas del cliente.
        raise HTTPException(404, f"instancia desconocida: {nombre}")
    return reg[nombre]


def _consulta(db: Path, sql: str, args: tuple = ()) -> list | None:
    """None = SIN DATOS (no hay BD o no existe la tabla)."""
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _contratados(ruta: Path) -> dict:
    f = ruta / "contratados.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {}


@app.get("/api/instancias")
def api_instancias():
    return {"instancias": sorted(instancias().keys())}


@app.get("/api/estado")
def api_estado(instancia: str):
    ruta = _instancia_o_404(instancia)
    db = ruta / "data" / "kaizen.db"
    manifests = sorted(p.parent.name for p in (ruta / "cubos").glob("*/manifest.json"))
    contratados = _contratados(ruta)
    autonomias = _consulta(db, "SELECT cubo, nivel FROM config_autonomia")
    mapa_aut = dict(autonomias) if autonomias else {}
    cubos = []
    for nombre in manifests:
        try:
            m = json.loads((ruta / "cubos" / nombre / "manifest.json")
                           .read_text(encoding="utf-8"))
        except ValueError:
            m = {}
        cubos.append({
            "nombre": nombre,
            "contratado": bool(contratados.get(nombre, False)),
            "autonomia": mapa_aut.get(nombre, m.get("nivel_autonomia_defecto", "BAJA")),
            "irreversibles": m.get("acciones_irreversibles", []),
            "nota": m.get("nota_estado", ""),
            "descripcion": m.get("descripcion", ""),
        })
    pipeline = _consulta(db, "SELECT estado, COUNT(*) FROM leads GROUP BY estado")
    costes = _consulta(db, "SELECT COALESCE(SUM(coste_eur),0) FROM costes "
                           "WHERE substr(ts,1,10)=date('now')")
    limite = _consulta(db, "SELECT valor FROM config_valores "
                           "WHERE clave='LIMITE_COSTE_DIARIO_EUR'")
    verifs = _consulta(db, "SELECT ts, tipo, accion, veredicto, confianza "
                           "FROM verificaciones ORDER BY id DESC LIMIT 5")
    return {
        "instancia": instancia,
        "cubos": cubos,
        "pipeline": dict(pipeline) if pipeline else None,          # None = SIN DATOS
        "coste_hoy_eur": round(costes[0][0], 4) if costes else None,
        "limite_eur": float(limite[0][0]) if limite else None,
        "verificaciones": [list(v) for v in verifs] if verifs is not None else None,
    }


class Accion(BaseModel):
    instancia: str
    accion: str
    cubo: str | None = None
    nivel: str | None = None
    eur: float | None = None
    motivo: str | None = None


@app.post("/api/accion")
def api_accion(a: Accion):
    ruta = _instancia_o_404(a.instancia)
    if a.accion not in ACCIONES_PERMITIDAS:
        raise HTTPException(400, f"accion no permitida: {a.accion}")
    if a.accion in ("contratar", "descontratar"):
        if not a.cubo:
            raise HTTPException(400, "falta cubo")
        f = ruta / "contratados.json"
        datos = _contratados(ruta)
        datos[a.cubo] = (a.accion == "contratar")
        f.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        return {"ok": True, "salida": f"{a.cubo}: contratado={datos[a.cubo]} "
                "(marcador v1; la ejecucion de acciones sigue gobernada por "
                "autonomia + gates de la instancia)"}
    if a.accion == "set_autonomia":
        if not (a.cubo and a.nivel and a.motivo and a.motivo.strip()):
            raise HTTPException(400, "set_autonomia exige cubo, nivel y motivo")
        if a.nivel not in NIVELES:
            raise HTTPException(400, f"nivel invalido: {a.nivel}")
        salida = EJECUTOR(ruta, ["operador", "set-autonomia", a.cubo, a.nivel,
                                 "--motivo", a.motivo])
    elif a.accion == "set_limite":
        if a.eur is None or not (a.motivo and a.motivo.strip()):
            raise HTTPException(400, "set_limite exige eur y motivo")
        salida = EJECUTOR(ruta, ["operador", "set-limite-coste", str(a.eur),
                                 "--motivo", a.motivo])
    elif a.accion == "forense":
        salida = EJECUTOR(ruta, ["forense", "diario"])
    else:  # director_html
        salida = EJECUTOR(ruta, ["director", "--html"])
    return {"ok": True, "salida": salida}


# ------------------------------------------------------- alta de empresa (form)
import re as _re


def _slug(nombre: str) -> str:
    s = nombre.lower()
    for a, b in (("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n"),("ü","u")):
        s = s.replace(a, b)
    s = _re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40]


class Alta(BaseModel):
    instancia: str
    nombre_empresa: str
    actividad: str = ""
    publico: str = ""
    tono: str = "cercano y artesano"
    nunca_decir: str = ""
    palabras_prohibidas: str = ""
    responsable: str = ""
    cargo: str = ""
    telefono: str = ""
    email: str = ""
    departamentos: list[str] = []


@app.post("/api/alta")
def api_alta(a: Alta):
    ruta = _instancia_o_404(a.instancia)
    slug = _slug(a.nombre_empresa)
    if not slug:
        raise HTTPException(400, "nombre de empresa vacio o invalido")
    if not a.responsable.strip():
        raise HTTPException(400, "falta el responsable que firma (obligatorio)")
    destino = (ruta / "empresas" / slug).resolve()
    if not str(destino).startswith(str((ruta / "empresas").resolve())):
        raise HTTPException(400, "nombre invalido")
    if destino.exists():
        raise HTTPException(409, f"la empresa '{slug}' ya existe; no se sobrescribe")
    from datetime import date
    hoy = date.today().isoformat()
    (destino / "brand").mkdir(parents=True)

    def _w(rel, datos):
        (destino / rel).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")

    _w("perfil.json", {"empresa": slug, "version": "1.0", "actualizado": hoy,
                       "nombre": a.nombre_empresa.strip(),
                       "descripcion_breve": a.actividad.strip(),
                       "publico_objetivo": a.publico.strip(),
                       "via": "formulario del Centro de Mando"})
    _w("brand/guia.json", {"empresa": slug, "version": "1.0", "actualizado": hoy,
                           "posicionamiento": a.actividad.strip(),
                           "tono": a.tono, "valores": []})
    palabras = [x.strip().lower() for x in a.palabras_prohibidas.split(",") if x.strip()]
    _w("brand/palabras_prohibidas.json",
       {"empresa": slug, "version": "1.0",
        "comentario": "Deteccion por substring (minusculas). Origen: formulario de alta.",
        "palabras": palabras})
    argumentos = [{"id": f"veto_{i+1}", "patrones_substring": [t.strip().lower()],
                   "motivo": "vetado por el cliente en el alta"}
                  for i, t in enumerate(a.nunca_decir.splitlines()) if t.strip()]
    _w("brand/argumentos_prohibidos.json",
       {"empresa": slug, "version": "1.0",
        "comentario": "Argumentos vetados a nivel de marca. Origen: formulario de alta.",
        "argumentos": argumentos})
    _w("brand/firma.json", {"empresa": slug, "version": "1.0",
                            "remitente_nombre": a.responsable.strip(),
                            "remitente_cargo": a.cargo.strip(),
                            "remitente_empresa": a.nombre_empresa.strip(),
                            "telefono": a.telefono.strip(), "email": a.email.strip()})
    todos = sorted(x.parent.name for x in (ruta / "cubos").glob("*/manifest.json"))
    _w("contratados.json", {c: (c in a.departamentos) for c in todos})
    return {"ok": True, "empresa": slug,
            "creado": ["perfil.json", "brand/ (guia, palabras y argumentos prohibidos, firma)",
                        "contratados.json"],
            "siguiente": ("Ficha creada. El guardian de marca ya puede juzgar textos de "
                          f"'{a.nombre_empresa.strip()}' con su propio criterio. Los permisos "
                          "siguen en BAJA: nada sale al mundo sin tu autonomia + comite.")}



_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Centro de Mando - Kaizen</title>
<style>
body{background:#F5F1E8;color:#1A1A1A;font-family:Georgia,serif;max-width:1080px;
     margin:1.5rem auto;padding:0 1rem}
h1{border-bottom:3px solid #C09244;padding-bottom:.3rem;margin-bottom:.4rem}
.fila{display:flex;gap:1rem;align-items:center;flex-wrap:wrap;margin:.8rem 0}
select,input,button{font:inherit;padding:.35rem .6rem;border:1px solid #1A1A1A;
     background:#fff}
button{background:#C09244;color:#F5F1E8;cursor:pointer;border:none}
button.sec{background:#fff;color:#1A1A1A;border:1px solid #1A1A1A}
table{border-collapse:collapse;width:100%;margin:.6rem 0}
th,td{border:1px solid #1A1A1A;padding:.35rem .55rem;text-align:left;font-size:.95rem}
th{background:#C09244;color:#F5F1E8}
.ok{color:#1c6b2a;font-weight:bold}.deg{color:#8a6d00;font-weight:bold}
.err{color:#8a1c1c;font-weight:bold}.sind{font-style:italic}
#salida{white-space:pre-wrap;background:#1A1A1A;color:#F5F1E8;padding:.7rem;
     font-family:Consolas,monospace;font-size:.85rem;min-height:2.2rem}
.pill{display:inline-block;padding:.05rem .5rem;border:1px solid #1A1A1A;
     border-radius:1rem;font-size:.85rem}
footer{margin-top:1.2rem;font-size:.8rem;color:#555}
</style></head><body>
<h1>Centro de Mando <span style="font-size:1rem;color:#555">Kaizen · solo local (127.0.0.1)</span></h1>
<div class="fila">
  <label><b>Empresa:</b></label>
  <select id="inst" onchange="cargar()"></select>
  <button class="sec" onclick="cargar()">Actualizar</button>
  <button onclick="accion({accion:'forense'})">Forense diario</button>
  <button onclick="accion({accion:'director_html'})">Regenerar panel cliente</button>
  <button class="sec" onclick="location='/alta'">+ Alta de empresa</button>
</div>
<div id="resumen" class="fila"></div>
<table id="tabla"><thead><tr>
<th>Departamento</th><th>Contratado</th><th>Autonomia</th><th>Acciones irreversibles</th>
<th>Nota</th><th>Operar</th></tr></thead><tbody></tbody></table>
<div class="fila">
  <b>Limite de gasto:</b>
  <input id="eur" type="number" step="0.5" style="width:6rem" placeholder="EUR">
  <input id="motivo-lim" style="width:20rem" placeholder="motivo (obligatorio)">
  <button onclick="setLimite()">Fijar limite</button>
</div>
<h3>Ultimas verificaciones</h3><div id="verifs" class="sind">SIN DATOS</div>
<h3>Salida</h3><div id="salida">(las respuestas de las acciones aparecen aqui, literales)</div>
<footer>Lecturas: SQL de solo-lectura sobre la BD de cada instancia. Acciones: via el
CLI de la propia instancia — el candado del operador y las cadenas de hash de esa
instancia siguen mandando. "Contratado" es un marcador comercial v1: no abre permisos;
la autonomia y los gates deciden.</footer>
<script>
const $=id=>document.getElementById(id);
async function j(u,opt){const r=await fetch(u,opt);if(!r.ok)throw new Error(await r.text());return r.json()}
async function init(){
  const d=await j('/api/instancias');
  $('inst').innerHTML=d.instancias.map(i=>`<option>${i}</option>`).join('');
  cargar();
}
function nivelSel(c){
  const ops=['CERO','BAJA','MEDIA','ALTA'].map(n=>
    `<option ${n===c?'selected':''}>${n}</option>`).join('');
  return `<select class="niv">${ops}</select>`;
}
async function cargar(){
  const inst=$('inst').value; if(!inst) return;
  const d=await j('/api/estado?instancia='+encodeURIComponent(inst));
  const pipe = d.pipeline ? Object.entries(d.pipeline).map(([k,v])=>`${k}:${v}`).join(' · ')
                          : 'SIN DATOS (ejecuta registro migrar en esa instancia)';
  const coste = d.coste_hoy_eur===null ? 'SIN DATOS'
              : `${d.coste_hoy_eur.toFixed(2)} EUR` + (d.limite_eur?` de ${d.limite_eur.toFixed(2)}`:'' );
  $('resumen').innerHTML =
    `<span class="pill"><b>Pipeline:</b> ${pipe}</span>
     <span class="pill"><b>Gasto hoy:</b> ${coste}</span>`;
  const tb=$('tabla').tBodies[0]; tb.innerHTML='';
  for(const c of d.cubos){
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><b>${c.nombre}</b><br><span style="font-size:.8rem;color:#555">${c.descripcion}</span></td>
      <td style="text-align:center">${c.contratado?'SI':'no'}</td>
      <td>${nivelSel(c.autonomia)}</td>
      <td>${c.irreversibles.join(', ')||'-'}</td>
      <td>${c.nota||''}</td>
      <td><input placeholder="motivo" style="width:9rem" class="mot">
          <button onclick="setAut(this,'${c.nombre}')">Aplicar</button>
          <button class="sec" onclick="accion({accion:'${c.contratado?'descontratar':'contratar'}',cubo:'${c.nombre}'})">
          ${c.contratado?'Descontratar':'Contratar'}</button></td>`;
    tb.appendChild(tr);
  }
  $('verifs').innerHTML = d.verificaciones===null ? 'SIN DATOS'
    : (d.verificaciones.length===0 ? '(ninguna)' :
       '<table><tr><th>Cuando (UTC)</th><th>Tipo</th><th>Accion</th><th>Veredicto</th><th>Confianza</th></tr>'+
       d.verificaciones.map(v=>`<tr><td>${v[0].slice(0,16).replace('T',' ')}</td><td>${v[1]}</td>
        <td>${v[2]}</td><td>${v[3]}</td><td>${v[4]===null?'-':Number(v[4]).toFixed(2)}</td></tr>`).join('')+'</table>');
}
async function accion(cuerpo){
  cuerpo.instancia=$('inst').value;
  try{
    const d=await j('/api/accion',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(cuerpo)});
    $('salida').textContent=d.salida||JSON.stringify(d);
  }catch(e){ $('salida').textContent='ERROR: '+e.message; }
  cargar();
}
function setAut(btn,cubo){
  const tr=btn.closest('tr');
  accion({accion:'set_autonomia',cubo:cubo,
          nivel:tr.querySelector('.niv').value,
          motivo:tr.querySelector('.mot').value});
}
function setLimite(){
  accion({accion:'set_limite',eur:parseFloat($('eur').value),
          motivo:$('motivo-lim').value});
}
init();
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def portada():
    return _HTML



_HTML_ALTA = '''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Alta de empresa - Kaizen</title>
<style>
body{background:#F5F1E8;color:#1A1A1A;font-family:Georgia,serif;max-width:760px;
     margin:1.5rem auto;padding:0 1rem}
h1{border-bottom:3px solid #C09244;padding-bottom:.3rem}
label{display:block;margin:.7rem 0 .2rem;font-weight:bold}
small{color:#555;font-weight:normal}
input,textarea,select{width:100%;font:inherit;padding:.4rem;border:1px solid #1A1A1A;
     background:#fff;box-sizing:border-box}
textarea{min-height:4rem}
.deps{display:grid;grid-template-columns:1fr 1fr;gap:.2rem .8rem;margin:.4rem 0}
.deps label{font-weight:normal;margin:0;display:flex;gap:.4rem;align-items:center}
.deps input{width:auto}
button{font:inherit;background:#C09244;color:#F5F1E8;border:none;padding:.6rem 1.4rem;
     cursor:pointer;margin-top:1rem}
#out{white-space:pre-wrap;background:#1A1A1A;color:#F5F1E8;padding:.7rem;margin-top:1rem;
     font-family:Consolas,monospace;font-size:.85rem;display:none}
a{color:#8a6d00}
</style></head><body>
<h1>Alta de empresa</h1>
<p>Esto es lo UNICO que Kaizen necesita saber de un cliente nuevo para empezar.
Rellenalo con el (10 minutos) o mandale estas preguntas tal cual.</p>
<label>Nombre de la empresa *</label><input id="nombre" placeholder="Panaderia Pedro SL">
<label>Que vende / a que se dedica * <small>(dos o tres frases, con sus palabras)</small></label>
<textarea id="actividad" placeholder="Pan artesano de masa madre en Padron..."></textarea>
<label>Quien es su cliente tipico</label>
<input id="publico" placeholder="bares, cafeterias y tiendas gourmet de la zona">
<label>Como quiere sonar</label>
<select id="tono"><option>cercano y artesano</option><option>profesional y sobrio</option>
<option>juvenil y fresco</option><option>premium y elegante</option></select>
<label>Cosas que NUNCA hay que decir <small>(una por linea)</small></label>
<textarea id="nunca" placeholder="somos los mas baratos&#10;criticar a la competencia"></textarea>
<label>Palabras prohibidas <small>(separadas por comas)</small></label>
<input id="palabras" placeholder="barato, oferta, industrial">
<label>Quien firma las comunicaciones * <small>(nombre real del responsable)</small></label>
<input id="resp" placeholder="Pedro Garcia">
<label>Su cargo</label><input id="cargo" placeholder="Gerente">
<label>Telefono de contacto</label><input id="tel">
<label>Email de contacto</label><input id="email">
<label>Departamentos que contrata</label>
<div class="deps" id="deps"></div>
<button onclick="enviar()">Crear la ficha de la empresa</button>
<p><a href="/">&larr; volver al Centro de Mando</a></p>
<div id="out"></div>
<script>
const DEPS=["comercial","brand","marketing","customer_success","inteligencia",
            "finanzas","legal","ops","qa","rrhh"];
document.getElementById('deps').innerHTML=DEPS.map(d=>
  `<label><input type="checkbox" value="${d}" ${d==='brand'?'checked':''}>${d}</label>`).join('');
async function enviar(){
  const g=id=>document.getElementById(id).value;
  const deps=[...document.querySelectorAll('#deps input:checked')].map(x=>x.value);
  const inst=(await (await fetch('/api/instancias')).json()).instancias[0];
  const r=await fetch('/api/alta',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({instancia:inst,nombre_empresa:g('nombre'),actividad:g('actividad'),
      publico:g('publico'),tono:g('tono'),nunca_decir:g('nunca'),
      palabras_prohibidas:g('palabras'),responsable:g('resp'),cargo:g('cargo'),
      telefono:g('tel'),email:g('email'),departamentos:deps})});
  const out=document.getElementById('out'); out.style.display='block';
  const d=await r.json().catch(()=>({detail:'error'}));
  out.textContent = r.ok ? ('CREADA: '+d.empresa+String.fromCharCode(10)+d.siguiente)
                         : ('ERROR: '+(d.detail||r.status));
}
</script></body></html>
'''


@app.get("/alta", response_class=HTMLResponse)
def alta_form():
    return _HTML_ALTA


if __name__ == "__main__":
    import uvicorn
    print("Centro de Mando Kaizen -> http://127.0.0.1:8600  (solo local; Ctrl+C para salir)")
    uvicorn.run(app, host="127.0.0.1", port=8600, log_level="warning")
