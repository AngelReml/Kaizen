# -*- coding: utf-8 -*-
"""core/apuestas.py: dosier, vetos, novedad, cuotas y maquina de estados (A1 del plan)."""
import copy
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core import apuestas as A
from core.knowledge import InMemoryKnowledge, JsonKnowledge
from core.rue import Bitacora

T = "t1"


# ── fixtures ────────────────────────────────────────────────────────────────

def coords(**kw):
    base = {"modelo_ingreso": "servicio_por_encargo", "cliente": "pyme", "canal": "contacto_directo",
            "mercado": "es_ES", "coste_inicial": "0", "tiempo_senal": "<=7d",
            "sector": "gestorias de barrio"}
    base.update(kw)
    return base


def borrador(**kw):
    base = {"titulo": "Recordatorios de plazos fiscales para autonomos",
            "problema": "Los autonomos olvidan fechas de impuestos y pagan recargos evitables.",
            "publico": "Autonomos de servicios sin gestor dedicado",
            "por_que_ahora": "Nuevas obligaciones de facturacion electronica este ano"}
    base.update(kw)
    return base


def dosier(**kw):
    base = {
        "nicho": {"problema": "Los autonomos olvidan fechas de impuestos", "publico": "Autonomos de servicios",
                  "por_que_ahora": "Nuevas obligaciones de facturacion"},
        "evidencia": [
            {"afirmacion": "Hay recargos por presentar fuera de plazo", "etiqueta": "RECORDADA"},
            {"afirmacion": "Existen calendarios fiscales oficiales", "etiqueta": "VERIFICADA",
             "fuente": {"url": "https://ejemplo.org/calendario", "fecha": "2026-10-01",
                        "extracto": "Calendario del contribuyente con las fechas limite"}},
        ],
        "coste": {"importe_eur": 0, "concepto": "ninguno", "alternativa_gratuita": "Hoja compartida con avisos"},
        "senal": {"que_se_mide": "Autonomos que piden el aviso gratis", "umbral": 10, "comparador": ">=",
                  "plazo_dias": 14, "fuente_dato": "Respuestas recibidas al mensaje de prueba"},
        "capacidades": {"necesarias": ["generar texto"], "tiene": ["generar texto"], "faltan": []},
        "necesita_del_operador": ["Publicar el mensaje en un grupo de autonomos"],
        "senal_real": {"que_personas": "Autonomos del grupo", "como_se_obtiene": "Cuantos responden pidiendo el aviso"},
        "primer_paso_gratuito": "Preguntar en un grupo si pagarian por recibir avisos",
        "riesgo_legal": {"nivel": "bajo", "por_que": "No se tratan datos sensibles"},
    }
    base.update(kw)
    return base


@pytest.fixture()
def ap():
    k = InMemoryKnowledge()
    b = Bitacora(k, T, fecha_alta="2026-07-10")
    reloj = {"t": datetime(2026, 10, 1, 12, tzinfo=timezone.utc)}
    a = A.Apuestas(k, T, bitacora=b, reloj=lambda: reloj["t"])
    a._reloj_mut = reloj
    return a, k, b


def _a_dosier(a, **kw):
    r = a.crear_borrador(borrador(**kw.get("b", {})), coords(**kw.get("c", {})))
    return a.completar_dosier(r["id"], dosier())


def _unico(i: int) -> str:
    """Palabra unica y estable por indice (las cifras sueltas no cuentan como palabras)."""
    return "zeta" + "".join("abcdefghij"[int(c)] for c in str(i)) + "omega"


def _palabras_unicas(u: str, campo: str) -> str:
    """Seis palabras que no comparte ningun otro texto de prueba."""
    return " ".join(f"{u}{campo}{c}" for c in "abcdef")


def _eventos(k):
    return [(e["tipo"], e["payload"]) for e in k.all(T, "evento").values()]


# ── dosier: limpieza y validacion ───────────────────────────────────────────

def test_dosier_valido_no_tiene_errores():
    assert A.validar_dosier(A.limpiar_dosier(dosier())) == []


