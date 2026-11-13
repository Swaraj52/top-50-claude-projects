from __future__ import annotations

from datetime import timedelta

from tests.conftest import create_habit, log_day, today_local


def test_week_page_shows_habit_and_report(browser):
    create_habit(browser, title="Morning walk", days=["0", "1", "2", "3", "4", "5", "6"])
    page = browser.get("/week")
    assert page.status_code == 200
    assert "Morning walk" in page.text
    assert "Weekly report" in page.text
    assert "What actually happened" in page.text


def test_week_grid_marks_completed_day(browser):
    habit_id = create_habit(browser)
    log_day(browser, habit_id, today_local(), "done")
    page = browser.get("/week")
    assert "1/1" in page.text
    assert "✓" in page.text


def test_week_report_counts_done_and_missed(browser):
    habit_id = create_habit(browser)
    log_day(browser, habit_id, today_local(), "done")
    page = browser.get("/week")
    assert "You completed" in page.text
    assert "decided habit days" in page.text


def test_week_navigation_links(browser):
    page = browser.get("/week")
    previous = today_local() - timedelta(days=today_local().weekday() + 7)
    assert f"/week?week={previous.isoformat()}" in page.text
    older = browser.get(f"/week?week={previous.isoformat()}")
    assert older.status_code == 200
    assert "This week" in older.text


def test_week_page_handles_bad_week_value(browser):
    page = browser.get("/week?week=not-a-date")
    assert page.status_code == 200
    assert "Weekly report" in page.text


def test_week_reflection_link(browser):
    page = browser.get("/week")
    assert "/reflect?week=" in page.text
