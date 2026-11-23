"""Draft an SOP from a short description.

The local outline is always available and is labelled as a starter, not as model output. With a key,
Claude proposes the same shape and the result is validated before it is shown; any failure keeps the
local outline and says why. Nothing is saved until the user accepts the draft.
"""

from __future__ import annotations

import json
import re

import httpx

from ..models import AREA_LABELS

SYSTEM = (
    "You write operating procedures for a small business. Use only the description supplied. "
    "Return plain, concrete steps a new team member could follow, with no invented systems, "
    "names, prices or deadlines. Return a single JSON object and nothing else."
)

FALLBACK_NOTE = "Claude was unavailable or returned an invalid draft; the local starter outline is shown."
LOCAL_NOTE = "No API key is configured; this is a local starter outline. Edit it before saving."

MIN_DESCRIPTION = 20
MAX_DESCRIPTION = 2000
MIN_STEPS = 4
MAX_STEPS = 10

TEMPLATES = {
    "sales": [
        ("Qualify the request", "Confirm the need, budget and decision date before quoting."),
        ("Prepare the quote", "Use the current price list and note anything non-standard."),
        ("Send and log it", "Send from the shared address and record it against the account."),
        ("Follow up", "Check in on the agreed date, not before."),
        ("Update the pipeline", "Move the account to its next stage with a note."),
    ],
    "delivery": [
        ("Confirm the scope", "Restate what was bought and what was not."),
        ("Schedule the work", "Put the delivery on the calendar with the named operator."),
        ("Do the work", "Follow the delivery checklist and record any deviation."),
        ("Check the result", "Have someone other than the operator check it."),
        ("Hand over and close", "Send the handover note and close the job."),
    ],
    "finance": [
        ("Collect the documents", "Gather every invoice, receipt and statement for the period."),
        ("Reconcile the entries", "Match the bank lines to the ledger."),
        ("Check the exceptions", "List anything unmatched and explain it."),
        ("Approve and file", "Get the owner's approval and file the pack."),
        ("Report the month", "Send the short summary and keep the numbers."),
    ],
    "people": [
        ("Confirm the need", "Write down the outcome this role must produce."),
        ("Draft the role", "Describe the work, the reporting line and the pay band."),
        ("Interview and decide", "Use the same questions for every candidate."),
        ("Make the offer", "Send the written offer and record the answer."),
        ("Onboard", "Assign a buddy, the first week and the first deliverable."),
    ],
    "operations": [
        ("Confirm the trigger", "State exactly what starts this process."),
        ("Gather the inputs", "Collect the records needed before any change is made."),
        ("Run the checks", "Follow the checks in order and note each result."),
        ("Record the outcome", "Write what changed, where and who approved it."),
        ("Review and close", "Check the result and close the item."),
    ],
    "product": [
        ("Collect the signal", "Link the request, complaint or measurement."),
        ("Triage and scope", "Decide what is in, what is out and why."),
        ("Build and review", "Ship behind a flag and get a second reader."),
        ("Release", "Write the note, tell the affected users and watch the metric."),
        ("Measure and learn", "Compare the result with the expected outcome."),
    ],
}

ROLES = ("Owner", "Operator", "Reviewer", "Operator", "Owner", "Reviewer", "Operator", "Reviewer")


def _text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _sentences(description: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", description.strip())
    return [_text(part, 240) for part in parts if len(_text(part, 240)) >= 8]


def local_outline(description: str, area: str) -> dict:
    sentences = _sentences(description)
    label = AREA_LABELS.get(area, "Operations")
    first = sentences[0].rstrip(".!?") if sentences else f"{label} process"
    title = first[:120] or f"{label} process"
    purpose_source = " ".join(sentences[:2]) if sentences else description
    purpose = purpose_source[:800]
    if len(purpose) < MIN_DESCRIPTION:
        purpose = f"{purpose} This procedure makes the work repeatable.".strip()
    scope = (
        f"Applies to {label.lower()} work that starts with: {first[:240].lower()}. "
        "It ends when the outcome is recorded and the owner has checked it."
    )[:600]
    if len(sentences) >= 3:
        chosen = sentences[:MAX_STEPS]
        steps = [
            {
                "title": sentence.rstrip(".!?")[:120],
                "detail": "",
                "role": ROLES[index % len(ROLES)],
            }
            for index, sentence in enumerate(chosen)
        ]
        while len(steps) < MIN_STEPS:
            fallback = TEMPLATES.get(area, TEMPLATES["operations"])[len(steps) % 5]
            steps.append({"title": fallback[0], "detail": fallback[1], "role": ROLES[len(steps) % len(ROLES)]})
    else:
        steps = [
            {"title": step_title, "detail": detail, "role": ROLES[index % len(ROLES)]}
            for index, (step_title, detail) in enumerate(TEMPLATES.get(area, TEMPLATES["operations"]))
        ]
    return {"title": title, "purpose": purpose, "scope": scope, "steps": steps[:MAX_STEPS]}


def build_prompt(description: str, area: str) -> str:
    label = AREA_LABELS.get(area, "Operations")
    return (
        f"Area: {label}\n"
        f"Description:\n{description.strip()[:MAX_DESCRIPTION]}\n\n"
        f"Write an SOP with 4 to 10 ordered steps. Each step needs a short title, one or two "
        f"sentences of detail, and a role (Owner, Operator or Reviewer). Give the SOP a title, a "
        f"purpose of 20 to 500 characters, and a scope of at most 500 characters. "
        f'Return JSON: {{"title": "...", "purpose": "...", "scope": "...", '
        f'"steps": [{{"title": "...", "detail": "...", "role": "..."}}]}}'
    )


def validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    title = _text(data.get("title"), 120)
    purpose = _text(data.get("purpose"), 800)
    scope = _text(data.get("scope"), 600)
    if not 3 <= len(title) <= 120:
        raise ValueError("title length out of range")
    if not MIN_DESCRIPTION <= len(purpose) <= 800:
        raise ValueError("purpose length out of range")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not MIN_STEPS <= len(raw_steps) <= MAX_STEPS:
        raise ValueError("step count out of range")
    steps = []
    for row in raw_steps:
        if not isinstance(row, dict):
            raise ValueError("each step must be an object")
        step_title = _text(row.get("title"), 120)
        detail = _text(row.get("detail"), 400)
        role = _text(row.get("role"), 60)
        if not 3 <= len(step_title) <= 120:
            raise ValueError("step title length out of range")
        steps.append({"title": step_title, "detail": detail, "role": role})
    return {"title": title, "purpose": purpose, "scope": scope, "steps": steps}


def _call(settings, prompt: str) -> dict:
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.anthropic_model,
            "max_tokens": 1200,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=settings.ai_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    text = "".join(block.get("text", "") for block in payload.get("content", [])).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model response was not a JSON object")
    return data


def draft(settings, description: str, area: str) -> tuple[dict, str, str]:
    """Return (draft, note, source). Source is 'local' or 'claude'."""
    local = local_outline(description, area)
    if not settings.ai_enabled:
        return local, LOCAL_NOTE, "local"
    try:
        data = _call(settings, build_prompt(description, area))
        return validate(data), "", "claude"
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return local, FALLBACK_NOTE, "local"
