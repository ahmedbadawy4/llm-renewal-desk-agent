from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional


@dataclass
class DebugTrace:
    request_id: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_LOCK = Lock()
_TRACES: Dict[str, DebugTrace] = {}
_MAX_TRACES = 200


def record_trace(request_id: str, payload: Dict[str, Any]) -> None:
    with _LOCK:
        _TRACES[request_id] = DebugTrace(request_id=request_id, payload=payload)
        if len(_TRACES) > _MAX_TRACES:
            _TRACES.pop(next(iter(_TRACES)))


def get_trace(request_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        trace = _TRACES.get(request_id)
    if not trace:
        return None
    return {
        "request_id": trace.request_id,
        "created_at": trace.created_at,
        **trace.payload,
    }
