from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import mail
from app.timeutil import (
    is_valid_timezone,
    parse_local_datetime,
    parse_people,
    relative_day,
    relative_label,
    to_utc,
    zone,
)


def message(direction="in", sender="Priya <priya@lumen.example>", body="Hello.", hours_ago=1.0):
    return SimpleNamespace(
        direction=direction,
        sender=sender,
        body=body,
        received_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        recipients="me@example.com",
    )


def thread(category="reply", messages=None, participants="Priya"):
    return SimpleNamespace(
        category=category,
        participants=participants,
        subject="Q4 launch",
        messages=messages or [message()],
    )


# ---------- subject and sender helpers ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Re: Q4 launch", "q4 launch"),
        ("RE: RE: Q4 launch", "q4 launch"),
        ("Fwd: Q4 launch", "q4 launch"),
        ("Fw: Q4 launch", "q4 launch"),
        ("Aw: Q4 launch", "q4 launch"),
        ("Sv: Q4 launch", "q4 launch"),
        ("Re[2]: Q4   launch", "q4 launch"),
        ("  Q4 Launch  ", "q4 launch"),
        ("", ""),
    ],
)
def test_subject_key_removes_reply_prefixes(raw, expected):
    assert mail.subject_key(raw) == expected


def test_display_subject_falls_back_for_an_empty_subject():
    assert mail.display_subject("") == "(no subject)"
    assert mail.display_subject("Re:  ") == "(no subject)"
    assert mail.display_subject("Re: Hello") == "Hello"


def test_email_of_and_display_sender():
    assert mail.email_of("Priya Raman <PRIYA@lumen.example>") == "priya@lumen.example"
    assert mail.email_of("priya@lumen.example") == "priya@lumen.example"
    assert mail.display_sender('"Priya Raman" <priya@lumen.example>') == "Priya Raman"
    assert mail.display_sender("priya@lumen.example") == "priya@lumen.example"


def test_first_name_from_a_name_and_from_an_address():
    assert mail.first_name("Priya Raman <priya@lumen.example>") == "Priya"
    assert mail.first_name("meera.iyer@northwind.example") == "Meera"


def test_clean_text_collapses_whitespace_and_truncates():
    assert mail.clean_text("  a\n\t b   c ", 100) == "a b c"
    assert len(mail.clean_text("x" * 50, 10)) == 10


def test_vip_matching_by_address_or_name():
    vips = mail.vip_set("priya@lumen.example, Kavya Rao")
    assert mail.is_vip("Priya Raman <PRIYA@lumen.example>", vips)
    assert mail.is_vip("Kavya Rao <kavya@elsewhere.example>", vips)
    assert not mail.is_vip("someone@else.example", vips)
    assert not mail.is_vip("someone@else.example", set())


# ---------- classification ----------


def test_classify_routes_a_question_to_reply():
    result = mail.classify("a@b.example", "Quick question", "Can you confirm the date?")
    assert result.category == "reply"
    assert "Contains a direct question" in result.reasons


def test_classify_routes_a_polite_request_to_reply():
    result = mail.classify("a@b.example", "Deck", "Could you review the deck before Friday?")
    assert result.category == "reply"
    assert "Contains a request" in result.reasons


def test_classify_routes_a_subject_question_to_reply():
    assert mail.classify("a@b.example", "Are we still on?", "Just checking.").category == "reply"


def test_classify_routes_plain_information_to_fyi():
    result = mail.classify("a@b.example", "Notes", "The doc is updated. No action needed.")
    assert result.category == "fyi"
    assert result.reasons == ["No question or request found"]


def test_classify_routes_newsletter_wording():
    result = mail.classify("news@x.example", "Weekly digest", "Unsubscribe or manage your preferences.")
    assert result.category == "newsletter"
    assert "Newsletter or bulk-mail wording" in result.reasons


def test_classify_routes_receipt_wording():
    result = mail.classify("billing@x.example", "Your invoice", "Invoice INV-1. Total charged: 24 USD. Payment received.")
    assert result.category == "receipt"
    assert "Invoice or receipt wording" in result.reasons


def test_a_vip_lands_in_reply_even_without_a_question():
    result = mail.classify("priya@lumen.example", "FYI", "The doc is updated.", {"priya@lumen.example"})
    assert result.category == "reply"
    assert "VIP sender" in result.reasons


def test_a_vip_does_not_override_bulk_mail():
    result = mail.classify("priya@lumen.example", "Newsletter", "Unsubscribe here.", {"priya@lumen.example"})
    assert result.category == "newsletter"