@pytest.mark.parametrize("ruta,valor,fragmento", [
    (("nicho", "problema"), "corto", "nicho.problema"),
    (("coste", "alternativa_gratuita"), "", "alternativa_gratuita"),
    (("coste", "importe_eur"), -1, "importe_eur"),
    (("coste", "importe_eur"), "12", "importe_eur"),
    (("coste", "importe_eur"), float("nan"), "importe_eur"),
    (("coste", "importe_eur"), float("inf"), "importe_eur"),
    (("coste", "importe_eur"), True, "importe_eur"),
    (("senal", "umbral"), None, "umbral"),
    (("senal", "comparador"), "=", "comparador"),
    (("senal", "plazo_dias"), 0, "plazo_dias"),
    (("senal", "plazo_dias"), 181, "plazo_dias"),
    (("senal", "plazo_dias"), 14.5, "plazo_dias"),
    (("senal", "fuente_dato"), "", "fuente_dato"),
    (("capacidades", "necesarias"), [], "capacidades.necesarias"),
    (("senal_real", "como_se_obtiene"), "", "senal_real"),
    (("riesgo_legal", "nivel"), "nulo", "riesgo_legal"),
])
def test_cada_campo_obligatorio_se_exige(ruta, valor, fragmento):
    d = dosier()
    d[ruta[0]][ruta[1]] = valor
    errores = A.validar_dosier(A.limpiar_dosier(d))
    assert any(fragmento in e for e in errores), errores


@pytest.mark.parametrize("campo", ["necesita_del_operador", "primer_paso_gratuito"])
def test_campos_de_primer_nivel_obligatorios(campo):
    d = dosier()
    d[campo] = [] if campo == "necesita_del_operador" else ""
    assert any(campo in e for e in A.validar_dosier(A.limpiar_dosier(d)))


def test_evidencia_minimo_dos_y_etiquetas_validas():
    d = dosier()
    d["evidencia"] = d["evidencia"][:1]
    assert any("minimo 2" in e for e in A.validar_dosier(A.limpiar_dosier(d)))
    d = dosier()
    d["evidencia"][0]["etiqueta"] = "CIERTA"
    assert any("etiqueta" in e for e in A.validar_dosier(A.limpiar_dosier(d)))


@pytest.mark.parametrize("fuente", [
    None, {}, {"url": "javascript:alert(1)", "fecha": "2026-10-01", "extracto": "x" * 20},
    {"url": "ftp://x.org/a", "fecha": "2026-10-01", "extracto": "x" * 20},
    {"url": "https://x.org/a", "fecha": "ayer", "extracto": "x" * 20},
    {"url": "https://x.org/a", "fecha": "2026-10-01", "extracto": "corto"},
    {"url": "https://x.org/a b", "fecha": "2026-10-01", "extracto": "x" * 20},
])
def test_verificada_exige_fuente_real_con_url_http_fecha_y_extracto(fuente):
    d = dosier()
    d["evidencia"][1] = {"afirmacion": "Algo comprobado por herramienta", "etiqueta": "VERIFICADA",
                         **({"fuente": fuente} if fuente is not None else {})}
    assert any("VERIFICADA exige fuente" in e for e in A.validar_dosier(A.limpiar_dosier(d)))


@pytest.mark.parametrize("hostil", [None, [], "texto", 42, {"nicho": []}, {"evidencia": "x"}, {"senal": 3},
                                    {"capacidades": [1]}, {"evidencia": [1, None, "x", {"fuente": 5}]}])
def test_entradas_hostiles_dan_errores_no_excepciones(hostil):
    errores = A.validar_dosier(A.limpiar_dosier(hostil))
    assert errores and all(isinstance(e, str) for e in errores)


def test_limpieza_acota_textos_quita_control_y_descarta_claves_desconocidas():
    d = dosier()
    d["nicho"]["problema"] = "a\x00b\x07c" + "x" * 5000
    d["clave_extra"] = "no debe pasar"
    d["evidencia"] = d["evidencia"] * 10
    limpio = A.limpiar_dosier(d)
    assert "\x00" not in limpio["nicho"]["problema"] and len(limpio["nicho"]["problema"]) <= 600
    assert "clave_extra" not in limpio and len(limpio["evidencia"]) <= A.MAX_LISTA


