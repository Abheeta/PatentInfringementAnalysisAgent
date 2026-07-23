"""LLM provider abstraction. Ollama only for now — see
docs/superpowers/specs/2026-07-23-qwen-integration-design.md §1.
"""

import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.errors import ApiError

logger = logging.getLogger(__name__)

_USER_MESSAGE = "The AI assistant is temporarily unavailable. Please try again in a moment."


class LLMUnavailableError(ApiError):
    """502 llm_unavailable. Subclasses ApiError so main.py's existing
    global exception handler catches it with no router changes.

    `message` is always the generic, user-facing text — technical detail
    (which provider, what actually failed) is logged server-side via
    `detail`, never sent to the frontend.
    """

    def __init__(self, detail: str):
        logger.warning("LLM call failed: %s", detail)
        super().__init__(502, "llm_unavailable", _USER_MESSAGE)


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: list[dict], schema: dict) -> dict:
        """Sends messages to the model, constrained to schema, and returns
        the parsed JSON object."""


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str, num_ctx: int, timeout: float):
        self._host = host
        self._model = model
        self._num_ctx = num_ctx
        self._timeout = timeout

    def generate(self, messages: list[dict], schema: dict) -> dict:
        try:
            response = httpx.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "format": schema,
                    "stream": False,
                    "options": {"num_ctx": self._num_ctx},
                },
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            raise LLMUnavailableError(
                f"Ollama request timed out after {self._timeout}s."
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Could not reach Ollama: {exc}.")

        if response.status_code != 200:
            raise LLMUnavailableError(
                f"Ollama returned status {response.status_code}."
            )

        try:
            content = response.json()["message"]["content"]
            return json.loads(content)
        except (KeyError, json.JSONDecodeError) as exc:
            raise LLMUnavailableError(f"Ollama returned an unparseable response: {exc}.")


_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider_instance
    if _provider_instance is None:
        if settings.LLM_PROVIDER == "ollama":
            _provider_instance = OllamaProvider(
                host=settings.OLLAMA_HOST,
                model=settings.OLLAMA_MODEL,
                num_ctx=settings.OLLAMA_NUM_CTX,
                timeout=settings.OLLAMA_TIMEOUT,
            )
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
    return _provider_instance
