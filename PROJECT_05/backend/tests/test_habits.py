from __future__ import annotations

from datetime import timedelta

from tests.conftest import create_habit, log_day, today_local


def test_create_habit_redirects_to_detail(browser):
    habit_id = create_habit(browser, title="Morning walk", days=["0", "2", "4"], cue="After brushing my teeth")
    page = browser.get(f"/habits/{habit_id}")
    assert page.status_code == 200
    assert "Morning walk" in page.text
    assert "After brushing my teeth" in page.text
    assert "Mon · Wed · Fri" in page.text


def test_create_habit_requires_a_day(browser):
    r = browser.post("/habits", {"title": "Read", "days": [], "cue": "", "intention": ""})
    assert r.status_code == 422
    assert "Choose at least one day" in r.text


def test_create_habit_rejects_short_title(browser):
    r = browser.post("/habits", {"title": "a", "days": ["0"], "cue": "", "intention": ""})
    assert r.status_code == 422
    assert "Please add a habit" in r.text


def test_create_habit_trims_whitespace(browser):
    habit_id = create_habit(browser, title="  Evening   journal  ")
    page = browser.get(f"/habits/{habit_id}")
    assert "Evening journal" in page.text


def test_edit_habit(browser):
    habit_id = create_habit(browser, title="Read", days=["0"])
    r = browser.post(
        f"/habits/{habit_id}/update",
        {"title": "Read 10 pages", "days": ["1", "3"], "cue": "After lunch", "intention": "Keep the thread."},
    )
    assert r.status_code == 303
    page = browser.get(f"/habits/{habit_id}")
    assert "Read 10 pages" in page.text
    assert "Tue · Thu" in page.text
    assert "After lunch" in page.text


def test_pause_and_resume_habit(browser):
    habit_id = create_habit(browser)
    browser.post(f"/habits/{habit_id}/status", {"status": "paused"})
    assert "Paused" in browser.get(f"/habits/{habit_id}").text
    browser.post(f"/habits/{habit_id}/status", {"status": "active"})
    page = browser.get(f"/habits/{habit_id}")
    assert "Active" in page.text


def test_archive_habit(browser):
    habit_id = create_habit(browser)
    browser.post(f"/habits/{habit_id}/status", {"status": "archived"})
    page = browser.get("/habits?status=archived")
    assert "Read 20 minutes" in page.text
    assert "Archived" in page.text


def test_delete_habit(browser):
    habit_id = create_habit(browser)
    r = browser.post(f"/habits/{habit_id}/delete")
    assert r.status_code == 303
    assert browser.get(f"/habits/{habit_id}").status_code == 404


def test_habit_belongs_to_its_owner(make_browser):
    owner = make_browser().register(email="owner@example.com")
    habit_id = create_habit(owner, title="Private habit")
    other = make_browser().register(email="other@example.com")
    assert other.get(f"/habits/{habit_id}").status_code == 404


def test_dashboard_lists_todays_habit(browser):
    create_habit(browser, title="Read 20 minutes", days=[str(today_local().weekday())])
    page = browser.get("/")
    assert "Read 20 minutes" in page.text
    assert "0-day streak" in page.text


def test_log_today_done(browser):
    habit_id = create_habit(browser)
    r = log_day(browser, habit_id, today_local(), "done")
    assert r.status_code == 303
    page = browser.get("/")
    assert "Done" in page.text
    assert "1-day streak" in page.text


def test_log_today_as_planned_rest(browser):
    habit_id = create_habit(browser)
    log_day(browser, habit_id, today_local(), "skipped")
    page = browser.get("/")
    assert "Rest" in page.text
    assert "Did it" in page.text


def test_clear_today_log(browser):
    habit_id = create_habit(browser)
    log_day(browser, habit_id, today_local(), "done")
    r = log_day(browser, habit_id, today_local(), "clear")
    assert r.status_code == 303
    page = browser.get("/")
    assert "Undo" not in page.text
    assert "Read 20 minutes" in page.text


def test_reject_future_log(browser):
    habit_id = create_habit(browser)
    r = log_day(browser, habit_id, today_local() + timedelta(days=1), "done")
    assert r.status_code == 422
    assert "future" in r.text


def test_reject_log_before_habit_existed(browser):
    habit_id = create_habit(browser)
    r = log_day(browser, habit_id, today_local() - timedelta(days=1), "done")
    assert r.status_code == 422
    assert "before this habit existed" in r.text


def test_reject_unknown_log_status(browser):
    habit_id = create_habit(browser)
    r = log_day(browser, habit_id, today_local(), "banana")
    assert r.status_code == 422
    assert "Unknown log status" in r.text


def test_htmx_log_returns_redirect_header(browser):
    habit_id = create_habit(browser)
    r = browser.post(
        f"/habits/{habit_id}/log",
        {"day": today_local().isoformat(), "status": "done", "next": "/"},
        htmx=True,
    )
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == "/"


def test_habit_detail_month_navigation(browser):
    habit_id = create_habit(browser)
    page = browser.get(f"/habits/{habit_id}?month=2020-02")
    assert page.status_code == 200
    assert "February 2020" in page.text
    assert "calendar" in page.text