# ── vetos ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto", [
    "Vender reseñas falsas para restaurantes", "comprar reseñas en bloque", "Enviar spam a pymes",
    "correos masivos no solicitados", "un esquema piramidal de afiliados", "campaña electoral de un partido",
    "financiación política encubierta", "distribuir ransomware",
])
def test_vetos_detectan_las_categorias_del_suelo(texto):
    assert A.comprobar_vetos(texto), texto


@pytest.mark.parametrize("texto", ["Recordatorios de plazos para autonomos", "Informes de precios de alquiler",
                                   "Una gestoría que ayuda con la factura electrónica"])
def test_vetos_no_saltan_con_texto_normal(texto):
    assert A.comprobar_vetos(texto) == []


def test_un_veto_en_el_dosier_o_borrador_lo_rechaza(ap):
    a, _, _ = ap
    with pytest.raises(A.ApuestaInvalida, match="veto"):
        a.crear_borrador(borrador(problema="Generar reseñas falsas para negocios locales sin tiempo"), coords())
    r = a.crear_borrador(borrador(), coords())
    d = dosier()
    d["primer_paso_gratuito"] = "Enviar spam a mil empresas"
    with pytest.raises(A.ApuestaInvalida, match="veto"):
        a.completar_dosier(r["id"], d)
    assert a.obtener(r["id"])["estado"] == "BORRADOR"                 # nada se guardo


# ── novedad ─────────────────────────────────────────────────────────────────

def test_similitud_basica():
    assert A.similitud("plazos fiscales autonomos", "Plazos Fiscales de los AUTÓNOMOS") > 0.5
    assert A.similitud("plazos fiscales autonomos", "recetas de cocina vegana") == 0.0
    assert A.similitud("", "algo") == 0.0


def test_un_borrador_casi_igual_se_rechaza_y_dice_a_cual_se_parece(ap):
    a, _, _ = ap
    r = a.crear_borrador(borrador(), coords())
    parecido = borrador(titulo="Recordatorios de plazos fiscales para autónomos", por_que_ahora="otro motivo")
    with pytest.raises(A.Repetida) as e:
        a.crear_borrador(parecido, coords(modelo_ingreso="producto_digital", cliente="particular",
                                          canal="redes_sociales", sector="otra cosa distinta"))
    assert e.value.similar_a == r["id"] and "demasiado_parecida" in e.value.razon


def test_mismas_coordenadas_y_sector_se_rechaza_aunque_el_texto_cambie(ap):
    a, _, _ = ap
    a.crear_borrador(borrador(), coords())
    otro = borrador(titulo="Marketplace de repartidores locales", problema="Los repartidores no encuentran pedidos cerca.",
                    publico="Repartidores independientes de ciudades medianas")
    with pytest.raises(A.Repetida) as e:
        a.crear_borrador(otro, coords(sector="Gestorías de barrio"))
    assert "mismas_coordenadas" in e.value.razon
    a.crear_borrador(otro, coords(sector="reparto de comida", canal="alianzas"))     # cambia de verdad: entra


def test_se_compara_tambien_con_las_descartadas_y_podadas(ap):
    a, _, _ = ap
    r = a.crear_borrador(borrador(), coords())
    a.descartar(r["id"], por="op", razon="ya probado antes", aprendizaje={"esperaba": "x" * 5, "paso": "yyyyy", "haria_distinto": "zzzzz"})
    with pytest.raises(A.Repetida):
        a.crear_borrador(borrador(), coords(modelo_ingreso="otro"))


def test_variacion_de_una_apuesta_crece_exige_cambio_y_no_compara_texto_con_la_madre(ap):
    a, _, _ = ap
    r = _a_dosier(a)
    _llevar_a(a, r["id"], "CRECE")
    mismo = borrador()
    with pytest.raises(A.Repetida, match="variacion_sin_cambio"):
        a.crear_borrador(mismo, coords(), variacion_de=r["id"])
    v = a.crear_borrador(mismo, coords(canal="redes_sociales"), variacion_de=r["id"])
    assert v["variacion_de"] == r["id"]
    with pytest.raises(A.ApuestaInvalida, match="CRECE"):
        a.crear_borrador(borrador(titulo="Otra cosa sin relacion alguna", problema="Un problema muy distinto del anterior.", publico="Otra gente distinta por completo"),
                         coords(sector="xx yy", canal="alianzas"), variacion_de="no_existe")


