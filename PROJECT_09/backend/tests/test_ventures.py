from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import CanvasEntry, Venture
from conftest import add_canvas, add_venture


def test_new_venture_form_renders(browser):
    r = browser.get("/ventures/new")
    assert r.status_code == 200
    assert "Name the idea" in r.text
    assert 'name="currency"' in r.text


def test_create_venture_redirects_to_the_overview(browser):
    r = browser.post(
        "/ventures/new",
        {
            "name": "Sahaj",
            "one_liner": "Scheduling for solar installers.",
            "stage": "validating",
            "horizon": "90 days",
            "currency": "INR",
            "segment": "Owner-run installers",
        },
    )
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/ventures/")
    assert location.endswith("?saved=1")


def test_overview_shows_the_venture_and_credit(browser):
    venture_id = add_venture(browser, name="Sahaj")
    r = browser.get(f"/ventures/{venture_id}")
    assert r.status_code == 200
    assert "Sahaj" in r.text
    assert "Built by" in r.text
    assert "Next moves" in r.text


def test_overview_states_an_empty_venture_honestly(browser):
    venture_id = add_venture(browser, name="Thin")
    text = browser.get(f"/ventures/{venture_id}").text
    assert "No revenue streams yet" in text
    assert "No KPIs" in text
    assert "0/9 blocks" in text


def test_venture_name_is_required(browser):
    r = browser.post("/ventures/new", {"name": " "})
    assert r.status_code == 422
    assert "at least two characters" in r.text


def test_duplicate_names_are_rejected_case_sensitively(browser):
    add_venture(browser, name="Sahaj")
    r = browser.post("/ventures/new", {"name": "Sahaj"})
    assert r.status_code == 409
    assert "already have a venture with that name" in r.text


def test_two_different_names_are_allowed(browser, db):
    add_venture(browser, name="Sahaj")
    add_venture(browser, name="Second Draft")
    assert len(db.scalars(select(Venture)).all()) == 2


@pytest.mark.parametrize(
    ("stage", "expected"),
    [("idea", "idea"), ("validating", "validating"), ("building", "building"), ("growing", "growing")],
)
def test_stage_is_stored(browser, db, stage, expected):
    add_venture(browser, name=f"Stage {stage}", stage=stage)
    venture = db.scalar(select(Venture).where(Venture.name == f"Stage {stage}"))
    assert venture.stage == expected


def test_unknown_stage_falls_back_to_idea(browser, db):
    add_venture(browser, name="Odd Stage", stage="someday")
    venture = db.scalar(select(Venture).where(Venture.name == "Odd Stage"))
    assert venture.stage == "idea"


def test_unknown_currency_falls_back_to_inr(browser, db):
    add_venture(browser, name="Odd Currency", currency="XYZ")
    venture = db.scalar(select(Venture).where(Venture.name == "Odd Currency"))
    assert venture.currency == "INR"


def test_unknown_horizon_falls_back_to_90_days(browser, db):
    add_venture(browser, name="Odd Horizon", horizon="someday")
    venture = db.scalar(select(Venture).where(Venture.name == "Odd Horizon"))
    assert venture.horizon == "90 days"


def test_long_text_fields_are_clamped(browser, db):
    add_venture(browser, name="Long", market="m" * 2500, segment="s" * 300)
    venture = db.scalar(select(Venture).where(Venture.name == "Long"))
    assert len(venture.market) == 2000
    assert len(venture.segment) == 240


def test_edit_form_prefills(browser):
    venture_id = add_venture(browser, name="Sahaj", segment="Solar installers")
    r = browser.get(f"/ventures/{venture_id}/edit")
    assert r.status_code == 200
    assert 'value="Sahaj"' in r.text
    assert 'value="Solar installers"' in r.text


