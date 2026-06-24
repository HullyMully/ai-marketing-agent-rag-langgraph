"""LLM dialogue planner — the assistant's reasoning layer.

For every user message the planner is given the full conversational context
(company profile, relevant knowledge, recent history, session memory, the lead
draft and ticket state, the available backend actions, and the latest message)
and returns a single structured decision: what the user means, what to say next,
and which backend action (if any) should run.

Two backends, one contract:

* ``_llm_plan`` builds a strict JSON prompt, calls the configured
  OpenAI-compatible / DeepSeek model, and parses the JSON robustly. It never
  crashes on bad output — it repairs lightly and otherwise falls back.
* ``_mock_plan`` is a deterministic engine used in ``MOCK_LLM`` mode and as the
  safe fallback. It produces the same decision contract without any API calls,
  so the product runs and is testable fully offline.

The planner only *recommends* actions. The backend (see ``app.agent.graph``)
validates and executes them — the LLM can never create a lead or ticket on its
own.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agent import responses
from app.agent.llm import get_llm
from app.agent.understanding import Analysis, analyze

logger = logging.getLogger("assistant.planner")

# Actions the planner may recommend; the backend validates each before running.
AVAILABLE_ACTIONS = [
    "answer_only",
    "update_lead_draft",
    "create_lead",
    "create_ticket",
    "ask_clarifying_question",
    "pause_qualification",
    "retrieve_knowledge",
]


class PlannerError(Exception):
    """Raised internally when the model cannot produce a valid decision."""


# --------------------------------------------------------------------------- #
# Pydantic schema for the planner's structured decision
# --------------------------------------------------------------------------- #
class UserIntent(str, Enum):
    greeting = "greeting"
    casual_chat = "casual_chat"
    ask_services = "ask_services"
    ask_pricing = "ask_pricing"
    ask_process = "ask_process"
    start_project = "start_project"
    provide_lead_info = "provide_lead_info"
    ask_human = "ask_human"
    complaint = "complaint"
    meta_question = "meta_question"
    clarification = "clarification"
    confusion = "confusion"
    unrelated = "unrelated"
    unclear = "unclear"


class ConversationTarget(str, Enum):
    configured_company = "configured_company"
    user_project = "user_project"
    assistant_product = "assistant_product"
    previous_reply = "previous_reply"
    unrelated = "unrelated"
    unclear = "unclear"


class ContextRelation(str, Enum):
    continues_previous_topic = "continues_previous_topic"
    switches_topic = "switches_topic"
    asks_clarification = "asks_clarification"
    asks_meta_question = "asks_meta_question"
    provides_requested_info = "provides_requested_info"
    rejects_or_pauses = "rejects_or_pauses"
    unclear = "unclear"


class AssistantMode(str, Enum):
    answering = "answering"
    exploring = "exploring"
    qualifying = "qualifying"
    paused = "paused"
    escalating = "escalating"
    casual = "casual"


class RecommendedAction(str, Enum):
    answer_only = "answer_only"
    update_lead_draft = "update_lead_draft"
    create_lead = "create_lead"
    create_ticket = "create_ticket"
    ask_clarifying_question = "ask_clarifying_question"
    pause_qualification = "pause_qualification"
    retrieve_knowledge = "retrieve_knowledge"


class ExtractedFields(BaseModel):
    """Lead fields the planner pulled out of the latest user message."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    service_interest: str | None = None
    budget_range: str | None = None
    product_type: str | None = None
    budget_unknown: bool | None = None
    user_agrees_to_proceed: bool | None = None
    notes: str | None = None


class MemoryUpdates(BaseModel):
    model_config = ConfigDict(extra="ignore")

    facts_to_remember: list[str] = Field(default_factory=list)
    lead_draft_updates: dict = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    """Strict schema every LLM planner decision must validate against."""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    conversation_target: ConversationTarget = ConversationTarget.unclear
    context_relation: ContextRelation = ContextRelation.unclear
    should_continue_qualification: bool = False
    why_this_response: str = ""
    user_intent: UserIntent = UserIntent.unclear
    assistant_mode: AssistantMode = AssistantMode.answering
    extracted_fields: ExtractedFields = Field(default_factory=ExtractedFields)
    memory_updates: MemoryUpdates = Field(default_factory=MemoryUpdates)
    missing_fields: list[str] = Field(default_factory=list)
    recommended_action: RecommendedAction = RecommendedAction.answer_only
    action_payload: dict = Field(default_factory=dict)
    assistant_reply: str = ""
    knowledge_used: bool = False
    sources: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    safety_notes: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, v))


def validate_planner_output(data: dict) -> PlannerOutput:
    """Validate a raw decision dict against the planner schema.

    Raises :class:`pydantic.ValidationError` if the data does not conform.
    """
    return PlannerOutput.model_validate(data)

# Fields that signal the user genuinely wants to start a request.
_CONCRETE_FIELDS = ("company", "contact_email", "name", "budget_range")
_PROCEED = (
    "yes", "yeah", "yep", "sure", "go ahead", "let's do it", "lets do it",
    "continue", "proceed", "create the request", "start the request",
    "prepare a request", "sounds good", "do it", "collect details", "collect",
)


@dataclass
class PlannerDecision:
    """Structured decision returned for one user message."""

    conversation_target: str = "unclear"
    context_relation: str = "unclear"
    should_continue_qualification: bool = False
    why_this_response: str = ""
    user_intent: str = "unclear"
    assistant_mode: str = "answering"
    extracted_fields: dict = field(default_factory=dict)
    memory_updates: dict = field(default_factory=lambda: {"facts_to_remember": [], "lead_draft_updates": {}})
    missing_fields: list = field(default_factory=list)
    recommended_action: str = "answer_only"
    action_payload: dict = field(default_factory=dict)
    assistant_reply: str = ""
    knowledge_used: bool = False
    sources: list = field(default_factory=list)
    confidence: float = 0.5
    safety_notes: list = field(default_factory=list)

    # --- bridge fields for the existing UI/metrics (not part of the LLM schema) ---
    legacy_intent: str = "unknown"
    legacy_action: str = ""
    memory_used: bool = False

    def as_public_dict(self) -> dict:
        """The JSON-schema portion (what an LLM would return)."""
        keys = (
            "conversation_target", "context_relation",
            "should_continue_qualification", "user_intent", "assistant_mode",
            "extracted_fields", "memory_updates", "missing_fields",
            "recommended_action", "action_payload", "assistant_reply",
            "knowledge_used", "sources", "confidence", "safety_notes",
        )
        return {k: v for k, v in asdict(self).items() if k in keys}


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def plan(context: dict, *, memory=None, session: str | None = None) -> PlannerDecision:
    """Return a :class:`PlannerDecision` for the given context.

    Uses the real LLM when configured; otherwise the deterministic mock engine.
    Any failure in the LLM path falls back to the mock engine so a turn never
    crashes on bad model output.
    """
    from app.config import settings

    if settings.mock_llm:
        return _mock_plan(context, memory, session)
    try:
        return _llm_plan(context, memory, session)
    except Exception as exc:  # never crash a turn on LLM/parsing problems
        logger.warning("LLM planner failed (%s); using deterministic fallback", type(exc).__name__)
        decision = _mock_plan(context, memory, session)
        decision.safety_notes.append("llm_fallback")
        return decision


