"""Tests del guard de envío del EmailChannel — la barrera arquitectónica del operador.

El requisito: el SDR NO PUEDE enviar nada sin aprobación. Tres barreras independientes.
Estos tests verifican que CADA UNA bloquea por separado y todas a la vez.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge import InMemoryKnowledge
from departments.comercial.cola_aprobacion import (
    ColaAprobacion, EnvioSinAprobacion, hash_mensaje,
)
from departments.comercial.sdr.canales.email import EmailChannel


@pytest.fixture
def cola_y_pendiente():
    k = InMemoryKnowledge()
    cola = ColaAprobacion(k, "laboratorio")
    pendiente = cola.encolar(
        lead_id="lead_x", canal="email", destino="cliente@example.com",
        asunto="Asunto OK", cuerpo="Cuerpo OK", brand_review={"aprobado": True},
        campaign_id="camp_test",
    )
    return cola, pendiente


def test_barrera_1_sin_flag_global(monkeypatch, cola_y_pendiente):
    """Sin KAIZEN_ENVIO_HABILITADO=true, no se envía aunque haya token + hash OK."""
    cola, pendiente = cola_y_pendiente
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "false")
    monkeypatch.setenv("SMTP_HOST", "fake"); monkeypatch.setenv("SMTP_USER", "fake")
    monkeypatch.setenv("SMTP_PASS", "fake")
    cola.aprobar(pendiente.id)
    with pytest.raises(EnvioSinAprobacion, match="KAIZEN_ENVIO_HABILITADO"):
        EmailChannel().enviar_pendiente(cola, pendiente.id)


def test_barrera_2_sin_token_aprobado(monkeypatch, cola_y_pendiente):
    """Aunque KAIZEN_ENVIO_HABILITADO=true, un pendiente en estado 'pendiente' (no aprobado)
    bloquea el envío. La cola.aprobar() es el único camino para generar token."""
    cola, pendiente = cola_y_pendiente
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SMTP_HOST", "fake"); monkeypatch.setenv("SMTP_USER", "fake")
    monkeypatch.setenv("SMTP_PASS", "fake")
    # NO aprobamos → token_aprobacion es None
    with pytest.raises(EnvioSinAprobacion, match="estado"):
        EmailChannel().enviar_pendiente(cola, pendiente.id)


def test_barrera_3_hash_modificado_tras_aprobacion(monkeypatch, cola_y_pendiente):
    """Aprobar A y luego intentar enviar B (asunto/cuerpo modificado) debe bloquearse.
    Es el ataque clásico 'firmaste algo distinto a lo que envío'."""
    cola, pendiente = cola_y_pendiente
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SMTP_HOST", "fake"); monkeypatch.setenv("SMTP_USER", "fake")
    monkeypatch.setenv("SMTP_PASS", "fake")
    nodo = cola.aprobar(pendiente.id)
    # Manipulamos el nodo en Knowledge para simular un cambio post-aprobación.
    nodo["cuerpo"] = "Cuerpo distinto al aprobado"
    cola.k.add(cola.company, "email_pendiente_aprobacion", pendiente.id, nodo)
    # enviar_pendiente recomputa el hash del cuerpo actual; no coincide con el aprobado.
    with pytest.raises(EnvioSinAprobacion, match="hash"):
        EmailChannel().enviar_pendiente(cola, pendiente.id)


def test_barrera_2_token_invalido(monkeypatch, cola_y_pendiente):
    """Un token inventado no debe pasar verificar_token aunque exista el pendiente."""
    cola, pendiente = cola_y_pendiente
    cola.aprobar(pendiente.id)
    with pytest.raises(EnvioSinAprobacion, match="[Tt]oken"):
        cola.verificar_token(pendiente_id=pendiente.id, token="token_inventado",
                             hash_a_enviar=hash_mensaje("email", "cliente@example.com",
                                                        "Asunto OK", "Cuerpo OK"))


def test_contactar_directo_sin_aprobacion_lanza(monkeypatch):
    """Llamar a EmailChannel.contactar() sin pasar el dict `aprobacion` siempre falla."""
    with pytest.raises(EnvioSinAprobacion, match="aprobacion"):
        EmailChannel().contactar(destino="x@y.com", asunto="A", cuerpo="B")


def test_envio_correcto_con_las_cinco_barreras_satisfechas(monkeypatch, cola_y_pendiente):
    """Camino feliz post-2026-08-02: flag + token + hash + TTL + transparencia AI Act.
    Desde la entrada en vigor del art. 50, el camino feliz EXIGE que el cuerpo se
    identifique como IA — un 'happy path' sin disclosure ya no es feliz: es ilegal."""
    cola, _ = cola_y_pendiente
    cuerpo_legal = ("Cuerpo OK\n\nMensaje generado por un sistema automatizado y "
                    "revisado por un humano antes del envío.")
    pendiente = cola.encolar(
        lead_id="lead_y", canal="email", destino="cliente@example.com",
        asunto="Asunto OK", cuerpo=cuerpo_legal, brand_review={"aprobado": True},
        campaign_id="camp_test",
    )
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SMTP_HOST", "fake"); monkeypatch.setenv("SMTP_USER", "fake")
    monkeypatch.setenv("SMTP_PASS", "fake")
    cola.aprobar(pendiente.id)
    # Mock smtp_send para no enviar nada real.
    enviados = []
    import agentes
    monkeypatch.setattr(agentes, "smtp_send", lambda to, a, c: enviados.append((to, a, c)))
    resultado = EmailChannel().enviar_pendiente(cola, pendiente.id)
    assert resultado.estado == "enviado"
    assert enviados == [("cliente@example.com", "Asunto OK", cuerpo_legal)]
    # Estado del pendiente actualizado.
    assert cola.get(pendiente.id)["estado"] == "enviado"


def test_barrera_5_aiact_bloquea_cuerpo_sin_transparencia(monkeypatch, cola_y_pendiente):
    """Las cuatro primeras barreras satisfechas, pero el cuerpo no se identifica como
    IA → el candado del art. 50 bloquea el envío y el claim se revierte (reintentable)."""
    from core.aiact_gate import AIActSinTransparencia
    cola, pendiente = cola_y_pendiente      # cuerpo "Cuerpo OK": sin disclosure
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SMTP_HOST", "fake"); monkeypatch.setenv("SMTP_USER", "fake")
    monkeypatch.setenv("SMTP_PASS", "fake")
    cola.aprobar(pendiente.id)
    enviados = []
    import agentes
    monkeypatch.setattr(agentes, "smtp_send", lambda to, a, c: enviados.append((to, a, c)))
    with pytest.raises(AIActSinTransparencia):
        EmailChannel().enviar_pendiente(cola, pendiente.id)
    assert enviados == []                                   # nada salió
    assert cola.get(pendiente.id)["estado"] == "aprobado"   # claim revertido


def test_pendiente_rechazado_no_puede_aprobarse_ni_enviarse(monkeypatch, cola_y_pendiente):
    cola, pendiente = cola_y_pendiente
    cola.rechazar(pendiente.id, motivo="tono no es Iván")
    with pytest.raises(ValueError):
        cola.aprobar(pendiente.id)
    monkeypatch.setenv("KAIZEN_ENVIO_HABILITADO", "true")
    monkeypatch.setenv("SMTP_HOST", "fake"); monkeypatch.setenv("SMTP_USER", "fake")
    monkeypatch.setenv("SMTP_PASS", "fake")
    with pytest.raises(EnvioSinAprobacion):
        EmailChannel().enviar_pendiente(cola, pendiente.id)
