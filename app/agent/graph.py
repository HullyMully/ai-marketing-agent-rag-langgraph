"""The conversational agent — an LLM planner with backend action validation.

Each turn flows through a small LangGraph pipeline:

1. ``plan`` — assemble the full context (company profile, relevant knowledge from
   RAG, recent history, session memory, lead draft, ticket state, available
   actions, the latest message) and ask :mod:`app.agent.planner` for a single
   structured decision.
2. ``act`` — the backend *validates* the recommended action and only then
   executes it. The planner can recommend creating a lead or ticket, but the
   deterministic rules here decide whether that actually happens; otherwise the
   assistant asks a natural follow-up instead.

In ``MOCK_LLM`` mode the planner is a deterministic engine, so the whole system
runs and is testable offline. With a real OpenAI-compatible / DeepSeek model the
LLM becomes the reasoning layer while these backend rules keep actions safe.
"""
from __future__ import annotations

import difflib
import re

from langgraph.graph import END, StateGraph

from app.agent import planner
from app.agent.llm import get_llm
from app.agent.memory import get_memory
from app.agent.prompts import FINAL_REPLY_PROMPT, RAG_ANSWER_PROMPT, get_system_persona
from app.agent.state import AgentState
from app.agent.understanding import analyze
from app.agent.validation import validate_lead_creation, validate_ticket_creation
from app.company import get_company
from app.config import settings
from app.rag.retriever import get_retriever
from app.tools.crm_tools import create_lead
from app.tools.escalation import escalate_to_human

_NEW_REQUEST_HINTS = ("start a new request", "create another lead", "new project", "another lead")
_VALID_EMAIL = "@"
_ENTERPRISE_HINTS = ("enterprise", "custom workflow", "custom enterprise")
_ENGLISH_LANGUAGE_PHRASES = (
    "speak english", "english please", "in english", "answer in english",
    "reply in english", "translate to english", "translate into english",
    "idk russian", "i don't know russian", "i dont know russian",
    "i do not know russian",
)
_RUSSIAN_LANGUAGE_PHRASES = (
    "на русском", "по-русски", "по русски", "сможешь на русском",
    "говори на русском", "ответь на русском", "переведи на русский",
    "translate to russian",
)


def _history_text(history: list[dict[str, str]], limit: int = 6) -> str:
    recent = history[-limit:]
    if not recent:
        return "(no previous messages)"
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)


def _is_new_request(message: str) -> bool:
    text = message.lower()
    return any(h in text for h in _NEW_REQUEST_HINTS)


def _previous_assistant_message(history: list[dict[str, str]]) -> str:
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            return turn.get("content", "")
    return ""


def _current_mode(memory, session: str) -> str:
    if memory.get(session, "qualification_paused"):
        return "paused"
    if memory.get(session, "exploration_mode"):
        return "exploring"
    if memory.get(session, "qualification_active"):
        return "qualifying"
    return "answering"


def _detect_language_preference(message: str) -> str:
    """Return a lightweight language preference from the latest user message."""
    text = (message or "").lower()
    if any(phrase in text for phrase in _ENGLISH_LANGUAGE_PHRASES):
        return "en"
    if any(phrase in text for phrase in _RUSSIAN_LANGUAGE_PHRASES) or _looks_russian(message):
        return "ru"
    if re.search(r"[A-Za-z]", message or ""):
        return "en"
    return ""


def _remember_language_preference(memory, session: str, message: str) -> None:
    preferred = _detect_language_preference(message)
    if preferred:
        memory.set_flag(session, "preferred_language", preferred)


def _language_instruction(memory, session: str, message: str) -> str:
    """Instruction passed to the final LLM so replies do not drift languages."""
    preferred = _detect_language_preference(message)
    if preferred:
        memory.set_flag(session, "preferred_language", preferred)
    stored = memory.get(session, "preferred_language")
    text = (message or "").lower()
    if any(phrase in text for phrase in ("translate to english", "translate into english")):
        return (
            "The user explicitly asked for English. Translate the relevant previous "
            "assistant message into English and reply in English."
        )
    if any(phrase in text for phrase in ("переведи на русский", "translate to russian")):
        return (
            "The user explicitly asked for Russian. Translate the relevant previous "
            "assistant message into Russian and reply in Russian."
        )
    if preferred == "en":
        return "Reply in English because the latest user message or explicit request is in English."
    if preferred == "ru":
        return "Reply in Russian because the latest user message or explicit request is in Russian."
    if stored == "en":
        return "No explicit language switch in this turn; keep replying in English."
    if stored == "ru":
        return "No explicit language switch in this turn; keep replying in Russian."
    return "Reply in the same language as the latest user message."


