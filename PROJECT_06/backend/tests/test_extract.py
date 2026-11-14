from __future__ import annotations

from datetime import date, timedelta

from app.services.extract import extract

DAY = date(2026, 11, 12)  # a Thursday


def owners(extraction):
    return [(a.owner, a.title) for a in extraction.actions]


def test_sections_are_parsed():
    notes = """Weekly review

Attendees: Priya, Arjun

Summary: We reviewed the beta and the onboarding flow.

Decisions:
- Ship the beta on 1 December
- Keep pricing on one page

Action items:
- Priya will send the onboarding deck
"""
    result = extract(notes, "", DAY)
    assert result.summary.startswith("We reviewed the beta")
    assert result.decisions == ["Ship the beta on 1 December", "Keep pricing on one page"]
    assert owners(result) == [("Priya", "send the onboarding deck")]
    assert result.attendees == ["Priya", "Arjun"]


def test_inline_headers_do_not_leak_into_attendees():
    notes = """Attendees: Priya, Arjun
Summary: We agreed the launch is still on.
Decisions: Ship on 1 December
Actions: Priya will send the deck
"""
    result = extract(notes, "", DAY)
    assert result.attendees == ["Priya", "Arjun"]
    assert result.summary == "We agreed the launch is still on."
    assert result.decisions == ["Ship on 1 December"]
    assert owners(result) == [("Priya", "send the deck")]


def test_bullet_styles_are_stripped():
    notes = """Decisions:
* Use the blue theme
1. Keep the old logo
• Move the standup to 9:30

Actions:
1) Arjun will call the vendor
- @Meera update the roadmap
"""
    result = extract(notes, "", DAY)
    assert "Use the blue theme" in result.decisions
    assert "Keep the old logo" in result.decisions
    assert "Move the standup to 9:30" in result.decisions
    assert ("Arjun", "call the vendor") in owners(result)
    assert ("Meera", "update the roadmap") in owners(result)


def test_unsectioned_agreement_becomes_a_decision():
    notes = "We discussed pricing for a while. We agreed to keep the free tier."
    result = extract(notes, "", DAY)
    assert result.decisions == ["Keep the free tier."]


def test_decision_prefixes_are_removed():
    assert extract("Decision: Ship the beta", "", DAY).decisions == ["Ship the beta"]
    assert extract("Approved: the new budget", "", DAY).decisions == ["The new budget"]
    assert extract("We decided to postpone the launch", "", DAY).decisions == ["Postpone the launch"]
    assert extract("It was agreed the office closes on Friday", "", DAY).decisions == [
        "The office closes on Friday"
    ]


def test_action_prefixes_are_parsed():
    notes = """TODO: Priya to send the deck
Action: Arjun will book the room
Next step: ask legal about the contract
Follow-up: Meera will update the roadmap
"""
    result = extract(notes, "", DAY)
    assert ("Priya", "send the deck") in owners(result)
    assert ("Arjun", "book the room") in owners(result)
    assert any(title == "ask legal about the contract" for _, title in owners(result))
    assert ("Meera", "update the roadmap") in owners(result)


def test_follow_up_without_a_colon_keeps_the_phrase():
    result = extract("Actions:\n- Follow up with their security questionnaire", "", DAY)
    assert owners(result) == [("", "Follow up with their security questionnaire")]


def test_at_mentions_set_the_owner():
    result = extract("- @priya send the onboarding deck", "", DAY)
    assert owners(result) == [("priya", "send the onboarding deck")]
    assert "priya" in result.attendees


def test_owner_label_sets_the_owner():
    result = extract("- Prepare the deck | Owner: Meera", "Priya", DAY)
    assert owners(result) == [("Meera", "Prepare the deck")]


def test_will_phrase_sets_the_owner():
    result = extract("Arjun will draft the migration note", "", DAY)
    assert owners(result) == [("Arjun", "draft the migration note")]


