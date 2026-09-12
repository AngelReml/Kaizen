"""Tests del motor de reintentos (M3)."""
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.lead_schema import LeadDoc
from core.pipeline_state_machine import EstadoPipeline, PipelineMachine
from core.reintentos import MotorReintentos, RecomendacionReintento, _politica_default

TZ_ES = ZoneInfo("Europe/Madrid")


def _lead(categoria: str = "cafeteria_especialidad",
          intentos: int = 0,
          estado_pipeline: str = "contacting") -> LeadDoc:
    return LeadDoc.from_dict({
        "id": "lead_test", "company": "laboratorio",
        "nombre": "Test", "categoria_icp": categoria,
        "anillo": 1, "estado_pipeline": estado_pipeline,
        "reintentos": {"intentos_realizados": intentos, "max_intentos": 5},
    })


def _motor(reloj_local_iso: str = "2026-05-27T11:00:00+02:00",
            seed: int = 42) -> MotorReintentos:
    """Motor con reloj fijo + RNG determinista. `reloj_local_iso` es hora local ES."""
    fijo_utc = datetime.fromisoformat(reloj_local_iso).astimezone(timezone.utc)
    return MotorReintentos(politica_dict=_politica_default(),
                            clock=lambda: fijo_utc,
                            rng=random.Random(seed))


# ── Resultados terminales ────────────────────────────────────────────────────
def test_opt_out_genera_do_not_call():
    m = _motor()
    lead = _lead()
    rec = m.decidir(lead, "opt_out")
    assert rec.transicion_a == "do_not_call"
    assert rec.do_not_call is True
    assert rec.proxima_accion_tipo == "none"


def test_no_interesa_genera_lost():
    m = _motor()
    lead = _lead()
    rec = m.decidir(lead, "no_interesa")
    assert rec.transicion_a == "lost"
    assert rec.proxima_accion_tipo == "none"
    assert "no interés" in rec.razon


# ── Callback pactado (caso Lidia) ───────────────────────────────────────────
def test_callback_pactado_crea_compromiso():
    m = _motor()
    lead = _lead(estado_pipeline="contacted")
    contexto = {
        "callback_ts": "2026-05-28T10:00:00+00:00",
        "contexto": "callback con encargado mañana 10-11h",
        "origen_interaccion_id": "CA469a",
    }
    rec = m.decidir(lead, "callback_pactado", contexto)
    assert rec.transicion_a == "queued"
    assert rec.proxima_accion_tipo == "llamar"
    assert rec.proxima_accion_ts == "2026-05-28T10:00:00+00:00"
    assert rec.compromiso_a_crear is not None
    assert rec.compromiso_a_crear.tipo == "callback"
    assert rec.compromiso_a_crear.fecha_objetivo == "2026-05-28T10:00:00+00:00"
    assert rec.compromiso_a_crear.tolerancia_min == 15
    assert rec.compromiso_a_crear.origen_interaccion_id == "CA469a"
    assert rec.incrementar_intentos is False    # callback no es reintento


def test_callback_sin_fecha_degrada_a_no_buen_momento():
    m = _motor()
    lead = _lead()
    rec = m.decidir(lead, "callback_pactado", {})  # sin callback_ts
    assert rec.transicion_a == "queued"
    assert rec.proxima_accion_tipo == "llamar"
    assert "7 días" in rec.razon


# ── No answer con max_intentos y override por categoría ─────────────────────
def test_no_answer_primer_intento_programa_proximo():
    m = _motor()
    lead = _lead(intentos=0)
    rec = m.decidir(lead, "no_answer")
    assert rec.transicion_a == "queued"
    assert rec.proxima_accion_tipo == "llamar"
    assert rec.proxima_accion_ts is not None
    assert rec.incrementar_intentos is True
    assert "reintento 1/3" in rec.razon


def test_no_answer_alcanza_max_intentos_lost():
    """Política default: max_intentos=3. Si ya hay 3, el 4º intento → LOST."""
    m = _motor()
    lead = _lead(intentos=3)
    rec = m.decidir(lead, "no_answer")
    assert rec.transicion_a == "lost"
    assert rec.proxima_accion_tipo == "none"
    assert "max intentos" in rec.razon


def test_override_por_categoria_hotel_boutique_aumenta_a_5():
    """Política con override: hotel_boutique_con_desayuno tiene max_intentos=5."""
    politica = _politica_default()
    politica["categorias_override"] = {
        "hotel_boutique_con_desayuno": {"no_answer": {"max_intentos": 5}}
    }
    m = MotorReintentos(politica_dict=politica,
                         clock=lambda: datetime(2026, 5, 27, 9, 0, tzinfo=timezone.utc),
                         rng=random.Random(0))
    # Con 3 intentos ya (que en default sería el límite) hotel boutique todavía permite.
    lead = _lead(categoria="hotel_boutique_con_desayuno", intentos=3)
    rec = m.decidir(lead, "no_answer")
    assert rec.transicion_a == "queued"        # no LOST, sigue intentando
    assert "1/5" not in rec.razon and "4/5" in rec.razon


