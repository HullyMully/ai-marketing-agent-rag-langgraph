"""Replay two multi-turn conversations against a running local API.

Start the server first:
    uvicorn app.main:app --reload

Then run:
    python scripts/test_real_conversation.py

Standard library only — no third-party deps, no API keys. Every reply comes from
the real assistant; this script just drives the conversation and checks the high
-level outcome of each scenario:

  A) A confused / joking / refusing user  -> NO lead is created.
  B) A willing user who provides every field -> exactly ONE lead, only at the end.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# A) Confused / joking / refusal — must stay exploratory, never create a lead.
SCENARIO_A = [
    "Hello",
    "Hello!",
    "What do you mean? I wanna to hello to you",
    "seo",
    "Hahahah I'm joking. I need paid ads for my saas",
    "and seo",
    "Help me with that",
    "No(",
    "I don't remember",
    "I FORGOT",
    "NO",
]

# B) Willing user — provides every field; one lead should be created at the end.
SCENARIO_B = [
    "Hello, I need help with marketing",
    "Help starting a project please",
    "Paid ads for my SaaS",
    "My company is BrightDesk",
    "My name is Sam and email is sam@brightdesk.example",
    "Budget is around $5k/month",
    "What did I tell you about my company?",
]


def call_chat(session: str, message: str) -> dict:
    payload = json.dumps({"session_id": session, "user_message": message}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def replay(title: str, session: str, messages: list[str]) -> list[dict]:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    results = []
    for message in messages:
        data = call_chat(session, message)
        results.append(data)
        print(f"\nuser     : {message}")
        print(f"assistant: {data.get('answer', '')}")
        print(f"  mode={data.get('mode')}  paused={data.get('qualification_paused')}  "
              f"interests={data.get('known_interests')}")
        print(f"  lead_id={data.get('lead_id')}  ticket_id={data.get('ticket_id')}  "
              f"next={data.get('next_step')}")
    return results


def main() -> int:
    try:
        a = replay("SCENARIO A — confused / joking / refusal (expect NO lead)",
                   "real-conversation-a", SCENARIO_A)
        b = replay("SCENARIO B — willing user (expect exactly ONE lead at the end)",
                   "real-conversation-b", SCENARIO_B)
    except urllib.error.URLError as exc:
        print(f"\nCould not reach the API ({exc}). Is it running?")
        return 1

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    a_leads = any(x.get("lead_created") for x in a)
    a_tickets = any(x.get("ticket_created") for x in a)
    b_lead_ids = {x.get("lead_id") for x in b if x.get("lead_created")}
    print(f"A) created a lead?   {a_leads}   (expected: False)")
    print(f"A) created a ticket? {a_tickets}  (expected: False)")
    print(f"A) paused at end?    {a[-1].get('qualification_paused')}  (expected: True)")
    print(f"B) lead id(s):       {b_lead_ids or '{}'}  (expected: exactly one)")

    ok = (not a_leads) and (not a_tickets) and (len(b_lead_ids) == 1)
    print("\nRESULT:", "PASS" if ok else "CHECK OUTPUT")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
