"""One structured-output call to Claude with consistent error handling."""

from __future__ import annotations

import json
import logging
import time

import anthropic

log = logging.getLogger(__name__)


class AIError(Exception):
    """The AI result is unavailable; the message is safe to show to the user."""


def call_json(
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    content: str,
    schema: dict,
    effort: str = "low",
    max_tokens: int = 8000,
) -> dict:
    started = time.monotonic()
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise AIError("the Anthropic API key was rejected") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AIError("the Anthropic API key lacks permission for this model") from exc
    except anthropic.NotFoundError as exc:
        raise AIError(f"model '{model}' is not available to this API key") from exc
    except anthropic.RateLimitError as exc:
        raise AIError("the Anthropic API rate limit was reached") from exc
    except anthropic.APIStatusError as exc:
        raise AIError(f"the Anthropic API returned an error ({exc.status_code})") from exc
    except anthropic.APIConnectionError as exc:  # includes timeouts
        raise AIError("the Anthropic API could not be reached") from exc

    log.info(
        "claude call: model=%s stop=%s request_id=%s %.1fs",
        getattr(response, "model", model),
        response.stop_reason,
        getattr(response, "_request_id", None),
        time.monotonic() - started,
    )
    if response.stop_reason == "refusal":
        raise AIError("the model declined this request")
    if response.stop_reason == "max_tokens":
        raise AIError("the model's answer was cut off")
    text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("the model returned an answer in an unexpected format") from exc
    if not isinstance(data, dict):
        raise AIError("the model returned an answer in an unexpected format")
    return data
