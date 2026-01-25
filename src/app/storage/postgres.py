from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock

import psycopg
from psycopg_pool import ConnectionPool

from ..core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_pool_lock = Lock()


def get_pool(settings: Settings | None = None) -> ConnectionPool:
    global _pool
    cfg = settings or get_settings()

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(
                    conninfo=cfg.database_url,
                    min_size=2,
                    max_size=10,
                    open=False,
                )
                _pool.open()
                logger.info("Database connection pool initialized")

    return _pool


@contextmanager
def get_connection(settings: Settings | None = None, use_pool: bool = True):
    cfg = settings or get_settings()

    if use_pool:
        pool = get_pool(cfg)
        conn = pool.getconn()
        try:
            yield conn
        finally:
            pool.putconn(conn)
    else:
        conn = psycopg.connect(cfg.database_url, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()


def ensure_pgvector_extension(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    try:
        with get_connection(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                logger.info("pgvector extension enabled")
    except Exception as e:
        logger.warning(f"Failed to enable pgvector extension: {e}")
