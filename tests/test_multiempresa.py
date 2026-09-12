"""Tests de multi-empresa y aislamiento estricto (Fase 6)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import diario_ops
from core.bus import InMemoryBus
from core.director import Director
from core.knowledge import InMemoryKnowledge
from core.empresa import Empresa, RegistroEmpresas
from departments.prospeccion import ProspeccionDepartment


# ── memoria de conocimiento aislada ─────────────────────────────────────────
def test_knowledge_no_cruza_entre_empresas():
    k = InMemoryKnowledge()
    k.add("laboratorio", "lead", "cliente_b", {"fit": "alta"})
    k.add("demo-soft", "lead", "techcorp", {"fit": "media"})

    assert k.get("laboratorio", "lead", "cliente_b") == {"fit": "alta"}
    assert k.get("laboratorio", "lead", "techcorp") is None          # no ve la otra empresa
    assert list(k.all("demo-soft", "lead").keys()) == ["techcorp"]
    assert "cliente_b" not in k.all("demo-soft", "lead")


def test_knowledge_lista_empresas():
    k = InMemoryKnowledge()
    k.add("laboratorio", "lead", "x", {})
    k.add("demo-soft", "lead", "y", {})
    assert k.companies() == ["demo-soft", "laboratorio"]


# ── bus aislado por empresa ─────────────────────────────────────────────────
def test_bus_aislado_dos_empresas():
    bus = InMemoryBus()
    director = Director(bus, {"prospeccion": ProspeccionDepartment(bus, simulacion=True)})
    director.handle_intent("busca leads gourmet", company="laboratorio")
    director.handle_intent("busca leads de software", company="demo-soft")

    ha = bus.history(company="laboratorio")
    hd = bus.history(company="demo-soft")
    assert ha and hd
    assert all(e.company == "laboratorio" for e in ha)
    assert all(e.company == "demo-soft" for e in hd)
    # plantilla reutilizada (mismo Director/departamento) sin cruce: la orden de una
    # empresa no aparece en el flujo de la otra.
    intents_a = " ".join(e.payload.get("intent", "") for e in ha)
    intents_d = " ".join(e.payload.get("intent", "") for e in hd)
    assert "gourmet" in intents_a and "gourmet" not in intents_d
    assert "software" in intents_d and "software" not in intents_a


# ── registro de empresas ────────────────────────────────────────────────────
def test_registro_alta_y_lista():
    r = RegistroEmpresas()
    r.alta(Empresa("laboratorio", "Laboratorio KAIZEN", "Alimentación"))
    r.alta(Empresa("demo-soft", "Demo Software S.L.", "Software"))
    assert [e.slug for e in r.lista()] == ["demo-soft", "laboratorio"]
    assert r.get("laboratorio").nombre == "Laboratorio KAIZEN"
    assert r.get("inexistente") is None


def test_simulador_genera_leads_contextuales():
    """El simulador detecta el sector del CONTEXTO_NEGOCIO y devuelve leads coherentes."""
    from departments.prospeccion import ProspeccionDepartment
    orig = diario_ops.DIARIO
    with tempfile.TemporaryDirectory() as tmp:
        diario_ops.DIARIO = Path(tmp)
        try:
            for slug, ctx in [("rep", "Repostería artesanal, sector alimentación gourmet."),
                              ("tech", "Empresa de software SaaS y tecnología digital.")]:
                d = Path(tmp) / slug
                d.mkdir(parents=True)
                (d / "CONTEXTO_NEGOCIO.md").write_text(ctx, encoding="utf-8")
            dept = ProspeccionDepartment(InMemoryBus(), simulacion=True)
            r_rep = dept._sim_executor("perfil", "rep")
            r_tech = dept._sim_executor("perfil", "tech")
            r_none = dept._sim_executor("perfil", "sin_contexto")
            assert r_rep.data["sector"] == "alimentacion" and r_rep.data["leads"]
            assert r_tech.data["sector"] == "software" and r_tech.data["leads"]
            assert r_none.data["leads"] == []
        finally:
            diario_ops.DIARIO = orig


def test_diario_aislado_por_empresa():
    """Cada empresa tiene su carpeta diario/<empresa>/; las fichas no cruzan."""
    orig = diario_ops.DIARIO
    with tempfile.TemporaryDirectory() as tmp:
        diario_ops.DIARIO = Path(tmp)
        try:
            diario_ops.write_cliente("lead_a", "datos A", company="laboratorio")
            diario_ops.write_cliente("lead_b", "datos B", company="demo-soft")
            assert diario_ops.list_clientes("laboratorio") == ["lead_a"]
            assert diario_ops.list_clientes("demo-soft") == ["lead_b"]
            assert diario_ops.read_cliente("lead_b", "laboratorio") == ""   # no cruza
            assert diario_ops.read_cliente("lead_a", "laboratorio") == "datos A"
        finally:
            diario_ops.DIARIO = orig


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests OK")
    sys.exit(1 if fallos else 0)
