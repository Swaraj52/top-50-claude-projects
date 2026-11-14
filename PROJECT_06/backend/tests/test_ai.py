from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.services import ai


def make_meeting(day=date(2026, 11, 12)):
    return SimpleNamespace(title="Weekly product review", occurred_on=day)


NOTES = """Weekly product review

Summary: We reviewed the beta scope.

Decisions:
- Ship the beta on 1 December

Actions:
- @Priya send the onboarding deck by Friday
"""


class FakeResponse:
    def __init__(self, payload=None, status=200, text=None):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload) if text is None and payload is not None else (text or "")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad status", request=None, response=None)

    def json(self):
        return self._payload


class FakeClient:
    """Stands in for httpx.Client and records the request it was given."""

    calls: list[dict] = []
    response: FakeResponse | Exception = None

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):  # noqa: A002 - mirrors httpx
        FakeClient.calls.append({"url": url, "headers": headers or {}, "json": json})
        if isinstance(FakeClient.response, Exception):
            raise FakeClient.response
        return FakeClient.response


@pytest.fixture
def fake_http(monkeypatch):
    FakeClient.calls = []
    FakeClient.response = FakeResponse()
    monkeypatch.setattr(ai.httpx, "Client", FakeClient)
    return FakeClient


def claude_payload(**overrides):
    payload = {
        "summary": "The team agreed to ship the beta on 1 December.",
        "decisions": ["Ship the beta on 1 December"],
        "actions": [{"title": "Send the onboarding deck", "owner": "Priya", "due_date": "2026-11-13"}],
        "content": [{"type": "text", "text": ""}],
    }
    payload.update(overrides)
    payload["content"] = [{"type": "text", "text": json.dumps({k: v for k, v in payload.items() if k != "content"})}]
    return payload


# --- validation ------------------------------------------------------------


def test_validate_accepts_a_well_formed_payload():
    summary, decisions, actions = ai._validate(
        {
            "summary": "The team agreed to ship.",
            "decisions": ["Ship the beta on 1 December"],
            "actions": [{"title": "Send the deck", "owner": "Priya", "due_date": "2026-11-13"}],
        },
        date(2026, 11, 12),
    )
    assert summary == "The team agreed to ship."
    assert decisions == ["Ship the beta on 1 December"]
    assert actions[0].title == "Send the deck"
    assert actions[0].owner == "Priya"
    assert actions[0].due_date == date(2026, 11, 13)


def test_validate_collapses_whitespace():
    summary, _, _ = ai._validate({"summary": "  A   lot\nof\tspace.  "}, date(2026, 11, 12))
    assert summary == "A lot of space."


def test_validate_rejects_a_non_object():
    with pytest.raises(ValueError):
        ai._validate(["not", "an", "object"], date(2026, 11, 12))


def test_validate_rejects_a_short_summary():
    with pytest.raises(ValueError):
        ai._validate({"summary": "Ok", "decisions": [], "actions": []}, date(2026, 11, 12))


def test_validate_rejects_wrong_list_types():
    with pytest.raises(ValueError):
        ai._validate({"summary": "Enough text here.", "decisions": "nope", "actions": []}, date(2026, 11, 12))
    with pytest.raises(ValueError):
        ai._validate({"summary": "Enough text here.", "decisions": [], "actions": {}}, date(2026, 11, 12))


def test_validate_treats_missing_lists_as_empty():
    summary, decisions, actions = ai._validate({"summary": "A short but valid summary."}, date(2026, 11, 12))
    assert summary == "A short but valid summary."
    assert decisions == []
    assert actions == []


def test_validate_drops_short_decisions_and_actions():
    _, decisions, actions = ai._validate(
        {
            "summary": "A valid summary sentence.",
            "decisions": ["no", "This decision is long enough"],
            "actions": [
                {"title": "x"},
                {"title": "Actually do the thing", "owner": "", "due_date": ""},
                "not a dict",
            ],
        },
        date(2026, 11, 12),
    )
    assert decisions == ["This decision is long enough"]
    assert [a.title for a in actions] == ["Actually do the thing"]


def test_validate_caps_the_number_of_items():
    _, decisions, actions = ai._validate(
        {
            "summary": "A valid summary sentence.",
            "decisions": [f"Decision number {i} is long enough" for i in range(20)],
            "actions": [{"title": f"Action item number {i}"} for i in range(20)],
        },
        date(2026, 11, 12),
    )
    assert len(decisions) == 8
    assert len(actions) == 12


def test_validate_clamps_long_text():
    summary, decisions, actions = ai._validate(
        {
            "summary": "word " * 400,
            "decisions": ["decision " * 200],
            "actions": [{"title": "task " * 200, "owner": "owner " * 100}],
        },
        date(2026, 11, 12),
    )
    assert len(summary) <= 600
    assert len(decisions[0]) <= 450
    assert len(actions[0].title) <= 240
    assert len(actions[0].owner) <= 80


def test_validate_drops_invalid_or_distant_due_dates():
    _, _, actions = ai._validate(
        {
            "summary": "A valid summary sentence.",
            "decisions": [],
            "actions": [
                {"title": "Bad date task", "due_date": "not-a-date"},
                {"title": "Too far away", "due_date": "2035-01-01"},
                {"title": "Fine date", "due_date": "2026-11-20"},
            ],
        },
        date(2026, 11, 12),
    )
    assert [a.due_date for a in actions] == [None, None, date(2026, 11, 20)]


