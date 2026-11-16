from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Collection, Item
from app.services.clusters import GENERIC, build_clusters, slugify

BASE = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


def item(item_id: int, title: str, tags: str = "", body: str = "", age: int = 0) -> Item:
    moment = BASE - timedelta(days=age)
    return Item(
        id=item_id,
        user_id=1,
        title=title,
        body=body,
        tags=tags,
        kind="note",
        created_at=moment,
        updated_at=moment,
        origin="written",
    )


def test_slugify_is_stable_and_safe():
    assert slugify("Pricing · Lumen") == "pricing-lumen"
    assert slugify("  Hello, World!  ") == "hello-world"
    assert slugify("") == "cluster"
    assert slugify("!!!") == "cluster"
    assert len(slugify("x" * 100)) <= 60


def test_a_single_item_has_no_clusters():
    assert build_clusters([item(1, "Alone", "pricing")]) == []


def test_two_tags_make_a_cluster():
    items = [
        item(1, "Pricing review", "pricing, q4"),
        item(2, "Pricing teardown", "pricing, research"),
    ]
    clusters = build_clusters(items)
    assert len(clusters) == 1
    assert clusters[0].name == "Pricing"
    assert clusters[0].count == 2
    assert clusters[0].slug == "pricing"


def test_cluster_name_uses_words_not_stems():
    items = [item(1, "Pricing one", "pricing"), item(2, "Pricing two", "pricing")]
    cluster = build_clusters(items)[0]
    assert cluster.name == "Pricing"
    assert cluster.slug == "pricing"
    assert cluster.terms == ["Pricing"]


def test_tags_are_preferred_over_title_words():
    items = [
        item(1, "A weekly note", "pricing, q4"),
        item(2, "Another weekly note", "pricing, research"),
        item(3, "Weekly review one", ""),
        item(4, "Weekly review two", ""),
    ]
    clusters = build_clusters(items)
    assert clusters[0].name.startswith("Pricing")
    assert clusters[0].count == 2


def test_titles_still_cluster_when_no_shared_tags_exist():
    items = [
        item(1, "Lumen renewal", ""),
        item(2, "Lumen onboarding", ""),
    ]
    clusters = build_clusters(items)
    assert clusters[0].name == "Lumen"
    assert clusters[0].count == 2


def test_generic_words_never_name_a_cluster():
    items = [
        item(1, "First thoughts", "notes"),
        item(2, "First draft", "notes"),
        item(3, "Second thoughts", "notes"),
    ]
    clusters = build_clusters(items)
    names = " ".join(cluster.name for cluster in clusters)
    assert "First" not in names
    assert "Note" not in names
    assert "Thought" in names or "Draft" in names or clusters == []


def test_a_term_in_almost_every_item_is_not_a_cluster():
    items = [item(index, f"Common word {index}", "common") for index in range(1, 11)]
    assert build_clusters(items) == []


def test_identical_member_sets_are_not_repeated():
    items = [
        item(1, "Pricing q4", "pricing, q4"),
        item(2, "Pricing research", "pricing, research"),
    ]
    clusters = build_clusters(items)
    signatures = {frozenset(entry.id for entry in cluster.items) for cluster in clusters}
    assert len(signatures) == len(clusters)


def test_clusters_can_overlap_and_cover_more_items():
    items = [
        item(1, "Pricing review", "pricing, lumen"),
        item(2, "Pricing teardown", "pricing, research"),
        item(3, "Lumen onboarding", "lumen, onboarding"),
    ]
    clusters = build_clusters(items)
    by_name = {cluster.name: cluster for cluster in clusters}
    assert "Pricing" in by_name
    assert "Lumen" in by_name
    assert by_name["Pricing"].count == 2
    assert by_name["Lumen"].count == 2


def test_members_are_sorted_newest_first():
    items = [
        item(1, "Pricing old", "pricing", age=10),
        item(2, "Pricing new", "pricing", age=1),
        item(3, "Pricing middle", "pricing", age=5),
    ]
    clusters = build_clusters(items)
    assert [entry.id for entry in clusters[0].items] == [2, 3, 1]


def test_limit_is_respected():
    items = []
    for tag in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf"):
        for index in (0, 1):
            items.append(item(len(items) + 1, f"{tag} {index}", tag))
    assert len(build_clusters(items, limit=3)) == 3


def test_two_shared_terms_are_joined_in_the_name():
    items = [
        item(1, "Postgres index notes", "database, postgres, performance"),
        item(2, "SQLite WAL notes", "database, sqlite, performance"),
    ]
    clusters = build_clusters(items)
    assert clusters[0].name == "Database · Performance"
    assert clusters[0].terms == ["Database", "Performance"]


def test_generic_list_covers_function_words():
    for word in ("first", "one", "keep", "return", "note", "notes", "make", "time"):
        assert word in GENERIC


def test_clusters_page_and_detail(browser):
    from conftest import add_item

    add_item(browser, title="Pricing review", body="pricing text", tags="pricing, q4")
    add_item(browser, title="Pricing teardown", body="pricing text", tags="pricing, research")
    page = browser.get("/clusters")
    assert page.status_code == 200
    assert "Pricing" in page.text
    assert "2 items" in page.text
    detail = browser.get("/clusters/pricing")
    assert detail.status_code == 200
    assert "Pricing review" in detail.text
    assert "hidden model" in detail.text
    assert browser.get("/clusters/not-a-cluster").status_code == 404


def test_cluster_page_explains_an_empty_library(browser):
    r = browser.get("/clusters")
    assert "No clusters yet" in r.text
