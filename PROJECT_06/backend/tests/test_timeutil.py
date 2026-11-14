from __future__ import annotations

from datetime import date, timedelta

from app.timeutil import is_valid_timezone, parse_attendees, relative_day, zone


def test_relative_day_understands_common_phrases():
    today = date(2026, 11, 12)  # Thursday
    assert relative_day("today", today) == today
    assert relative_day("EOD", today) == today
    assert relative_day("tomorrow", today) == today + timedelta(days=1)
    assert relative_day("next week", today) == today + timedelta(days=7)
    assert relative_day("in a week", today) == today + timedelta(days=7)


def test_relative_day_parses_iso_dates():
    assert relative_day("2026-11-20", date(2026, 11, 12)) == date(2026, 11, 20)
    assert relative_day("2026-02-30", date(2026, 11, 12)) is None
    assert relative_day("20/11/2026", date(2026, 11, 12)) is None


def test_relative_day_takes_the_next_weekday_not_today():
    thursday = date(2026, 11, 12)
    assert relative_day("Friday", thursday) == date(2026, 11, 13)
    assert relative_day("by monday", thursday) == date(2026, 11, 16)
    # The same weekday means next week, not zero days ahead.
    assert relative_day("Thursday", thursday) == date(2026, 11, 19)


def test_relative_day_returns_none_for_unknown_text():
    assert relative_day("", date(2026, 11, 12)) is None
    assert relative_day("soon", date(2026, 11, 12)) is None
    assert relative_day("when the client replies", date(2026, 11, 12)) is None


def test_parse_attendees_splits_and_cleans():
    assert parse_attendees("Priya, Arjun; Meera\nDev") == ["Priya", "Arjun", "Meera", "Dev"]
    assert parse_attendees(" @Priya , @arjun ") == ["Priya", "arjun"]


def test_parse_attendees_drops_blank_and_overlong_names():
    assert parse_attendees("Priya,, ,Arjun") == ["Priya", "Arjun"]
    assert parse_attendees("x" * 90) == []


def test_parse_attendees_keeps_order_and_caps_the_list():
    raw = ",".join(f"Person {i}" for i in range(40))
    people = parse_attendees(raw)
    assert len(people) == 30
    assert people[0] == "Person 0"
    assert people[-1] == "Person 29"


def test_parse_attendees_drops_case_insensitive_duplicates():
    assert parse_attendees("Priya, priya, PRIYA") == ["Priya"]


def test_zone_falls_back_to_utc_for_invalid_names():
    assert str(zone("Not/AZone")) == "UTC"
    assert str(zone("")) == "UTC"
    assert str(zone("Asia/Kolkata")) == "Asia/Kolkata"


def test_date_formats_are_short_and_readable():
    from app.web import _date

    day = date(2026, 11, 12)
    assert _date(day) == "12 Nov"
    assert _date(day, "long") == "12 Nov 2026"
    assert _date(day, "weekday") == "Thu 12 Nov"
    assert _date(day, "day") == "Thu"
    assert _date(day, "month") == "November 2026"
    assert _date(None) == "No date"


def test_timezone_validation():
    assert is_valid_timezone("Asia/Kolkata")
    assert is_valid_timezone("Europe/London")
    assert not is_valid_timezone("Mars/Olympus")
    assert not is_valid_timezone("")