# --- no key, local only ----------------------------------------------------


def test_without_a_key_the_local_extractor_is_used():
    settings = Settings(_env_file=None, anthropic_api_key="")
    result = ai.suggest(settings, make_meeting(), NOTES, "Priya, Arjun")
    assert result.source == "local"
    assert result.model is None
    assert "Local extractor" in result.note
    assert "Ship the beta on 1 December" in result.extraction.decisions
    assert ("Priya", "send the onboarding deck") in [(a.owner, a.title) for a in result.extraction.actions]


def test_a_blank_key_counts_as_no_key():
    settings = Settings(_env_file=None, anthropic_api_key="   ")
    assert not settings.ai_enabled
    assert ai.suggest(settings, make_meeting(), NOTES, "").source == "local"


# --- Claude path ------------------------------------------------------------


def configured(**overrides):
    return Settings(
        _env_file=None,
        anthropic_api_key="test-key-not-real",
        anthropic_model="claude-test-model",
        ai_timeout_seconds=5,
        **overrides,
    )


def test_claude_result_is_validated_and_labelled(fake_http):
    fake_http.response = FakeResponse(claude_payload())
    result = ai.suggest(configured(), make_meeting(), NOTES, "Priya, Arjun")
    assert result.source == "claude"
    assert result.model == "claude-test-model"
    assert result.note == ""
    assert result.extraction.summary == "The team agreed to ship the beta on 1 December."
    assert result.extraction.decisions == ["Ship the beta on 1 December"]
    assert result.extraction.actions[0].owner == "Priya"
    assert result.extraction.actions[0].due_date == date(2026, 11, 13)


def test_claude_request_is_shaped_correctly(fake_http):
    fake_http.response = FakeResponse(claude_payload())
    ai.suggest(configured(), make_meeting(), NOTES, "Priya")
    call = fake_http.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "test-key-not-real"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["json"]["model"] == "claude-test-model"
    assert call["json"]["system"] == ai.SYSTEM
    assert call["json"]["max_tokens"] == 1400
    assert [m["role"] for m in call["json"]["messages"]] == ["user"]
    body = json.loads(call["json"]["messages"][0]["content"])
    assert body["meeting"]["title"] == "Weekly product review"
    assert body["meeting"]["date"] == "2026-11-12"
    assert "Notes" not in body and "notes" in body


def test_claude_result_keeps_local_attendees(fake_http):
    fake_http.response = FakeResponse(
        claude_payload(
            summary="We agreed to ship.",
            decisions=["Ship it"],
            actions=[{"title": "Send the deck", "owner": "Priya", "due_date": ""}],
        )
    )
    result = ai.suggest(configured(), make_meeting(), NOTES, "Priya, Arjun, Meera")
    assert result.extraction.attendees == ["Priya", "Arjun", "Meera"]


def test_code_fenced_json_is_accepted(fake_http):
    inner = {
        "summary": "The team agreed to ship the beta.",
        "decisions": ["Ship the beta on 1 December"],
        "actions": [],
    }
    fenced = "```json\n" + json.dumps(inner) + "\n```"
    fake_http.response = FakeResponse({"content": [{"type": "text", "text": fenced}]})
    result = ai.suggest(configured(), make_meeting(), NOTES, "")
    assert result.source == "claude"
    assert result.extraction.decisions == ["Ship the beta on 1 December"]


# --- fallbacks -------------------------------------------------------------


def fallback(result):
    assert result.source == "local"
    assert "local extractor was used" in result.note.lower()
    assert result.extraction.decisions


def test_bad_json_falls_back_to_local(fake_http):
    fake_http.response = FakeResponse({"content": [{"type": "text", "text": "this is not json"}]})
    fallback(ai.suggest(configured(), make_meeting(), NOTES, ""))


def test_non_json_content_type_falls_back_to_local(fake_http):
    fake_http.response = FakeResponse({"content": []})
    fallback(ai.suggest(configured(), make_meeting(), NOTES, ""))


def test_empty_claude_result_falls_back_to_local(fake_http):
    fake_http.response = FakeResponse(
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"summary": "Too short.", "decisions": [], "actions": []}),
                }
            ]
        }
    )
    fallback(ai.suggest(configured(), make_meeting(), NOTES, ""))


def test_http_error_falls_back_to_local(fake_http):
    fake_http.response = FakeResponse(status=500, payload={"error": "boom"})
    fallback(ai.suggest(configured(), make_meeting(), NOTES, ""))


def test_network_error_falls_back_to_local(fake_http):
    fake_http.response = httpx.ConnectError("no route to host")
    fallback(ai.suggest(configured(), make_meeting(), NOTES, ""))


def test_timeout_error_falls_back_to_local(fake_http):
    fake_http.response = httpx.ReadTimeout("too slow")
    fallback(ai.suggest(configured(), make_meeting(), NOTES, ""))


def test_fallback_still_returns_real_extraction(fake_http):
    fake_http.response = httpx.ConnectError("offline")
    result = ai.suggest(configured(), make_meeting(), NOTES, "Priya")
    assert ("Priya", "send the onboarding deck") in [(a.owner, a.title) for a in result.extraction.actions]
