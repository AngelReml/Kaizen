"""Operaciones de lectura/escritura del Diario, por empresa. Archivos Markdown locales.

Estructura:  diario/<empresa>/{CONTEXTO_NEGOCIO,ESTADO_ACTUAL,DECISIONES,ULTIMOS_MOVIMIENTOS}.md
             diario/<empresa>/clientes/<lead>.md

El aislamiento entre empresas es por carpeta: nada cruza salvo que se pida otra empresa.
Todas las funciones aceptan `company` (por defecto, la empresa principal).
"""
import re
from datetime import datetime
from pathlib import Path

# R-TENANT: `None` = resolver contra la raiz de datos en cada llamada. Se deja
# como atributo de modulo porque los tests lo sustituyen por un tmpdir.
ROOT = Path(__file__).parent
DIARIO = None
DEFAULT_COMPANY = "laboratorio"

# Archivos protegidos: solo se modifican por orden explícita del usuario
PROTECTED = {"CONTEXTO_NEGOCIO", "DECISIONES"}


def _dir(company: str) -> Path:
    if DIARIO is not None:                      # los tests lo sustituyen por un tmpdir
        return DIARIO / company
    from core.rutas import dir_diario_empresa
    return dir_diario_empresa(company)          # NO crea: leer no debe crear carpetas


def _clientes_dir(company: str) -> Path:
    return _dir(company) / "clientes"        # NO crea


def _path(name: str, company: str) -> Path:
    return _dir(company) / f"{name}.md"


def read(name: str, company: str = DEFAULT_COMPANY) -> str:
    p = _path(name, company)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write(name: str, content: str, company: str = DEFAULT_COMPANY) -> None:
    if name in PROTECTED:
        raise RuntimeError(
            f"'{name}.md' es un archivo protegido. "
            "Solo se edita por orden explícita del usuario, nunca por un agente."
        )
    p = _path(name, company)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def append_decision(entry: str, company: str = DEFAULT_COMPANY) -> None:
    """Añade una entrada cronológica a DECISIONES.md (acumulativo, nunca se reescribe)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    p = _path("DECISIONES", company)
    p.parent.mkdir(parents=True, exist_ok=True)
    current = p.read_text(encoding="utf-8") if p.exists() else ""
    p.write_text(current + f"\n\n---\n**{ts}**\n{entry}", encoding="utf-8")


def append_movimiento(entry: str, company: str = DEFAULT_COMPANY) -> None:
    """Añade una miga de pan a ULTIMOS_MOVIMIENTOS.md."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    current = read("ULTIMOS_MOVIMIENTOS", company)
    write("ULTIMOS_MOVIMIENTOS", current + f"\n\n---\n*{ts}*\n{entry}", company)


def read_cliente(nombre: str, company: str = DEFAULT_COMPANY) -> str:
    p = _clientes_dir(company) / f"{nombre}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_cliente(nombre: str, content: str, company: str = DEFAULT_COMPANY) -> None:
    d = _clientes_dir(company)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{nombre}.md").write_text(content, encoding="utf-8")


def list_clientes(company: str = DEFAULT_COMPANY) -> list[str]:
    d = _clientes_dir(company)
    return sorted(p.stem for p in d.glob("*.md")) if d.exists() else []


def _extraer_identidad_remitente(texto_contexto: str) -> dict:
    """Lee la sección 'Contacto comercial (remitente)' del CONTEXTO_NEGOCIO y devuelve
    {nombre, cargo, empresa, telefono, email}. Claves ausentes -> cadena vacía (nunca None
    ni valores inventados)."""
    def _campo(*etiquetas: str) -> str:
        for et in etiquetas:
            m = re.search(rf"\*\*{et}:?\*\*\s*([^\n*]+)", texto_contexto or "", re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""
    return {
        "nombre": _campo("Nombre"),
        "cargo": _campo("Cargo"),
        "empresa": _campo("Empresa"),
        "telefono": _campo("Teléfono", "Telefono"),
        "email": _campo("Email", "Correo"),
    }


def export_context(company: str = DEFAULT_COMPANY) -> str:
    """Genera el bloque de arranque para pegar al inicio de una sesión de Claude."""
    estado = read("ESTADO_ACTUAL", company)
    movimientos = read("ULTIMOS_MOVIMIENTOS", company)
    return (
        f"PROYECTO KAIZEN — Sesión activa. Empresa: {company}.\n\n"
        "=== ESTADO ACTUAL ===\n"
        f"{estado}\n\n"
        "=== ÚLTIMOS MOVIMIENTOS ===\n"
        f"{movimientos}"
    )
