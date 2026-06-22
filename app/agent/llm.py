"""LLM abstraction with a fully offline mock implementation.

`get_llm()` returns either a `MockLLM` (deterministic, no API key) or a thin
wrapper around LangChain's `ChatOpenAI`. Both expose the same `.complete(prompt)`
method, so the rest of the agent never branches on the backend.
"""
from __future__ import annotations

from app.config import settings


class MockLLM:
    """Deterministic stand-in for an LLM (demo mode).

    It does not "reason"; it produces grounded, templated text from the prompt's
    context so the end-to-end pipeline is demonstrable without paid API keys.
    """

    def complete(self, prompt: str) -> str:
        return _mock_complete(prompt)


class OpenAILLM:
    """Wrapper around an OpenAI-compatible chat model via LangChain."""

    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI

        self._client = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.3,
        )

    def complete(self, prompt: str) -> str:
        return self._client.invoke(prompt).content  # type: ignore[return-value]


def _mock_complete(prompt: str) -> str:
    """Very small heuristic 'LLM' used only in demo mode."""
    lowered = prompt.lower()
    if "intent:" in lowered and "classify" in lowered:
        # Intent classification path is normally rule-based in mock mode.
        return "general_question"

    # For RAG answers we surface the retrieved context as the grounded answer.
    marker = "Knowledge base context:"
    if marker in prompt and "User question:" in prompt:
        context = prompt.split(marker, 1)[1].split("User question:", 1)[0].strip()
        snippet = _first_meaningful_lines(context, max_lines=4)
        if snippet:
            return (
                f"{snippet}\n\nIf you'd like, I can share more detail or connect "
                "you with a NovaGrowth specialist."
            )
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

    return "Thanks for your message! How can I help you with NovaGrowth's services today?"


def _first_meaningful_lines(text: str, max_lines: int = 4) -> str:
    lines = [
        ln.strip("# ").strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith(">")
    ]
    return " ".join(lines[:max_lines])[:600]


_llm: MockLLM | OpenAILLM | None = None


def get_llm() -> MockLLM | OpenAILLM:
    """Return a process-wide singleton LLM client."""
    global _llm
    if _llm is None:
        _llm = MockLLM() if settings.mock_llm else OpenAILLM()
    return _llm
