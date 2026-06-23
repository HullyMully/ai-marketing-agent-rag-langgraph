"""Prompt templates and persona used by the agent.

The persona is built from the configured company profile, so the same code
serves any business that configures `config/company.local.json` or env vars.
"""
from __future__ import annotations

from langchain_core.prompts import PromptTemplate

from app.company import get_company


def get_system_persona() -> str:
    """Build the assistant persona from the current company profile."""
    c = get_company()
    company = c.display_name
    industry = f" ({c.business_industry})" if c.business_industry else ""
    return (
        f"You are {c.assistant_name}, the AI assistant for {company}{industry}. "
        "You are warm, concise and professional. Answer using the provided "
        "knowledge base context. Keep replies short (2-4 sentences), in plain "
        "natural language. Do not paste raw markdown, headings, bullet lists or "
        "long document fragments. If the answer is not in the context, say you "
        f"are not sure and offer to connect the user with a {c.escalation_target}. "
        "Never invent pricing, legal or contractual details."
    )


# Used to answer knowledge questions with retrieved RAG context.
RAG_ANSWER_PROMPT = PromptTemplate.from_template(
    """{persona}

Conversation so far:
{history}

Knowledge base context:
{context}

User message: {question}

Write a short, friendly reply in your own words (2-4 sentences). Summarise the
relevant facts; do NOT copy the context verbatim or output markdown. If helpful,
suggest one natural next step."""
)

# Used to classify intent when running against a real LLM.
INTENT_CLASSIFICATION_PROMPT = PromptTemplate.from_template(
    """You are an intent classifier for a company's customer assistant. Classify
the user's latest message into exactly ONE of these intents:

- greeting: a simple hello/greeting with no specific request
- service_question: asks what the company does or which services it offers
- pricing_question: asks about price, cost, packages or budget ranges
- lead_qualification: a potential customer is interested, needs help, or wants to
  start working with the company but has not yet given full contact details
- create_lead: the user provides lead details (a name and/or company and an email)
- support_request: reports a problem or needs help with an existing account/issue
- human_escalation: explicitly asks for a human/manager/operator, is angry or
  complaining, or needs a custom/enterprise workflow
- memory_question: asks the assistant to recall something said earlier
- unknown: none of the above, or unclear

Reply with ONLY the intent label, nothing else.

Message: {message}
Intent:"""
)

# Used when asking the user for missing lead-qualification fields.
COLLECT_INFO_PROMPT = PromptTemplate.from_template(
    """{persona}

The user is interested in working with the company. You still need: {missing}.
Already known: {known}.

Ask one short, friendly follow-up question to collect the missing details."""
)
