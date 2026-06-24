"""The stateful conversational agent (LangGraph).

The assistant understands each message (intent + extracted fields + signals),
keeps a persistent lead draft, and uses deterministic business rules to decide
whether to answer from the knowledge base, guide the user toward the next missing
field, create a CRM lead, or open a support ticket.

It guides naturally instead of repeating a fallback: while a conversation is in
progress it always moves toward the next missing field, acknowledges corrections,
and handles uncertainty without resetting the draft.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent import responses
from app.agent.llm import get_llm
from app.agent.memory import get_memory
from app.agent.prompts import RAG_ANSWER_PROMPT, get_system_persona
from app.agent.state import AgentState
from app.agent.understanding import analyze
from app.company import get_company
from app.rag.retriever import get_retriever
from app.tools.crm_tools import create_lead
from app.tools.escalation import escalate_to_human

_KNOWLEDGE_INTENTS = {"service_question", "pricing_question", "support_request"}
_GUIDE_INTENTS = {
    "greeting", "needs_help", "project_start", "lead_info_update",
    "memory_correction", "budget_unknown",
}
_NEW_REQUEST_HINTS = ("start a new request", "create another lead", "new project", "another lead")
_VALID_EMAIL = "@"
# Concrete lead fields that signal the user genuinely wants to start a request.
_CONCRETE_FIELDS = ("company", "contact_email", "name", "budget_range")
_PROCEED = (
    "yes", "yeah", "yep", "sure", "go ahead", "let's do it", "lets do it",
    "continue", "proceed", "create the request", "start the request",
    "prepare a request", "sounds good", "do it",
)


def _history_text(history: list[dict[str, str]], limit: int = 6) -> str:
    recent = history[-limit:]
    if not recent:
        return "(no previous messages)"
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)


def _is_new_request(message: str) -> bool:
    text = message.lower()
    return any(h in text for h in _NEW_REQUEST_HINTS)


def _combine_services(existing: str, new: str) -> str:
    """Merge a newly-mentioned service into any already noted, preserving order."""
    parts = [p.strip() for p in (existing or "").split("+") if p.strip()]
    for token in (new or "").split("+"):
        token = token.strip()
        if token and token.lower() not in {p.lower() for p in parts}:
            parts.append(token)
    return " + ".join(parts)


def _wants_to_proceed(message: str) -> bool:
    text = message.lower().strip()
    return any(p == text or text.startswith(p + " ") or p in text for p in _PROCEED)


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def understand_node(state: AgentState) -> AgentState:
    """Analyse the message, track dialogue state, and merge fields into the draft."""
    memory = get_memory()
    session = state["session_id"]
    message = state["user_message"]

    if _is_new_request(message) and memory.is_lead_created(session):
        memory.reset_draft(session)

    draft = memory.get_draft(session)
    analysis = analyze(message, draft)

    state["intent"] = analysis.intent
    state["confidence"] = analysis.confidence
    state["user_confusion"] = analysis.user_confusion
    state["correction_detected"] = analysis.correction_detected
    state["asks_for_human"] = analysis.asks_for_human
    state["extracted"] = dict(analysis.fields)
    state["user_says_just_hello"] = analysis.user_says_just_hello

    # --- merge extracted fields, combining/replacing service interest ----------
    saved: list[str] = []
    if not memory.is_lead_created(session):
        values = dict(analysis.fields)
        new_service = values.get("service_interest")
        existing_service = draft.get("service_interest")
        if new_service and existing_service:
            # "and seo" combines; a fresh/corrected mention replaces.
            if analysis.additive_service:
                values["service_interest"] = _combine_services(existing_service, new_service)
            # otherwise the new value simply overwrites (replace).
        if analysis.budget_unknown:
            values["budget_unknown"] = True
        _, saved = memory.update_draft(session, values)
    state["saved_fields"] = saved

    # --- update dialogue counters/flags ---------------------------------------
    gave_concrete = any(f in _CONCRETE_FIELDS for f in saved)

    if analysis.social_greeting_only or analysis.user_says_just_hello:
        if not gave_concrete:
            memory.bump(session, "greeting_count")
    if analysis.refusal:
        memory.bump(session, "user_refused_count")
    if analysis.cannot_remember:
        memory.bump(session, "user_confusion_count")
    if analysis.frustration:
        memory.bump(session, "user_frustration_count")

    # Mark that the user genuinely wants to start a request.
    wants_request = (
        analysis.intent == "project_start"
        or gave_concrete
        or _wants_to_proceed(message)
    )
    if wants_request or memory.get(session, "qualification_active"):
        memory.set_flag(session, "qualification_active", True)

    # Exploration mode: enter on refusal / can't-remember / wants-guidance,
    # exit when the user re-engages (concrete details or a clear request).
    disengaged = analysis.refusal or analysis.cannot_remember or analysis.wants_guidance
    re_engaged = wants_request and not (analysis.refusal or analysis.frustration)
    if re_engaged:
        memory.set_flag(session, "exploration_mode", False)
    elif disengaged and not state["asks_for_human"]:
        memory.set_flag(session, "exploration_mode", True)

    # Pause qualification entirely after repeated refusal / frustration.
    refused = int(memory.get(session, "user_refused_count", 0) or 0)
    frustrated = int(memory.get(session, "user_frustration_count", 0) or 0)
    if refused + frustrated >= 2:
        memory.set_flag(session, "qualification_paused", True)

    return state


def retrieve_knowledge_node(state: AgentState) -> AgentState:
    """Retrieve knowledge-base chunks for knowledge intents."""
    if state.get("intent") in _KNOWLEDGE_INTENTS and not state.get("asks_for_human"):
        hits = get_retriever().search(state["user_message"], top_k=3)
        state["retrieved"] = [h.text for h in hits]
        state["sources"] = list(dict.fromkeys(h.source for h in hits))
    else:
        state["retrieved"] = []
        state["sources"] = []
    return state


def decide_action_node(state: AgentState) -> AgentState:
    """Route the turn from intent, signals and dialogue mode (deterministic)."""
    memory = get_memory()
    session = state["session_id"]
    intent = state.get("intent", "unknown")
    saved = state.get("saved_fields", [])
    gave_concrete = any(f in _CONCRETE_FIELDS for f in saved)

    # 1. Explicit human request / anger -> a human ticket.
    if state.get("asks_for_human"):
        state["route"] = "escalate"
        return state

    # 2. Knowledge questions are always answered (even if paused/exploring).
    if intent in _KNOWLEDGE_INTENTS:
        state["route"] = "answer"
        memory.reset_clarify(session)
        return state

    # 3. Recall question.
    if intent == "memory_question":
        state["route"] = "memory"
        memory.reset_clarify(session)
        return state

    # 4. Lead already created.
    if memory.is_lead_created(session):
        state["route"] = "lead_exists"
        return state

    memory.reset_clarify(session)

    # 5. Qualification paused -> never ask for lead details again.
    if memory.get(session, "qualification_paused"):
        state["route"] = "paused"
        return state

    # 6. A pure social greeting with nothing else going on -> respond socially.
    social = (
        intent == "greeting"
        and not gave_concrete
        and not memory.has_any_field(session)
        and not memory.get(session, "qualification_active")
    )
    if social:
        state["route"] = "social"
        return state

    # 7. Disengaged (refused / can't remember / wants guidance) -> exploration.
    if memory.get(session, "exploration_mode"):
        state["route"] = "explore"
        return state

    # 8. A bare service mention, with no intent to start a request yet ->
    #    ask whether to explore or open a request (don't push company/budget).
    service_known = bool(memory.get(session, "service_interest"))
    if (
        service_known
        and not memory.get(session, "qualification_active")
        and intent != "project_start"
    ):
        state["route"] = "direction"
        return state

    # 9. An active qualification flow -> collect the next field, or create a lead.
    in_flow = (
        intent in _GUIDE_INTENTS
        or memory.has_any_field(session)
        or bool(memory.get_last_asked(session))
        or bool(saved)
    )
    if in_flow:
        ready = (
            not memory.missing_fields(session)
            and memory.get(session, "qualification_active")
        )
        state["route"] = "tool" if ready else "collect"
        return state

    # 10. Truly unclear with no active conversation.
    count = memory.bump_clarify(session)
    state["clarification_count"] = count
    state["route"] = "escalate" if count >= 2 else "clarify"
    return state


# --- guidance helpers ------------------------------------------------------- #
def _acknowledge(state: AgentState, draft: dict) -> str:
    saved = state.get("saved_fields", [])
    if state.get("correction_detected"):
        for f in ("company", "name", "service_interest", "product_type"):
            if f in state.get("extracted", {}) and f not in saved and draft.get(f):
                return f"You're right, I already have {draft[f]}."
    if "service_interest" in saved:
        svc = draft["service_interest"].lower()
        if "product_type" in saved and draft.get("product_type"):
            return f"Got it — {svc} for your {draft['product_type']}."
        return f"Got it — {svc}."
    if "company" in saved:
        return f"Thanks — noted {draft['company']}."
    if "name" in saved:
        return f"Thanks, {draft['name']}."
    if "product_type" in saved:
        return f"Got it — a {draft['product_type']}."
    if "budget_range" in saved or "contact_email" in saved:
        return "Great, noted."
    return ""


def _explore_text(memory, session: str) -> str:
    """Exploration-mode guidance — never asks for company / budget / email."""
    draft = memory.get_draft(session)
    idx = int(memory.get(session, "user_confusion_count", 0) or 0) + int(
        memory.get(session, "user_refused_count", 0) or 0
    )
    return responses.explore(draft.get("service_interest", ""), draft.get("product_type", ""), idx)


def _question_type(missing: list[str]) -> str:
    if "service_interest" in missing:
        return "service"
    if "company" in missing or "budget_range" in missing:
        return "company_budget"
    if "name" in missing or "contact_email" in missing:
        return "contact"
    return "open"


def _service_question(state: AgentState, idx: int):
    confusion = bool(state.get("user_confusion"))
    intent = state.get("intent")
    if confusion:
        return (
            "What would you like to improve — getting more leads, increasing "
            "sales, reducing ad costs, improving website conversion, or "
            "understanding your analytics?"
        ), ["service_interest"]
    if intent == "project_start":
        return (
            "Let's set up your project. What product or company would you like to "
            "promote, and what kind of help do you need (paid ads, SEO, analytics, "
            "or a landing page audit)?"
        ), ["service_interest", "company"]
    options = [
        "What kind of help are you looking for — for example paid ads, SEO, "
        "analytics setup, or a landing page audit?",
        "Which area should we focus on first: paid ads, SEO, analytics, or a "
        "landing-page audit?",
    ]
    return options[idx % len(options)], ["service_interest"]


def collect_node(state: AgentState) -> AgentState:
    """Guide the user toward the next missing field, naturally and without
    repeating the same question more than twice."""
    memory = get_memory()
    session = state["session_id"]
    draft = memory.get_draft(session)
    missing = memory.missing_fields(session)
    state["missing_fields"] = missing

    qtype = _question_type(missing)
    progressed = bool(state.get("saved_fields"))

    # Anti-repetition: never ask the same missing-field question more than twice
    # in a row. If the user is making progress (gave a new field), that's not a
    # stuck loop, so keep collecting.
    if qtype != "open" and not progressed and memory.times_asked(session, qtype) >= 2:
        memory.set_flag(session, "exploration_mode", True)
        memory.note_question(session, "explore")
        memory.set_last_asked(session, [])
        state["answer"] = _explore_text(memory, session)
        state["action_taken"] = "exploring"
        return state

    idx = memory.times_asked(session, qtype)
    ack = _acknowledge(state, draft)

    if qtype == "service":
        question, asked = _service_question(state, idx)
    elif qtype == "company_budget":
        need_company = "company" in missing
        need_budget = "budget_range" in missing
        question = responses.ask_company_budget(need_company, need_budget, idx)
        asked = [f for f, need in (("company", need_company), ("budget_range", need_budget)) if need]
    elif qtype == "contact":
        need_name = "name" in missing
        need_email = "contact_email" in missing
        question = responses.ask_contact(need_name, need_email, idx)
        asked = [f for f, need in (("name", need_name), ("contact_email", need_email)) if need]
    else:
        question, asked = "Could you share a little more about what you need?", []

    memory.note_question(session, qtype)
    memory.set_last_asked(session, asked)
    state["answer"] = (ack + " " + question).strip() if ack else question
    state["action_taken"] = "collecting_info"
    return state


def social_node(state: AgentState) -> AgentState:
    """Respond to a plain greeting socially — no qualification pressure."""
    memory = get_memory()
    session = state["session_id"]
    idx = max(0, int(memory.get(session, "greeting_count", 1) or 1) - 1)
    if state.get("user_says_just_hello"):
        state["answer"] = responses.just_hello(idx)
    else:
        state["answer"] = responses.greeting(idx)
    memory.note_question(session, "social")
    memory.set_last_asked(session, [])
    state["action_taken"] = "greeted"
    return state


def explore_node(state: AgentState) -> AgentState:
    """Exploration mode: help the user think, never collect lead fields."""
    memory = get_memory()
    session = state["session_id"]
    state["missing_fields"] = memory.missing_fields(session)
    memory.set_flag(session, "exploration_mode", True)
    memory.note_question(session, "explore")
    memory.set_last_asked(session, [])
    state["answer"] = _explore_text(memory, session)
    state["action_taken"] = "exploring"
    return state


def direction_node(state: AgentState) -> AgentState:
    """A service is known but the user hasn't asked to start a request yet.
    Offer the choice between exploring and preparing a request."""
    memory = get_memory()
    session = state["session_id"]
    draft = memory.get_draft(session)
    state["missing_fields"] = memory.missing_fields(session)
    idx = memory.times_asked(session, "direction")
    ack = _acknowledge(state, draft)
    question = responses.service_direction(draft.get("service_interest", ""), idx)
    memory.note_question(session, "direction")
    # Allow a following bare answer (e.g. a company name) to be captured.
    memory.set_last_asked(session, ["company"])
    state["answer"] = (ack + " " + question).strip() if ack else question
    state["action_taken"] = "clarifying_direction"
    return state


def paused_node(state: AgentState) -> AgentState:
    """Qualification is paused after repeated refusal/frustration."""
    memory = get_memory()
    session = state["session_id"]
    draft = memory.get_draft(session)
    state["missing_fields"] = memory.missing_fields(session)
    idx = int(memory.get(session, "user_frustration_count", 0) or 0) + int(
        memory.get(session, "user_refused_count", 0) or 0
    )
    memory.set_last_asked(session, [])
    state["answer"] = responses.paused(
        draft.get("service_interest", ""), draft.get("product_type", ""), idx
    )
    state["action_taken"] = "qualification_paused"
    return state


def call_tool_node(state: AgentState) -> AgentState:
    """Create the CRM lead — only when validation passes."""
    memory = get_memory()
    session = state["session_id"]
    draft = memory.get_draft(session)

    # Deterministic guard: required complete, valid email, not already created,
    # the user actually wants to start a request, and qualification isn't paused.
    if (
        memory.is_lead_created(session)
        or memory.missing_fields(session)
        or _VALID_EMAIL not in draft.get("contact_email", "")
        or not memory.get(session, "qualification_active")
        or memory.get(session, "qualification_paused")
    ):
        return collect_node(state)

    budget = draft.get("budget_range") or ("unspecified" if draft.get("budget_unknown") else "")
    lead = create_lead(
        name=draft["name"],
        contact=draft["contact_email"],
        company=draft["company"],
        service_interest=draft["service_interest"],
        budget_range=budget or "unspecified",
        message=draft.get("product_type") or state["user_message"],
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
        f"{draft.get('company')}. To start a different request, just say "
        "\"new project\"."
    )
    state["action_taken"] = "lead_already_exists"
    return state


def clarify_node(state: AgentState) -> AgentState:
    """Friendly orientation for a genuinely unclear opening message."""
    state["clarification_count"] = get_memory().clarify_count(state["session_id"])
    state["answer"] = (
        "Happy to help! I can tell you about our services or pricing, or help you "
        "start a project. What would you like to do?"
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
    if draft.get("product_type"):
        parts.append(f"a {draft['product_type']}")
    if parts:
        state["answer"] = "So far you've mentioned " + ", ".join(parts) + "."
    else:
        state["answer"] = (
            "I don't have any details yet. What company are you with, and what are "
            "you looking for help with?"
        )
    state["action_taken"] = "answered_with_memory"
    return state


def escalate_to_human_node(state: AgentState) -> AgentState:
    """Create a high-priority escalation ticket for a human."""
    reason = "human_escalation" if state.get("asks_for_human") else "unclear_request"
    ticket = escalate_to_human(
        user_id=state.get("user_id") or state["session_id"],
        summary=f"User message: {state['user_message']}",
        reason=reason,
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

    graph.add_node("understand", understand_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge_node)
    graph.add_node("decide_action", decide_action_node)
    graph.add_node("collect", collect_node)
    graph.add_node("call_tool", call_tool_node)
    graph.add_node("lead_exists", lead_exists_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("memory_answer", memory_answer_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("escalate_to_human", escalate_to_human_node)
    graph.add_node("social", social_node)
    graph.add_node("explore", explore_node)
    graph.add_node("direction", direction_node)
    graph.add_node("paused", paused_node)

    graph.set_entry_point("understand")
    graph.add_edge("understand", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "decide_action")

    graph.add_conditional_edges(
        "decide_action",
        _route,
        {
            "escalate": "escalate_to_human",
            "answer": "generate_answer",
            "memory": "memory_answer",
            "collect": "collect",
            "tool": "call_tool",
            "lead_exists": "lead_exists",
            "clarify": "clarify",
            "social": "social",
            "explore": "explore",
            "direction": "direction",
            "paused": "paused",
        },
    )

    for node in (
        "collect", "call_tool", "lead_exists", "clarify",
        "memory_answer", "generate_answer", "escalate_to_human",
        "social", "explore", "direction", "paused",
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


def _known_interests(draft: dict) -> list[str]:
    """Human-readable list of what the user is interested in (services + product)."""
    interests = [p.strip() for p in (draft.get("service_interest") or "").split("+") if p.strip()]
    product = draft.get("product_type")
    if product:
        interests.append(product)
    return interests


def _conversation_mode(result, draft, lead_created, paused, exploring) -> str:
    """One of: answering / exploring / qualifying / paused."""
    action = result.get("action_taken")
    if paused:
        return "paused"
    if action in ("answered_from_kb", "answered_with_memory", "greeted", "asked_clarification"):
        return "answering"
    if exploring or action in ("exploring", "clarifying_direction"):
        return "exploring"
    if lead_created or action in ("collecting_info", "created_lead", "lead_already_exists"):
        return "qualifying"
    return "answering"


def _next_step(result, draft, lead_created, paused, exploring) -> str:
    """A short suggested next step for the operator / UI."""
    if paused:
        return "Qualification paused — offer general guidance only, no lead details."
    if lead_created:
        return "Lead captured — a human can follow up."
    if exploring or result.get("action_taken") == "exploring":
        return "Help the user pick a goal or service; don't ask for company/budget yet."
    if result.get("action_taken") == "clarifying_direction":
        return "Confirm whether to explore or start a request."
    missing = result.get("missing_fields") or []
    label = {
        "service_interest": "the service they need",
        "company": "the company/product name",
        "budget_range": "a rough budget",
        "name": "their name",
        "contact_email": "a contact email",
    }
    if missing:
        return f"Collect {label.get(missing[0], missing[0])}."
    return "Answer questions or offer to start a project."


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
        "saved_fields": [],
        "retrieved": [],
        "sources": [],
        "missing_fields": [],
        "memory_used": False,
        "escalated": False,
        "ticket_created": False,
        "clarification_count": 0,
        "action_taken": None,
        "created_lead_id": None,
        "created_ticket_id": None,
    }

    result: AgentState = get_agent().invoke(state)

    draft = memory.get_draft(session_id)
    lead_created = bool(draft.get("lead_created"))
    result["lead_draft"] = memory.known_fields(session_id)
    result["missing_fields"] = [] if lead_created else memory.missing_fields(session_id)
    result["lead_created"] = lead_created
    result["lead_id"] = draft.get("lead_id")
    result["ticket_created"] = bool(result.get("created_ticket_id"))
    result["clarification_count"] = memory.clarify_count(session_id)

    # --- dialogue policy surface for the UI ---
    paused = bool(draft.get("qualification_paused"))
    exploring = bool(draft.get("exploration_mode"))
    result["qualification_paused"] = paused
    result["exploration_mode"] = exploring
    result["known_interests"] = _known_interests(draft)
    result["mode"] = _conversation_mode(result, draft, lead_created, paused, exploring)
    result["next_step"] = _next_step(result, draft, lead_created, paused, exploring)
    result["dialogue_state"] = memory.dialogue_state(session_id)

    # Remember a short summary of what we just said (dialogue tracking).
    memory.set_flag(session_id, "last_assistant_summary", (result.get("answer") or "")[:160])

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
