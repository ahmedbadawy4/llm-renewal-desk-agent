from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


def chat_completion(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[Dict[str, str]],
    max_tokens: int = 800,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        return {
            "message": {
                "content": data["choices"][0]["message"]["content"],
                "role": data["choices"][0]["message"]["role"],
            },
            "usage": {
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
            },
        }
