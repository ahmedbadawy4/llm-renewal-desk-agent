from __future__ import annotations

import logging
from contextlib import contextmanager

import psycopg

from ..core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@contextmanager
def get_connection(settings: Settings | None = None):
    cfg = settings or get_settings()
    conn = psycopg.connect(cfg.database_url, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()