# --------------------------------------------------------------------------- #
# Real LLM backend
# --------------------------------------------------------------------------- #
_PLANNER_INSTRUCTIONS = """You are the reasoning layer of a company's AI customer assistant.
Read the CONTEXT and the latest user message, then decide what the assistant should do.

Return ONLY a single JSON object (no prose, no markdown fences) with EXACTLY these keys:
{
  "conversation_target": "configured_company | user_project | assistant_product | previous_reply | unrelated | unclear",
  "context_relation": "continues_previous_topic | switches_topic | asks_clarification | asks_meta_question | provides_requested_info | rejects_or_pauses | unclear",
  "should_continue_qualification": false,
  "why_this_response": "short internal explanation, never shown to the user",
  "user_intent": "greeting | casual_chat | ask_services | ask_pricing | ask_process | start_project | provide_lead_info | ask_human | complaint | meta_question | clarification | confusion | unrelated | unclear",
  "assistant_mode": "answering | exploring | qualifying | paused | escalating | casual",
  "extracted_fields": {"name": null, "company": null, "email": null, "phone": null, "service_interest": null, "budget_range": null, "product_type": null, "budget_unknown": null, "user_agrees_to_proceed": null, "notes": null},
  "memory_updates": {"facts_to_remember": [], "lead_draft_updates": {}},
  "missing_fields": [],
  "recommended_action": "answer_only | update_lead_draft | create_lead | create_ticket | ask_clarifying_question | pause_qualification | retrieve_knowledge",
  "action_payload": {},
  "assistant_reply": "short natural reply to the user",
  "knowledge_used": true,
  "sources": [],
  "confidence": 0.0,
  "safety_notes": []
}

Behaviour rules (follow strictly):
- The latest user message is the main task. Use history as context, not as permission to continue the previous flow forever.
- First decide what the latest message is about: the configured company, the user's project, this assistant/app, the previous assistant reply, something unrelated, or unclear.
- Decide whether it continues the previous topic, switches topic, asks for clarification/meta explanation, provides requested info, or rejects/pauses.
- Set should_continue_qualification=true only when the user clearly wants to start/proceed with a project or naturally provides lead details. Set it false for greetings, confusion, casual chat, meta/app questions, unrelated messages, refusals, or topic switches.
- Never expose why_this_response in assistant_reply. It is internal debugging metadata only.
- Do NOT use fixed menus, scripted phrases, or canned templates. Write every assistant_reply freshly in your own words, grounded in the CONTEXT.
- Match the latest user language unless the user explicitly asks to switch or translate.
  If they say "SPEAK ENGLISH PLEASE", "Translate to English", etc., reply in English immediately.
  If they ask for Russian or write in Russian, reply in Russian. Do not let older turns override the latest explicit language request.
- If the user asks to translate a previous assistant message, translate the relevant previous assistant message; do not continue qualification.
- Treat misspelled greetings, casual messages and confused beginner messages as normal conversation. Infer politely when obvious; otherwise ask one natural clarification.
- Swearing plus a help request can be frustration/confusion, not necessarily an escalation. Set create_ticket only for explicit human/escalation requests or real support complaints.
- For emergency requests, say the assistant cannot call emergency services and recommend contacting local emergency services directly; do not create a business support ticket unless the user asks for company support.
- Do NOT pretend that a lead or a ticket was created. Do NOT claim any backend action was completed — the backend executes and confirms actions, not you. You only *recommend* an action.
- Keep assistant_reply short and natural (1-3 sentences), no corporate filler, no JSON, no raw knowledge dumps.
- Preserve memory across turns: reuse facts already in the lead draft, session summary and history instead of re-asking. Put durable facts in memory_updates.facts_to_remember and field updates in memory_updates.lead_draft_updates.
- Extract lead fields naturally from the user's words; only set extracted_fields you actually saw, leave the rest null. Set user_agrees_to_proceed=true only when the user clearly agrees to start a request; set budget_unknown=true only when they say they have no budget figure.
- Ask only one or two useful questions at a time.
- Do NOT create a lead on greetings, casual chat, pricing questions, app/meta questions, confusion, or general questions. Recommend create_lead only when the user clearly wants to proceed AND name, company, email, service_interest and budget are known (or budget is explicitly unknown and they agreed to proceed). Otherwise recommend ask_clarifying_question or update_lead_draft.
- Do NOT create a ticket for ordinary confusion, jokes, swearing, "what do you mean?", "I don't remember", "I told you", greetings, or general service/pricing questions. Recommend create_ticket only when the user explicitly asks for a human/manager/operator/specialist/support, has a real complaint needing escalation, or needs a custom/enterprise/human review.
- If the user is confused, explain instead of pushing a form. If the user refuses or gets annoyed, pause qualification (pause_qualification).
- If the user asks a meta-question (e.g. "what do you mean?", "what did I tell you?", "what is this app?", "why do you need my email?"), answer it directly with answer_only.
- Use the provided knowledge to answer service/pricing/process questions; set knowledge_used and sources accordingly. Summarize; never paste raw context.
"""

_REPAIR_NOTE = (
    "\n\nYour previous output was NOT valid against the schema. "
    "Return ONLY a single corrected JSON object with exactly the required keys "
    "and valid enum values. No markdown, no prose, no comments."
)


def _llm_plan(context: dict, memory, session: str | None) -> PlannerDecision:
    prompt = build_planner_prompt(context)
    llm = get_llm()

    output = _request_validated_output(llm, prompt)
    if output is None:
        # Two attempts (original + one JSON-repair) both failed: return a
        # controlled internal planner error rather than crashing the turn. The
        # backend will generate a natural reply for the user.
        logger.warning("planner could not produce a valid decision after repair")
        return _planner_error_decision(context)

    data = _output_to_dict(output)
    decision = _decision_from_json(data, context)

    # Deterministic extraction stays authoritative for structured fields
    # (email/budget validity etc.); merge it over whatever the LLM proposed.
    draft = memory.get_draft(session) if (memory and session) else {}
    message = context["user_message"]
    det = analyze(message, draft)
    for key, value in det.fields.items():
        if value and not decision.extracted_fields.get(key):
            decision.extracted_fields[key] = value
    decision.legacy_intent = _legacy_intent(decision.user_intent, det)

    # Persist to session memory the same way the deterministic engine does, so
    # the backend sees an up-to-date draft and dialogue state regardless of which
    # planner produced the decision.
    if memory and session and not memory.is_lead_created(session):
        if not _should_merge_lead_fields({
            "conversation_target": decision.conversation_target,
            "context_relation": decision.context_relation,
            "should_continue_qualification": decision.should_continue_qualification,
        }):
            decision.extracted_fields = {}
        merged = Analysis(
            intent=det.intent,
            fields={**decision.extracted_fields},
            budget_unknown=det.budget_unknown or bool(decision.extracted_fields.get("budget_unknown")),
            additive_service=det.additive_service,
        )
        saved = _merge_fields(memory, session, merged, draft)
        # carry the emotional/social signals from deterministic analysis
        det.fields = merged.fields
        _update_dialogue_state(
            memory,
            session,
            det,
            saved,
            message,
            {
                "conversation_target": decision.conversation_target,
                "context_relation": decision.context_relation,
                "should_continue_qualification": decision.should_continue_qualification,
            },
        )
        # If the user agreed to proceed (per the planner), mark qualification active
        # so the backend may validate a lead once all fields are present.
        if decision.extracted_fields.get("user_agrees_to_proceed"):
            memory.set_flag(session, "qualification_active", True)
        memory.remember_facts(session, decision.memory_updates.get("facts_to_remember", []))
        decision.missing_fields = memory.missing_fields(session)
    return decision


