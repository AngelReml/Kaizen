"""F4 — entregabilidad E3 (herramientas listas hasta la frontera del dominio).

El dominio emisor es decision de Ivan (DR-10); estos tests prueban la MAQUINARIA que no
depende de el: analisis dig SPF/DKIM/DMARC, rampa <=10/dia, dominio-frio=PARAR.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.entregabilidad import (
    analizar_dns, comandos_dig, exigir_dominio_apto, DominioFrio,
    RampaEnvio, RampaAgotada, plan_test_bandeja,
)


def test_comandos_dig_documentados():
    c = comandos_dig("kaizen.example", "s1")
    assert c["spf"] == "dig +short TXT kaizen.example"
    assert c["dmarc"] == "dig +short TXT _dmarc.kaizen.example"
    assert "s1._domainkey.kaizen.example" in c["dkim"]


def test_dns_verde_con_los_tres():
    v = analizar_dns(
        "kaizen.example",
        spf_txt='"v=spf1 include:_spf.google.com -all"',
        dmarc_txt='"v=DMARC1; p=quarantine; rua=mailto:dmarc@kaizen.example"',
        dkim_txt='"v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDlongkeymaterial"')
    assert v.autenticado and not v.dominio_frio
    assert v.dmarc_politica == "quarantine"
    exigir_dominio_apto(v)          # no lanza


def test_dns_frio_para():
    v = analizar_dns("frio.example", spf_txt="", dmarc_txt="", dkim_txt="")
    assert v.dominio_frio and not v.spf_ok and not v.dmarc_ok and not v.dkim_ok
    with pytest.raises(DominioFrio):
        exigir_dominio_apto(v)


def test_dns_spf_permisivo_se_reporta():
    v = analizar_dns("x.example",
                     spf_txt='"v=spf1 include:mailgun.org"',      # sin -all/~all
                     dmarc_txt='"v=DMARC1; p=none"',
                     dkim_txt='"v=DKIM1; p=' + "A" * 40 + '"')
    assert v.spf_ok and any("-all" in p for p in v.problemas)
    assert any("p=none" in p for p in v.problemas)               # DMARC monitor, avisa


def test_rampa_limita_a_diez(tmp_path):
    r = RampaEnvio(tmp_path / "rampa.json", max_dia=10)
    assert r.puede_enviar() and r.restantes_hoy() == 10
    for i in range(10):
        r.registrar_envio()
    assert not r.puede_enviar() and r.restantes_hoy() == 0
    with pytest.raises(RampaAgotada):
        r.registrar_envio()


def test_rampa_contador_corrupto_es_fail_closed(tmp_path):
    p = tmp_path / "rampa.json"
    p.write_text("{basura", encoding="utf-8")
    r = RampaEnvio(p, max_dia=10)
    assert r.restantes_hoy() == 0 and not r.puede_enviar()      # ilegible = cupo agotado


def test_plan_test_bandeja_usa_cuentas_propias():
    plan = plan_test_bandeja("kaizen.example", ["yo@gmail.com", "yo@outlook.com", "malo"])
    assert plan["destinos"] == ["yo@gmail.com", "yo@outlook.com"]
    assert "spam" in plan["si_cae_en_spam"].lower()
