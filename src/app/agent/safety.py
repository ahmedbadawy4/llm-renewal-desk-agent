from __future__ import annotations

from .injection_classifier import InjectionClassifier

_injection_classifier: InjectionClassifier | None = None


def _get_classifier() -> InjectionClassifier:
    global _injection_classifier
    if _injection_classifier is None:
        _injection_classifier = InjectionClassifier()
    return _injection_classifier


def contains_prompt_injection(text: str, threshold: float = 0.5) -> bool:
    classifier = _get_classifier()
    return classifier.is_injection(text, threshold=threshold)