# --------------------------------------------------------------------------- #
# Node 1: build context + plan
# --------------------------------------------------------------------------- #
def plan_node(state: AgentState) -> AgentState:
    """Retrieve knowledge, build the planner context, and get a decision."""
    memory = get_memory()
    session = state["session_id"]
    message = state["user_message"]
    _remember_language_preference(memory, session, message)

    if _is_new_request(message) and memory.is_lead_created(session):
        memory.reset_draft(session)

    # RAG: retrieve relevant chunks so the planner can ground its answer.
    hits = get_retriever().search(message, top_k=3)
    knowledge = [{"text": h.text, "source": h.source} for h in hits]

    recent_history = memory.history(session, limit=14)
    context = {
        "company_profile": get_company().public_dict(),
        "knowledge_context": knowledge,
        "recent_conversation_history": recent_history,
        "previous_assistant_message": _previous_assistant_message(recent_history),
        "session_summary": memory.get(session, "conversation_summary") or "",
        "session_memory": {
            "known_facts": memory.get(session, "known_facts", []),
            "preferred_language": memory.get(session, "preferred_language") or "",
            "dialogue_state": memory.dialogue_state(session),
        },
        "lead_draft": memory.known_fields(session),
        "ticket_state": {
            "ticket_created": bool(memory.get(session, "ticket_created")),
            "lead_created": memory.is_lead_created(session),
        },
        "backend_action_history": (
            [memory.get(session, "last_backend_action")]
            if memory.get(session, "last_backend_action")
            else []
        ),
        "current_assistant_mode": _current_mode(memory, session),
        "available_actions": planner.AVAILABLE_ACTIONS,
        "user_message": message,
    }

    decision = planner.plan(context, memory=memory, session=session)

    state["decision"] = decision
    state["knowledge_context"] = knowledge
    state["intent"] = decision.legacy_intent
    state["user_intent"] = decision.user_intent
    state["confidence"] = decision.confidence
    return state


# --------------------------------------------------------------------------- #
# Node 2: validate + execute the recommended action
# --------------------------------------------------------------------------- #
def act_node(state: AgentState) -> AgentState:
    """Backend validation + safe execution of the planner's recommendation."""
    memory = get_memory()
    session = state["session_id"]
    decision = state["decision"]
    action = decision.recommended_action

    # Surface sources/knowledge regardless of branch.
    state["sources"] = list(decision.sources)
    state["knowledge_used"] = bool(decision.knowledge_used)
    state["memory_used"] = bool(decision.memory_used)
    state["validation"] = {"allowed": None, "reason": "not_applicable", "missing_fields": []}
    state["action_executed"] = False
    memory.remember_facts(session, (decision.memory_updates or {}).get("facts_to_remember", []))

    # Controlled internal planner error: no canned phrase — ask the LLM to write
    # a natural reply from context (deterministic fallback only in mock mode).
    if "planner_error" in (decision.safety_notes or []):
        state["validation"] = {"allowed": False, "reason": "planner_error", "missing_fields": []}
        state["answer"] = _final_reply(
            state, memory, session, decision,
            reason="planner_error", missing=memory.missing_fields(session),
        )
        state["action_taken"] = "answered"
        return state

    if action == "create_lead":
        return _do_create_lead(state, memory, session, decision)
    if action == "create_ticket":
        return _do_create_ticket(state, memory, session, decision)
    if action == "answer_only" and decision.knowledge_used and not decision.assistant_reply:
        return _do_answer_from_knowledge(state, decision)

    # answer_only, ask_clarifying_question, update_lead_draft,
    # pause_qualification, retrieve_knowledge -> final reply is still generated
    # by the reply layer. The planner's assistant_reply is only a draft/context,
    # never the final user-facing text.
    state["answer"] = _final_reply(
        state, memory, session, decision, reason="answer", missing=memory.missing_fields(session),
    )
    state["action_taken"] = decision.legacy_action or _legacy_action_default(action)
    return state


def _do_create_lead(state, memory, session, decision) -> AgentState:
    """Create a CRM lead ONLY if the backend validation layer agrees."""
    draft = memory.get_draft(session)
    user_agrees = bool(memory.get(session, "qualification_active")) or bool(
        (decision.extracted_fields or {}).get("user_agrees_to_proceed")
    )
    result = validate_lead_creation(
        draft=draft,
        lead_created=memory.is_lead_created(session),
        recommended_action="create_lead",
        user_agrees_to_proceed=user_agrees,
    )
    state["validation"] = result.as_dict()
    if not result.allowed:
        # The LLM jumped ahead — never fake success. Ask for what's missing,
        # with the reply written by the LLM (deterministic only in mock mode).
        return _ask_for_missing(state, memory, session, decision, result)

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
    state["action_executed"] = True
    state["action_taken"] = "created_lead"
    service = (draft["service_interest"] or "").lower()
    budget_phrase = f"{budget} budget" if budget and budget != "unspecified" else "budget to confirm"
    # The assistant confirms creation ONLY now that the backend has executed it.
    # In real mode the LLM writes the confirmation; the templated line is an
    # offline (mock) fallback only.
    state["answer"] = _confirm_reply(
        state, memory, session, decision, reason="lead_created",
        fallback=(
            f"Done. I created a lead for {draft['company']}: {service}, {budget_phrase}, "
            f"contact {draft['name']} at {draft['contact_email']}."
        ),
    )
    return state


