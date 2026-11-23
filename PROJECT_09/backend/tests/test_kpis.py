from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Kpi, KpiReading
from app.services.kpis import (
    expected_progress,
    item,
    latest_reading,
    ordered_readings,
    progress,
    sparkline,
    status_for,
    summary,
)
from conftest import add_kpi, add_reading, add_venture, ist_today


class FakeReading:
    def __init__(self, value, day, id=1, note=""):
        self.value, self.recorded_on, self.id, self.note = value, day, id, note


class FakeKpi:
    def __init__(
        self,
        baseline=0.0,
        target=100.0,
        direction="up",
        target_date=None,
        created_days_ago=0,
        readings=None,
        name="KPI",
        unit="",
        cadence="monthly",
        id=1,
    ):
        today = ist_today()
        self.baseline, self.target, self.direction = baseline, target, direction
        self.target_date = target_date
        self.created_at = __import__("datetime").datetime.combine(
            today - timedelta(days=created_days_ago), __import__("datetime").time.min
        ).replace(tzinfo=__import__("datetime").timezone.utc)
        self.readings, self.name, self.unit, self.cadence = readings or [], name, unit, cadence
        self.id = id


def test_progress_upwards():
    assert progress(FakeKpi(baseline=0, target=100), 25) == 25.0
    assert progress(FakeKpi(baseline=0, target=100), 100) == 100.0


def test_progress_is_clamped_to_zero_and_hundred():
    assert progress(FakeKpi(baseline=10, target=20), 0) == 0.0
    assert progress(FakeKpi(baseline=10, target=20), 60) == 100.0


def test_progress_downwards():
    assert progress(FakeKpi(baseline=6, target=2, direction="down"), 4) == 50.0
    assert progress(FakeKpi(baseline=6, target=2, direction="down"), 1) == 100.0


def test_progress_with_no_reading_is_none():
    assert progress(FakeKpi(), None) is None


def test_progress_with_an_equal_target():
    assert progress(FakeKpi(baseline=5, target=5), 5) == 100.0
    assert progress(FakeKpi(baseline=5, target=5), 4) == 0.0


def test_expected_progress_without_a_date_is_none():
    assert expected_progress(FakeKpi(), ist_today()) is None


def test_expected_progress_is_zero_on_day_one():
    kpi = FakeKpi(target_date=ist_today() + timedelta(days=30), created_days_ago=0)
    assert expected_progress(kpi, ist_today()) == 0.0


def test_expected_progress_reaches_hundred_after_the_date():
    kpi = FakeKpi(target_date=ist_today() - timedelta(days=5), created_days_ago=40)
    assert expected_progress(kpi, ist_today()) == 100.0


def test_expected_progress_is_linear():
    kpi = FakeKpi(target_date=ist_today(), created_days_ago=100)
    assert expected_progress(kpi, ist_today()) == 100.0


def test_latest_reading_is_the_most_recent_day():
    today = ist_today()
    kpi = FakeKpi(readings=[FakeReading(1, today - timedelta(days=2), 1), FakeReading(9, today, 2)])
    assert latest_reading(kpi).value == 9


def test_latest_reading_handles_none():
    assert latest_reading(FakeKpi()) is None


def test_ordered_readings_sort_by_day():
    today = ist_today()
    kpi = FakeKpi(readings=[FakeReading(9, today, 2), FakeReading(1, today - timedelta(days=2), 1)])
    assert [r.value for r in ordered_readings(kpi)] == [1, 9]


def test_status_without_a_reading_is_no_data():
    key, detail = status_for(FakeKpi(), ist_today())
    assert key == "no_data"
    assert detail["progress"] is None


def test_status_reached_at_the_target():
    today = ist_today()
    kpi = FakeKpi(baseline=0, target=100, readings=[FakeReading(100, today)])
    assert status_for(kpi, today)[0] == "reached"


def test_status_missed_after_the_target_date():
    today = ist_today()
    kpi = FakeKpi(
        baseline=0,
        target=100,
        target_date=today - timedelta(days=1),
        created_days_ago=10,
        readings=[FakeReading(40, today)],
    )
    assert status_for(kpi, today)[0] == "missed"


def test_status_ahead_of_pace():
    today = ist_today()
    kpi = FakeKpi(
        baseline=0,
        target=100,
        target_date=today + timedelta(days=20),
        created_days_ago=80,
        readings=[FakeReading(100, today)],
    )
    assert status_for(kpi, today)[0] == "reached"


def test_status_behind_pace():
    today = ist_today()
    kpi = FakeKpi(
        baseline=0,
        target=100,
        target_date=today + timedelta(days=20),
        created_days_ago=80,
        readings=[FakeReading(20, today)],
    )
    key, detail = status_for(kpi, today)
    assert key == "behind"
    assert detail["delta"] == pytest.approx(20.0 - 80.0, abs=0.11)


