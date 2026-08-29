"""PostgreSQL access for NEUROSCOPE research extraction."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PgConnection

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_database_url() -> str:
    """Load DATABASE_URL from the project-root .env files."""
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / ".env.local", override=True)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and add the "
            "Supabase PostgreSQL connection string."
        )
    return database_url


@contextmanager
def connect() -> Generator[PgConnection, None, None]:
    """Open a psycopg2 connection to the Supabase Postgres database."""
    connection = psycopg2.connect(load_database_url())
    try:
        yield connection
    finally:
        connection.close()
