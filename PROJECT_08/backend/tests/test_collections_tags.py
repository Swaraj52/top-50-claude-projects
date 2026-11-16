from __future__ import annotations

from conftest import add_collection, add_item


def test_create_and_list_a_collection(browser):
    add_collection(browser, "Client work", "The Lumen pilot")
    page = browser.get("/collections")
    assert "Client work" in page.text
    assert "The Lumen pilot" in page.text
    assert "0 items" in page.text


def test_empty_collection_name_is_refused(browser):
    r = browser.post("/collections", {"name": "   "})
    assert r.status_code == 303
    assert r.headers["location"] == "/collections?error=name"
    assert "Give the collection a short name" in browser.get("/collections?error=name").text


def test_duplicate_collection_name_is_refused_case_insensitively(browser):
    add_collection(browser, "Client work")
    r = browser.post("/collections", {"name": "client WORK"})
    assert r.headers["location"] == "/collections?error=duplicate"
    assert "already exists" in browser.get("/collections?error=duplicate").text


def test_collection_name_is_clamped(browser):
    add_collection(browser, "x" * 100)
    page = browser.get("/collections")
    assert "x" * 60 in page.text
    assert "x" * 61 not in page.text


def test_rename_a_collection(browser):
    add_collection(browser, "Old name")
    page = browser.get("/collections")
    import re

    match = re.search(r'action="/collections/(\d+)"', page.text)
    assert match
    collection_id = match.group(1)
    r = browser.post(f"/collections/{collection_id}", {"name": "New name", "description": "Updated"})
    assert r.status_code == 303
    page = browser.get("/collections")
    assert "New name" in page.text
    assert "Old name" not in page.text
    assert "Updated" in page.text


def test_rename_to_a_taken_name_is_refused(browser):
    add_collection(browser, "One")
    add_collection(browser, "Two")
    page = browser.get("/collections")
    import re

    ids = re.findall(r'action="/collections/(\d+)"', page.text)
    assert len(ids) == 2
    r = browser.post(f"/collections/{ids[0]}", {"name": "Two"})
    assert r.headers["location"] == "/collections?error=duplicate"


def test_rename_a_missing_collection_is_404(browser):
    assert browser.post("/collections/9999", {"name": "Nope"}).status_code == 404


def test_delete_a_collection_keeps_its_items(browser):
    add_collection(browser, "Temporary")
    page = browser.get("/collections")
    import re

    collection_id = re.search(r'action="/collections/(\d+)"', page.text).group(1)
    item_id = add_item(browser, title="Belongs to a shelf")
    edit = browser.get(f"/items/{item_id}/edit")
    r = browser.post(
        f"/items/{item_id}/edit",
        {"title": "Belongs to a shelf", "body": "x", "kind": "note", "collection_id": collection_id},
    )
    assert r.status_code == 303
    assert "Temporary" in browser.get(f"/items/{item_id}").text
    r = browser.post(f"/collections/{collection_id}/delete")
    assert r.status_code == 303
    detail = browser.get(f"/items/{item_id}")
    assert "Belongs to a shelf" in detail.text
    assert "Temporary" not in detail.text


def test_collections_page_lists_items_without_a_shelf(browser):
    add_item(browser, title="Loose item")
    page = browser.get("/collections")
    assert "Not on a shelf" in page.text
    assert "Loose item" in page.text


def test_dashboard_shows_collections_and_tags(browser):
    add_collection(browser, "Client work")
    add_item(browser, title="Pricing note", tags="pricing, q4")
    page = browser.get("/")
    assert "Client work" in page.text
    assert "pricing" in page.text


def test_tags_page_counts_items(browser):
    add_item(browser, title="One", tags="pricing, q4")
    add_item(browser, title="Two", tags="Pricing")
    page = browser.get("/tags")
    assert page.status_code == 200
    assert "pricing" in page.text
    assert "2 tags" in page.text or ">2<" in page.text


def test_tags_page_is_empty_without_tags(browser):
    add_item(browser, title="No tags", tags="")
    assert "No tags yet" in browser.get("/tags").text


def test_library_tag_filter_is_case_insensitive(browser):
    add_item(browser, title="Pricing note", tags="Pricing")
    add_item(browser, title="Other note", tags="other")
    page = browser.get("/library?tag=pricing")
    assert "Pricing note" in page.text
    assert "Other note" not in page.text


def test_library_collection_filter_uses_the_id(browser):
    add_collection(browser, "Client work")
    import re

    collection_id = re.search(r'action="/collections/(\d+)"', browser.get("/collections").text).group(1)
    item_id = add_item(browser, title="On the shelf")
    browser.post(
        f"/items/{item_id}/edit",
        {"title": "On the shelf", "body": "x", "kind": "note", "collection_id": collection_id},
    )
    page = browser.get(f"/library?collection={collection_id}")
    assert "On the shelf" in page.text
    assert "Showing 1 of 1" in page.text


def test_library_rejects_unknown_filters_quietly(browser):
    add_item(browser, title="Visible note")
    page = browser.get("/library?kind=poem&collection=9999&starred=maybe")
    assert page.status_code == 200
    assert "Visible note" in page.text


def test_library_filter_note_summarises_the_view(browser):
    add_item(browser, title="A note", kind="note")
    page = browser.get("/library?kind=note")
    assert "Showing 1 of 1" in page.text
    assert "kind" in page.text
