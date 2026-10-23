"""PostgreSQL access for NEUROSCOPE research extraction."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PgConnection

from ml.config import PROJECT_ROOT


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
    connection = None
    try:
        connection = psycopg2.connect(
            load_database_url(), connect_timeout=10, options="-c statement_timeout=120000"
        )
        connection.set_session(readonly=True)
    except psycopg2.Error:
        if connection is not None:
            connection.close()
        raise RuntimeError(
            "Database connection failed. Check DATABASE_URL, credentials and network reachability."
        ) from None
    try:
        yield connection
    finally:
        connection.close()
