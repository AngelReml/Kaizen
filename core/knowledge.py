"""Memoria de conocimiento por empresa (Capa 2) — aislamiento estricto.

Cada empresa tiene su propio espacio. La interfaz OBLIGA a pasar `company` en toda
operación, así que es imposible consultar datos sin acotar la empresa: el aislamiento
es estructural, no una convención.

Backend pluggable:
- `InMemoryKnowledge`: para tests y desarrollo sin disco.
- `JsonKnowledge`: persistente sobre archivo JSON único (atómico + thread-safe).
- `Neo4jKnowledge`: para producción con grafo. Pendiente de validación contra Neo4j real.

`get_knowledge()` elige por defecto: Neo4j si NEO4J_URI responde; si no, JsonKnowledge
en `state/knowledge.json`; si la escritura a disco falla, InMemoryKnowledge. La regla del
v0.2 §3.4 "NO SE PIERDE NADA" exige persistencia real por defecto.
"""
from __future__ import annotations

import copy
import json
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from core.bloqueo import bloqueo_exclusivo


class KnowledgeStore(ABC):
    @abstractmethod
    def add(self, company: str, tipo: str, key: str, data: dict) -> None: ...

    @abstractmethod
    def get(self, company: str, tipo: str, key: str) -> dict | None: ...

    @abstractmethod
    def all(self, company: str, tipo: str | None = None) -> dict: ...

    @abstractmethod
    def companies(self) -> list[str]: ...


class InMemoryKnowledge(KnowledgeStore):
    """Grafo en memoria: company -> tipo -> key -> data. Aislado por construcción."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, dict]]] = {}

    def add(self, company: str, tipo: str, key: str, data: dict) -> None:
        self._data.setdefault(company, {}).setdefault(tipo, {})[key] = data

    def get(self, company: str, tipo: str, key: str) -> dict | None:
        valor = self._data.get(company, {}).get(tipo, {}).get(key)
        return copy.deepcopy(valor)

    def all(self, company: str, tipo: str | None = None) -> dict:
        comp = self._data.get(company, {})
        if tipo is None:
            return copy.deepcopy({t: dict(v) for t, v in comp.items()})
        return copy.deepcopy(dict(comp.get(tipo, {})))

    def companies(self) -> list[str]:
        return sorted(self._data)

    def delete(self, company: str, tipo: str, key: str) -> bool:
        if key in self._data.get(company, {}).get(tipo, {}):
            del self._data[company][tipo][key]
            return True
        return False


class Neo4jKnowledge(KnowledgeStore):
    """Grafo Neo4j. Aislamiento por propiedad `company` en cada nodo (compatible Community).

    NOTA: escrito según la API del driver `neo4j`, pendiente de validación en vivo con
    `docker compose up`. No probado contra un Neo4j real en este entorno.
    """

    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None) -> None:
        import os
        from neo4j import GraphDatabase
        password = password or os.getenv("NEO4J_PASSWORD")
        if not password:
            # Sin credencial por defecto en el código (auditoría 2026-06-07).
            raise RuntimeError("NEO4J_PASSWORD no definido: requerido para Neo4jKnowledge "
                               "(no hay contraseña por defecto).")
        self._driver = GraphDatabase.driver(
            uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(user or os.getenv("NEO4J_USER", "neo4j"), password),
        )

    def add(self, company: str, tipo: str, key: str, data: dict) -> None:
        import json
        with self._driver.session() as s:
            s.run(
                "MERGE (e:Entidad {company:$c, tipo:$t, key:$k}) SET e.data=$d",
                c=company, t=tipo, k=key, d=json.dumps(data, ensure_ascii=False),
            )

    def get(self, company: str, tipo: str, key: str) -> dict | None:
        import json
        with self._driver.session() as s:
            rec = s.run(
                "MATCH (e:Entidad {company:$c, tipo:$t, key:$k}) RETURN e.data AS data",
                c=company, t=tipo, k=key,
            ).single()
        return json.loads(rec["data"]) if rec and rec["data"] else None

    def all(self, company: str, tipo: str | None = None) -> dict:
        import json
        with self._driver.session() as s:
            if tipo is None:
                recs = s.run(
                    "MATCH (e:Entidad {company:$c}) RETURN e.tipo AS tipo, e.key AS key, e.data AS data",
                    c=company,
                )
                out: dict = {}
                for r in recs:
                    out.setdefault(r["tipo"], {})[r["key"]] = json.loads(r["data"]) if r["data"] else {}
                return out
            recs = s.run(
                "MATCH (e:Entidad {company:$c, tipo:$t}) RETURN e.key AS key, e.data AS data",
                c=company, t=tipo,
            )
            return {r["key"]: (json.loads(r["data"]) if r["data"] else {}) for r in recs}

    def companies(self) -> list[str]:
        with self._driver.session() as s:
            recs = s.run("MATCH (e:Entidad) RETURN DISTINCT e.company AS c ORDER BY c")
            return [r["c"] for r in recs]

    def close(self) -> None:
        self._driver.close()


class JsonKnowledge(KnowledgeStore):
    """Backend persistente sobre un único archivo JSON (mismo schema que InMemoryKnowledge).

    Escritura atómica (tmp + os.replace) para que un crash a media escritura no corrompa
    el archivo. Lock para mutaciones concurrentes. Cumple la regla v0.2 §3.4 'NO SE PIERDE
    NADA' sin necesidad de Neo4j corriendo.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Candado de HILO (serializa llamadas dentro de este proceso). El candado
        # ENTRE PROCESOS (`core.bloqueo.bloqueo_exclusivo`) se toma dentro de este,
        # en cada operación — un `threading.Lock` no sirve cuando el CLI y el panel
        # son procesos distintos escribiendo el mismo fichero (auditoría 2026-08-02).
        self._lock = threading.Lock()
        self._mtime: float | None = None
        if self.path.exists():
            try:
                self._data: dict = json.loads(self.path.read_text(encoding="utf-8"))
                self._mtime = self.path.stat().st_mtime
            except Exception as e:
                # JSON corrupto: NO degrademos en silencio (eso pierde datos).
                raise RuntimeError(f"Knowledge corrupto en {self.path}: {e}") from e
        else:
            self._data = {}

    def _recargar_si_cambio_locked(self) -> None:
        """Recarga `self._data` desde disco si otro proceso escribió desde la última
        lectura de ESTE proceso. Debe llamarse con `self._lock` Y el candado entre
        procesos ya tomados. `add()`/`delete()` flushean inmediatamente tras mutar
        (no hay escritura diferida), así que no hay cambios locales pendientes que
        fusionar: una recarga simple basta."""
        if not self.path.exists():
            return
        mtime = self.path.stat().st_mtime
        if self._mtime is not None and mtime == self._mtime:
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            self._mtime = mtime
        except Exception as e:
            raise RuntimeError(f"Knowledge corrupto en {self.path}: {e}") from e

    def add(self, company: str, tipo: str, key: str, data: dict) -> None:
        with self._lock, bloqueo_exclusivo(self.path):
            self._recargar_si_cambio_locked()
            self._data.setdefault(company, {}).setdefault(tipo, {})[key] = data
            self._flush_locked()

    def get(self, company: str, tipo: str, key: str) -> dict | None:
        with self._lock, bloqueo_exclusivo(self.path):
            self._recargar_si_cambio_locked()
            valor = self._data.get(company, {}).get(tipo, {}).get(key)
            return copy.deepcopy(valor)

    def all(self, company: str, tipo: str | None = None) -> dict:
        with self._lock, bloqueo_exclusivo(self.path):
            self._recargar_si_cambio_locked()
            comp = self._data.get(company, {})
            if tipo is None:
                return copy.deepcopy({t: dict(v) for t, v in comp.items()})
            return copy.deepcopy(dict(comp.get(tipo, {})))

    def companies(self) -> list[str]:
        with self._lock, bloqueo_exclusivo(self.path):
            self._recargar_si_cambio_locked()
            return sorted(self._data)

    def delete(self, company: str, tipo: str, key: str) -> bool:
        """Útil para limpieza puntual (p. ej. retirar de la cola de aprobación)."""
        with self._lock, bloqueo_exclusivo(self.path):
            self._recargar_si_cambio_locked()
            if key in self._data.get(company, {}).get(tipo, {}):
                del self._data[company][tipo][key]
                self._flush_locked()
                return True
            return False

    def _flush_locked(self) -> None:
        """Escritura atómica. El lock de hilo y el candado entre procesos deben
        estar tomados por el llamador."""
        tmp = self.path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.path)
            self._mtime = self.path.stat().st_mtime
        finally:
            # Si dumps/replace fallan, no dejamos un .tmp parcial que bloquee la
            # siguiente escritura.
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


