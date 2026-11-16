from __future__ import annotations

import httpx
import pytest

from app.services import ai
from app.services.ask import Answer, Citation
from app.services.search import Hit


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            raise httpx.HTTPStatusError("boom", request=request, response=httpx.Response(self.status_code))

    def json(self):
        return self._payload


def message(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def local_answer() -> Answer:
    return Answer(
        text="Local answer text with a quote.",
        citations=[Citation(item_id=1, title="Pricing review", sentence="We agreed.", kind="note")],
        source="local",
        note="Local extractive answer.",
        read=1,
    )


def hit() -> Hit:
    from datetime import datetime, timezone

    from app.models import Item

    item = Item(
        id=1,
        user_id=1,
        title="Pricing review",
        body="We agreed the Starter plan keeps its price until January.",
        tags="pricing",
        kind="note",
        created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        origin="written",
    )
    return Hit(item, 1.0, ["pricing"], "snippet")


def test_upgrade_without_a_key_returns_the_local_answer(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("no HTTP call should happen without a key")

    monkeypatch.setattr(ai.httpx, "post", Boom)
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="")
    answer, note = ai.upgrade(settings, "pricing?", local_answer(), [hit()])
    assert answer.source == "local"
    assert note == "Local extractive answer."


def test_upgrade_without_citations_returns_local(monkeypatch):
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="k")
    empty = Answer(text="nothing", citations=[], source="local", note="No passage was read.", read=0)
    answer, note = ai.upgrade(settings, "q", empty, [])
    assert answer is empty
    assert note == "No passage was read."


def test_upgrade_uses_claude_and_keeps_citations(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(message('{"answer": "The Starter plan keeps its price until January."}'))

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="secret-key", anthropic_model="claude-test")
    answer, note = ai.upgrade(settings, "What happens to pricing?", local_answer(), [hit()])
    assert answer.source == "claude"
    assert answer.text == "The Starter plan keeps its price until January."
    assert len(answer.citations) == 1
    assert answer.read == 1
    assert "Claude wrote this answer" in answer.note
    assert note == ""
    assert calls[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert calls[0]["headers"]["x-api-key"] == "secret-key"
    assert calls[0]["headers"]["anthropic-version"] == "2023-06-01"
    assert calls[0]["json"]["model"] == "claude-test"
    prompt = calls[0]["json"]["messages"][0]["content"]
    assert "What happens to pricing?" in prompt
    assert "Pricing review" in prompt
    assert '{"answer": "..."}' in prompt


def test_upgrade_accepts_a_fenced_json_object(monkeypatch):
    monkeypatch.setattr(
        ai.httpx,
        "post",
        lambda *a, **k: FakeResponse(message('```json\n{"answer": "A fenced answer that is long enough."}\n```')),
    )
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="k")
    answer, note = ai.upgrade(settings, "q", local_answer(), [hit()])
    assert answer.source == "claude"
    assert "fenced" in answer.text


@pytest.mark.parametrize(
    "payload",
    [
        message("not json at all"),
        message("[]"),
        message('{"answer": 5}'),
        message('{"answer": "too short"}'),
        message('{"answer": "' + "x" * 1601 + '"}'),
        message("{}"),
        {"content": []},
    ],
)
def test_upgrade_falls_back_on_a_bad_result(monkeypatch, payload):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: FakeResponse(payload))
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="k")
    answer, note = ai.upgrade(settings, "q", local_answer(), [hit()])
    assert answer.source == "local"
    assert note == ai.FALLBACK_NOTE


def test_upgrade_falls_back_on_http_and_network_errors(monkeypatch):
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="k")

    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: FakeResponse({}, status_code=500))
    answer, note = ai.upgrade(settings, "q", local_answer(), [hit()])
    assert answer.source == "local"
    assert note == ai.FALLBACK_NOTE

    def timeout(*a, **k):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(ai.httpx, "post", timeout)
    answer, note = ai.upgrade(settings, "q", local_answer(), [hit()])
    assert answer.source == "local"
    assert note == ai.FALLBACK_NOTE


def test_answer_text_clamps_and_cleans():
    raw = "  one   two  " + "three four " * 4
    assert ai._answer_text(raw) == ("one two " + "three four " * 4).strip()
    with pytest.raises(ValueError):
        ai._answer_text("short")
    with pytest.raises(ValueError):
        ai._answer_text(12)
    with pytest.raises(ValueError):
        ai._answer_text("x" * 1601)


def test_ask_route_labels_a_claude_answer(app, make_browser, monkeypatch):
    monkeypatch.setattr(
        ai.httpx,
        "post",
        lambda *a, **k: FakeResponse(message('{"answer": "The pricing review happens in January."}')),
    )
    app.state.settings.anthropic_api_key = "test-key"
    app.state.ai_limiter = type("L", (), {"blocked": lambda self, key: False, "hit": lambda self, key: None})()

    b = make_browser().register(email="ai@example.com")
    from conftest import add_item

    add_item(b, title="Pricing review", body="We agreed the pricing review happens in January this year.")
    r = b.post("/ask", {"q": "when is the pricing review"})
    assert "Claude" in r.text
    assert "The pricing review happens in January." in r.text
    assert "answer-claude" in r.text
    assert "citations" in r.text.lower()


def test_ask_route_falls_back_when_claude_fails(app, make_browser, monkeypatch):
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: FakeResponse(message("nonsense")))
    app.state.settings.anthropic_api_key = "test-key"
    app.state.ai_limiter = type("L", (), {"blocked": lambda self, key: False, "hit": lambda self, key: None})()

    b = make_browser().register(email="fail@example.com")
    from conftest import add_item

    add_item(b, title="Pricing review", body="We agreed the pricing review happens in January this year.")
    r = b.post("/ask", {"q": "when is the pricing review"})
    assert "Local extract" in r.text
    assert ai.FALLBACK_NOTE in r.text


def test_ai_rate_limit_note(app, make_browser):
    app.state.settings.anthropic_api_key = "test-key"
    app.state.ai_limiter = type("L", (), {"blocked": lambda self, key: True, "hit": lambda self, key: None})()

    b = make_browser().register(email="limit@example.com")
    from conftest import add_item

    add_item(b, title="Pricing review", body="We agreed the pricing review happens in January this year.")
    r = b.post("/ask", {"q": "when is the pricing review"})
    assert "rate limit reached" in r.text
    assert "Local extract" in r.text


def test_prompt_contains_no_more_than_four_passages(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["prompt"] = json["messages"][0]["content"]
        return FakeResponse(message('{"answer": "A valid answer with enough characters to pass."}'))

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    from app.config import Settings

    settings = Settings(_env_file=None, anthropic_api_key="k")
    from datetime import datetime, timezone

    from app.models import Item

    hits = []
    for index in range(1, 8):
        item = Item(
            id=index,
            user_id=1,
            title=f"Item {index}",
            body=f"Body text for item {index}.",
            tags="",
            kind="note",
            created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            origin="written",
        )
        hits.append(Hit(item, 1.0, [], ""))
    ai.upgrade(settings, "q", local_answer(), hits)
    assert "Item 4" in seen["prompt"]
    assert "Item 5" not in seen["prompt"]
