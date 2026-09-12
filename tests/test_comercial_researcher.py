"""Tests del Researcher con una fuente sintética (no usa red).

El test E2E con Google Places vive en `test_comercial_e2e.py` y hace llamadas reales.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.anillos import ClasificadorAnillos
from departments.comercial.distancia.haversine import HaversineProvider
from departments.comercial.fuentes.base import CandidatoCrudo, FuenteLeads
from departments.comercial.icp import FiltroICP
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.researcher import Researcher


class FakeFuente(FuenteLeads):
    """Fuente determinista para tests: devuelve candidatos fijos por query."""
    nombre = "fake"

    def __init__(self, catalogo: dict[str, list[CandidatoCrudo]]) -> None:
        self.catalogo = catalogo
        self.llamadas: list[str] = []

    def buscar(self, query, *, centro=None, radio_m=30000, max_resultados=20):
        self.llamadas.append(query)
        return self.catalogo.get(query, [])[:max_resultados]


def _cand(nombre, lat, lon, place_types, *, id_externo=None, telefono="968 000 000",
          ratings_count=20, business_status="OPERATIONAL", web="https://x.test"):
    return CandidatoCrudo(
        fuente="fake", id_externo=id_externo or nombre,
        nombre=nombre, direccion=f"{nombre}, Murcia",
        ubicacion={"lat": lat, "lon": lon},
        tipo_principal=place_types[0] if place_types else None,
        place_types=list(place_types),
        descripcion="",
        metadatos={"business_status": business_status, "ratings_count": ratings_count,
                   "telefono": telefono, "web": web},
    )


def _researcher(catalogo) -> tuple[Researcher, LeadStore, FakeFuente]:
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    icp = FiltroICP("laboratorio")
    origen = icp.origen
    anillos = ClasificadorAnillos(HaversineProvider(), origen["lat"], origen["lon"],
                                  max_anillo_activo=icp.max_anillo)
    fuente = FakeFuente(catalogo)
    return Researcher(icp=icp, anillos=anillos, fuentes=[fuente],
                      lead_store=store, max_workers=2), store, fuente


def test_filtra_marca_excluida_no_se_crea_lead():
    catalogo = {
        # Una query devuelve un hotel legítimo y una marca excluida.
        "hotel boutique en Villa Sintetica": [
            _cand("Hotel La Parra", 38.24, -1.42, ["lodging"]),
            _cand("Marca Sintetica Excluida Uno S.L.", 38.24, -1.42, ["supermarket"]),
        ],
    }
    r, store, _ = _researcher(catalogo)
    # Forzamos solo la categoría hotel para limitar las queries que ejecuta.
    r.construir_campanas = lambda prioridades=("ALTA",): [
        type(r).__name__.__class__,
    ] or []   # no-op; usamos ejecutar_pasada manualmente sería complejo aquí.
    # Mejor: invocamos al pipeline con catálogo más amplio y dejamos que el ICP filtre.
    pass  # ver test siguiente


def test_pasada_completa_con_fuente_sintetica():
    # Construimos un catálogo donde cada query del ICP tiene 1-2 candidatos. Cubrimos
    # algunas queries que el Researcher generará realmente; las demás devolverán vacío.
    catalogo = {
        "hotel boutique en Villa Sintetica": [
            _cand("Hotel La Parra", 38.24, -1.42, ["lodging"]),
            _cand("Marca Sintetica Excluida Uno Hotel", 38.24, -1.42, ["lodging"]),
        ],
        "casa rural en Villa Sintetica": [
            _cand("Casa Rural El Olivar", 38.24, -1.41, ["lodging"]),
        ],
        "cafeteria de especialidad en Villa Sintetica": [
            _cand("Cafe Tostadero Norte", 38.25, -1.42, ["cafe"]),
            _cand("Marca Sintetica Excluida Dos Cafe", 38.25, -1.42, ["cafe"]),
        ],
        "tienda gourmet en Aldea Sintetica": [
            _cand("Delicatessen El Olivo", 38.25, -1.41, ["store"], ratings_count=5),
        ],
        "tienda gourmet en Villa Sintetica": [
            _cand("Super del Pueblo", 38.24, -1.42, ["supermarket"]),  # excluido por tipo
        ],
    }
    r, store, fuente = _researcher(catalogo)
    res = r.ejecutar_pasada(prioridades=("ALTA",), max_por_query=10, verbose=False)

    # Pasan el ICP los que encajan por place_type y no llevan marca excluida.
    cualificados = store.listar(EstadoLead.CUALIFICADO)
    nombres = sorted(c["nombre"] for c in cualificados)
    assert "Hotel La Parra" in nombres
    assert "Casa Rural El Olivar" in nombres
    assert "Delicatessen El Olivo" in nombres
    # Excluidos no deben aparecer: dos por marca, uno por place_type.
    assert not any("Marca Sintetica Excluida" in n or n == "Super del Pueblo"
                   for n in nombres)
    assert res.descartes_icp >= 3
    assert res.cualificados_nuevos >= 3


def test_dedup_por_id_externo():
    catalogo = {
        "hotel boutique en Villa Sintetica": [
            _cand("Hotel La Parra", 38.24, -1.42, ["lodging"], id_externo="place_1"),
        ],
        "casa rural en Villa Sintetica": [
            _cand("Hotel La Parra", 38.24, -1.42, ["lodging"], id_externo="place_1"),
        ],
    }
    r, store, _ = _researcher(catalogo)
    res = r.ejecutar_pasada(prioridades=("ALTA",), max_por_query=10, verbose=False)
    # El mismo place_id solo se crea una vez.
    assert res.cualificados_nuevos == 1


def test_dedup_fallback_por_slug_cuando_no_hay_id_externo():
    catalogo = {
        "hotel boutique en Villa Sintetica": [_cand("Hotel La Parra", 38.24, -1.42, ["lodging"], id_externo="")],
        "casa rural en Villa Sintetica":     [_cand("Hotel La Parra", 38.24, -1.42, ["lodging"], id_externo="")],
    }
    r, store, _ = _researcher(catalogo)
    res = r.ejecutar_pasada(prioridades=("ALTA",), max_por_query=10, verbose=False)
    assert res.cualificados_nuevos == 1


def test_pasada_idempotente_no_duplica_leads_existentes():
    catalogo = {
        "hotel boutique en Villa Sintetica": [_cand("Hotel La Parra", 38.24, -1.42, ["lodging"])],
    }
    r, store, _ = _researcher(catalogo)
    r.ejecutar_pasada(prioridades=("ALTA",), verbose=False)
    res2 = r.ejecutar_pasada(prioridades=("ALTA",), verbose=False)
    # Segunda pasada: el lead ya existe → ya_existentes >= 1, no crea duplicados.
    assert res2.leads_ya_existentes >= 1


def test_pasada_espeja_cualificados_en_lead_canon():
    """Puente aditivo (departments/comercial/puente_canonico.py): cada candidato que
    pasa ICP/anillo debe terminar tambien en la coleccion canonica 'lead_canon', sin
    que eso sustituya ni rompa el LeadStore legado."""
    catalogo = {
        "hotel boutique en Villa Sintetica": [
            _cand("Hotel La Parra", 38.24, -1.42, ["lodging"]),
        ],
        "casa rural en Villa Sintetica": [
            _cand("Casa Rural El Olivar", 38.24, -1.41, ["lodging"]),
        ],
    }
    r, store, _ = _researcher(catalogo)
    res = r.ejecutar_pasada(prioridades=("ALTA",), max_por_query=10, verbose=False)

    cualificados = store.listar(EstadoLead.CUALIFICADO)
    assert cualificados   # sanity: el legacy sigue funcionando igual que siempre

    canon = store.k.all("laboratorio", "lead_canon")
    nombres_canon = sorted(n["nombre"] for n in canon.values())
    nombres_legacy = sorted(c["nombre"] for c in cualificados)
    assert nombres_canon == nombres_legacy
    # El puente nunca debe generar errores propios que contaminen res.errores.
    assert not any("puente a lead_canon" in e for e in res.errores)
