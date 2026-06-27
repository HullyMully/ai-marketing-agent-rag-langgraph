# LangGraph flow

English | [Русский](./langgraph-flow.ru.md)

The agent is a compiled `StateGraph` (see `app/agent/graph.py`) with just two
nodes: **`plan`** and **`act`**. State is a `TypedDict` (`app/agent/state.py`)
threaded through both nodes. The reasoning lives in the **LLM planner**
(`app/agent/planner.py`); the graph orchestrates and the backend validates.

```mermaid
stateDiagram-v2
    [*] --> plan
    plan --> act
    act --> [*]
```

## Node `plan`

1. Builds the planner **input** from the company profile, retrieved RAG
   knowledge, recent conversation history, session memory, the current lead
   draft, the ticket state and the list of available actions, plus the latest
   user message.
2. Calls the planner, which returns a single structured **JSON decision**
   (intent, assistant mode, extracted fields, memory updates, missing fields,
   one recommended action, a natural reply, knowledge-used + sources, and a
   confidence score). The output is validated with Pydantic; invalid JSON is
   repaired with one retry, and a still-invalid result becomes a controlled
   internal error rather than a crash.

## Node `act`

The planner only *recommends* an action — the backend decides whether it runs
(`app/agent/validation.py`):

- **`create_lead`** executes only when the lead rules pass (see below); otherwise
  the assistant naturally asks for what's missing.
- **`create_ticket`** executes only when escalation is justified; otherwise the
  assistant clarifies instead.
- **`answer_only` / `ask_clarifying_question` / `update_lead_draft` /
  `pause_qualification` / `retrieve_knowledge`** relay the planner's reply (or, in
  real-LLM mode, a freshly generated contextual reply).

Memory updates and the lead draft are applied, side effects (lead/ticket ids) are
recorded, and the **final user-facing reply is LLM-generated** — never a scripted
template in normal chat.

## Available actions

`answer_only`, `update_lead_draft`, `create_lead`, `create_ticket`,
`ask_clarifying_question`, `pause_qualification`, `retrieve_knowledge`.

## Lead-creation rules

A lead is created only when **all** hold: no lead exists yet for the session; a
name, a company, a valid email and a service interest are present; and a budget
range is present **or** the budget is explicitly unknown and the user agreed to
proceed without one — and the planner actually recommended `create_lead`. Until
then the assistant keeps qualifying. Duplicate leads for the same session are
blocked.

## Ticket-escalation rules

A ticket is created only when escalation is genuinely justified: an explicit
request for a human/manager/operator/specialist/support, a real
complaint/frustration, a custom/enterprise need, or a high-confidence planner
escalation with a substantive reason that the backend rules agree with. A bare
greeting, "I am a new customer", "what do you mean?", "I don't remember",
"I told you", jokes, ordinary confusion or ordinary swearing **never** open a
ticket.

## Offline mode

With `MOCK_LLM=true` a deterministic engine produces the same decision contract
without any API call, so the whole graph runs and is testable offline. It is also
the safe fallback if a real model call fails. The deterministic engine is an
offline stand-in, not the product's reasoning layer — with a real model the LLM
planner makes the decisions and writes every reply.