def test_dos_hilos_con_el_mismo_borrador_solo_uno_entra(tmp_path):
    for ronda in range(8):
        k = JsonKnowledge(tmp_path / f"k{ronda}.json")
        res = []
        barrera = threading.Barrier(2)

        def crea():
            barrera.wait()
            try:
                A.Apuestas(k, T).crear_borrador(borrador(), coords())
                res.append("ok")
            except A.Repetida:
                res.append("repetida")
        hs = [threading.Thread(target=crea) for _ in range(2)]
        [h.start() for h in hs]; [h.join() for h in hs]
        assert sorted(res) == ["ok", "repetida"], (ronda, res)


# ── cuotas ──────────────────────────────────────────────────────────────────

def cand(i, **kw):
    c = coords(sector=f"sector numero {i}", **{k: v for k, v in kw.items() if k in coords()})
    return {"id": i, "borrador": borrador(titulo=f"Idea {i} totalmente distinta"), "coordenadas": c,
            "fuera_de_capacidades": kw.get("fuera", False), "variacion_de": kw.get("variacion_de")}


def test_seleccion_cubre_modelos_y_respeta_topes():
    pool = ([cand(i, modelo_ingreso="servicio_por_encargo") for i in range(6)]
            + [cand(10, modelo_ingreso="producto_digital", cliente="particular", canal="redes_sociales"),
               cand(11, modelo_ingreso="afiliacion", cliente="autonomo", canal="alianzas", fuera=True),
               cand(12, modelo_ingreso="datos_informes", cliente="empresa_grande", canal="boca_a_boca")])
    elegidos, fallos = A.seleccionar(pool, 5)
    assert len(elegidos) == 5 and fallos == []
    assert len({x["coordenadas"]["modelo_ingreso"] for x in elegidos}) >= 3
    for eje, tope in (("cliente", 2), ("canal", 2)):
        cuenta = {}
        for x in elegidos:
            cuenta[x["coordenadas"][eje]] = cuenta.get(x["coordenadas"][eje], 0) + 1
        assert max(cuenta.values()) <= tope


def test_seleccion_es_determinista_y_dice_que_cuotas_no_cumple():
    pool = [cand(i) for i in range(6)]                       # todos iguales en coordenadas
    e1, f1 = A.seleccionar(pool, 5)
    e2, f2 = A.seleccionar(copy.deepcopy(pool), 5)
    assert [x["id"] for x in e1] == [x["id"] for x in e2] and f1 == f2
    assert len(e1) == 2                                      # el tope por cliente/canal corta en 2
    assert {"min_modelos", "min_fuera_capacidades"} <= set(f1)


def test_exige_variacion_cuando_hay_una_apuesta_con_senal():
    pool = [cand(i, modelo_ingreso=m, cliente=c, canal=ca) for i, (m, c, ca) in enumerate([
        ("servicio_por_encargo", "pyme", "contacto_directo"), ("producto_digital", "particular", "redes_sociales"),
        ("afiliacion", "autonomo", "alianzas")])]
    pool.append(cand(9, modelo_ingreso="datos_informes", cliente="empresa_grande", canal="boca_a_boca", variacion_de="abc"))
    elegidos, fallos = A.seleccionar(pool, 4, exige_variacion=True)
    assert any(x.get("variacion_de") for x in elegidos) and "variacion" not in fallos
    _, fallos2 = A.seleccionar(pool[:3], 3, exige_variacion=True)
    assert "variacion" in fallos2


# ── maquina de estados ──────────────────────────────────────────────────────

APR = {"esperaba": "que pidieran el aviso", "paso": "pidieron pocos", "haria_distinto": "probar otro canal"}


