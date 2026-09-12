"""Centinela de datos (R-REV-1, pieza 1) — el guardia que sustituye al filtro
manual de cada commit.

Todo se prueba contra la funcion PURA `escanear`: sin git, sin disco, sin red.

Nota deliberada: las claves de ejemplo se ARMAN por concatenacion en tiempo de
ejecucion. Si estuvieran escritas enteras en el fuente, este mismo fichero
dispararia el centinela y no podria commitearse — el guardia se aplica a si
mismo, que es justo lo que debe hacer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from herramientas.centinela_datos import (escanear, informe, motivo_override,
                                          normalizar)

# Formas de clave realistas, nunca literales en el fuente.
CLAVE_ANTHROPIC = "sk-" + "ant-" + "api03-" + ("Ab3xY9" * 5)
CLAVE_OPENAI = "sk-" + ("Kd8Zq2Wn7Lp4Rt6Vx1Cy" * 2)


def _rutas(violaciones):
    return {v["ruta"] for v in violaciones}


def _b(texto):
    return texto.encode("utf-8")


# --- Reglas por RUTA ---------------------------------------------------------

def test_bloquea_las_cuatro_carpetas_de_datos():
    rutas = ["state/voz/quota/quota_20260803.json",
             "data/kaizen.db",
             "diario/clientereal/ESTADO_ACTUAL.md",
             "bitacora/2026-08-03.log"]
    v = escanear([(r, _b("contenido inocuo")) for r in rutas])
    assert _rutas(v) == set(rutas)
    assert all("no entra en git" in x["motivo"] for x in v)


def test_bloquea_brand_y_argumentario_de_empresa_real():
    v = escanear([("empresas/clientereal/brand/guia.json", _b("{}")),
                  ("empresas/clientereal/argumentario.json", _b("{}"))])
    assert _rutas(v) == {"empresas/clientereal/brand/guia.json",
                         "empresas/clientereal/argumentario.json"}


def test_permite_el_tenant_sintetico_laboratorio():
    """La allowlist manda sobre las reglas de ruta: laboratorio es ficcion."""
    v = escanear([("empresas/laboratorio/brand/guia.json", _b("{}")),
                  ("empresas/laboratorio/argumentario.json", _b("{}")),
                  ("empresas/laboratorio/perfil.json", _b("{}"))])
    assert v == []


def test_la_allowlist_no_perdona_una_clave_real():
    """Ser sintetico exime de las reglas de RUTA, no de las de CONTENIDO."""
    v = escanear([("empresas/laboratorio/perfil.json",
                   _b('{"k": "%s"}' % CLAVE_ANTHROPIC))])
    assert len(v) == 1
    assert "sk-ant" in v[0]["motivo"]


def test_bloquea_env_y_permite_env_example():
    v = escanear([(".env", _b("x=1")),
                  (".env.bak_20260802_cierre_sandbox", _b("x=1")),
                  (".env.example", _b("# plantilla\n"))])
    assert _rutas(v) == {".env", ".env.bak_20260802_cierre_sandbox"}


def test_bloquea_ficheros_de_secretos_y_contador_de_gasto():
    v = escanear([("notas/mis_keys.txt", _b("")),
                  ("SECRET_backup.txt", _b("")),
                  (".kaizen_cost.json", _b("{}"))])
    assert _rutas(v) == {"notas/mis_keys.txt", "SECRET_backup.txt",
                         ".kaizen_cost.json"}


def test_normaliza_separadores_de_windows():
    v = escanear([("diario\\clientereal\\DECISIONES.md", _b("x"))])
    assert _rutas(v) == {"diario/clientereal/DECISIONES.md"}
    assert normalizar(".\\state\\x.json") == "state/x.json"


# --- Reglas por CONTENIDO ----------------------------------------------------

def test_detecta_asignacion_de_clave_real_en_cualquier_ruta():
    v = escanear([("core/config.py", _b("ANTHROPIC_API" + "_KEY=" + CLAVE_ANTHROPIC))])
    # Cae por las dos reglas a la vez: la asignacion y la forma de clave suelta.
    assert _rutas(v) == {"core/config.py"}
    motivos = " | ".join(x["motivo"] for x in v)
    assert "asignacion de secreto real a ANTHROPIC_API_KEY" in motivos
    assert "incrustada" in motivos
    assert all("linea 1" in x["motivo"] for x in v)


def test_detecta_claves_sueltas_sin_asignacion():
    v = escanear([("docs/notas.md", _b("me paso esto por whatsapp: " + CLAVE_OPENAI)),
                  ("docs/otra.md", _b("y esta: " + CLAVE_ANTHROPIC))])
    assert len(v) == 2
    assert all("incrustada" in x["motivo"] for x in v)


def test_placeholders_no_disparan():
    """.env.example real del repo + las formas de relleno habituales."""
    ejemplo = "\n".join([
        "# Plantilla de variables de entorno. Copia a .env y rellena.",
        "ANTHROPIC_API" + "_KEY=sk-ant-...",
        "OPENAI_API" + "_KEY=",
        "GROQ_API" + "_KEY=your_key_here",
        "GEMINI_API" + "_KEY=xxx",
        "TWILIO_AUTH" + "_TOKEN=<tu-token>",
        "ELEVENLABS_API" + "_KEY=changeme",
    ])
    assert escanear([(".env.example", _b(ejemplo))]) == []


def test_una_referencia_de_codigo_no_es_un_secreto():
    """El patron real del repo: leer la variable, no incrustarla."""
    codigo = "\n".join([
        'clave = os.getenv("ANTHROPIC_API' + '_KEY", "")',
        'if linea.strip().startswith("OPENROUTER_API' + '_KEY="):',
        'HF' + '_TOKEN=${HF' + '_TOKEN}',
    ])
    assert escanear([("sustrato/comite.py", _b(codigo))]) == []


def test_tabla_de_variables_por_columnas_no_dispara():
    """Regresion: en AUDITORIA_KAIZEN_2026-07-02.md las variables van alineadas
    en columnas y todas vacias. El 'valor' de una es el NOMBRE de la siguiente;
    eso no es una credencial."""
    tabla = "\n".join([
        "ANTHROPIC_API" + "_KEY=        DEEPSEEK_API" + "_KEY=         ELEVENLABS_AGENT_ID=",
        "GROQ_API" + "_KEY=             HF" + "_TOKEN=                 IVAN_VOICE_ID=",
        "TWILIO_ACCOUNT" + "_SID=       TWILIO_API_KEY" + "_SECRET=    TWILIO_FROM_NUMBER=",
    ])
    assert escanear([("AUDITORIA_KAIZEN_2026-07-02.md", _b(tabla))]) == []


def test_permite_un_py_normal_sin_secretos():
    codigo = "\n".join(["# -*- coding: utf-8 -*-",
                        "def suma(a, b):",
                        "    return a + b",
                        ""])
    assert escanear([("core/util.py", _b(codigo))]) == []


def test_valor_no_reconocible_bloquea_para_revision_humana():
    """Fail-closed: si no es placeholder ni codigo, se para y que mire un humano."""
    v = escanear([("notas.md", _b("GEMINI_API" + "_KEY=Zt4Rq9Ln2Xb7Kd5Mw"))])
    assert len(v) == 1


# --- Casos de borde y fail-closed -------------------------------------------

def test_contenido_ilegible_bloquea():
    v = escanear([("core/util.py", None)])
    assert len(v) == 1
    assert "fail-closed" in v[0]["motivo"]


def test_entrada_no_reconocida_bloquea():
    v = escanear([("solo-la-ruta",), ("", _b("x"))])
    assert len(v) == 2
    assert all("fail-closed" in x["motivo"] for x in v)


def test_binario_no_revienta():
    assert escanear([("empresas/laboratorio/logo.png", b"\x89PNG\r\n\x1a\n\xff\xfe")]) == []


def test_staging_limpio_no_produce_nada():
    assert escanear([]) == []


# --- Override del operador ---------------------------------------------------

def test_override_con_motivo_desbloquea_pero_deja_rastro():
    v = escanear([("diario/clientereal/ESTADO_ACTUAL.md", _b("x"))])
    lineas, codigo = informe(v, motivo="rescate del savepoint, autorizado por Angel")
    assert codigo == 0
    texto = "\n".join(lineas)
    assert "rescate del savepoint" in texto
    assert "diario/clientereal/ESTADO_ACTUAL.md" in texto   # la violacion sigue a la vista


def test_sin_motivo_no_hay_bypass():
    v = escanear([("diario/clientereal/ESTADO_ACTUAL.md", _b("x"))])
    for motivo in (None, "", "   ", "\t\n"):
        lineas, codigo = informe(v, motivo=motivo)
        assert codigo == 1
        assert "BLOQUEADO" in "\n".join(lineas)


def test_la_variable_vacia_no_cuenta_como_motivo():
    assert motivo_override({}) is None
    assert motivo_override({"CENTINELA_OVERRIDE": ""}) is None
    assert motivo_override({"CENTINELA_OVERRIDE": "   "}) is None
    assert motivo_override({"CENTINELA_OVERRIDE": " migracion R-REV-1 "}) == "migracion R-REV-1"


def test_limpio_sale_con_codigo_cero():
    lineas, codigo = informe([], motivo=None)
    assert codigo == 0
    assert "OK" in lineas[0]


# ── R-TENANT: ningun nombre de cliente real en el arbol del producto ──────────
#
# La lista de vetados llega SIEMPRE por parametro: escribirla en el fuente seria
# la propia violacion que se persigue (por eso `nombres_vetados` la deriva de la
# raiz de datos, que vive fuera del arbol).

VETADO = "clientereal"


def test_nombre_de_cliente_en_el_arbol_se_bloquea():
    v = escanear([("kaizen.py", _b(f"BANNER = 'Kaizen · {VETADO.capitalize()}'"))],
                 vetados={VETADO})
    assert _rutas(v) == {"kaizen.py"}
    assert "R-TENANT" in v[0]["motivo"]
    assert VETADO in v[0]["motivo"]


def test_sin_lista_de_vetados_la_regla_no_dispara():
    """Sin raiz de datos no hay contra que comparar: el resto de reglas siguen,
    pero esta no puede inventarse un veredicto."""
    entrada = [("kaizen.py", _b(f"BANNER = '{VETADO}'"))]
    assert escanear(entrada, vetados=None) == []
    assert escanear(entrada, vetados=set()) == []
    assert escanear(entrada) == []


def test_se_reporta_una_vez_por_nombre_no_por_aparicion():
    contenido = "\n".join([f"# {VETADO}"] * 5)
    v = escanear([("docs.md", _b(contenido))], vetados={VETADO})
    assert len(v) == 1


def test_solo_palabra_completa():
    """`laboratorio_dos` no puede disparar dentro de `serial` o `industrial`."""
    v = escanear([("core/x.py", _b("modo = 'serial'  # industrial"))], vetados={"laboratorio_dos"})
    assert v == []


def test_el_tenant_sintetico_no_es_un_nombre_vetado():
    from herramientas.centinela_datos import TENANTS_SINTETICOS
    v = escanear([("core/rutas.py", _b("TENANTS = ('laboratorio',)"))],
                 vetados={n for n in {"laboratorio"} if n not in TENANTS_SINTETICOS})
    assert v == []
