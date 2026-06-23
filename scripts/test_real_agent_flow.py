"""Run the full lead-qualification flow against a running local API.

Start the server first:
    uvicorn app.main:app --reload

Then run:
    python scripts/test_real_agent_flow.py

Standard library only — no third-party deps, no API keys. Every reply comes from
the real agent; this script just drives the conversation and prints the session
state it returns.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION = "real-flow-demo"

MESSAGES = [
    "Hello I am a new customer",
    "I need help with SaaS ads",
    "Company is BrightDesk, budget around $5k/month",
    "My name is Sam, email sam@brightdesk.example",
    "What company did I mention?",
]


def call_chat(message: str) -> dict:
    payload = json.dumps({"session_id": SESSION, "user_message": message}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    print(f"Driving the lead flow against {BASE_URL}/chat\n" + "=" * 64)
    for message in MESSAGES:
        try:
            data = call_chat(message)
        except urllib.error.URLError as exc:
            print(f"\nCould not reach the API ({exc}). Is it running?")
            return 1
        print(f"\nuser         : {message}")
        print(f"answer       : {data.get('answer', '')}")
        print(f"intent       : {data.get('intent')}")
        print(f"action       : {data.get('action')}")
        print(f"lead_draft   : {data.get('lead_draft')}")
        print(f"missing      : {data.get('missing_fields')}")
        print(f"lead_id      : {data.get('lead_id')}")
        print(f"ticket_id    : {data.get('ticket_id')}")
    print("\n" + "=" * 64)
    print("Expected: a single lead is created only at the last contact step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
