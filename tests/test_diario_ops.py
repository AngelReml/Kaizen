"""Tests de diario_ops, en particular _extraer_identidad_remitente (PASO 9, criterio 6)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import diario_ops

CTX = """# Contexto del Negocio

## Contacto comercial (remitente)
- **Nombre:** Iván Carbonell
- **Cargo:** Director comercial
- **Empresa:** Repostería de Prueba (Localidad)
- **Teléfono:** 600 000 000
- **Email:** persona@ejemplo.com *(provisional)*
"""


def test_extraer_identidad_completa():
    r = diario_ops._extraer_identidad_remitente(CTX)
    assert r["nombre"] == "Iván Carbonell"
    assert r["cargo"] == "Director comercial"
    assert r["telefono"] == "600 000 000"
    assert r["email"] == "persona@ejemplo.com"


def test_extraer_identidad_ausente_devuelve_cadenas_vacias():
    r = diario_ops._extraer_identidad_remitente("# Contexto sin sección de remitente")
    assert set(r) == {"nombre", "cargo", "empresa", "telefono", "email"}
    assert all(v == "" for v in r.values())     # nunca None, nunca inventado
    assert all(v is not None for v in r.values())


def test_read_no_crea_directorios():
    import tempfile
    orig = diario_ops.DIARIO
    with tempfile.TemporaryDirectory() as tmp:
        diario_ops.DIARIO = Path(tmp)
        try:
            diario_ops.read("CONTEXTO_NEGOCIO", "empresa_inexistente")
            assert not (Path(tmp) / "empresa_inexistente").exists()   # leer no crea carpetas
        finally:
            diario_ops.DIARIO = orig


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1; print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
