from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi import status
from pydantic import BaseModel

from ..agent import runner
from ..agent.exceptions import InjectionDetectedError
from ..agent.schemas import RenewalBriefResponse
from ..core import debug as core_debug
from ..core.config import Settings, get_settings
from ..llm import ollama as ollama_client
from ..storage import object_store
from ..workers.job_queue import get_job_queue

router = APIRouter()


class RenewalBriefRequest(BaseModel):
    refresh: bool = False
    llm_provider: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None


@router.post("/ingest", tags=["ingestion"], status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    vendor_id: str,
    contract: UploadFile | None = File(default=None),
    invoices: UploadFile | None = File(default=None),
    usage: UploadFile | None = File(default=None),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    if not any([contract, invoices, usage]):
        raise HTTPException(status_code=400, detail="Provide at least one file to ingest")

    job_queue = get_job_queue(settings)
    job_ids: list[str] = []
    saved: dict[str, str] = {}
    uploads = {"contract": contract, "invoices": invoices, "usage": usage}

    for label, file in uploads.items():
        if not file:
            continue
        contents = await file.read()
        stored_path = object_store.store_file(vendor_id, f"{label}_{file.filename}", contents, doc_type=None)
        saved[label] = str(stored_path)

        job_id = job_queue.submit(vendor_id, f"{label}_{file.filename}", stored_path, label)
        job_ids.append(job_id)

    manifest = object_store.load_manifest(vendor_id)
    manifest.update(saved)
    object_store.save_manifest(vendor_id, manifest)

    return {
        "status": "accepted",
        "vendor_id": vendor_id,
        "message": "Ingestion scheduled",
        "job_ids": job_ids,
        "object_store": settings.object_store_bucket,
        "files": manifest,
    }


@router.get("/jobs/{job_id}", tags=["ingestion"])
async def get_job_status(job_id: str, settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    job_queue = get_job_queue(settings)
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.job_id,
        "vendor_id": job.vendor_id,
        "filename": job.filename,
        "doc_type": job.doc_type,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error": job.error,
        "result": job.result,
    }


@router.get("/jobs", tags=["ingestion"])
async def list_jobs(
    vendor_id: str | None = None,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    job_queue = get_job_queue(settings)
    jobs = job_queue.list_jobs(vendor_id)

    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "vendor_id": job.vendor_id,
                "filename": job.filename,
                "doc_type": job.doc_type,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
            }
            for job in jobs
        ]
    }


@router.post("/renewal-brief/batch", tags=["agent"])
async def batch_renewal_brief(
    vendor_ids: list[str],
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    from ..scheduler.jobs import process_batch_renewal_briefs

    results = await process_batch_renewal_briefs(vendor_ids, settings)
    success_count = sum(1 for r in results if r["status"] == "success")

    return {
        "status": "completed",
        "total": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }


@router.post("/renewal-brief", response_model=RenewalBriefResponse, tags=["agent"])
async def renewal_brief(
    vendor_id: str,
    payload: RenewalBriefRequest,
    settings: Settings = Depends(get_settings),
) -> RenewalBriefResponse:
    provider = payload.llm_provider.strip().lower() if payload.llm_provider else None
    if provider and provider not in {"mock", "ollama"}:
        raise HTTPException(status_code=400, detail=f"Unsupported llm_provider: {payload.llm_provider}")
    settings_data = settings.model_dump()
    if provider:
        settings_data["llm_provider"] = provider
    if payload.ollama_base_url:
        settings_data["ollama_base_url"] = payload.ollama_base_url
    if payload.ollama_model:
        settings_data["ollama_model"] = payload.ollama_model
    request_settings = Settings(**settings_data)
    try:
        brief = runner.generate_brief(vendor_id=vendor_id, refresh=payload.refresh, settings=request_settings)
    except InjectionDetectedError as exc:
        raise HTTPException(status_code=400, detail=f"Prompt injection detected: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RenewalBriefResponse(status="ok", request_id=brief.request_id, brief=brief)


@router.get("/demo/renewal-brief", response_model=RenewalBriefResponse, tags=["demo"])
async def demo_renewal_brief(
    vendor_id: str = "vendor_123",
    refresh: bool = False,
    settings: Settings = Depends(get_settings),
) -> RenewalBriefResponse:
    examples = Path(settings.examples_dir)
    contract = examples / "sample_contract.pdf"
    invoices = examples / "invoices.csv"
    usage = examples / "usage.csv"
    if not contract.exists() or not invoices.exists() or not usage.exists():
        raise HTTPException(status_code=404, detail="Sample files not found")
    inputs = runner.InputPaths(contract_path=contract, invoices_path=invoices, usage_path=usage)
    try:
        brief = runner.generate_brief(vendor_id=vendor_id, refresh=refresh, settings=settings, inputs=inputs)
    except InjectionDetectedError as exc:
        raise HTTPException(status_code=400, detail=f"Prompt injection detected: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RenewalBriefResponse(status="ok", request_id=brief.request_id, brief=brief)


@router.get("/llm/health", tags=["system"])
async def llm_health(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    provider = settings.llm_provider.strip().lower()
    if provider != "ollama":
        return {"status": "skipped", "provider": provider}
    try:
        data = ollama_client.list_models(settings.ollama_base_url)
        model_names = [entry.get("name", "") for entry in data.get("models", []) if entry.get("name")]
        has_model = settings.ollama_model in model_names
        return {
            "status": "ok" if has_model else "missing_model",
            "provider": provider,
            "model": settings.ollama_model,
            "model_count": len(model_names),
            "sample_models": model_names[:5],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {exc}") from exc


@router.get("/debug/trace/{request_id}", tags=["debug"])
async def debug_trace(request_id: str) -> Dict[str, Any]:
    trace = core_debug.get_trace(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/debug/traces", tags=["debug"])
async def search_traces(
    vendor_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    error_type: str | None = None,
    limit: int = 100,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    from datetime import datetime

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    traces = core_debug.search_traces(
        vendor_id=vendor_id,
        start_date=start,
        end_date=end,
        error_type=error_type,
        limit=limit,
        settings=settings,
    )

    return {"traces": traces, "count": len(traces)}


@router.get("/debug/traces/export", tags=["debug"])
async def export_traces(
    vendor_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    from datetime import datetime

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    traces = core_debug.export_traces(
        vendor_id=vendor_id,
        start_date=start,
        end_date=end,
        settings=settings,
    )

    return {"traces": traces, "count": len(traces)}