# --------------------------------------------------------------------------- #
# LLM call + validation/repair loop
# --------------------------------------------------------------------------- #
def _request_validated_output(llm, prompt: str) -> "PlannerOutput | None":
    """Call the model, parse + validate; on failure retry once with a repair note.

    Returns a validated :class:`PlannerOutput`, or ``None`` if both the initial
    attempt and the single repair attempt fail to produce schema-valid JSON.
    """
    attempts = (prompt, prompt + _REPAIR_NOTE)
    for index, attempt_prompt in enumerate(attempts):
        # Transport/network errors propagate so plan() can fall back safely.
        raw = llm.complete(attempt_prompt)
        data = parse_decision(raw)
        if data is not None:
            try:
                return validate_planner_output(data)
            except ValidationError as exc:
                logger.info(
                    "planner output failed validation on attempt %d (%s)",
                    index + 1, type(exc).__name__,
                )
        else:
            logger.info("planner output not parseable on attempt %d", index + 1)
    return None


def _output_to_dict(output: "PlannerOutput") -> dict:
    """Convert a validated PlannerOutput into the dict shape _decision_from_json expects."""
    data = output.model_dump()
    # extracted_fields is a nested model dump; keep only truthy values so the
    # downstream merge does not overwrite known data with nulls.
    ef = data.get("extracted_fields") or {}
    data["extracted_fields"] = {k: v for k, v in ef.items() if v}
    return data


def _planner_error_decision(context: dict) -> PlannerDecision:
    """A controlled internal planner error decision (no crash, no canned phrase).

    The reply is intentionally left empty; the backend generates a natural,
    context-grounded message for the user.
    """
    decision = PlannerDecision(
        conversation_target="unclear",
        context_relation="unclear",
        should_continue_qualification=False,
        why_this_response="planner output could not be parsed or validated",
        user_intent="unclear",
        assistant_mode="answering",
        recommended_action="answer_only",
        assistant_reply="",
        confidence=0.0,
        safety_notes=["planner_error"],
    )
    decision.sources = [k.get("source") for k in context.get("knowledge_context", []) if k.get("source")]
    return decision


def build_planner_prompt(context: dict) -> str:
    """Assemble the planner prompt from the conversation context."""
    company = _fmt_company(context.get("company_profile", {}))
    knowledge = _fmt_knowledge(context.get("knowledge_context", []))
    history = _fmt_history(context.get("recent_conversation_history", []))
    summary = context.get("session_summary") or "(none)"
    previous = context.get("previous_assistant_message") or "(none)"
    session_memory = json.dumps(context.get("session_memory", {}), ensure_ascii=False)
    lead_draft = json.dumps(context.get("lead_draft", {}), ensure_ascii=False)
    ticket = json.dumps(context.get("ticket_state", {}), ensure_ascii=False)
    action_history = json.dumps(context.get("backend_action_history", []), ensure_ascii=False)
    current_mode = context.get("current_assistant_mode") or "answering"
    actions = ", ".join(context.get("available_actions", AVAILABLE_ACTIONS))
    return (
        f"{_PLANNER_INSTRUCTIONS}\n\n"
        "CONTEXT\n"
        f"Company profile:\n{company}\n\n"
        f"Relevant company knowledge:\n{knowledge}\n\n"
        f"Conversation summary: {summary}\n\n"
        f"Recent conversation:\n{history}\n\n"
        f"Previous assistant message: {previous}\n\n"
        f"Session memory: {session_memory}\n"
        f"Current lead draft: {lead_draft}\n"
        f"Ticket/escalation state: {ticket}\n"
        f"Backend action history: {action_history}\n"
        f"Current assistant mode: {current_mode}\n"
        f"Available actions: {actions}\n\n"
        f"Latest user message: {context.get('user_message', '')}\n\n"
        "JSON:"
    )


def parse_decision(raw: str | None) -> dict | None:
    """Robustly parse a JSON object from raw LLM output.

    Tries a direct load, then the outermost ``{...}`` slice, then a light repair
    (strip code fences / trailing commas). Returns None if nothing parses.
    """
    if not raw:
        return None
    text = raw.strip()
    for candidate in _json_candidates(text):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _json_candidates(text: str):
    yield text
    if text.startswith("```"):
        stripped = text.strip("`")
        if "\n" in stripped:
            stripped = stripped.split("\n", 1)[1]
        yield stripped
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        block = text[start:end + 1]
        yield block
        # light repair: remove trailing commas before } or ]
        import re
        yield re.sub(r",(\s*[}\]])", r"\1", block)


def _decision_from_json(data: dict, context: dict) -> PlannerDecision:
    ef = data.get("extracted_fields") or {}
    # normalise "email" -> "contact_email" used internally
    if ef.get("email") and not ef.get("contact_email"):
        ef["contact_email"] = ef.pop("email")
    mem = data.get("memory_updates") or {}
    action = str(data.get("recommended_action", "answer_only"))
    if action not in AVAILABLE_ACTIONS:
        action = "answer_only"
    decision = PlannerDecision(
        conversation_target=str(data.get("conversation_target", "unclear")),
        context_relation=str(data.get("context_relation", "unclear")),
        should_continue_qualification=bool(data.get("should_continue_qualification", False)),
        why_this_response=str(data.get("why_this_response", ""))[:300],
        user_intent=str(data.get("user_intent", "unclear")),
        assistant_mode=str(data.get("assistant_mode", "answering")),
        extracted_fields={k: v for k, v in ef.items() if v},
        memory_updates={
            "facts_to_remember": list(mem.get("facts_to_remember", []) or []),
            "lead_draft_updates": dict(mem.get("lead_draft_updates", {}) or {}),
        },
        missing_fields=list(data.get("missing_fields", []) or []),
        recommended_action=action,
        action_payload=dict(data.get("action_payload", {}) or {}),
        assistant_reply=str(data.get("assistant_reply", "")).strip(),
        knowledge_used=bool(data.get("knowledge_used")),
        sources=list(data.get("sources", []) or context.get("sources", []) or []),
        confidence=_safe_float(data.get("confidence"), 0.6),
        safety_notes=list(data.get("safety_notes", []) or []),
    )
    if not decision.sources:
        decision.sources = [k.get("source") for k in context.get("knowledge_context", []) if k.get("source")]
    decision.legacy_action = _legacy_action_for(decision)
    return decision


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Deterministic mock backend (offline + safe fallback)
# --------------------------------------------------------------------------- #
def _mock_plan(context: dict, memory, session: str | None) -> PlannerDecision:
    """Deterministic planner used in MOCK_LLM mode and as the LLM fallback.

    It reproduces the natural-dialogue policy without any API call, updating the
    session's dialogue state and returning a full decision.
    """
    message = context["user_message"]
    draft = memory.get_draft(session)
    a = analyze(message, draft)
    context_view = _mock_context_view(context, memory, session, a)

    if not _should_merge_lead_fields(context_view):
        a.fields = {}
        a.budget_unknown = False
    saved = _merge_fields(memory, session, a, draft)
    _update_dialogue_state(memory, session, a, saved, message, context_view)
    return _route_and_reply(context, memory, session, a, saved, context_view)


