import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import anthropic
import httpx2
import pytest

from app.routers.briefing import get_ai_client
from app.services.briefing import DayContext, generate_rule_based
from app.timeutil import local_today

IST = ZoneInfo("Asia/Kolkata")
TODAY = local_today(IST)

VALID = {
    "headline": "Two meetings and an overdue proposal",
    "summary": "Start with the proposal before your 11:00 call.",
    "schedule_notes": ["Free 13:00-17:00 for deep work."],
    "focus": [
        {"title": "Send proposal", "reason": "Overdue, high priority", "task_id": 1},
        {"title": "Invented task", "reason": "hallucinated id", "task_id": 999},
    ],
    "heads_up": [],
}


class FakeMessages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def fake_client(outcome):
    messages = FakeMessages(outcome)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def reply(payload, stop_reason="end_turn"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model="claude-opus-5-5",
        _request_id="req_test",
    )


@pytest.fixture
def with_ai(app, settings):
    """Pretend a key is configured and route calls to a fake client."""
    settings.anthropic_api_key = "sk-test-not-real"

    def install(outcome):
        client, messages = fake_client(outcome)
        app.dependency_overrides[get_ai_client] = lambda: client
        return messages

    yield install
    app.dependency_overrides.clear()


def seed(client):
    client.post("/api/tasks", json={"title": "Send proposal", "priority": "high", "due_date": str(TODAY - timedelta(days=1))})
    client.post("/api/tasks", json={"title": "Review PR", "due_date": str(TODAY)})


def test_without_a_key_the_rule_based_briefing_is_used(client):
    seed(client)
    r = client.post("/api/briefing")
    assert r.status_code == 201
    b = r.json()
    assert b["source"] == "rule" and b["model"] is None and b["note"] is None
    assert b["content"]["focus"][0] == {"title": "Send proposal", "reason": "High priority, overdue since " + str(TODAY - timedelta(days=1)), "task_id": 1}
    assert client.get("/api/briefing/today").json()["id"] == b["id"]
    assert client.get("/api/dashboard/today").json()["briefing"]["id"] == b["id"]


def test_ai_briefing_request_shape_and_validation(client, with_ai):
    seed(client)
    messages = with_ai(reply(VALID))
    b = client.post("/api/briefing").json()
    assert b["source"] == "ai" and b["model"] == "claude-opus-5-5" and b["note"] is None
    assert b["content"]["headline"] == VALID["headline"]
    # A task id the model invented is dropped; the real one is kept.
    assert [f["task_id"] for f in b["content"]["focus"]] == [1, None]

    [call] = messages.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    snapshot = json.loads(call["messages"][0]["content"])
    assert snapshot["tasks_overdue"][0]["title"] == "Send proposal"
    assert snapshot["tasks_due_today"][0]["title"] == "Review PR"


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (reply("not json at all"), "unexpected format"),
        (reply({"headline": "missing fields"}), "unexpected format"),
        (reply(VALID, stop_reason="refusal"), "declined"),
        (reply(VALID, stop_reason="max_tokens"), "cut off"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), "could not be reached"),
    ],
)
def test_ai_failures_fall_back_to_rules_with_a_visible_note(client, with_ai, outcome, expected):
    seed(client)
    with_ai(outcome)
    b = client.post("/api/briefing").json()
    assert b["source"] == "rule" and b["model"] is None
    assert expected in b["note"] and "rule-based" in b["note"]
    assert b["content"]["focus"][0]["title"] == "Send proposal"


def test_regeneration_is_rate_limited(client):
    assert client.post("/api/briefing").status_code == 201
    r = client.post("/api/briefing")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_meta_reports_ai_enabled(anon, settings):
    settings.anthropic_api_key = "sk-test-not-real"
    assert anon.get("/api/meta").json() == {"version": "1.0.0", "ai_enabled": True, "ai_model": "claude-opus-5-5"}


# --- rule engine unit tests ------------------------------------------------------------


def ctx(**kw):
    base = dict(
        day=date(2026, 11, 9),
        tz=IST,
        now_local=datetime(2026, 11, 9, 8, 0, tzinfo=IST),
        events=[], overdue=[], due_today=[], upcoming=[], reminders=[], emails=[], priorities=[],
    )
    base.update(kw)
    return DayContext(**base)


def ev(title, start, end, all_day=False):
    return {"title": title, "start": start, "end": end, "all_day": all_day, "location": ""}


def test_rule_engine_empty_day():
    c = generate_rule_based(ctx())
    assert c.headline.startswith("A clear day")
    assert c.focus == [] and c.schedule_notes == ["Longest free block: 08:00-18:00 (10h 0m)."]


def test_rule_engine_spots_overlaps_back_to_back_and_free_time():
    c = generate_rule_based(
        ctx(
            events=[
                ev("Standup", "09:00", "09:15"),
                ev("Design review", "09:15", "10:30"),
                ev("Vendor call", "10:00", "11:00"),
                ev("Offsite", "00:00", "23:59", all_day=True),
            ]
        )
    )
    assert c.headline == "3 meetings"
    assert "All day: Offsite" in c.schedule_notes
    assert any("Back-to-back" in n for n in c.schedule_notes)
    assert any("overlaps" in n for n in c.schedule_notes)
    assert "Longest free block: 11:00-18:00 (7h 0m)." in c.schedule_notes
    assert c.summary.startswith('You have 3 events today, starting with "Standup" at 09:00.')


def test_rule_engine_orders_focus_by_priority_then_overdue_first():
    c = generate_rule_based(
        ctx(
            overdue=[{"id": 1, "title": "old low", "priority": "low", "due_date": "2026-11-01"},
                     {"id": 2, "title": "old high", "priority": "high", "due_date": "2026-11-05"}],
            due_today=[{"id": 3, "title": "today high", "priority": "high", "due_date": "2026-11-09"},
                       {"id": 4, "title": "today medium", "priority": "medium", "due_date": "2026-11-09"}],
            reminders=[{"text": "Pay rent", "time": "18:00"}],
            emails=[{"from": "Priya", "subject": "Contract", "flagged": True, "unread": True}],
        )
    )
    assert [f.task_id for f in c.focus] == [2, 3, 4]
    assert c.heads_up == ["Reminder at 18:00: Pay rent", 'Flagged email from Priya: "Contract"']
    assert "1 email needs attention." in c.summary
