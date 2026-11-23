from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models import (
    CanvasEntry,
    CostLine,
    Kpi,
    KpiReading,
    Milestone,
    RevenueStream,
    SwotItem,
    User,
    Venture,
)
from conftest import add_canvas, add_cost, add_kpi, add_milestone, add_reading, add_stream, add_swot, add_venture
from scripts import import_data


def run_import(monkeypatch, settings, path, email="swayam@example.com", dry_run=False):
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    argv = ["import_data.py", str(path), "--email", email]
    if dry_run:
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    return import_data.main()


def export_of(browser) -> dict:
    return json.loads(browser.get("/settings/export").text)


def write_payload(tmp_path, payload) -> "object":
    path = tmp_path / "keystone-export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_read_accepts_a_valid_export(tmp_path):
    payload = {"format": "keystone-export-v1", "ventures": []}
    path = write_payload(tmp_path, payload)
    assert import_data._read(path) == payload


def test_read_accepts_a_missing_format_for_older_files(tmp_path):
    path = write_payload(tmp_path, {"ventures": []})
    assert import_data._read(path)["ventures"] == []


def test_read_rejects_an_unknown_format(tmp_path):
    path = write_payload(tmp_path, {"format": "loom-export-v1", "ventures": []})
    with pytest.raises(SystemExit):
        import_data._read(path)


def test_read_rejects_a_non_keystone_document(tmp_path):
    path = write_payload(tmp_path, {"items": []})
    with pytest.raises(SystemExit):
        import_data._read(path)


def test_read_rejects_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        import_data._read(path)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), ("", 0), ("12", 12), (" 1,499 ", 1499), ("-5", 0), ("lots", 0), ("1e9", 1_000_000_000)],
)
def test_int_is_clamped_and_safe(value, expected):
    assert import_data._int(value) == expected


def test_int_respects_the_range():
    assert import_data._int("0", fallback=3, low=1) == 1
    assert import_data._int("9", fallback=3, high=5) == 5


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0.0), ("1.5", 1.5), (" 2,000 ", 2000.0), ("nan", 0.0), ("inf", 0.0), ("x", 0.0)],
)
def test_float_is_safe(value, expected):
    assert import_data._float(value) == expected


def test_choice_falls_back_for_unknown_values():
    assert import_data._choice("now", ("now", "next"), "next") == "now"
    assert import_data._choice("someday", ("now", "next"), "next") == "next"
    assert import_data._choice(None, ("now",), "now") == "now"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), ("yes", True), ("ON", True), ("1", True), ("no", False), (0, False)],
)
def test_flag_parses_booleans(value, expected):
    assert import_data._flag(value) is expected


def test_day_parses_iso_dates_and_rejects_junk():
    assert import_data._day("2026-05-04") == date(2026, 5, 4)
    assert import_data._day("2026-05-04T09:00:00Z") == date(2026, 5, 4)
    assert import_data._day("not-a-date") is None
    assert import_data._day(None) is None


def test_moment_parses_offsets_and_assumes_utc():
    parsed = import_data._moment("2026-05-04T09:30:00Z")
    assert parsed == datetime(2026, 5, 4, 9, 30, tzinfo=timezone.utc)
    naive = import_data._moment("2026-05-04T09:30:00")
    assert naive.tzinfo == timezone.utc
    assert import_data._moment("junk") is None


def test_text_collapses_whitespace_and_clamps():
    assert import_data._text("  A\n\tnote  ", 20) == "A note"
    assert len(import_data._text("x" * 50, 10)) == 10


