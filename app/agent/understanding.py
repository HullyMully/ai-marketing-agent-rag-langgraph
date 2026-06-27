"""Conversation understanding layer.

For every user message this produces a structured `Analysis`: an intent,
extracted lead fields, and signals like confusion / correction / asks-for-human.

Two strategies:
* A robust deterministic analyzer (used in MOCK_LLM mode and as a safe backstop).
* An LLM analyzer that returns JSON (used when MOCK_LLM=false). Its output is
  merged with the deterministic extraction, which stays authoritative for
  structured, business-critical fields (email validity, budget, etc.).

Business decisions (create a lead? open a ticket?) are made by deterministic
rules in the graph — never by the LLM alone.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

ALLOWED_INTENTS = {
    "greeting", "needs_help", "service_question", "pricing_question",
    "project_start", "lead_info_update", "budget_unknown", "memory_correction",
    "human_escalation", "support_request", "memory_question", "unknown",
}

# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+\d[\d\s().-]{6,}\d")
_NAME_RE = re.compile(
    r"\b(?i:my name is|i am|i'm|this is)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)"
)
_COMPANY_RE = re.compile(
    r"\b(?i:company(?:'s)? name is|company name is|my company is|company is|"
    r"company:|work at|i work for|i'm from|i am from|i'm with|i am with|here at|"
    r"we are|we're|from)\s+([A-Z][A-Za-z0-9&._-]+(?:\s+[A-Z][A-Za-z0-9&._-]+){0,3})"
)
_BUDGET_RE = re.compile(
    r"\$\s?[\d,]+\s?[km]?(?:\s?/?\s?(?:per month|a month|months|month|mo))?",
    re.IGNORECASE,
)
_BARE_TOKEN_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9&._-]{1,30})\b")

_CONFUSION = [
    "i don't know", "i dont know", "i do not know", "i don't remember",
    "i dont remember", "don't remember", "not sure", "no idea", "idk",
    "can't remember", "cannot remember", "don't recall", "no clue", "unsure",
    "help me with that", "help me decide",
]
_CORRECTION = [
    "i told you", "i told u", "i already said", "i already told", "i said",
    "as i said", "i mentioned", "already gave", "you have", "u have",
    "i just said", "like i said",
]
_HUMAN = [
    "human", "real person", "a person", "speak to someone", "talk to someone",
    "speak to a human", "talk to a human", "manager", "operator",
    "representative", "live agent", "real human", "speak to a specialist",
]
_ANGRY = [
    "angry", "furious", "terrible", "awful", "unacceptable", "worst",
    "frustrated", "ridiculous", "complaint", "complain", "refund",
]
_ENTERPRISE = ["custom enterprise", "enterprise workflow", "enterprise plan", "custom workflow"]
_MEMORY_Q = [
    "what did i tell you", "what did i say", "what company did i", "what do you have",
    "what have i told you", "what did i mention", "remind me what i", "do you remember what",
    "what's my company", "what company and budget",
]
_PRICING = ["price", "prices", "pricing", "cost", "how much", "package", "packages", "rates", "fee"]
_SERVICE_Q = [
    "what services", "what do you offer", "what do you do", "what can you do",
    "which services", "do you offer", "what services do you provide",
]
_PROJECT = ["start a project", "starting a project", "new project", "a project", "launch", "promote"]
_HELP = ["help", "need help", "i need", "get started", "looking to", "want to", "i'd like"]
_BUDGET_UNKNOWN_OK = [
    "no budget", "budget is unknown", "mark it unknown", "mark budget unknown",
    "without a budget", "without budget", "skip budget", "don't have a budget",
    "budget tbd", "no set budget", "proceed without",
]

# --- social / emotional signals -------------------------------------------- #
_GREETING_WORDS = [
    "hello", "hi", "hey", "hiya", "howdy", "good morning", "good afternoon",
    "good evening", "greetings", "yo",
]
# Words that don't add a real request on top of a greeting.
_GREETING_FILLER = {
    "there", "again", "you", "u", "to", "i", "im", "i'm", "just", "wanna",
    "want", "wanted", "say", "saying", "said", "do", "and", "the", "a", "an",
    "me", "my", "we", "back", "all", "everyone", "team", "guys", "好", "ok",
}
_JUST_HELLO = [
    "just saying hello", "just saying hi", "saying hello", "saying hi",
    "wanna say hi", "want to say hi", "wanna say hello", "want to say hello",
    "wanna to hello", "want to hello", "to hello to you", "hello to you",
    "hi to you", "just wanted to say hi", "just wanted to say hello",
    "just a hello",
]
_JOKING = [
    "joking", "kidding", "just kidding", "jk", "haha", "hahaha", "hahah",
    "lol", "lmao", "actually", "sorry", "no i mean", "no, i mean", "i mean",
    "my bad", "scratch that", "nvm", "never mind", "nevermind",
]
_REFUSAL_TOKENS = {"no", "nope", "nah", "na", "no.", "no)", "no(", "no!"}
_REFUSAL_PHRASES = [
    "not now", "don't want", "dont want", "do not want", "no thanks",
    "no thank you", "maybe later", "later", "not really", "not right now",
    "rather not", "i'd rather not", "skip it",
]
_CANNOT_REMEMBER = [
    "forgot", "i forget", "don't remember", "dont remember", "do not remember",
    "can't remember", "cant remember", "cannot remember", "don't recall",
    "dont recall", "no memory", "idk", "i don't know", "i dont know",
]
_FRUSTRATION_PHRASES = [
    "i told you", "i told u", "i already told", "i already said", "stop asking",
    "stop it", "why are you asking", "why do you keep asking", "enough",
    "you keep asking", "i said no", "leave me alone", "for the last time",
]
_WANTS_GUIDANCE = [
    "help me with that", "help me decide", "what should i do", "what do you recommend",
    "can you suggest", "could you suggest", "any suggestions", "what do you suggest",
    "not sure what", "i don't know what", "i dont know what", "what would you do",
    "guide me", "where do i start", "where should i start", "what are my options",
]
_ADDITIVE = ["and ", "also", "plus", " + ", "+", "as well", " too", "along with"]

# service keyword -> readable label
_SERVICES = {
    "Paid ads": ["paid ads", "paid advertising", "paid acquisition", "ppc", "google ads", "meta ads", "ads"],
    "SEO": ["seo", "search engine", "organic ranking"],
    "Analytics setup": ["analytics", "ga4", "tracking setup", "conversion tracking"],
    "Landing page audit": ["landing page", "page audit"],
    "Content marketing": ["content marketing", "blog", "articles"],
    "Email marketing": ["email marketing", "newsletter", "lifecycle"],
    "Social media": ["social media", "instagram", "tiktok"],
}
_PRODUCTS = {
    "SaaS": ["saas", "software as a service"],
    "E-commerce": ["ecommerce", "e-commerce", "online store", "shopify", "store", "shop"],
    "Mobile app": ["mobile app", "ios app", "android app"],
    "B2B": ["b2b"],
    "Website": ["website", "web site"],
}

_NOT_NAMES = {
    "hi", "hello", "hey", "company", "budget", "the", "contact", "email", "we",
    "our", "yes", "no", "ok", "okay", "thanks", "sure", "paid", "seo", "help",
    "sorry", "oh", "please", "what", "why", "how", "when", "where", "who",
}


@dataclass
class Analysis:
    intent: str = "unknown"
    fields: dict = field(default_factory=dict)
    budget_unknown: bool = False
    user_sentiment: str = "neutral"
    user_confusion: bool = False
    correction_detected: bool = False
    asks_for_human: bool = False
    confidence: float = 0.5
    short_reason: str = ""
    # --- social / emotional signals ---
    social_greeting_only: bool = False
    user_says_just_hello: bool = False
    joking: bool = False
    refusal: bool = False
    cannot_remember: bool = False
    frustration: bool = False
    wants_guidance: bool = False
    additive_service: bool = False


def _has(text: str, phrases) -> bool:
    return any(p in text for p in phrases)


_WORD_RE = re.compile(r"[a-z']+")


def _is_all_caps(message: str) -> bool:
    """True if the message is shouted (mostly uppercase letters)."""
    letters = [c for c in message if c.isalpha()]
    return len(letters) >= 2 and message.upper() == message


def _greeting_only(message: str) -> bool:
    """Greeting word(s) with no substantive request attached."""
    text = message.lower()
    if not _has(text, _GREETING_WORDS) and text.strip() not in {"hi", "hello", "hey"}:
        return False
    # strip greeting phrases, then check what meaningful words remain.
    stripped = text
    for g in _GREETING_WORDS:
        stripped = stripped.replace(g, " ")
    words = [w for w in _WORD_RE.findall(stripped) if w not in _GREETING_FILLER]
    return len(words) == 0


def _detect_refusal(message: str) -> bool:
    text = message.lower().strip()
    tokens = set(_WORD_RE.findall(text))
    if text in _REFUSAL_TOKENS or text.rstrip(".,!?;:)(" ) in {"no", "nope", "nah"}:
        return True
    if "no" in tokens and len(tokens) <= 2:
        return True
    return _has(text, _REFUSAL_PHRASES)


def _match_label(text: str, mapping: dict) -> str:
    for label, keywords in mapping.items():
        if any(k in text for k in keywords):
            return label
    return ""


def extract_fields(message: str, last_asked: list[str] | None = None) -> dict:
    """Deterministic extraction of lead fields from one message."""
    last_asked = last_asked or []
    found: dict = {}
    text = message.lower()

    email = _EMAIL_RE.search(message)
    if email:
        found["contact_email"] = email.group(0).rstrip(".,;)")

    phone = _PHONE_RE.search(message)
    if phone:
        found["phone"] = phone.group(0).strip()

    name = _NAME_RE.search(message)
    if name:
        found["name"] = name.group(1).strip()

    company = _COMPANY_RE.search(message)
    if company:
        found["company"] = company.group(1).strip().rstrip(".,;")

    service = _match_label(text, _SERVICES)
    if service:
        found["service_interest"] = service

    product = _match_label(text, _PRODUCTS)
    if product:
        found["product_type"] = product

    budget = _BUDGET_RE.search(message)
    if budget:
        found["budget_range"] = budget.group(0).strip()

    # Bare answer to a field we just asked for (e.g. "FalkoTeam, I told u").
    if last_asked:
        bare = _BARE_TOKEN_RE.match(message.strip())
        token = bare.group(1) if bare else ""
        if token and token.lower() not in _NOT_NAMES:
            if "company" in last_asked and "company" not in found and not service and not product:
                found["company"] = token
            elif "name" in last_asked and "name" not in found:
                # Accept a leading name even when an email is also present, but
                # only in a clear "Name" or "Name, email@x" shape — never grab a
                # stray first word like "My" from "My email is ...".
                rest = message.strip()[len(token):].lstrip(" ,;:-")
                if rest == "" or _EMAIL_RE.match(rest):
                    found["name"] = token

    return found


def _restated_known(message: str, draft: dict, found: dict) -> dict:
    """If the user repeats a value we already have (a correction/restatement),
    mark that field as (re)provided so the assistant can acknowledge it."""
    text = message.lower()
    for f in ("company", "name", "service_interest", "product_type"):
        val = draft.get(f)
        if val and f not in found and val.lower() in text:
            found[f] = val
    return found


def analyze_rule_based(message: str, draft: dict | None = None) -> Analysis:
    """Deterministic analysis used in mock mode and as a backstop."""
    draft = draft or {}
    text = message.lower()
    last_asked = list(draft.get("last_asked", []))
    fields = extract_fields(message, last_asked)
    fields = _restated_known(message, draft, fields)

    confusion = _has(text, _CONFUSION)
    correction = _has(text, _CORRECTION)
    asks_human = _has(text, _HUMAN) or _has(text, _ANGRY) or _has(text, _ENTERPRISE)
    budget_unknown = _has(text, _BUDGET_UNKNOWN_OK)

    # --- social / emotional signals ---
    greeting_only = _greeting_only(message)
    just_hello = greeting_only or _has(text, _JUST_HELLO)
    joking = _has(text, _JOKING)
    refusal = _detect_refusal(message)
    cannot_remember = _has(text, _CANNOT_REMEMBER)
    frustration = _has(text, _FRUSTRATION_PHRASES) or (
        _is_all_caps(message) and (refusal or cannot_remember)
    )
    wants_guidance = _has(text, _WANTS_GUIDANCE)
    additive_service = bool(fields.get("service_interest")) and _has(text, _ADDITIVE)
    confusion = confusion or cannot_remember
    correction = correction or joking
    sentiment = "frustrated" if (_has(text, _ANGRY) or frustration) else "neutral"

    # Decide intent (priority order).
    if asks_human:
        intent = "human_escalation"
    elif _has(text, _MEMORY_Q):
        intent = "memory_question"
    elif _has(text, _PRICING) and not fields.get("budget_range"):
        intent = "pricing_question"
    elif _has(text, _SERVICE_Q):
        intent = "service_question"
    elif correction and fields:
        intent = "memory_correction"
    elif fields:
        intent = "project_start" if _has(text, _PROJECT) else "lead_info_update"
    elif budget_unknown:
        intent = "budget_unknown"
    elif _has(text, _PROJECT):
        intent = "project_start"
    elif _has(text, ["hello", "hi ", "hey", "good morning", "good afternoon"]) or text.strip() in {"hi", "hello", "hey"}:
        intent = "greeting"
    elif _has(text, _HELP) or confusion:
        intent = "needs_help"
    else:
        intent = "unknown"

    conf = 0.85 if fields or intent not in {"unknown"} else 0.3
    return Analysis(
        intent=intent,
        fields=fields,
        budget_unknown=budget_unknown,
        user_sentiment=sentiment,
        user_confusion=confusion,
        correction_detected=correction,
        asks_for_human=asks_human,
        confidence=conf,
        short_reason="rule-based",
        social_greeting_only=greeting_only,
        user_says_just_hello=just_hello,
        joking=joking,
        refusal=refusal,
        cannot_remember=cannot_remember,
        frustration=frustration,
        wants_guidance=wants_guidance,
        additive_service=additive_service,
    )


_LLM_PROMPT = (
    "You analyze one user message to a company's AI assistant and return JSON only.\n"
    "Return an object with keys: intent, fields, user_sentiment, user_confusion, "
    "correction_detected, asks_for_human, confidence, short_reason.\n"
    "intent is one of: greeting, needs_help, service_question, pricing_question, "
    "project_start, lead_info_update, budget_unknown, memory_correction, "
    "human_escalation, support_request, memory_question, unknown.\n"
    "fields is an object that may contain: name, company, email, phone, "
    "service_interest, budget_range, product_type, notes. Only include fields the "
    "user actually provided.\n"
    "Known draft so far: {draft}\n"
    "User message: {message}\n"
    "JSON:"
)


def analyze_with_llm(message: str, draft: dict | None = None) -> Analysis:
    """LLM-based analysis merged with deterministic extraction (authoritative)."""
    from app.agent.llm import get_llm

    draft = draft or {}
    base = analyze_rule_based(message, draft)
    try:
        raw = get_llm().complete(
            _LLM_PROMPT.format(
                draft=json.dumps(draft.get("__public__", {k: draft.get(k) for k in (
                    "name", "company", "contact_email", "service_interest",
                    "budget_range", "product_type")})),
                message=message,
            )
        )
        data = _parse_json(raw)
    except Exception:
        return base
    if not isinstance(data, dict):
        return base

    intent = str(data.get("intent", base.intent)).strip()
    if intent not in ALLOWED_INTENTS:
        intent = base.intent

    fields = dict(base.fields)  # deterministic wins for what it found
    llm_fields = data.get("fields") or {}
    if isinstance(llm_fields, dict):
        for k, v in llm_fields.items():
            key = "contact_email" if k == "email" else k
            if v and key not in fields and key in (
                "name", "company", "contact_email", "phone", "service_interest",
                "budget_range", "product_type", "notes",
            ):
                fields[key] = str(v).strip()

    return Analysis(
        intent=intent,
        fields=fields,
        budget_unknown=base.budget_unknown or bool(data.get("budget_unknown")),
        user_sentiment=str(data.get("user_sentiment", base.user_sentiment)),
        user_confusion=base.user_confusion or bool(data.get("user_confusion")),
        correction_detected=base.correction_detected or bool(data.get("correction_detected")),
        asks_for_human=base.asks_for_human or bool(data.get("asks_for_human")),
        confidence=float(data.get("confidence", base.confidence) or base.confidence),
        short_reason=str(data.get("short_reason", "llm"))[:120],
        # Social/emotional signals stay deterministic (cheap and reliable).
        social_greeting_only=base.social_greeting_only,
        user_says_just_hello=base.user_says_just_hello,
        joking=base.joking,
        refusal=base.refusal,
        cannot_remember=base.cannot_remember,
        frustration=base.frustration,
        wants_guidance=base.wants_guidance,
        additive_service=base.additive_service,
    )


def _parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


def analyze(message: str, draft: dict | None = None) -> Analysis:
    """Public entry point — LLM when configured, deterministic otherwise."""
    from app.config import settings

    if settings.mock_llm:
        return analyze_rule_based(message, draft)
    try:
        return analyze_with_llm(message, draft)
    except Exception:
        return analyze_rule_based(message, draft)