def test_attendee_name_at_the_start_sets_the_owner():
    result = extract("- Meera to review the pricing page", "Meera, Arjun", DAY)
    assert owners(result) == [("Meera", "review the pricing page")]


def test_action_without_an_owner_stays_unassigned():
    result = extract("Actions:\n- Book the offsite venue", "", DAY)
    assert owners(result) == [("", "Book the offsite venue")]


def test_iso_due_date_is_parsed_and_removed():
    result = extract("- @Priya send the deck by 2026-11-20", "", DAY)
    assert result.actions[0].due_date == date(2026, 11, 20)
    assert result.actions[0].title == "send the deck"


def test_weekday_due_date_uses_the_meeting_day():
    result = extract("- @Priya send the deck by Friday", "", DAY)
    assert result.actions[0].due_date == date(2026, 11, 13)


def test_relative_due_dates_use_the_meeting_day():
    assert extract("- @Priya send the deck tomorrow", "", DAY).actions[0].due_date == DAY + timedelta(days=1)
    assert extract("- @Priya send the deck today", "", DAY).actions[0].due_date == DAY
    assert extract("- @Priya send the deck next week", "", DAY).actions[0].due_date == DAY + timedelta(days=7)


def test_unrecognised_due_phrase_is_kept_in_the_title():
    result = extract("- @Priya send the deck by the end of Q4", "", DAY)
    assert result.actions[0].due_date is None
    assert "end of Q4" in result.actions[0].title


def test_duplicate_decisions_and_actions_are_removed():
    notes = """Decisions:
- Ship the beta
- Ship the beta

Actions:
- @Priya send the deck
- @Priya send the deck
"""
    result = extract(notes, "", DAY)
    assert result.decisions == ["Ship the beta"]
    assert len(result.actions) == 1


def test_empty_notes_return_an_honest_summary():
    result = extract("", "", DAY)
    assert result.summary == "Notes recorded."
    assert result.decisions == []
    assert result.actions == []


def test_fallback_summary_counts_what_was_found():
    result = extract("Decisions:\n- Ship it\nActions:\n- @Priya send the deck", "", DAY)
    assert "1 decision" in result.summary
    assert "1 follow-up" in result.summary


def test_first_paragraph_becomes_the_summary_when_unsectioned():
    result = extract("We reviewed the quarter.\nThe mood was good.", "", DAY)
    assert result.summary == "We reviewed the quarter. The mood was good."


def test_mentions_are_added_to_attendees_without_duplicates():
    result = extract("- @Priya send the deck\n- @Arjun book the room", "Priya", DAY)
    assert result.attendees == ["Priya", "Arjun"]


def test_attendee_list_does_not_swallow_the_next_section():
    notes = """Attendees:
Priya
Arjun

Summary: Short meeting.
"""
    result = extract(notes, "", DAY)
    assert result.attendees == ["Priya", "Arjun"]
    assert result.summary == "Short meeting."


def test_extract_never_raises_on_odd_input():
    for notes in ["   ", "\n\n\n", "@", "Action:", "-", "Decisions:\n- ", "x" * 5000, "🎉" * 50]:
        result = extract(notes, "", DAY)
        assert isinstance(result.summary, str)


def test_long_summary_and_titles_are_clamped():
    result = extract("Summary: " + ("word " * 400), "", DAY)
    assert len(result.summary) <= 800
    action = extract("Actions:\n- " + ("task " * 200), "", DAY).actions[0]
    assert len(action.title) <= 280


def test_bullets_keep_their_section_across_blank_lines():
    notes = """Actions:
- @Priya send the deck

- @Arjun book the room
"""
    result = extract(notes, "", DAY)
    assert len(result.actions) == 2


def test_meeting_day_controls_weekday_due_dates():
    friday = date(2026, 11, 13)
    result = extract("- @Priya send the deck by Friday", "", friday)
    assert result.actions[0].due_date == date(2026, 11, 20)  # next Friday, not the same day
