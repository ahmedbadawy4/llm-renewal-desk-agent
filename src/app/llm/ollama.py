from __future__ import annotations

from typing import Any, Dict

import httpx


def chat_completion(base_url: str, payload: Dict[str, Any], timeout_seconds: float = 60.0) -> Dict[str, Any]:
    """
    Call Ollama's chat endpoint and return the parsed JSON response.
    """
    with httpx.Client(base_url=base_url, timeout=timeout_seconds) as client:
        response = client.post("/api/chat", json=payload, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    return response.json()


def list_models(base_url: str, timeout_seconds: float = 10.0) -> Dict[str, Any]:
    """
    Fetch Ollama's available model list.
    """
    with httpx.Client(base_url=base_url, timeout=timeout_seconds) as client:
        response = client.get("/api/tags")
    response.raise_for_status()
    return response.json()