def _do_create_ticket(state, memory, session, decision) -> AgentState:
    """Open an escalation ticket ONLY if the validation layer agrees."""
    message = state["user_message"]
    a = analyze(message, memory.get_draft(session))
    payload = decision.action_payload or {}
    reason = payload.get("reason", "human_escalation")

    result = validate_ticket_creation(
        message=message,
        asks_for_human=a.asks_for_human,
        is_frustrated=a.user_sentiment == "frustrated",
        recommended_action="create_ticket",
        reason=reason,
        confidence=decision.confidence,
        confidence_threshold=settings.escalation_confidence_threshold,
        ticket_created=bool(memory.get(session, "ticket_created")),
    )
    state["validation"] = result.as_dict()
    if not result.allowed:
        # Not enough to involve a human — clarify instead of opening a ticket.
        state["answer"] = _final_reply(
            state, memory, session, decision, reason=result.reason,
            missing=memory.missing_fields(session),
        )
        state["action_taken"] = "asked_clarification"
        return state

    ticket = escalate_to_human(
        user_id=state.get("user_id") or session,
        summary=payload.get("summary", f"User message: {message}"),
        reason=reason,
    )
    memory.set_flag(session, "ticket_created", True)
    state["created_ticket_id"] = ticket["id"]
    state["escalated"] = True
    state["ticket_created"] = True
    state["action_executed"] = True
    state["action_taken"] = "escalated_to_human"
    target = get_company().escalation_target
    # Confirm escalation ONLY now that the backend has opened the ticket.
    state["answer"] = _confirm_reply(
        state, memory, session, decision, reason="ticket_created",
        fallback=(
            f"I've passed this to a {target} (ticket #{ticket['id']}). "
            "They'll follow up within one business day."
        ),
    )
    return state


def _do_answer_from_knowledge(state, decision) -> AgentState:
    """Generate a grounded RAG answer with the LLM (used when the planner left
    the reply to the backend, e.g. the deterministic mock engine)."""
    if settings.mock_llm:
        state["answer"] = _mock_knowledge_reply(state, decision)
        state["action_taken"] = "answered_from_kb"
        return state

    chunks = [c.get("text", "") for c in state.get("knowledge_context", [])]
    context = "\n\n".join(chunks) or "(no context found)"
    prompt = RAG_ANSWER_PROMPT.format(
        persona=get_system_persona(),
        history=_history_text(state.get("history", [])),
        context=context,
        language_instruction=_language_instruction(get_memory(), state["session_id"], state["user_message"]),
        question=state["user_message"],
    )
    try:
        state["answer"] = get_llm().complete(prompt).strip()
    except Exception:
        state["answer"] = _llm_unavailable_reply()
    state["action_taken"] = "answered_from_kb"
    return state


def _ask_for_missing(state, memory, session, decision, result=None) -> AgentState:
    """Downgrade a premature create_lead into a natural request for what's left."""
    missing = (result.missing_fields if result else None) or memory.missing_fields(session)
    reason = result.reason if result else "missing_required_fields"
    state["answer"] = _final_reply(state, memory, session, decision, reason=reason, missing=missing)
    state["action_taken"] = "collecting_info"
    return state


# --------------------------------------------------------------------------- #
# Final reply generation (LLM writes every user-facing message)
# --------------------------------------------------------------------------- #
def _final_reply(state, memory, session, decision, *, reason: str, missing: list) -> str:
    """Generate the final assistant reply.

    With a real LLM configured, the reply is written fresh by the model from the
    full context plus the backend validation outcome — no canned phrases. In
    offline ``MOCK_LLM`` mode (tests/demo) it falls back to a deterministic,
    context-aware message so the pipeline runs without any API call.
    """
    if settings.mock_llm:
        return _mock_final_reply(state, memory, session, decision, reason, missing)

    chunks = [c.get("text", "") for c in state.get("knowledge_context", [])]
    context = "\n\n".join(chunks) or "(no context retrieved)"
    prompt = FINAL_REPLY_PROMPT.format(
        persona=get_system_persona(),
        history=_history_text(state.get("history", [])),
        context=context,
        lead_draft=memory.known_fields(session) or "(nothing yet)",
        missing=", ".join(missing) or "(none)",
        language_instruction=_language_instruction(memory, session, state["user_message"]),
        conversation_target=getattr(decision, "conversation_target", "unclear"),
        context_relation=getattr(decision, "context_relation", "unclear"),
        user_intent=getattr(decision, "user_intent", "unclear"),
        assistant_mode=getattr(decision, "assistant_mode", "answering"),
        should_continue_qualification=getattr(decision, "should_continue_qualification", False),
        draft_reply=getattr(decision, "assistant_reply", "") or "(none)",
        action=decision.recommended_action,
        validation=_validation_phrase(reason),
        question=state["user_message"],
    )
    try:
        reply = get_llm().complete(prompt).strip()
        if reply:
            return reply
    except Exception:
        return _llm_unavailable_reply()
    return _llm_unavailable_reply()