def test_receipt_wording_needs_a_receipt_word():
    result = mail.classify("a@b.example", "Order update", "Your order is on its way.")
    assert result.category == "fyi"


# ---------- priority ----------


def test_priority_explains_every_signal():
    t = thread("reply", [message(body="Can you confirm by Friday?")], "Priya")
    score, reasons = mail.priority(t, {"priya@lumen.example"}, datetime.now(timezone.utc), True, True)
    assert score >= 80
    assert "Needs a reply" in reasons
    assert "VIP sender" in reasons
    assert "Unread" in reasons
    assert "Starred" in reasons
    assert "Has a question" in reasons
    assert "Mentions a deadline" in reasons
    assert "Arrived today" in reasons
    assert score <= 100


def test_priority_is_lower_for_an_old_newsletter():
    t = thread("newsletter", [message(body="Unsubscribe here.", hours_ago=24 * 20)], "News")
    score, reasons = mail.priority(t, set(), datetime.now(timezone.utc), False, False)
    assert score <= 10
    assert "VIP sender" not in reasons


def test_priority_counts_waiting_without_a_vip():
    t = thread("waiting", [message(body="Thanks.", hours_ago=100)], "Priya")
    score, reasons = mail.priority(t, set(), datetime.now(timezone.utc), False, False)
    assert "Waiting on them" in reasons
    assert score >= 12


# ---------- summaries ----------


def test_summary_keeps_the_question_and_drops_the_greeting():
    messages = [
        message(
            body="Hi Swayam,\n\nCould you confirm the launch date by Friday?\n\nThanks,\nPriya\n\n"
            "On Mon, Swayam wrote:\n> older text"
        )
    ]
    summary = mail.summarise_local(messages)
    assert summary.startswith("Could you confirm the launch date")
    assert "Hi Swayam" not in summary
    assert "older text" not in summary


def test_summary_falls_back_to_the_latest_sentences():
    messages = [message(body="The doc is updated. Nothing is needed from you.")]
    summary = mail.summarise_local(messages)
    assert "doc is updated" in summary


def test_summary_of_an_empty_thread():
    assert "No messages" in mail.summarise_local([])


def test_summary_handles_an_empty_body():
    assert "no readable text" in mail.summarise_local([message(body="   ")])


# ---------- drafts ----------


def test_local_draft_quotes_the_ask_and_uses_the_signature():
    t = thread("reply")
    user = SimpleNamespace(name="Swayam", signature="Product lead, Lumen Labs")
    text = mail.draft_local(t, [message(body="Could you send the deck by Friday?")], user, "warm")
    assert text.subject == "Re: Q4 launch"
    assert text.body.startswith("Hi Priya,")
    assert "You asked:" in text.body
    assert "send it over" in text.body
    assert "Product lead, Lumen Labs" in text.body


def test_brief_draft_omits_the_quote():
    t = thread("reply")
    user = SimpleNamespace(name="Swayam", signature="")
    text = mail.draft_local(t, [message(body="Can you confirm?")], user, "brief")
    assert "You asked:" not in text.body
    assert "Swayam" in text.body


def test_formal_draft_uses_dear():
    t = thread("reply")
    user = SimpleNamespace(name="Swayam", signature="")
    text = mail.draft_local(t, [message(body="Can you confirm?")], user, "formal")
    assert text.body.startswith("Dear Priya,")


def test_draft_handles_a_meeting_request():
    t = thread("reply")
    user = SimpleNamespace(name="Swayam", signature="")
    text = mail.draft_local(t, [message(body="Are you free for a call on Tuesday?")], user)
    assert "Happy to meet" in text.body


def test_draft_never_invents_an_amount():
    t = thread("receipt")
    user = SimpleNamespace(name="Swayam", signature="")
    text = mail.draft_local(t, [message(body="Your invoice is attached. Total: 45 USD.")], user)
    assert "$" not in text.body
    assert "paid" not in text.body.lower()
    assert "You asked:" in text.body


# ---------- .eml parsing ----------


def test_parse_eml_reads_headers_and_body():
    raw = (
        b"From: Priya Raman <priya@lumen.example>\r\n"
        b"To: swayam@example.com\r\n"
        b"Subject: Re: Launch\r\n"
        b"Date: Fri, 13 Nov 2026 09:30:00 +0530\r\n"
        b"Message-ID: <abc@lumen.example>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Hello there.\r\n"
    )
    parsed = mail.parse_eml(raw)
    assert parsed.sender == "Priya Raman <priya@lumen.example>"
    assert parsed.subject == "Re: Launch"
    assert parsed.body == "Hello there."
    assert parsed.external_id == "abc@lumen.example"
    assert parsed.received_at.tzinfo is not None


