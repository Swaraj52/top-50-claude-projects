from __future__ import annotations

import math

import pytest
from sqlalchemy import select

from app.models import CostLine, RevenueStream
from app.services.finance import SCENARIOS, by_model, cost_totals, scenario_table, stream_expected, summary, weighted_revenue
from conftest import add_cost, add_stream, add_venture


class FakeStream:
    def __init__(self, price, volume, confidence="medium", model="subscription", name="Stream", id=1):
        self.price, self.volume, self.confidence = price, volume, confidence
        self.model, self.name, self.id = model, name, id


class FakeCost:
    def __init__(self, amount, kind="fixed", name="Cost", id=1):
        self.amount, self.kind, self.name, self.id = amount, kind, name, id


def test_stream_expected_is_price_times_volume():
    assert stream_expected(FakeStream(1499, 40)) == 59960


def test_stream_expected_never_goes_negative():
    assert stream_expected(FakeStream(-10, 5)) == 0
    assert stream_expected(FakeStream(10, -5)) == 0


def test_weighted_revenue_uses_confidence():
    streams = [
        FakeStream(1000, 10, confidence="high"),
        FakeStream(1000, 10, confidence="medium"),
        FakeStream(1000, 10, confidence="low"),
    ]
    # 10000 + 7000 + 4000
    assert weighted_revenue(streams) == 21000


def test_cost_totals_split_fixed_and_variable():
    fixed, variable = cost_totals([FakeCost(18000, "fixed"), FakeCost(5500, "variable"), FakeCost(2400, "variable")])
    assert fixed == 18000
    assert variable == 7900


def test_summary_computes_the_base_case():
    streams = [FakeStream(1499, 40, confidence="high"), FakeStream(6000, 3, confidence="medium")]
    costs = [FakeCost(18000), FakeCost(7900, "variable")]
    result = summary(streams, costs)
    assert result["expected_mrr"] == 1499 * 40 + 6000 * 3
    assert result["arr"] == result["expected_mrr"] * 12
    assert result["volume"] == 43
    assert result["total_cost"] == 25900
    assert result["margin"] == result["expected_mrr"] - 25900
    assert result["scenario"] == "base"
    assert result["scenario_factor"] == 1.0
    assert result["costed"] is True


def test_summary_margin_percent_rounds():
    streams = [FakeStream(100, 10)]
    costs = [FakeCost(500)]
    result = summary(streams, costs)
    assert result["margin"] == 500
    assert result["margin_percent"] == 50


def test_summary_without_revenue_has_no_margin_percent():
    result = summary([], [FakeCost(1000)])
    assert result["expected_mrr"] == 0
    assert result["margin"] == -1000
    assert result["margin_percent"] is None
    assert result["breakeven_units"] is None
    assert result["costed"] is False


def test_summary_blended_price_and_breakeven():
    streams = [FakeStream(100, 10), FakeStream(50, 10)]
    costs = [FakeCost(900)]
    result = summary(streams, costs)
    assert result["blended_price"] == 75.0
    assert result["breakeven_units"] == math.ceil(900 / 75.0) == 12


def test_conservative_and_upside_scale_volume():
    streams = [FakeStream(100, 10)]
    costs = [FakeCost(200)]
    conservative = summary(streams, costs, scenario="conservative")
    upside = summary(streams, costs, scenario="upside")
    assert conservative["revenue"] == 700
    assert conservative["margin"] == 500
    assert upside["revenue"] == 1400
    assert upside["margin"] == 1200


def test_an_unknown_scenario_falls_back_to_base():
    result = summary([FakeStream(100, 10)], [], scenario="wishful")
    assert result["scenario_factor"] == 1.0
    assert result["revenue"] == 1000


def test_scenario_table_has_three_cases():
    rows = scenario_table([FakeStream(100, 10)], [FakeCost(200)])
    assert [row["key"] for row in rows] == ["conservative", "base", "upside"]
    assert [row["factor"] for row in rows] == [0.7, 1.0, 1.4]
    assert rows[0]["revenue"] == 700
    assert rows[2]["revenue"] == 1400


