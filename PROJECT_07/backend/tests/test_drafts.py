from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.models import Draft, Message, Thread
from app.services import ai
from conftest import compose


class FakeResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {"content": [{"type": "text", "text": self._text}]}


def enable_claude(app, key="test-key"):
    app.state.settings.anthropic_api_key = key


def get_drafts(app, thread_id=None):
    with app.state.sessionmaker() as db:
        query = select(Draft).order_by(Draft.id)
        if thread_id is not None:
            query = query.where(Draft.thread_id == thread_id)
        return list(db.scalars(query))


def get_thread(app, thread_id):
    with app.state.sessionmaker() as db:
        return db.get(Thread, thread_id)


def test_draft_route_creates_a_local_scaffold(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    assert r.status_code == 303
    drafts = get_drafts(app, thread_id)
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.status == "draft"
    assert draft.source == "local"
    assert draft.tone == "warm"
    assert draft.subject.startswith("Re: ")
    assert "You asked:" in draft.body
    assert "no model call" not in draft.note  # the note says it is a scaffold, not a summary
    assert "template" in draft.note


@pytest.mark.parametrize("tone", ["warm", "brief", "formal"])
def test_each_tone_is_stored(browser, app, tone):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": tone, "engine": "local"})
    assert get_drafts(app, thread_id)[-1].tone == tone


def test_an_unknown_tone_falls_back_to_warm(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "shouty", "engine": "local"})
    assert get_drafts(app, thread_id)[-1].tone == "warm"


def test_claude_without_a_key_falls_back_to_local(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "claude"})
    draft = get_drafts(app, thread_id)[-1]
    assert draft.source == "local"
    assert "template" in draft.note


def test_claude_success_is_used_and_labelled(browser, app, monkeypatch):
    enable_claude(app)
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["payload"] = json
        return FakeResponse('{"subject": "Re: Q4 launch", "body": "Hi Priya,\\n\\nI will send the numbers today.\\n\\nSwayam"}')

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "claude"})
    draft = get_drafts(app, thread_id)[-1]
    assert draft.source == "claude"
    assert draft.body.startswith("Hi Priya")
    assert draft.note == ""
    assert seen["url"].endswith("/v1/messages")
    assert seen["headers"]["x-api-key"] == "test-key"
    prompt = seen["payload"]["messages"][0]["content"]
    assert "Could you review the pricing section" in prompt
    assert "warm" in prompt
    assert "Swayam" in prompt


def test_a_claude_failure_falls_back_with_an_honest_note(browser, app, monkeypatch):
    enable_claude(app)

    def boom(*args, **kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(ai.httpx, "post", boom)
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "claude"})
    draft = get_drafts(app, thread_id)[-1]
    assert draft.source == "local"
    assert "Claude was unavailable" in draft.note


def test_the_drafter_is_rate_limited(browser, app, monkeypatch):
    enable_claude(app)
    monkeypatch.setattr(
        ai.httpx,
        "post",
        lambda *a, **k: FakeResponse('{"subject": "Re: x", "body": "A perfectly valid reply body for the test."}'),
    )
    thread_id = compose(browser)
    for _ in range(8):
        browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "claude"})
    blocked = browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "claude"})
    assert blocked.status_code == 429
    assert len(get_drafts(app, thread_id)) == 8


def test_a_draft_can_be_edited(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    r = browser.post(f"/drafts/{draft.id}", {"subject": "Re: Revised", "body": "A shorter reply."})
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        saved = db.get(Draft, draft.id)
        assert saved.subject == "Re: Revised"
        assert saved.body == "A shorter reply."


def test_a_draft_edit_validates_the_subject(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    r = browser.post(f"/drafts/{draft.id}", {"subject": "x", "body": "Body stays."})
    assert r.status_code == 422


def test_a_draft_edit_validates_the_body(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    r = browser.post(f"/drafts/{draft.id}", {"subject": "Re: Fine", "body": ""})
    assert r.status_code == 422


def test_marking_sent_records_an_outbound_message_and_waits(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    browser.post(f"/drafts/{draft.id}", {"subject": "Re: Q4 launch", "body": "Here are the numbers."})
    r = browser.post(f"/drafts/{draft.id}/send")
    assert r.status_code == 303

    with app.state.sessionmaker() as db:
        saved = db.get(Draft, draft.id)
        thread = db.get(Thread, thread_id)
        out = [m for m in thread.messages if m.direction == "out"]
        assert saved.status == "sent"
        assert "does not send email" in saved.note
        assert len(out) == 1
        assert out[0].body == "Here are the numbers."
        assert thread.status == "waiting"
        assert thread.category == "waiting"
        assert thread.unread is False


def test_a_sent_draft_cannot_be_sent_twice(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    browser.post(f"/drafts/{draft.id}/send")
    r = browser.post(f"/drafts/{draft.id}/send")
    assert r.status_code == 409
    from sqlalchemy import func, select as sql_select

    with app.state.sessionmaker() as db:
        outbound = db.scalar(
            sql_select(func.count(Message.id)).where(Message.thread_id == thread_id, Message.direction == "out")
        )
    assert outbound == 1


def test_a_sent_draft_cannot_be_edited(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    browser.post(f"/drafts/{draft.id}/send")
    r = browser.post(f"/drafts/{draft.id}", {"subject": "Re: New", "body": "Rewrite."})
    assert r.status_code == 409


def test_deleting_a_draft_keeps_the_thread(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    r = browser.post(f"/drafts/{draft.id}/delete")
    assert r.status_code == 303
    assert get_drafts(app, thread_id) == []
    assert get_thread(app, thread_id) is not None


def test_another_users_draft_is_not_reachable(browser, make_browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    other = make_browser().register(email="other@example.com", name="Other")
    assert other.post(f"/drafts/{draft.id}/send").status_code == 404
    assert other.post(f"/drafts/{draft.id}").status_code == 404
    assert other.post(f"/drafts/{draft.id}/delete").status_code == 404


def test_drafts_page_shows_open_and_sent(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "brief", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    page = browser.get("/drafts").text
    assert draft.subject in page
    assert "Mark sent" in page

    browser.post(f"/drafts/{draft.id}/send")
    assert draft.subject in browser.get("/drafts?status=sent").text
    assert draft.subject not in browser.get("/drafts?status=draft").text


def test_the_thread_page_lists_drafts_and_marks_them(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/draft", {"tone": "warm", "engine": "local"})
    draft = get_drafts(app, thread_id)[-1]
    page = browser.get(f"/threads/{thread_id}").text
    assert draft.subject in page
    assert "Mark sent" in page
    assert "Copy text" in page
    browser.post(f"/drafts/{draft.id}/send")
    after = browser.get(f"/threads/{thread_id}").text
    assert "Sent from here (1)" in after
    assert "marked sent" in after
