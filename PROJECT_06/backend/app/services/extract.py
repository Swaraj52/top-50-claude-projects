"""Deterministic meeting-notes extraction: summary, decisions, owners and follow-ups.

This is the fallback path and the always-available baseline for Quorum. It is deliberately
rule-based: the same notes produce the same result, no network is involved, and every result is
labelled "local" in the UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..timeutil import parse_attendees, relative_day

BULLET = re.compile(r"^\s*(?:[-*•–—]|\d+[.)])\s*")
HEADER = re.compile(
    r"^\s*(summary|overview|decisions?|action items?|actions?|next steps?|attendees|"
    r"participants|notes|discussion|context)\s*:?\s*$",
    re.IGNORECASE,
)
INLINE_HEADER = re.compile(
    r"^\s*(summary|overview|decisions?|action items?|actions?|next steps?|attendees|"
    r"participants|notes|discussion|context)\s*:\s*(.+)$",
    re.IGNORECASE,
)
DECISION_PREFIX = re.compile(
    r"^\s*(?:decision|decided|we agreed|we decided|we settled|it was agreed(?: that)?|the team agreed(?: that)?|agreed|approved|final call|resolution|outcome)\s*[:\-–—]?\s*",
    re.IGNORECASE,
)
ACTION_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:action(?:\s+items?)?|next\s+steps?|todos?|to-dos?)\b\s*[:\-–—]?\s+"
    r"|(?:ai|follow[- ]?ups?)\b\s*[:\-–—]\s*"
    r")",
    re.IGNORECASE,
)
AGREEMENT = re.compile(r"\b(we (?:agreed|decided|settled)|it was agreed|the team agreed|approved)\b", re.IGNORECASE)
WILL_DO = re.compile(
    r"^(?P<owner>[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?)\s+(?:will|is going to|is to|to)\s+(?P<task>.{3,})$"
)
AT_OWNER = re.compile(r"@([A-Za-z][\w.-]*)")
OWNER_LABEL = re.compile(r"\bowner\s*[:\-]\s*([A-Za-z][\w .'-]{0,60})", re.IGNORECASE)
DUE = re.compile(r"\b(?:by|due|before)\s+([^,.;\n]+)", re.IGNORECASE)
BARE_DUE = re.compile(r"\b(today|tomorrow|next week|in a week)\b\s*[.!]?\s*$", re.IGNORECASE)
WHITESPACE = re.compile(r"\s+")


@dataclass
class ActionDraft:
    title: str
    owner: str = ""
    due_date: date | None = None


@dataclass
class Extraction:
    summary: str
    decisions: list[str] = field(default_factory=list)
    actions: list[ActionDraft] = field(default_factory=list)
    attendees: list[str] = field(default_factory=list)
    note: str = "Local extractor: rules only, no model call."


def _clean(line: str) -> str:
    return WHITESPACE.sub(" ", BULLET.sub("", line)).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", WHITESPACE.sub(" ", text))
    return [p.strip() for p in parts if p.strip()]


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _trim(text: str, limit: int) -> str:
    text = text.strip().lstrip("-–—:;,| ").rstrip(" ,;:|–—-")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _strip_due(text: str, day: date) -> tuple[str, date | None]:
    match = DUE.search(text)
    if match:
        parsed = relative_day(match.group(1), day)
        if parsed is not None:
            cleaned = (text[: match.start()] + " " + text[match.end():]).strip(" ,.;-–—")
            return cleaned, parsed
    bare = BARE_DUE.search(text)
    if bare:
        parsed = relative_day(bare.group(1), day)
        if parsed is not None:
            cleaned = (text[: bare.start()] + " " + text[bare.end():]).strip(" ,.;-–—")
            return cleaned, parsed
    return text, None


def _decision_text(raw: str) -> str:
    text = DECISION_PREFIX.sub("", _clean(raw)).strip()
    text = re.sub(r"^to\s+", "", text, flags=re.IGNORECASE)
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return _trim(text, 500)


def _owner_and_title(raw: str, attendees: list[str]) -> tuple[str, str]:
    """Return (owner, title) from one action line."""
    text = ACTION_PREFIX.sub("", _clean(raw)).strip()
    owner = ""

    label = OWNER_LABEL.search(text)
    if label:
        owner = _trim(label.group(1), 80)
        text = (text[: label.start()] + " " + text[label.end():]).strip(" ,.;-–—")

    at = AT_OWNER.search(text)
    if at and not owner:
        owner = at.group(1)
        text = (text[: at.start()] + " " + text[at.end():]).strip(" ,.;-–—")

    will = WILL_DO.match(text)
    if will:
        owner = owner or will.group("owner").strip()
        text = will.group("task").strip()

    if not owner:
        lowered = {name.lower(): name for name in attendees}
        for name in attendees:
            if text.lower().startswith(name.lower() + " "):
                owner = lowered[name.lower()]
                text = text[len(name):].strip(" ,:;-–—")
                break

    text = ACTION_PREFIX.sub("", text).strip()
    text = _trim(text, 280)
    return _trim(owner, 80), text


def _section_name(raw: str) -> str:
    name = raw.strip().lower()
    if name.startswith("decision"):
        return "decisions"
    if name.startswith(("action", "next step", "follow")):
        return "actions"
    if name.startswith(("attendee", "participant")):
        return "attendees"
    if name in ("summary", "overview"):
        return "summary"
    return "notes"


def _looks_like_action(line: str) -> bool:
    if ACTION_PREFIX.match(line) or AT_OWNER.search(line) or OWNER_LABEL.search(line):
        return True
    return bool(WILL_DO.match(_clean(line)))


def _looks_like_decision(line: str) -> bool:
    if DECISION_PREFIX.match(line):
        return True
    return bool(AGREEMENT.search(line))


def _decisions_in(line: str) -> list[str]:
    """Pull only the agreement clauses out of a mixed paragraph."""
    out = []
    for sentence in _sentences(line):
        if _looks_like_decision(sentence):
            text = _decision_text(sentence)
            if text:
                out.append(text)
    return out


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = _key(item)
        if len(key) < 4 or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract(notes: str, attendees_raw: str = "", meeting_day: date | None = None) -> Extraction:
    """Extract structure from pasted notes. Never raises on ordinary text."""
    day = meeting_day or date.today()
    lines = [line for line in (notes or "").replace("\r\n", "\n").split("\n")]
    explicit_attendees = parse_attendees(attendees_raw)

    section = ""
    summary_parts: list[str] = []
    decisions: list[str] = []
    actions: list[ActionDraft] = []
    mentioned: list[str] = []
    first_paragraph: list[str] = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            # A blank line ends a prose paragraph or an attendee list, but bullets keep their section.
            if section in ("summary", "attendees"):
                section = ""
            continue

        inline = INLINE_HEADER.match(stripped)
        if inline:
            section = _section_name(inline.group(1))
            stripped = inline.group(2).strip()
            if not stripped:
                continue
        else:
            header = HEADER.match(stripped)
            if header:
                section = _section_name(header.group(1))
                continue

        clean = _clean(stripped)
        if not clean:
            continue
        for found in AT_OWNER.findall(clean):
            if found not in mentioned:
                mentioned.append(found)

        if section == "attendees":
            explicit_attendees.extend(parse_attendees(clean))
            continue

        if section == "summary":
            summary_parts.append(clean)
            continue

        if section == "actions":
            without_due, due = _strip_due(clean, day)
            owner, title = _owner_and_title(without_due, explicit_attendees or mentioned)
            if title:
                actions.append(ActionDraft(title=_trim(title, 280), owner=owner, due_date=due))
            continue

        if section == "decisions":
            text = _decision_text(clean)
            if text:
                decisions.append(text)
            continue

        # Unsectioned notes: use the directives in each line, and keep prose for the summary.
        if _looks_like_action(clean):
            without_due, due = _strip_due(clean, day)
            owner, title = _owner_and_title(without_due, explicit_attendees or mentioned)
            if title:
                actions.append(ActionDraft(title=_trim(title, 280), owner=owner, due_date=due))
            continue
        if _looks_like_decision(clean):
            found = _decisions_in(clean)
            if found:
                decisions.extend(found)
            continue
        if len(first_paragraph) < 6:
            first_paragraph.append(clean)

    # Sentence-level rescue: notes often put several directives in one paragraph.
    if not decisions:
        for sentence in _sentences(notes or ""):
            if _looks_like_decision(sentence):
                text = _decision_text(sentence)
                if text:
                    decisions.append(text)
    if not actions:
        for sentence in _sentences(notes or ""):
            if _looks_like_action(sentence):
                without_due, due = _strip_due(sentence, day)
                owner, title = _owner_and_title(without_due, explicit_attendees or mentioned)
                if title:
                    actions.append(ActionDraft(title=_trim(title, 280), owner=owner, due_date=due))

    decisions = _dedupe(decisions)[:15]
    seen_actions: set[str] = set()
    unique_actions: list[ActionDraft] = []
    for action in actions:
        key = _key(action.title)
        if len(key) < 4 or key in seen_actions:
            continue
        seen_actions.add(key)
        if action.due_date is None:
            action.title, action.due_date = _strip_due(action.title, day)
        unique_actions.append(action)
    actions = unique_actions[:25]

    attendees = list(dict.fromkeys([*explicit_attendees, *mentioned]))[:30]

    if summary_parts:
        summary = _trim(WHITESPACE.sub(" ", " ".join(summary_parts)), 800)
    elif first_paragraph:
        summary = _trim(WHITESPACE.sub(" ", " ".join(first_paragraph)), 800)
    else:
        summary = ""

    if not summary:
        bits = []
        if decisions:
            bits.append(f"{len(decisions)} decision{'s' if len(decisions) != 1 else ''}")
        if actions:
            bits.append(f"{len(actions)} follow-up{'s' if len(actions) != 1 else ''}")
        summary = "Notes recorded" + (": " + " and ".join(bits) + "." if bits else ".")

    return Extraction(summary=summary, decisions=decisions, actions=actions, attendees=attendees)