_instance: KnowledgeStore | None = None
_instance_lock = threading.Lock()


def get_knowledge() -> KnowledgeStore:
    """Backend de conocimiento ACTIVO (singleton thread-safe).

    Prioridad:
      1. Neo4j si NEO4J_URI está definido y responde.
      2. JsonKnowledge en KAIZEN_KNOWLEDGE_PATH (default: state/knowledge.json), por la
         regla v0.2 §3.4 'NO SE PIERDE NADA'.
      3. InMemoryKnowledge como último recurso (solo si el disco falla).
    """
    global _instance
    with _instance_lock:
        if _instance is not None:
            return _instance
        if os.getenv("NEO4J_URI"):
            try:
                k = Neo4jKnowledge()
                k._driver.verify_connectivity()
                _instance = k
                return _instance
            except Exception:
                pass
        if os.getenv("KAIZEN_KNOWLEDGE_INMEMORY") == "1":
            _instance = InMemoryKnowledge()    # opt-in para tests que no quieren tocar disco
            return _instance
        ruta = os.getenv("KAIZEN_KNOWLEDGE_PATH")
        if not ruta:
            # Default: state/knowledge.json en la RAIZ DE DATOS (R-TENANT),
            # que por defecto vive fuera del arbol de git.
            from core.rutas import dir_state
            ruta = str(dir_state() / "knowledge.json")
        try:
            _instance = JsonKnowledge(ruta)
            return _instance
        except Exception as e:
            # Regla v0.2 §3.4 "NO SE PIERDE NADA": si el disco falla, el sistema FALLA
            # RUIDOSAMENTE para que el operador intervenga. Degradar a memoria en
            # silencio perdería todos los datos del día al reiniciar.
            # Opt-in para entornos efímeros: KAIZEN_ALLOW_MEMORY_FALLBACK=1.
            if os.getenv("KAIZEN_ALLOW_MEMORY_FALLBACK") == "1":
                print(f"[knowledge] JsonKnowledge falló en {ruta}: {e}. Fallback a "
                      f"InMemoryKnowledge PERMITIDO por flag (los datos no persistirán).",
                      flush=True)
                _instance = InMemoryKnowledge()
                return _instance
            raise RuntimeError(
                f"No se pudo abrir el Knowledge persistente en {ruta}: {e}. "
                f"Arregla disco/permisos/JSON, o exporta KAIZEN_ALLOW_MEMORY_FALLBACK=1 "
                f"si aceptas perder datos."
            ) from e


def reset_knowledge_singleton() -> None:
    """Limpia el singleton. Útil para tests que cambian el backend en ejecución."""
    global _instance
    with _instance_lock:
        _instance = None
