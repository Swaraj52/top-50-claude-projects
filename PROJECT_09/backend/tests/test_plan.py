from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Milestone
from app.services.milestones import board, groups, sort_key, summary, visible_status
from conftest import add_milestone, add_venture, ist_today


class Fake:
    def __init__(self, title="A milestone", due=None, horizon="now", status="planned", order=1, id=1):
        self.title, self.due_date, self.horizon = title, due, horizon
        self.status, self.sort_order, self.id = status, order, id


def test_plan_page_shows_three_horizons(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/plan").text
    assert "Now" in text and "Next" in text and "Later" in text


def test_empty_plan_reads_honestly(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/plan").text
    assert "0%" in text
    assert "nothing open" in text


def test_add_a_milestone(browser, db):
    venture_id = add_venture(browser)
    due = ist_today() + timedelta(days=10)
    r = browser.post(
        f"/ventures/{venture_id}/plan",
        {
            "title": "Ten installers entering jobs",
            "success_criterion": "Ten accounts log three jobs in a week.",
            "owner": "Swayam",
            "due_date": due.isoformat(),
            "horizon": "now",
            "status": "in_progress",
        },
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/plan#now"
    milestone = db.scalar(select(Milestone))
    assert milestone.title == "Ten installers entering jobs"
    assert milestone.due_date == due
    assert milestone.horizon == "now"
    assert milestone.status == "in_progress"
    assert milestone.sort_order == 1


def test_milestone_title_is_required(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/plan", {"title": "ab"})
    assert r.status_code == 422
    assert db.scalars(select(Milestone)).all() == []


def test_an_unknown_horizon_falls_back_to_now(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, horizon="someday")
    assert db.scalar(select(Milestone)).horizon == "now"


def test_an_unknown_status_falls_back_to_planned(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, status="maybe")
    assert db.scalar(select(Milestone)).status == "planned"


def test_a_bad_due_date_is_stored_as_undated(browser, db):
    venture_id = add_venture(browser)
    browser.post(f"/ventures/{venture_id}/plan", {"title": "No real date", "due_date": "not-a-date"})
    assert db.scalar(select(Milestone)).due_date is None


def test_overdue_is_derived_from_the_date(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Late thing", due_date=ist_today() - timedelta(days=4))
    milestone = db.scalar(select(Milestone))
    assert milestone.status == "planned"
    assert visible_status(milestone, ist_today()) == "overdue"
    text = browser.get(f"/ventures/{venture_id}/plan").text
    assert "Overdue" in text
    assert "4 days overdue" in text


def test_a_done_milestone_is_never_overdue(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Finished early", due_date=ist_today() - timedelta(days=9), status="done")
    milestone = db.scalar(select(Milestone))
    assert visible_status(milestone, ist_today()) == "done"


def test_mark_done_sets_completed_at(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Finish me")
    r = browser.post("/milestones/1/status", {"status": "done"})
    assert r.status_code == 303
    milestone = db.scalar(select(Milestone))
    assert milestone.status == "done"
    assert milestone.completed_at is not None


def test_reopen_clears_completed_at(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Finish me", status="done")
    browser.post("/milestones/1/status", {"status": "in_progress"})
    milestone = db.scalar(select(Milestone))
    assert milestone.status == "in_progress"
    assert milestone.completed_at is None


def test_an_unknown_status_keeps_the_current_one(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Keep status", status="at_risk")
    browser.post("/milestones/1/status", {"status": "teleported"})
    assert db.scalar(select(Milestone)).status == "at_risk"


def test_edit_form_prefills(browser):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Distributor training deck")
    r = browser.get(f"/ventures/{venture_id}/plan?edit=1")
    assert 'value="Distributor training deck"' in r.text
    assert "Edit milestone" in r.text


def test_edit_updates_and_marks_completion(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Old title", horizon="now")
    r = browser.post(
        "/milestones/1/edit",
        {
            "title": "New title",
            "success_criterion": "A real test.",
            "owner": "Priya",
            "due_date": (ist_today() + timedelta(days=5)).isoformat(),
            "horizon": "next",
            "status": "done",
        },
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/plan#next"
    milestone = db.scalar(select(Milestone))
    assert milestone.title == "New title"
    assert milestone.horizon == "next"
    assert milestone.status == "done"
    assert milestone.completed_at is not None


def test_edit_rejects_a_blank_title(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Keep me")
    r = browser.post("/milestones/1/edit", {"title": ""})
    assert r.status_code == 422
    assert db.scalar(select(Milestone)).title == "Keep me"


def test_delete_a_milestone(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Delete me", horizon="later")
    r = browser.post("/milestones/1/delete")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/plan#later"
    assert db.scalars(select(Milestone)).all() == []


def test_plan_is_owner_scoped(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    add_milestone(browser, venture_id, title="Mine")
    other = make_browser().register(email="plan-other@example.com", name="Other")
    assert other.post("/milestones/1/edit", {"title": "Stolen"}).status_code == 404
    assert other.post("/milestones/1/status", {"status": "done"}).status_code == 404
    assert other.post("/milestones/1/delete").status_code == 404


def test_summary_reports_progress_and_next():
    today = ist_today()
    items = [
        Fake("Done one", today - timedelta(days=3), status="done"),
        Fake("Next one", today + timedelta(days=2), id=2),
        Fake("Undated", None, id=3),
    ]
    result = summary(items, today)
    assert result["total"] == 3
    assert result["done"] == 1
    assert result["open"] == 2
    assert result["progress"] == 33
    assert result["next_due"].title == "Next one"
    assert result["overdue_count"] == 0


def test_next_due_falls_back_to_an_undated_item():
    today = ist_today()
    result = summary([Fake("Undated", None)], today)
    assert result["next_due"].title == "Undated"


def test_summary_counts_overdue_separately():
    today = ist_today()
    result = summary([Fake("Late", today - timedelta(days=2))], today)
    assert result["overdue_count"] == 1
    assert result["by_status"]["overdue"] == 1
    assert result["open"] == 1


def test_sort_key_puts_dated_items_first():
    today = ist_today()
    items = [Fake("Undated", None, id=2), Fake("Dated", today, id=1)]
    assert [m.title for m in sorted(items, key=sort_key)] == ["Dated", "Undated"]


def test_groups_keep_the_canonical_horizon_order():
    today = ist_today()
    rows = groups([Fake("Later", today, horizon="later"), Fake("Now", today, horizon="now")], today)
    assert [row["key"] for row in rows] == ["now", "next", "later"]
    assert rows[0]["items"][0].title == "Now"


def test_board_derives_each_card_status():
    today = ist_today()
    rows = board([Fake("Late", today - timedelta(days=1), horizon="now")], today)
    card = rows[0]["cards"][0]
    assert card["status"] == "overdue"
    assert card["label"] == "Overdue"
    assert card["days"] == -1


def test_done_milestones_show_a_line_through(browser):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Completed thing", status="done")
    text = browser.get(f"/ventures/{venture_id}/plan").text
    assert "status-done" in text
    assert "Completed thing" in text


def test_plan_page_offers_mark_done_for_open_items(browser):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Open thing")
    text = browser.get(f"/ventures/{venture_id}/plan").text
    assert "Mark done" in text


def test_plan_page_offers_reopen_for_done_items(browser):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Done thing", status="done")
    text = browser.get(f"/ventures/{venture_id}/plan").text
    assert "Reopen" in text


def test_overview_flags_overdue_milestones(browser):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, title="Late", due_date=ist_today() - timedelta(days=3))
    text = browser.get(f"/ventures/{venture_id}").text
    assert "1 overdue" in text
    assert "Resolve 1 overdue milestone" in text


def test_success_criterion_is_clamped(browser, db):
    venture_id = add_venture(browser)
    add_milestone(browser, venture_id, success_criterion="s" * 400)
    assert len(db.scalar(select(Milestone)).success_criterion) == 300