def test_status_on_track_within_ten_points():
    today = ist_today()
    kpi = FakeKpi(
        baseline=0,
        target=100,
        target_date=today + timedelta(days=20),
        created_days_ago=80,
        readings=[FakeReading(75, today)],
    )
    assert status_for(kpi, today)[0] == "on_track"


def test_status_without_a_date_uses_the_midpoint_rule():
    today = ist_today()
    assert status_for(FakeKpi(readings=[FakeReading(60, today)]), today)[0] == "on_track"
    assert status_for(FakeKpi(readings=[FakeReading(40, today)]), today)[0] == "behind"


def test_sparkline_needs_two_readings():
    today = ist_today()
    assert sparkline([FakeReading(1, today)]) is None
    assert sparkline([]) is None


def test_sparkline_makes_points_for_each_reading():
    today = ist_today()
    readings = [FakeReading(1, today - timedelta(days=2)), FakeReading(3, today - timedelta(days=1)), FakeReading(2, today)]
    result = sparkline(readings)
    assert result["width"] == 132
    assert len(result["points"].split()) == 3
    assert result["low"] == 1 and result["high"] == 3


def test_sparkline_handles_a_flat_line():
    today = ist_today()
    result = sparkline([FakeReading(5, today - timedelta(days=1)), FakeReading(5, today)])
    ys = [float(point.split(",")[1]) for point in result["points"].split()]
    assert ys[0] == ys[1]


def test_summary_computes_health():
    today = ist_today()
    kpis = [
        FakeKpi(name="A", baseline=0, target=100, readings=[FakeReading(100, today)], id=1),
        FakeKpi(name="B", baseline=0, target=100, readings=[FakeReading(90, today)], id=2),
        FakeKpi(name="C", id=3),
    ]
    result = summary(kpis, today)
    assert result["total"] == 3
    assert result["measured"] == 2
    assert result["healthy"] == 2
    assert result["health_percent"] == 100
    assert result["counts"]["no_data"] == 1


def test_summary_attention_lists_missed_before_behind():
    today = ist_today()
    kpis = [
        FakeKpi(name="Behind", baseline=0, target=100, target_date=today + timedelta(days=20), created_days_ago=80, readings=[FakeReading(20, today)], id=1),
        FakeKpi(name="Missed", baseline=0, target=100, target_date=today - timedelta(days=1), created_days_ago=80, readings=[FakeReading(20, today)], id=2),
    ]
    result = summary(kpis, today)
    assert [row["kpi"].name for row in result["attention"]] == ["Missed", "Behind"]


def test_item_carries_the_label_and_spark():
    today = ist_today()
    kpi = FakeKpi(readings=[FakeReading(1, today - timedelta(days=1)), FakeReading(2, today)])
    row = item(kpi, today)
    assert row["status_label"]
    assert row["spark"] is not None


def test_kpi_page_shows_the_plan(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, name="Activated installers", unit="installers", target="40")
    text = browser.get(f"/ventures/{venture_id}/kpis").text
    assert "Activated installers" in text
    assert "No readings" in text
    assert "Higher is better" in text


def test_add_kpi_stores_the_values(browser, db):
    venture_id = add_venture(browser)
    due = ist_today() + timedelta(days=90)
    r = add_kpi(
        browser,
        venture_id,
        name="Activated installers",
        unit="installers",
        baseline="0",
        target="40",
        target_date=due,
        cadence="weekly",
    )
    assert r == f"/ventures/{venture_id}/kpis"
    kpi = db.scalar(select(Kpi))
    assert kpi.name == "Activated installers"
    assert kpi.baseline == 0
    assert kpi.target == 40
    assert kpi.target_date == due
    assert kpi.cadence == "weekly"


