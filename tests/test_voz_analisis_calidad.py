"""Tests del pipeline AnalisisCalidadLlamada (4 criterios + puntuación)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from departments.comercial.brand_guardian import BrandGuardian
from departments.comercial.sdr.compromiso import CompromisoDetector
from departments.comercial.sdr.voz_conversacional.analisis_calidad import (
    AnalisisCalidadLlamada, DictamenCalidad, DictamenObjecion, _puntuacion,
    _silencios_largos_s,
)


CTX = """## Contacto comercial (remitente)
- **Nombre:** Iván Carbonell
- **Empresa:** Repostería Laboratorio (Cieza)
"""


def _chat_secuencial(respuestas):
    """Cada llamada devuelve la siguiente respuesta en orden."""
    it = iter(respuestas)
    def _c(messages, system=None, **kw): return next(it)
    return _c


def _analizador(respuestas_llm):
    """AnalisisCalidadLlamada con chat mockeado para los 3 LLM calls que hace:
    compromiso, tono, objeciones+mejoras."""
    chat = _chat_secuencial(respuestas_llm)
    bg = BrandGuardian(empresa="laboratorio", contexto_negocio=CTX, chat=chat)
    cd = CompromisoDetector(chat=chat)
    return AnalisisCalidadLlamada(chat=chat, brand_guardian=bg, compromiso=cd)


def _transcript_basico():
    return [
        {"hablante": "agente", "ts": 0.0, "texto": "Hola buenos días, le habla Iván de Laboratorio."},
        {"hablante": "cliente", "ts": 5.0, "texto": "Sí dígame, ¿qué quería?"},
        {"hablante": "agente", "ts": 6.0, "texto": "Le llamo por si encajamos como proveedor."},
        {"hablante": "cliente", "ts": 9.0, "texto": "Pues mire, tengo un evento la semana que viene."},
        {"hablante": "agente", "ts": 11.0, "texto": "Excelente, le mando muestra entonces."},
    ]


# ── Pipeline completo ───────────────────────────────────────────────────────
def test_analiza_compromiso_tono_objeciones_y_mejoras():
    transcript = _transcript_basico()
    respuestas = [
        # 1) CompromisoDetector
        '{"es_compromiso": true, "confianza": 0.85, '
        '"senales_detectadas": ["evento próximo"], '
        '"motivo": "menciona evento", "recomendacion": "escalar_account_executive"}',
        # 2) BrandGuardian.analizar_tono_conversacional
        '{"ok": true, "problemas": [], "sugerencias": ["dar más pausas"]}',
        # 3) Objeciones + mejoras
        '{"objeciones": [], "mejoras_generales": ["preguntar más por preferencias del cliente"]}',
    ]
    an = _analizador(respuestas)
    dictamen = an.analizar(transcript=transcript, call_sid="CA1",
                            lead={"id": "x", "nombre": "X"}, duracion_s=60.0)
    assert isinstance(dictamen, DictamenCalidad)
    assert dictamen.compromiso.es_compromiso is True
    assert dictamen.tono.ok is True
    assert dictamen.objeciones == []
    assert "pausas" in dictamen.tono.sugerencias[0] or "preguntar" in dictamen.mejoras[0]
    # Compromiso (4) + tono (2) + sin obj no abord (2) + turnos balanceados (1) + sin silencios (1) = 10
    assert dictamen.puntuacion_global == 10


def test_puntuacion_baja_sin_compromiso_y_tono_malo():
    transcript = _transcript_basico()
    respuestas = [
        '{"es_compromiso": false, "confianza": 0.1, "senales_detectadas": [], '
        '"motivo": "cortesía", "recomendacion": "descartar"}',
        '{"ok": false, "problemas": ["sonó a IA"], "sugerencias": []}',
        '{"objeciones": [{"frase_cliente": "no me interesa", "abordada": false, '
        '"motivo": "agente insistió", "sugerencia": "aceptar el no"}], "mejoras_generales": []}',
    ]
    an = _analizador(respuestas)
    d = an.analizar(transcript=transcript, call_sid="CA2",
                    lead={"id": "y"}, duracion_s=60.0)
    # 0 (sin compromiso) + 0 (tono malo) + 0 (objeción no abordada) + 1 (turnos) + 1 (silencios) = 2
    assert d.puntuacion_global == 2
    assert d.tono.ok is False
    assert len(d.objeciones) == 1 and not d.objeciones[0].abordada


def test_cuenta_turnos_correctamente():
    transcript = _transcript_basico()
    respuestas = [
        '{"es_compromiso": false, "confianza": 0.3, "senales_detectadas": [], "motivo": "x", "recomendacion": "nurturing"}',
        '{"ok": true, "problemas": [], "sugerencias": []}',
        '{"objeciones": [], "mejoras_generales": []}',
    ]
    d = _analizador(respuestas).analizar(transcript=transcript, call_sid="CA3",
                                          lead={"id": "z"}, duracion_s=15.0)
    assert d.turnos_agente == 3
    assert d.turnos_cliente == 2


# ── Helpers internos ────────────────────────────────────────────────────────
def test_puntuacion_acota_a_10():
    """Aunque los puntos sumen más, no pasa de 10."""
    from departments.comercial.sdr.compromiso import DecisionCompromiso
    from departments.comercial.sdr.voz_conversacional.analisis_calidad import DictamenTono
    comp = DecisionCompromiso(es_compromiso=True, confianza=0.9)
    tono = DictamenTono(ok=True)
    assert _puntuacion(compromiso=comp, tono=tono, objeciones=[],
                       turnos_agente=2, turnos_cliente=3, silencios_s=1) == 10


def test_silencios_largos_suma_pausas_sobre_umbral():
    transcript = [
        {"hablante": "agente", "ts": 0.0, "texto": "..."},
        {"hablante": "cliente", "ts": 10.0, "texto": "..."},   # gap 10s
        {"hablante": "agente", "ts": 11.0, "texto": "..."},    # gap 1s (no cuenta)
    ]
    silencios = _silencios_largos_s(transcript, umbral_s=3.0)
    # gap 10s exceds umbral por 7s; gap 1s no cuenta
    assert abs(silencios - 7.0) < 0.01


def test_transcript_vacio_devuelve_objeciones_vacias():
    respuestas = [
        '{"es_compromiso": false, "confianza": 0.0, "senales_detectadas": [], "motivo":"vacío","recomendacion":"descartar"}',
        '{"ok": false, "problemas": ["vacío"], "sugerencias": []}',
        # Tercera respuesta no se llama si transcript está vacío
    ]
    an = _analizador(respuestas)
    d = an.analizar(transcript=[], call_sid="CA0", lead=None, duracion_s=0)
    assert d.objeciones == []
    assert d.mejoras == []
