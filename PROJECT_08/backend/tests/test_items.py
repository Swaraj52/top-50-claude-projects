from __future__ import annotations

from conftest import add_collection, add_item


def test_empty_library_offers_three_starts(browser):
    r = browser.get("/library")
    assert r.status_code == 200
    assert "The library is empty" in r.text


def test_create_item_shows_on_detail_and_library(browser):
    item_id = add_item(browser, title="Quarterly pricing review", body="The Starter plan keeps its price.")
    detail = browser.get(f"/items/{item_id}")
    assert detail.status_code == 200
    assert "Quarterly pricing review" in detail.text
    assert "The Starter plan keeps its price." in detail.text
    library = browser.get("/library")
    assert "Quarterly pricing review" in library.text
    assert "1 item" in browser.get("/").text or "Library" in library.text


def test_title_is_required(browser):
    r = browser.post("/items/new", {"title": "   ", "body": "text"})
    assert r.status_code == 422
    assert "Give the item a title" in r.text


def test_body_limit_is_enforced(browser):
    r = browser.post("/items/new", {"title": "Too long", "body": "x" * 100_001})
    assert r.status_code == 422
    assert "too long" in r.text


def test_body_at_the_limit_is_accepted(browser):
    item_id = add_item(browser, title="Right at the edge", body="y" * 100_000)
    assert browser.get(f"/items/{item_id}").status_code == 200


def test_unknown_kind_is_refused(browser):
    r = browser.post("/items/new", {"title": "Odd", "body": "text", "kind": "novel"})
    assert r.status_code == 422
    assert "four kinds" in r.text


def test_each_kind_is_accepted(browser):
    for kind in ("note", "article", "reference", "snippet"):
        item_id = add_item(browser, title=f"A {kind}", body="Body text.", kind=kind)
        assert kind in browser.get(f"/items/{item_id}").text


def test_tags_are_cleaned_and_deduplicated(browser):
    item_id = add_item(browser, tags="pricing, Pricing, q4 ;  decisions")
    detail = browser.get(f"/items/{item_id}")
    assert detail.text.count(">pricing<") >= 1
    assert ">q4<" in detail.text
    assert ">decisions<" in detail.text


def test_tag_limit_is_ten(browser):
    tags = ", ".join(f"tag{i}" for i in range(15))
    item_id = add_item(browser, tags=tags)
    detail = browser.get(f"/items/{item_id}")
    assert "tag9" in detail.text
    assert "tag10" not in detail.text


def test_source_url_must_be_http(browser):
    r = browser.post("/items/new", {"title": "Bad link", "body": "text", "source_url": "javascript:alert(1)"})
    assert r.status_code == 422
    assert "http://" in r.text


def test_valid_source_url_is_stored_and_labelled(browser):
    item_id = add_item(
        browser,
        title="Design of Everyday Things",
        body="A note about doors.",
        kind="reference",
        source_url="https://books.example/design",
    )
    detail = browser.get(f"/items/{item_id}")
    assert "https://books.example/design" in detail.text
    assert "books.example" in detail.text
    assert "Loom has not fetched this page" in detail.text


def test_star_toggles_and_shows_in_library(browser):
    item_id = add_item(browser, title="Star me")
    detail = browser.get(f"/items/{item_id}")
    assert "★ starred" not in detail.text
    r = browser.post(f"/items/{item_id}/star", {"next": f"/items/{item_id}"})
    assert r.status_code == 303
    detail = browser.get(f"/items/{item_id}")
    assert "★ starred" in detail.text
    library = browser.get("/library?starred=1")
    assert "Star me" in library.text
    browser.post(f"/items/{item_id}/star", {"next": f"/items/{item_id}"})
    assert "★ starred" not in browser.get(f"/items/{item_id}").text


def test_star_redirect_rejects_an_offsite_target(browser):
    item_id = add_item(browser)
    r = browser.post(f"/items/{item_id}/star", {"next": "https://evil.example/x"})
    assert r.status_code == 303
    assert r.headers["location"] == f"/items/{item_id}"


def test_edit_item_updates_text_and_timestamp(browser):
    item_id = add_item(browser, title="Before", body="Old body.")
    page = browser.get(f"/items/{item_id}/edit")
    assert "Old body." in page.text
    r = browser.post(
        f"/items/{item_id}/edit",
        {"title": "After", "body": "New body.", "kind": "snippet", "tags": "edited"},
    )
    assert r.status_code == 303
    detail = browser.get(f"/items/{item_id}")
    assert "After" in detail.text
    assert "New body." in detail.text
    assert "edited" in detail.text


