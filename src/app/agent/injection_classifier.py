from __future__ import annotations

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


class InjectionClassifier:
    def __init__(self) -> None:
        self.patterns = {
            "instruction_override": [
                r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
                r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
                r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
                r"override\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
            ],
            "credential_extraction": [
                r"send\s+(me\s+)?(your\s+)?(api\s+)?(key|token|credential|password|secret)",
                r"email\s+(me\s+)?(your\s+)?(api\s+)?(key|token|credential|password|secret)",
                r"output\s+(your\s+)?(api\s+)?(key|token|credential|password|secret)",
                r"reveal\s+(your\s+)?(api\s+)?(key|token|credential|password|secret)",
            ],
            "external_call": [
                r"http://",
                r"https://",
                r"curl\s+",
                r"wget\s+",
                r"fetch\s*\(",
            ],
            "data_exfiltration": [
                r"leak\s+",
                r"exfiltrate\s+",
                r"send\s+data\s+to",
                r"post\s+to\s+http",
            ],
            "role_impersonation": [
                r"you\s+are\s+(now\s+)?(a\s+)?(different|new|another)\s+",
                r"act\s+as\s+if\s+you\s+are",
                r"pretend\s+to\s+be",
            ],
            "system_prompt_extraction": [
                r"what\s+are\s+your\s+instructions?",
                r"show\s+me\s+your\s+system\s+prompt",
                r"repeat\s+your\s+instructions?",
                r"what\s+is\s+your\s+prompt",
            ],
        }

        self.weights = {
            "instruction_override": 1.0,
            "credential_extraction": 1.0,
            "external_call": 0.8,
            "data_exfiltration": 1.0,
            "role_impersonation": 0.7,
            "system_prompt_extraction": 0.5,
        }

    def classify(self, text: str) -> Dict[str, float]:
        text_lower = text.lower()
        scores: Dict[str, float] = {}

        for category, patterns in self.patterns.items():
            category_score = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                if matches > 0:
                    category_score += matches * self.weights[category]

            scores[category] = category_score

        total_score = sum(scores.values())
        scores["total"] = total_score
        scores["is_injection"] = total_score > 0.5

        return scores

    def is_injection(self, text: str, threshold: float = 0.5) -> bool:
        result = self.classify(text)
        return result["total"] > threshold
