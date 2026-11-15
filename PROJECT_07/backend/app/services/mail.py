"""Email parsing, rules-based triage and the local summary/draft writers.

Nothing in this module touches the network. It is the default path for ingest, summary and
drafting, and the fallback when the optional Claude call fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.message import Message as EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

CATEGORY_LABELS = {
    "reply": "Needs reply",
    "waiting": "Waiting on them",
    "fyi": "FYI",
    "newsletter": "Newsletter",
    "receipt": "Receipt",
}

_PREFIX = re.compile(r"^\s*(?:(?:re|fwd?|aw|sv)\s*(?:\[\d+\])?\s*:\s*)+", re.IGNORECASE)
_VIP_SPLIT = re.compile(r"[,;\n]+")
_ASK = re.compile(
    r"\b(?:could you|can you|would you|will you|please|need you to|do you|are you able|"
    r"review|approve|confirm|send|share|introduce|reply|get back|thoughts|what do you think|"
    r"let me know|sign off|take a look|fill (?:this |it )?in)\b",
    re.IGNORECASE,
)
_DEADLINE = re.compile(
    r"\b(?:today|tomorrow|eod|asap|deadline|due\b|"
    r"by (?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?\b|"
    r"by (?:next week|end of (?:day|week|month))|before (?:eod|friday|monday))\b",
    re.IGNORECASE,
)
_NEWSLETTER = re.compile(
    r"\b(?:unsubscribe|view (?:this|it) in (?:your )?browser|newsletter|digest|"
    r"you (?:are|'re) receiving this|manage (?:your )?preferences)\b",
    re.IGNORECASE,
)
_RECEIPT = re.compile(
    r"\b(?:invoice|receipt|order\s*(?:#|number|no\.?)?|payment|charged|total due|"
    r"billing|statement|refund)\b",
    re.IGNORECASE,
)
_MEETING = re.compile(r"\b(?:meeting|call|calendar|schedule|catch up|sync|availability|free at)\b", re.IGNORECASE)
_APPROVAL = re.compile(r"\b(?:approve|approval|sign off|sign-off|review and confirm)\b", re.IGNORECASE)
_SEND = re.compile(r"\b(?:send|share|forward|attach|deck|document|file|proposal)\b", re.IGNORECASE)
_GREETING = re.compile(r"^(?:hi|hello|hey|dear|good (?:morning|afternoon|evening))\b", re.IGNORECASE)
_CLOSING = re.compile(r"^(?:thanks|thank you|best|regards|kind regards|cheers|sincerely)[,!.]?$", re.IGNORECASE)


@dataclass
class ParsedEmail:
    sender: str
    recipients: str
    subject: str
    body: str
    received_at: datetime | None
    external_id: str | None


@dataclass
class Classification:
    category: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class DraftText:
    subject: str
    body: str


def clean_text(value: str, limit: int) -> str:
    return " ".join((value or "").split())[:limit]


def subject_key(subject: str) -> str:
    """Threading key: reply prefixes removed, case folded, whitespace collapsed."""
    stripped = _PREFIX.sub("", subject or "")
    return " ".join(stripped.split()).lower()[:200]


def display_subject(subject: str) -> str:
    stripped = _PREFIX.sub("", subject or "")
    return clean_text(stripped, 200) or "(no subject)"


def email_of(value: str) -> str:
    match = re.search(r"<([^>]+)>", value or "")
    if match:
        return match.group(1).strip().lower()
    return (value or "").strip().lower()


def display_sender(value: str) -> str:
    raw = (value or "").strip()
    if "<" in raw and raw.endswith(">"):
        name = raw[: raw.rfind("<")].strip().strip('"')
        if name:
            return name[:120]
    return email_of(raw)[:120]


def first_name(value: str) -> str:
    name = display_sender(value)
    if "@" in name and " " not in name:
        return name.split("@")[0].replace(".", " ").title().split(" ")[0]
    return name.split(" ")[0] if name else "there"


def vip_set(raw: str) -> set[str]:
    return {piece.strip().lower() for piece in _VIP_SPLIT.split(raw or "") if piece.strip()}


def is_vip(sender: str, vips: set[str]) -> bool:
    if not vips:
        return False
    return email_of(sender) in vips or display_sender(sender).lower() in vips


def classify(sender: str, subject: str, body: str, vips: set[str] | None = None) -> Classification:
    """Assign one of five categories from explicit, testable signals."""
    vips = vips or set()
    text = f"{subject}\n{body}"
    reasons: list[str] = []

    if is_vip(sender, vips):
        reasons.append("VIP sender")

    if _NEWSLETTER.search(text):
        reasons.append("Newsletter or bulk-mail wording")
        return Classification("newsletter", reasons)
    if _RECEIPT.search(text) and ("invoice" in text.lower() or "receipt" in text.lower() or "payment" in text.lower()):
        reasons.append("Invoice or receipt wording")
        return Classification("receipt", reasons)

    asks = bool(_ASK.search(body)) or subject.rstrip().endswith("?") or "?" in body
    if asks or is_vip(sender, vips):
        if "?" in body or subject.rstrip().endswith("?"):
            reasons.append("Contains a direct question")
        if _ASK.search(body):
            reasons.append("Contains a request")
        if is_vip(sender, vips) and not asks:
            reasons.append("From someone you marked VIP")
        return Classification("reply", reasons[:4])

    if not reasons:
        reasons.append("No question or request found")
    return Classification("fyi", reasons[:4])


def priority(thread, vips: set[str], now: datetime, unread: bool, starred: bool) -> tuple[int, list[str]]:
    """A small, explainable score. Every point has a reason shown in the UI."""
    score = 0
    reasons: list[str] = []
    base = {"reply": 30, "waiting": 12, "fyi": 8, "newsletter": 2, "receipt": 2}
    score += base.get(thread.category, 8)
    if thread.category == "reply":
        reasons.append("Needs a reply")
    elif thread.category == "waiting":
        reasons.append("Waiting on them")

    latest = thread.messages[-1] if thread.messages else None
    if latest is not None and is_vip(latest.sender, vips):
        score += 22
        reasons.append("VIP sender")
    if unread:
        score += 8
        reasons.append("Unread")
    if starred:
        score += 15
        reasons.append("Starred")

    if latest is not None:
        if "?" in latest.body or latest.body.rstrip().endswith("?"):
            score += 8
            reasons.append("Has a question")
        if _DEADLINE.search(latest.body):
            score += 12
            reasons.append("Mentions a deadline")
        age_hours = max(0.0, (now - latest.received_at).total_seconds() / 3600)
        if age_hours < 24:
            score += 8
            reasons.append("Arrived today")
        elif age_hours < 72:
            score += 5
        elif age_hours < 168:
            score += 2

    return min(100, score), reasons


def _strip_quoted(body: str) -> str:
    lines = []
    for line in (body or "").splitlines():
        if line.strip() in (">", "--") or line.lstrip().startswith(">"):
            continue
        if re.match(r"^On .+ wrote:$", line.strip()):
            break
        lines.append(line)
    return "\n".join(lines)


def _body_core(body: str) -> str:
    text = _strip_quoted(body)
    lines = [line.strip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    if lines and len(lines[0]) < 60 and _GREETING.match(lines[0]):
        lines.pop(0)
    for index, line in enumerate(lines):
        if _CLOSING.match(line) and index > 0:
            lines = lines[:index]
            break
    return " ".join(" ".join(lines).split())


def _sentences(text: str) -> list[str]:
    return [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", text) if piece.strip()]


def summarise_local(messages) -> str:
    """Two sentences from the latest inbound message, with the ask kept."""
    inbound = [m for m in messages if m.direction == "in"]
    latest = (inbound or list(messages))[-1] if messages else None
    if latest is None:
        return "No messages in this thread yet."
    core = _body_core(latest.body)
    if not core:
        return "The latest message has no readable text."
    sentences = _sentences(core)
    chosen: list[str] = []
    for sentence in sentences:
        if "?" in sentence:
            chosen.append(sentence)
            break
    for sentence in sentences:
        if sentence not in chosen:
            chosen.append(sentence)
        if len(chosen) >= 2:
            break
    text = " ".join(chosen)
    if len(text) > 320:
        text = text[:317].rsplit(" ", 1)[0] + "…"
    return text or "The latest message has no readable text."


def _ask_phrase(body: str) -> str:
    core = _body_core(body)
    for sentence in _sentences(core):
        if "?" in sentence or _ASK.search(sentence):
            return sentence[:180].strip()
    return _sentences(core)[0][:180].strip() if core else ""


def draft_local(thread, messages, user, tone: str = "warm") -> DraftText:
    """A reply scaffold. It never claims facts the thread does not contain."""
    inbound = [m for m in messages if m.direction == "in"]
    latest = (inbound or list(messages))[-1] if messages else None
    person = first_name(latest.sender) if latest is not None else "there"
    ask = _ask_phrase(latest.body) if latest is not None else ""
    subject = f"Re: {display_subject(thread.subject)}"[:200]

    greeting = "Dear" if tone == "formal" else "Hi"
    lines = [f"{greeting} {person},"]

    if _MEETING.search(ask):
        reply = "Happy to meet. Send a couple of times that suit you and I'll confirm one."
    elif _APPROVAL.search(ask):
        reply = "Thanks for sending this over. I'll review it and confirm my decision."
    elif _SEND.search(ask):
        reply = "Thanks — I'll put that together and send it over."
    elif "?" in ask:
        reply = "Good question — let me check and come back to you with a proper answer."
    elif ask:
        reply = "Thanks for the note. I've picked this up and will follow up shortly."
    else:
        reply = "Thanks for the note. Noted — I'll follow up if I need anything else."

    if tone != "brief":
        lines.append("")
        if ask:
            lines.append(f"You asked: “{ask}”")
            lines.append("")
        lines.append(reply)
    else:
        lines.append(reply)

    if user.signature:
        lines.extend(["", user.name, user.signature])
    else:
        lines.extend(["", user.name])
    return DraftText(subject=subject, body="\n".join(lines)[:4000])


def parse_eml(raw: bytes) -> ParsedEmail:
    """Parse a .eml file defensively: headers, a text body, an optional Message-ID."""
    message: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw or b"")
    sender = clean_text(str(message.get("From", "")), 254)
    recipients = clean_text(str(message.get("To", "")), 400)
    subject = clean_text(str(message.get("Subject", "")), 200)
    external_id = (str(message.get("Message-ID", "")) or "").strip().strip("<>")[:200] or None

    received: datetime | None = None
    raw_date = str(message.get("Date", "") or "")
    if raw_date:
        try:
            received = parsedate_to_datetime(raw_date)
        except (TypeError, ValueError):
            received = None
    if received is not None and received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)

    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_content()
                except (LookupError, ValueError):
                    body = part.get_payload(decode=True).decode("utf-8", "replace")
                if body.strip():
                    break
        if not body.strip():
            for part in message.walk():
                if part.get_content_type() == "text/html":
                    try:
                        html = part.get_content()
                    except (LookupError, ValueError):
                        html = part.get_payload(decode=True).decode("utf-8", "replace")
                    body = re.sub(r"<[^>]+>", " ", html)
                    break
    else:
        try:
            body = message.get_content()
        except (LookupError, ValueError):
            body = message.get_payload(decode=True).decode("utf-8", "replace")

    body = body.replace("\r\n", "\n").replace("\r", "\n").strip()[:60_000]
    return ParsedEmail(
        sender=sender,
        recipients=recipients,
        subject=subject,
        body=body,
        received_at=received,
        external_id=external_id,
    )
