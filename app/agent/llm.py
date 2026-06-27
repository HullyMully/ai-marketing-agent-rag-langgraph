"""LLM abstraction with an explicit offline mock implementation.

`get_llm()` returns either a thin wrapper around LangChain's `ChatOpenAI` or,
when explicitly configured, a `MockLLM` (deterministic, no API key). Both expose
the same `.complete(prompt)` method, so the rest of the agent never branches on
the backend.

The OpenAI-compatible wrapper works with OpenAI, DeepSeek and similar endpoints
via `OPENAI_BASE_URL` + `LLM_MODEL`. Secrets are never logged.
"""
from __future__ import annotations

import logging

from pydantic.v1 import SecretStr

from app.config import settings

logger = logging.getLogger("assistant.llm")


class MockLLM:
    """Deterministic stand-in for an LLM (tests/offline demo mode).

    It does not "reason" or produce production-quality dialogue. Use it only for
    tests and explicit offline demos when paid/API-backed models are unavailable.
    """

    def complete(self, prompt: str) -> str:
        return _mock_complete(prompt)


class OpenAILLM:
    """Wrapper around an OpenAI-compatible chat model (OpenAI, DeepSeek, ...)."""

    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI

        # Never log the API key; log only the non-secret endpoint/model.
        logger.info(
            "LLM configured: model=%s base_url=%s timeout=%ss",
            settings.llm_model, settings.openai_base_url, settings.llm_timeout,
        )
        self._client = ChatOpenAI(
            model=settings.llm_model,
            api_key=SecretStr(settings.openai_api_key),
            base_url=settings.openai_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout,
            max_retries=1,
        )

    def complete(self, prompt: str) -> str:
        try:
            return self._client.invoke(prompt).content  # type: ignore[return-value]
        except Exception as exc:
            # Log the failure type only (no prompt contents, no secrets) and
            # re-raise so callers can fall back safely.
            logger.warning("LLM request failed: %s", type(exc).__name__)
            raise


def _mock_complete(prompt: str) -> str:
    """Very small heuristic 'LLM' used only in demo mode."""
    lowered = prompt.lower()
    if "intent:" in lowered and "classify" in lowered:
        # Intent classification is rule-based in mock mode; safe fallback label.
        return "unknown"

    # For RAG answers we surface the retrieved context as the grounded answer.
    marker = "Knowledge base context:"
    if marker in prompt and ("User message:" in prompt or "User question:" in prompt):
        context = prompt.split(marker, 1)[1].split("User message:", 1)
        if len(context) == 1:
            context = prompt.split(marker, 1)[1].split("User question:", 1)
        snippet = _first_meaningful_lines(context[0].strip(), max_lines=2)
        if snippet:
            return snippet
        return (
            "I'm not fully sure about that based on what I have. I can connect "
            "you with a human manager who can help."
        )

    if "Ask a short, friendly follow-up" in prompt:
        return (
            "Great – I'd love to help you get started! Could you share your name, "
            "company, the best email or phone to reach you, and which service "
            "you're interested in?"
        )

    return "I'm here. Could you rephrase what you want to do next?"


def _first_meaningful_lines(text: str, max_lines: int = 2) -> str:
    lines = [
        ln.strip("# ").strip().lstrip("-* ").strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith(">")
    ]
    return " ".join(lines[:max_lines])[:280]


_llm: MockLLM | OpenAILLM | None = None


def llm_runtime_mode() -> str:
    """Return the public runtime mode name for diagnostics/UI metadata."""
    return "mock" if settings.mock_llm else "llm"


def get_llm() -> MockLLM | OpenAILLM:
    """Return a process-wide singleton LLM client."""
    global _llm
    if _llm is None:
        if settings.mock_llm:
            logger.warning("MOCK_LLM is enabled: responses are offline test/demo output, not production AI.")
            _llm = MockLLM()
        else:
            _llm = OpenAILLM()
    return _llm
