"""Tests de la máquina de estados del pipeline (M2)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.lead_schema import LeadDoc
from core.pipeline_state_machine import (
    EstadoPipeline, PipelineMachine, TransicionInvalida, TransicionPipeline,
    TRANSICIONES_VALIDAS, mapear_legacy_estado, MAPEO_LEGACY_ESTADOS,
)


def _lead(estado: EstadoPipeline = EstadoPipeline.COLD) -> LeadDoc:
    return LeadDoc.from_dict({
        "id": "lead_test", "company": "laboratorio", "nombre": "Test",
        "estado_pipeline": estado.value,
    })


# ── Validación de transiciones ───────────────────────────────────────────────
def test_puede_transicionar_directo_y_inverso():
    assert PipelineMachine.puede_transicionar("cold", "queued") is True
    assert PipelineMachine.puede_transicionar("queued", "cold") is True
    assert PipelineMachine.puede_transicionar("cold", "customer") is False


def test_puede_transicionar_acepta_enum_y_string():
    assert PipelineMachine.puede_transicionar(EstadoPipeline.COLD,
                                               EstadoPipeline.QUEUED) is True
    assert PipelineMachine.puede_transicionar("cold", EstadoPipeline.QUEUED) is True
    assert PipelineMachine.puede_transicionar(EstadoPipeline.COLD, "queued") is True


def test_puede_transicionar_falso_si_estado_invalido():
    assert PipelineMachine.puede_transicionar("zombi", "customer") is False
    assert PipelineMachine.puede_transicionar("cold", "zombi") is False


# ── Transición válida ───────────────────────────────────────────────────────
def test_transicion_valida_actualiza_lead_y_devuelve_registro():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.COLD)
    lead, reg = m.transicionar(lead, EstadoPipeline.QUEUED,
                                razon="aprobado para campaña",
                                evento_disparador="manual")
    assert lead.estado_pipeline == "queued"
    assert reg.desde == "cold" and reg.a == "queued"
    assert reg.razon == "aprobado para campaña"
    assert reg.evento_disparador == "manual"
    # Historial pipeline append
    hp = lead.metadatos_extra["historial_pipeline"]
    assert len(hp) == 1 and hp[0]["a"] == "queued"


def test_transicion_invalida_lanza_y_no_modifica_lead():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.COLD)
    with pytest.raises(TransicionInvalida, match="cold → customer"):
        m.transicionar(lead, EstadoPipeline.CUSTOMER, razon="atajo")
    # Estado intacto
    assert lead.estado_pipeline == "cold"
    assert "historial_pipeline" not in lead.metadatos_extra


def test_estado_destino_no_existe():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.COLD)
    with pytest.raises(TransicionInvalida, match="no es un EstadoPipeline válido"):
        m.transicionar(lead, "zombi", razon="x")


def test_estado_actual_invalido_lanza_claro():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.COLD)
    lead.estado_pipeline = "zombi"
    with pytest.raises(TransicionInvalida, match="estado_pipeline inválido"):
        m.transicionar(lead, EstadoPipeline.QUEUED, razon="x")


# ── DO_NOT_CALL ──────────────────────────────────────────────────────────────
def test_do_not_call_desde_cualquier_estado():
    m = PipelineMachine()
    for origen in EstadoPipeline:
        if origen == EstadoPipeline.DO_NOT_CALL: continue
        lead = _lead(origen)
        lead, _ = m.transicionar(lead, EstadoPipeline.DO_NOT_CALL,
                                  razon="cliente pidió no más llamadas")
        assert lead.estado_pipeline == "do_not_call"
        assert lead.do_not_call is True


def test_do_not_call_es_terminal_duro():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.DO_NOT_CALL)
    # Cualquier intento de salir falla.
    for destino in EstadoPipeline:
        if destino == EstadoPipeline.DO_NOT_CALL: continue
        with pytest.raises(TransicionInvalida):
            m.transicionar(lead, destino, razon=f"intento ir a {destino.value}")
    # Sigue en DO_NOT_CALL.
    assert lead.estado_pipeline == "do_not_call"


# ── LOST permite resurrect a COLD ───────────────────────────────────────────
def test_lost_a_cold_para_resurrect_en_nurturing():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.LOST)
    lead, reg = m.transicionar(lead, EstadoPipeline.COLD,
                                razon="campaña de nurturing 6 meses después")
    assert lead.estado_pipeline == "cold"


# ── Historial append-only ───────────────────────────────────────────────────
def test_historial_pipeline_es_append_only():
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.COLD)
    lead, _ = m.transicionar(lead, EstadoPipeline.QUEUED, razon="r1")
    lead, _ = m.transicionar(lead, EstadoPipeline.CONTACTING, razon="r2")
    lead, _ = m.transicionar(lead, EstadoPipeline.CONTACTED, razon="r3")
    hp = lead.metadatos_extra["historial_pipeline"]
    assert len(hp) == 3
    assert [t["a"] for t in hp] == ["queued", "contacting", "contacted"]
    assert [t["desde"] for t in hp] == ["cold", "queued", "contacting"]


# ── Hooks ────────────────────────────────────────────────────────────────────
def test_hooks_se_invocan_con_lead_y_transicion():
    m = PipelineMachine()
    capturados: list[tuple[str, str, str]] = []
    def h(lead, transicion):
        capturados.append((lead.id, transicion.desde, transicion.a))
    m.registrar_hook(h)
    lead = _lead(EstadoPipeline.COLD)
    m.transicionar(lead, EstadoPipeline.QUEUED, razon="x")
    assert capturados == [("lead_test", "cold", "queued")]


def test_hook_que_lanza_excepcion_no_bloquea_transicion(capsys):
    m = PipelineMachine()
    def hook_malo(lead, t): raise RuntimeError("disco lleno")
    def hook_bueno(lead, t): hook_bueno.calls.append(t.a)
    hook_bueno.calls = []
    m.registrar_hook(hook_malo)
    m.registrar_hook(hook_bueno)
    lead = _lead(EstadoPipeline.COLD)
    lead, _ = m.transicionar(lead, EstadoPipeline.QUEUED, razon="x")
    # La transición ocurrió a pesar de la excepción del hook malo.
    assert lead.estado_pipeline == "queued"
    # El hook bueno se invocó después del malo (aislamiento).
    assert hook_bueno.calls == ["queued"]
    # Y vimos el aviso en stderr.
    err = capsys.readouterr().err
    assert "hook" in err.lower() and "disco lleno" in err


def test_quitar_hook():
    m = PipelineMachine()
    def h(lead, t): pass
    m.registrar_hook(h)
    assert m.quitar_hook(h) is True
    assert m.quitar_hook(h) is False     # ya no está


# ── Matriz completa: cada transición permitida y cada inválida cubierta ─────
def test_matriz_completa_de_transiciones_validas():
    """Para cada par (origen, destino) permitido, comprobamos que funciona.
    Para cada par no permitido, comprobamos que lanza."""
    m = PipelineMachine()
    for origen in EstadoPipeline:
        for destino in EstadoPipeline:
            if origen == destino: continue
            lead = _lead(origen)
            permitida = destino in TRANSICIONES_VALIDAS[origen]
            if permitida:
                lead, _ = m.transicionar(lead, destino, razon="matriz")
                assert lead.estado_pipeline == destino.value
            else:
                with pytest.raises(TransicionInvalida):
                    m.transicionar(lead, destino, razon="matriz invalida")


# ── Mapeo legacy → pipeline (versión interna) ───────────────────────────────
def test_mapeo_legacy_estados_completo():
    assert MAPEO_LEGACY_ESTADOS["identificado"] == EstadoPipeline.COLD
    assert MAPEO_LEGACY_ESTADOS["en_contacto"] == EstadoPipeline.CONTACTING
    assert MAPEO_LEGACY_ESTADOS["compromiso_reciproco"] == EstadoPipeline.ENGAGED
    assert MAPEO_LEGACY_ESTADOS["muestra_enviada"] == EstadoPipeline.SAMPLE_SENT
    assert MAPEO_LEGACY_ESTADOS["cliente_activo"] == EstadoPipeline.CUSTOMER
    assert MAPEO_LEGACY_ESTADOS["en_riesgo"] == EstadoPipeline.CUSTOMER
    assert MAPEO_LEGACY_ESTADOS["perdido"] == EstadoPipeline.LOST


def test_mapear_legacy_estado_default_cold_para_desconocido():
    assert mapear_legacy_estado("zombi") == EstadoPipeline.COLD
    assert mapear_legacy_estado("") == EstadoPipeline.COLD


# ── Caso narrativo Lidia (sin hooks aún, eso vendrá en M3-M4) ───────────────
def test_caso_narrativo_lidia_pacto_callback():
    """Iván llama. Conecta con Lidia (no decisor). Pacta callback mañana 10-11h.

    En la máquina pura (sin hooks de M3-M4 todavía):
        COLD → QUEUED (aprobado) → CONTACTING (llamando) → CONTACTED (Lidia, no decisor)
        → QUEUED (callback pactado, próxima acción ts=mañana 10h)
    """
    m = PipelineMachine()
    lead = _lead(EstadoPipeline.COLD)
    lead, _ = m.transicionar(lead, EstadoPipeline.QUEUED, razon="aprobado en cola")
    lead, _ = m.transicionar(lead, EstadoPipeline.CONTACTING,
                              razon="POST outbound CAI", evento_disparador="CA469a")
    lead, _ = m.transicionar(lead, EstadoPipeline.CONTACTED,
                              razon="habló con Lidia (no decisor)",
                              detalle={"persona": "Lidia", "es_decisor": False},
                              evento_disparador="CA469a")
    lead, _ = m.transicionar(lead, EstadoPipeline.QUEUED,
                              razon="callback pactado mañana 10-11h",
                              detalle={"callback_at": "2026-05-28T10:00:00+00:00",
                                       "tolerancia_min": 60},
                              evento_disparador="CA469a")
    assert lead.estado_pipeline == "queued"
    hp = lead.metadatos_extra["historial_pipeline"]
    assert [t["a"] for t in hp] == ["queued", "contacting", "contacted", "queued"]
    # La razón del último estado está en el último registro.
    assert "callback" in hp[-1]["razon"]
