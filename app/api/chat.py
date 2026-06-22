"""Chat endpoint – the conversational entry point to the agent."""
from __future__ import annotations

from fastapi import APIRouter

from app.agent.graph import run_agent
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send a user message to the agent and return its reply.

    The agent is stateful: pass the same `session_id` across turns and it will
    remember context (e.g., lead details collected earlier).
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
        escalated=bool(result.get("escalated")),
        action_taken=result.get("action_taken"),
        created_lead_id=result.get("created_lead_id"),
        created_ticket_id=result.get("created_ticket_id"),
        confidence=float(result.get("confidence", 1.0)),
        sources=result.get("sources", []),
    )