def _llevar_a(a, ap_id, destino):
    """Camina por el flujo normal hasta `destino` (BORRADOR..CRECE/PODADA)."""
    orden = ["DOSIER", "ELEGIDA", "EN_PRUEBA", "MEDIDA", destino]
    r = a.obtener(ap_id)
    if r["estado"] == "BORRADOR":
        a.completar_dosier(ap_id, dosier())
    if destino == "DOSIER":
        return a.obtener(ap_id)
    a.elegir(ap_id, por="op")
    if destino == "ELEGIDA":
        return a.obtener(ap_id)
    a.iniciar_prueba(ap_id, por="op")
    if destino == "EN_PRUEBA":
        return a.obtener(ap_id)
    a.registrar_medicion(ap_id, por="op", valor=12 if destino == "CRECE" else 1, referencia="hoja de respuestas")
    if destino == "MEDIDA":
        return a.obtener(ap_id)
    return a.cerrar(ap_id, destino, por="op", aprendizaje=APR)


def test_camino_completo_con_nueva_ronda_y_poda(ap):
    a, k, b = ap
    r = a.crear_borrador(borrador(), coords())
    assert r["estado"] == "BORRADOR" and r["ronda"] == 1
    r = _llevar_a(a, r["id"], "CRECE")
    assert r["estado"] == "CRECE" and r["propuesta_regla"]["decision"] == "CRECE"
    r = a.iniciar_prueba(r["id"], por="op", criterio={"umbral": 20, "plazo_dias": 30})
    assert r["estado"] == "EN_PRUEBA" and r["ronda"] == 2 and r["rondas_previas"][0]["ronda"] == 1
    assert r["medicion"] is None and r["criterio"]["umbral"] == 20
    a.registrar_medicion(r["id"], por="op", valor=5, referencia="panel de visitas")
    r = a.cerrar(r["id"], "PODADA", por="op", aprendizaje=APR)
    assert r["estado"] == "PODADA" and [h["a"] for h in r["historial"]][-1] == "PODADA"
    tipos = [t for t, _ in _eventos(k)]
    assert tipos.count("inteligencia.apuesta.en_prueba") == 2 and tipos[-1] == "inteligencia.apuesta.podada"
    assert b.verificar()["integra"] is True


def test_ninguna_transicion_fuera_de_la_tabla_es_posible(ap):
    a, _, _ = ap
    for de in A.ESTADOS:
        for hacia in A.ESTADOS:
            u = _unico(len(a.listar()))
            r = a.crear_borrador(borrador(titulo=_palabras_unicas(u, "t"), problema=_palabras_unicas(u, "p"),
                                          publico=_palabras_unicas(u, "u")),
                                 coords(sector=f"sector {u}", canal=A.CANALES[len(a.listar()) % 7],
                                        modelo_ingreso=A.MODELOS_INGRESO[len(a.listar()) % 9],
                                        cliente=A.CLIENTES[len(a.listar()) % 5]))
            # forzar el estado de partida sin pasar por el flujo (solo para la tabla)
            r2 = a.obtener(r["id"]); r2["estado"] = de; a.k.add(T, A.COLECCION, r["id"], r2)
            if hacia in A.TRANSICIONES[de]:
                continue
            with pytest.raises(A.TransicionInvalida):
                a._transitar(r["id"], hacia, actor="operador", por="op", mutar=lambda r: None)
            assert a.obtener(r["id"])["estado"] == de


def test_terminales_no_tienen_salida(ap):
    a, _, _ = ap
    r = _llevar_a(a, a.crear_borrador(borrador(), coords())["id"], "PODADA")
    for f in (lambda: a.elegir(r["id"], por="op"), lambda: a.iniciar_prueba(r["id"], por="op"),
              lambda: a.cerrar(r["id"], "CRECE", por="op", aprendizaje=APR),
              lambda: a.descartar(r["id"], por="op", razon="ya no", aprendizaje=APR)):
        with pytest.raises(A.TransicionInvalida, match="terminal"):
            f()


