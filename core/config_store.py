"""Persistencia de configuración. Backend pluggable: memoria o PostgreSQL.

Guarda las empresas registradas y ajustes clave/valor que deben sobrevivir reinicios.
`get_config()` usa Postgres si DATABASE_URL está disponible; si no, memoria.

NOTA: PostgresConfig está escrito según la API de psycopg2, pendiente de validación en
vivo con `docker compose up`. No probado contra un Postgres real en este entorno.
"""
from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod


class ConfigStore(ABC):
    @abstractmethod
    def add_company(self, slug: str, nombre: str, sector: str = "", contexto: str = "") -> None: ...

    @abstractmethod
    def list_companies(self) -> list[dict]: ...

    @abstractmethod
    def get_setting(self, key: str, default: str | None = None) -> str | None: ...

    @abstractmethod
    def set_setting(self, key: str, value: str) -> None: ...


class InMemoryConfig(ConfigStore):
    def __init__(self) -> None:
        self._companies: dict[str, dict] = {}
        self._settings: dict[str, str] = {}

    def add_company(self, slug, nombre, sector="", contexto=""):
        self._companies[slug] = {"slug": slug, "nombre": nombre, "sector": sector, "contexto": contexto}

    def list_companies(self):
        return [self._companies[s] for s in sorted(self._companies)]

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = str(value)


class PostgresConfig(ConfigStore):
    def __init__(self, dsn: str | None = None) -> None:
        import psycopg2
        dsn = dsn or os.getenv("DATABASE_URL")
        if not dsn:
            # Sin DSN/credenciales por defecto en el código (auditoría 2026-06-07).
            raise RuntimeError("DATABASE_URL no definido: requerido para PostgresConfig.")
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        with self._conn.cursor() as c:
            c.execute("CREATE TABLE IF NOT EXISTS empresas "
                      "(slug TEXT PRIMARY KEY, nombre TEXT, sector TEXT, contexto TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

    def add_company(self, slug, nombre, sector="", contexto=""):
        with self._conn.cursor() as c:
            c.execute(
                "INSERT INTO empresas (slug, nombre, sector, contexto) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (slug) DO UPDATE SET nombre=EXCLUDED.nombre, "
                "sector=EXCLUDED.sector, contexto=EXCLUDED.contexto",
                (slug, nombre, sector, contexto),
            )

    def list_companies(self):
        with self._conn.cursor() as c:
            c.execute("SELECT slug, nombre, sector, contexto FROM empresas ORDER BY slug")
            return [{"slug": r[0], "nombre": r[1], "sector": r[2], "contexto": r[3]} for r in c.fetchall()]

    def get_setting(self, key, default=None):
        with self._conn.cursor() as c:
            c.execute("SELECT value FROM settings WHERE key=%s", (key,))
            r = c.fetchone()
            return r[0] if r else default

    def set_setting(self, key, value):
        with self._conn.cursor() as c:
            c.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                      "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, str(value)))


def get_config() -> ConfigStore:
    """Postgres si DATABASE_URL está disponible; si no, memoria.

    Regla v0.2 §3.4 'NO SE PIERDE NADA': si el operador declaró DATABASE_URL pero
    Postgres falla, el sistema FALLA RUIDOSAMENTE (no degrada a memoria en silencio,
    lo que perdería empresas/settings al reiniciar) — mismo patrón que
    `core.knowledge.get_knowledge()`. Opt-in explícito para entornos efímeros:
    KAIZEN_ALLOW_MEMORY_CONFIG=1.
    """
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        try:
            return PostgresConfig()
        except Exception as e:
            if os.getenv("KAIZEN_ALLOW_MEMORY_CONFIG") == "1":
                print(f"[config_store] PostgresConfig falló: {e}. Fallback a "
                      f"InMemoryConfig PERMITIDO por flag (empresas/settings no persistirán).",
                      file=sys.stderr, flush=True)
                return InMemoryConfig()
            raise RuntimeError(
                f"No se pudo abrir el ConfigStore persistente (DATABASE_URL definido): {e}. "
                f"Arregla Postgres/credenciales, o exporta KAIZEN_ALLOW_MEMORY_CONFIG=1 "
                f"si aceptas perder empresas/settings."
            ) from e
    return InMemoryConfig()
