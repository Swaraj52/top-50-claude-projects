from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.services import ai


class FakeResponse:
    def __init__(self, text, status=200):
        self._text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=httpx.Request("POST", "https://x"), response=self)

    def json(self):
        return {"content": [{"type": "text", "text": self._text}]}


def settings(key="test-key"):
    return SimpleNamespace(
        anthropic_api_key=key,
        anthropic_model="claude-test",
        anthropic_timeout=20,
        ai_timeout_seconds=20,
        ai_enabled=bool(key),
    )


def message(direction="in", sender="Priya <priya@lumen.example>", body="Could you confirm by Friday?", hours=1):
    return SimpleNamespace(
        direction=direction,
        sender=sender,
        body=body,
        received_at=datetime.now(timezone.utc) - timedelta(hours=hours),
    )


def thread(messages=None, subject="Q4 launch", participants="Priya"):
    return SimpleNamespace(
        subject=subject,
        participants=participants,
        messages=messages or [message()],
    )


def user():
    return SimpleNamespace(name="Swayam", signature="Product lead, Lumen Labs")


def payload(text):
    return FakeResponse(text)


def test_no_key_uses_the_local_summary_with_a_note():
    got, source, note = ai.summarise(settings(""), thread(), thread().messages)
    assert source == "local"
    assert "Confirm" in got or "confirm" in got
    assert "no model call" in note


def test_no_key_uses_the_local_draft_with_a_note():
    got, source, note = ai.draft(settings(""), thread(), thread().messages, user())
    assert source == "local"
    assert "Hi Priya" in got.body
    assert "template" in note


def test_a_valid_claude_summary_is_used(monkeypatch):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: payload('{"summary": "Priya needs the numbers by Friday."}'))
    got, source, note = ai.summarise(settings(), thread(), thread().messages)
    assert got == "Priya needs the numbers by Friday."
    assert source == "claude"
    assert note == ""


def test_code_fences_are_tolerated(monkeypatch):
    monkeypatch.setattr(
        ai.httpx, "post", lambda *a, **k: payload("```json\n{\"summary\": \"A wrapped but valid summary.\"}\n```")
    )
    got, source, _ = ai.summarise(settings(), thread(), thread().messages)
    assert got == "A wrapped but valid summary."
    assert source == "claude"


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "[]",
        '{"summary": 42}',
        '{"summary": "short"}',
        '{"summary": "' + "x" * 900 + '"}',
        '{"other": "field"}',
    ],
)
def test_an_invalid_summary_falls_back(monkeypatch, raw):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: payload(raw))
    got, source, note = ai.summarise(settings(), thread(), thread().messages)
    assert source == "local"
    assert "Claude was unavailable" in note


def test_an_http_error_falls_back(monkeypatch):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: FakeResponse("nope", 503))
    _, source, note = ai.summarise(settings(), thread(), thread().messages)
    assert source == "local"
    assert "invalid result" in note


def test_a_network_error_falls_back(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(ai.httpx, "post", boom)
    _, source, _ = ai.summarise(settings(), thread(), thread().messages)
    assert source == "local"


def test_the_summary_request_has_the_expected_shape(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["body"] = json
        seen["timeout"] = timeout
        return payload('{"summary": "A valid summary of the thread."}')

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    ai.summarise(settings(), thread(), thread().messages)
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["anthropic-version"]
    assert seen["body"]["model"] == "claude-test"
    assert seen["body"]["max_tokens"] == 700
    assert seen["body"]["system"].startswith("You help one person triage")
    assert "Could you confirm by Friday?" in seen["body"]["messages"][0]["content"]
    assert seen["timeout"] == 20


def test_the_draft_request_includes_the_signature(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["body"] = json
        return payload('{"subject": "Re: Q4 launch", "body": "Hi Priya, here are the numbers.\\n\\nSwayam\\nProduct lead"}')

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    got, source, _ = ai.draft(settings(), thread(), thread().messages, user(), "formal")
    assert source == "claude"
    assert got.subject == "Re: Q4 launch"
    assert "\n" in got.body
    prompt = seen["body"]["messages"][0]["content"]
    assert "formal" in prompt
    assert "Product lead, Lumen Labs" in prompt


@pytest.mark.parametrize(
    "raw",
    [
        '{"subject": "Re: x", "body": "short"}',
        '{"subject": "x", "body": "A perfectly fine body that passes the length check."}',
        '{"subject": "Re: x", "body": 12}',
        '{"body": "A perfectly fine body that passes the length check."}',
        "[]",
    ],
)
def test_an_invalid_draft_falls_back(monkeypatch, raw):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: payload(raw))
    got, source, note = ai.draft(settings(), thread(), thread().messages, user())
    assert source == "local"
    assert "template" not in note
    assert "Claude was unavailable" in note


def test_the_transcript_keeps_only_the_last_six_messages(monkeypatch):
    seen = {}
    messages = [message(body=f"Message number {i}" + " filler" * 40, hours=i) for i in range(10)]

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["body"] = json
        return payload('{"summary": "A valid summary of the thread."}')

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    ai.summarise(settings(), thread(messages), messages)
    prompt = seen["body"]["messages"][0]["content"]
    assert "Message number 9" in prompt
    assert "Message number 3" not in prompt


def test_the_transcript_is_bounded(monkeypatch):
    seen = {}
    messages = [message(body="z" * 3000, hours=i) for i in range(6)]

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["body"] = json
        return payload('{"summary": "A valid summary of the thread."}')

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    ai.summarise(settings(), thread(messages), messages)
    prompt = seen["body"]["messages"][0]["content"]
    assert len(prompt) < 7000


def test_a_summary_is_whitespace_normalised(monkeypatch):
    monkeypatch.setattr(
        ai.httpx, "post", lambda *a, **k: payload('{"summary": "Line one.\\nLine   two."}')
    )
    got, source, _ = ai.summarise(settings(), thread(), thread().messages)
    assert got == "Line one. Line two."
    assert source == "claude"


def test_a_fallback_does_not_claim_claude_was_used(monkeypatch):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: payload("garbage"))
    got, source, note = ai.summarise(settings(), thread(), thread().messages)
    assert source == "local"
    assert "Claude" in note
    assert "local writer" in note
