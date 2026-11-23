from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.models import Venture
from app.services import ai
from app.services import brief as brief_service
from app.services import overview as overview_service
from conftest import add_canvas, add_cost, add_kpi, add_milestone, add_reading, add_stream, add_swot, add_venture

GOOD_NARRATIVE = (
    "Sahaj is a validating venture selling scheduling software to owner-run solar installers "
    "in Pune and Nashik, where job books still live in notebooks and WhatsApp threads.\n\n"
    "The base case earns ninety thousand rupees a month against twenty-six thousand of monthly "
    "cost, which leaves a wide margin at forty paying units and no invented demand.\n\n"
    "The next milestone is ten installers logging jobs weekly, while two of the three measured "
    "KPIs sit behind their expected pace and need a decision this month."
)


def _empty_venture(**overrides):
    fields = {
        "id": 1,
        "name": "Thin",
        "one_liner": "",
        "stage": "idea",
        "currency": "INR",
        "segment": "",
        "market": "",
        "alternatives": "",
        "differentiation": "",
        "narrative": "",
        "canvas": [],
        "streams": [],
        "costs": [],
        "milestones": [],
        "kpis": [],
        "swot": [],
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _snapshot(venture):
    return overview_service.snapshot(venture, __import__("datetime").date(2026, 5, 1))


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return {"content": [{"type": "text", "text": __import__("json").dumps(self._payload)}]}


def test_brief_page_shows_all_six_sections(browser):
    venture_id = add_venture(browser, market="Maharashtra installs are growing")
    add_canvas(browser, venture_id, block="problem", title="Job books lose money")
    add_canvas(browser, venture_id, block="customers", title="Installers with four crews")
    add_canvas(browser, venture_id, block="value", title="One list on a phone")
    text = browser.get(f"/ventures/{venture_id}/brief").text
    for heading in (
        "The opening",
        "Where it plays",
        "How it earns",
        "What happens next",
        "What would prove it",
        "What could break it",
    ):
        assert heading in text
    assert "The memo" in text


def test_empty_venture_states_what_is_missing(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/brief").text
    assert "No revenue streams are defined yet" in text
    assert "No milestones are planned yet" in text
    assert "No KPIs are defined yet" in text
    assert "No SWOT items are recorded yet" in text
    assert "Thin on" in text or "thin on" in text


def test_brief_uses_the_stored_inputs(browser):
    venture_id = add_venture(
        browser,
        name="Sahaj",
        segment="Owner-run solar installers",
        market="Maharashtra installs are growing",
        alternatives="Notebooks",
        differentiation="Solar-specific job list",
    )
    add_canvas(browser, venture_id, block="problem", title="Job books lose money", detail="Missed follow-ups")
    add_canvas(browser, venture_id, block="customers", title="Installers with four crews")
    add_canvas(browser, venture_id, block="value", title="One list on a phone")
    add_stream(browser, venture_id, price="1499", volume="40")
    add_cost(browser, venture_id, amount="25900")
    add_milestone(browser, venture_id, title="Ten installers logging jobs")
    add_kpi(browser, venture_id, name="Activated installers", target="40")
    add_swot(browser, venture_id, quadrant="threat", text="An incumbent adds a free tier", impact="5")

    text = browser.get(f"/ventures/{venture_id}/brief").text
    assert "Job books lose money — Missed follow-ups" in text
    assert "One list on a phone" in text
    assert "₹59,960" in text
    assert "₹25,900" in text
    assert "Ten installers logging jobs" in text
    assert "An incumbent adds a free tier" in text
    assert "Built by" in text and "Swayam" in text


def test_draft_memo_is_labelled(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/brief").text
    assert "A draft assembled locally" in text
    assert "Save this memo" in text


def test_saving_the_memo_stores_it(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    r = browser.post(f"/ventures/{venture_id}/brief")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/brief?saved=1"
    db.expire_all()
    venture = db.get(Venture, venture_id)
    assert venture.narrative
    assert venture.narrative_source == "local"
    assert venture.narrative_at is not None
    text = browser.get(f"/ventures/{venture_id}/brief?saved=1").text
    assert "Memo saved." in text
    assert "Local" in text
    assert "Discard saved memo" in text


def test_reset_discards_the_saved_memo(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    browser.post(f"/ventures/{venture_id}/brief")
    r = browser.post(f"/ventures/{venture_id}/brief/reset")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/brief"
    db.expire_all()
    venture = db.get(Venture, venture_id)
    assert venture.narrative == ""
    assert venture.narrative_at is None


def test_ai_button_is_hidden_without_a_key(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/brief").text
    assert "Rewrite with Claude" not in text
    assert "Add an API key" in text


def test_ai_rewrite_without_a_key_keeps_the_local_memo(browser, db):
    venture_id = add_venture(browser, name="Sahaj")
    browser.post(f"/ventures/{venture_id}/brief")
    db.expire_all()
    before = db.get(Venture, venture_id).narrative
    r = browser.post(f"/ventures/{venture_id}/brief/ai")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/brief?ai=failed"
    db.expire_all()
    venture = db.get(Venture, venture_id)
    assert venture.narrative == before
    assert venture.narrative_source == "local"
    text = browser.get(f"/ventures/{venture_id}/brief?ai=failed").text
    assert "Claude was unavailable" in text


def test_ai_rewrite_success_stores_claude_prose(browser, db, app, monkeypatch):
    venture_id = add_venture(browser, name="Sahaj")
    browser.post(f"/ventures/{venture_id}/brief")
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **kw: FakeResponse({"narrative": GOOD_NARRATIVE}))
    r = browser.post(f"/ventures/{venture_id}/brief/ai")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/brief?ai=saved"
    db.expire_all()
    venture = db.get(Venture, venture_id)
    assert venture.narrative == GOOD_NARRATIVE
    assert venture.narrative_source == "claude"
    text = browser.get(f"/ventures/{venture_id}/brief?ai=saved").text
    assert "Claude rewrote the memo" in text
    assert "Sahaj is a validating venture" in text


def test_ai_rewrite_uses_the_stored_facts_in_the_prompt(browser, db, app, monkeypatch):
    venture_id = add_venture(browser, name="Sahaj", segment="Solar installers")
    add_stream(browser, venture_id, price="1499", volume="40")
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse({"narrative": GOOD_NARRATIVE})

    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    browser.post(f"/ventures/{venture_id}/brief/ai")
    payload = seen["json"]
    user_text = payload["messages"][0]["content"]
    assert "Sahaj" in user_text
    assert "Solar installers" in user_text
    assert "Return JSON" in user_text
    assert payload["system"] == ai.SYSTEM
    assert seen["headers"]["x-api-key"] == "test-key"


@pytest.mark.parametrize(
    "narrative",
    [
        "# Heading\n\n" + GOOD_NARRATIVE,
        "Only one paragraph that is comfortably longer than forty characters but still alone.",
        "Too short. " * 2,
    ],
)
def test_ai_rewrite_rejects_invalid_prose(browser, db, app, monkeypatch, narrative):
    venture_id = add_venture(browser, name="Sahaj")
    browser.post(f"/ventures/{venture_id}/brief")
    db.expire_all()
    before = db.get(Venture, venture_id).narrative
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **kw: FakeResponse({"narrative": narrative}))
    r = browser.post(f"/ventures/{venture_id}/brief/ai")
    assert r.headers["location"] == f"/ventures/{venture_id}/brief?ai=failed"
    db.expire_all()
    venture = db.get(Venture, venture_id)
    assert venture.narrative == before
    assert venture.narrative_source == "local"


def test_ai_rewrite_survives_an_http_error(browser, db, app, monkeypatch):
    venture_id = add_venture(browser, name="Sahaj")
    browser.post(f"/ventures/{venture_id}/brief")
    db.expire_all()
    before = db.get(Venture, venture_id).narrative

    def boom(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(ai.httpx, "post", boom)
    r = browser.post(f"/ventures/{venture_id}/brief/ai")
    assert r.headers["location"] == f"/ventures/{venture_id}/brief?ai=failed"
    db.expire_all()
    assert db.get(Venture, venture_id).narrative == before


def test_ai_rewrite_over_htmx_returns_the_partial(browser, app, monkeypatch):
    venture_id = add_venture(browser, name="Sahaj")
    monkeypatch.setattr(app.state.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(ai.httpx, "post", lambda *a, **kw: FakeResponse({"narrative": GOOD_NARRATIVE}))
    r = browser.post(f"/ventures/{venture_id}/brief/ai", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<html" not in r.text
    assert 'id="memo"' in r.text
    assert "Claude" in r.text


def test_brief_routes_are_owner_scoped(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    other = make_browser().register(email="brief-other@example.com", name="Other")
    assert other.c.get(f"/ventures/{venture_id}/brief").status_code == 404
    assert other.post(f"/ventures/{venture_id}/brief").status_code == 404
    assert other.post(f"/ventures/{venture_id}/brief/ai").status_code == 404
    assert other.post(f"/ventures/{venture_id}/brief/reset").status_code == 404


def test_narrative_text_accepts_plain_paragraphs():
    assert ai.narrative_text(GOOD_NARRATIVE) == GOOD_NARRATIVE


def test_narrative_text_normalises_whitespace_and_crlf():
    messy = GOOD_NARRATIVE.replace("\n\n", "\r\n\r\n").replace(" a ", "   a  ")
    cleaned = ai.narrative_text(messy)
    assert "\r" not in cleaned
    assert "   " not in cleaned


@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        "one paragraph only, comfortably longer than forty characters, but alone.",
        "# heading\n\n" + GOOD_NARRATIVE,
        "```\n" + GOOD_NARRATIVE + "\n```",
        "\n\n".join(["A short paragraph that is still under the minimum length."] * 7),
        "x" * 4000,
    ],
)
def test_narrative_text_rejects_bad_input(value):
    with pytest.raises(ValueError):
        ai.narrative_text(value)


def test_prompt_carries_every_section_and_the_json_instruction():
    venture = _empty_venture(name="Sahaj", one_liner="One list on a phone", segment="Installers")
    snap = _snapshot(venture)
    blocks = brief_service.sections(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    text = brief_service.prompt(venture, "A small memo.", blocks)
    assert "Venture: Sahaj" in text
    assert "One-liner: One list on a phone" in text
    for block in blocks:
        assert block["heading"] in text
    assert 'Return JSON: {"narrative"' in text


def test_sections_open_with_the_name_and_stage():
    venture = _empty_venture(name="Sahaj", stage="validating", one_liner="One list", segment="Installers")
    snap = _snapshot(venture)
    blocks = brief_service.sections(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    opening = next(block for block in blocks if block["key"] == "opening")["body"]
    assert opening[0] == "Sahaj is a validating venture."
    assert "One list" in opening
    assert "It is aimed at Installers." in opening


def test_sections_say_what_is_missing_for_an_empty_venture():
    venture = _empty_venture()
    snap = _snapshot(venture)
    blocks = {block["key"]: block for block in brief_service.sections(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])}
    assert "No revenue streams are defined yet" in blocks["model"]["body"][0]
    assert "No milestones are planned yet" in blocks["execution"]["body"][0]
    assert "No KPIs are defined yet" in blocks["proof"]["body"][0]
    assert "No SWOT items are recorded yet" in blocks["risks"]["body"][0]


def test_sections_never_invent_a_number():
    venture = _empty_venture(name="Sahaj")
    snap = _snapshot(venture)
    blocks = brief_service.sections(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    joined = " ".join(" ".join(block["body"]) for block in blocks)
    assert "₹" not in joined
    assert "month" not in joined.lower()


def test_memo_keeps_the_founder_voice_and_names_the_gap():
    venture = _empty_venture(name="Thin", segment="Installers")
    snap = _snapshot(venture)
    memo = brief_service.memo(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    assert memo.startswith("Thin is a idea venture")
    assert "no revenue model yet" in memo
    assert "No KPIs are defined yet." in memo
    assert "thin on problem, customer segments, value proposition" in memo
    assert "\n\n" in memo


def test_memo_uses_the_canvas_and_the_numbers():
    from app.models import CanvasEntry

    venture = _empty_venture(name="Sahaj", stage="validating", segment="Installers")
    entries = [
        CanvasEntry(venture_id=1, block="problem", title="Job books lose money", detail="Missed follow-ups", sort_order=1),
        CanvasEntry(venture_id=1, block="value", title="One list on a phone", detail="", sort_order=2),
    ]
    venture.canvas = entries
    from app.models import CostLine, RevenueStream

    venture.streams = [RevenueStream(venture_id=1, name="Subscription", price=1000, volume=10, confidence="high", unit="per month", model="subscription")]
    venture.costs = [CostLine(venture_id=1, name="Hosting", amount=2000, kind="fixed")]
    snap = _snapshot(venture)
    memo = brief_service.memo(venture, entries, snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    assert "the problem is Job books lose money — Missed follow-ups" in memo
    assert "the promise is One list on a phone" in memo
    assert "₹10,000 a month" in memo
    assert "₹8,000" in memo
    assert "80% margin" in memo


def test_memo_says_when_the_numbers_are_negative():
    from app.models import CostLine, RevenueStream

    venture = _empty_venture(name="Sahaj")
    venture.streams = [RevenueStream(venture_id=1, name="Subscription", price=100, volume=1, confidence="medium", unit="per month", model="subscription")]
    venture.costs = [CostLine(venture_id=1, name="Support", amount=500, kind="fixed")]
    snap = _snapshot(venture)
    memo = brief_service.memo(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    assert "shortfall" in memo


def test_memo_mentions_milestones_and_kpis():
    from datetime import date, timedelta

    from app.models import Kpi, KpiReading, Milestone

    venture = _empty_venture(name="Sahaj")
    today = date(2026, 5, 1)
    venture.milestones = [
        Milestone(venture_id=1, title="First ten installers", due_date=today + timedelta(days=10), horizon="now", status="in_progress", sort_order=1),
        Milestone(venture_id=1, title="Distributor deck", due_date=today - timedelta(days=2), horizon="now", status="planned", sort_order=2),
    ]
    kpi = Kpi(venture_id=1, name="Activated installers", unit="installers", direction="up", baseline=0, target=40, cadence="monthly")
    kpi.readings = [KpiReading(kpi_id=1, value=10, recorded_on=today)]
    venture.kpis = [kpi]
    snap = _snapshot(venture)
    memo = brief_service.memo(venture, [], snap["finance"], snap["plan"], snap["kpis"], snap["swot"])
    assert "0 of 2 milestones are done" in memo
    assert "First ten installers" in memo
    assert "1 are overdue" in memo
    assert "KPIs are on pace" in memo


def _complete_venture(browser):
    from app.models import CANVAS_BLOCKS

    venture_id = add_venture(browser, name="Sahaj", segment="Installers")
    for block in CANVAS_BLOCKS:
        add_canvas(browser, venture_id, block=block, title=f"A {block} note")
    add_stream(browser, venture_id)
    add_cost(browser, venture_id)
    add_kpi(browser, venture_id)
    add_swot(browser, venture_id, quadrant="strength", text="Two design partners")
    return venture_id


def test_overview_offers_the_brief_as_a_next_move(browser):
    venture_id = _complete_venture(browser)
    text = browser.get(f"/ventures/{venture_id}").text
    assert "Write the strategy brief" in text


def test_brief_is_not_listed_after_it_is_saved(browser):
    venture_id = _complete_venture(browser)
    browser.post(f"/ventures/{venture_id}/brief")
    text = browser.get(f"/ventures/{venture_id}").text
    assert "Write the strategy brief" not in text


def test_export_contains_the_saved_narrative(browser):
    import json

    venture_id = add_venture(browser, name="Sahaj")
    browser.post(f"/ventures/{venture_id}/brief")
    payload = json.loads(browser.get("/settings/export").text)
    assert payload["ventures"][0]["narrative_source"] == "local"
    assert payload["ventures"][0]["narrative"]
