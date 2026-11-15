from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Mailbox, Message, Thread, User
from conftest import compose, make_eml


def threads_of(app, email="swayam@example.com"):
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        return list(db.scalars(select(Thread).where(Thread.user_id == uid).order_by(Thread.id)))


def messages_of(app, thread_id):
    with app.state.sessionmaker() as db:
        return list(db.scalars(select(Message).where(Message.thread_id == thread_id).order_by(Message.id)))


def test_compose_creates_a_routed_thread(browser, app):
    thread_id = compose(browser)
    rows = threads_of(app)
    assert len(rows) == 1
    thread = rows[0]
    assert thread.id == thread_id
    assert thread.subject == "Q4 launch checklist"
    assert thread.category == "reply"
    assert thread.category_source == "rules"
    assert thread.status == "open"
    assert thread.unread is True
    assert "review the pricing" in thread.summary.lower()
    assert "Priya Raman" in thread.participants

    page = browser.get(f"/threads/{thread_id}?imported=1")
    assert page.status_code == 200
    assert "review the pricing" in page.text
    assert "Logged." in page.text
    assert "Needs a reply" in page.text


def test_opening_a_thread_clears_unread(browser, app):
    thread_id = compose(browser)
    browser.get(f"/threads/{thread_id}")
    with app.state.sessionmaker() as db:
        assert db.get(Thread, thread_id).unread is False


def test_a_new_message_makes_the_thread_unread_again(browser, app):
    thread_id = compose(browser, subject="Same subject")
    browser.get(f"/threads/{thread_id}")
    compose(browser, subject="Re: Same subject", body="One more thing: can you confirm by Monday?")
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert thread.unread is True
        assert len(thread.messages) == 2


def test_reply_prefixes_thread_together(browser, app):
    first = compose(browser, subject="Q4 launch checklist")
    second = compose(browser, subject="RE: Re: Q4 launch checklist", body="Adding one detail.")
    assert first == second
    assert len(messages_of(app, first)) == 2


def test_a_different_case_and_spacing_still_threads(browser, app):
    first = compose(browser, subject="Q4 Launch Checklist")
    second = compose(browser, subject="  fwd: q4   launch   checklist ", body="More.")
    assert first == second


def test_a_closed_thread_starts_a_new_thread(browser, app):
    first = compose(browser)
    browser.post(f"/threads/{first}/status", {"status": "closed", "next": f"/threads/{first}"})
    second = compose(browser, subject="Q4 launch checklist", body="Starting again.")
    assert second != first
    assert len(threads_of(app)) == 2


def test_threading_is_scoped_to_the_mailbox(browser, app):
    first = compose(browser)
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == "swayam@example.com"))
        other = Mailbox(user_id=uid, name="Work", address="work@example.com")
        db.add(other)
        db.commit()
        other_id = other.id
    second = compose(browser, subject="Q4 launch checklist", mailbox_id=str(other_id), body="Same subject, other box.")
    assert second != first
    assert len(threads_of(app)) == 2


def test_compose_requires_a_sender(browser, app):
    browser.get("/compose")
    r = browser.post("/compose", {"sender": "", "subject": "No sender", "body": "Hello"})
    assert r.status_code == 200
    assert "Add the sender" in r.text
    assert threads_of(app) == []


def test_compose_requires_an_at_sign(browser, app):
    browser.get("/compose")
    r = browser.post("/compose", {"sender": "Priya Raman", "subject": "No address", "body": "Hello"})
    assert r.status_code == 200
    assert "Add the sender" in r.text


def test_compose_requires_a_body(browser, app):
    browser.get("/compose")
    r = browser.post("/compose", {"sender": "a@b.example", "subject": "Empty", "body": "   "})
    assert r.status_code == 200
    assert "Paste the message body" in r.text


def test_compose_rejects_an_oversized_body(browser, app):
    browser.get("/compose")
    r = browser.post("/compose", {"sender": "a@b.example", "subject": "Huge", "body": "x" * 60_001})
    assert r.status_code == 200
    assert "too long" in r.text


def test_compose_accepts_an_empty_subject(browser, app):
    thread_id = compose(browser, subject="")
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert thread.subject == "(no subject)"


