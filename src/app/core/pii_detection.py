from __future__ import annotations

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


class PIIDetector:
    def __init__(self) -> None:
        self.patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }

    def detect(self, text: str) -> Dict[str, List[str]]:
        detected: Dict[str, List[str]] = {}
        for pii_type, pattern in self.patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                detected[pii_type] = list(set(matches))
        return detected

    def redact(self, text: str, replacement: str = "[REDACTED]") -> str:
        detected = self.detect(text)
        redacted = text

        for pii_type, values in detected.items():
            for value in values:
                redacted = redacted.replace(value, replacement)

        return redacted

    def has_pii(self, text: str) -> bool:
        return len(self.detect(text)) > 0


_pii_detector: PIIDetector | None = None


def get_pii_detector() -> PIIDetector:
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector


def detect_pii(text: str) -> Dict[str, List[str]]:
    detector = get_pii_detector()
    return detector.detect(text)


def redact_pii(text: str, replacement: str = "[REDACTED]") -> str:
    detector = get_pii_detector()
    return detector.redact(text, replacement)


def has_pii(text: str) -> bool:
    detector = get_pii_detector()
    return detector.has_pii(text)