def test_by_model_groups_and_sorts():
    rows = by_model(
        [
            FakeStream(100, 10, model="subscription", name="A"),
            FakeStream(300, 10, model="one_off", name="B"),
            FakeStream(50, 10, model="subscription", name="C"),
        ]
    )
    assert [row["model"] for row in rows] == ["one_off", "subscription"]
    assert rows[0]["amount"] == 3000
    assert rows[1]["amount"] == 1500
    assert sum(row["share"] for row in rows) == 100


def test_by_model_handles_an_empty_model():
    assert by_model([]) == []


def test_revenue_page_shows_the_summary(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, price="1499", volume="40")
    add_cost(browser, venture_id, amount="25900")
    text = browser.get(f"/ventures/{venture_id}/revenue").text
    assert "Base MRR" in text
    assert "₹59,960" in text
    assert "₹1,499" in text


def test_add_stream_stores_the_values(browser, db):
    venture_id = add_venture(browser)
    r = add_stream(
        browser,
        venture_id,
        name="Migration",
        model="one_off",
        price="6000",
        unit="per account",
        volume="3",
        confidence="medium",
        notes="First ten only",
    )
    assert r == f"/ventures/{venture_id}/revenue#streams"
    stream = db.scalar(select(RevenueStream))
    assert stream.name == "Migration"
    assert stream.model == "one_off"
    assert stream.price == 6000
    assert stream.volume == 3
    assert stream.unit == "per account"
    assert stream.confidence == "medium"


def test_stream_name_is_required(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/revenue/streams", {"name": " ", "price": "10"})
    assert r.status_code == 422
    assert db.scalars(select(RevenueStream)).all() == []


def test_negative_price_and_volume_are_clamped(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, price="-100", volume="-5")
    stream = db.scalar(select(RevenueStream))
    assert stream.price == 0
    assert stream.volume == 0


def test_an_unknown_model_falls_back(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, model="barter")
    assert db.scalar(select(RevenueStream)).model == "subscription"


def test_an_unknown_confidence_falls_back(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, confidence="certain")
    assert db.scalar(select(RevenueStream)).confidence == "medium"


def test_a_blank_unit_gets_the_default(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, unit="")
    assert db.scalar(select(RevenueStream)).unit == "per month"


def test_edit_stream_updates_the_row(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, name="Old", price="100", volume="1")
    r = browser.post(
        "/streams/1/edit",
        {
            "name": "New",
            "model": "usage",
            "price": "250",
            "unit": "per seat",
            "volume": "8",
            "confidence": "low",
            "notes": "Changed",
        },
    )
    assert r.status_code == 303
    stream = db.scalar(select(RevenueStream))
    assert stream.name == "New"
    assert stream.model == "usage"
    assert stream.price == 250
    assert stream.volume == 8
    assert stream.confidence == "low"


def test_edit_stream_rejects_a_blank_name(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, name="Keep")
    r = browser.post("/streams/1/edit", {"name": ""})
    assert r.status_code == 422
    assert db.scalar(select(RevenueStream)).name == "Keep"


def test_delete_stream(browser, db):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id)
    r = browser.post("/streams/1/delete")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/revenue#streams"
    assert db.scalars(select(RevenueStream)).all() == []


def test_add_cost_stores_the_values(browser, db):
    venture_id = add_venture(browser)
    r = add_cost(browser, venture_id, name="Hosting", amount="5500", kind="variable", notes="Grows with jobs")
    assert r == f"/ventures/{venture_id}/revenue#costs"
    cost = db.scalar(select(CostLine))
    assert cost.name == "Hosting"
    assert cost.amount == 5500
    assert cost.kind == "variable"


def test_cost_name_is_required(browser, db):
    venture_id = add_venture(browser)
    r = browser.post(f"/ventures/{venture_id}/revenue/costs", {"name": "", "amount": "10"})
    assert r.status_code == 422
    assert db.scalars(select(CostLine)).all() == []


def test_an_unknown_cost_kind_falls_back_to_fixed(browser, db):
    venture_id = add_venture(browser)
    add_cost(browser, venture_id, kind="surprise")
    assert db.scalar(select(CostLine)).kind == "fixed"


def test_negative_cost_is_clamped(browser, db):
    venture_id = add_venture(browser)
    add_cost(browser, venture_id, amount="-50")
    assert db.scalar(select(CostLine)).amount == 0


