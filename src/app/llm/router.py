from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

from ..core.config import Settings
from ..core.retry import retry_with_backoff, RetryConfig, CircuitBreaker
from . import ollama
from .openai import chat_completion as openai_chat_completion

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    cost_per_1k_tokens: float = 0.0001
    max_tokens: int = 800


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model_configs: Dict[str, ModelConfig] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._initialize_models()

    def _initialize_models(self) -> None:
        if self.settings.llm_provider == "ollama":
            self._model_configs["ollama"] = ModelConfig(
                provider="ollama",
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                cost_per_1k_tokens=0.0,
            )
            self._circuit_breakers["ollama"] = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        openai_api_key = getattr(self.settings, "openai_api_key", None)
        openai_base_url = getattr(self.settings, "openai_base_url", "https://api.openai.com/v1")
        openai_model = getattr(self.settings, "openai_model", "gpt-3.5-turbo")

        if openai_api_key:
            self._model_configs["openai"] = ModelConfig(
                provider="openai",
                model=openai_model,
                base_url=openai_base_url,
                api_key=openai_api_key,
                cost_per_1k_tokens=0.002,
            )
            self._circuit_breakers["openai"] = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

    def select_model(
        self,
        estimated_tokens: int = 0,
        complexity: str = "medium",
        budget_available: float = 1.0,
        quality_requirement: str = "standard",
    ) -> ModelConfig:
        if not self._model_configs:
            raise RuntimeError("No models configured")

        if complexity == "simple" and "ollama" in self._model_configs:
            return self._model_configs["ollama"]

        if quality_requirement == "high" and "openai" in self._model_configs:
            estimated_cost = (estimated_tokens / 1000.0) * self._model_configs["openai"].cost_per_1k_tokens
            if estimated_cost <= budget_available:
                return self._model_configs["openai"]

        if "ollama" in self._model_configs:
            return self._model_configs["ollama"]

        if "openai" in self._model_configs:
            return self._model_configs["openai"]

        return list(self._model_configs.values())[0]

    def call(
        self,
        messages: list[Dict[str, str]],
        estimated_tokens: int = 0,
        complexity: str = "medium",
        budget_available: float = 1.0,
        quality_requirement: str = "standard",
        timeout_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        model_config = self.select_model(estimated_tokens, complexity, budget_available, quality_requirement)
        breaker = self._circuit_breakers.get(model_config.provider)

        retry_config = RetryConfig(max_attempts=3, initial_delay=1.0, max_delay=10.0)

        @retry_with_backoff(config=retry_config, retryable_exceptions=(Exception,))
        def _call_with_retry() -> Dict[str, Any]:
            if breaker:
                return breaker.call(lambda: self._call_model(model_config, messages, timeout_seconds))
            return self._call_model(model_config, messages, timeout_seconds)

        try:
            return _call_with_retry()
        except Exception as e:
            logger.warning(f"Model {model_config.provider} failed: {e}, trying fallback")
            return self._fallback_call(messages, timeout_seconds)

    def _call_model(
        self,
        model_config: ModelConfig,
        messages: list[Dict[str, str]],
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        if model_config.provider == "ollama":
            payload = {
                "model": model_config.model,
                "messages": messages,
                "options": {"num_predict": model_config.max_tokens},
            }
            return ollama.chat_completion(
                model_config.base_url or self.settings.ollama_base_url,
                payload,
                timeout_seconds=timeout_seconds,
            )

        elif model_config.provider == "openai":
            return openai_chat_completion(
                api_key=model_config.api_key or "",
                base_url=model_config.base_url or "https://api.openai.com/v1",
                model=model_config.model,
                messages=messages,
                max_tokens=model_config.max_tokens,
                timeout_seconds=timeout_seconds,
            )

        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}")

    def _fallback_call(self, messages: list[Dict[str, str]], timeout_seconds: float) -> Dict[str, Any]:
        if "ollama" in self._model_configs:
            try:
                model_config = self._model_configs["ollama"]
                payload = {
                    "model": model_config.model,
                    "messages": messages,
                    "options": {"num_predict": model_config.max_tokens},
                }
                return ollama.chat_completion(
                    model_config.base_url or self.settings.ollama_base_url,
                    payload,
                    timeout_seconds=timeout_seconds,
                )
            except Exception:
                pass

        raise RuntimeError("All model providers failed")
