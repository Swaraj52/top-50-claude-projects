from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from app.models import ActionItem, Decision, Meeting
from conftest import DEFAULT_NOTES, create_meeting, today_local


def rows(app, model):
    with app.state.sessionmaker() as db:
        return list(db.scalars(select(model)))


def test_create_meeting_stores_extracted_memory(browser, app):
    meeting_id = create_meeting(browser)
    with app.state.sessionmaker() as db:
        meeting = db.get(Meeting, meeting_id)
        assert meeting.title == "Weekly product review"
        assert meeting.summary.startswith("We reviewed the beta")
        assert meeting.source == "local"
        assert meeting.extract_note
        decisions = [d.text for d in meeting.decisions]
        assert "Ship the beta on 1 December" in decisions
        actions = {(a.owner, a.title) for a in meeting.actions}
        assert ("Priya", "send the onboarding deck") in actions
        assert ("Arjun", "draft the migration note") in actions


def test_create_meeting_redirects_to_the_detail_page(browser):
    r = browser.post(
        "/meetings",
        {"title": "Design sync", "occurred_on": today_local().isoformat(), "attendees": "Priya", "notes": DEFAULT_NOTES},
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith("/meetings/")
    assert "created=1" in r.headers["location"]


def test_meeting_detail_shows_decisions_owners_and_dates(browser):
    meeting_id = create_meeting(browser)
    page = browser.get(f"/meetings/{meeting_id}").text
    assert "Ship the beta on 1 December" in page
    assert "send the onboarding deck" in page
    assert "Priya" in page
    assert "Local read" in page
    assert "The original notes" in page


def test_create_meeting_rejects_a_short_title(browser, app):
    r = browser.post(
        "/meetings",
        {"title": "ab", "occurred_on": today_local().isoformat(), "attendees": "", "notes": DEFAULT_NOTES},
    )
    assert r.status_code == 422
    assert "title" in r.text.lower()
    assert rows(app, Meeting) == []


def test_create_meeting_rejects_short_notes(browser, app):
    r = browser.post(
        "/meetings",
        {"title": "Design sync", "occurred_on": today_local().isoformat(), "attendees": "", "notes": "too short"},
    )
    assert r.status_code == 422
    assert rows(app, Meeting) == []


def test_create_meeting_rejects_notes_over_the_limit(browser):
    r = browser.post(
        "/meetings",
        {"title": "Design sync", "occurred_on": today_local().isoformat(), "attendees": "", "notes": "x" * 60001},
    )
    assert r.status_code == 422
    assert "60,000" in r.text


def test_create_meeting_requires_csrf(browser, app):
    r = browser.post(
        "/meetings",
        {"title": "Design sync", "occurred_on": today_local().isoformat(), "attendees": "", "notes": DEFAULT_NOTES},
        csrf=False,
    )
    assert r.status_code == 403
    assert rows(app, Meeting) == []


def test_invalid_meeting_date_falls_back_to_today(browser, app):
    r = browser.post(
        "/meetings",
        {"title": "Design sync", "occurred_on": "not-a-date", "attendees": "", "notes": DEFAULT_NOTES},
    )
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        assert db.scalar(select(Meeting)).occurred_on == today_local()


def test_at_mentions_are_added_to_attendees(browser, app):
    notes = "We agreed to ship. @Priya send the deck. @Arjun book the room."
    r = browser.post(
        "/meetings",
        {"title": "Design sync", "occurred_on": today_local().isoformat(), "attendees": "", "notes": notes},
    )
    meeting_id = int(r.headers["location"].split("/meetings/")[1].split("?")[0])
    with app.state.sessionmaker() as db:
        meeting = db.get(Meeting, meeting_id)
        assert "Priya" in meeting.attendees
        assert "Arjun" in meeting.attendees


def test_meetings_list_shows_a_row(browser):
    create_meeting(browser)
    page = browser.get("/meetings").text
    assert "Weekly product review" in page
    assert "2 decisions" in page


def test_meetings_search_matches_title_notes_and_summary(browser):
    create_meeting(browser)
    assert "Weekly product review" in browser.get("/meetings?q=onboarding").text
    assert "Weekly product review" in browser.get("/meetings?q=migration").text
    assert "No meeting matches" in browser.get("/meetings?q=zzzznothing").text


def test_meetings_source_filter(browser):
    create_meeting(browser)
    assert "Weekly product review" in browser.get("/meetings?source=local").text
    assert "Weekly product review" not in browser.get("/meetings?source=claude").text


def test_empty_meetings_page_offers_the_first_capture(make_browser):
    b = make_browser().register()
    page = b.get("/meetings").text
    assert "The archive is empty" in page


def test_unknown_meeting_returns_a_nice_404(browser):
    r = browser.get("/meetings/9999")
    assert r.status_code == 404
    assert "exist" in r.text


def test_edit_updates_the_title_without_touching_memory(browser, app):
    meeting_id = create_meeting(browser)
    r = browser.post(
        f"/meetings/{meeting_id}/edit",
        {"title": "Weekly product review, revised", "occurred_on": today_local().isoformat(), "attendees": "Priya, Arjun", "notes": DEFAULT_NOTES},
    )
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        meeting = db.get(Meeting, meeting_id)
        assert meeting.title == "Weekly product review, revised"
        assert len(meeting.decisions) == 2
        assert len(meeting.actions) == 2


def test_edit_rejects_a_short_title(browser):
    meeting_id = create_meeting(browser)
    r = browser.post(
        f"/meetings/{meeting_id}/edit",
        {"title": "no", "occurred_on": today_local().isoformat(), "attendees": "", "notes": DEFAULT_NOTES},
    )
    assert r.status_code == 422


def test_editing_the_date_moves_the_decisions_with_it(browser, app):
    meeting_id = create_meeting(browser)
    moved = today_local() + timedelta(days=3)
    browser.post(
        f"/meetings/{meeting_id}/edit",
        {"title": "Weekly product review", "occurred_on": moved.isoformat(), "attendees": "Priya, Arjun", "notes": DEFAULT_NOTES},
    )
    with app.state.sessionmaker() as db:
        for decision in db.scalars(select(Decision).where(Decision.meeting_id == meeting_id)):
            assert decision.decided_on == moved


def test_edit_with_reextract_rebuilds_from_the_new_notes(browser, app):
    meeting_id = create_meeting(browser)
    new_notes = """Budget review

Summary: We looked at the quarter.

Decisions:
- Cut the tooling budget

Actions:
- @Meera update the forecast
"""
    r = browser.post(
        f"/meetings/{meeting_id}/edit",
        {"title": "Weekly product review", "occurred_on": today_local().isoformat(), "attendees": "Priya, Meera", "notes": new_notes, "reextract": "1"},
    )
    assert r.status_code == 303
    with app.state.sessionmaker() as db:
        meeting = db.get(Meeting, meeting_id)
        assert [d.text for d in meeting.decisions] == ["Cut the tooling budget"]
        assert [(a.owner, a.title) for a in meeting.actions] == [("Meera", "update the forecast")]


def test_delete_removes_the_meeting_and_its_children(browser, app):
    meeting_id = create_meeting(browser)
    r = browser.post(f"/meetings/{meeting_id}/delete")
    assert r.status_code == 303
    assert r.headers["location"].startswith("/meetings")
    with app.state.sessionmaker() as db:
        assert db.get(Meeting, meeting_id) is None
        assert db.scalar(select(func.count()).select_from(Decision)) == 0
        assert db.scalar(select(func.count()).select_from(ActionItem)) == 0


def test_another_account_cannot_read_edit_or_delete_a_meeting(make_browser, app):
    owner = make_browser().register()
    meeting_id = create_meeting(owner)
    stranger = make_browser().register(email="stranger@example.com", name="Stranger")
    assert stranger.get(f"/meetings/{meeting_id}").status_code == 404
    assert stranger.get(f"/meetings/{meeting_id}/edit").status_code == 404
    assert stranger.post(f"/meetings/{meeting_id}/extract").status_code == 404
    assert stranger.post(f"/meetings/{meeting_id}/delete").status_code == 404
    with app.state.sessionmaker() as db:
        assert db.get(Meeting, meeting_id) is not None


def test_reextract_replaces_manual_additions(browser, app):
    meeting_id = create_meeting(browser)
    browser.post(f"/meetings/{meeting_id}/decisions", {"text": "A manual decision", "status": "agreed"})
    browser.post(f"/meetings/{meeting_id}/extract")
    with app.state.sessionmaker() as db:
        texts = [d.text for d in db.get(Meeting, meeting_id).decisions]
        assert "A manual decision" not in texts
        assert "Ship the beta on 1 December" in texts


def test_html_in_notes_is_escaped(browser):
    notes = "We agreed to ship <script>alert('x')</script> by Friday.\n\nActions:\n- @Priya send the <b>deck</b>"
    r = browser.post(
        "/meetings",
        {"title": "Escaping test", "occurred_on": today_local().isoformat(), "attendees": "", "notes": notes},
    )
    meeting_id = int(r.headers["location"].split("/meetings/")[1].split("?")[0])
    page = browser.get(f"/meetings/{meeting_id}").text
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "<b>deck</b>" not in page


def test_dashboard_counts_open_overdue_and_soon(browser):
    create_meeting(browser)
    page = browser.get("/").text
    assert "Open follow-ups" in page
    assert 'stat-value">2<' in page
    assert "send the onboarding deck" in page
    assert "Weekly product review" in page


def test_seventh_capture_in_the_window_uses_the_local_limiter_note(browser, app):
    for index in range(6):
        create_meeting(browser, title=f"Meeting {index}")
    meeting_id = create_meeting(browser, title="Meeting six")
    with app.state.sessionmaker() as db:
        assert "limit" in db.get(Meeting, meeting_id).extract_note.lower()
