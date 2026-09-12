"""Tests del EmailComposer (con LLM mockeado) y la orquestación del SDR.preparar()."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.brand_guardian import BrandGuardian
from departments.comercial.cola_aprobacion import ColaAprobacion
from departments.comercial.email_composer import EmailComposer
from departments.comercial.lifecycle import EstadoLead, LeadStore
from departments.comercial.sdr.multicanal import SDRMulticanal


CONTEXTO = """## Contacto comercial (remitente)
- **Nombre:** Iván Carbonell
- **Cargo:** Director comercial
- **Empresa:** Repostería Laboratorio (Cieza)
- **Teléfono:** 600 000 000
"""
CUERPO_BUENO = (
    "Buenos días,\n\nLes escribo desde Repostería Laboratorio, obrador centenario de Cieza. "
    "Quería presentarles nuestros productos artesanales: tortas, rollicos, dulces "
    "tradicionales con recetas de más de cien años. Pienso que podrían encajar con la "
    "carta de su establecimiento. Si les apetece probar, estaré encantado de acercarme con "
    "una selección sin compromiso.\n\nUn saludo,\nIván Carbonell\nRepostería Laboratorio (Cieza)\n600 000 000"
    # Desde el 2026-08-02 (AI Act art. 50, candado E4) un cuerpo "bueno" DEBE
    # identificarse como IA: sin disclosure, el composer lo rechaza en composición.
    "\n\n(Mensaje redactado con un sistema automatizado y revisado por una persona "
    "antes de enviarse.)"
)


def _bg_acepta():
    return BrandGuardian(empresa="laboratorio", contexto_negocio=CONTEXTO,
                         semantic_evaluator=lambda *a, **kw: {"ok": True, "motivo": "OK", "dictamen": "APROBADO"})


def _chat_secuencial(respuestas):
    """Devuelve respuestas en orden por llamada (para simular cuerpo+asunto+reintentos)."""
    it = iter(respuestas)
    def chat(messages, system=None, **kw):
        return next(it)
    return chat


def test_composer_devuelve_borrador_aprobado_al_primer_intento():
    composer = EmailComposer(
        empresa="laboratorio",
        brand_guardian=_bg_acepta(),
        chat=_chat_secuencial([CUERPO_BUENO, "Repostería artesanal para vuestra carta"]),
    )
    lead = {"id": "x", "nombre": "X", "categoria_icp": "hotel_boutique_con_desayuno",
            "prioridad_icp": "ALTA", "ubicacion": {"direccion": "Cieza"}}
    b = composer.componer(lead)
    assert b.aprobado_por_brand
    assert b.intentos == 1
    assert b.asunto and b.cuerpo


def test_composer_reintenta_si_brand_guardian_rechaza_primero():
    """Primer intento: cuerpo corto → BG rechaza. Segundo: cuerpo OK → BG acepta."""
    cuerpo_corto = "Hola, un saludo."
    composer = EmailComposer(
        empresa="laboratorio",
        brand_guardian=_bg_acepta(),
        chat=_chat_secuencial([cuerpo_corto, "asunto1", CUERPO_BUENO, "asunto2"]),
        intentos_max=2,
    )
    lead = {"id": "x", "nombre": "X", "categoria_icp": "cafeteria_especialidad",
            "prioridad_icp": "ALTA", "ubicacion": {"direccion": "Murcia"}}
    b = composer.componer(lead)
    assert b.intentos == 2
    assert b.aprobado_por_brand


def test_composer_se_rinde_tras_intentos_max():
    """Si todos los intentos fallan BG, devuelve el último con review no-aprobado."""
    cuerpo_corto = "Hola."
    composer = EmailComposer(
        empresa="laboratorio",
        brand_guardian=_bg_acepta(),
        chat=_chat_secuencial([cuerpo_corto, "a1", cuerpo_corto, "a2"]),
        intentos_max=2,
    )
    lead = {"id": "x", "nombre": "X", "categoria_icp": "tienda_gourmet_delicatessen",
            "prioridad_icp": "ALTA", "ubicacion": {"direccion": "Yecla"}}
    b = composer.componer(lead)
    assert b.intentos == 2
    assert not b.aprobado_por_brand


# ── SDRMulticanal.preparar() ─────────────────────────────────────────────────
def _seed_leads_enriquecidos(n: int) -> tuple[LeadStore, ColaAprobacion]:
    k = InMemoryKnowledge()
    store = LeadStore(k, "laboratorio")
    for i in range(n):
        store.crear(f"l{i}", {
            "nombre": f"Lead {i}", "anillo": 0, "prioridad_icp": "ALTA",
            "categoria_icp": "hotel_boutique_con_desayuno",
            "metadatos_fuente": {"ratings_count": 50, "rating": 4.5},
            "ubicacion": {"direccion": "Cieza"},
            "contacto": {"telefono": "968", "web": "x", "email": f"l{i}@x.com"},
        })
        store.transicionar(f"l{i}", EstadoLead.CUALIFICADO, razon="seed")
        store.transicionar(f"l{i}", EstadoLead.ENRIQUECIDO, razon="seed")
    cola = ColaAprobacion(k, "laboratorio")
    return store, cola


class _ComposerStub:
    """Composer mockeado para no llamar al LLM en tests de integración del SDR."""
    def __init__(self):
        self.llamadas = 0
    def componer(self, lead):
        self.llamadas += 1
        from departments.comercial.brand_guardian import BrandReview
        from departments.comercial.email_composer import Borrador
        return Borrador(
            asunto=f"Asunto {lead['id']}",
            cuerpo=f"Cuerpo {lead['id']} OK",
            review=BrandReview(aprobado=True, problemas=[], sugerencias=[], detalle_llm="OK"),
            intentos=1, lead_id=lead["id"], razones_de_personalizacion=["test"],
        )


def test_sdr_preparar_encola_los_top_n():
    store, cola = _seed_leads_enriquecidos(5)
    sdr = SDRMulticanal(lead_store=store, cola=cola, composer=_ComposerStub())
    res = sdr.preparar(limite=3, verbose=False)
    assert res.preparados == 3
    assert len(res.pendientes_ids) == 3
    # Estado de los leads: SIGUEN en ENRIQUECIDO (no enviado todavía).
    for pid in res.pendientes_ids:
        p = cola.get(pid)
        assert store.get(p["lead_id"])["estado"] == EstadoLead.ENRIQUECIDO.value


def test_sdr_preparar_idempotente_no_repite_leads():
    store, cola = _seed_leads_enriquecidos(3)
    sdr = SDRMulticanal(lead_store=store, cola=cola, composer=_ComposerStub())
    r1 = sdr.preparar(limite=3, verbose=False)
    assert r1.preparados == 3
    # Segunda pasada: todos ya están en cola → 0 preparados nuevos.
    r2 = sdr.preparar(limite=3, verbose=False)
    assert r2.preparados == 0


def test_sdr_preparar_filtra_sin_destino():
    """Lead sin contacto.email se cuenta en sin_destino (Fase 1.5 lo resolverá)."""
    store, cola = _seed_leads_enriquecidos(0)
    store.crear("sin_mail", {"nombre": "Sin email", "anillo": 0,
                              "prioridad_icp": "ALTA", "contacto": {"telefono": "x", "web": "y"}})
    store.transicionar("sin_mail", EstadoLead.CUALIFICADO, razon="seed")
    store.transicionar("sin_mail", EstadoLead.ENRIQUECIDO, razon="seed")
    sdr = SDRMulticanal(lead_store=store, cola=cola, composer=_ComposerStub())
    res = sdr.preparar(limite=10, verbose=False)
    assert res.preparados == 0
    assert res.sin_destino == 1
