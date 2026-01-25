from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..storage.postgres import get_connection
from ..core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def record_trace(request_id: str, payload: Dict[str, Any], settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    try:
        vendor_id = payload.get("vendor_id")
        with get_connection(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO debug_traces (request_id, vendor_id, payload, created_at)
                    VALUES (%s, %s, %s::jsonb, %s)
                    ON CONFLICT (request_id) DO UPDATE SET
                        vendor_id = EXCLUDED.vendor_id,
                        payload = EXCLUDED.payload,
                        created_at = EXCLUDED.created_at
                    """,
                    (request_id, vendor_id, json.dumps(payload), datetime.now(timezone.utc)),
                )
    except Exception as e:
        logger.warning(f"Failed to record trace: {e}")


def get_trace(request_id: str, settings: Settings | None = None) -> Optional[Dict[str, Any]]:
    cfg = settings or get_settings()
    try:
        with get_connection(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT request_id, vendor_id, payload, created_at
                    FROM debug_traces
                    WHERE request_id = %s
                    """,
                    (request_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "request_id": row[0],
                    "vendor_id": row[1],
                    "created_at": row[3].isoformat() if row[3] else None,
                    **row[2],
                }
    except Exception as e:
        logger.warning(f"Failed to get trace: {e}")
        return None


def search_traces(
    vendor_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    error_type: Optional[str] = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> List[Dict[str, Any]]:
    cfg = settings or get_settings()
    try:
        with get_connection(cfg) as conn:
            with conn.cursor() as cur:
                query = "SELECT request_id, vendor_id, payload, created_at FROM debug_traces WHERE 1=1"
                params: List[Any] = []

                if vendor_id:
                    query += " AND vendor_id = %s"
                    params.append(vendor_id)

                if start_date:
                    query += " AND created_at >= %s"
                    params.append(start_date)

                if end_date:
                    query += " AND created_at <= %s"
                    params.append(end_date)

                if error_type:
                    query += " AND payload @> %s::jsonb"
                    params.append(json.dumps({"validation": {"error_type": error_type}}))

                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                results = []
                for row in cur.fetchall():
                    results.append(
                        {
                            "request_id": row[0],
                            "vendor_id": row[1],
                            "created_at": row[3].isoformat() if row[3] else None,
                            **row[2],
                        }
                    )
                return results
    except Exception as e:
        logger.warning(f"Failed to search traces: {e}")
        return []


def export_traces(
    vendor_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    settings: Settings | None = None,
) -> List[Dict[str, Any]]:
    return search_traces(vendor_id, start_date, end_date, None, limit=10000, settings=settings)