# ── no_buen_momento_sin_fecha y no_interesa_ahora ───────────────────────────
def test_no_buen_momento_sin_fecha_reintento_7_dias():
    m = _motor()
    lead = _lead()
    rec = m.decidir(lead, "no_buen_momento_sin_fecha")
    assert rec.transicion_a == "queued"
    assert rec.proxima_accion_tipo == "llamar"
    # La próxima acción es 7 días después del reloj fijo (lunes 11h ES + 7d = lunes 11h)
    proxima = datetime.fromisoformat(rec.proxima_accion_ts)
    delta_dias = (proxima - datetime(2026, 5, 27, 9, 0, tzinfo=timezone.utc)).days
    assert 6 <= delta_dias <= 8


def test_no_interesa_ahora_nurturing_3_meses():
    m = _motor()
    lead = _lead()
    rec = m.decidir(lead, "no_interesa_ahora")
    assert rec.transicion_a == "queued"
    assert rec.proxima_accion_tipo == "nurturing"
    proxima = datetime.fromisoformat(rec.proxima_accion_ts)
    # 3 meses = ~90 días
    delta_dias = (proxima - datetime(2026, 5, 27, 9, 0, tzinfo=timezone.utc)).days
    assert 80 <= delta_dias <= 100


# ── Resultado desconocido es no-op explícito ─────────────────────────────────
def test_resultado_desconocido_no_op():
    m = _motor()
    lead = _lead()
    rec = m.decidir(lead, "marcianos_llaman")
    assert rec.transicion_a is None
    assert rec.proxima_accion_tipo is None
    assert "desconocido" in rec.razon


# ── Cálculo de franja válida ─────────────────────────────────────────────────
def test_franja_lunes_12h_30_se_mueve_a_16h():
    """Lunes 12:30 ES + 3h = 15:30 → cae fuera de franja → mueve a 16:00."""
    m = _motor(reloj_local_iso="2026-05-25T12:30:00+02:00")  # lunes
    # Forzamos 3h con un RNG que devuelve 3.0
    class _RNG:
        def uniform(self, a, b): return 3.0
    m.rng = _RNG()
    lead = _lead()
    rec = m.decidir(lead, "no_answer")
    proxima = datetime.fromisoformat(rec.proxima_accion_ts).astimezone(TZ_ES)
    assert proxima.hour == 16 and proxima.minute == 0


def test_franja_viernes_18h_se_mueve_a_lunes():
    """Viernes 18:00 ES + 4h = sábado 22h → mueve a lunes 10h."""
    m = _motor(reloj_local_iso="2026-05-29T18:00:00+02:00")  # viernes
    class _RNG:
        def uniform(self, a, b): return 4.0
    m.rng = _RNG()
    lead = _lead()
    rec = m.decidir(lead, "no_answer")
    proxima = datetime.fromisoformat(rec.proxima_accion_ts).astimezone(TZ_ES)
    assert proxima.weekday() == 0  # lunes
    assert proxima.hour == 10


# ── aplicar() ────────────────────────────────────────────────────────────────
def test_aplicar_actualiza_lead_completo():
    m = _motor()
    lead = _lead(estado_pipeline="contacted")
    machine = PipelineMachine()
    rec = m.decidir(lead, "callback_pactado",
                    {"callback_ts": "2026-05-28T10:00:00+00:00",
                     "contexto": "callback Lidia"})
    lead = m.aplicar(lead, rec, machine=machine)
    assert lead.estado_pipeline == "queued"
    assert lead.reintentos.proxima_accion_ts == "2026-05-28T10:00:00+00:00"
    assert lead.reintentos.proxima_accion_tipo == "llamar"
    assert len(lead.compromisos) == 1
    assert lead.compromisos[0].tipo == "callback"


def test_aplicar_opt_out_marca_do_not_call_flag():
    """opt_out es válido desde cualquier estado (DO_NOT_CALL terminal universal)."""
    m = _motor()
    lead = _lead(estado_pipeline="contacted")
    machine = PipelineMachine()
    rec = m.decidir(lead, "opt_out")
    lead = m.aplicar(lead, rec, machine=machine)
    assert lead.do_not_call is True
    assert lead.estado_pipeline == "do_not_call"


