"""The stateful conversational agent, implemented with LangGraph.

Graph nodes (states):
    classify_intent -> retrieve_knowledge -> decide_action -> {
        collect_missing_info | call_tool | generate_answer | escalate_to_human
    }

The graph makes realistic routing decisions:
* Service/pricing/campaign questions are answered from the RAG knowledge base.
* A user who wants to work with the agency is qualified; once name + contact are
  known a CRM lead is created.
* Explicit human requests or low-confidence turns create an escalation ticket.
* Missing lead info triggers a short follow-up question.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.llm import get_llm
from app.agent.memory import extract_slots, get_memory
from app.agent.prompts import RAG_ANSWER_PROMPT, SYSTEM_PERSONA
from app.agent.state import AgentState
from app.config import settings
from app.rag.retriever import get_retriever
from app.tools.crm_tools import create_lead
from app.tools.escalation import escalate_to_human

# Intents that should be answered from the knowledge base via RAG.
_KNOWLEDGE_INTENTS = {
    "service_question",
    "pricing_question",
    "campaign_status_question",
    "general_question",
    "support_request",
}


def _history_text(history: list[dict[str, str]], limit: int = 6) -> str:
    recent = history[-limit:]
    if not recent:
        return "(no previous messages)"
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def classify_intent_node(state: AgentState) -> AgentState:
    """Classify intent and capture any lead details from the message."""
    from app.agent.intent import classify_intent

    intent, confidence = classify_intent(state["user_message"])
    state["intent"] = intent
    state["confidence"] = confidence

    # Always try to remember lead details, regardless of intent.
    memory = get_memory()
    extracted = extract_slots(state["user_message"])
    if extracted:
        memory.update_slots(state["session_id"], extracted)
    state["slots"] = memory.get_slots(state["session_id"])
    return state


def retrieve_knowledge_node(state: AgentState) -> AgentState:
    """Retrieve relevant knowledge-base chunks for knowledge intents."""
    if state.get("intent") in _KNOWLEDGE_INTENTS:
        hits = get_retriever().search(state["user_message"], top_k=3)
        state["retrieved"] = [h.text for h in hits]
        state["sources"] = list(dict.fromkeys(h.source for h in hits))
    else:
        state["retrieved"] = []
        state["sources"] = []
    return state


def decide_action_node(state: AgentState) -> AgentState:
    """Decide which terminal action the graph should route to."""
    memory = get_memory()
    intent = state.get("intent", "unknown")
    confidence = state.get("confidence", 0.0)

    if intent == "human_escalation" or confidence < settings.escalation_confidence_threshold:
        state["route"] = "escalate"
    elif intent == "create_lead":
        missing = memory.missing_required(state["session_id"])
        state["missing_fields"] = missing
        state["route"] = "collect" if missing else "tool"
    else:
        state["route"] = "answer"
    return state


def collect_missing_info_node(state: AgentState) -> AgentState:
    """Ask a short follow-up question for missing lead fields."""
    missing = state.get("missing_fields", []) or ["name", "contact"]
    pretty = {
        "name": "your name",
        "contact": "the best email or phone to reach you",
        "company": "your company",
        "service_interest": "which service you're interested in",
        "budget_range": "a rough monthly budget",
    }
    asks = ", ".join(pretty.get(m, m) for m in missing)
    state["answer"] = (
        "I'd be glad to help you get started with NovaGrowth! Could you share "
        f"{asks}? That way I can set you up with the right specialist."
    )
    state["action_taken"] = "collect_missing_info"
    return state


def call_tool_node(state: AgentState) -> AgentState:
    """Create a CRM lead from the collected slots."""
    memory = get_memory()
    slots = memory.get_slots(state["session_id"])
    lead = create_lead(
        name=slots.get("name", "Unknown"),
        contact=slots.get("contact", "unspecified"),
        company=slots.get("company"),
        service_interest=slots.get("service_interest"),
        budget_range=slots.get("budget_range", "unspecified"),
        message=state["user_message"],
    )
    state["created_lead_id"] = lead["id"]
    state["action_taken"] = "created_lead"
    memory.clear_slots(state["session_id"])

    svc = slots.get("service_interest", "your goals")
    company = slots.get("company")
    for_company = f" for {company}" if company else ""
    state["answer"] = (
        f"You're all set, {slots.get('name', 'there')}! I've created a lead"
        f"{for_company} (#{lead['id']}) for {svc}. A NovaGrowth manager will "
        f"follow up with you at {slots.get('contact')} shortly. "
        "Anything else I can help with?"
    )
    return state


def escalate_to_human_node(state: AgentState) -> AgentState:
    """Create a high-priority escalation ticket for a human manager."""
    reason = (
        "human_escalation"
        if state.get("intent") == "human_escalation"
        else "low_confidence"
    )
    ticket = escalate_to_human(
        user_id=state.get("user_id") or state["session_id"],
        summary=f"User message: {state['user_message']}",
        reason=reason,
    )
    state["created_ticket_id"] = ticket["id"]
    state["escalated"] = True
    state["action_taken"] = "escalated_to_human"
    state["answer"] = (
        "I've flagged this for a human manager at NovaGrowth "
        f"(ticket #{ticket['id']}). Someone will follow up with you, usually "
        "within one business day. Is there anything else I can help with in the "
        "meantime?"
    )
    return state


def generate_answer_node(state: AgentState) -> AgentState:
    """Generate a grounded answer from retrieved knowledge (RAG path)."""
    context = "\n\n".join(state.get("retrieved", [])) or "(no context found)"
    prompt = RAG_ANSWER_PROMPT.format(
        persona=SYSTEM_PERSONA,
        history=_history_text(state.get("history", [])),
        context=context,
        question=state["user_message"],
    )
    state["answer"] = get_llm().complete(prompt).strip()
    state["action_taken"] = "answered_from_kb"
    return state


def _route(state: AgentState) -> str:
    return state.get("route", "answer")


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph():
    """Compile and return the LangGraph conversation graph."""
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge_node)
    graph.add_node("decide_action", decide_action_node)
    graph.add_node("collect_missing_info", collect_missing_info_node)
    graph.add_node("call_tool", call_tool_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("escalate_to_human", escalate_to_human_node)

    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "decide_action")

    graph.add_conditional_edges(
        "decide_action",
        _route,
        {
            "escalate": "escalate_to_human",
            "collect": "collect_missing_info",
            "tool": "call_tool",
            "answer": "generate_answer",
        },
    )

    graph.add_edge("collect_missing_info", END)
    graph.add_edge("call_tool", END)
    graph.add_edge("escalate_to_human", END)
    graph.add_edge("generate_answer", END)

    return graph.compile()


_compiled = None


def get_agent():
    """Return a compiled, cached agent graph."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


def run_agent(
    *, session_id: str, user_message: str, user_id: str | None = None
) -> AgentState:
    """Execute one turn of the conversation through the graph."""
    memory = get_memory()
    history = memory.history(session_id)

    state: AgentState = {
        "session_id": session_id,
        "user_id": user_id,
        "user_message": user_message,
        "history": history,
        "retrieved": [],
        "sources": [],
        "slots": {},
        "missing_fields": [],
        "escalated": False,
        "action_taken": None,
        "created_lead_id": None,
        "created_ticket_id": None,
    }

    result: AgentState = get_agent().invoke(state)

    # Persist this turn to memory for future context + metrics.
    memory.add_turn(
        session_id=session_id,
        role="user",
        content=user_message,
        user_id=user_id,
        intent=result.get("intent"),
    )
    memory.add_turn(
        session_id=session_id,
        role="assistant",
        content=result.get("answer", ""),
        user_id=user_id,
        intent=result.get("intent"),
        escalated=bool(result.get("escalated")),
    )
    return result