def _should_merge_lead_fields(context_view: dict) -> bool:
    return (
        context_view.get("conversation_target") == "user_project"
        or bool(context_view.get("should_continue_qualification"))
        or context_view.get("context_relation") == "provides_requested_info"
    )


_APP_TERMS = {
    "app", "application", "assistant", "bot", "chat", "tool", "platform", "site",
    "website", "page", "system", "here",
}
_QUESTION_TERMS = {
    "what", "where", "why", "how", "who", "when", "which", "explain", "mean",
    "means", "work", "works",
}
_PREVIOUS_REPLY_TERMS = {
    "mean", "means", "meant", "asking", "asked", "need", "email", "remember",
    "said", "told", "previous", "that",
}
_PREVIOUS_REPLY_PHRASES = (
    "what do you want to know", "what do you need", "what should i send",
    "what info do you need", "что тебе нужно", "что нужно", "что ты хочешь узнать",
)
_SWITCH_TERMS = {
    "actually", "wait", "instead", "now", "anyway", "scratch", "forget",
    "another", "else", "back",
}
_CASUAL_GREETING_TERMS = {
    "hi", "hello", "hey", "yo", "привет", "здравствуй", "здравствуйте",
}
_CASUAL_CHECKIN_PHRASES = (
    "how are you", "how are u", "how's it going", "how is it going",
    "как дела", "как ты", "как жизнь",
)
_ABUSE_TERMS = {"fuck", "fucking", "shit", "bitch", "asshole", "идиот", "дурак"}
_EMERGENCY_PHRASES = (
    "call 911", "911", "emergency", "urgent help", "ambulance", "police",
    "позвони 112", "112", "скорая", "полиция",
)
_BEGINNER_PHRASES = (
    "i am new", "i'm new", "im new", "new customer", "i am a new customer",
    "i'm a new customer", "я новый", "я новичок", "новый клиент",
)
_CAPABILITY_PHRASES = (
    "what can you do", "what do you do", "how can you help", "what can this do",
    "what can this app do", "what are you able to do", "что ты умеешь",
    "что можешь", "что ты можешь", "чем можешь помочь",
)
_RUSSIAN_REQUEST_PHRASES = (
    "на русском", "по-русски", "по русски", "сможешь на русском",
    "говори на русском", "ответь на русском",
)
_TRANSLATE_TO_RUSSIAN_PHRASES = (
    "переведи на русский", "переведи по-русски", "переведи свои сообщения",
    "translate to russian", "translate your messages",
)
_ENGLISH_REQUEST_PHRASES = (
    "speak english", "english please", "in english", "answer in english",
    "reply in english", "idk russian", "i don't know russian",
    "i dont know russian", "i do not know russian",
)
_TRANSLATE_TO_ENGLISH_PHRASES = (
    "translate to english", "translate into english",
)
_PRACTICAL_HELP_TERMS = {
    "open", "bottle", "can", "coke", "fix", "use", "hand", "help", "помоги",
    "открыть", "бутылку", "банку",
}


def _mock_context_view(context: dict, memory, session: str, a: Analysis) -> dict:
    """Small offline conversation analyzer mirroring the real planner contract."""
    message = context.get("user_message", "")
    text = message.lower()
    tokens = set(_words(text))
    has_prior_topic = bool(memory.has_any_field(session) or context.get("previous_assistant_message"))

    target = "unclear"
    relation = "unclear"
    reason = "latest message did not clearly map to a known target"

    if a.refusal or a.frustration:
        target = "previous_reply" if has_prior_topic else "unclear"
        relation = "rejects_or_pauses"
        reason = "user is rejecting or pausing the current flow"
    elif _is_translate_to_english_request(text):
        target = "previous_reply"
        relation = "asks_meta_question"
        reason = "user asks to translate previous assistant messages into English"
    elif _is_english_language_request(text):
        target = "assistant_product"
        relation = "asks_meta_question"
        reason = "user asks the assistant to continue in English"
    elif _is_translate_to_russian_request(text):
        target = "previous_reply"
        relation = "asks_meta_question"
        reason = "user asks to translate previous assistant messages into Russian"
    elif _is_russian_language_request(text):
        target = "assistant_product"
        relation = "asks_meta_question"
        reason = "user asks the assistant to continue in Russian"
    elif _is_emergency_request(text):
        target = "unrelated"
        relation = "switches_topic" if has_prior_topic else "unclear"
        reason = "user appears to need emergency help outside assistant capabilities"
    elif _is_abusive(tokens):
        target = "unrelated"
        relation = "rejects_or_pauses"
        reason = "user is being abusive; answer with a boundary, not escalation"
    elif _is_casual_checkin(text):
        target = "unclear"
        relation = "switches_topic" if has_prior_topic else "continues_previous_topic"
        reason = "user is making casual conversation"
    elif _is_capability_question(text):
        target = "assistant_product"
        relation = "asks_meta_question" if has_prior_topic else "continues_previous_topic"
        reason = "user asks what this assistant can do"
    elif _is_beginner_message(text):
        target = "unclear"
        relation = "asks_clarification"
        reason = "user is new and needs orientation before qualification"
    elif _is_casual_greeting(tokens, text):
        target = "unclear"
        relation = "switches_topic" if has_prior_topic else "unclear"
        reason = "user is greeting casually"
    elif a.user_says_just_hello or a.social_greeting_only:
        target = "unclear"
        relation = "switches_topic" if has_prior_topic else "unclear"
        reason = "user is casually greeting"
    elif _short_previous_reply_clarification(tokens, context):
        target = "previous_reply"
        relation = "asks_clarification"
        reason = "user asks for clarification of the previous assistant reply"
    elif _asks_about_assistant_product(text, tokens, a):
        target = "assistant_product"
        relation = "switches_topic" if has_prior_topic else "asks_meta_question"
        reason = "user asks about this assistant or app"
    elif _asks_about_previous_reply(text, tokens, a):
        target = "previous_reply"
        relation = "asks_meta_question"
        reason = "user asks why the assistant said or requested something"
    elif a.intent in _KNOWLEDGE_INTENTS:
        target = "configured_company"
        relation = "switches_topic" if _has_switch_cue(tokens) else "continues_previous_topic"
        reason = "user asks about company knowledge"
    elif _wants_to_proceed(text):
        target = "user_project"
        relation = "continues_previous_topic"
        reason = "user agrees to continue with a project request"
    elif a.fields or a.intent in {"project_start", "lead_info_update", "budget_unknown"}:
        target = "user_project"
        relation = "provides_requested_info" if a.fields else "continues_previous_topic"
        reason = "user is discussing their project or providing lead details"
    elif _is_practical_unrelated_request(tokens):
        target = "unrelated"
        relation = "switches_topic" if has_prior_topic else "unclear"
        reason = "user asks for practical help outside the configured company/project context"
    elif a.intent == "needs_help":
        target = "unclear"
        relation = "asks_clarification"
        reason = "user wants help but has not chosen a concrete project/request yet"
    elif a.user_confusion or a.cannot_remember or a.wants_guidance:
        target = "user_project" if memory.has_any_field(session) else "unclear"
        relation = "asks_clarification"
        reason = "user is confused and needs orientation before qualification"
    elif _is_question_like(text, tokens):
        target = "unrelated"
        relation = "switches_topic" if has_prior_topic else "unclear"
        reason = "user asks a question outside the configured company and project context"
    elif a.intent == "greeting":
        target = "unclear"
        relation = "switches_topic" if has_prior_topic else "unclear"
        reason = "user is casually greeting"

    if _has_switch_cue(tokens) and relation == "continues_previous_topic":
        relation = "switches_topic"

    should_continue = (
        target == "user_project"
        and relation not in {"asks_clarification", "asks_meta_question", "rejects_or_pauses", "switches_topic"}
        and (
            any(field in a.fields for field in _CONCRETE_FIELDS)
            or a.intent == "project_start"
            or _wants_to_proceed(text)
            or ("project" in tokens and ("need" in tokens or "help" in tokens))
        )
    )

    return {
        "conversation_target": target,
        "context_relation": relation,
        "should_continue_qualification": should_continue,
        "why_this_response": reason,
        "user_intent": _mock_user_intent_for_context(target, relation, reason, a),
        "language_preference": _mock_language_preference(text, message),
    }


