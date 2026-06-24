"""Property-style tests for the conversation planner.

These cases protect the general behavior: the latest user message dominates,
meta/app questions interrupt qualification, repeated replies are blocked, and
tests assert planner metadata instead of exact wording.
"""
import uuid

from fastapi.testclient import TestClient


def _sid(tag: str) -> str:
    return f"general-{tag}-{uuid.uuid4().hex[:6]}"


def _chat(client: TestClient, sid: str, msg: str) -> dict:
    resp = client.post("/chat", json={"session_id": sid, "user_message": msg})
    assert resp.status_code == 200
    return resp.json()


def _assert_no_duplicate_neighbors(replies: list[str]) -> None:
    for previous, current in zip(replies, replies[1:]):
        assert previous.strip().lower() != current.strip().lower()


def test_beginner_then_app_question_switches_context(client: TestClient) -> None:
    sid = _sid("app-switch")
    turns = [
        _chat(client, sid, "Hello my brother"),
        _chat(client, sid, "I am new, so Idk what to do there"),
        _chat(client, sid, "What about this app?"),
    ]

    _assert_no_duplicate_neighbors([t["answer"] for t in turns])
    for turn in turns:
        assert turn["lead_created"] is False
        assert turn["ticket_created"] is False

    third = turns[-1]
    assert third["recommended_action"] == "answer_only"
    assert third["conversation_target"] == "assistant_product"
    assert third["context_relation"] in {"switches_topic", "asks_meta_question"}
    assert third["should_continue_qualification"] is False
    assert third["planner_decision"]["conversation_target"] == "assistant_product"
    assert any(word in third["answer"].lower() for word in ("app", "assistant", "chat"))


def test_topic_switches_do_not_resume_old_qualification(client: TestClient) -> None:
    sid = _sid("switches")
    replies = []

    first = _chat(client, sid, "I need help with marketing")
    replies.append(first["answer"])
    assert first["lead_created"] is False
    assert first["ticket_created"] is False

    app = _chat(client, sid, "Actually, what is this app?")
    replies.append(app["answer"])
    assert app["conversation_target"] == "assistant_product"
    assert app["should_continue_qualification"] is False
    assert app["lead_created"] is False

    pricing = _chat(client, sid, "Ok, now tell me about pricing")
    replies.append(pricing["answer"])
    assert pricing["conversation_target"] == "configured_company"
    assert pricing["knowledge_used"] is True
    assert pricing["sources"]
    assert pricing["lead_created"] is False

    email = _chat(client, sid, "Wait, why do you need my email?")
    replies.append(email["answer"])
    assert email["conversation_target"] == "previous_reply"
    assert email["context_relation"] in {"asks_meta_question", "asks_clarification"}
    assert email["should_continue_qualification"] is False
    assert email["lead_created"] is False
    assert email["ticket_created"] is False

    _assert_no_duplicate_neighbors(replies)


def test_repeated_vague_messages_do_not_repeat_or_create_records(client: TestClient) -> None:
    sid = _sid("vague")
    turns = [
        _chat(client, sid, "I am new here"),
        _chat(client, sid, "I still don't get it"),
        _chat(client, sid, "bro explain"),
    ]

    _assert_no_duplicate_neighbors([t["answer"] for t in turns])
    for turn in turns:
        assert turn["lead_created"] is False
        assert turn["ticket_created"] is False
        assert turn["should_continue_qualification"] is False
        assert turn["recommended_action"] in {"answer_only", "ask_clarifying_question"}


def test_latest_message_beats_exploration_template(client: TestClient) -> None:
    sid = _sid("latest")
    turns = [
        _chat(client, sid, "hello my brother"),
        _chat(client, sid, "What?"),
        _chat(client, sid, "I am new, so please help me"),
        _chat(client, sid, "How can I open the can of coke"),
    ]
    answers = [t["answer"] for t in turns]

    _assert_no_duplicate_neighbors(answers)
    for turn in turns:
        assert turn["lead_created"] is False
        assert turn["ticket_created"] is False
        assert turn["should_continue_qualification"] is False

    assert turns[1]["conversation_target"] == "previous_reply"
    assert turns[2]["recommended_action"] == "answer_only"
    assert turns[3]["conversation_target"] == "unrelated"
    assert turns[3]["recommended_action"] == "answer_only"
    assert "can" in turns[3]["answer"].lower() or "pull" in turns[3]["answer"].lower()

    repeated_template = "what's the main goal: more signups, more demos, lower ad costs"
    assert all(repeated_template not in answer.lower() for answer in answers)


