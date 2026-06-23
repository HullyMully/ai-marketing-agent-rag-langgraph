"""The stateful conversational agent, implemented with LangGraph.

The agent behaves like a real sales/support assistant for the configured company:

* Service / pricing / support questions are answered from the knowledge base (RAG).
* Prospects are qualified across several turns into a session **lead draft**
  (name, company, contact email, service interest, budget). A CRM lead is created
  only once all required fields are known — never after just a name + email — and
  never twice in the same session.
* Explicit human/manager requests (or clearly complex enterprise needs) create a
  ticket. Unclear messages get a short clarifying question, not a ticket.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.llm import get_llm
from app.agent.memory import REQUIRED_FIELDS, extract_fields, get_memory
from app.agent.prompts import RAG_ANSWER_PROMPT, get_system_persona
from app.company import get_company
from app.agent.state import AgentState
from app.rag.retriever import get_retriever
from app.tools.crm_tools import create_lead
from app.tools.escalation import escalate_to_human

_KNOWLEDGE_INTENTS = {"service_question", "pricing_question", "support_request"}
_LEAD_INTENTS = {"greeting", "lead_qualification", "create_lead"}

_NEW_REQUEST_HINTS = (
    "new request", "another lead", "different company", "start over",
    "new project", "new client", "second lead", "new lead",
)


def _history_text(history: list[dict[str, str]], limit: int = 6) -> str:
    recent = history[-limit:]
    if not recent:
        return "(no previous messages)"
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)


def _is_new_request(message: str) -> bool:
    text = message.lower()
    return any(h in text for h in _NEW_REQUEST_HINTS)


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def classify_intent_node(state: AgentState) -> AgentState:
    """Classify intent and merge any extracted lead fields into the draft."""
    from app.agent.intent import classify_intent

    intent, confidence = classify_intent(state["user_message"])
    state["intent"] = intent
    state["confidence"] = confidence

    memory = get_memory()
    session = state["session_id"]

    if _is_new_request(state["user_message"]) and memory.is_lead_created(session):
        memory.reset_draft(session)

    extracted = extract_fields(state["user_message"])
    state["extracted"] = extracted
    if extracted and not memory.is_lead_created(session):
        memory.update_draft(session, extracted)
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
    """Route the turn, driven by intent AND the current lead draft."""
    memory = get_memory()
    session = state["session_id"]
    intent = state.get("intent", "unknown")
    extracted_any = bool(state.get("extracted"))

    if intent == "human_escalation":
        state["route"] = "escalate"
    elif intent in _KNOWLEDGE_INTENTS:
        state["route"] = "answer"
    elif intent == "memory_question":
        state["route"] = "memory"
    elif memory.is_lead_created(session):
        # A lead already exists this session — never create a duplicate.
        state["route"] = "lead_exists"
    elif intent in _LEAD_INTENTS or extracted_any:
        state["route"] = "collect" if memory.missing_fields(session) else "tool"
    else:
        state["route"] = "clarify"
    return state


def collect_missing_info_node(state: AgentState) -> AgentState:
    """Ask one natural follow-up for the next missing lead fields."""
    memory = get_memory()
    missing = memory.missing_fields(state["session_id"])
    state["missing_fields"] = missing

    if "service_interest" in missing:
        answer = (
            "Welcome! What kind of help are you looking for — for example paid ads, "
            "SEO, analytics setup, or a landing page audit?"
        )
    elif "company" in missing or "budget_range" in missing:
        needs = []
        if "company" in missing:
            needs.append("which company you're with")
        if "budget_range" in missing:
            needs.append("your rough monthly budget")
        answer = "Got it. Could you tell me " + " and ".join(needs) + "?"
    elif "name" in missing or "contact_email" in missing:
        needs = []
        if "name" in missing:
            needs.append("your name")
        if "contact_email" in missing:
            needs.append("the best email for follow-up")
        answer = "Thanks. What's " + " and ".join(needs) + "?"
    else:  # pragma: no cover - defensive
        answer = "Could you share a little more about what you need?"

    state["answer"] = answer
    state["action_taken"] = "collecting_info"
    return state


def call_tool_node(state: AgentState) -> AgentState:
    """Create the CRM lead once the draft is complete."""
    memory = get_memory()
    session = state["session_id"]
    draft = memory.get_draft(session)

    budget = draft.get("budget_range") or ("unspecified" if draft.get("budget_unknown") else "")
    lead = create_lead(
        name=draft["name"],
        contact=draft["contact_email"],
        company=draft["company"],
        service_interest=draft["service_interest"],
        budget_range=budget or "unspecified",
        message=state["user_message"],
    )
    memory.mark_lead_created(session, lead["id"])
    state["created_lead_id"] = lead["id"]
    state["action_taken"] = "created_lead"

    service = (draft["service_interest"] or "").lower()
    budget_phrase = f"{budget} budget" if budget and budget != "unspecified" else "budget to confirm"
    state["answer"] = (
        f"Done. I created a lead for {draft['company']}: {service}, {budget_phrase}, "
        f"contact {draft['name']} at {draft['contact_email']}."
    )
    return state


def lead_exists_node(state: AgentState) -> AgentState:
    """Acknowledge an already-created lead without making a duplicate."""
    draft = get_memory().get_draft(state["session_id"])
    state["answer"] = (
        f"You're already set — I created lead #{draft.get('lead_id')} for "
        f"{draft.get('company')}. Want to start a new request or change anything?"
    )
    state["action_taken"] = "lead_already_exists"
    return state


def clarify_node(state: AgentState) -> AgentState:
    """Ask one short clarifying question (never a ticket)."""
    state["answer"] = (
        "Sorry, I didn't quite catch that. Could you tell me a bit more — are you "
        "after our services, pricing, or help starting a project?"
    )
    state["action_taken"] = "asked_clarification"
    return state


def memory_answer_node(state: AgentState) -> AgentState:
    """Answer a recall question from the session's lead draft."""
    draft = get_memory().get_draft(state["session_id"])
    state["memory_used"] = True
    parts: list[str] = []
    if draft.get("company"):
        parts.append(draft["company"])
    if draft.get("service_interest"):
        parts.append(draft["service_interest"].lower())
    if draft.get("budget_range"):
        parts.append(f"{draft['budget_range']} budget")
    if parts:
        state["answer"] = "So far you've mentioned " + ", ".join(parts) + "."
    else:
        state["answer"] = (
            "I don't have those details yet. What company are you with, and what "
            "are you looking for help with?"
        )
    state["action_taken"] = "answered_with_memory"
    return state