def _words(text: str) -> list[str]:
    expanded = (
        text.replace("what's", "what is")
        .replace("whats", "what is")
        .replace("where's", "where is")
        .replace("how's", "how is")
    )
    table = str.maketrans({c: " " for c in "?!,.;:()[]{}\""})
    return [w.strip("'") for w in expanded.translate(table).split() if w.strip()]


def _has_switch_cue(tokens: set[str]) -> bool:
    return bool(tokens & _SWITCH_TERMS) or {"something", "else"}.issubset(tokens)


def _is_casual_greeting(tokens: set[str], text: str) -> bool:
    return bool(tokens & _CASUAL_GREETING_TERMS) or text.strip() in _CASUAL_GREETING_TERMS


def _is_casual_checkin(text: str) -> bool:
    return any(phrase in text for phrase in _CASUAL_CHECKIN_PHRASES)


def _is_abusive(tokens: set[str]) -> bool:
    return bool(tokens & _ABUSE_TERMS)


def _is_emergency_request(text: str) -> bool:
    return any(phrase in text for phrase in _EMERGENCY_PHRASES)


def _is_beginner_message(text: str) -> bool:
    return any(phrase in text for phrase in _BEGINNER_PHRASES)


def _is_capability_question(text: str) -> bool:
    return any(phrase in text for phrase in _CAPABILITY_PHRASES)


def _is_russian_language_request(text: str) -> bool:
    return any(phrase in text for phrase in _RUSSIAN_REQUEST_PHRASES)


def _is_translate_to_russian_request(text: str) -> bool:
    return any(phrase in text for phrase in _TRANSLATE_TO_RUSSIAN_PHRASES)


def _is_english_language_request(text: str) -> bool:
    return any(phrase in text for phrase in _ENGLISH_REQUEST_PHRASES)


def _is_translate_to_english_request(text: str) -> bool:
    return any(phrase in text for phrase in _TRANSLATE_TO_ENGLISH_PHRASES)


def _mock_language_preference(text: str, original: str) -> str:
    if _is_english_language_request(text) or _is_translate_to_english_request(text):
        return "en"
    if _is_russian_language_request(text) or _is_translate_to_russian_request(text):
        return "ru"
    if _looks_russian_text(original):
        return "ru"
    return "en" if any("a" <= ch.lower() <= "z" for ch in original) else ""


def _is_practical_unrelated_request(tokens: set[str]) -> bool:
    return bool(tokens & _PRACTICAL_HELP_TERMS) and bool({"open", "открыть"} & tokens)


def _looks_russian_text(text: str) -> bool:
    return any("а" <= ch <= "я" or ch == "ё" for ch in text)


def _mock_user_intent_for_context(target: str, relation: str, reason: str, a: Analysis) -> str:
    if "translate" in reason or "Russian" in reason or "English" in reason:
        return "meta_question"
    if "what this assistant can do" in reason:
        return "meta_question"
    if "emergency" in reason:
        return "unrelated"
    if "abusive" in reason:
        return "complaint"
    if "casual conversation" in reason:
        return "casual_chat"
    if "new" in reason:
        return "confusion"
    if "greeting" in reason:
        return "greeting"
    if target == "unrelated":
        return "unrelated"
    if relation == "asks_clarification":
        return "confusion"
    return _legacy_to_user_intent(a.intent, a)


def _short_previous_reply_clarification(tokens: set[str], context: dict) -> bool:
    if not context.get("previous_assistant_message"):
        return False
    return tokens in ({"what"}, {"huh"}, {"why"}, {"why", "that"}, {"what", "mean"})


def _is_question_like(text: str, tokens: set[str]) -> bool:
    return "?" in text or bool(tokens & _QUESTION_TERMS)


def _asks_about_assistant_product(text: str, tokens: set[str], a: Analysis) -> bool:
    if a.intent in _KNOWLEDGE_INTENTS or a.fields:
        return False
    if not _is_question_like(text, tokens):
        return False
    if tokens & _APP_TERMS:
        return True
    return (
        {"what", "this"}.issubset(tokens)
        or {"where", "am"}.issubset(tokens)
        or {"what", "can"}.issubset(tokens)
        or {"how", "work"}.issubset(tokens)
        or {"how", "works"}.issubset(tokens)
    )


def _asks_about_previous_reply(text: str, tokens: set[str], a: Analysis) -> bool:
    if a.intent == "memory_question":
        return True
    if any(phrase in text for phrase in _PREVIOUS_REPLY_PHRASES):
        return True
    if not _is_question_like(text, tokens):
        return False
    if "why" in tokens and bool(tokens & _PREVIOUS_REPLY_TERMS):
        return True
    if "mean" in tokens or "meant" in tokens or "explain" in tokens:
        return True
    return {"what", "about", "that"}.issubset(tokens)


def _merge_fields(memory, session, a: Analysis, draft: dict) -> list:
    if memory.is_lead_created(session):
        return []
    values = dict(a.fields)
    new_service = values.get("service_interest")
    existing_service = draft.get("service_interest")
    if new_service and existing_service and a.additive_service:
        values["service_interest"] = _combine_services(existing_service, new_service)
    if a.budget_unknown:
        values["budget_unknown"] = True
    _, saved = memory.update_draft(session, values)
    return saved


