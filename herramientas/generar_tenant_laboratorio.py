"""Generador del tenant SINTÉTICO 'laboratorio' (D11 E0.2 / R-REV-3).

Crea N leads inventados y deterministas bajo la empresa 'laboratorio' en un
knowledge.json, para ensayar el circuito COMPLETO de KAIZEN (Fase 0 → tarjeta →
Mesa → ejecutor → SMTP a buzones PROPIOS) sin tocar jamás a un tercero real.

Garantías:
- Determinista: mismo N → mismos bytes (sin reloj, sin azar). Reproducible y
  diffeable, como manda la casa.
- Inofensivo: emails en dominio .invalid (RFC 2606: jamás entregable) salvo que el
  operador pase --buzon-propio para el ensayo real de SMTP contra su propio buzón.
- Reversible: copia de seguridad del knowledge antes de escribir; escritura
  atómica (tmp + replace); las demás empresas quedan intactas byte a byte.
- Marcado: cada lead lleva "sintetico": true y nombres inequívocamente falsos.

Uso:
    python herramientas/generar_tenant_laboratorio.py                # 50 leads
    python herramientas/generar_tenant_laboratorio.py --n 20
    python herramientas/generar_tenant_laboratorio.py --knowledge ruta.json
    python herramientas/generar_tenant_laboratorio.py --buzon-propio yo@midominio.es
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# R-TENANT: el knowledge es DATO. Se resuelve al usarlo, no en el import.
KNOWLEDGE_DEFECTO = None
EMPRESA = "laboratorio"
TS_FIJO = "2026-08-03T00:00:00+00:00"     # determinista a propósito
FECHA_FIJA = "2026-08-03"

#: Los ficheros del tenant sintético se versionan CON el producto (son ficción,
#: no dato de cliente): `empresas/laboratorio/` está en la allowlist del
#: centinela y en `core.rutas.TENANTS_SINTETICOS`.
DIR_TENANT_DEFECTO = RAIZ / "empresas" / EMPRESA
REGISTRO_DEFECTO = RAIZ / "empresas" / "tenants.laboratorio.json"

_CATEGORIAS = [
    # (categoria_icp, prioridad, place_type, prefijo de nombre)
    ("cafeteria_especialidad", "ALTA", "cafe", "Cafetería Sintética"),
    ("tienda_gourmet_delicatessen", "ALTA", "deli", "Gourmet Sintético"),
    ("hotel_boutique_con_desayuno", "ALTA", "hotel", "Hotel Sintético"),
    ("restaurante_con_postre_artesanal", "MEDIA", "restaurant", "Restaurante Sintético"),
    ("catering_regional_premium", "MEDIA", "catering_service", "Catering Sintético"),
]


def _lead(i: int, buzon_propio: str | None) -> tuple[str, dict]:
    cat, prio, ptype, prefijo = _CATEGORIAS[i % len(_CATEGORIAS)]
    lid = f"lab_{i:02d}_{cat[:12]}"
    nombre = f"{prefijo} {i:02d}"
    email = buzon_propio if buzon_propio else f"lead{i:02d}@laboratorio.invalid"
    anillo = 0 if i % 3 == 0 else 1
    minutos = 12.0 + (i % 3) * 11.0        # 12 / 23 / 34 min — dentro de anillos 0-1
    return lid, {
        "id": lid,
        "company": EMPRESA,
        "sintetico": True,
        "nombre": nombre,
        "estado": "enriquecido",
        "estado_pipeline": "cold",
        "categoria_icp": cat,
        "prioridad_icp": prio,
        "anillo": anillo,
        "distancia_minutos": minutos,
        "distancia_metros": minutos * 900,
        "distancia_provider": "sintetico",
        "tipo_detectado": ptype,
        "place_types": [ptype],                                   # I-1 desde el nacimiento
        "icp_match": {"senal": "place_type", "peso": 2,           # I-3 desde el nacimiento
                      "razon": f"Encaja en {cat} ({prio}): place_type match (sintetico)"},
        "contacto": {"telefono": f"9680000{i:02d}", "web": f"https://lab{i:02d}.laboratorio.invalid",
                     "email": email},
        "ubicacion": {"lat": 38.20 + i * 0.001, "lon": -1.40 - i * 0.001,
                      "direccion": f"Calle del Ensayo {i}, Cieza (sintetica)",
                      "municipio": "Cieza"},
        "metadatos_fuente": {"rating": 3.5 + (i % 4) * 0.4,
                             "ratings_count": 10 + i * 3,
                             "business_status": "OPERATIONAL",
                             "telefono": f"9680000{i:02d}",
                             "web": f"https://lab{i:02d}.laboratorio.invalid"},
        "tamano_estimado": ["minimo", "pequeno", "medio"][i % 3],
        "fuentes": [{"nombre": "sintetico", "id_externo": f"lab-{i:04d}"}],
        "descripcion": f"Negocio sintetico nº {i} del tenant laboratorio (no existe).",
        "do_not_call": False,
        "creado_en": TS_FIJO,
        "actualizado_en": TS_FIJO,
        "interacciones": [],
        "compromisos": [],
        "historial": [{"ts": TS_FIJO, "desde": None, "a": "enriquecido",
                       "razon": "generado por generar_tenant_laboratorio (sintetico)",
                       "detalle": {}}],
    }


# ── Ficheros del tenant (mismo esquema que un tenant real, contenido inventado) ──

def argumentario_sintetico() -> dict:
    """Argumentario del tenant sintético. Mismo ESQUEMA que el de un tenant real;
    el contenido es ficción coherente con los leads que emite `_lead()`.

    Las tres formas de `argumentos_prohibidos` están representadas a propósito —
    dos con `patrones_substring` y una con `deteccion: semantica_llm` — porque el
    filtrado de `core.argumentario.patrones_argumentos_prohibidos()` depende de
    esa distinción y sin ella el camino no se ejercita.
    """
    return {
        "version": "1.0",
        "empresa": EMPRESA,
        "actualizado": FECHA_FIJA,
        "fuente": "generado por generar_tenant_laboratorio.py — SINTETICO, sin tercero detras",
        "argumentos_funcionan": [
            {"prioridad": 1, "id": "margen_sintetico",
             "texto": "Margen del 70% sobre PVP recomendado en el producto sintetico de ensayo.",
             "porque": "Cifra inventada; existe para ejercitar el orden por prioridad."},
            {"prioridad": 2, "id": "entrega_sintetica",
             "texto": "Entrega en 24h en el area sintetica de ensayo.",
             "porque": "Ficcion coherente con los leads del tenant laboratorio."},
            {"prioridad": 3, "id": "sin_minimo_sintetico",
             "texto": "Sin pedido minimo durante el ensayo.",
             "porque": "Ficcion; ningun compromiso real detras."},
            {"prioridad": 4, "id": "formato_sintetico",
             "texto": "Formato de prueba pensado para el circuito de laboratorio.",
             "porque": "Ficcion; cierra la lista en cuatro como un tenant real."},
        ],
        "argumentos_prohibidos": [
            {"id": "superlativo_absoluto",
             "texto_ejemplo": "El mejor producto sintetico del mundo.",
             "patrones_substring": ["el mejor del mundo", "insuperable",
                                    "el numero uno", "unico en el mercado"],
             "razon": "Superlativo no verificable: regla dura, se detecta por substring."},
            {"id": "promesa_de_resultado",
             "texto_ejemplo": "Garantizamos que duplicas ventas.",
             "patrones_substring": ["garantizamos que", "duplicas ventas",
                                    "resultados garantizados", "sin riesgo alguno"],
             "razon": "Promesa de resultado: regla dura, se detecta por substring."},
            {"id": "comparacion_precio_competencia",
             "texto_ejemplo": "Somos mas baratos que el de al lado.",
             "patrones_substring": [],
             "deteccion": "semantica_llm",
             "razon": "Comparacion de precio: depende del contexto, la juzga el LLM."},
        ],
        "segmentos_diana": [
            {"prioridad": 1, "id": "cafeteria_especialidad",
             "nombre": "Cafeteria de especialidad (sintetica)",
             "razon": "Segmento de ensayo; coincide con los leads generados."},
            {"prioridad": 2, "id": "tienda_gourmet_delicatessen",
             "nombre": "Tienda gourmet / delicatessen (sintetica)",
             "razon": "Segmento de ensayo; coincide con los leads generados."},
            {"prioridad": 3, "id": "hotel_boutique_con_desayuno",
             "nombre": "Hotel boutique con desayuno (sintetico)",
             "razon": "Segmento de ensayo; coincide con los leads generados."},
            {"prioridad": 4, "id": "restaurante_con_postre_artesanal",
             "nombre": "Restaurante con postre artesanal (sintetico)",
             "razon": "Segmento de ensayo; coincide con los leads generados."},
        ],
        "competencia": [
            {"id": f"competidor_sintetico_{i}",
             "nombre": f"Competidor Sintetico {i}",
             "ubicacion": "Area sintetica de ensayo",
             "rol": ["obrador", "industrial", "distribuidor", "mayorista"][i - 1],
             "fortaleza": f"Fortaleza inventada nº {i}.",
             "amenaza": f"Amenaza inventada nº {i}."}
            for i in range(1, 5)
        ],
        "precios_competencia_uso_interno": {
            "_aviso": ("USO INTERNO. NUNCA se pasa al transcript ni al email saliente. "
                       "Cifras inventadas del tenant sintetico."),
            "moneda": "EUR",
            "referencias": [
                {"id": "ref_sintetica_1", "producto": "Magdalena sintetica",
                 "precio_eur": 0.30, "iva_incluido": True,
                 "nota": "Anomalia sintetica a proposito: precio por debajo del resto."},
                {"id": "ref_sintetica_2", "producto": "Croissant sintetico",
                 "precio_eur": 1.10, "iva_incluido": True,
                 "nota": "Referencia inventada."},
                {"id": "ref_sintetica_3", "producto": "Tarta sintetica (racion)",
                 "precio_eur": 2.75, "iva_incluido": True,
                 "nota": "Referencia inventada."},
                {"id": "ref_sintetica_4", "producto": "Caja surtida sintetica",
                 "precio_eur": 12.50, "iva_incluido": False,
                 "nota": "Referencia inventada."},
            ],
        },
        "distribuidores_logistica_fase1": [
            {"id": f"distribuidor_sintetico_{i}",
             "nombre": f"Distribuidor Sintetico {i}",
             "ubicacion": "Area sintetica de ensayo",
             "antiguedad_anos": 5 + i}
            for i in range(1, 4)
        ],
    }


def brand_sintetico() -> dict:
    """Los cinco ficheros de `brand/` del tenant sintetico, con el MISMO esquema
    que los de un tenant real. Devuelve {nombre_fichero: contenido}.

    Existian ya, escritos a mano con un esquema mas laxo (sin `version`, con
    `remitente` en vez de `remitente_*`, `assets: []` en vez de paleta/logos):
    por eso el departamento Brand no se podia ejercitar contra el laboratorio.
    """
    return {
        "guia.json": {
            "empresa": EMPRESA,
            "version": "1.0",
            "actualizado": FECHA_FIJA,
            "posicionamiento": ("Empresa sintetica de pruebas: mensajes claros, "
                                "honestos y sin promesas."),
            "valores": ["honestidad", "claridad", "cero promesas", "sobriedad"],
            "tono": {
                "descripcion": "Directo y sobrio, sin superlativos.",
                "voz": ["claro", "concreto", "cercano", "verificable"],
                "anti_voz": ["grandilocuente", "publicitario", "vago",
                             "urgente", "adulador"],
            },
            "que_decir": ["lo que el producto hace", "plazos reales",
                          "condiciones sin letra pequena", "quien firma el mensaje"],
            "que_no_decir": ["precio", "descuento", "garantizado", "sin compromiso"],
            "cliente_ideal": ("Negocio sintetico del area de ensayo; no existe "
                              "ninguno real detras."),
        },
        "firma.json": {
            "empresa": EMPRESA,
            "version": "1.0",
            "remitente_nombre": "Equipo del Laboratorio",
            "remitente_cargo": "Ensayo sintetico",
            "remitente_empresa": "Laboratorio Sintetico S.L. (no existe)",
            "telefono": "968000000",
            "email": "equipo@laboratorio.invalid",
            "cierre_sugerido": "Un saludo,\nEquipo del Laboratorio",
        },
        "palabras_prohibidas.json": {
            "empresa": EMPRESA,
            "version": "1.0",
            "comentario": ("Regla dura del Brand Guardian: se comparan en minusculas "
                           "contra el cuerpo del mensaje. Lista sintetica."),
            "palabras": ["barato", "barata", "gratis", "milagroso", "garantizado",
                         "insuperable", "unico", "revolucionario", "increible",
                         "espectacular", "chollo", "oferta irrepetible", "sin riesgo",
                         "urgente", "ultima oportunidad", "exclusivo", "premium",
                         "lider"],
        },
        "argumentos_prohibidos.json": {
            "empresa": EMPRESA,
            "version": "1.0",
            "comentario": ("Argumentos vetados del tenant sintetico. Los marcados "
                           "`deteccion: semantica_llm` no generan patron substring."),
            "argumentos_prohibidos": [
                {"id": "precio",
                 "patrones_substring": ["le ofrezco un precio", "descuento del",
                                        "precio especial", "rebaja"],
                 "razon": "Prometer precios es competencia exclusiva de un humano."},
                {"id": "superlativo_absoluto",
                 "patrones_substring": ["el mejor del mundo", "insuperable",
                                        "el numero uno", "unico en el mercado"],
                 "razon": "Superlativo no verificable."},
                {"id": "comparacion_precio_competencia",
                 "patrones_substring": [],
                 "deteccion": "semantica_llm",
                 "razon": "Comparacion de precio: la juzga el LLM, no la regla dura."},
            ],
        },
        "assets_manifest.json": {
            "empresa": EMPRESA,
            "version": "1.0",
            "actualizado": FECHA_FIJA,
            "comentario": "Manifiesto sintetico: ningun asset real referenciado.",
            "paleta": {
                "primario": "#1F2933",
                "secundario": "#7B8794",
                "acento": "#C13B2F",
                "texto": "#111827",
                "comentario": "Colores inventados para el ensayo.",
            },
            "tipografias": {
                "titulares": "Sintetica Display",
                "cuerpo": "Sintetica Text",
                "comentario": "Tipografias inexistentes, a proposito.",
            },
            "logos": [
                {"id": "logo_principal", "version": "1.0",
                 "ruta": "empresas/laboratorio/brand/logo_sintetico.svg",
                 "estado": "placeholder"},
            ],
            "plantillas": [
                {"id": "email_presentacion", "version": "1.0",
                 "descripcion": "Plantilla sintetica de email de presentacion."},
            ],
        },
    }


#: Numero de variantes de apertura de voz que emite el generador.
N_VARIANTES_VOZ = 5


def aiact_sintetico() -> dict:
    """Textos AI Act art. 50 del tenant SINTETICO: {nombre_fichero: contenido}.

    OJO CON QUE ES ESTO: son textos de transparencia para un tenant que **no
    contacta con nadie** (leads inventados, correos `.invalid`). Existen para que
    el candado del AI Act se pueda EJERCITAR de punta a punta sin usar el texto
    aprobado de un cliente real. No aprueban nada para ningun tenant real: esa
    aprobacion es del operador y solo del operador (§11.2 de R-TENANT).
    """
    aprobadas = [
        "Este mensaje lo ha redactado un sistema automatizado de inteligencia "
        "artificial en nombre de Laboratorio KAIZEN; una persona revisa y aprueba "
        "cada envio. Si prefiere no recibir mas correos, responda a este mensaje y "
        "lo registraremos de inmediato.",
        "Le escribe el asistente virtual de Laboratorio KAIZEN, supervisado y "
        "aprobado por una persona antes de cada envio. Responda a este correo si "
        "desea dejar de recibir comunicaciones.",
    ]
    email = ["# Variantes de transparencia AI Act art. 50 — EMAIL (tenant sintetico)",
             "",
             "Generado por `herramientas/generar_tenant_laboratorio.py`. SINTETICO:",
             "el tenant `laboratorio` no escribe a ningun tercero real.",
             "",
             "## APROBADAS", ""]
    email += [f"- {v}" for v in aprobadas]
    email += ["", "## PROPUESTAS SIN APROBAR (no se usan en runtime)", ""]

    voz = ["# Primeros mensajes AI Act art. 50 — VOZ (tenant sintetico)",
           "",
           "Generado por `herramientas/generar_tenant_laboratorio.py`. SINTETICO:",
           "el tenant `laboratorio` no llama a ningun tercero real.",
           ""]
    for i in range(1, N_VARIANTES_VOZ + 1):
        voz.append(
            f"{i}. Hola, buenos dias. Le llama el asistente virtual de Laboratorio "
            f"KAIZEN. Soy un sistema automatizado de inteligencia artificial, no una "
            f"persona. Esta llamada es comercial y puede grabarse para control de "
            f"calidad; si prefiere no continuar, digamelo o cuelgue sin ningun "
            f"problema. (Variante sintetica {i} de {N_VARIANTES_VOZ}.)")
        voz.append("")
    return {"aiact_email_variantes.md": "\n".join(email) + "\n",
            "aiact_primeros_mensajes.md": "\n".join(voz)}


def icp_sintetico() -> dict:
    """ICP del tenant sintetico. Mismo ESQUEMA que el de un tenant real.

    Las categorias coinciden con las que emite `_lead()`, para que el filtro
    acepte los leads sinteticos y el circuito se pueda ensayar de punta a punta.
    """
    return {
        "empresa": EMPRESA,
        "version": "1.0",
        "actualizado": FECHA_FIJA,
        "fuente": "generado por generar_tenant_laboratorio.py — SINTETICO",
        "notas": "Geografia y marcas inventadas. Ningun negocio real referenciado.",
        "geografia": {
            "origen": {"lat": 38.24, "lon": -1.42, "nombre": "Villa Sintetica"},
            "max_anillo_activo": 1,
            "anillos": {
                "0": ["Villa Sintetica"],
                "1": ["Aldea Sintetica"],
                "2": ["Comarca Sintetica"],
                "3": [],
            },
        },
        # `place_types` usa los tipos reales del proveedor de mapas (no son dato de
        # cliente) para que el filtro se ejercite igual que en produccion.
        "tipos_incluidos": [
            {"categoria": "hotel_boutique_con_desayuno", "prioridad": "ALTA",
             "place_types": ["lodging"], "keywords": ["hotel", "casa rural", "hostal"],
             "query_seeds": ["hotel boutique", "casa rural"],
             "razon": "Segmento de ensayo: alojamiento con desayuno."},
            {"categoria": "tienda_gourmet_delicatessen", "prioridad": "ALTA",
             "place_types": ["deli", "store"], "keywords": ["gourmet", "delicatessen"],
             "query_seeds": ["tienda gourmet"],
             "razon": "Segmento de ensayo: tienda gourmet."},
            {"categoria": "cafeteria_especialidad", "prioridad": "ALTA",
             "place_types": ["cafe"], "keywords": ["cafeteria", "tostadero", "cafe"],
             "query_seeds": ["cafeteria de especialidad"],
             "razon": "Segmento de ensayo: cafeteria de especialidad."},
            {"categoria": "restaurante_con_postre_artesanal", "prioridad": "MEDIA",
             "place_types": ["restaurant"], "keywords": ["restaurante", "meson"],
             "query_seeds": ["restaurante"],
             "razon": "Segmento de ensayo: restaurante."},
            {"categoria": "catering_regional_premium", "prioridad": "MEDIA",
             "place_types": ["catering_service"], "keywords": ["catering", "eventos"],
             "query_seeds": ["catering"],
             "razon": "Segmento de ensayo: catering."},
        ],
        "tipos_excluidos": [
            {"categoria": "cadena_sintetica_excluida",
             "razon": "Cadena inventada: sirve para ejercitar la exclusion por tipo.",
             "place_types": ["supermarket"],
             "keywords": ["cadena sintetica", "supermercado sintetico"]},
        ],
        "marcas_excluidas": ["Marca Sintetica Excluida Uno",
                             "Marca Sintetica Excluida Dos",
                             "Marca Sintetica Excluida Tres"],
        "exclusiones_por_patron": [
            {"patron": r"^sintetic[oa] excluid[oa]\b",
             "razon": "Patron inventado para ejercitar la exclusion por regex."},
        ],
        "criterios_actividad": {"max_dias_sin_actividad": 540,
                                "min_resenas_recientes": 1},
    }


def diario_sintetico() -> dict:
    """Diario del tenant sintetico: {nombre_fichero: contenido}.

    El diario es DATO y sale del arbol en R-TENANT F5, pero el del tenant
    sintetico es ficcion y viaja con el producto (ver `core.rutas`). Sin el, la
    simulacion de prospeccion no detecta sector y devuelve cero leads: el
    circuito completo no se podia ensayar sin datos de un cliente real.
    """
    return {
        "CONTEXTO_NEGOCIO.md": (
            "# Contexto de negocio — Laboratorio Sintetico S.L. (no existe)\n\n"
            "Tenant SINTETICO para ensayar el circuito completo de KAIZEN sin tocar\n"
            "a ningun tercero real. Nada de este fichero describe a una empresa real.\n\n"
            "## Sector\n\n"
            "Alimentacion y hosteleria: reposteria de ensayo para cafeterias, tiendas\n"
            "gourmet, hoteles con desayuno y restaurantes del area sintetica.\n\n"
            "## Producto\n\n"
            "Producto de pruebas del laboratorio. Sin catalogo real, sin precios reales.\n\n"
            "## Contacto comercial (remitente)\n\n"
            "- **Nombre:** Equipo del Laboratorio\n"
            "- **Cargo:** Ensayo sintetico\n"
            "- **Empresa:** Laboratorio Sintetico S.L. (no existe)\n"
            "- **Telefono:** 968000000\n"
            "- **Email:** equipo@laboratorio.invalid\n"),
        "ESTADO_ACTUAL.md": (
            "# Estado actual — laboratorio\n\n"
            "Tenant sintetico en ensayo. Sin operaciones reales en curso.\n"),
        "DECISIONES.md": (
            "# Decisiones — laboratorio\n\n"
            "Fichero sintetico. Las decisiones reales de un tenant viven en su\n"
            "propio diario, fuera del arbol del producto.\n"),
        "ULTIMOS_MOVIMIENTOS.md": (
            "# Ultimos movimientos — laboratorio\n\n"
            "Sin movimientos: el tenant sintetico no opera contra nadie.\n"),
    }


def registro_sintetico() -> dict:
    """Registro de tenants con UNA ficha: la del tenant sintetico.

    El registro real lista razones sociales de terceros y vive fuera del arbol
    (R-TENANT); este es su equivalente versionable para que la suite y el panel
    tengan un registro valido sin datos de cliente.
    """
    return {
        "_doc": ("Registro de tenants SINTETICO (R-TENANT). Ninguna ficha sin mandato "
                 "(D00 §2.3). No contiene ningun tercero real: la ficha describe al "
                 "tenant de laboratorio, que es ficcion."),
        "version": 1,
        "tenants": [{
            "id": EMPRESA,
            "razon_social": "Laboratorio Sintetico S.L. (no existe)",
            "vertical": "ensayo",
            "estado": "activo",
            "fecha_alta": FECHA_FIJA,
            "partner_id": None,
            "referencia_credenciales": "fuera del repo",
            "mandato": {
                "PROVISIONAL": True,
                "nivel_por_defecto": "BAJA",
                "techo_coste_diario_eur": 5.0,
                "max_emails_dia": 10,
                "max_llamadas_dia": 25,
                "horario_contacto": {"inicio": "10:00", "fin": "18:30",
                                     "dias": "L-V", "tz": "Europe/Madrid"},
                "ventana_repeticion_meses": 12,
            },
        }],
    }


def _escribir_json(ruta: Path, datos: dict) -> str:
    """Escribe JSON determinista y VERIFICA por relectura (E1)."""
    contenido = json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    if ruta.read_text(encoding="utf-8") != contenido:
        raise IOError(f"E1: desfase al escribir {ruta}")
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def generar_ficheros_tenant(dir_tenant: Path = DIR_TENANT_DEFECTO,
                            registro: Path = REGISTRO_DEFECTO) -> dict:
    """Emite los ficheros del tenant sintetico y su registro de tenants."""
    dir_tenant = Path(dir_tenant)
    salida: dict[str, dict] = {}
    ruta_arg = dir_tenant / "argumentario.json"
    salida["argumentario"] = {"ruta": str(ruta_arg),
                              "sha256": _escribir_json(ruta_arg, argumentario_sintetico())}
    ruta_icp = dir_tenant / "icp.json"
    salida["icp"] = {"ruta": str(ruta_icp),
                     "sha256": _escribir_json(ruta_icp, icp_sintetico())}
    for nombre, texto in aiact_sintetico().items():
        ruta = dir_tenant / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
        if ruta.read_text(encoding="utf-8") != texto:
            raise IOError(f"E1: desfase al escribir {ruta}")
        salida[f"aiact/{nombre}"] = {
            "ruta": str(ruta),
            "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest()}
    for nombre, contenido in brand_sintetico().items():
        ruta = dir_tenant / "brand" / nombre
        salida[f"brand/{nombre}"] = {"ruta": str(ruta),
                                     "sha256": _escribir_json(ruta, contenido)}
    salida["registro"] = {"ruta": str(registro),
                          "sha256": _escribir_json(Path(registro), registro_sintetico())}
    dir_diario = RAIZ / "diario" / EMPRESA
    for nombre, texto in diario_sintetico().items():
        ruta = dir_diario / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
        if ruta.read_text(encoding="utf-8") != texto:
            raise IOError(f"E1: desfase al escribir {ruta}")
        salida[f"diario/{nombre}"] = {
            "ruta": str(ruta),
            "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest()}
    return salida


def knowledge_defecto() -> Path:
    """Ruta del knowledge. Se resuelve al llamar, contra la raiz de datos."""
    from core.rutas import dir_state
    return dir_state() / "knowledge.json"


def generar(ruta_knowledge: Path | None = None, n: int = 50,
            buzon_propio: str | None = None, backup: bool = True) -> dict:
    """Escribe/reescribe la empresa 'laboratorio' en el knowledge. Devuelve resumen."""
    ruta = Path(ruta_knowledge) if ruta_knowledge is not None else knowledge_defecto()
    datos: dict = {}
    if ruta.exists():
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if backup:
            shutil.copy2(ruta, ruta.with_name(ruta.name + ".bak_laboratorio"))
    leads = dict(_lead(i, buzon_propio) for i in range(n))
    nodo = datos.get(EMPRESA) if isinstance(datos.get(EMPRESA), dict) else {}
    nodo = dict(nodo or {})
    nodo["lead"] = leads
    datos[EMPRESA] = nodo
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp_laboratorio")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)
    return {"empresa": EMPRESA, "leads": len(leads), "ruta": str(ruta),
            "emails_invalid": sum(1 for l in leads.values()
                                  if l["contacto"]["email"].endswith(".invalid"))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--knowledge", default=None)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--buzon-propio", default=None,
                    help="email PROPIO del operador para el ensayo SMTP (si no, .invalid)")
    ap.add_argument("--solo-ficheros", action="store_true",
                    help="emite solo los ficheros del tenant, sin tocar el knowledge")
    args = ap.parse_args()
    ficheros = generar_ficheros_tenant()
    for nombre, info in ficheros.items():
        print(f"{nombre}: {info['ruta']}  sha256={info['sha256'][:12]}...")
    if args.solo_ficheros:
        return
    resumen = generar(Path(args.knowledge) if args.knowledge else None,
                      n=args.n, buzon_propio=args.buzon_propio)
    print(f"tenant '{resumen['empresa']}': {resumen['leads']} leads sinteticos "
          f"({resumen['emails_invalid']} con email .invalid) en {resumen['ruta']}")


if __name__ == "__main__":
    main()
