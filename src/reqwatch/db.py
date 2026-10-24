"""Postgres access. DATABASE_URL comes only from the environment
(GitHub Actions secret in CI, gitignored .env locally). Never logged.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
NEON_FREE_LIMIT_BYTES = 1 * 1024 * 1024 * 1024  # Neon Free: 1 GB per project (Phase 0, checked Oct 2026)


def connect(database_url: str | None = None) -> psycopg.Connection:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (env / GitHub Actions secret). Refusing to guess.")
    return psycopg.connect(url)


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text())
    conn.commit()


def database_size_bytes(conn: psycopg.Connection) -> int:
    row = conn.execute("select pg_database_size(current_database())").fetchone()
    return int(row[0])


def project_months_until_limit(current_bytes: int, growth_bytes_per_run: int | None,
                               runs_per_day: int = 1, limit_bytes: int = NEON_FREE_LIMIT_BYTES) -> float | None:
    """Projected months until the storage limit at the observed per-run growth.

    Returns None when growth is not positive/measured yet -- the report must
    say "not measured yet" rather than print an invented number.
    """
    if growth_bytes_per_run is None or growth_bytes_per_run <= 0:
        return None
    remaining = limit_bytes - current_bytes
    if remaining <= 0:
        return 0.0
    runs_left = remaining / growth_bytes_per_run
    return round(runs_left / runs_per_day / 30.44, 2)
