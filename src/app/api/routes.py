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

    saved: dict[str, str] = {}
    uploads = {"contract": contract, "invoices": invoices, "usage": usage}
    for label, file in uploads.items():
        if not file:
            continue
        contents = await file.read()
        stored_path = object_store.store_file(vendor_id, f"{label}_{file.filename}", contents)
        saved[label] = str(stored_path)

    manifest = object_store.load_manifest(vendor_id)
    manifest.update(saved)
    object_store.save_manifest(vendor_id, manifest)

    return {
        "status": "accepted",
        "vendor_id": vendor_id,
        "message": "Ingestion scheduled",
        "object_store": settings.object_store_bucket,
        "files": manifest,
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