def test_parse_eml_prefers_the_plain_text_part():
    raw = (
        b"From: a@b.example\r\nSubject: Multi\r\nContent-Type: multipart/alternative; boundary=X\r\n\r\n"
        b"--X\r\nContent-Type: text/html\r\n\r\n<p>HTML version</p>\r\n"
        b"--X\r\nContent-Type: text/plain\r\n\r\nPlain version\r\n--X--\r\n"
    )
    assert "Plain version" in mail.parse_eml(raw).body


def test_parse_eml_falls_back_to_html_text():
    raw = (
        b"From: a@b.example\r\nSubject: Multi\r\nContent-Type: multipart/alternative; boundary=X\r\n\r\n"
        b"--X\r\nContent-Type: text/html\r\n\r\n<p>HTML <b>version</b></p>\r\n--X--\r\n"
    )
    body = mail.parse_eml(raw).body
    assert "HTML" in body and "<p>" not in body


def test_parse_eml_survives_a_bad_date_and_no_message_id():
    raw = b"From: a@b.example\r\nSubject: Odd\r\nDate: not a date\r\n\r\nBody\r\n"
    parsed = mail.parse_eml(raw)
    assert parsed.received_at is None
    assert parsed.external_id is None


def test_parse_eml_ignores_attachments():
    raw = (
        b"From: a@b.example\r\nSubject: Attach\r\nContent-Type: multipart/mixed; boundary=X\r\n\r\n"
        b"--X\r\nContent-Type: text/plain\r\n\r\nSee attached.\r\n"
        b"--X\r\nContent-Type: text/plain\r\nContent-Disposition: attachment; filename=a.txt\r\n\r\nSECRET\r\n--X--\r\n"
    )
    body = mail.parse_eml(raw).body
    assert "See attached" in body
    assert "SECRET" not in body


# ---------- time utilities ----------


def test_zone_and_validity():
    assert zone("Asia/Kolkata").key == "Asia/Kolkata"
    assert zone("Not/AZone").key == "UTC"
    assert is_valid_timezone("Europe/Berlin")
    assert not is_valid_timezone("Nowhere/Special")


def test_relative_day_phrases():
    today = date(2026, 11, 14)  # a Saturday
    assert relative_day("today", today) == today
    assert relative_day("tomorrow", today) == today + timedelta(days=1)
    assert relative_day("next week", today) == today + timedelta(days=7)
    assert relative_day("2026-12-01", today) == date(2026, 12, 1)
    assert relative_day("by friday", today) == date(2026, 11, 20)
    assert relative_day("Friday", date(2026, 11, 13)) == date(2026, 11, 20)
    assert relative_day("sometime soon", today) is None
    assert relative_day("", today) is None
    assert relative_day("2026-13-40", today) is None


def test_parse_people_splits_and_deduplicates():
    assert parse_people("Priya, Arjun; Meera\nPriya") == ["Priya", "Arjun", "Meera"]
    assert parse_people("   ") == []


def test_to_utc_interprets_a_naive_value_in_the_local_zone():
    kolkata = zone("Asia/Kolkata")
    value = to_utc(datetime(2026, 11, 14, 9, 0), kolkata)
    assert value.hour == 3 and value.minute == 30
    assert value.tzinfo == timezone.utc


def test_parse_local_datetime_handles_offsets_and_garbage():
    kolkata = zone("Asia/Kolkata")
    parsed = parse_local_datetime("2026-11-14T09:00", kolkata)
    assert parsed.hour == 3
    with_z = parse_local_datetime("2026-11-14T09:00:00Z", kolkata)
    assert with_z.hour == 9
    assert parse_local_datetime("not a date", kolkata) is None
    assert parse_local_datetime("", kolkata) is None


def test_relative_labels():
    now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    assert relative_label(now - timedelta(seconds=5), now) == "now"
    assert relative_label(now - timedelta(minutes=12), now) == "12m"
    assert relative_label(now - timedelta(hours=3), now) == "3h"
    assert relative_label(now - timedelta(days=2), now) == "2d"
    assert relative_label(now - timedelta(days=30), now) == "4w"
