from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import CANVAS_BLOCKS, CanvasEntry
from conftest import add_canvas, add_venture


def test_canvas_page_shows_all_nine_blocks(browser):
    venture_id = add_venture(browser)
    r = browser.get(f"/ventures/{venture_id}/canvas")
    assert r.status_code == 200
    for label in ("Problem", "Customer segments", "Value proposition", "Solution", "Channels"):
        assert label in r.text
    assert "Unfair advantage" in r.text


def test_empty_canvas_shows_prompts(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/canvas").text
    assert "Which concrete problem are you solving" in text
    assert "0/9 filled" in text


def test_add_a_note(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(
        f"/ventures/{venture_id}/canvas",
        {"block": "problem", "title": "Installers lose track of jobs", "detail": "Thirty to fifty open jobs"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/canvas#problem"
    entry = db.scalar(select(CanvasEntry))
    assert entry.block == "problem"
    assert entry.title == "Installers lose track of jobs"
    assert entry.detail == "Thirty to fifty open jobs"
    assert entry.sort_order == 1


def test_notes_render_in_their_block(browser):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, block="channels", title="Installer WhatsApp groups")
    text = browser.get(f"/ventures/{venture_id}/canvas").text
    assert "Installer WhatsApp groups" in text
    assert "1/9 filled" in text


def test_canvas_completeness_updates(browser):
    venture_id = add_venture(browser)
    for block in CANVAS_BLOCKS:
        add_canvas(browser, venture_id, block=block, title=f"A {block} note")
    text = browser.get(f"/ventures/{venture_id}/canvas").text
    assert "9/9 filled" in text
    assert "100%" in text


def test_short_titles_are_rejected(browser):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/canvas", {"block": "problem", "title": "ab"})
    assert r.status_code == 422
    assert "at least three characters" in r.text


def test_an_unknown_block_falls_back_to_problem(browser, db):
    venture_id = add_venture(browser)
    browser.post(f"/ventures/{venture_id}/canvas", {"block": "nonsense", "title": "A real note"})
    assert db.scalar(select(CanvasEntry)).block == "problem"


def test_sort_order_keeps_adding_after_the_last(browser, db):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, title="First note")
    add_canvas(browser, venture_id, title="Second note")
    orders = [e.sort_order for e in db.scalars(select(CanvasEntry).order_by(CanvasEntry.id)).all()]
    assert orders == [1, 2]


def test_detail_is_clamped(browser, db):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, title="Clamped", detail="d" * 900)
    assert len(db.scalar(select(CanvasEntry)).detail) == 600


def test_edit_form_prefills_a_note(browser):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, block="value", title="One list on a phone")
    entry = browser.get(f"/ventures/{venture_id}/canvas").text
    assert "One list on a phone" in entry
    r = browser.get(f"/ventures/{venture_id}/canvas?edit=1")
    assert 'value="One list on a phone"' in r.text
    assert "Edit note" in r.text


def test_edit_updates_a_note(browser, db):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, block="problem", title="Old title")
    r = browser.post(
        "/canvas/1/edit",
        {"block": "customers", "title": "New title", "detail": "Now with evidence"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/canvas#customers"
    entry = db.scalar(select(CanvasEntry))
    assert entry.block == "customers"
    assert entry.title == "New title"
    assert entry.detail == "Now with evidence"


def test_edit_rejects_a_blank_title(browser, db):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, title="Keep me")
    r = browser.post("/canvas/1/edit", {"block": "problem", "title": ""})
    assert r.status_code == 422
    assert db.scalar(select(CanvasEntry)).title == "Keep me"


def test_delete_removes_a_note(browser, db):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, title="Delete me")
    r = browser.post("/canvas/1/delete")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/canvas#problem"
    assert db.scalars(select(CanvasEntry)).all() == []


def test_canvas_entries_are_owner_scoped(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    add_canvas(browser, venture_id, title="My note")
    other = make_browser().register(email="canvas-other@example.com", name="Other")
    assert other.post("/canvas/1/edit", {"title": "Stolen"}).status_code == 404
    assert other.post("/canvas/1/delete").status_code == 404


def test_grouped_orders_blocks_canonically():
    from app.services.canvas import grouped

    class Fake:
        def __init__(self, block, order, id):
            self.block, self.sort_order, self.id = block, order, id

    entries = [Fake("value", 2, 1), Fake("problem", 5, 2), Fake("problem", 1, 3)]
    rows = grouped(entries)
    assert list(rows) == list(CANVAS_BLOCKS)
    assert [e.id for e in rows["problem"]] == [3, 2]


def test_completeness_reports_missing_labels():
    from app.services.canvas import completeness

    class Fake:
        block = "problem"

    result = completeness([Fake()])
    assert result["filled"] == 1
    assert result["percent"] == 11
    assert "customers" in result["missing"]
    assert "Customer segments" in result["missing_labels"]


def test_gaps_are_limited_and_explained():
    from app.services.canvas import gaps

    result = gaps([], limit=2)
    assert len(result) == 2
    assert result[0]["block"] == "problem"
    assert "problem" in result[0]["prompt"].lower()


def test_ready_requires_every_block():
    from app.services.canvas import ready

    class Fake:
        def __init__(self, block):
            self.block = block

    assert ready([Fake(b) for b in CANVAS_BLOCKS]) is True
    assert ready([Fake("problem")]) is False


def test_overview_lists_canvas_gaps(browser):
    venture_id = add_venture(browser)
    add_canvas(browser, venture_id, block="problem", title="A real problem")
    text = browser.get(f"/ventures/{venture_id}").text
    assert "Still empty" in text
    assert "Customer segments" in text


def test_canvas_page_is_anchored_per_block(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/canvas").text
    for block in CANVAS_BLOCKS:
        assert f'id="{block}"' in text


@pytest.mark.parametrize("block", CANVAS_BLOCKS)
def test_each_block_accepts_a_note(browser, db, block):
    venture_id = add_venture(browser, name=f"Venture {block}")
    add_canvas(browser, venture_id, block=block, title=f"Note for {block}")
    assert db.scalar(select(CanvasEntry).where(CanvasEntry.block == block)) is not None