def test_edit_saves_and_redirects(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    r = browser.post(
        f"/ventures/{venture_id}/edit",
        {
            "name": "Sahaj Two",
            "one_liner": "Updated line.",
            "stage": "building",
            "horizon": "6 months",
            "currency": "USD",
            "segment": "Installers",
            "market": "Growing",
            "alternatives": "Notebooks",
            "differentiation": "Solar-specific",
        },
    )
    assert r.status_code == 303
    venture = db.get(Venture, venture_id)
    assert venture.name == "Sahaj Two"
    assert venture.stage == "building"
    assert venture.currency == "USD"


def test_edit_rejects_a_blank_name(browser):
    venture_id = add_venture(browser, name="Sahaj")
    r = browser.post(f"/ventures/{venture_id}/edit", {"name": ""})
    assert r.status_code == 422
    assert "at least two characters" in r.text


def test_edit_rejects_a_name_used_by_another_venture(browser):
    add_venture(browser, name="One")
    other = add_venture(browser, name="Two")
    r = browser.post(f"/ventures/{other}/edit", {"name": "One"})
    assert r.status_code == 409
    assert "Another venture already uses that name" in r.text


def test_edit_allows_keeping_its_own_name(browser):
    venture_id = add_venture(browser, name="Sahaj")
    r = browser.post(
        f"/ventures/{venture_id}/edit",
        {"name": "Sahaj", "stage": "idea", "horizon": "90 days", "currency": "INR"},
    )
    assert r.status_code == 303


def test_archive_hides_the_venture_from_the_portfolio(browser, db):
    venture_id = add_venture(browser, name="Old Idea")
    r = browser.post(f"/ventures/{venture_id}/archive")
    assert r.status_code == 303
    assert r.headers["location"] == "/?archived=1"
    assert db.get(Venture, venture_id).archived is True
    assert "Old Idea" not in browser.get("/").text
    assert "Old Idea" in browser.get("/?archived=1").text


def test_restore_returns_the_venture(browser, db):
    venture_id = add_venture(browser, name="Old Idea")
    browser.post(f"/ventures/{venture_id}/archive")
    r = browser.post(f"/ventures/{venture_id}/archive")
    assert r.headers["location"] == f"/ventures/{venture_id}"
    assert db.get(Venture, venture_id).archived is False
    assert "Old Idea" in browser.get("/").text


def test_dashboard_links_to_the_archive_when_it_has_content(browser):
    venture_id = add_venture(browser, name="Old Idea")
    browser.post(f"/ventures/{venture_id}/archive")
    assert "Archived ventures (1)" in browser.get("/").text


def test_archived_view_links_back(browser):
    assert "Active ventures" in browser.get("/?archived=1").text


def test_delete_requires_the_exact_name(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    r = browser.post(f"/ventures/{venture_id}/delete", {"confirm": "sahaj"})
    assert r.status_code == 422
    assert "Type the venture name exactly" in r.text
    assert db.get(Venture, venture_id) is not None


def test_delete_removes_the_venture_and_its_children(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    add_canvas(browser, venture_id, title="A problem worth solving")
    r = browser.post(f"/ventures/{venture_id}/delete", {"confirm": "Sahaj"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert db.get(Venture, venture_id) is None
    assert db.scalars(select(CanvasEntry)).all() == []


def test_venture_pages_404_for_a_missing_id(browser):
    for path in (
        "/ventures/424242",
        "/ventures/424242/edit",
        "/ventures/424242/canvas",
        "/ventures/424242/swot",
        "/ventures/424242/revenue",
        "/ventures/424242/plan",
        "/ventures/424242/kpis",
        "/ventures/424242/brief",
    ):
        assert browser.get(path).status_code == 404, path


def test_dashboard_card_counts_canvas_and_plan(browser):
    venture_id = add_venture(browser, name="Sahaj")
    add_canvas(browser, venture_id, block="problem", title="A real problem")
    text = browser.get("/").text
    assert "11%" in text
    assert "0/0" in text


def test_portfolio_total_counts_open_milestones(browser):
    from datetime import date, timedelta

    from conftest import add_milestone

    venture_id = add_venture(browser, name="Sahaj")
    add_milestone(browser, venture_id, title="First", due_date=date.today() + timedelta(days=5))
    add_milestone(browser, venture_id, title="Second", due_date=date.today() + timedelta(days=9))
    text = browser.get("/").text
    assert ">2<" in text


def test_venture_currency_is_used_in_money(browser):
    from conftest import add_cost, add_stream

    venture_id = add_venture(browser, name="Dollar", currency="USD")
    add_stream(browser, venture_id, price="100", volume="10")
    add_cost(browser, venture_id, amount="200")
    text = browser.get(f"/ventures/{venture_id}/revenue").text
    assert "$1,000" in text
    assert "₹" not in text
