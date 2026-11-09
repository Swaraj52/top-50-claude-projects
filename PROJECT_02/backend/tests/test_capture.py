import httpx
import pytest

from app.services import fetcher, youtube
from tests.conftest import ARTICLE_HABITS, ARTICLE_SLEEP

EML = b"""From: "Morning Brew" <crew@morningbrew.example>
To: rhea@example.com
Subject: =?utf-8?q?Markets_=E2=80=94_Tuesday?=
Date: Tue, 03 Nov 2026 06:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="b1"

--b1
Content-Type: text/plain; charset=utf-8

Plain fallback text.
--b1
Content-Type: text/html; charset=utf-8

<html><body><table><tr><td><h1>Markets</h1><p>Stocks rallied as inflation cooled for the third straight month, lifting rate-sensitive tech shares.</p><p>Oil slipped on weaker demand forecasts from Asia.</p></td></tr></table></body></html>
--b1--
"""


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Title (Field Notes) >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


# --- fetcher (SSRF guard) -------------------------------------------------------------


def test_fetcher_rejects_private_and_non_http_targets(web):
    transport = httpx.MockTransport(web.handler)
    for url in ("http://localhost/admin", "http://internal.example/", "http://metadata.example/latest"):
        with pytest.raises(fetcher.FetchError, match="private or local"):
            fetcher.fetch(url, transport=transport)
    with pytest.raises(fetcher.FetchError, match="http and https"):
        fetcher.fetch("file:///etc/passwd", transport=transport)
    assert web.requests == []  # nothing was ever requested


def test_fetcher_checks_every_redirect_hop(web):
    web.add("https://public.example/go", "", status=302, headers={"location": "http://internal.example/secret"})
    with pytest.raises(fetcher.FetchError, match="private or local"):
        fetcher.fetch("https://public.example/go", transport=httpx.MockTransport(web.handler))
    assert web.requests == ["https://public.example/go"]


def test_fetcher_limits_size_and_type(web):
    transport = httpx.MockTransport(web.handler)
    web.add("https://big.example/", "x" * 2000)
    with pytest.raises(fetcher.FetchError, match="larger"):
        fetcher.fetch("https://big.example/", max_bytes=1000, transport=transport)
    web.add("https://img.example/cat.png", b"\x89PNG", content_type="image/png")
    with pytest.raises(fetcher.FetchError, match="Unsupported content type"):
        fetcher.fetch("https://img.example/cat.png", transport=transport)


# --- saving links ---------------------------------------------------------------------


def test_save_article_extracts_clean_text_and_metadata(save):
    item = save("https://brainweekly.example/sleep#comments", tags=["Sleep Science", "memory"])
    assert item["kind"] == "article" and item["status"] == "inbox"
    assert item["title"] == "Why sleep matters for memory"
    assert item["url"] == "https://brainweekly.example/sleep"  # fragment dropped
    assert item["source_name"] == "Brain Weekly" and "Maya Rao" in item["author"]
    assert "hippocampus replays" in item["content"]
    assert "Subscribe Login" not in item["content"] and "Copyright" not in item["content"]
    assert item["tags"] == ["memory", "sleep-science"]
    assert item["word_count"] > 60 and item["reading_minutes"] >= 1


def test_saving_the_same_link_twice_returns_the_original(client, save):
    first = save("https://brainweekly.example/sleep")
    r = client.post("/api/items/url", json={"url": "brainweekly.example/sleep"})
    assert r.status_code == 200
    assert r.json()["item"]["id"] == first["id"]
    assert r.json()["warnings"] == ["You already saved this link."]


def test_follows_public_redirects(client, web):
    web.add("https://short.example/x", "", status=301, headers={"location": "https://brainweekly.example/sleep"})
    web.add("https://brainweekly.example/sleep", ARTICLE_SLEEP)
    r = client.post("/api/items/url", json={"url": "https://short.example/x"})
    assert r.status_code == 201 and r.json()["item"]["source_name"] == "Brain Weekly"


def test_unreachable_or_private_links_are_rejected_with_a_reason(client, web):
    r = client.post("/api/items/url", json={"url": "http://localhost:8002/api/items"})
    assert r.status_code == 400 and "private or local" in r.json()["detail"]
    r = client.post("/api/items/url", json={"url": "https://gone.example/page"})
    assert r.status_code == 400 and "HTTP 404" in r.json()["detail"]


