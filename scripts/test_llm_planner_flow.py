"""Replay several conversations through the LLM planner against a local server.

Start the server first:
    uvicorn app.main:app --reload

Then run:
    python scripts/test_llm_planner_flow.py

Works in MOCK_LLM mode (deterministic planner) or against a real
OpenAI-compatible / DeepSeek model. Standard library only — no secrets printed.

It prints, for every turn: the user message, the assistant reply, the planner's
intent / mode / recommended action, the lead draft, missing fields, and any
lead/ticket ids and knowledge sources.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

CONVERSATIONS = {
    "A) casual / meta chat (no lead, no ticket)": [
        "Hello",
        "SAY HELLO TO ME",
        "What do you mean?",
        "What did I tell you so far?",
    ],
    "B) exploratory marketing help (no lead yet)": [
        "I need paid ads for my SaaS",
        "and SEO",
        "Help me with that",
        "I don't remember the company",
    ],
    "C) lead creation (one lead at the end)": [
        "Hi, I'd like to start a project",
        "Paid ads for my SaaS",
        "Collect details",
        "Company is BrightDesk",
        "My name is Sam, email sam@brightdesk.example",
        "Budget is around $5k/month",
    ],
    "D) human escalation (ticket)": [
        "This is taking forever, I want to talk to a human manager",
    ],
    "E) service / pricing via RAG": [
        "What services do you provide?",
        "How much does it cost?",
    ],
}


def call_chat(session: str, message: str) -> dict:
    payload = json.dumps({"session_id": session, "user_message": message}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def replay(title: str, session: str, messages: list[str]) -> None:
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)
    for message in messages:
        d = call_chat(session, message)
        print(f"\nuser      : {message}")
        print(f"assistant : {d.get('assistant_reply') or d.get('answer', '')}")
        print(f"  intent={d.get('user_intent')}  mode={d.get('mode')}  "
              f"action={d.get('recommended_action')}")
        print(f"  draft={d.get('lead_draft')}  missing={d.get('missing_fields')}")
        print(f"  lead_id={d.get('lead_id')}  ticket_id={d.get('ticket_id')}  "
              f"sources={d.get('sources')}")


def main() -> int:
    try:
        for i, (title, messages) in enumerate(CONVERSATIONS.items()):
            replay(title, f"planner-flow-{i}", messages)
    except urllib.error.URLError as exc:
        print(f"\nCould not reach the API ({exc}). Is the server running?")
        return 1
    print("\n" + "=" * 76)
    print("Done. Expect: A/B create nothing, C creates exactly one lead, D opens a "
          "ticket, E answers from the knowledge base with sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
