from __future__ import annotations

from typing import Iterable

INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous",
    "disregard",
    "send credentials",
    "http://",
    "https://",
    "email credentials",
    "leak",
)


def contains_prompt_injection(text: str, patterns: Iterable[str] | None = None) -> bool:
    haystack = text.lower()
    pats = patterns or INJECTION_PATTERNS
    return any(pat in haystack for pat in pats)