def test_aplicar_no_answer_incrementa_intentos():
    """ASUNCIÓN: el SDR ya transicionó contacting→no_answer; el motor lleva a queued."""
    m = _motor()
    lead = _lead(estado_pipeline="no_answer", intentos=1)
    machine = PipelineMachine()
    rec = m.decidir(lead, "no_answer")
    lead = m.aplicar(lead, rec, machine=machine)
    assert lead.reintentos.intentos_realizados == 2
    assert lead.estado_pipeline == "queued"


def test_aplicar_callback_NO_incrementa_intentos():
    """Un callback pactado no es un reintento — es un compromiso."""
    m = _motor()
    lead = _lead(estado_pipeline="contacted", intentos=1)
    machine = PipelineMachine()
    rec = m.decidir(lead, "callback_pactado",
                    {"callback_ts": "2026-05-28T10:00:00+00:00"})
    lead = m.aplicar(lead, rec, machine=machine)
    assert lead.reintentos.intentos_realizados == 1     # sin cambio


def test_aplicar_idempotente_no_duplica_compromiso():
    m = _motor()
    lead = _lead(estado_pipeline="contacted")
    machine = PipelineMachine()
    rec = m.decidir(lead, "callback_pactado",
                    {"callback_ts": "2026-05-28T10:00:00+00:00"})
    m.aplicar(lead, rec, machine=machine)
    # 2ª aplicación: el compromiso ya existe con misma fecha+tipo, no se duplica.
    # (transición pipeline sí podría fallar al re-transicionar; aceptamos
    # idempotencia funcional: la lista de compromisos queda con 1 sola entrada.)
    lead.estado_pipeline = "contacted"           # rebobinamos manualmente
    m.aplicar(lead, rec, machine=None)            # sin machine = sin re-transición
    assert len(lead.compromisos) == 1


# ── Carga desde JSON real (Laboratorio) ──────────────────────────────────────────
def test_carga_politica_desde_json_real(tmp_path):
    politica_json = tmp_path / "p.json"
    politica_json.write_text(json.dumps({
        "version": "test", "default_max_intentos": 7,
        "franjas_horarias_es": ["09-12"],
        "dias_laborables": [0, 1, 2, 3, 4],
        "tz": "Europe/Madrid",
        "reglas": {"no_answer": {"max_intentos": 1, "intervalo_min_horas": 2,
                                  "intervalo_max_horas": 2}},
        "categorias_override": {},
    }), encoding="utf-8")
    m = MotorReintentos(politica_path=politica_json,
                         clock=lambda: datetime(2026, 5, 27, 9, 0, tzinfo=timezone.utc),
                         rng=random.Random(0))
    lead = _lead(intentos=0)
    rec = m.decidir(lead, "no_answer")
    # 2º intento ya pasaría el max=1; pero estamos en 0+1=1 → sigue OK
    assert rec.transicion_a == "queued"
    lead.reintentos.intentos_realizados = 1
    rec2 = m.decidir(lead, "no_answer")
    assert rec2.transicion_a == "lost"
    assert "max intentos alcanzado (1)" in rec2.razon


def test_politica_inexistente_usa_defaults():
    """Si el path no existe y no se pasa politica_dict → defaults razonables."""
    m = MotorReintentos(politica_path=Path("/inexistente/p.json"))
    assert m.politica["default_max_intentos"] == 3
    lead = _lead()
    rec = m.decidir(lead, "opt_out")
    assert rec.transicion_a == "do_not_call"


# ── La política JSON del tenant se carga sin errores ─────────────────────────
def test_politica_del_tenant_es_valida_y_funcional():
    """R-TENANT: la ruta la resuelve `core.rutas`, no se construye a mano contra
    el árbol, y el tenant es el SINTÉTICO, no un cliente real."""
    from core.rutas import dir_empresa
    p = dir_empresa("laboratorio") / "politica_reintentos.json"
    assert p.exists()
    m = MotorReintentos(politica_path=p,
                         clock=lambda: datetime(2026, 5, 27, 9, 0, tzinfo=timezone.utc),
                         rng=random.Random(42))
    lead = _lead(categoria="hotel_boutique_con_desayuno", intentos=0)
    rec = m.decidir(lead, "no_answer")
    assert rec.transicion_a == "queued"
    # Override: hotel boutique tiene max_intentos=5 según el JSON real
    lead.reintentos.intentos_realizados = 4
    rec2 = m.decidir(lead, "no_answer")
    # 4+1=5 → todavía OK (=max). Probemos un 6º
    assert rec2.transicion_a == "queued"
    lead.reintentos.intentos_realizados = 5
    rec3 = m.decidir(lead, "no_answer")
    assert rec3.transicion_a == "lost"
