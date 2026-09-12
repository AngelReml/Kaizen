"""Test de consola segura (canonico 10.3) — Bloque 1.

Nota de precision sobre el canonico: cp1252 SI codifica el simbolo euro
(0x80); el fallo real de la consola Windows es el codepage OEM cp850, que
NO lo codifica. Se simula cp850 estricto: print("...euro...") reventaria;
safe_print no debe reventar y degrada euro a EUR solo en consola.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sustrato.consola import safe_print


def test_euro_no_revienta(monkeypatch):
    crudo = io.BytesIO()
    falso_stdout = io.TextIOWrapper(crudo, encoding="cp850", errors="strict")
    monkeypatch.setattr(sys, "stdout", falso_stdout)
    safe_print("coste del dia: 16€ y con acentos: aprobacion siñor ñ")
    falso_stdout.flush()
    salida = crudo.getvalue().decode("cp850", errors="replace")
    assert "16EUR" in salida            # euro degradado SOLO en consola
    assert "\n" in salida               # se imprimio algo terminado en salto


def test_euro_pasa_intacto_en_utf8(capsys):
    safe_print("limite 16€")
    capturado = capsys.readouterr()
    assert "16€" in capturado.out  # en consola UTF-8 no se degrada