def _confirm_reply(state, memory, session, decision, *, reason: str, fallback: str) -> str:
    """Confirm an executed backend action in a natural reply.

    In real-LLM mode the model writes the confirmation from the now-confirmed
    facts; ``fallback`` (a templated line) is used only offline in ``MOCK_LLM``
    mode or if the LLM call fails. This guarantees the assistant only claims a
    lead/ticket exists *after* the backend actually created it.
    """
    if settings.mock_llm:
        return fallback
    chunks = [c.get("text", "") for c in state.get("knowledge_context", [])]
    context = "\n\n".join(chunks) or "(no context retrieved)"
    prompt = FINAL_REPLY_PROMPT.format(
        persona=get_system_persona(),
        history=_history_text(state.get("history", [])),
        context=context,
        lead_draft=memory.known_fields(session) or "(nothing yet)",
        missing="(none)",
        language_instruction=_language_instruction(memory, session, state["user_message"]),
        conversation_target=getattr(decision, "conversation_target", "unclear"),
        context_relation=getattr(decision, "context_relation", "unclear"),
        user_intent=getattr(decision, "user_intent", "unclear"),
        assistant_mode=getattr(decision, "assistant_mode", "answering"),
        should_continue_qualification=getattr(decision, "should_continue_qualification", False),
        draft_reply=getattr(decision, "assistant_reply", "") or "(none)",
        action=decision.recommended_action,
        validation=_validation_phrase(reason),
        question=state["user_message"],
    )
    try:
        reply = get_llm().complete(prompt).strip()
        if reply:
            return reply
    except Exception:
        return _llm_unavailable_reply(action_completed="The backend action was completed successfully.")
    return _llm_unavailable_reply(action_completed="The backend action was completed successfully.")


def _validation_phrase(reason: str) -> str:
    return {
        "missing_required_fields": "rejected — required lead details are still missing",
        "user_has_not_agreed": "rejected — the user has not yet agreed to start a request",
        "lead_already_exists": "rejected — a lead already exists for this session",
        "not_an_escalation": "rejected — this does not warrant a human ticket",
        "ticket_already_exists": "rejected — a ticket already exists for this session",
        "planner_error": "the reasoning step produced no clear action",
        "lead_created": "executed — the lead was just created in the CRM; you may confirm it to the user",
        "ticket_created": "executed — the escalation ticket was just created; you may confirm it to the user",
        "answer": "no backend action required",
    }.get(reason, f"reviewed ({reason})")


def _mock_final_reply(state, memory, session, decision, reason: str, missing: list) -> str:
    """Offline stand-in for the final LLM reply layer.

    This intentionally does not return planner.assistant_reply. It uses the same
    structured inputs the real final prompt receives, so mock mode cannot hide a
    bad architecture by replaying deterministic planner templates.
    """
    message = (state.get("user_message") or "").strip()
    text = message.lower()
    target = getattr(decision, "conversation_target", "unclear")
    relation = getattr(decision, "context_relation", "unclear")
    intent = getattr(decision, "user_intent", "unclear")
    should_qualify = bool(getattr(decision, "should_continue_qualification", False))
    preferred_language = _detect_language_preference(message) or memory.get(session, "preferred_language")
    preferred_ru = preferred_language == "ru"

    if reason in ("missing_required_fields", "user_has_not_agreed") and should_qualify:
        return _mock_missing_reply(memory, session, missing, ru=preferred_ru)
    if reason in ("not_an_escalation", "ticket_already_exists"):
        return "I can handle this here for now. What would you like me to clarify?"

    if text in {"please", "pls", "пожалуйста"}:
        return "Sure. What do you need help with?"
    if text in {"answer", "ответь"}:
        return "What should I answer? Send me the question."
    if text in {"okay", "ok", "ок", "окей"}:
        return "Хорошо. Что делаем дальше?" if preferred_ru else "Okay. What would you like to do next?"

    if _is_translate_to_russian_text(text):
        memory.set_flag(session, "preferred_language", "ru")
        return _mock_translate_recent_assistant_to_ru(state.get("history", []))

    if _is_russian_language_text(text):
        memory.set_flag(session, "preferred_language", "ru")
        return "Да, могу отвечать на русском. Что хочешь узнать или сделать?"

    if _is_translate_to_english_text(text):
        memory.set_flag(session, "preferred_language", "en")
        return _mock_translate_recent_assistant_to_en(state.get("history", []))

    if _is_english_language_text(text):
        memory.set_flag(session, "preferred_language", "en")
        return "Sure, I'll use English from here. What do you need help with?"

    if target == "assistant_product":
        return _mock_capability_reply(preferred_ru)

    if target == "previous_reply" or relation == "asks_meta_question":
        if _asks_what_assistant_needs(text) and memory.has_any_field(session):
            return _mock_missing_reply(memory, session, missing, ru=preferred_ru)
        if "email" in text:
            if preferred_ru:
                return (
                    "Email нужен только если ты хочешь создать заявку для follow-up. "
                    "Для обычных вопросов можно продолжать без контактных данных."
                )
            return (
                "Email is only needed if you decide to create a follow-up request. "
                "For normal questions, you can keep chatting without sharing contact details."
            )
        if preferred_ru:
            return (
                "Я могу переключиться на твой последний вопрос и не продолжать старую ветку. "
                "Скажи, что именно нужно объяснить или сделать."
            )
        return (
            "I meant that we can pause the earlier thread and answer your latest question first. "
            "You do not have to fill out project details unless you want follow-up."
        )

    if intent == "complaint":
        return _rotate_reply(memory, session, "mock_complaint_reply_count", [
            "I can keep helping, but I need the conversation to stay usable. Tell me what you want fixed or explained.",
            "I'm here to help, not argue. If you want to continue, send the actual issue.",
        ])

    if target == "unrelated" or intent == "unrelated":
        return _mock_unrelated_reply(memory, session, message)

    if intent == "greeting":
        if _looks_russian(message):
            return _rotate_reply(memory, session, "mock_ru_greeting_reply_count", [
                "Привет! Я на связи. Чем помочь?",
                "Привет. Расскажи, что нужно разобрать.",
            ])
        return _rotate_reply(memory, session, "mock_greeting_reply_count", [
            "Hey, good to see you. What would you like help with?",
            "Hi, I'm here. What do you need?",
        ])

    if intent == "casual_chat":
        if "как дела" in text or "как ты" in text:
            return _rotate_reply(memory, session, "mock_ru_casual_reply_count", [
                "Всё нормально, спасибо. Я здесь, чтобы помочь — что разбираем?",
                "Нормально, спасибо. Что хочешь сделать дальше?",
            ])
        return _rotate_reply(memory, session, "mock_casual_reply_count", [
            "I'm doing okay, thanks. What can I help you with?",
            "Doing fine, thanks. What are we working on?",
        ])

    if intent == "confusion" or relation == "asks_clarification":
        if "new" in text or "customer" in text or "нов" in text:
            if preferred_ru:
                return _rotate_reply(memory, session, "mock_ru_beginner_reply_count", [
                    "Конечно. Я могу объяснить, что умеет ассистент, ответить по компании или помочь оформить заявку.",
                    "Если ты новый клиент, начни с простого: что хочешь узнать или какую задачу решить?",
                ])
            return _rotate_reply(memory, session, "mock_beginner_reply_count", [
                "Welcome. I can help you understand the app, learn about the company, or figure out what to do next.",
                "No problem. Since you're new, start with what you came here to do, even roughly.",
            ])
        if preferred_ru:
            return _rotate_reply(memory, session, "mock_ru_confusion_reply_count", [
                "Конечно, помогу. Ты хочешь понять это приложение, узнать о компании или решить другую задачу?",
                "Без проблем. Опиши ситуацию одним предложением, даже примерно.",
            ])
        return _rotate_reply(memory, session, "mock_confusion_reply_count", [
            "Sure, I can help. Are you trying to understand this app, ask about the company, or solve something else?",
            "No problem. Tell me the situation in one sentence, even roughly.",
            "I can help from there. What is the first thing you want to figure out?",
        ])

    if getattr(decision, "knowledge_used", False):
        return _mock_knowledge_reply(state, decision)

    if should_qualify and getattr(decision, "recommended_action", "") in {
        "ask_clarifying_question", "update_lead_draft",
    }:
        return _mock_missing_reply(memory, session, missing, ru=preferred_ru)

    if message:
        return _rotate_reply(memory, session, "mock_generic_reply_count", [
            "Понял. Расскажи чуть подробнее, чтобы я ответил по делу.",
            "Окей. С чем именно помочь?",
            "Могу помочь; пришли конкретный вопрос или цель.",
        ] if preferred_ru else [
            "Got it. Tell me a little more so I can answer usefully.",
            "Okay. What should I help with specifically?",
            "I can help; send the concrete question or goal.",
        ])
    return _safe_fallback_reply()