def _update_dialogue_state(
    memory, session, a: Analysis, saved: list, message: str, context_view: dict | None = None
) -> None:
    context_view = context_view or {}
    if context_view.get("language_preference"):
        memory.set_flag(session, "preferred_language", context_view["language_preference"])
    gave_concrete = any(f in _CONCRETE_FIELDS for f in saved)
    if a.social_greeting_only or a.user_says_just_hello:
        if not gave_concrete:
            memory.bump(session, "greeting_count")
    if a.refusal:
        memory.bump(session, "user_refused_count")
    if a.cannot_remember:
        memory.bump(session, "user_confusion_count")
    if a.frustration:
        memory.bump(session, "user_frustration_count")

    wants_request = context_view.get("should_continue_qualification") and (
        a.intent == "project_start"
        or gave_concrete
        or _wants_to_proceed(message)
    )
    if wants_request or memory.get(session, "qualification_active"):
        memory.set_flag(session, "qualification_active", True)

    disengaged = (
        a.refusal or a.cannot_remember or a.wants_guidance
        or context_view.get("context_relation") in {"asks_meta_question", "switches_topic"}
    )
    re_engaged = wants_request and not (a.refusal or a.frustration)
    if re_engaged:
        memory.set_flag(session, "exploration_mode", False)
    elif disengaged and not a.asks_for_human:
        memory.set_flag(session, "exploration_mode", True)

    refused = int(memory.get(session, "user_refused_count", 0) or 0)
    frustrated = int(memory.get(session, "user_frustration_count", 0) or 0)
    if refused + frustrated >= 2:
        memory.set_flag(session, "qualification_paused", True)

    memory.set_flag(session, "last_user_intent", a.intent)


_KNOWLEDGE_INTENTS = {"service_question", "pricing_question", "support_request"}
_GUIDE_INTENTS = {
    "greeting", "needs_help", "project_start", "lead_info_update",
    "memory_correction", "budget_unknown",
}


def _route_and_reply(context, memory, session, a: Analysis, saved: list, context_view: dict) -> PlannerDecision:
    message = context["user_message"]
    intent = a.intent
    gave_concrete = any(f in _CONCRETE_FIELDS for f in saved)
    if context_view.get("should_continue_qualification") and _wants_to_proceed(message):
        memory.set_flag(session, "qualification_active", True)

    d = PlannerDecision(
        confidence=a.confidence,
        conversation_target=context_view.get("conversation_target", "unclear"),
        context_relation=context_view.get("context_relation", "unclear"),
        should_continue_qualification=bool(context_view.get("should_continue_qualification")),
        why_this_response=context_view.get("why_this_response", ""),
    )
    d.extracted_fields = dict(a.fields)
    d.missing_fields = memory.missing_fields(session)
    d.legacy_intent = intent
    d.user_intent = context_view.get("user_intent") or _legacy_to_user_intent(intent, a)
    if (
        d.conversation_target == "user_project"
        and a.fields
        and ("need" in message.lower() or "project" in message.lower() or intent == "project_start")
    ):
        d.should_continue_qualification = True

    if d.user_intent == "casual_chat":
        memory.reset_clarify(session)
        d.assistant_mode = "casual"
        d.recommended_action = "answer_only"
        d.should_continue_qualification = False
        d.assistant_reply = ""
        d.legacy_action = "answered"
        return d

    if d.user_intent == "greeting" and not gave_concrete:
        memory.reset_clarify(session)
        d.assistant_mode = "casual"
        d.recommended_action = "answer_only"
        d.should_continue_qualification = False
        d.assistant_reply = ""
        d.legacy_action = "greeted"
        return d

    # 1. Human / complaint -> recommend a ticket (backend validates).
    if a.asks_for_human and d.user_intent != "complaint":
        d.assistant_mode = "escalating"
        d.recommended_action = "create_ticket"
        d.action_payload = {"reason": "human_escalation", "summary": f"User message: {message}"}
        d.user_intent = "complaint" if a.user_sentiment == "frustrated" else "ask_human"
        return d

    if d.user_intent == "complaint":
        memory.reset_clarify(session)
        d.assistant_mode = "answering"
        d.recommended_action = "answer_only"
        d.should_continue_qualification = False
        d.assistant_reply = ""
        d.legacy_action = "answered"
        return d

    # 2. Recall question.
    if intent == "memory_question":
        memory.reset_clarify(session)
        d.assistant_mode = "answering"
        d.conversation_target = "previous_reply"
        d.context_relation = "asks_meta_question"
        d.should_continue_qualification = False
        d.user_intent = "meta_question"
        d.recommended_action = "answer_only"
        d.memory_used = True
        d.assistant_reply = _memory_reply(memory, session)
        d.legacy_action = "answered_with_memory"
        return d

    # 3. App/meta/previous-reply questions always answer directly before any
    # qualification state can resume.
    if (
        d.conversation_target == "assistant_product"
        or (
            d.conversation_target == "previous_reply"
            and d.context_relation in {"asks_meta_question", "asks_clarification"}
        )
        or d.context_relation == "asks_meta_question"
    ):
        memory.reset_clarify(session)
        d.assistant_mode = "answering"
        d.should_continue_qualification = False
        d.recommended_action = "answer_only"
        d.assistant_reply = _meta_or_app_reply(context, memory, session, a, d)
        d.legacy_action = "answered"
        return d

    # 4. Knowledge questions -> answer from RAG (reply generated by backend).
    if intent in _KNOWLEDGE_INTENTS:
        memory.reset_clarify(session)
        d.assistant_mode = "answering"
        d.conversation_target = "configured_company"
        d.context_relation = (
            "switches_topic" if context.get("current_assistant_mode") in {"exploring", "qualifying"} else "continues_previous_topic"
        )
        d.should_continue_qualification = False
        d.recommended_action = "answer_only"
        d.knowledge_used = True
        d.sources = [k.get("source") for k in context.get("knowledge_context", []) if k.get("source")]
        d.legacy_action = "answered_from_kb"
        return d

    # 5. Unrelated questions switch away from qualification and should be answered
    # directly by the final reply layer.
    if d.conversation_target == "unrelated":
        memory.reset_clarify(session)
        d.assistant_mode = "answering"
        d.user_intent = "unrelated"
        d.recommended_action = "answer_only"
        d.should_continue_qualification = False
        d.assistant_reply = ""
        d.legacy_action = "answered"
        return d

    # 6. Beginner/confused messages get orientation, not lead-field pressure.
    if d.user_intent == "confusion" and not saved:
        d.assistant_mode = "exploring"
        d.recommended_action = "answer_only"
        d.should_continue_qualification = False
        d.assistant_reply = _orientation_reply(context, memory, session)
        d.legacy_action = "exploring"
        return d

    # 7. Vague help/beginner messages are not consent to qualify.
    if intent == "needs_help" and not saved and not d.should_continue_qualification:
        d.assistant_mode = "answering"
        d.user_intent = "confusion"
        d.recommended_action = "answer_only"
        d.assistant_reply = _orientation_reply(context, memory, session)
        d.legacy_action = "answered"
        return d

    # 8. Lead already created.
    if memory.is_lead_created(session):
        d.assistant_mode = "answering"
        d.recommended_action = "answer_only"
        d.assistant_reply = _lead_exists_reply(memory, session)
        d.legacy_action = "lead_already_exists"
        return d

    memory.reset_clarify(session)

    # 9. Paused.
    if memory.get(session, "qualification_paused"):
        d.assistant_mode = "paused"
        d.recommended_action = "pause_qualification"
        d.should_continue_qualification = False
        d.assistant_reply = _paused_reply(memory, session)
        d.legacy_action = "qualification_paused"
        return d

    # 10. Pure social greeting.
    social = (
        intent == "greeting" and not gave_concrete
        and not memory.has_any_field(session)
        and not memory.get(session, "qualification_active")
    )
    if social:
        d.assistant_mode = "casual"
        d.user_intent = "greeting"
        d.recommended_action = "answer_only"
        d.should_continue_qualification = False
        d.assistant_reply = _social_reply(memory, session, a)
        d.legacy_action = "greeted"
        return d

    # 11. Exploration.
    if memory.get(session, "exploration_mode") and not d.should_continue_qualification:
        d.assistant_mode = "exploring"
        d.recommended_action = "ask_clarifying_question"
        d.should_continue_qualification = False
        d.assistant_reply = _explore_reply(memory, session)
        d.legacy_action = "exploring"
        return d

    # 12. Bare service mention -> explore vs request.
    if (
        memory.get(session, "service_interest")
        and not memory.get(session, "qualification_active")
        and intent != "project_start"
        and not d.should_continue_qualification
    ):
        d.assistant_mode = "exploring"
        d.user_intent = "provide_lead_info"
        d.recommended_action = "ask_clarifying_question"
        d.should_continue_qualification = False
        d.assistant_reply = _direction_reply(memory, session, a)
        d.legacy_action = "clarifying_direction"
        return d

    # 13. Active qualification -> collect or (if ready) create a lead.
    in_flow = (
        d.should_continue_qualification
        and (intent in _GUIDE_INTENTS
        or memory.has_any_field(session)
        or bool(memory.get_last_asked(session))
        or bool(saved))
    )
    if in_flow:
        ready = not memory.missing_fields(session) and memory.get(session, "qualification_active")
        if ready:
            d.assistant_mode = "qualifying"
            d.recommended_action = "create_lead"
            d.action_payload = {"draft": memory.known_fields(session)}
            d.user_intent = "provide_lead_info"
            return d
        d.assistant_mode = "qualifying"
        d.user_intent = "provide_lead_info" if saved else d.user_intent
        d.recommended_action = "update_lead_draft" if saved else "ask_clarifying_question"
        reply, qtype = _collect_reply(context, memory, session, a, saved)
        d.assistant_reply = reply
        d.action_payload = {"asked": qtype}
        d.legacy_action = "collecting_info"
        return d

    # 14. Truly unclear with no active conversation.
    #
    # Ordinary confusion, jokes or venting must NEVER open a ticket or repeat the
    # same menu. After the first clarification we switch to gentle exploration
    # (offer guidance), so the user is never pushed or stonewalled.
    count = memory.bump_clarify(session)
    if count >= 2:
        memory.set_flag(session, "exploration_mode", True)
        d.assistant_mode = "exploring"
        d.user_intent = "unclear"
        d.recommended_action = "ask_clarifying_question"
        d.assistant_reply = _explore_reply(memory, session)
        d.legacy_action = "exploring"
        return d
    d.assistant_mode = "answering"
    d.user_intent = "unclear"
    d.recommended_action = "ask_clarifying_question"
    d.assistant_reply = _clarify_reply()
    d.legacy_action = "asked_clarification"
    return d


