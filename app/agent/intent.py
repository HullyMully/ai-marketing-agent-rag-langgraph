"""Intent classification.

Two strategies:
* Rule-based keyword classifier (deterministic, used in demo/mock mode and tests).
* LLM-based classifier via LangChain (used when MOCK_LLM=false).

Both return a tuple of (intent, confidence).
"""
from __future__ import annotations

INTENTS = [
    "general_question",
    "pricing_question",
    "service_question",
    "create_lead",
    "campaign_status_question",
    "support_request",
    "human_escalation",
    "unknown",
]

_KEYWORDS: dict[str, list[str]] = {
    "human_escalation": [
        "human", "manager", "real person", "agent", "speak to someone",
        "talk to someone", "representative", "complaint", "refund", "lawyer",
        "legal", "billing dispute", "escalate",
    ],
    "create_lead": [
        "become a client", "sign up", "hire you", "work with you", "get started",
        "want to start", "launch a campaign", "run ads", "run a campaign",
        "interested in working", "i'd like to", "i want to", "my budget",
        "my company", "my email", "my name is",
    ],
    "pricing_question": [
        "price", "pricing", "cost", "how much", "package", "packages", "fee",
        "fees", "budget", "quote", "rates",
    ],
    "campaign_status_question": [
        "campaign status", "campaign process", "how do you run", "workflow",
        "optimization", "reporting cadence", "campaign workflow", "status of",
    ],
    "service_question": [
        "service", "services", "what do you do", "offer", "ppc", "seo",
        "content marketing", "social media", "email marketing", "cro",
        "do you do",
    ],
    "support_request": [
        "help", "issue", "problem", "support", "not working", "broken",
        "question about my account",
    ],
}


def classify_rule_based(message: str) -> tuple[str, float]:
    """Classify intent using keyword heuristics.

    Order matters: escalation and lead intent are checked before the more
    generic knowledge intents.
    """
    text = message.lower()

    def hits(words: list[str]) -> int:
        return sum(1 for w in words if w in text)

    # Priority order for overlapping signals.
    priority = [
        "human_escalation",
        "create_lead",
        "pricing_question",
        "campaign_status_question",
        "service_question",
        "support_request",
    ]

    best_intent = "unknown"
    best_score = 0
    for intent in priority:
        score = hits(_KEYWORDS[intent])
        if score > best_score:
            best_score = score
            best_intent = intent

    if best_score == 0:
        # No keywords matched – treat as a low-confidence general question.
        if text.strip().endswith("?") or len(text.split()) > 3:
            return "general_question", 0.35
        return "unknown", 0.2

    # Map keyword hit count to a rough confidence score.
    confidence = min(0.5 + 0.15 * best_score, 0.95)
    return best_intent, confidence


def classify_with_llm(message: str) -> tuple[str, float]:
    """Classify intent using an LLM (only when MOCK_LLM=false)."""
    from app.agent.llm import get_llm
    from app.agent.prompts import INTENT_CLASSIFICATION_PROMPT

    llm = get_llm()
    raw = llm.complete(
        INTENT_CLASSIFICATION_PROMPT.format(
            intents=", ".join(INTENTS), message=message
        )
    ).strip().lower()
    intent = next((i for i in INTENTS if i in raw), "unknown")
    # The LLM path still uses the rule-based score as a confidence proxy.
    _, rule_conf = classify_rule_based(message)
    confidence = 0.8 if intent != "unknown" else max(rule_conf, 0.3)
    return intent, confidence


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