def test_delete_item_removes_it(browser):
    item_id = add_item(browser, title="Delete me")
    r = browser.post(f"/items/{item_id}/delete")
    assert r.status_code == 303
    assert browser.get(f"/items/{item_id}").status_code == 404


def test_item_can_be_assigned_to_a_collection(browser):
    add_collection(browser, "Client work")
    collections = browser.get("/collections").text
    assert "Client work" in collections
    item_id = add_item(browser, title="On a shelf")
    page = browser.get(f"/items/{item_id}/edit")
    assert "Client work" in page.text
    import re

    match = re.search(r'<option value="(\d+)"[^>]*>Client work</option>', page.text)
    assert match
    r = browser.post(
        f"/items/{item_id}/edit",
        {"title": "On a shelf", "body": "Text.", "kind": "note", "collection_id": match.group(1)},
    )
    assert r.status_code == 303
    assert "Client work" in browser.get(f"/items/{item_id}").text


def test_upload_markdown_creates_a_note(browser):
    r = browser.post(
        "/items/upload",
        files={"file": ("meeting notes.md", b"# Notes\n\nWe agreed the price.", "text/markdown")},
    )
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.endswith("/edit")
    detail = browser.get(location.split("/edit")[0])
    assert "meeting notes" in detail.text
    assert "We agreed the price." in detail.text


def test_upload_plain_text_is_accepted(browser):
    r = browser.post("/items/upload", files={"file": ("a.txt", b"plain text body", "text/plain")})
    assert r.status_code == 303
    assert "plain text body" in browser.get(r.headers["location"].split("/edit")[0]).text


def test_upload_html_is_reduced_to_text(browser):
    html = (
        b"<html><head><title>T</title><style>.x{color:red}</style></head>"
        b"<body><h1>Heading</h1><p>First &amp; second.</p><script>alert(1)</script></body></html>"
    )
    r = browser.post("/items/upload", files={"file": ("page.html", html, "text/html")})
    assert r.status_code == 303
    detail = browser.get(r.headers["location"].split("/edit")[0])
    assert "Heading" in detail.text
    assert "First &amp; second." in detail.text
    assert "alert(1)" not in detail.text


def test_upload_rejects_an_unsupported_type(browser):
    r = browser.post("/items/upload", files={"file": ("a.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 303
    assert r.headers["location"] == "/items/new?upload=type"
    assert "not supported" in browser.get("/items/new?upload=type").text


def test_upload_rejects_a_file_over_the_cap(browser):
    r = browser.post("/items/upload", files={"file": ("big.txt", b"x" * (512 * 1024 + 1), "text/plain")})
    assert r.status_code == 303
    assert r.headers["location"] == "/items/new?upload=large"
    assert "larger than 512 KB" in browser.get("/items/new?upload=large").text


def test_upload_without_a_file_reports_missing(browser):
    r = browser.post("/items/upload", files={"file": ("", b"", "application/octet-stream")})
    assert r.status_code == 303
    assert r.headers["location"] == "/items/new?upload=missing"
    assert "Choose a file" in browser.get("/items/new?upload=missing").text


def test_upload_accepts_a_utf8_bom(browser):
    r = browser.post("/items/upload", files={"file": ("bom.md", "\ufeffHello from a BOM".encode("utf-8"), "text/markdown")})
    assert r.status_code == 303
    detail = browser.get(r.headers["location"].split("/edit")[0])
    assert "Hello from a BOM" in detail.text
    assert "\ufeff" not in detail.text


def test_new_item_page_honours_the_kind_query(browser):
    r = browser.get("/items/new?kind=reference")
    assert 'value="reference" selected' in r.text


def test_edit_page_for_a_missing_item_is_404(browser):
    assert browser.get("/items/9999").status_code == 404
    assert browser.get("/items/9999/edit").status_code == 404


def test_collection_assignment_uses_only_your_own_collections(make_browser):
    a = make_browser().register(email="a@example.com")
    add_collection(a, "A shelf")
    b = make_browser().register(email="b@example.com", name="B")
    item_id = add_item(b, title="B item")
    import re

    page = b.get(f"/items/{item_id}/edit")
    assert "A shelf" not in page.text
    # A guessed id must not attach another user's collection.
    b.post(f"/items/{item_id}/edit", {"title": "B item", "body": "x", "kind": "note", "collection_id": "1"})
    assert "A shelf" not in b.get(f"/items/{item_id}").text
