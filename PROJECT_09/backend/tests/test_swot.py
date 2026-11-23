from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import SwotItem
from conftest import add_swot, add_venture


def test_swot_page_shows_four_quadrants(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/swot").text
    for label in ("Strength", "Weakness", "Opportunity", "Threat"):
        assert label in text
    assert "Not started" in text


def test_add_a_strength(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(
        f"/ventures/{venture_id}/swot",
        {"quadrant": "strength", "text": "Two design partners", "impact": "5", "evidence": "Signed pilots"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/swot#strength"
    item = db.scalar(select(SwotItem))
    assert item.quadrant == "strength"
    assert item.impact == 5
    assert item.evidence == "Signed pilots"


def test_impact_is_clamped_to_one_and_five(browser, db):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, text="Too high", impact="9")
    add_swot(browser, venture_id, text="Too low", impact="0")
    impacts = sorted(i.impact for i in db.scalars(select(SwotItem)).all())
    assert impacts == [1, 5]


def test_a_non_numeric_impact_uses_the_default(browser, db):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, text="Odd impact", impact="lots")
    assert db.scalar(select(SwotItem)).impact == 3


def test_an_unknown_quadrant_falls_back_to_strength(browser, db):
    venture_id = add_venture(browser)
    browser.post(f"/ventures/{venture_id}/swot", {"quadrant": "neutral", "text": "Not a quadrant"})
    assert db.scalar(select(SwotItem)).quadrant == "strength"


def test_short_text_is_rejected(browser):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/swot", {"quadrant": "weakness", "text": "ab"})
    assert r.status_code == 422
    assert "at least three characters" in r.text


def test_items_render_in_their_quadrant(browser):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, quadrant="threat", text="An incumbent adds a free tier")
    text = browser.get(f"/ventures/{venture_id}/swot").text
    assert "An incumbent adds a free tier" in text


def test_edit_form_prefills(browser):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, quadrant="opportunity", text="Subsidy moved online")
    r = browser.get(f"/ventures/{venture_id}/swot?edit=1")
    assert 'value="Subsidy moved online"' in r.text
    assert "Edit item" in r.text


def test_edit_moves_the_item_and_updates_the_impact(browser, db):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, quadrant="strength", text="Might be a threat")
    r = browser.post(
        "/swot/1/edit",
        {"quadrant": "threat", "text": "An incumbent could bundle this", "impact": "4", "evidence": "Pricing page"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/swot#threat"
    item = db.scalar(select(SwotItem))
    assert item.quadrant == "threat"
    assert item.impact == 4


def test_edit_rejects_a_blank_text(browser, db):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, text="Keep this")
    r = browser.post("/swot/1/edit", {"quadrant": "strength", "text": ""})
    assert r.status_code == 422
    assert db.scalar(select(SwotItem)).text == "Keep this"


def test_delete_removes_the_item(browser, db):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, quadrant="weakness", text="No invoicing yet")
    r = browser.post("/swot/1/delete")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/swot#weakness"
    assert db.scalars(select(SwotItem)).all() == []


def test_swot_is_owner_scoped(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    add_swot(browser, venture_id, text="A real strength")
    other = make_browser().register(email="swot-other@example.com", name="Other")
    assert other.post("/swot/1/edit", {"text": "Stolen"}).status_code == 404
    assert other.post("/swot/1/delete").status_code == 404


def test_evidence_is_clamped(browser, db):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, text="Clamped evidence", evidence="e" * 400)
    assert len(db.scalar(select(SwotItem)).evidence) == 300


def test_a_balanced_ledger_reads_even():
    from app.services.swot import summary

    class Fake:
        def __init__(self, quadrant, impact, id=1):
            self.quadrant, self.impact, self.id = quadrant, impact, id

    result = summary([Fake("strength", 4), Fake("threat", 4)])
    assert result["balance"] == 0
    assert result["tone"] == "even"
    assert result["tone_label"] == "Balanced"


def test_a_positive_ledger_reads_strong():
    from app.services.swot import summary

    class Fake:
        def __init__(self, quadrant, impact, id=1):
            self.quadrant, self.impact, self.id = quadrant, impact, id

    result = summary([Fake("strength", 5), Fake("opportunity", 4), Fake("threat", 2)])
    assert result["positive"] == 9
    assert result["negative"] == 2
    assert result["tone"] == "strong"


def test_a_negative_ledger_reads_exposed():
    from app.services.swot import summary

    class Fake:
        def __init__(self, quadrant, impact, id=1):
            self.quadrant, self.impact, self.id = quadrant, impact, id

    result = summary([Fake("weakness", 5), Fake("threat", 4), Fake("strength", 2)])
    assert result["balance"] == -7
    assert result["tone"] == "exposed"


def test_an_empty_ledger_says_not_started():
    from app.services.swot import summary

    result = summary([])
    assert result["tone"] == "empty"
    assert result["tone_label"] == "Not started"


def test_risks_are_the_three_highest_negatives():
    from app.services.swot import summary

    class Fake:
        def __init__(self, quadrant, impact, text, id=1):
            self.quadrant, self.impact, self.text, self.id = quadrant, impact, text, id

    items = [
        Fake("threat", 2, "small", 1),
        Fake("weakness", 5, "big", 2),
        Fake("threat", 4, "medium", 3),
        Fake("strength", 5, "good", 4),
        Fake("weakness", 3, "third", 5),
    ]
    result = summary(items)
    assert [i.text for i in result["risks"]] == ["big", "medium", "third"]


def test_quadrants_sort_by_impact():
    from app.services.swot import grouped

    class Fake:
        def __init__(self, quadrant, impact, id):
            self.quadrant, self.impact, self.id = quadrant, impact, id

    rows = grouped([Fake("strength", 2, 1), Fake("strength", 5, 2), Fake("threat", 1, 3)])
    assert [i.impact for i in rows["strength"]] == [5, 2]
    assert [i.impact for i in rows["threat"]] == [1]


def test_overview_states_the_ledger_tone(browser):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, quadrant="weakness", text="Support load is unknown", impact="5")
    add_swot(browser, venture_id, quadrant="threat", text="An incumbent bundles it", impact="4")
    text = browser.get(f"/ventures/{venture_id}").text
    assert "Leaning exposed" in text
    assert "Sharpest risk" in text


def test_swot_page_names_the_sharpest_risks(browser):
    venture_id = add_venture(browser)
    add_swot(browser, venture_id, quadrant="threat", text="Distribution is the bottleneck", impact="5")
    text = browser.get(f"/ventures/{venture_id}/swot").text
    assert "What would hurt first" in text
    assert "Distribution is the bottleneck" in text
