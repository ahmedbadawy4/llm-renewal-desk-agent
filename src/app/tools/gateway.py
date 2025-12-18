from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from fastapi import HTTPException, status


@dataclass
class Tool:
    name: str
    handler: Callable[..., Any]
    description: str


class ToolGateway:
    def __init__(self, allowlist: dict[str, Tool]):
        self.allowlist = allowlist

    def call(self, tool_name: str, **kwargs: Any) -> Any:
        tool = self.allowlist.get(tool_name)
        if not tool:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tool not allowed")
        return tool.handler(**kwargs)


__all__ = ["Tool", "ToolGateway"]