def test_kpi_name_is_required(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/kpis", {"name": "x", "baseline": "0", "target": "1"})
    assert r.status_code == 422
    assert db.scalars(select(Kpi)).all() == []


def test_kpi_baseline_and_target_must_be_numbers(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/kpis", {"name": "Real name", "baseline": "abc", "target": "10"})
    assert r.status_code == 422
    assert "must both be numbers" in r.text


def test_kpi_target_must_differ_from_the_baseline(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/kpis", {"name": "Flat", "baseline": "5", "target": "5"})
    assert r.status_code == 422
    assert "must differ" in r.text


def test_an_unknown_direction_falls_back_to_up(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, direction="sideways")
    assert db.scalar(select(Kpi)).direction == "up"


def test_an_unknown_cadence_falls_back_to_monthly(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, cadence="hourly")
    assert db.scalar(select(Kpi)).cadence == "monthly"


def test_edit_kpi_updates_the_plan(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, name="Old", baseline="0", target="10")
    r = browser.post(
        "/kpis/1/edit",
        {
            "name": "New",
            "unit": "users",
            "direction": "down",
            "baseline": "100",
            "target": "10",
            "target_date": (ist_today() + timedelta(days=30)).isoformat(),
            "cadence": "quarterly",
        },
    )
    assert r.status_code == 303
    kpi = db.scalar(select(Kpi))
    assert kpi.name == "New"
    assert kpi.direction == "down"
    assert kpi.baseline == 100
    assert kpi.target == 10
    assert kpi.cadence == "quarterly"


def test_edit_kpi_rejects_a_blank_name(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, name="Keep")
    r = browser.post("/kpis/1/edit", {"name": "", "baseline": "0", "target": "10"})
    assert r.status_code == 422
    assert db.scalar(select(Kpi)).name == "Keep"


def test_delete_kpi_removes_its_readings(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="5")
    r = browser.post("/kpis/1/delete")
    assert r.status_code == 303
    assert db.scalars(select(Kpi)).all() == []
    assert db.scalars(select(KpiReading)).all() == []


def test_add_reading_stores_a_value(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    r = add_reading(browser, 1, value="12.5", note="First week")
    assert r == f"/ventures/{venture_id}/kpis?saved=1"
    reading = db.scalar(select(KpiReading))
    assert reading.value == 12.5
    assert reading.note == "First week"
    assert reading.recorded_on == ist_today()


def test_a_second_reading_on_the_same_day_replaces_the_first(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="10")
    add_reading(browser, 1, value="14", note="Corrected")
    readings = db.scalars(select(KpiReading)).all()
    assert len(readings) == 1
    assert readings[0].value == 14
    assert readings[0].note == "Corrected"


def test_a_reading_needs_a_number(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    r = browser.post("/kpis/1/readings", {"value": "lots", "recorded_on": ""})
    assert r.status_code == 422
    assert "needs a number" in r.text
    assert db.scalars(select(KpiReading)).all() == []


def test_a_future_reading_is_rejected(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    r = browser.post(
        "/kpis/1/readings",
        {"value": "10", "recorded_on": (ist_today() + timedelta(days=1)).isoformat()},
    )
    assert r.status_code == 422
    assert "cannot be dated in the future" in r.text


def test_a_reading_can_be_backdated(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    day = ist_today() - timedelta(days=14)
    add_reading(browser, 1, value="6", recorded_on=day)
    assert db.scalar(select(KpiReading)).recorded_on == day


def test_delete_reading(browser, db):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="5")
    r = browser.post("/readings/1/delete")
    assert r.status_code == 303
    assert db.scalars(select(KpiReading)).all() == []


def test_reading_edit_link_is_not_offered(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    text = browser.get(f"/ventures/{venture_id}/kpis").text
    assert "Record" in text


def test_kpi_pages_are_owner_scoped(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="5")
    other = make_browser().register(email="kpi-other@example.com", name="Other")
    assert other.post("/kpis/1/edit", {"name": "Stolen", "baseline": "0", "target": "1"}).status_code == 404
    assert other.post("/kpis/1/readings", {"value": "1"}).status_code == 404
    assert other.post("/readings/1/delete").status_code == 404
    assert other.post("/kpis/1/delete").status_code == 404


def test_kpi_page_shows_a_reading_and_the_pace(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, target="100", target_date=ist_today() + timedelta(days=30))
    add_reading(browser, 1, value="25")
    text = browser.get(f"/ventures/{venture_id}/kpis").text
    assert "25" in text
    assert "of the gap closed" in text
    assert "expected" in text


def test_a_sparkline_appears_after_two_readings(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id)
    add_reading(browser, 1, value="5", recorded_on=ist_today() - timedelta(days=7))
    add_reading(browser, 1, value="9", recorded_on=ist_today())
    text = browser.get(f"/ventures/{venture_id}/kpis").text
    assert "<polyline" in text
    assert "2 readings" in text


def test_kpi_page_marks_reached(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, baseline="0", target="10")
    add_reading(browser, 1, value="10")
    assert "Reached" in browser.get(f"/ventures/{venture_id}/kpis").text


def test_overview_lists_the_kpis(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, name="Jobs scheduled", target="400")
    text = browser.get(f"/ventures/{venture_id}").text
    assert "Jobs scheduled" in text
    assert "no reading" in text


def test_empty_kpi_page_asks_for_three_numbers(browser):
    venture_id = add_venture(browser)
    text = browser.get(f"/ventures/{venture_id}/kpis").text
    assert "Pick three numbers" in text
    assert "Demand, conversion and retention" in text


def test_kpi_edit_form_prefills(browser):
    venture_id = add_venture(browser)
    add_kpi(browser, venture_id, name="Setup hours", unit="hours", baseline="6", target="2", direction="down")
    r = browser.get(f"/ventures/{venture_id}/kpis?edit=1")
    assert 'value="Setup hours"' in r.text
    assert "Edit KPI" in r.text
