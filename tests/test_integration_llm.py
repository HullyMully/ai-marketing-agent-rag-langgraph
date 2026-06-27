"""Optional real-LLM integration test.

Skipped by default. It is the only test that talks to a real
OpenAI-compatible / DeepSeek endpoint, so it runs only when explicitly enabled:

    RUN_LLM_INTEGRATION=1 \
    MOCK_LLM=false \
    OPENAI_BASE_URL=https://api.deepseek.com \
    OPENAI_API_KEY=sk-... \
    LLM_MODEL=deepseek-chat \
    pytest -m integration tests/test_integration_llm.py

Everything else in the suite is fully mocked and needs no network or keys.
"""
import os

import pytest

pytestmark = pytest.mark.integration

_ENABLED = os.getenv("RUN_LLM_INTEGRATION") == "1"


@pytest.mark.skipif(not _ENABLED, reason="set RUN_LLM_INTEGRATION=1 (and real LLM env) to run")
def test_real_llm_planner_returns_valid_decision() -> None:
    from app.agent import planner
    from app.agent.memory import get_memory
    from app.config import settings

    if settings.mock_llm:
        pytest.skip("MOCK_LLM is true — configure a real OpenAI-compatible model to run")

    # Ensure the LLM client is (re)built from the real configuration.
    import app.agent.llm as llm_mod
    llm_mod._llm = None

    context = {
        "company_profile": {"company_name": "Acme Growth Studio"},
        "knowledge_context": [],
        "recent_conversation_history": [],
        "session_summary": "",
        "lead_draft": {},
        "ticket_state": {"ticket_created": False, "lead_created": False},
        "available_actions": planner.AVAILABLE_ACTIONS,
        "user_message": "What services do you provide?",
    }
    decision = planner.plan(context, memory=get_memory(), session="llm-int-1")

    # The real model must return a schema-valid, non-faked decision.
    assert decision.recommended_action in planner.AVAILABLE_ACTIONS
    assert isinstance(decision.assistant_reply, str) and decision.assistant_reply.strip()
    assert 0.0 <= float(decision.confidence) <= 1.0
    # A plain services question must never fabricate a lead/ticket action.
    assert decision.recommended_action not in ("create_lead", "create_ticket")