def _mock_missing_reply(memory, session, missing: list, *, ru: bool = False) -> str:
    if ru:
        label = {
            "name": "имя",
            "company": "название компании или продукта",
            "contact_email": "email для связи",
            "service_interest": "какая помощь нужна",
            "budget_range": "примерный бюджет",
        }
        wanted = [label.get(m, m) for m in (missing or memory.missing_fields(session))[:2]]
        if not wanted:
            return "Базовые данные уже есть. Подготовить заявку для follow-up?"
        joined = " и ".join(wanted)
        return _rotate_reply(memory, session, "mock_ru_missing_reply_count", [
            "Чтобы подготовить заявку, мне ещё нужно: " + joined + ".",
            "Сейчас не хватает таких данных: " + joined + ".",
            "Для заявки пришли, пожалуйста: " + joined + ".",
        ])

    label = {
        "name": "your name",
        "company": "the company or product name",
        "contact_email": "a follow-up email",
        "service_interest": "what you want help with",
        "budget_range": "a rough budget range",
    }
    wanted = [label.get(m, m) for m in (missing or memory.missing_fields(session))[:2]]
    if not wanted:
        return "I have the basics. Should I prepare the follow-up request now?"
    joined = " and ".join(wanted)
    return _rotate_reply(memory, session, "mock_missing_reply_count", [
        "To prepare a follow-up request, I still need " + joined + ".",
        "Right now I need " + joined + " to prepare the request.",
        "Please send " + joined + ", and I can keep building the request.",
    ])