def test_chaotic_casual_and_help_turns_do_not_leak_router_templates(client: TestClient) -> None:
    sid = _sid("chaotic")
    script = [
        "Привет",
        "как дела",
        "Hello",
        "how are you",
        "FUCK YOU",
        "answer",
        "help me",
        "help me please",
        "please",
        "help me",
        "call 911",
        "okay",
        "Help me",
        "I am new",
        "I am new customer help me",
    ]
    turns = [_chat(client, sid, msg) for msg in script]
    answers = [turn["answer"] for turn in turns]

    _assert_no_duplicate_neighbors(answers)
    for turn in turns:
        assert turn["lead_created"] is False
        assert turn["ticket_created"] is False
        assert turn["should_continue_qualification"] is False

    banned_fragments = [
        "i will answer the message in front of me",
        "fresh angle",
        "let me answer that a different way",
        "outside the company/project context",
        "let's reset this turn",
        "you asked:",
    ]
    for answer in answers:
        lower = answer.lower()
        assert not any(fragment in lower for fragment in banned_fragments)

    assert turns[0]["user_intent"] == "greeting"
    assert turns[1]["user_intent"] == "casual_chat"
    assert turns[4]["user_intent"] == "complaint"
    assert turns[10]["conversation_target"] == "unrelated"
    assert "911" in turns[10]["answer"]
    assert turns[-1]["user_intent"] == "confusion"


def test_capability_language_practical_and_project_turns_stay_contextual(client: TestClient) -> None:
    sid = _sid("capability-language")
    script = [
        "привет",
        "hello",
        "How are you",
        "give me hand with open my bottle of coke",
        "Okay sorry",
        "Idk I'm new. What can you do?",
        "а на русском сможешь?",
        "переведи на русский свои сообщения",
        "Idk I'm new. What can you do?",
        "I need paid ads for my saas project",
        "What do you want to know?",
    ]
    turns = [_chat(client, sid, msg) for msg in script]
    answers = [turn["answer"] for turn in turns]

    _assert_no_duplicate_neighbors(answers)
    for turn in turns:
        assert turn["lead_created"] is False
        assert turn["ticket_created"] is False

    assert turns[3]["conversation_target"] == "unrelated"
    assert "bottle" in turns[3]["answer"].lower() or "cap" in turns[3]["answer"].lower()

    first_capability = turns[5]
    assert first_capability["conversation_target"] == "assistant_product"
    assert first_capability["knowledge_used"] is False
    assert "lead qualification policy" not in first_capability["answer"].lower()
    assert "required fields" not in first_capability["answer"].lower()

    assert turns[6]["conversation_target"] == "assistant_product"
    assert "рус" in turns[6]["answer"].lower()
    assert turns[7]["conversation_target"] == "previous_reply"
    assert "по-русски" in turns[7]["answer"].lower() or "рус" in turns[7]["answer"].lower()
    assert any(
        word in turns[8]["answer"].lower()
        for word in ("company", "request", "lead", "project")
    )

    project = turns[9]
    assert project["conversation_target"] == "user_project"
    assert project["recommended_action"] == "update_lead_draft"
    assert "Paid ads" in project["lead_draft"].get("service_interest", "")
    assert project["lead_draft"].get("product_type") == "SaaS"

    follow_up = turns[10]
    assert follow_up["conversation_target"] == "previous_reply"
    assert "what" not in follow_up["lead_draft"].get("company", "").lower()
    assert any(word in follow_up["answer"].lower() for word in ("нужно", "не хватает", "need"))