def test_full_round_trip_restores_every_entity(browser, db, monkeypatch, settings, tmp_path):
    venture_id = add_venture(
        browser,
        name="Sahaj",
        segment="Owner-run solar installers",
        market="Maharashtra installs are growing",
        alternatives="Notebooks",
        differentiation="Solar-specific job list",
    )
    add_canvas(browser, venture_id, block="problem", title="Job books lose money", detail="Missed follow-ups")
    add_swot(browser, venture_id, quadrant="threat", text="An incumbent bundles it", impact="5", evidence="Pricing page")
    add_stream(browser, venture_id, name="Subscription", price="1499", unit="per month", volume="40", confidence="high")
    add_cost(browser, venture_id, name="Support", amount="18000", kind="fixed")
    add_milestone(browser, venture_id, title="Ten installers", success_criterion="Ten accounts", owner="Swayam")
    add_kpi(browser, venture_id, name="Activated installers", unit="installers", target="40")
    add_reading(browser, 1, value="12", note="First week")
    browser.post(f"/ventures/{venture_id}/brief")

    payload = export_of(browser)
    path = write_payload(tmp_path, payload)
    assert browser.post(f"/ventures/{venture_id}/delete", {"confirm": "Sahaj"}).status_code == 303
    db.expire_all()
    assert db.scalar(select(Venture)) is None

    assert run_import(monkeypatch, settings, path) == 0
    db.expire_all()
    venture = db.scalar(select(Venture))
    assert venture is not None
    assert venture.name == "Sahaj"
    assert venture.segment == "Owner-run solar installers"
    assert venture.narrative_source == "local"
    assert venture.narrative
    assert len(db.scalars(select(CanvasEntry)).all()) == 1
    assert len(db.scalars(select(SwotItem)).all()) == 1
    assert db.scalar(select(RevenueStream)).price == 1499
    assert db.scalar(select(CostLine)).amount == 18000
    assert db.scalar(select(Milestone)).title == "Ten installers"
    kpi = db.scalar(select(Kpi))
    assert kpi.name == "Activated installers"
    assert kpi.target == 40
    reading = db.scalar(select(KpiReading))
    assert reading.value == 12
    assert reading.note == "First week"


def test_a_second_import_skips_existing_ventures(browser, db, monkeypatch, settings, tmp_path):
    venture_id = add_venture(browser, name="Sahaj")
    add_canvas(browser, venture_id, title="A real problem")
    path = write_payload(tmp_path, export_of(browser))
    assert run_import(monkeypatch, settings, path) == 0
    assert run_import(monkeypatch, settings, path) == 0
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Venture)) == 1
    assert db.scalar(select(func.count()).select_from(CanvasEntry)) == 1


def test_a_dry_run_writes_nothing(browser, db, monkeypatch, settings, tmp_path):
    venture_id = add_venture(browser, name="Sahaj")
    add_canvas(browser, venture_id, title="A real problem")
    path = write_payload(tmp_path, export_of(browser))
    browser.post(f"/ventures/{venture_id}/delete", {"confirm": "Sahaj"})
    assert run_import(monkeypatch, settings, path, dry_run=True) == 0
    db.expire_all()
    assert db.scalar(select(Venture)) is None
    assert db.scalar(select(CanvasEntry)) is None


def test_import_requires_an_existing_account(browser, monkeypatch, settings, tmp_path):
    path = write_payload(tmp_path, {"format": "keystone-export-v1", "ventures": []})
    with pytest.raises(SystemExit):
        run_import(monkeypatch, settings, path, email="nobody@example.com")


