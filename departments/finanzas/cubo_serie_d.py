"""Cubo Finanzas segun KAIZEN-D04: Pista A (FA0-FA2: liquidacion reproducible,
conciliacion, aging) y NUCLEO de Pista B (FB1/FB3: cadena SHA-256 por NIF con
escritor serializado R-11, anulacion-como-registro con borrado IMPOSIBLE por
construccion, remisor con reintentos contra simulador local GR-08, verificacion
de cadena independiente).

AVISO LEGAL HONESTO (D04 §11.2 y FB0): el mapeo de campos del RFA contra los
anexos oficiales de la Orden HAC/1177/2024, el QR tributario y la certificacion
son FB0/FB2 y NO estan hechos — este motor NO ES CONFORME AUN y no debe emitir
facturas reales. `NO_CONFORME_TODAVIA = True` lo hace fisico. R-01 de D09: el
fallo de remision JAMAS bloquea la emision; solo la cadena rota la bloquea.
R-19: banca solo por import manual CSV; jamas credenciales.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import threading
from datetime import datetime, timezone

from core.rue import Sobre, nuevo_id

NO_CONFORME_TODAVIA = True     # FB0 (mapeo oficial) + certificacion externa pendientes


class VerifactuNoConforme(RuntimeError):
    """R-11: se intento emitir a un destinatario real con el motor NO conforme todavia.
    Fail-closed: la factura no se crea ni se remite."""


# ── Dinero fiscal en Decimal (R-12, auditoria 2026-07-20) ─────────────────────
# Antes: float + round() bancario (round(2.675,2)=2.67 vs 2.68 fiscal) e IVA fijo 21%.
# Ahora: Decimal con ROUND_HALF_UP en todo calculo monetario y tipos de IVA validados.
from decimal import Decimal, ROUND_HALF_UP     # noqa: E402

# Tipos de IVA vigentes en España (general, reducido, superreducido, exento).
IVA_VALIDOS = (Decimal("0.21"), Decimal("0.10"), Decimal("0.04"), Decimal("0.00"))


class IVAInvalido(ValueError):
    """R-12: tipo de IVA fuera de los vigentes (21/10/4/exento)."""


def _eur(x) -> float:
    """Redondeo monetario correcto: media-arriba a 2 decimales (no binario)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _cuota_iva(neto, iva_pct) -> float:
    return float((Decimal(str(neto)) * Decimal(str(iva_pct)))
                 .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _canon(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ── Pista A: Liquidador (FA0) ────────────────────────────────────────────────

class Liquidador:
    """Numeros que el cliente y el operador pueden defender: reproducibles o error."""

    def __init__(self, knowledge, tenant: str, *, bitacora=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora

    def calcular(self, periodo: str, *, costes_directos: dict, comision_pct: float = 0.5,
                 version_anexo: str = "anexo-I-v1") -> dict:
        """Agrega pedidos ATRIBUIDOS del periodo. PENDIENTE_VALIDACION queda FUERA
        con informe (D04 A1). Determinista: recalcular = mismos numeros."""
        pedidos, fuera = [], []
        for pid, p in sorted(self.k.all(self.tenant, "pedido_atribuido").items()):
            if not p.get("ts", "").startswith(periodo):
                continue
            if p["estado"] != "ATRIBUIDO":
                fuera.append(pid)
                continue
            bruto = _eur(p.get("importe_bruto") or 0.0)
            coste = _eur(costes_directos.get(pid, 0.0))
            neto = _eur(bruto - coste)                         # R-12: Decimal ROUND_HALF_UP
            pedidos.append({"pedido_id": pid, "via": p["via"], "importe_bruto": bruto,
                            "costes_directos": coste, "beneficio_neto": neto,
                            "comision": _eur(Decimal(str(neto)) * Decimal(str(comision_pct)))})
        liq = {"periodo": periodo, "tenant": self.tenant, "pedidos": pedidos,
               "excluidos_pendientes": fuera,
               "total_atribuible": _eur(sum(p["beneficio_neto"] for p in pedidos)),
               "total_comision": _eur(sum(p["comision"] for p in pedidos)),
               "hash_pedidos": _sha(_canon([p["pedido_id"] for p in pedidos])),
               "version_anexo": version_anexo, "comision_pct": comision_pct}
        liq["hash_liquidacion"] = _sha(_canon(liq))
        self.k.add(self.tenant, "liquidacion", f"{periodo}", liq)
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo="finanzas.liquidacion.calculada",
                                  payload={"periodo": periodo,
                                           "total_comision": liq["total_comision"],
                                           "hash_liquidacion": liq["hash_liquidacion"]},
                                  origen="finanzas.liquidador"))
        return liq


# ── Pista A: Conciliador (FA2) — solo import manual (R-19) ──────────────────

class Conciliador:
    def __init__(self, knowledge, tenant: str, *, tolerancia_eur: float = 0.01) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.tol = tolerancia_eur

    def importar_csv(self, contenido_csv: str) -> list[dict]:
        """Import manual de extracto (fecha,concepto,importe). Jamas credenciales bancarias."""
        movimientos = []
        for fila in csv.DictReader(io.StringIO(contenido_csv)):
            m = {"id": nuevo_id(), "fecha": fila["fecha"], "concepto": fila["concepto"],
                 "importe": _eur(fila["importe"]), "estado": "SIN_CONCILIAR"}
            self.k.add(self.tenant, "movimiento_banco", m["id"], m)
            movimientos.append(m)
        return movimientos

    def proponer(self) -> list[dict]:
        """Matching determinista por importe dentro de tolerancia; el humano confirma."""
        propuestas = []
        facturas = {fid: f for fid, f in self.k.all(self.tenant, "factura").items()
                    if f.get("estado_cobro", "PENDIENTE") == "PENDIENTE"}
        for m in self.k.all(self.tenant, "movimiento_banco").values():
            if m["estado"] != "SIN_CONCILIAR":
                continue
            for fid, f in sorted(facturas.items()):
                if abs(f["importe_total"] - m["importe"]) <= self.tol:
                    propuestas.append({"movimiento_ref": m["id"], "factura_ref": fid,
                                       "delta": round(f["importe_total"] - m["importe"], 2)})
                    facturas.pop(fid)
                    break
        return propuestas

    def confirmar(self, propuesta: dict, *, por: str) -> dict:
        if por != "operador":
            raise PermissionError("la conciliacion la confirma el operador (BAJA)")
        f = self.k.get(self.tenant, "factura", propuesta["factura_ref"])
        m = self.k.get(self.tenant, "movimiento_banco", propuesta["movimiento_ref"])
        f["estado_cobro"] = "COBRADO"; m["estado"] = "CONCILIADO"
        self.k.add(self.tenant, "factura", propuesta["factura_ref"], f)
        self.k.add(self.tenant, "movimiento_banco", propuesta["movimiento_ref"], m)
        return {"factura": propuesta["factura_ref"], "estado": "COBRADO"}

    def aging(self, *, ahora: datetime | None = None) -> list[dict]:
        ahora = ahora or datetime.now(timezone.utc)
        out = []
        for fid, f in sorted(self.k.all(self.tenant, "factura").items()):
            if f.get("estado_cobro", "PENDIENTE") == "PENDIENTE":
                dias = (ahora - datetime.fromisoformat(f["fecha_emision"])).days
                out.append({"factura_ref": fid, "dias_pendiente": dias})
        return sorted(out, key=lambda x: -x["dias_pendiente"])


# ── Pista B nucleo: motor SIF (FB1/FB3) ──────────────────────────────────────

def nif_valido(nif: str) -> bool:
    """Validacion algoritmica del digito de control (DNI/NIE). Determinista, sin datos legales."""
    letras = "TRWAGMYFPDXBNJZSQVHLCKE"
    nif = nif.strip().upper()
    if len(nif) != 9:
        return False
    cuerpo, letra = nif[:-1], nif[-1]
    if cuerpo[0] in "XYZ":
        cuerpo = str("XYZ".index(cuerpo[0])) + cuerpo[1:]
    if not cuerpo.isdigit():
        return False
    return letras[int(cuerpo) % 23] == letra


# R-11: el candado de escritor-unico-por-NIF NO puede vivir en la instancia — si
# MotorSIF se instancia por-peticion, cada instancia trae su propio dict de locks
# y la serializacion entre peticiones concurrentes queda anulada. Registro a
# nivel de MODULO, compartido por todas las instancias, con clave (tenant, nif)
# (antes solo por nif, lo que ademas mezclaba tenants distintos en el mismo lock).
_locks_nif: dict[tuple[str, str], threading.Lock] = {}
_locks_nif_guard = threading.Lock()


def _lock_nif_global(tenant: str, nif: str) -> threading.Lock:
    with _locks_nif_guard:
        return _locks_nif.setdefault((tenant, nif), threading.Lock())


class MotorSIF:
    """Cadena legal por NIF-obligado, separada de la bitacora operativa (dos cadenas,
    mismo ADN). Borrado: NO EXISTE como ruta de codigo; anular = registro nuevo."""

    def __init__(self, knowledge, tenant: str, *, bitacora=None, remisor=None) -> None:
        self.k = knowledge
        self.tenant = tenant
        self.b = bitacora
        self.remisor = remisor or AEATSimulador()

    def _lock_nif(self, nif: str) -> threading.Lock:
        return _lock_nif_global(self.tenant, nif)

    def _registros(self, nif: str) -> list[tuple[str, dict]]:
        return sorted(((k_, r) for k_, r in self.k.all(self.tenant, "sif_registro").items()
                       if r["nif_obligado"] == nif))

    def emitir(self, *, nif_obligado: str, nif_destinatario: str, serie: str,
               importe_neto: float, iva_pct: float = 0.21, descripcion: str = "") -> dict:
        # R-11 (auditoria 2026-07-20): la salvaguarda era decorativa (cuerpo `pass`), asi que
        # emitir() creaba y "remitia" la factura igual. Ahora es REAL: mientras el sistema no
        # sea conforme (FB0 + certificacion pendientes), SOLO se emite a destinatarios
        # sinteticos; una factura a un NIF real se RECHAZA fail-closed (no depende de "no esta
        # en el panel"). Levantar el candado es cerrar FB0 + poner NO_CONFORME_TODAVIA=False.
        destinatario_sintetico = str(nif_destinatario).startswith("SINTETICO-")
        if NO_CONFORME_TODAVIA and not destinatario_sintetico:
            raise VerifactuNoConforme(
                "Verifactu NO CONFORME todavia (FB0/certificacion pendientes): prohibido emitir "
                f"a un destinatario real ({nif_destinatario!r}). Solo destinatarios 'SINTETICO-' "
                "hasta cerrar FB0 (D04 §16) — es un deber legal, no una opcion del panel.")
        if not (nif_valido(nif_obligado) or nif_obligado.startswith("SINTETICO-")):
            raise ValueError(f"NIF_INVALIDO: {nif_obligado!r} (validacion estructural, no LLM)")
        if importe_neto <= 0 or not serie:
            raise ValueError("INCOMPLETA: sin serie o importe la factura no existe")
        if Decimal(str(iva_pct)) not in IVA_VALIDOS:          # R-12: IVA parametrizable validado
            raise IVAInvalido(f"tipo de IVA {iva_pct!r} no vigente (usa 0.21/0.10/0.04/0.00)")
        neto = _eur(importe_neto)                             # R-12: Decimal ROUND_HALF_UP
        cuota = _cuota_iva(importe_neto, iva_pct)
        with self._lock_nif(nif_obligado):                    # R-11: escritor unico por NIF
            regs = self._registros(nif_obligado)
            numero = len(regs) + 1
            huella_prev = regs[-1][1]["huella"] if regs else _sha(f"SIF||{nif_obligado}")
            rfa = {"tipo_registro": "ALTA", "numero": numero, "serie": serie,
                   "nif_obligado": nif_obligado, "nif_destinatario": nif_destinatario,
                   "descripcion": descripcion, "importe_neto": neto, "iva_pct": float(iva_pct),
                   "iva_cuota": cuota, "importe_total": _eur(neto + cuota),
                   "ts": _ts(), "mapeo_oficial": "PENDIENTE-FB0 (no conforme aun)"}
            rfa["huella_anterior"] = huella_prev
            rfa["huella"] = _sha(huella_prev + "||" + _canon({k: v for k, v in rfa.items()
                                                              if k not in ("huella_anterior", "huella")}))
            clave = f"{nif_obligado}::{numero:08d}"
            self.k.add(self.tenant, "sif_registro", clave, rfa)
        factura_id = f"{serie}-{numero:06d}"
        self.k.add(self.tenant, "factura",
                   factura_id, {"factura_id": factura_id, "rfa_ref": clave,
                                "importe_total": rfa["importe_total"],
                                "fecha_emision": rfa["ts"], "estado": "EMITIDA",
                                "estado_cobro": "PENDIENTE"})
        if self.b is not None:
            self.b.publicar(Sobre(tenant_id=self.tenant, tipo="finanzas.factura.emitida",
                                  payload={"factura_ref": factura_id, "rfa_ref": clave,
                                           "huella_hash": rfa["huella"]},
                                  origen="finanzas.sif"))
        # remision inmediata: deber legal, automatica en TODOS los niveles;
        # su fallo JAMAS invalida ni bloquea la factura (R-01)
        remision = self.remitir(clave)
        return {"factura_id": factura_id, "rfa_ref": clave, "huella": rfa["huella"],
                "remision": remision}

    def remitir(self, rfa_ref: str, *, max_reintentos: int = 3) -> dict:
        rfa = self.k.get(self.tenant, "sif_registro", rfa_ref)
        intentos = 0
        while intentos < max_reintentos:
            intentos += 1
            resp = self.remisor.enviar(rfa)
            if resp["codigo"] in ("ACEPTADA", "ACEPTADA_CON_ERRORES", "RECHAZADA"):
                self.k.add(self.tenant, "sif_remision", f"{rfa_ref}::{intentos}",
                           {"rfa_ref": rfa_ref, "codigo": resp["codigo"],
                            "intento": intentos, "ts": _ts()})
                return {"codigo": resp["codigo"], "intentos": intentos}
        self.k.add(self.tenant, "sif_remision", f"{rfa_ref}::pendiente",
                   {"rfa_ref": rfa_ref, "codigo": "PENDIENTE_REINTENTO",
                    "intento": intentos, "ts": _ts()})
        return {"codigo": "PENDIENTE_REINTENTO", "intentos": intentos}   # R-01: no bloquea

    def anular(self, rfa_ref: str, *, motivo: str, por: str) -> dict:
        """Anulacion = REGISTRO NUEVO encadenado. La original queda en la cadena, inmutable."""
        if por != "operador":
            raise PermissionError("anular es humano SIEMPRE (D04 §6)")
        original = self.k.get(self.tenant, "sif_registro", rfa_ref)
        if original is None:
            raise ValueError("registro inexistente")
        nif = original["nif_obligado"]
        with self._lock_nif(nif):
            regs = self._registros(nif)
            numero = len(regs) + 1
            huella_prev = regs[-1][1]["huella"]
            reg = {"tipo_registro": "ANULACION", "numero": numero, "anula_a": rfa_ref,
                   "motivo": motivo, "nif_obligado": nif, "ts": _ts()}
            reg["huella_anterior"] = huella_prev
            reg["huella"] = _sha(huella_prev + "||" + _canon({k: v for k, v in reg.items()
                                                              if k not in ("huella_anterior", "huella")}))
            self.k.add(self.tenant, "sif_registro", f"{nif}::{numero:08d}", reg)
        return reg

    def verificar_cadena(self, nif: str) -> dict:
        """Verificable FUERA del programa: recomputo puro (D04 §4.4/13.4)."""
        prev = _sha(f"SIF||{nif}")
        for clave, r in self._registros(nif):
            cuerpo = {k: v for k, v in r.items() if k not in ("huella_anterior", "huella")}
            if r["huella_anterior"] != prev or r["huella"] != _sha(prev + "||" + _canon(cuerpo)):
                return {"integra": False, "punto": clave}
            prev = r["huella"]
        return {"integra": True, "registros": len(self._registros(nif))}


class AEATSimulador:
    """Entorno de pruebas local (GR-08). La integracion real con AEAT es externa (FB0/FB2)."""

    def __init__(self, fallos_antes_de_aceptar: int = 0) -> None:
        self.fallos = fallos_antes_de_aceptar
        self.recibidos: list[dict] = []

    def enviar(self, rfa: dict) -> dict:
        if self.fallos > 0:
            self.fallos -= 1
            return {"codigo": "TIMEOUT"}
        self.recibidos.append(rfa)
        if not rfa.get("nif_destinatario"):
            return {"codigo": "RECHAZADA"}
        return {"codigo": "ACEPTADA"}


# Borrado imposible POR CONSTRUCCION: este modulo no define ninguna funcion de
# borrado de registros SIF, y el test 13.7 verifica que no exista tal ruta.
