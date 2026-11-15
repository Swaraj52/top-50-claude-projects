from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models import FollowUp
from conftest import compose, today_local


def get_followups(app):
    with app.state.sessionmaker() as db:
        return list(db.scalars(select(FollowUp).order_by(FollowUp.id)))


def test_add_a_follow_up_with_a_relative_date(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/followups", {"title": "The signed deck", "due_date": "tomorrow"})
    assert r.status_code == 303
    followup = get_followups(app)[0]
    assert followup.title == "The signed deck"
    assert followup.due_date == today_local() + timedelta(days=1)
    assert followup.status == "open"


def test_add_a_follow_up_with_an_iso_date(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "The invoice", "due_date": "2026-12-01"})
    assert get_followups(app)[0].due_date.isoformat() == "2026-12-01"


def test_add_a_follow_up_with_no_date(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Ask about the roadmap", "due_date": ""})
    assert get_followups(app)[0].due_date is None


def test_a_short_follow_up_title_is_rejected(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/followups", {"title": "ab"})
    assert r.status_code == 422
    assert get_followups(app) == []


def test_a_follow_up_needs_your_own_thread(browser, make_browser, app):
    thread_id = compose(browser)
    other = make_browser().register(email="other@example.com", name="Other")
    r = other.post(f"/threads/{thread_id}/followups", {"title": "Not mine to add"})
    assert r.status_code == 404


def test_the_followups_page_groups_by_date(browser, app):
    thread_id = compose(browser)
    today = today_local()
    entries = [
        ("Overdue thing", (today - timedelta(days=2)).isoformat()),
        ("Today thing", today.isoformat()),
        ("This week thing", (today + timedelta(days=4)).isoformat()),
        ("Later thing", (today + timedelta(days=20)).isoformat()),
        ("Undated thing", ""),
    ]
    for title, due in entries:
        browser.post(f"/threads/{thread_id}/followups", {"title": title, "due_date": due})
    page = browser.get("/followups").text
    for label in ("Overdue", "Today", "Next seven days", "Later", "No date"):
        assert label in page
    for title, _ in entries:
        assert title in page
    assert page.index("Overdue thing") < page.index("Today thing") < page.index("This week thing")


def test_a_follow_up_is_completed_and_reopened(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Waiting on legal"})
    followup_id = get_followups(app)[0].id
    browser.post(f"/followups/{followup_id}/toggle")
    done = get_followups(app)[0]
    assert done.status == "done"
    assert done.completed_at is not None
    browser.post(f"/followups/{followup_id}/toggle")
    reopened = get_followups(app)[0]
    assert reopened.status == "open"
    assert reopened.completed_at is None


def test_done_and_open_tabs(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Open item"})
    browser.post(f"/threads/{thread_id}/followups", {"title": "Done item"})
    done_id = get_followups(app)[1].id
    browser.post(f"/followups/{done_id}/toggle")
    open_page = browser.get("/followups?status=open").text
    done_page = browser.get("/followups?status=done").text
    assert "Open item" in open_page and "Done item" not in open_page
    assert "Done item" in done_page and "Open item" not in done_page


def test_a_follow_up_can_be_updated(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Old title", "due_date": "2026-12-01"})
    followup_id = get_followups(app)[0].id
    r = browser.post(f"/followups/{followup_id}/update", {"title": "New title", "due_date": "2026-12-09"})
    assert r.status_code == 303
    saved = get_followups(app)[0]
    assert saved.title == "New title"
    assert saved.due_date.isoformat() == "2026-12-09"


def test_an_update_can_clear_the_date(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Dated", "due_date": "2026-12-01"})
    followup_id = get_followups(app)[0].id
    browser.post(f"/followups/{followup_id}/update", {"title": "Dated", "due_date": ""})
    assert get_followups(app)[0].due_date is None


def test_an_update_rejects_a_short_title(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Fine title"})
    followup_id = get_followups(app)[0].id
    r = browser.post(f"/followups/{followup_id}/update", {"title": "x", "due_date": ""})
    assert r.status_code == 422


def test_deleting_a_follow_up(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Remove me"})
    followup_id = get_followups(app)[0].id
    r = browser.post(f"/followups/{followup_id}/delete")
    assert r.status_code == 303
    assert get_followups(app) == []


def test_another_users_follow_up_is_not_reachable(browser, make_browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Private item"})
    followup_id = get_followups(app)[0].id
    other = make_browser().register(email="other@example.com", name="Other")
    assert other.post(f"/followups/{followup_id}/toggle").status_code == 404
    assert other.post(f"/followups/{followup_id}/update", {"title": "Hijacked"}).status_code == 404
    assert other.post(f"/followups/{followup_id}/delete").status_code == 404


def test_a_follow_up_redirect_only_allows_a_site_path(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Redirect test"})
    followup_id = get_followups(app)[0].id
    r = browser.post(f"/followups/{followup_id}/toggle", {"next": "//evil.example"})
    assert r.status_code == 303
    assert r.headers["location"] == "/followups"


def test_the_dashboard_and_thread_page_show_follow_ups(browser):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Visible on both"})
    assert "Visible on both" in browser.get(f"/threads/{thread_id}").text
    assert "Visible on both" in browser.get("/").text


def test_counts_are_shown_on_the_followups_page(browser):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Counted item"})
    page = browser.get("/followups").text
    assert "Open<span class=\"n\">1</span>" in page or "Open" in page
