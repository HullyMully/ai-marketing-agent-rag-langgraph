"""Natural, non-repetitive response templates for the dialogue policy.

Each helper returns wording chosen by a rotating index (a turn counter) so the
assistant never sends the exact same line twice in a row. Selection is
deterministic — driven by the counter — so tests stay stable.
"""
from __future__ import annotations


def _pick(options: list[str], index: int) -> str:
    """Deterministically rotate through `options` by `index`."""
    if not options:
        return ""
    return options[index % len(options)]


# --------------------------------------------------------------------------- #
# Social / greeting
# --------------------------------------------------------------------------- #
_GREETINGS = [
    "Hi! Good to see you. I can help with marketing questions, pricing, or "
    "starting a project whenever you're ready.",
    "Hey again. Want to ask about services, pricing, or just start with a quick "
    "project idea?",
    "Hello! No rush — I'm here for marketing questions, pricing, or a project "
    "whenever you'd like.",
]

_JUST_HELLO = [
    "Got it — just saying hello \U0001F642 No rush. When you're ready, I can help "
    "with marketing services, pricing, or a project request.",
    "Hello to you too \U0001F642 Whenever you feel like it, I can talk through "
    "services, pricing, or a project idea.",
]


def greeting(index: int) -> str:
    return _pick(_GREETINGS, index)


def just_hello(index: int) -> str:
    return _pick(_JUST_HELLO, index)


# --------------------------------------------------------------------------- #
# Direction question after a bare service mention ("seo")
# --------------------------------------------------------------------------- #
def service_direction(service: str, index: int) -> str:
    svc = (service or "that").lower()
    options = [
        f"Sure, {svc} is one direction. Do you want to focus on {svc} only, or "
        "weigh it against other channels first?",
        f"Happy to dig into {svc}. Would you like to learn how it works, or have "
        "me prepare a request for the team?",
        "Should we keep this exploratory for now, or start a request?",
    ]
    return _pick(options, index)


# --------------------------------------------------------------------------- #
# Exploration mode (help the user think; never ask company/budget/email)
# --------------------------------------------------------------------------- #
def explore(service: str, product: str, index: int) -> str:
    svc = (service or "marketing").lower()
    where = f"a {product}" if product else "your product"
    options = [
        f"That's okay — we can just explore options for now. For {where}, what's "
        "the main goal: more signups, more demos, lower ad costs, or better "
        "visibility?",
        f"No problem. We can keep it general. Tell me what you do remember — the "
        "product type, target audience, or the goal you have in mind.",
        f"Sure. For {where}, a sensible starting point is usually: define the "
        f"audience, test {svc}, and improve landing-page conversion. Want me to "
        "walk through that?",
        f"No worries — we can skip the details. I can explain how {svc} could work "
        f"for {where} without creating anything.",
    ]
    return _pick(options, index)


# --------------------------------------------------------------------------- #
# Qualification paused (after repeated refusal / frustration)
# --------------------------------------------------------------------------- #
def paused(service: str, product: str, index: int) -> str:
    svc = (service or "marketing").lower()
    where = f"a {product}" if product else "your product"
    options = [
        "Understood — I won't ask for any lead details. If you'd like, I can just "
        f"explain how {svc} could work for {where}.",
        "No problem, I'll pause the questions. We can keep things general for as "
        "long as you want.",
        f"Got it, I'll stop asking. Whenever you're ready, I'm happy to talk "
        f"through {svc} for {where} — no commitment.",
    ]
    return _pick(options, index)


# --------------------------------------------------------------------------- #
# Qualification: ask for company / budget (varied) and other fields
# --------------------------------------------------------------------------- #
def ask_company_budget(need_company: bool, need_budget: bool, index: int) -> str:
    """Varied phrasing for the company/budget step so it never repeats verbatim."""
    if need_company and need_budget:
        options = [
            "Do you want to keep this exploratory, or should I collect details "
            "for the team — company name and a rough monthly budget?",
            "To prepare a request, I'd need the company name and an approximate "
            "monthly budget. Want to continue, or keep exploring?",
            "If you'd like to start a request, could you share the company name "
            "and a rough monthly budget? (We can skip it if you'd rather explore.)",
        ]
    elif need_company:
        options = [
            "Which company or product should I put this under? (Happy to keep it "
            "exploratory if you'd prefer.)",
            "Do you already have a company or product name, or should we start "
            "from the goal of the campaign?",
            "What's the company or product name? We can also keep this general "
            "for now.",
        ]
    else:  # need_budget only
        options = [
            "Roughly what monthly budget are you thinking? I can mark it as "
            "unknown if you're not sure.",
            "Do you have an approximate monthly budget in mind, or should I note "
            "it as to-be-decided?",
            "What's a rough monthly budget? No problem if it's still undecided.",
        ]
    return _pick(options, index)


def ask_contact(need_name: bool, need_email: bool, index: int) -> str:
    parts = []
    if need_name:
        parts.append("your name")
    if need_email:
        parts.append("the best email for follow-up")
    joined = " and ".join(parts) if parts else "a little more about what you need"
    options = [
        f"Great — what's {joined}?",
        f"Almost there. Could you share {joined}?",
        f"Perfect. Last bit: {joined}?",
    ]
    return _pick(options, index)
