from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

from ..agent import runner
from ..core.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def process_batch_renewal_briefs(vendor_ids: List[str], settings: Settings) -> List[dict]:
    results = []
    for vendor_id in vendor_ids:
        try:
            brief = runner.generate_brief(vendor_id, refresh=False, settings=settings)
            results.append(
                {
                    "vendor_id": vendor_id,
                    "status": "success",
                    "request_id": brief.request_id,
                }
            )
        except Exception as e:
            logger.error(f"Failed to generate brief for {vendor_id}: {e}")
            results.append(
                {
                    "vendor_id": vendor_id,
                    "status": "failed",
                    "error": str(e),
                }
            )
    return results


async def scheduled_renewal_briefs(settings: Settings) -> None:
    logger.info("Running scheduled renewal briefs")
    try:
        from ..storage.postgres import get_connection

        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT vendor_id FROM document_chunks
                    WHERE created_at > NOW() - INTERVAL '30 days'
                    """
                )
                vendor_ids = [row[0] for row in cur.fetchall()]

        if vendor_ids:
            results = await process_batch_renewal_briefs(vendor_ids, settings)
            success_count = sum(1 for r in results if r["status"] == "success")
            logger.info(f"Scheduled briefs completed: {success_count}/{len(results)} successful")
    except Exception as e:
        logger.error(f"Scheduled renewal briefs failed: {e}")
