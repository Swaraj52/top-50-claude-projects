"""Turn fetched or uploaded content into a title + readable plain text."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from urllib.parse import urlsplit

import trafilatura

MAX_CONTENT_CHARS = 2_000_000
MAX_PDF_PAGES = 400


class ExtractError(Exception):
    """A user-facing problem reading a file or page."""


@dataclass
class Extracted:
    kind: str
    title: str
    content: str = ""
    source_name: str = ""
    author: str = ""
    published: str = ""
    description: str = ""
    warnings: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_CONTENT_CHARS]


def _host(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def from_html(html: str, url: str = "") -> Extracted:
    doc = trafilatura.bare_extraction(
        html, url=url or None, with_metadata=True, include_comments=False, include_tables=True
    )
    meta = doc.as_dict() if doc is not None and hasattr(doc, "as_dict") else (doc or {})
    title = (meta.get("title") or "").strip()
    text = _clean(meta.get("text") or "")
    # trafilatura often repeats the headline as the first line of the body.
    if title and text.split("\n", 1)[0].strip() == title:
        text = text.split("\n", 1)[1].strip() if "\n" in text else ""
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    result = Extracted(
        kind="article",
        title=title or _host(url) or "Untitled page",
        content=text,
        source_name=(meta.get("sitename") or _host(url) or "")[:200],
        author=(meta.get("author") or "")[:200],
        published=(meta.get("date") or "")[:40],
        description=(meta.get("description") or "")[:2000],
    )
    if not text:
        result.warnings.append("No readable article text was found; saved as a bookmark.")
    return result


def from_text(raw: str, filename: str = "", title: str = "") -> Extracted:
    text = _clean(raw)
    if not title:
        heading = re.match(r"\s*#\s+(.+)", text)
        title = heading.group(1).strip() if heading else (filename.rsplit(".", 1)[0] if filename else "")
    if not title:
        title = (text.split("\n", 1)[0][:80] or "Untitled note").strip()
    return Extracted(kind="note", title=title[:500], content=text)


def from_eml(data: bytes) -> Extracted:
    try:
        msg = BytesParser(policy=policy.default).parsebytes(data)
    except Exception as exc:  # malformed MIME raises several types
        raise ExtractError("That file is not a readable email (.eml)") from exc
    subject = str(msg.get("subject", "")).strip() or "Untitled newsletter"
    name, addr = parseaddr(str(msg.get("from", "")))
    published = ""
    try:
        if msg.get("date"):
            published = parsedate_to_datetime(str(msg["date"])).date().isoformat()
    except (TypeError, ValueError):
        pass

    plain = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    text = ""
    if html is not None:
        text = from_html(html.get_content()).content
    if not text and plain is not None:
        text = plain.get_content()
    if not text:
        raise ExtractError("The email has no readable text")
    return Extracted(
        kind="newsletter",
        title=subject[:500],
        content=_clean(text),
        source_name=(name or addr.split("@")[-1])[:200],
        author=(name or addr)[:200],
        published=published,
    )


def from_pdf(data: bytes, filename: str = "") -> Extracted:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages[:MAX_PDF_PAGES]]
        info = reader.metadata or {}
    except (PdfReadError, ValueError, KeyError) as exc:
        raise ExtractError("That PDF could not be read") from exc
    text = _clean("\n\n".join(pages))
    if not text:
        raise ExtractError("The PDF has no extractable text (scanned images aren't supported)")
    title = str(info.get("/Title") or "").strip() or (filename.rsplit(".", 1)[0] if filename else "Untitled PDF")
    result = Extracted(kind="pdf", title=title[:500], content=text, author=str(info.get("/Author") or "")[:200])
    if len(reader.pages) > MAX_PDF_PAGES:
        result.warnings.append(f"Only the first {MAX_PDF_PAGES} pages were imported.")
    return result