def test_compose_uses_a_pasted_time_in_the_users_zone(browser, app):
    thread_id = compose(browser, received_at="2026-11-10T09:00")
    message = messages_of(app, thread_id)[0]
    assert message.received_at == datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc)


def test_compose_ignores_another_users_mailbox(browser, make_browser, app):
    other = make_browser().register(email="other@example.com", name="Other")
    other.get("/compose")
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == "other@example.com"))
        box_id = db.scalar(select(Mailbox.id).where(Mailbox.user_id == uid))
    thread_id = compose(browser, mailbox_id=str(box_id))
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert thread.mailbox.address == "swayam@example.com"


def test_compose_uploads_an_eml_file(browser, app):
    browser.get("/compose")
    r = browser.post(
        "/compose",
        {"sender": "", "subject": "", "body": ""},
        files={"file": ("mail.eml", make_eml(subject="From a file"), "message/rfc822")},
    )
    assert r.status_code == 303
    thread_id = int(r.headers["location"].split("/threads/")[1].split("?")[0])
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert thread.subject == "From a file"
        assert thread.category == "reply"
        message = thread.messages[0]
        assert message.external_id == "eml-1@lumen.example"
        assert "real .eml file" in message.body


def test_the_same_eml_message_id_is_imported_once(browser, app):
    raw = make_eml(subject="Duplicate guard", message_id="<same@lumen.example>")
    browser.get("/compose")
    first = browser.post("/compose", {"sender": "", "subject": "", "body": ""}, files={"file": ("a.eml", raw)})
    second = browser.post("/compose", {"sender": "", "subject": "", "body": ""}, files={"file": ("b.eml", raw)})
    first_id = int(first.headers["location"].split("/threads/")[1].split("?")[0])
    second_id = int(second.headers["location"].split("/threads/")[1].split("?")[0])
    assert first_id == second_id
    assert len(messages_of(app, first_id)) == 1


def test_an_oversized_eml_is_rejected(browser, app):
    browser.get("/compose")
    r = browser.post(
        "/compose",
        {"sender": "", "subject": "", "body": ""},
        files={"file": ("big.eml", b"a" * 2_000_001)},
    )
    assert r.status_code == 200
    assert "2 MB maximum" in r.text
    assert threads_of(app) == []


def test_an_eml_without_a_body_is_rejected(browser, app):
    raw = b"From: a@b.example\r\nSubject: Empty\r\nContent-Type: text/plain\r\n\r\n"
    browser.get("/compose")
    r = browser.post("/compose", {"sender": "", "subject": "", "body": ""}, files={"file": ("e.eml", raw)})
    assert r.status_code == 200
    assert "Paste the message body" in r.text


def test_a_manual_route_survives_a_new_inbound_message(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/category", {"category": "fyi", "next": f"/threads/{thread_id}"})
    compose(browser, subject="Q4 launch checklist", body="One more thought.")
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert thread.category == "fyi"
        assert thread.category_source == "you"


def test_message_text_is_escaped_in_the_page(browser):
    thread_id = compose(browser, body="<script>alert('x')</script> Can you confirm?")
    page = browser.get(f"/threads/{thread_id}").text
    assert "<script>alert('x')</script>" not in page
    assert "&lt;script&gt;" in page


def test_participants_include_names_from_recipients(browser, app):
    thread_id = compose(
        browser,
        sender="Priya Raman <priya@lumen.example>",
        recipients="Swayam Naik <swayam@example.com>, Arjun Mehta <arjun@acme.example>",
    )
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert "Priya Raman" in thread.participants
        assert "Arjun Mehta" in thread.participants


def test_compose_creates_a_mailbox_when_none_exists(browser, app):
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == "swayam@example.com"))
        for box in db.scalars(select(Mailbox).where(Mailbox.user_id == uid)):
            db.delete(box)
        db.commit()
    thread_id = compose(browser, mailbox_id="0")
    with app.state.sessionmaker() as db:
        thread = db.get(Thread, thread_id)
        assert thread.mailbox is not None
        assert thread.mailbox.name == "Personal"
