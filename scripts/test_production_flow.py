"""Manual end-to-end check of the assistant against a running local server.

This drives a realistic conversation through the live ``/chat`` endpoint and
prints the backend metadata for each turn. Every reply comes from the real
agent — the script only sends messages and reports what comes back.

Start the server first:

    uvicorn app.main:app --reload

Then, in another terminal:

    python scripts/test_production_flow.py

Standard library only — no third-party deps and no API keys required (the
server runs in MOCK_LLM mode by default).

The flow exercises six steps:

    1. greeting
    2. service request
    3. partial lead info (company + budget)
    4. complete lead info (name + email)  -> lead is created here, and only here
    5. memory follow-up
    6. human escalation                   -> a support ticket is created
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION = f"prod-flow-{uuid.uuid4().hex[:8]}"

STEPS = [
    ("greeting", "Hello, I need help with marketing"),
    ("service request", "Paid ads for my SaaS"),
    ("partial lead info", "BrightDesk, around $5k/month"),
    ("complete lead info", "Sam, sam@brightdesk.example"),
    ("memory follow-up", "What did I tell you about my company?"),
    ("human escalation", "Actually, can I talk to a human manager?"),
]


def call_chat(message: str) -> dict:
    payload = json.dumps(
        {"session_id": SESSION, "user_message": message}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print(f"Driving the production flow against {BASE_URL}/chat")
    print(f"session_id = {SESSION}")
    print("=" * 70)

    lead_id = None
    ticket_id = None

    for label, message in STEPS:
        try:
            data = call_chat(message)
        except urllib.error.URLError as exc:
            print(f"\nCould not reach the API ({exc}). Is the server running?")
            return 1

        lead_id = data.get("lead_id") or lead_id
        ticket_id = data.get("ticket_id") or ticket_id

        print(f"\n[{label}]")
        print(f"  message       : {message}")
        print(f"  answer        : {data.get('answer', '')}")
        print(f"  intent        : {data.get('intent')}")
        print(f"  action        : {data.get('action')}")
        print(f"  lead_draft    : {data.get('lead_draft')}")
        print(f"  missing_fields: {data.get('missing_fields')}")
        print(f"  lead_id       : {data.get('lead_id')}")
        print(f"  ticket_id     : {data.get('ticket_id')}")

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  lead created  : {'yes (#%s)' % lead_id if lead_id else 'no'}")
    print(f"  ticket created: {'yes (#%s)' % ticket_id if ticket_id else 'no'}")
    print(
        "  Expected: exactly one lead, created only at the 'complete lead info' "
        "step, and one escalation ticket."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
