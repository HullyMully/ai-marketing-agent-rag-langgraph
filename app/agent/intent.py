"""Intent classification.

Two strategies:
* Rule-based keyword classifier (deterministic, used in demo/mock mode and tests).
* LLM-based classifier via the configured provider (used when MOCK_LLM=false).

Both return a tuple of (intent, confidence). The rule-based classifier is also
used as a safe backstop if the LLM returns something unusable.
"""
from __future__ import annotations

import re

INTENTS = [
    "greeting",
    "service_question",
    "pricing_question",
    "lead_qualification",
    "create_lead",
    "support_request",
    "human_escalation",
    "memory_question",
    "unknown",
]

# Explicit human request, anger/complaint, or custom-enterprise needs.
_ESCALATION_PHRASES = [
    "human", "real person", "a person", "speak to someone", "talk to someone",
    "speak to a human", "talk to a human", "manager", "operator", "representative",
    "live agent", "customer service rep", "speak to a specialist",
    "talk to a specialist", "real human",
    # complaints / anger
    "complaint", "complain", "refund", "angry", "furious", "terrible", "awful",
    "unacceptable", "worst", "frustrated", "disappointed", "this is ridiculous",
    "lawyer", "legal", "billing dispute", "escalate",
    # custom enterprise
    "custom enterprise", "enterprise workflow", "enterprise plan", "custom workflow",
]

# Asking the assistant to recall earlier context.
_MEMORY_PHRASES = [
    "do you remember", "remember what", "what company did i", "what did i say",
    "what's my company", "what is my company", "what company i mentioned",
    "remind me what i", "what did i tell you", "do you recall",
    "have i mentioned", "mentioned so far", "what company and budget",
    "what do you have so far", "what have i told you",
]

_GREETINGS = [
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "greetings", "hiya", "howdy",
]

# Scored keyword groups. Higher score wins; ties broken by `_PRIORITY`.
_KEYWORDS: dict[str, list[str]] = {
    "pricing_question": [
        "price", "prices", "pricing", "cost", "costs", "how much", "package",
        "packages", "fee", "fees", "quote", "rates", "budget range", "how expensive",
    ],
    "lead_qualification": [
        "new customer", "new client", "interested", "need help", "want help",
        "want to start", "get started", "getting started", "launch ads",
        "launching ads", "paid ads", "run ads", "running ads", "marketing help",
        "help with marketing", "need marketing", "work with you", "become a client",
        "sign up", "launch a campaign", "start a project", "grow my", "scale my",
        "i want to", "i'd like to", "we need help", "looking to", "help launching",
        "help us launch",
    ],
    "service_question": [
        "service", "services", "what do you offer", "what can you do",
        "what do you do", "do you do", "do you offer", "ppc", "seo",
        "content marketing", "social media", "email marketing", "what services",
    ],
    "support_request": [
        "not working", "broken", "bug", "error", "can't log", "cannot log",
        "account problem", "trouble with", "isn't working", "stopped working",
    ],
}

_PRIORITY = ["pricing_question", "lead_qualification", "service_question", "support_request"]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NAME_RE = re.compile(r"(?i)\b(?:my name is|i am|i'm|this is)\s+[A-Za-z]")
_GREETING_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(g) for g in _GREETINGS) + r")\b")


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def classify_rule_based(message: str) -> tuple[str, float]:
    """Classify intent using robust keyword heuristics.

    Order: explicit escalation and memory questions first, then a scored match
    across the remaining intents, then greeting / contact-details fallbacks. An
    unmatched message is `unknown` (which the graph clarifies — it does NOT
    escalate on its own).
    """
    text = message.lower()

    # 1. Explicit human request / anger / enterprise -> escalation.
    if _contains_any(text, _ESCALATION_PHRASES):
        return "human_escalation", 0.9

    # 2. Recall request.
    if _contains_any(text, _MEMORY_PHRASES):
        return "memory_question", 0.85

    # 3. Full lead details present (email + a name) -> ready to create a lead.
    has_email = bool(_EMAIL_RE.search(message))
    has_name = bool(_NAME_RE.search(message))
    if has_email and has_name:
        return "create_lead", 0.9

    # 4. Scored keyword match.
    best_intent = "unknown"
    best_score = 0
    for intent in _PRIORITY:
        score = sum(1 for kw in _KEYWORDS[intent] if kw in text)
        if score > best_score:
            best_score = score
            best_intent = intent
    if best_score > 0:
        confidence = min(0.6 + 0.12 * best_score, 0.95)
        return best_intent, confidence

    # 5. Contact details (email) without other signal -> still a lead.
    if has_email:
        return "lead_qualification", 0.7

    # 6. Pure greeting.
    if _GREETING_RE.search(message):
        return "greeting", 0.9

    # 7. Nothing matched -> unknown (the graph will ask a clarifying question).
    return "unknown", 0.3


def classify_with_llm(message: str) -> tuple[str, float]:
    """Classify intent with the configured LLM, falling back to rules."""
    from app.agent.llm import get_llm
    from app.agent.prompts import INTENT_CLASSIFICATION_PROMPT

    llm = get_llm()
    raw = llm.complete(INTENT_CLASSIFICATION_PROMPT.format(message=message))
    raw = (raw or "").strip().lower()
    intent = next((i for i in INTENTS if i in raw), None)
    if intent is None or intent == "unknown":
        # Trust the deterministic rules rather than a vague LLM reply.
        return classify_rule_based(message)
    return intent, 0.85


def classify_intent(message: str) -> tuple[str, float]:
    """Public entry point – picks the strategy based on configuration."""
    from app.config import settings

    if settings.mock_llm:
        return classify_rule_based(message)
    try:
        return classify_with_llm(message)
    except Exception:
        # Fail safe to deterministic rules if the LLM call fails.
        return classify_rule_based(message)
