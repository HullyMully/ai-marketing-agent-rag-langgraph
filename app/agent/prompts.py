"""LangChain prompt templates used by the agent."""
from __future__ import annotations

from langchain_core.prompts import PromptTemplate

SYSTEM_PERSONA = (
    "You are Nova, the AI assistant for NovaGrowth Agency, a digital marketing "
    "agency. You are helpful, concise and honest. You answer using the provided "
    "knowledge base context. If the answer is not in the context, say you are not "
    "sure and offer to connect the user with a human manager. Never invent "
    "pricing, legal, or contractual details."
)

# Used to answer knowledge questions with retrieved RAG context.
RAG_ANSWER_PROMPT = PromptTemplate.from_template(
    """{persona}

Conversation so far:
{history}

Knowledge base context:
{context}

User question: {question}

Write a clear, friendly answer (2-5 sentences). If relevant, mention the next
step (e.g., booking a discovery call). Do not fabricate details that are not in
the context."""
)

# Used to classify intent when running against a real LLM.
INTENT_CLASSIFICATION_PROMPT = PromptTemplate.from_template(
    """Classify the user's message into exactly one of these intents:
{intents}

Reply with only the intent label.

Message: {message}
Intent:"""
)

# Used when asking the user for missing lead-qualification fields.
COLLECT_INFO_PROMPT = PromptTemplate.from_template(
    """{persona}

The user wants to work with the agency. You still need: {missing}.
Already known: {known}.

Ask a short, friendly follow-up question to collect the missing details. Ask for
all missing fields in one message."""
)
