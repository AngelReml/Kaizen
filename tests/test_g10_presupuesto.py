"""Regresion del patron comprobar-y-luego-gastar, en los TRES sitios donde estaba
(auditoria 2026-08-02: B-03, C-12 y G-10 son el mismo fallo con tres almacenes).

El fallo: se comprobaba el techo, se hacia la llamada y se apuntaba el gasto
DESPUES, protegido solo por un `threading.Lock`. Entre proceso y proceso eso no
protege nada: los dos leen el mismo total, los dos deciden que cabe y los dos
gastan. El arreglo es el mismo en los tres: RESERVAR en el mismo acto atomico en
que se comprueba, y liquidar o liberar al terminar.

Cada test lanza N hilos compitiendo por un techo que solo admite M < N.
"""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.bloqueo import BloqueoNoDisponible, bloqueo_exclusivo


def _competir(n_hilos, intento):
    """Lanza n_hilos simultaneos (barrera) y devuelve (concedidos, rechazados)."""
    concedidos, rechazados = [], []
    barrera = threading.Barrier(n_hilos)

    def corre(i):
        barrera.wait()
        try:
            concedidos.append(intento())
        except Exception as exc:                    # noqa: BLE001
            rechazados.append(type(exc).__name__)

    hilos = [threading.Thread(target=corre, args=(i,)) for i in range(n_hilos)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return concedidos, rechazados


# ─────────────────────────────────────────── el candado entre procesos
def test_bloqueo_serializa_el_ciclo_leer_decidir_escribir(tmp_path):
    contador = tmp_path / "n.json"
    contador.write_text(json.dumps({"n": 0}), encoding="utf-8")

    def incrementa():
        for _ in range(50):
            with bloqueo_exclusivo(contador):
                n = json.loads(contador.read_text(encoding="utf-8"))["n"]
                contador.write_text(json.dumps({"n": n + 1}), encoding="utf-8")

    hilos = [threading.Thread(target=incrementa) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert json.loads(contador.read_text(encoding="utf-8"))["n"] == 200


def test_bloqueo_falla_en_vez_de_esperar_para_siempre(tmp_path):
    objetivo = tmp_path / "x.json"
    with bloqueo_exclusivo(objetivo):
        soltado = threading.Event()

        def otro():
            try:
                with bloqueo_exclusivo(objetivo, timeout_s=0.2):
                    pass
            except BloqueoNoDisponible:
                soltado.set()

        h = threading.Thread(target=otro)
        h.start()
        h.join(timeout=5)
    assert soltado.is_set(), "el segundo debia rendirse, no colgarse"


# ─────────────────────────────────────────── C-12 · quota diaria de llamadas
def test_c12_la_quota_de_voz_no_se_pasa_con_reservas_concurrentes(tmp_path, monkeypatch):
    monkeypatch.setenv("KAIZEN_VOZ_QUOTA_DIR", str(tmp_path))
    monkeypatch.setenv("KAIZEN_VOZ_MAX_LLAMADAS_DIA", "5")
    from departments.comercial.sdr.voz_conversacional import pre_flight as pf

    concedidos, rechazados = _competir(12, pf.reservar_llamada)
    assert len(concedidos) == 5
    assert len(rechazados) == 7
    assert sorted(concedidos) == [1, 2, 3, 4, 5]        # sin numeros repetidos
    assert pf.llamadas_hoy() == 5


def test_c12_liberar_devuelve_el_hueco(tmp_path, monkeypatch):
    monkeypatch.setenv("KAIZEN_VOZ_QUOTA_DIR", str(tmp_path))
    monkeypatch.setenv("KAIZEN_VOZ_MAX_LLAMADAS_DIA", "1")
    from departments.comercial.sdr.voz_conversacional import pre_flight as pf

    assert pf.reservar_llamada() == 1
    with pytest.raises(pf.QuotaAgotada):
        pf.reservar_llamada()
    pf.liberar_llamada()                                # la llamada no salio
    assert pf.reservar_llamada() == 1                   # el hueco vuelve a estar libre


def test_c12_contador_corrupto_no_se_incrementa(tmp_path, monkeypatch):
    """Antes: lectura corrupta devolvia el maximo y se escribia maximo+1, dejando
    el contador permanentemente por encima del techo."""
    monkeypatch.setenv("KAIZEN_VOZ_QUOTA_DIR", str(tmp_path))
    monkeypatch.setenv("KAIZEN_VOZ_MAX_LLAMADAS_DIA", "25")
    from departments.comercial.sdr.voz_conversacional import pre_flight as pf

    ruta = pf._quota_path()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("{esto no es json", encoding="utf-8")

    assert pf.llamadas_hoy() == 25                      # lectura tolerante: agotado
    with pytest.raises(pf.QuotaCorrupta):
        pf.reservar_llamada()
    assert ruta.read_text(encoding="utf-8") == "{esto no es json"   # intacto


# ─────────────────────────────────────────── B-03 · contabilidad de claude_client
def test_b03_el_techo_diario_no_se_pasa_con_reservas_concurrentes(tmp_path, monkeypatch):
    import claude_client as ai

    monkeypatch.setattr(ai, "COST_FILE", tmp_path / ".kaizen_cost.json")
    monkeypatch.setattr(ai, "DAILY_BUDGET_EUR", 1.0)
    por_llamada_usd = 0.20 / ai.EUR_PER_USD              # 0.20 EUR -> caben 5

    concedidos, rechazados = _competir(10, lambda: ai._reservar(por_llamada_usd))
    assert len(concedidos) == 5
    assert len(rechazados) == 5
    # `abs=1e-4`: el estado se guarda redondeado a 6 decimales de USD, asi que 5
    # reservas acumulan una diferencia de redondeo muy por debajo del centimo.
    reservado_eur = ai._leer_estado()["reservado"] * ai.EUR_PER_USD
    assert reservado_eur == pytest.approx(1.0, abs=1e-4)
    assert reservado_eur <= 1.0                          # nunca por encima del techo


def test_b03_liquidar_por_debajo_de_lo_estimado_devuelve_presupuesto(tmp_path, monkeypatch):
    import claude_client as ai

    monkeypatch.setattr(ai, "COST_FILE", tmp_path / ".kaizen_cost.json")
    monkeypatch.setattr(ai, "DAILY_BUDGET_EUR", 10.0)
    reservado = ai._reservar(1.0)
    assert ai._load_daily() == pytest.approx(1.0)
    ai._liquidar(reservado, 0.25)                        # costo menos de lo estimado
    assert ai._load_daily() == pytest.approx(0.25)


def test_b03_liberar_deja_el_gasto_a_cero(tmp_path, monkeypatch):
    import claude_client as ai

    monkeypatch.setattr(ai, "COST_FILE", tmp_path / ".kaizen_cost.json")
    monkeypatch.setattr(ai, "DAILY_BUDGET_EUR", 10.0)
    reservado = ai._reservar(1.0)
    ai._liberar(reservado)                               # la llamada no se hizo
    assert ai._load_daily() == pytest.approx(0.0)


def test_b03_modelo_sin_tarifa_se_presume_caro(monkeypatch):
    """Presuponer barato hacia que el techo no viese el gasto real (B-01)."""
    import claude_client as ai

    caro = ai.estimar_usd("modelo-que-no-existe", [{"content": "x" * 4000}], None, 1000)
    haiku = ai.estimar_usd("claude-haiku-4-5", [{"content": "x" * 4000}], None, 1000)
    assert caro > haiku


# ─────────────────────────────────────────── G-10 · coste del sustrato
def _bd_con_limite(tmp_path, limite_eur):
    from sustrato import bus, coste, gates
    conn = bus.conexion(tmp_path / "coste.db")
    bus.instalar(conn); coste.instalar(conn); gates.instalar(conn)
    gates.set_limite_coste(conn, limite_eur)
    return conn


def test_g10_reservas_concurrentes_no_pasan_del_limite(tmp_path):
    from sustrato import bus, coste

    ruta = tmp_path / "coste.db"
    _bd_con_limite(tmp_path, 1.0).close()

    def intento():
        conn = bus.conexion(ruta)
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            return coste.reservar(conn, 0.2)
        finally:
            conn.close()

    concedidos, rechazados = _competir(10, intento)
    assert len(concedidos) == 5
    assert rechazados == ["LimiteCosteSuperado"] * 5
    conn = bus.conexion(ruta)
    assert coste.comprobar_limite(conn) == pytest.approx(1.0)


def test_g10_liquidar_y_liberar_ajustan_el_gasto(tmp_path):
    from sustrato import coste

    conn = _bd_con_limite(tmp_path, 10.0)
    r1 = coste.reservar(conn, 0.5)
    r2 = coste.reservar(conn, 0.5)
    assert coste.comprobar_limite(conn) == pytest.approx(1.0)
    assert len(coste.reservas_abiertas(conn)) == 2

    coste.liquidar(conn, r1, 0.1)                        # costo menos
    assert coste.comprobar_limite(conn) == pytest.approx(0.6)
    coste.liberar(conn, r2)                              # no se gasto
    assert coste.comprobar_limite(conn) == pytest.approx(0.1)
    assert coste.reservas_abiertas(conn) == []


def test_g10_la_reserva_cuenta_contra_el_techo_desde_ya(tmp_path):
    """Si lo reservado no contase, dos procesos se autorizarian el mismo hueco."""
    from sustrato import coste

    conn = _bd_con_limite(tmp_path, 1.0)
    coste.reservar(conn, 0.9)
    with pytest.raises(coste.LimiteCosteSuperado):
        coste.reservar(conn, 0.2)


def test_g10_la_estimacion_del_comite_depende_del_tamano(tmp_path):
    """Antes eran 0.02 EUR fijos, mirase el contexto lo que mirase."""
    from sustrato import comite

    pequeno = comite.estimar_eur("sys", "hola", 200)
    grande = comite.estimar_eur("sys", "x" * 200_000, 200)
    assert grande > pequeno * 10


def test_g10_migracion_aditiva_sobre_bd_sin_columna_estado(tmp_path):
    from sustrato import bus, coste

    conn = bus.conexion(tmp_path / "vieja.db")
    conn.executescript("""
        CREATE TABLE costes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, proveedor TEXT NOT NULL,
          concepto TEXT NOT NULL, unidades REAL NOT NULL, coste_eur REAL NOT NULL,
          cubo TEXT NOT NULL DEFAULT 'comercial');
    """)
    conn.commit()
    bus.instalar(conn); coste.instalar(conn)             # no debe reventar
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(costes)").fetchall()}
    assert "estado" in columnas
