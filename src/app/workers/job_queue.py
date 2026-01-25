from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from ..core.config import Settings
from .parser import process_document_async

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    vendor_id: str
    filename: str
    file_path: Path
    doc_type: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict] = None


class JobQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()
        self._running = False

    def submit(
        self,
        vendor_id: str,
        filename: str,
        file_path: Path,
        doc_type: str,
    ) -> str:
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            vendor_id=vendor_id,
            filename=filename,
            file_path=file_path,
            doc_type=doc_type,
        )

        with self._lock:
            self._jobs[job_id] = job

        asyncio.create_task(self._process_job(job))
        return job_id

    async def _process_job(self, job: Job) -> None:
        with self._lock:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)

        try:
            result = await process_document_async(
                job.vendor_id,
                job.filename,
                job.file_path,
                job.doc_type,
                self.settings,
            )

            with self._lock:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.result = result
        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            with self._lock:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                job.error = str(e)

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, vendor_id: Optional[str] = None) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
            if vendor_id:
                jobs = [j for j in jobs if j.vendor_id == vendor_id]
            return sorted(jobs, key=lambda j: j.created_at, reverse=True)


_global_queue: Optional[JobQueue] = None


def get_job_queue(settings: Settings) -> JobQueue:
    global _global_queue
    if _global_queue is None:
        _global_queue = JobQueue(settings)
    return _global_queue