def test_el_operador_debe_identificarse_y_la_regla_solo_propone(ap):
    a, _, _ = ap
    r = _a_dosier(a)
    with pytest.raises(A.ApuestaInvalida, match="por"):
        a.elegir(r["id"], por="  ")
    _llevar_a(a, r["id"], "MEDIDA")
    r = a.obtener(r["id"])
    assert r["estado"] == "MEDIDA" and r["propuesta_regla"]["decision"] == "PODADA"      # valor 1 < umbral 10
    r = a.cerrar(r["id"], "CRECE", por="op", aprendizaje=APR)                            # decide el humano
    assert r["estado"] == "CRECE"
    evs = dict((t, p) for t, p in _eventos(a.k))
    assert evs["inteligencia.apuesta.crece"]["contra_la_regla"] is True


@pytest.mark.parametrize("comparador,valor,esperado", [(">=", 10, "CRECE"), (">=", 9.99, "PODADA"),
                                                       ("<=", 10, "CRECE"), ("<=", 10.01, "PODADA")])
def test_regla_propuesta_segun_comparador(ap, comparador, valor, esperado):
    a, _, _ = ap
    r = _a_dosier(a)
    a.elegir(r["id"], por="op")
    a.iniciar_prueba(r["id"], por="op", criterio={"comparador": comparador, "umbral": 10})
    r = a.registrar_medicion(r["id"], por="op", valor=valor, referencia="fuente")
    assert r["propuesta_regla"]["decision"] == esperado


def test_aprendizaje_y_razon_obligatorios_al_cerrar(ap):
    a, _, _ = ap
    r = _a_dosier(a)
    with pytest.raises(A.ApuestaInvalida, match="razon"):
        a.descartar(r["id"], por="op", razon="no", aprendizaje=APR)
    with pytest.raises(A.ApuestaInvalida, match="aprendizaje"):
        a.descartar(r["id"], por="op", razon="no me convence", aprendizaje={"esperaba": "", "paso": "", "haria_distinto": ""})
    assert a.obtener(r["id"])["estado"] == "DOSIER"
    _llevar_a(a, r["id"], "MEDIDA")
    with pytest.raises(A.ApuestaInvalida, match="aprendizaje"):
        a.cerrar(r["id"], "PODADA", por="op", aprendizaje=None)
    with pytest.raises(A.ApuestaInvalida, match="CRECE o PODADA"):
        a.cerrar(r["id"], "ELEGIDA", por="op", aprendizaje=APR)


@pytest.mark.parametrize("criterio,fragmento", [
    ({"coste_max_eur": 5}, "coste_max_eur"), ({"plazo_dias": 0}, "plazo_dias"), ({"plazo_dias": 999}, "plazo_dias"),
    ({"comparador": "="}, "comparador"), ({"umbral": "mucho"}, "umbral"), ({"fuente_dato": "x"}, "fuente_dato"),
])
def test_criterio_de_muerte_completo_y_sin_gasto(ap, criterio, fragmento):
    a, _, _ = ap
    r = _a_dosier(a)
    a.elegir(r["id"], por="op")
    with pytest.raises(A.ApuestaInvalida, match=fragmento):
        a.iniciar_prueba(r["id"], por="op", criterio=criterio)
    assert a.obtener(r["id"])["estado"] == "ELEGIDA" and a.obtener(r["id"])["criterio"] is None


def test_el_criterio_hereda_la_senal_del_dosier_y_fija_fecha_limite(ap):
    a, _, _ = ap
    r = _a_dosier(a)
    a.elegir(r["id"], por="op")
    r = a.iniciar_prueba(r["id"], por="op")
    c = r["criterio"]
    assert (c["umbral"], c["comparador"], c["plazo_dias"], c["coste_max_eur"]) == (10, ">=", 14, 0)
    assert c["fecha_inicio"] == "2026-10-01" and c["fecha_limite"] == "2026-10-15"


def test_medicion_exige_numero_y_referencia(ap):
    a, _, _ = ap
    r = _llevar_a(a, a.crear_borrador(borrador(), coords())["id"], "EN_PRUEBA")
    for valor, ref in (("mucho", "x"), (None, "x"), (float("nan"), "x"), (True, "x"), (5, ""), (5, "ab")):
        with pytest.raises(A.ApuestaInvalida):
            a.registrar_medicion(r["id"], por="op", valor=valor, referencia=ref)
    assert a.obtener(r["id"])["estado"] == "EN_PRUEBA"