def _mock_unrelated_reply(memory, session, message: str) -> str:
    text = message.lower()
    preferred_language = _detect_language_preference(message) or memory.get(session, "preferred_language")
    ru = preferred_language == "ru"
    if "911" in text or "112" in text or "emergency" in text:
        return (
            "I can't call emergency services for you. If someone is in danger, call 911 "
            "or your local emergency number from your phone now."
        )
    if "open" in text and ("can" in text or "bottle" in text or "coke" in text):
        return (
            "If it is a plastic bottle, twist the cap counterclockwise while holding the bottle firmly. "
            "If it is a can, lift the pull tab and press it back until it opens."
        )
    if ru:
        return _rotate_reply(memory, session, "mock_ru_unrelated_reply_count", [
            "Могу помочь и с этим. Уточни одну деталь, чтобы я не гадал.",
            "Да, разберём. Что именно нужно сделать?",
        ])
    if message:
        return _rotate_reply(memory, session, "mock_unrelated_reply_count", [
            "I can answer that too. What exactly do you want to know?",
            "Sure, I can help with that. Give me one detail so I don't guess.",
        ])
    return _safe_fallback_reply()


def _mock_capability_reply(ru: bool) -> str:
    if ru:
        return (
            "Я AI-ассистент в этом чате: могу отвечать на вопросы о компании по базе знаний, объяснять услуги и цены, "
            "помогать понять, что тебе нужно, собрать заявку/lead и при необходимости передать вопрос человеку."
        )
    return (
        "This chat assistant can answer questions about the configured company, explain services or pricing, "
        "help you figure out what you need, collect a lead request, or escalate to a human when needed."
    )


def _mock_knowledge_reply(state, decision) -> str:
    message = (state.get("user_message") or "").lower()
    ru = _looks_russian(state.get("user_message", ""))
    if "what can you do" in message or "what do you do" in message:
        return _mock_capability_reply(ru)
    if "pricing" in message or "price" in message or "cost" in message:
        return (
            "Pricing depends on the service scope and campaign needs. I can summarize the available packages or help you prepare a request."
        )
    if "service" in message or "offer" in message:
        return (
            "The company can help with marketing work such as paid ads, SEO, analytics setup, and landing-page improvements."
        )
    text = _first_useful_knowledge_sentence(state.get("knowledge_context", []))
    if text:
        return text
    return _mock_capability_reply(ru)


def _first_useful_knowledge_sentence(chunks: list[dict[str, str]]) -> str:
    banned = {"required fields", "lead qualification policy", "ticket creation", "backend"}
    for chunk in chunks:
        raw = (chunk.get("text") or "").strip()
        for line in raw.splitlines():
            text = line.strip("# -*\t ").strip()
            if not text:
                continue
            lower = text.lower()
            if any(b in lower for b in banned):
                continue
            return text[:260]
    return ""


def _mock_translate_recent_assistant_to_ru(history: list[dict[str, str]]) -> str:
    assistant_turns = [
        turn.get("content", "") for turn in history
        if turn.get("role") == "assistant" and turn.get("content")
    ][-3:]
    if not assistant_turns:
        return "Пока нечего переводить: у меня нет предыдущих сообщений в этой сессии."
    return (
        "Конечно. Коротко по-русски: я могу помочь разобраться с приложением, "
        "ответить на вопросы о компании, объяснить услуги или собрать заявку, если ты захочешь."
    )


def _mock_translate_recent_assistant_to_en(history: list[dict[str, str]]) -> str:
    assistant_turns = [
        turn.get("content", "") for turn in history
        if turn.get("role") == "assistant" and turn.get("content")
    ][-3:]
    if not assistant_turns:
        return "There is nothing to translate yet because I do not have an earlier assistant message in this session."
    return (
        "Sure. In English: I can help you understand the app, answer company questions, "
        "explain services, or collect a request if you choose to start one."
    )


def _is_russian_language_text(text: str) -> bool:
    return any(
        phrase in text
        for phrase in ("на русском", "по-русски", "по русски", "сможешь на русском")
    )


def _is_english_language_text(text: str) -> bool:
    return any(phrase in text for phrase in _ENGLISH_LANGUAGE_PHRASES)


def _is_translate_to_russian_text(text: str) -> bool:
    return any(
        phrase in text
        for phrase in ("переведи на русский", "переведи свои сообщения", "translate to russian")
    )


def _is_translate_to_english_text(text: str) -> bool:
    return any(phrase in text for phrase in ("translate to english", "translate into english"))


def _asks_what_assistant_needs(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "what do you want to know", "what do you need", "what info do you need",
            "what should i send", "что тебе нужно", "что нужно",
        )
    )


def _deterministic_reply(memory, session, reason: str, missing: list) -> str:
    """Offline (mock-mode) fallback reply when no LLM is configured."""
    if reason in ("missing_required_fields", "user_has_not_agreed"):
        label = {
            "name": "your name", "company": "your company",
            "contact_email": "the best email", "service_interest": "what you need help with",
            "budget_range": "a rough budget",
        }
        wanted = ", ".join(label.get(m, m) for m in (missing or memory.missing_fields(session)))
        return f"Almost there — could you share {wanted or 'a few more details'}?"
    if reason in ("not_an_escalation", "ticket_already_exists"):
        return "I can handle this here for now. What would you like me to clarify?"
    return _safe_fallback_reply()


def _legacy_action_default(action: str) -> str:
    return {
        "answer_only": "answered",
        "ask_clarifying_question": "asked_clarification",
        "update_lead_draft": "collecting_info",
        "pause_qualification": "qualification_paused",
        "retrieve_knowledge": "answered_from_kb",
    }.get(action, "answered")


def _safe_fallback_reply() -> str:
    return "I'm here. Could you rephrase what you want to do next?"


