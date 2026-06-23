"""Manually exercise the agent against a running local API.

Start the server first:
    uvicorn app.main:app --reload

Then run:
    python scripts/test_agent_flows.py

Uses only the standard library (no third-party deps, no API keys). It posts a
handful of messages to /chat and prints the assistant answer plus routing
metadata (intent, action, lead/ticket ids).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION = "manual-flow-demo"

# (session_id, message). A shared session shows memory across turns.
FLOWS: list[tuple[str, str]] = [
    (SESSION + "-1", "Hello I'm a new customer!"),
    (SESSION + "-2", "What services do you offer?"),
    (SESSION + "-3", "What pricing packages are available?"),
    (SESSION + "-4", "I need help launching paid ads for my SaaS product."),
    (
        SESSION + "-4",
        "My name is Sam. I work at BrightDesk. Budget is around $5k/month. "
        "Contact me at sam@brightdesk.example.",
    ),
    (SESSION + "-4", "What company did I mention?"),
    (SESSION + "-5", "I need a human manager for a custom enterprise workflow."),
    (SESSION + "-6", "asdf qwerty zxcv"),
]


def call_chat(session_id: str, message: str) -> dict:
    payload = json.dumps({"session_id": session_id, "user_message": message}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    print(f"Posting demo flows to {BASE_URL}/chat\n" + "=" * 60)
    for session_id, message in FLOWS:
        try:
            data = call_chat(session_id, message)
        except urllib.error.URLError as exc:
            print(f"\nCould not reach the API ({exc}). Is it running?")
            return 1
        print(f"\nuser   : {message}")
        print(f"answer : {data.get('answer', '')}")
        print(
            "meta   : "
            f"intent={data.get('intent')} "
            f"action={data.get('action_taken')} "
            f"lead_id={data.get('created_lead_id')} "
            f"ticket_id={data.get('created_ticket_id')} "
            f"escalated={data.get('escalated')}"
        )
    print("\n" + "=" * 60)
    print("Done. Greetings/interest should show no ticket; explicit human "
          "requests should.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
