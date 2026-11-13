from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.models import Habit, HabitLog, Reflection
from app.services import habitmath

TODAY = date(2026, 11, 12)  # a Thursday


def make_habit(days: str = "0,1,2,3,4,5,6", created: date = date(2026, 11, 1)) -> Habit:
    return Habit(
        id=1,
        user_id=1,
        title="Read",
        intention="",
        cue="",
        days=days,
        status="active",
        created_at=datetime.combine(created, time(7), tzinfo=timezone.utc),
    )


def make_log(day: date, status: str = "done") -> HabitLog:
    return HabitLog(
        id=day.toordinal(),
        user_id=1,
        habit_id=1,
        day=day,
        status=status,
        note="",
        created_at=datetime.combine(day, time(20), tzinfo=timezone.utc),
    )


def days_back(*offsets: int) -> list[HabitLog]:
    return [make_log(TODAY - timedelta(days=offset)) for offset in offsets]


def test_streak_counts_consecutive_done_days():
    habit = make_habit()
    logs = days_back(0, 1, 2, 3, 4)
    assert habitmath.streak(habit, logs, TODAY) == 5


def test_streak_treats_planned_rest_as_neutral():
    habit = make_habit()
    logs = days_back(0, 1, 3, 4) + [make_log(TODAY - timedelta(days=2), "skipped")]
    assert habitmath.streak(habit, logs, TODAY) == 4


def test_streak_breaks_on_a_missing_scheduled_day():
    habit = make_habit()
    logs = days_back(0, 2, 3)
    assert habitmath.streak(habit, logs, TODAY) == 1


def test_streak_ignores_an_unlogged_today():
    habit = make_habit()
    logs = days_back(1, 2, 3, 4)
    assert habitmath.streak(habit, logs, TODAY) == 4


def test_streak_respects_the_schedule():
    habit = make_habit(days="0,2,4")  # Mon, Wed, Fri
    logs = [make_log(date(2026, 11, 9)), make_log(date(2026, 11, 11))]
    assert habitmath.streak(habit, logs, TODAY) == 2


def test_longest_streak_finds_the_best_run():
    habit = make_habit()
    logs = days_back(7, 6, 5) + days_back(2, 1, 0)
    assert habitmath.longest_streak(habit, logs, TODAY) == 3


def test_range_stats_counts_done_skipped_and_missed():
    habit = make_habit()
    logs = [
        make_log(TODAY - timedelta(days=4)),
        make_log(TODAY - timedelta(days=3)),
        make_log(TODAY - timedelta(days=2), "skipped"),
    ]
    stats = habitmath.range_stats(habit, logs, TODAY - timedelta(days=4), TODAY, TODAY)
    assert stats == {"scheduled": 5, "done": 2, "skipped": 1, "missed": 1, "rate": 67}


def test_range_stats_never_counts_today_as_missed():
    habit = make_habit()
    logs = [make_log(TODAY - timedelta(days=2)), make_log(TODAY - timedelta(days=1))]
    stats = habitmath.range_stats(habit, logs, TODAY - timedelta(days=2), TODAY, TODAY)
    assert stats["scheduled"] == 3
    assert stats["done"] == 2
    assert stats["missed"] == 0
    assert stats["rate"] == 100


def test_calendar_status_distinguishes_states():
    habit = make_habit(days="0,1,2,3,4")
    logs = [make_log(TODAY)]
    assert habitmath.calendar_status(habit, logs, TODAY, TODAY) == "done"
    assert habitmath.calendar_status(habit, logs, date(2026, 11, 11), TODAY) == "missed"
    assert habitmath.calendar_status(habit, logs, date(2026, 11, 14), TODAY) == "off"
    assert habitmath.calendar_status(habit, logs, date(2026, 11, 16), TODAY) == "future"


def test_calendar_status_marks_unlogged_today_as_pending():
    habit = make_habit()
    assert habitmath.calendar_status(habit, [], TODAY, TODAY) == "pending"
    # Yesterday stays missed; only today gets the open grace state.
    assert habitmath.calendar_status(habit, [], TODAY - timedelta(days=1), TODAY) == "missed"


def test_weekday_pattern_reports_rates():
    habit = make_habit()
    logs = days_back(0, 1, 2, 3, 4)
    pattern = habitmath.weekday_pattern([habit], {habit.id: logs}, TODAY, weeks=2)
    assert len(pattern) == 7
    assert all(row["scheduled"] >= 0 for row in pattern)
    assert sum(row["scheduled"] for row in pattern) > 0


def test_weekly_series_has_eight_points():
    habit = make_habit()
    series = habitmath.weekly_series([habit], {habit.id: days_back(0, 1, 2)}, TODAY, weeks=8)
    assert len(series["labels"]) == 8
    assert len(series["done"]) == 8
    assert series["done"][-1] == 3


def test_reflection_streak_counts_back_from_this_week():
    this_monday = TODAY - timedelta(days=TODAY.weekday())
    reflections = [
        Reflection(user_id=1, week_start=this_monday, mood=4, worked="", friction="", change="", created_at=datetime.now(timezone.utc)),
        Reflection(user_id=1, week_start=this_monday - timedelta(days=7), mood=3, worked="", friction="", change="", created_at=datetime.now(timezone.utc)),
        Reflection(user_id=1, week_start=this_monday - timedelta(days=14), mood=5, worked="", friction="", change="", created_at=datetime.now(timezone.utc)),
    ]
    assert habitmath.reflection_streak(reflections, TODAY) == 3


def test_reflection_streak_tolerates_an_open_current_week():
    this_monday = TODAY - timedelta(days=TODAY.weekday())
    reflections = [
        Reflection(user_id=1, week_start=this_monday - timedelta(days=7), mood=3, worked="", friction="", change="", created_at=datetime.now(timezone.utc)),
        Reflection(user_id=1, week_start=this_monday - timedelta(days=14), mood=3, worked="", friction="", change="", created_at=datetime.now(timezone.utc)),
    ]
    assert habitmath.reflection_streak(reflections, TODAY) == 2
