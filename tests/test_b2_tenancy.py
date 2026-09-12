"""Bloque D00-B2: registro de tenants, primitivas de datos y aislamiento adversario.

Ataca las invariantes I1/I3/I5 de D00 §2.2 con dos tenants adversarios cuyos datos
estan diseñados para aflorar en el otro (nombres/emails sembrados), y verifica el
gate anti-literales sobre las rutas de produccion tocadas en B2.
"""
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.knowledge import InMemoryKnowledge
from core import tenants as T

RAIZ = Path(__file__).parent.parent
VENENO_A = "VENENO_DE_TENANT_A_919"
VENENO_B = "VENENO_DE_TENANT_B_747"


@pytest.fixture()
def k_adversario():
    k = InMemoryKnowledge()
    k.add("tenant_a", "lead", "l1", {"id": "l1", "nombre": VENENO_A,
                                     "email": "a@venenoa.example",
                                     "fecha_ultima_transicion": "2026-07-01T00:00:00+00:00"})
    k.add("tenant_a", "compromiso", "c1", {"id": "c1", "texto": f"llamar a {VENENO_A}"})
    k.add("tenant_b", "lead", "l9", {"id": "l9", "nombre": VENENO_B,
                                     "email": "b@venenob.example",
                                     "fecha_ultima_transicion": "2024-01-01T00:00:00+00:00"})
    return k


def test_registro_carga_fichas_validas():
    """R-TENANT: el test valida la FORMA del registro, no QUE clientes hay dentro.
    Antes exigia tres ids reales, lo que ataba la suite a la cartera del momento."""
    reg = T.cargar_registro()
    assert reg["tenants"], "registro sin tenants"
    for t in reg["tenants"]:
        assert t["id"] and t["id"] == t["id"].lower() and t["id"].isascii()
        assert t["estado"] in ("activo", "pausado", "baja")
        assert t["mandato"]["nivel_por_defecto"] == "BAJA"   # default de la serie


def test_tenant_sin_ficha_no_opera():
    with pytest.raises(T.TenantInvalido):
        T.get_tenant("tenant_fantasma")


def test_export_no_fuga_datos_de_otro_tenant(k_adversario, tmp_path):
    man = T.exportar_tenant(k_adversario, "tenant_a", tmp_path)
    contenido = Path(man["fichero"]).read_text(encoding="utf-8")
    assert VENENO_A in contenido
    assert VENENO_B not in contenido, "FUGA I1: datos de B en el export de A"
    assert man["sha256"] and man["tipos"] == {"lead": 1, "compromiso": 1}


def test_borrado_exige_export_y_deja_acta_sin_tocar_al_vecino(k_adversario, tmp_path):
    dry = T.borrar_dato_cliente(k_adversario, "tenant_a")
    assert dry["dry_run"] and dry["plan_borrado"] == {"lead": ["l1"], "compromiso": ["c1"]}
    assert k_adversario.get("tenant_a", "lead", "l1") is not None  # dry-run: cero efectos
    with pytest.raises(T.TenantInvalido):
        T.borrar_dato_cliente(k_adversario, "tenant_a", confirmar=True)  # sin export
    man = T.exportar_tenant(k_adversario, "tenant_a", tmp_path)
    acta = T.borrar_dato_cliente(k_adversario, "tenant_a", export_manifest=man,
                                 confirmar=True, acta_dir=tmp_path)
    assert acta["borrados"] == 2 and acta["hash_acta"]
    assert k_adversario.all("tenant_a") in ({}, {"lead": {}, "compromiso": {}})
    assert k_adversario.get("tenant_b", "lead", "l9")["nombre"] == VENENO_B  # B intacto


def test_snapshot_reproducible(k_adversario, tmp_path):
    s1 = T.snapshot(k_adversario, "tenant_b", tmp_path)
    s2 = T.snapshot(k_adversario, "tenant_b", tmp_path)
    assert s1["sha256"] == s2["sha256"]