def _llm_unavailable_reply(action_completed: str | None = None) -> str:
    if action_completed:
        return (
            f"{action_completed} The language model is unavailable right now, "
            "so I cannot generate the normal conversational reply."
        )
    return (
        "The language model is unavailable right now, so I cannot generate a proper "
        "answer for this turn. Please try again in a moment."
    )


def _looks_russian(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text))


def _rotate_reply(memory, session: str, key: str, options: list[str]) -> str:
    if not options:
        return _safe_fallback_reply()
    idx = max(0, int(memory.bump(session, key)) - 1)
    return options[idx % len(options)]


def _guard_repeated_reply(state, memory, session: str, decision, answer: str) -> str:
    """Prevent identical/near-identical consecutive assistant replies."""
    candidate = (answer or "").strip()
    if not candidate:
        return candidate
    recent = [
        turn.get("content", "")
        for turn in state.get("history", [])
        if turn.get("role") == "assistant" and turn.get("content")
    ][-3:]
    if not any(_too_similar(candidate, previous) for previous in recent):
        return candidate

    if settings.mock_llm:
        return _mock_repetition_rewrite(state, memory, session, decision, candidate, recent)

    chunks = [c.get("text", "") for c in state.get("knowledge_context", [])]
    context = "\n\n".join(chunks) or "(no context retrieved)"
    prompt = (
        f"{get_system_persona()}\n\n"
        "The draft reply is too similar to a recent assistant reply. Rewrite it in a fresh way.\n"
        "Answer the latest user message directly. Do not repeat the previous answer. "
        "Do not output JSON or markdown.\n\n"
        f"Recent assistant replies:\n{_history_text([{'role': 'assistant', 'content': r} for r in recent])}\n\n"
        f"Relevant company knowledge:\n{context}\n\n"
        f"Planner target: {getattr(decision, 'conversation_target', 'unclear')}\n"
        f"Planner relation: {getattr(decision, 'context_relation', 'unclear')}\n"
        f"Latest user message: {state.get('user_message', '')}\n\n"
        f"Draft reply to rewrite: {candidate}\n\n"
        "Fresh reply:"
    )
    try:
        rewritten = get_llm().complete(prompt).strip()
        if rewritten and not any(_too_similar(rewritten, previous) for previous in recent):
            return rewritten
    except Exception:
        return candidate
    return candidate