# --------------------------------------------------------------------------- #
# Reply builders (shared, deterministic templates with variation)
# --------------------------------------------------------------------------- #
def _social_reply(memory, session, a: Analysis) -> str:
    idx = max(0, int(memory.get(session, "greeting_count", 1) or 1) - 1)
    memory.note_question(session, "social")
    memory.set_last_asked(session, [])
    return responses.just_hello(idx) if a.user_says_just_hello else responses.greeting(idx)


def _meta_or_app_reply(context, memory, session, a: Analysis, d: PlannerDecision) -> str:
    memory.note_question(session, "meta")
    memory.set_last_asked(session, [])
    text = context.get("user_message", "").lower()
    profile = context.get("company_profile", {}) or {}
    product = profile.get("product_name") or profile.get("brand_label") or "this assistant"
    company = profile.get("company_name") or profile.get("brand_label") or "the configured company"
    assistant = profile.get("assistant_name") or "the assistant"

    if d.conversation_target == "assistant_product":
        if profile.get("company_name"):
            return (
                f"You're in {product}, chatting with {assistant} for {company}. "
                "It can answer company questions and help prepare a project request only if you choose to share details."
            )
        return (
            f"You're in {product}, a configurable customer-assistant chat. "
            "It can answer the configured company's questions and, with your consent, gather details for follow-up."
        )
    if "email" in text:
        return (
            "Email is only needed if you decide to create a follow-up request. "
            "For general questions, you can keep asking without sharing contact details."
        )
    if a.intent == "memory_question":
        return _memory_reply(memory, session)
    previous = context.get("previous_assistant_message") or ""
    if previous:
        return (
            "I meant that we can stay conversational unless you choose to start a request. "
            "Your latest question comes first; I won't keep collecting details unless that is useful."
        )
    return (
        "Good question. I can explain the current step first, and we can skip collecting project details until you want that."
    )


def _explore_reply(memory, session) -> str:
    memory.set_flag(session, "exploration_mode", True)
    memory.note_question(session, "explore")
    memory.set_last_asked(session, [])
    return _explore_text(memory, session)


def _direction_reply(memory, session, a: Analysis) -> str:
    draft = memory.get_draft(session)
    idx = memory.times_asked(session, "direction")
    ack = _acknowledge(memory, session, a)
    question = responses.service_direction(draft.get("service_interest", ""), idx)
    memory.note_question(session, "direction")
    memory.set_last_asked(session, ["company"])
    return (ack + " " + question).strip() if ack else question


def _paused_reply(memory, session) -> str:
    draft = memory.get_draft(session)
    idx = int(memory.get(session, "user_frustration_count", 0) or 0) + int(
        memory.get(session, "user_refused_count", 0) or 0
    )
    memory.set_last_asked(session, [])
    return responses.paused(draft.get("service_interest", ""), draft.get("product_type", ""), idx)


def _orientation_reply(context, memory, session) -> str:
    idx = memory.times_asked(session, "orientation")
    profile = context.get("company_profile", {}) or {}
    company = profile.get("company_name") or profile.get("brand_label") or "the configured company"
    options = [
        (
            f"No rush. This chat can orient you around {company}, answer a specific question, "
            "or talk through a project idea without creating anything."
        ),
        (
            "We can slow down and start with the basics. Ask what this chat is for, ask about the company, "
            "or describe a goal in plain words."
        ),
        (
            "That's fine. We can keep this as a quick explanation first, and only move into a project request "
            "if you decide that is what you want."
        ),
    ]
    memory.note_question(session, "orientation")
    memory.set_last_asked(session, [])
    return options[idx % len(options)]