def test_edit_cost_updates_the_row(browser, db):
    venture_id = add_venture(browser)
    add_cost(browser, venture_id, name="Old", amount="10")
    r = browser.post("/costs/1/edit", {"name": "New", "amount": "99", "kind": "variable", "notes": "N"})
    assert r.status_code == 303
    cost = db.scalar(select(CostLine))
    assert (cost.name, cost.amount, cost.kind) == ("New", 99, "variable")


def test_edit_cost_rejects_a_blank_name(browser, db):
    venture_id = add_venture(browser)
    add_cost(browser, venture_id, name="Keep")
    r = browser.post("/costs/1/edit", {"name": ""})
    assert r.status_code == 422
    assert db.scalar(select(CostLine)).name == "Keep"


def test_delete_cost(browser, db):
    venture_id = add_venture(browser)
    add_cost(browser, venture_id)
    r = browser.post("/costs/1/delete")
    assert r.status_code == 303
    assert r.headers["location"] == f"/ventures/{venture_id}/revenue#costs"
    assert db.scalars(select(CostLine)).all() == []


def test_finance_is_owner_scoped(browser, make_browser):
    venture_id = add_venture(browser, name="Mine")
    add_stream(browser, venture_id)
    add_cost(browser, venture_id)
    other = make_browser().register(email="money-other@example.com", name="Other")
    assert other.post("/streams/1/edit", {"name": "Stolen"}).status_code == 404
    assert other.post("/costs/1/edit", {"name": "Stolen"}).status_code == 404
    assert other.post("/streams/1/delete").status_code == 404
    assert other.post("/costs/1/delete").status_code == 404


def test_scenario_switch_changes_the_strip(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, price="1000", volume="10")
    add_cost(browser, venture_id, amount="500")
    base = browser.get(f"/ventures/{venture_id}/revenue?scenario=base").text
    upside = browser.get(f"/ventures/{venture_id}/revenue?scenario=upside").text
    assert ">₹10,000</strong>" in base
    assert ">₹10,000</td>" in base
    assert ">₹14,000</td>" in upside
    assert ">₹13,500</td>" in upside


def test_an_unknown_scenario_renders_base(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, price="1000", volume="10")
    r = browser.get(f"/ventures/{venture_id}/revenue?scenario=nonsense")
    assert r.status_code == 200
    assert "₹10,000" in r.text


def test_the_scenario_table_is_always_shown(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, price="1000", volume="10")
    add_cost(browser, venture_id, amount="500")
    text = browser.get(f"/ventures/{venture_id}/revenue").text
    assert "Conservative" in text and "Upside" in text
    assert "×0.7" in text and "×1.4" in text


def test_model_split_appears_with_streams(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, name="Subscription", model="subscription", price="100", volume="10")
    add_stream(browser, venture_id, name="Setup", model="one_off", price="500", volume="2")
    text = browser.get(f"/ventures/{venture_id}/revenue").text
    assert "Where the money comes from" in text
    assert "Subscription" in text and "One-off sale" in text


def test_confidence_chip_is_visible(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, confidence="low")
    text = browser.get(f"/ventures/{venture_id}/revenue").text
    assert "Low confidence" in text


def test_stream_edit_link_prefills(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, name="Installer subscription")
    r = browser.get(f"/ventures/{venture_id}/revenue?edit_stream=1")
    assert 'value="Installer subscription"' in r.text
    assert "Edit stream" in r.text


def test_cost_edit_link_prefills(browser):
    venture_id = add_venture(browser)
    add_cost(browser, venture_id, name="Support contractor")
    r = browser.get(f"/ventures/{venture_id}/revenue?edit_cost=1")
    assert 'value="Support contractor"' in r.text
    assert "Edit cost" in r.text


def test_overview_shows_arr_and_cost(browser):
    venture_id = add_venture(browser)
    add_stream(browser, venture_id, price="1000", volume="10")
    add_cost(browser, venture_id, amount="2000")
    text = browser.get(f"/ventures/{venture_id}").text
    assert "base ARR" in text
    assert "₹2,000 monthly cost" in text


def test_every_confidence_weight_is_used():
    from app.models import CONFIDENCE_WEIGHTS

    assert CONFIDENCE_WEIGHTS == {"high": 1.0, "medium": 0.7, "low": 0.4}
    assert [key for key, _label, _factor in SCENARIOS] == ["conservative", "base", "upside"]