def test_pide_medicion_avisa_pero_no_cambia_el_estado(ap):
    a, _, _ = ap
    r = _llevar_a(a, a.crear_borrador(borrador(), coords())["id"], "EN_PRUEBA")
    assert a.pide_medicion() == []
    a._reloj_mut["t"] += timedelta(days=15)                       # plazo de 14 dias vencido
    assert a.pide_medicion() == [r["id"]]
    assert a.obtener(r["id"])["estado"] == "EN_PRUEBA"


def test_conteo_por_estado(ap):
    a, _, _ = ap
    a.crear_borrador(borrador(), coords())
    r = a.crear_borrador(borrador(titulo="Otra idea distinta del todo", problema="Un problema totalmente diferente aqui.", publico="Un publico muy otro"),
                         coords(sector="zz otra", canal="alianzas", modelo_ingreso="afiliacion"))
    a.completar_dosier(r["id"], dosier())
    c = a.conteo_por_estado()
    assert c["BORRADOR"] == 1 and c["DOSIER"] == 1 and sum(c.values()) == 2


# ── sellado: sin texto, integro, sin interbloqueo ───────────────────────────

def test_los_eventos_llevan_ids_y_huellas_pero_nunca_el_texto(ap):
    a, k, b = ap
    r = _llevar_a(a, a.crear_borrador(borrador(), coords())["id"], "PODADA")
    volcado = str(_eventos(k))
    for texto in ("Recordatorios de plazos", "autonomos olvidan", "Publicar el mensaje", "hoja de respuestas",
                  "que pidieran el aviso"):
        assert texto not in volcado
    ev = dict(_eventos(k))
    assert ev["inteligencia.apuesta.dosier_completado"]["dosier_sha256"] == r["dosier_sha256"]
    assert ev["inteligencia.apuesta.creada"]["modelo_ingreso"] == "servicio_por_encargo"
    assert b.verificar()["integra"] is True


def test_sin_bitacora_funciona_y_no_sella():
    k = InMemoryKnowledge()
    a = A.Apuestas(k, T)
    r = a.crear_borrador(borrador(), coords())
    a.completar_dosier(r["id"], dosier())
    assert k.all(T, "evento") == {}