def test_import_clamps_and_skips_invalid_entries(browser, db, monkeypatch, settings, tmp_path):
    payload = {
        "format": "keystone-export-v1",
        "ventures": [
            {
                "name": "  Imported  ",
                "stage": "someday",
                "currency": "XYZ",
                "narrative_source": "robot",
                "canvas": [
                    {"block": "problem", "title": "A real note"},
                    {"block": "nonsense", "title": "Wrong block"},
                    {"block": "value", "title": ""},
                    "not a dict",
                ],
                "swot": [
                    {"quadrant": "threat", "text": "A real threat", "impact": "99"},
                    {"quadrant": "neutral", "text": "Wrong quadrant"},
                    {"quadrant": "weakness", "text": ""},
                ],
                "streams": [
                    {"name": "Plan", "price": "-5", "volume": "lots", "confidence": "certain", "model": "barter"},
                    {"name": "", "price": "10"},
                ],
                "costs": [
                    {"name": "Hosting", "amount": "-50", "kind": "surprise"},
                    {"name": "", "amount": "10"},
                ],
                "milestones": [
                    {"title": "Dated", "due_date": "junk", "status": "done", "completed_at": "2026-05-04T09:00:00Z"},
                    {"title": "", "due_date": "2026-05-04"},
                    "not a dict",
                ],
                "kpis": [
                    {
                        "name": "Activated installers",
                        "baseline": "0",
                        "target": "40",
                        "direction": "sideways",
                        "cadence": "hourly",
                        "readings": [
                            {"value": "5", "recorded_on": "2026-05-01"},
                            {"value": "9", "recorded_on": "2026-05-01"},
                            {"value": "junk", "recorded_on": "junk"},
                        ],
                    },
                    {"name": ""},
                ],
            },
            {"name": " ", "canvas": []},
            "not a venture",
        ],
    }
    path = write_payload(tmp_path, payload)
    assert run_import(monkeypatch, settings, path) == 0
    db.expire_all()
    venture = db.scalar(select(Venture))
    assert venture.name == "Imported"
    assert venture.stage == "idea"
    assert venture.currency == "INR"
    assert venture.narrative_source == "local"
    assert db.scalar(select(func.count()).select_from(CanvasEntry)) == 1
    assert db.scalar(select(func.count()).select_from(SwotItem)) == 1
    assert db.scalar(select(SwotItem)).impact == 5
    stream = db.scalar(select(RevenueStream))
    assert (stream.price, stream.volume, stream.model, stream.confidence) == (0, 0, "subscription", "medium")
    cost = db.scalar(select(CostLine))
    assert (cost.amount, cost.kind) == (0, "fixed")
    milestone = db.scalar(select(Milestone))
    assert milestone.due_date is None
    assert milestone.status == "done"
    assert milestone.completed_at is not None
    kpi = db.scalar(select(Kpi))
    assert (kpi.direction, kpi.cadence) == ("up", "monthly")
    assert db.scalar(select(func.count()).select_from(KpiReading)) == 1


def test_import_creates_nothing_when_the_document_has_no_ventures(browser, db, monkeypatch, settings, tmp_path):
    path = write_payload(tmp_path, {"format": "keystone-export-v1", "ventures": []})
    assert run_import(monkeypatch, settings, path) == 0
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Venture)) == 0


def test_import_keeps_mixed_currencies_separate(browser, db, monkeypatch, settings, tmp_path):
    payload = {
        "format": "keystone-export-v1",
        "ventures": [
            {"name": "Rupees", "currency": "INR", "streams": [{"name": "Plan", "price": "1000", "volume": "10"}]},
            {"name": "Dollars", "currency": "USD", "streams": [{"name": "Plan", "price": "100", "volume": "10"}]},
        ],
    }
    path = write_payload(tmp_path, payload)
    assert run_import(monkeypatch, settings, path) == 0
    db.expire_all()
    ventures = {v.name: v for v in db.scalars(select(Venture)).all()}
    assert ventures["Rupees"].currency == "INR"
    assert ventures["Dollars"].currency == "USD"
    assert db.scalar(select(func.count()).select_from(RevenueStream)) == 2


def test_import_is_scoped_to_the_named_account(browser, make_browser, db, monkeypatch, settings, tmp_path):
    add_venture(browser, name="Mine")
    path = write_payload(tmp_path, export_of(browser))
    other = make_browser().register(email="other@example.com", name="Other")
    assert run_import(monkeypatch, settings, path, email="other@example.com") == 0
    db.expire_all()
    mine = db.scalar(select(User).where(User.email == "swayam@example.com"))
    theirs = db.scalar(select(User).where(User.email == "other@example.com"))
    assert db.scalar(select(func.count()).select_from(Venture).where(Venture.user_id == mine.id)) == 1
    assert db.scalar(select(func.count()).select_from(Venture).where(Venture.user_id == theirs.id)) == 1
