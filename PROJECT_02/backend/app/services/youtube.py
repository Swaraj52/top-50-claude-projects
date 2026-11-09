"""YouTube capture: official oEmbed metadata plus a best-effort transcript."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx

log = logging.getLogger(__name__)

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}


@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel: str
    thumbnail_url: str


def video_id(url: str) -> str | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        return None
    candidate = None
    if host.endswith("youtu.be"):
        candidate = parts.path.strip("/").split("/")[0]
    elif parts.path == "/watch":
        candidate = parse_qs(parts.query).get("v", [None])[0]
    else:
        m = re.match(r"^/(?:shorts|embed|live|v)/([^/?#]+)", parts.path)
        candidate = m.group(1) if m else None
    return candidate if candidate and _ID.match(candidate) else None


def canonical_url(vid: str) -> str:
    return f"https://www.youtube.com/watch?v={vid}"


def fetch_info(vid: str, transport: httpx.BaseTransport | None = None) -> VideoInfo:
    """Metadata from YouTube's public oEmbed endpoint (no API key needed)."""
    try:
        with httpx.Client(timeout=10.0, transport=transport) as client:
            resp = client.get(
                "https://www.youtube.com/oembed", params={"url": canonical_url(vid), "format": "json"}
            )
    except httpx.HTTPError as exc:
        raise LookupError("YouTube could not be reached") from exc
    if resp.status_code in (401, 403, 404):
        raise LookupError("YouTube says this video is private, removed or not embeddable")
    if resp.status_code >= 400:
        raise LookupError(f"YouTube answered HTTP {resp.status_code}")
    data = resp.json()
    return VideoInfo(
        video_id=vid,
        title=str(data.get("title") or "YouTube video")[:500],
        channel=str(data.get("author_name") or "")[:200],
        thumbnail_url=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
    )


def _stamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def format_transcript(snippets: list[tuple[float, str]], every: float = 60.0) -> str:
    """Group caption snippets into paragraphs, each starting with a [m:ss] timestamp."""
    paras, current, started = [], [], None
    for start, text in snippets:
        text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        if not text:
            continue
        if started is None:
            started = start
        if current and start - started >= every:
            paras.append(f"[{_stamp(started)}] " + " ".join(current))
            current, started = [], start
        current.append(text)
    if current:
        paras.append(f"[{_stamp(started or 0)}] " + " ".join(current))
    return "\n\n".join(paras)


def fetch_transcript(vid: str) -> str | None:
    """Best effort: YouTube may refuse automated transcript requests from some networks."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch(vid, languages=["en", "en-US", "en-GB", "hi"])
        return format_transcript([(s.start, s.text) for s in fetched]) or None
    except Exception as exc:  # the library raises many specific errors; all mean "no transcript"
        log.info("no transcript for %s: %s", vid, exc.__class__.__name__)
        return None