def escalate_to_human_node(state: AgentState) -> AgentState:
    """Create a high-priority escalation ticket for a human manager."""
    ticket = escalate_to_human(
        user_id=state.get("user_id") or state["session_id"],
        summary=f"User message: {state['user_message']}",
        reason="human_escalation",
    )
    state["created_ticket_id"] = ticket["id"]
    state["escalated"] = True
    state["ticket_created"] = True
    state["action_taken"] = "escalated_to_human"
    target = get_company().escalation_target
    state["answer"] = (
        f"I've passed this to a {target} (ticket #{ticket['id']}). "
        "They'll follow up within one business day."
    )
    return state


def generate_answer_node(state: AgentState) -> AgentState:
    """Generate a grounded answer from retrieved knowledge (RAG path)."""
    context = "\n\n".join(state.get("retrieved", [])) or "(no context found)"
    prompt = RAG_ANSWER_PROMPT.format(
        persona=get_system_persona(),
        history=_history_text(state.get("history", [])),
        context=context,
        question=state["user_message"],
    )
    state["answer"] = get_llm().complete(prompt).strip()
    state["action_taken"] = "answered_from_kb"
    return state


def _route(state: AgentState) -> str:
    return state.get("route", "clarify")


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
    graph.add_node("lead_exists", lead_exists_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("memory_answer", memory_answer_node)
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
            "answer": "generate_answer",
            "memory": "memory_answer",
            "collect": "collect_missing_info",
            "tool": "call_tool",
            "lead_exists": "lead_exists",
            "clarify": "clarify",
        },
    )

    for node in (
        "collect_missing_info", "call_tool", "lead_exists", "clarify",
        "memory_answer", "generate_answer", "escalate_to_human",
    ):
        graph.add_edge(node, END)

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
    """Execute one turn and return product-friendly metadata."""
    memory = get_memory()
    history = memory.history(session_id)

    state: AgentState = {
        "session_id": session_id,
        "user_id": user_id,
        "user_message": user_message,
        "history": history,
        "extracted": {},
        "retrieved": [],
        "sources": [],
        "missing_fields": [],
        "memory_used": False,
        "escalated": False,
        "ticket_created": False,
        "action_taken": None,
        "created_lead_id": None,
        "created_ticket_id": None,
    }

    result: AgentState = get_agent().invoke(state)

    # Derive clean product metadata from the session draft.
    draft = memory.get_draft(session_id)
    lead_created = bool(draft.get("lead_created"))
    result["lead_draft"] = memory.known_fields(session_id)
    result["missing_fields"] = [] if lead_created else memory.missing_fields(session_id)
    result["lead_created"] = lead_created
    result["lead_id"] = draft.get("lead_id")
    result["ticket_created"] = bool(result.get("created_ticket_id"))

    memory.add_turn(
        session_id=session_id, role="user", content=user_message,
        user_id=user_id, intent=result.get("intent"),
    )
    memory.add_turn(
        session_id=session_id, role="assistant", content=result.get("answer", ""),
        user_id=user_id, intent=result.get("intent"),
        escalated=bool(result.get("escalated")),
    )
    return result


# Required fields are re-exported for callers/tests that want them.
__all__ = ["run_agent", "get_agent", "build_graph", "REQUIRED_FIELDS"]