def test_retencion_detecta_viejos_y_es_dry_run_por_defecto(k_adversario):
    ahora = datetime(2026, 7, 10, tzinfo=timezone.utc)
    r = T.retencion(k_adversario, "tenant_b", dias=365, ahora=ahora)
    assert r["candidatos"] == ["l9"] and r["dry_run"]
    assert k_adversario.get("tenant_b", "lead", "l9") is not None
    r2 = T.retencion(k_adversario, "tenant_b", dias=365, ahora=ahora, confirmar=True)
    assert r2["accion"] == "plataforma.retencion.ejecutada"
    assert k_adversario.get("tenant_b", "lead", "l9") is None


# ── Gate anti-literales (D00 §2.2, B2.2) ─────────────────────────────────────

# R-TENANT (2026-08-04): ya NO hay patron permitido. Los tres que habia
# —default de opcion CLI, KAIZEN_COMPANY y default de parametro— eran justo las
# tres formas en que un cliente real se colaba en el producto. El defecto es
# ahora el tenant sintetico y el gate no admite excepciones.
#
# El nombre vetado no se escribe aqui: eso seria la propia violacion. Se deriva
# del registro de tenants de la raiz de datos, que vive fuera del arbol.
RUTAS_SANEADAS = [
    "kaizen.py",
    "mesa_jefe.py",
    "agentes.py",
    "diario_ops.py",
    "core/tenants.py",
    "core/rutas.py",
    "core/compromisos.py",
    "core/knowledge_migration.py",
    "core/rue.py",
    "sustrato/cli.py",
    "sustrato/propuestas.py",
    "sustrato/registro.py",
    "sustrato/config.py",
    "cubos/comercial/adaptador.py",
    "cubos/comercial/ritual_manana.py",
    "departments/brand/config.py",
    "departments/brand/asset_manager.py",
    "departments/brand/brand_guardian.py",
    "departments/brand/brand_strategist.py",
    "departments/brand/director.py",
    "departments/brand/voice_auditor.py",
    "departments/comercial/brand_guardian.py",
    "departments/comercial/director.py",
    "departments/comercial/email_composer.py",
    "departments/comercial/icp.py",
    "departments/comercial/researcher.py",
    "departments/comercial/rituales.py",
    "departments/comercial/account_executive.py",
    "departments/comercial/dashboard_director.py",
    "departments/comercial/sdr/compromiso.py",
    "departments/comercial/sdr/voz_play/composer.py",
    "departments/comercial/sdr/voz_conversacional/post_call.py",
    "departments/comercial/sdr/voz_conversacional/analisis_calidad.py",
    "departments/comercial/sdr/voz_conversacional/cliente_eleven_cai.py",
    "panel_mando/app.py",
    "api/server.py",
]


def _nombres_de_cliente_reales() -> set:
    """Ids de tenant reales conocidos por la raiz de datos. Vacio = no comprobable."""
    sys.path.insert(0, str(RAIZ / "herramientas"))
    from herramientas.centinela_datos import nombres_vetados
    return nombres_vetados() or set()


def test_gate_anti_literales_en_rutas_criticas():
    """Ningun nombre de cliente real en las rutas ya saneadas. Este gate fija lo
    limpio para que no se reabra; el barrido total lo hace el centinela en cada
    commit (herramientas/centinela_datos.py)."""
    vetados = _nombres_de_cliente_reales()
    if not vetados:
        pytest.skip("raiz de datos no accesible: no hay contra que comprobar")
    violaciones = []
    for rel in RUTAS_SANEADAS:
        f = RAIZ / rel
        if not f.exists():
            continue
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            bajo = linea.lower()
            for nombre in vetados:
                if re.search(r"\b%s\b" % re.escape(nombre), bajo):
                    violaciones.append(f"{rel}:{n}: {linea.strip()[:90]}")
                    break
    assert not violaciones, f"nombre de cliente real en el arbol del producto: {violaciones}"