def _collect_reply(context, memory, session, a: Analysis, saved: list):
    draft = memory.get_draft(session)
    missing = memory.missing_fields(session)
    qtype = _question_type(missing)
    progressed = bool(saved)

    if qtype != "open" and not progressed and memory.times_asked(session, qtype) >= 2:
        memory.set_flag(session, "exploration_mode", True)
        memory.note_question(session, "explore")
        memory.set_last_asked(session, [])
        return _explore_text(memory, session), "explore"

    idx = memory.times_asked(session, qtype)
    ack = _acknowledge(memory, session, a)
    if qtype == "service":
        question, asked = _service_question(a, idx)
    elif qtype == "company_budget":
        need_company = "company" in missing
        need_budget = "budget_range" in missing
        question = responses.ask_company_budget(need_company, need_budget, idx)
        asked = [f for f, n in (("company", need_company), ("budget_range", need_budget)) if n]
    elif qtype == "contact":
        need_name = "name" in missing
        need_email = "contact_email" in missing
        question = responses.ask_contact(need_name, need_email, idx)
        asked = [f for f, n in (("name", need_name), ("contact_email", need_email)) if n]
    else:
        question, asked = "Could you share a little more about what you need?", []

    memory.note_question(session, qtype)
    memory.set_last_asked(session, asked)
    reply = (ack + " " + question).strip() if ack else question
    return reply, qtype


def _memory_reply(memory, session) -> str:
    draft = memory.get_draft(session)
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
        return "So far you've mentioned " + ", ".join(parts) + "."
    return (
        "I don't have any details yet. What company are you with, and what are you "
        "looking for help with?"
    )


def _lead_exists_reply(memory, session) -> str:
    draft = memory.get_draft(session)
    return (
        f"You're already set — I created lead #{draft.get('lead_id')} for "
        f"{draft.get('company')}. To start a different request, just say \"new project\"."
    )


def _clarify_reply() -> str:
    return (
        "I can follow the thread you choose. Are you asking about this chat, the company, "
        "or your own project?"
    )


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _acknowledge(memory, session, a: Analysis) -> str:
    draft = memory.get_draft(session)
    saved = a.fields  # what was extracted this turn
    if a.correction_detected:
        for f in ("company", "name", "service_interest", "product_type"):
            if f in a.fields and draft.get(f):
                return f"You're right, I already have {draft[f]}."
    if "service_interest" in saved and draft.get("service_interest"):
        svc = draft["service_interest"].lower()
        if draft.get("product_type"):
            return f"Got it — {svc} for your {draft['product_type']}."
        return f"Got it — {svc}."
    if "company" in saved and draft.get("company"):
        return f"Thanks — noted {draft['company']}."
    if "name" in saved and draft.get("name"):
        return f"Thanks, {draft['name']}."
    if "product_type" in saved and draft.get("product_type"):
        return f"Got it — a {draft['product_type']}."
    if "budget_range" in saved or "contact_email" in saved:
        return "Great, noted."
    return ""


def _question_type(missing: list) -> str:
    if "service_interest" in missing:
        return "service"
    if "company" in missing or "budget_range" in missing:
        return "company_budget"
    if "name" in missing or "contact_email" in missing:
        return "contact"
    return "open"


def _service_question(a: Analysis, idx: int):
    if a.user_confusion:
        return (
            "What would you like to improve — getting more leads, increasing sales, "
            "reducing ad costs, improving website conversion, or understanding your "
            "analytics?"
        ), ["service_interest"]
    if a.intent == "project_start":
        return (
            "Let's set up your project. What product or company would you like to "
            "promote, and what kind of help do you need (paid ads, SEO, analytics, "
            "or a landing page audit)?"
        ), ["service_interest", "company"]
    options = [
        "Which area should we look at first: acquisition, search visibility, tracking, "
        "or the landing page?",
        "Which area should we focus on first: paid ads, SEO, analytics, or a "
        "landing-page audit?",
    ]
    return options[idx % len(options)], ["service_interest"]


def _explore_text(memory, session) -> str:
    draft = memory.get_draft(session)
    idx = int(memory.get(session, "user_confusion_count", 0) or 0) + int(
        memory.get(session, "user_refused_count", 0) or 0
    )
    return responses.explore(draft.get("service_interest", ""), draft.get("product_type", ""), idx)


def _combine_services(existing: str, new: str) -> str:
    parts = [p.strip() for p in (existing or "").split("+") if p.strip()]
    for token in (new or "").split("+"):
        token = token.strip()
        if token and token.lower() not in {p.lower() for p in parts}:
            parts.append(token)
    return " + ".join(parts)


def _wants_to_proceed(message: str) -> bool:
    text = message.lower().strip()
    return any(p == text or text.startswith(p + " ") or p in text for p in _PROCEED)


# --- intent vocabulary mapping --------------------------------------------- #
def _legacy_to_user_intent(intent: str, a: Analysis) -> str:
    if a.user_confusion or a.cannot_remember:
        return "confusion"
    mapping = {
        "greeting": "greeting",
        "service_question": "ask_services",
        "pricing_question": "ask_pricing",
        "support_request": "ask_process",
        "project_start": "start_project",
        "lead_info_update": "provide_lead_info",
        "budget_unknown": "provide_lead_info",
        "memory_correction": "provide_lead_info",
        "human_escalation": "ask_human",
        "memory_question": "meta_question",
        "needs_help": "confusion" if a.wants_guidance else "start_project",
        "unknown": "unclear",
    }
    return mapping.get(intent, "unclear")


def _legacy_intent(user_intent: str, det: Analysis) -> str:
    """Best-effort legacy intent label from an LLM user_intent (for metrics/UI)."""
    mapping = {
        "ask_services": "service_question",
        "ask_pricing": "pricing_question",
        "ask_process": "support_request",
        "start_project": "project_start",
        "provide_lead_info": "lead_info_update",
        "ask_human": "human_escalation",
        "complaint": "human_escalation",
        "meta_question": "memory_question",
        "clarification": "memory_question",
        "confusion": "needs_help",
        "unrelated": "unknown",
        "greeting": "greeting",
        "casual_chat": "greeting",
        "unclear": "unknown",
    }
    return mapping.get(user_intent, det.intent or "unknown")


def _legacy_action_for(decision: PlannerDecision) -> str:
    return {
        "create_ticket": "escalated_to_human",
        "create_lead": "created_lead",
        "pause_qualification": "qualification_paused",
    }.get(decision.recommended_action, decision.legacy_action or "")


# --- prompt formatting helpers --------------------------------------------- #
def _fmt_company(profile: dict) -> str:
    if not profile:
        return "(not configured)"
    keys = ("company_name", "company_description", "business_industry", "assistant_name", "escalation_target")
    lines = [f"- {k}: {profile[k]}" for k in keys if profile.get(k)]
    return "\n".join(lines) or "(not configured)"


def _fmt_knowledge(chunks: list) -> str:
    if not chunks:
        return "(no relevant knowledge retrieved)"
    out = []
    for c in chunks[:4]:
        src = c.get("source", "?")
        text = (c.get("text", "") or "").strip().replace("\n", " ")
        out.append(f"[{src}] {text[:400]}")
    return "\n".join(out)


def _fmt_history(history: list) -> str:
    if not history:
        return "(no previous messages)"
    return "\n".join(f"{t.get('role')}: {t.get('content')}" for t in history[-12:])
