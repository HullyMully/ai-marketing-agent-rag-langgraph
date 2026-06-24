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
        "You are warm, concise and professional. Use the provided knowledge base "
        "for company-specific questions, and use the conversation context for "
        "meta questions, language requests, greetings, practical off-topic help "
        "and follow-ups. Keep replies short (2-4 sentences), in plain natural "
        "language. Do not paste raw markdown, headings, bullet lists or long "
        "document fragments. If a company-specific answer is not in the context, "
        f"say you are not sure and offer to connect the user with a {c.escalation_target}. "
        "Never invent pricing, legal or contractual details."
    )


# Used to answer knowledge questions with retrieved RAG context.
RAG_ANSWER_PROMPT = PromptTemplate.from_template(
    """{persona}

Conversation so far:
{history}

Knowledge base context:
{context}

Language policy:
{language_instruction}

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

# Used to generate the FINAL assistant reply after the backend has validated
# (and possibly rejected) the planner's recommended action. The reply must be
# written fresh by the LLM — never a canned phrase. The backend passes the
# validation outcome so the model can explain or ask naturally.
FINAL_REPLY_PROMPT = PromptTemplate.from_template(
    """{persona}

Conversation so far:
{history}

Relevant company knowledge:
{context}

What we know about this lead so far: {lead_draft}
Still missing before a request can be created: {missing}

Language policy:
{language_instruction}

Planner analysis:
- conversation_target: {conversation_target}
- context_relation: {context_relation}
- user_intent: {user_intent}
- assistant_mode: {assistant_mode}
- should_continue_qualification: {should_continue_qualification}
- draft_reply_from_planner: {draft_reply}

The backend reviewed the recommended action "{action}" and decided: {validation}.
(Do NOT claim any lead or ticket was created unless the decision says it was executed.)

User's latest message: {question}

Write the assistant's next reply in your own words (1-3 short, natural sentences).
The latest user message is the main task: answer it directly, even if it
switches away from the previous lead flow. Only ask for lead details when
should_continue_qualification is true or the validation result says details are
required for an explicitly requested action. If the user asks about the app,
the previous reply, or something unrelated, answer that instead of continuing
qualification. If the user asks to translate the previous assistant message,
translate it instead of continuing the old topic. If the user explicitly asks
for English/Russian, obey that immediately even if earlier messages used a
different language. Never output JSON, menus, markdown, or canned phrases."""
)