def _too_similar(a: str, b: str) -> bool:
    na, nb = _normalise_reply(a), _normalise_reply(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if min(len(na), len(nb)) > 40 and (na in nb or nb in na):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.88


def _normalise_reply(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", text.lower())).strip()


def _mock_repetition_rewrite(state, memory, session: str, decision, candidate: str, recent: list[str]) -> str:
    profile = get_company()
    message = (state.get("user_message") or "").lower()
    target = getattr(decision, "conversation_target", "unclear")
    relation = getattr(decision, "context_relation", "unclear")
    mode = getattr(decision, "assistant_mode", "answering")
    intent = getattr(decision, "user_intent", "unclear")
    variant = max(0, int(memory.bump(session, "repeat_rewrite_count")) - 1)

    if mode == "paused" or relation == "rejects_or_pauses":
        options = [
            "I'll pause the questions here and won't ask for lead details. We can stay general.",
            "Understood. The qualification thread is paused, and you can ask about anything else.",
            "Got it; I'll stop that line of questions. We can continue without collecting details.",
        ]
        reply = options[variant % len(options)]
    elif target == "assistant_product" or "app" in message or "assistant" in message:
        options = [
            (
                f"This is {profile.brand_label}: a chat for {profile.display_name}. "
                "It can answer company questions, and it only gathers project details when you choose that path."
            ),
            (
                f"You're using {profile.brand_label}. Think of it as a guided chat for {profile.display_name}, "
                "not a form you have to complete."
            ),
        ]
        reply = options[variant % len(options)]
    elif target == "previous_reply" or relation == "asks_meta_question":
        options = [
            (
                "Let me clarify: the earlier questions are optional unless you want a follow-up request. "
                "Your latest question is what I should answer now."
            ),
            "You do not need to continue the earlier thread. Ask the thing you mean, and I'll answer it directly.",
        ]
        reply = options[variant % len(options)]
    elif intent == "casual_chat":
        options = [
            "I'm here and ready to help. What do you want to work through?",
            "Doing fine, thanks. Tell me what you need help with.",
        ]
        reply = options[variant % len(options)]
    elif intent == "complaint":
        options = [
            "I can help if we keep it constructive. What do you want me to fix or explain?",
            "Let's keep this useful. Tell me the actual problem, and I'll try to help.",
        ]
        reply = options[variant % len(options)]
    elif intent == "unrelated":
        options = [
            "I can help with that too. Give me one more detail so I answer the right thing.",
            "Sure. What part of that do you want help with?",
        ]
        reply = options[variant % len(options)]
    elif intent == "greeting":
        options = [
            "Hello again. What can I help with?",
            "Hi, I'm here. What do you need?",
        ]
        reply = options[variant % len(options)]
    elif intent == "confusion":
        options = [
            "Sure, I can help. Are you asking about this app, the company, or something else?",
            "No problem. Tell me the situation in one sentence, even roughly.",
        ]
        reply = options[variant % len(options)]
    else:
        options = [
            "Got it. What would you like me to do next?",
            "I can help; give me a little more context.",
            "Tell me the next thing you want answered.",
        ]
        reply = options[variant % len(options)]

    if any(_too_similar(reply, previous) for previous in recent):
        fallbacks = [
            "What do you need right now?",
            "Give me one concrete detail and I'll help from there.",
            "I'm here; tell me the specific question.",
        ]
        for option in fallbacks:
            if not any(_too_similar(option, previous) for previous in recent):
                return option
        return f"{fallbacks[variant % len(fallbacks)]} ({variant + 1})"
    return reply


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph():
    """Compile and return the planner→act conversation graph."""
    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("act", act_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "act")
    graph.add_edge("act", END)
    return graph.compile()


_compiled = None


def get_agent():
    """Return a compiled, cached agent graph."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


# --------------------------------------------------------------------------- #
# Product-facing surface
# --------------------------------------------------------------------------- #
def _known_interests(draft: dict) -> list[str]:
    interests = [p.strip() for p in (draft.get("service_interest") or "").split("+") if p.strip()]
    if draft.get("product_type"):
        interests.append(draft["product_type"])
    return interests


def _conversation_mode(decision, lead_created, paused, exploring) -> str:
    mode = getattr(decision, "assistant_mode", "answering")
    if paused:
        return "paused"
    if mode == "casual":
        return "answering"
    if mode in ("answering", "exploring", "qualifying", "escalating"):
        return "qualifying" if mode == "escalating" else mode
    if lead_created:
        return "qualifying"
    return "answering"


def _next_step(decision, draft, lead_created, paused, exploring, missing) -> str:
    if paused:
        return "Qualification paused — offer general guidance only, no lead details."
    if lead_created:
        return "Lead captured — a human can follow up."
    if exploring or decision.assistant_mode == "exploring":
        return "Help the user pick a goal or service; don't ask for company/budget yet."
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


def _update_summary(memory, session: str, history: list) -> None:
    """Maintain a short rolling conversation summary once the chat gets long."""
    if len(history) < 8:
        return
    draft = memory.get_draft(session)
    bits = []
    if draft.get("service_interest"):
        bits.append(f"wants {draft['service_interest']}")
    if draft.get("product_type"):
        bits.append(f"for a {draft['product_type']}")
    if draft.get("company"):
        bits.append(f"company {draft['company']}")
    if memory.get(session, "qualification_paused"):
        bits.append("qualification paused")
    elif memory.get(session, "exploration_mode"):
        bits.append("exploring options")
    summary = "User " + ", ".join(bits) + "." if bits else ""
    if summary:
        memory.set_flag(session, "conversation_summary", summary)


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

    decision = result.get("decision")
    result["answer"] = _guard_repeated_reply(
        result, memory, session_id, decision, result.get("answer", "")
    )
    draft = memory.get_draft(session_id)
    lead_created = bool(draft.get("lead_created"))
    paused = bool(draft.get("qualification_paused"))
    exploring = bool(draft.get("exploration_mode"))
    missing = [] if lead_created else memory.missing_fields(session_id)

    result["extracted"] = dict(getattr(decision, "extracted_fields", {}) or {})
    result["lead_draft"] = memory.known_fields(session_id)
    result["missing_fields"] = missing
    result["lead_created"] = lead_created
    result["lead_id"] = draft.get("lead_id")
    result["ticket_created"] = bool(result.get("created_ticket_id"))
    result["clarification_count"] = memory.clarify_count(session_id)
    result["qualification_paused"] = paused
    result["exploration_mode"] = exploring
    result["known_interests"] = _known_interests(draft)
    result["mode"] = _conversation_mode(decision, lead_created, paused, exploring)
    result["next_step"] = _next_step(decision, draft, lead_created, paused, exploring, missing)
    result["dialogue_state"] = memory.dialogue_state(session_id)
    result["recommended_action"] = getattr(decision, "recommended_action", "answer_only")
    result["conversation_target"] = getattr(decision, "conversation_target", "unclear")
    result["context_relation"] = getattr(decision, "context_relation", "unclear")
    result["should_continue_qualification"] = bool(
        getattr(decision, "should_continue_qualification", False)
    )
    result["assistant_reply"] = result.get("answer", "")
    result["confidence"] = float(getattr(decision, "confidence", 1.0) or 1.0)
    result["llm_runtime_mode"] = "mock" if settings.mock_llm else "llm"
    result["mock_llm"] = bool(settings.mock_llm)

    # --- planner / validation transparency metadata ---
    result["planner_decision"] = (
        decision.as_public_dict()
        if decision is not None and hasattr(decision, "as_public_dict")
        else {}
    )
    result["validation"] = result.get("validation") or {
        "allowed": None, "reason": "not_applicable", "missing_fields": [],
    }
    result["action_executed"] = bool(result.get("action_executed"))

    memory.set_flag(session_id, "last_assistant_summary", (result.get("answer") or "")[:160])
    memory.set_flag(session_id, "last_backend_action", result.get("action_taken"))
    _update_summary(memory, session_id, history)

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