def test_page_without_article_text_is_kept_as_bookmark(client, web):
    web.add("https://app.example/", "<html><head><title>Some App</title></head><body><div id=root></div></body></html>")
    r = client.post("/api/items/url", json={"url": "https://app.example/"})
    assert r.status_code == 201
    assert r.json()["item"]["title"] == "Some App"
    assert "bookmark" in r.json()["warnings"][0]


def test_youtube_link_uses_oembed_and_transcript(client, web, monkeypatch):
    web.add("https://www.youtube.com/oembed", '{"title": "How memory works", "author_name": "Brain Lab"}', content_type="application/json")
    monkeypatch.setattr(youtube, "fetch_transcript", lambda vid: "[0:00] Welcome. Today: spaced repetition and memory.")
    r = client.post("/api/items/url", json={"url": "https://youtu.be/dQw4w9WgXcQ?t=42"})
    assert r.status_code == 201, r.text
    item = r.json()["item"]
    assert item["kind"] == "video" and item["title"] == "How memory works" and item["author"] == "Brain Lab"
    assert item["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert item["has_transcript"] and "spaced repetition" in item["content"]
    assert item["thumbnail_url"] == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"


def test_youtube_without_transcript_warns_and_accepts_pasted_one(client, web):
    web.add("https://www.youtube.com/oembed", '{"title": "Lecture 1", "author_name": "MIT"}', content_type="application/json")
    r = client.post("/api/items/url", json={"url": "https://www.youtube.com/watch?v=abcdefghijk"})
    assert "No transcript" in r.json()["warnings"][0]
    item_id = r.json()["item"]["id"]
    patched = client.patch(f"/api/items/{item_id}", json={"content": "[0:00] Entropy always increases."}).json()
    assert patched["has_transcript"] is True
    assert client.get("/api/search", params={"q": "entropy"}).json()["hits"][0]["item"]["id"] == item_id


@pytest.mark.parametrize(
    "url, vid",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=x", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://vimeo.com/123", None),
        ("https://www.youtube.com/watch?v=short", None),
    ],
)
def test_video_id_parsing(url, vid):
    assert youtube.video_id(url) == vid


def test_transcript_formatting_groups_by_minute():
    text = youtube.format_transcript([(0, "hello"), (30, "world"), (61, "next\nminute"), (3700, "late")])
    assert text == "[0:00] hello world\n\n[1:01] next minute\n\n[1:01:40] late"


# --- text and files ---------------------------------------------------------------------


def test_save_pasted_newsletter(client):
    r = client.post("/api/items/text", json={"content": "Issue 12\n\nRates fell again.", "title": "The Weekly", "kind": "newsletter"})
    assert r.status_code == 201
    assert r.json()["item"]["kind"] == "newsletter" and r.json()["item"]["title"] == "The Weekly"


def test_note_title_defaults_to_markdown_heading(client):
    r = client.post("/api/items/text", json={"content": "# Book ideas\n\nA novel about lighthouses."})
    assert r.json()["item"]["title"] == "Book ideas"


def test_upload_eml_newsletter(client):
    r = client.post("/api/items/upload", files={"file": ("issue.eml", EML, "message/rfc822")}, data={"tags": "finance, News"})
    assert r.status_code == 201, r.text
    item = r.json()["item"]
    assert item["kind"] == "newsletter" and item["title"] == "Markets — Tuesday"
    assert item["author"] == "Morning Brew" and "inflation cooled" in item["content"]
    assert item["tags"] == ["finance", "news"]


def test_upload_pdf_and_markdown(client):
    r = client.post("/api/items/upload", files={"file": ("notes.pdf", make_pdf("Photosynthesis converts light"), "application/pdf")})
    assert r.status_code == 201, r.text
    assert r.json()["item"]["kind"] == "pdf" and "Photosynthesis" in r.json()["item"]["content"]
    assert r.json()["item"]["title"] == "Field Notes"
    r = client.post("/api/items/upload", files={"file": ("ideas.md", b"Just a line of text", "text/markdown")})
    assert r.json()["item"]["title"] == "ideas"


def test_upload_rejects_unknown_types_and_broken_files(client):
    assert client.post("/api/items/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/items/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}).status_code == 400


def test_other_article_for_search_fixture(save):
    assert save("https://habits.example/tiny", ARTICLE_HABITS)["title"] == "Tiny habits that stick"
