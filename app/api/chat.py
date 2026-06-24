"""Chat endpoint – the conversational entry point to the agent."""
from __future__ import annotations

from fastapi import APIRouter

from app.agent.graph import run_agent
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send a user message to the agent and return its reply plus session state.

    The agent is stateful: pass the same `session_id` across turns and it builds
    up a lead draft, remembers details, and only creates a CRM lead once the
    required fields are all known.
    """
    result = run_agent(
        session_id=request.session_id,
        user_message=request.user_message,
        user_id=request.user_id,
    )
    return ChatResponse(
        session_id=request.session_id,
        answer=result.get("answer", ""),
        intent=result.get("intent", "unknown"),
        action=result.get("action_taken"),
        assistant_reply=result.get("assistant_reply", result.get("answer", "")),
        conversation_target=result.get("conversation_target", "unclear"),
        context_relation=result.get("context_relation", "unclear"),
        should_continue_qualification=bool(result.get("should_continue_qualification")),
        user_intent=result.get("user_intent", "unclear"),
        recommended_action=result.get("recommended_action", "answer_only"),
        knowledge_used=bool(result.get("knowledge_used")),
        lead_draft=result.get("lead_draft", {}),
        missing_fields=result.get("missing_fields", []),
        lead_created=bool(result.get("lead_created")),
        lead_id=result.get("lead_id"),
        mode=result.get("mode", "answering"),
        known_interests=result.get("known_interests", []),
        qualification_paused=bool(result.get("qualification_paused")),
        exploration_mode=bool(result.get("exploration_mode")),
        next_step=result.get("next_step", ""),
        ticket_created=bool(result.get("ticket_created")),
        ticket_id=result.get("created_ticket_id"),
        sources=result.get("sources", []),
        memory_used=bool(result.get("memory_used")),
        clarification_count=int(result.get("clarification_count", 0)),
        planner_decision=result.get("planner_decision", {}),
        validation=result.get("validation", {}),
        action_executed=bool(result.get("action_executed")),
        escalated=bool(result.get("escalated")),
        confidence=float(result.get("confidence", 1.0)),
        llm_runtime_mode=result.get("llm_runtime_mode", "llm"),
        mock_llm=bool(result.get("mock_llm")),
    )