def test_sin_interbloqueo_con_la_bitacora_real_publicando_a_la_vez(tmp_path):
    """Regresion de un interbloqueo ABBA real (visto en core/autonomia.py): sellar dentro del candado
    de datos. Se ejecuta en un SUBPROCESO con plazo: un interbloqueo deja candados del proceso
    retenidos y colgaria tambien a los tests siguientes si ocurriera aqui dentro."""
    import subprocess
    codigo = """
import sys, threading, time
sys.path.insert(0, %r)
from core import apuestas as A
from core.knowledge import JsonKnowledge
from core.rue import Bitacora, Sobre
T = "t1"
k = JsonKnowledge(sys.argv[1])
b = Bitacora(k, T, fecha_alta="2026-07-10")
a = A.Apuestas(k, T, bitacora=b)
def u(i):
    return "zeta" + "".join("abcdefghij"[int(c)] for c in str(i)) + "omega"
def pal(x, campo):
    return " ".join(x + campo + c for c in "abcdef")
def trabaja():
    for i in range(12):
        x = u(i)
        r = a.crear_borrador({"titulo": pal(x, "t"), "problema": pal(x, "p"), "publico": pal(x, "u")},
                             {"modelo_ingreso": A.MODELOS_INGRESO[i %% 9], "cliente": A.CLIENTES[i %% 5],
                              "canal": A.CANALES[i %% 7], "mercado": "es_ES", "coste_inicial": "0",
                              "tiempo_senal": "<=7d", "sector": "sector aparte " + x})
def publica():
    for i in range(80):
        b.publicar(Sobre(tenant_id=T, tipo="plataforma.diario.entrada", payload={"n": i}, origen="t"))
hs = [threading.Thread(target=f, daemon=True) for f in (trabaja, publica, publica)]
[h.start() for h in hs]
limite = time.monotonic() + 40
for h in hs:
    h.join(timeout=max(0.0, limite - time.monotonic()))
if any(h.is_alive() for h in hs):
    sys.exit(3)
sys.exit(0 if b.verificar()["integra"] else 4)
""" % str(Path(__file__).parent.parent)
    try:
        r = subprocess.run([sys.executable, "-c", codigo, str(tmp_path / "k.json")], timeout=90,
                           capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        pytest.fail("interbloqueo entre Apuestas y Bitacora (el subproceso no termino)")
    assert r.returncode == 0, f"codigo {r.returncode}: {r.stdout[-300:]} {r.stderr[-500:]}"


def test_una_validacion_fallida_dentro_de_la_transicion_no_deja_nada_a_medias(ap):
    a, k, b = ap
    r = _a_dosier(a)
    a.elegir(r["id"], por="op")
    antes = a.obtener(r["id"])
    n_eventos = len(k.all(T, "evento"))
    with pytest.raises(A.ApuestaInvalida):
        a.iniciar_prueba(r["id"], por="op", criterio={"coste_max_eur": 50})
    assert a.obtener(r["id"]) == antes and len(k.all(T, "evento")) == n_eventos


def test_empresas_distintas_no_se_mezclan():
    k = InMemoryKnowledge()
    A.Apuestas(k, "a").crear_borrador(borrador(), coords())
    assert A.Apuestas(k, "b").listar() == []
    A.Apuestas(k, "b").crear_borrador(borrador(), coords())            # mismo texto en otra empresa: entra


# ── frases del feed y registro de eventos ───────────────────────────────────

def test_todos_los_eventos_de_apuestas_estan_registrados_y_tienen_frase_propia():
    from core.rue import cargar_rue
    from panel_mando import nucleo as N
    tipos = [t for t in cargar_rue()["tipos"] if t.startswith(("inteligencia.apuesta.", "inteligencia.exploracion."))]
    assert len(tipos) == 10
    for t in tipos:
        assert t in N.FRASES, t
        f = N.render({"tipo": t, "payload": {}})
        assert isinstance(f, str) and f
        assert f != N._f_generico({"tipo": t, "payload": {}}), f"{t}: cae en la frase generica"


def test_frases_legibles_con_datos():
    from panel_mando import nucleo as N
    assert N.render({"tipo": "inteligencia.apuesta.creada",
                     "payload": {"modelo_ingreso": "servicio_por_encargo", "cliente": "pyme"}}) == \
        "propuse una apuesta nueva: servicio por encargo para pyme"
    assert "CRECE" in N.render({"tipo": "inteligencia.apuesta.medida", "payload": {"propuesta": "CRECE"}})
    assert "ciclo 2" in N.render({"tipo": "inteligencia.exploracion.ciclo_terminado",
                                  "payload": {"ciclo": 2, "dosieres": 5, "rechazados_por_repeticion": 3}})


def test_el_mundo_atribuye_los_eventos_de_apuestas_a_inteligencia():
    from panel_mando import mundo as M
    ev = M.evento_rue(1, {"tipo": "inteligencia.apuesta.creada", "payload": {"modelo_ingreso": "otro", "cliente": "pyme"}, "ts": "x"})
    assert ev["cubo"] == "inteligencia" and "apuesta" in ev["frase"]


@pytest.mark.parametrize("malo", ["texto", 5, [1], True])
def test_un_criterio_que_no_es_objeto_se_rechaza_en_vez_de_ignorarse(ap, malo):
    a, _, _ = ap
    r = _a_dosier(a)
    a.elegir(r["id"], por="op")
    with pytest.raises(A.ApuestaInvalida, match="criterio"):
        a.iniciar_prueba(r["id"], por="op", criterio=malo)
    assert a.obtener(r["id"])["estado"] == "ELEGIDA"
    assert a.iniciar_prueba(r["id"], por="op", criterio=None)["estado"] == "EN_PRUEBA"        # vacio = hereda
