from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Collection, Item
from app.services.search import (
    expand,
    label,
    parse_query,
    related,
    search,
    snippet,
    split_tags,
    stem,
    tag_key,
    tokenize,
    url_host,
)

BASE = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


def item(
    item_id: int,
    title: str,
    body: str = "",
    *,
    tags: str = "",
    kind: str = "note",
    starred: bool = False,
    author: str = "",
    source_url: str = "",
    collection: Collection | None = None,
    age: int = 0,
) -> Item:
    moment = BASE - timedelta(days=age)
    return Item(
        id=item_id,
        user_id=1,
        title=title,
        body=body,
        tags=tags,
        kind=kind,
        starred=starred,
        author=author,
        source_url=source_url,
        collection=collection,
        created_at=moment,
        updated_at=moment,
        origin="written",
    )


def test_stem_is_stable_and_small():
    assert stem("pricing") == "pric"
    assert stem("prices") == "price"
    assert stem("meetings") == "meet"
    assert stem("studies") == "study"
    assert stem("boxes") == "box"
    assert stem("plans") == "plan"
    assert stem("ai") == "ai"
    assert stem("2026") == "2026"


def test_tokenize_drops_filler_and_keeps_code_words():
    assert tokenize("The pricing review and the plan") == ["pric", "review", "plan"]
    assert tokenize("C++ and C# notes") == ["c++", "c#", "note"]
    assert tokenize("a b c") == []
    assert "997" in tokenize("invoice 997")


def test_curly_quotes_and_dashes_are_normalized():
    assert tokenize("Priya’s “pricing” note – revised") == ["priya", "pric", "note", "revis"]


def test_expand_is_symmetric_and_sorted():
    assert "price" in expand("pric")
    assert "pric" in expand("price")
    assert expand("pric") == sorted(expand("pric"))
    assert expand("unrelatedword") == ["unrelatedword"]


def test_label_turns_stems_into_words():
    assert label("pric") == "pricing"
    assert label("review") == "review"
    assert label("call") == "call"


def test_split_tags_handles_separators_and_case():
    assert split_tags("pricing, Pricing; q4 ,, decisions") == ["pricing", "q4", "decisions"]
    assert split_tags("") == []
    assert split_tags(None) == []


def test_split_tags_caps_length_and_count():
    assert split_tags("x" * 40) == []
    assert len(split_tags(", ".join(f"tag{i}" for i in range(20)))) == 10


def test_tag_key_and_host_helpers():
    assert tag_key("Client Work") == "client-work"
    assert tag_key("!!!") == "tag"
    assert url_host("https://www.books.example/a/b") == "books.example"
    assert url_host("not a url") == ""


def test_parse_query_extracts_filters():
    query = parse_query('kind:note tag:pricing in:client-work is:starred "quarterly plan" renewal')
    assert query.kind == "note"
    assert query.tag == "pricing"
    assert query.collection == "client-work"
    assert query.starred is True
    assert query.phrases == ["quarterly plan"]
    assert query.terms == ["renewal"]


def test_parse_query_ignores_unknown_filters_visibly():
    query = parse_query("kind:poem is:secret pricing")
    assert query.kind == ""
    assert query.starred is False
    assert set(query.ignored) == {"kind:poem", "is:secret"}
    assert any("ignored" in line for line in query.summary())


def test_parse_query_display_never_shows_a_stem():
    query = parse_query("pricing decisions")
    assert query.terms == ["pric", "decision"]
    assert query.terms_display == ["pricing", "decisions"]
    assert "pric," not in " ".join(query.summary())


def test_parse_query_caps_terms():
    query = parse_query(" ".join(f"word{i}" for i in range(30)))
    assert len(query.terms) == 12


def test_parse_query_expands_known_synonyms():
    query = parse_query("prices")
    assert "cost" in query.expansions or "pric" in query.expansions
    assert any(line.startswith("also matching") for line in query.summary())


def test_empty_query_is_inactive():
    query = parse_query("the and of")
    assert query.active is False
    assert query.terms == []
    assert query.summary() == []


def test_search_titles_outrank_bodies():
    items = [
        item(1, "Pricing decisions", "Nothing else here.", age=3),
        item(2, "Weekly notes", "We mentioned pricing once in a long body about other things.", age=1),
    ]
    hits = search(items, parse_query("pricing"))
    assert [hit.item.id for hit in hits] == [1, 2]
    assert hits[0].score > hits[1].score


def test_search_requires_a_term_unless_filters_apply():
    items = [item(1, "One"), item(2, "Two")]
    assert search(items, parse_query("nothingmatches")) == []
    assert len(search(items, parse_query("is:starred"))) == 0
    items[0].starred = True
    assert [hit.item.id for hit in search(items, parse_query("is:starred"))] == [1]


def test_search_with_no_query_lists_recent_first():
    items = [item(1, "Old", age=10), item(2, "New", age=1), item(3, "Middle", age=5)]
    hits = search(items, parse_query(""))
    assert [hit.item.id for hit in hits] == [2, 3, 1]
    assert all(hit.score == 0 for hit in hits)


def test_search_filters_by_kind_tag_starred_and_collection():
    work = Collection(id=7, user_id=1, name="Client Work")
    items = [
        item(1, "Pricing note", "pricing", tags="pricing, q4", kind="note", collection=work),
        item(2, "Pricing article", "pricing", tags="pricing", kind="article", starred=True),
        item(3, "Pricing snippet", "pricing", tags="other", kind="snippet"),
    ]
    assert [hit.item.id for hit in search(items, parse_query("pricing kind:article"))] == [2]
    assert [hit.item.id for hit in search(items, parse_query("pricing tag:q4"))] == [1]
    assert [hit.item.id for hit in search(items, parse_query("pricing is:starred"))] == [2]
    assert [hit.item.id for hit in search(items, parse_query("pricing in:client-work"))] == [1]
    assert [hit.item.id for hit in search(items, parse_query("pricing in:Client Work"))] == [1]


def test_phrase_query_requires_the_exact_words():
    items = [
        item(1, "Q4 pricing review", "The review of pricing happened."),
        item(2, "Pricing elsewhere", "A review of the pricing page."),
    ]
    hits = search(items, parse_query('"pricing review"'))
    assert [hit.item.id for hit in hits] == [1]
    assert hits[0].phrase_hits == 1
    assert hits[0].percent >= 1


def test_all_query_terms_present_gets_a_bonus():
    items = [
        item(1, "Pricing and review", "both words"),
        item(2, "Pricing only", "one word, repeated pricing pricing pricing"),
    ]
    hits = search(items, parse_query("pricing review"))
    assert hits[0].item.id == 1


def test_matched_terms_are_display_forms():
    hits = search([item(1, "Pricing review", "text")], parse_query("pricing reviews"))
    assert "pricing" in hits[0].matched
    assert "pric" not in hits[0].matched


def test_search_limit_is_respected():
    items = [item(index, f"Pricing {index}", "pricing") for index in range(1, 30)]
    assert len(search(items, parse_query("pricing"), limit=5)) == 5


def test_snippet_marks_terms_and_escapes_html():
    body = "Intro text. <script>alert(1)</script> The pricing page changed."
    out = snippet(body, ["pricing"], width=200)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "<mark>pricing</mark>" in out


def test_snippet_is_safe_for_a_term_containing_markup():
    out = snippet("A <b>bold</b> claim about pricing.", ["<b>"], width=120)
    assert "&lt;b&gt;" in out
    assert "<mark>&lt;b&gt;</mark>" in out


def test_snippet_without_a_match_truncates_at_a_space():
    out = snippet("word " * 200, ["absent"], width=50)
    assert out.endswith("…")
    assert len(out) <= 52


def test_snippet_empty_body_is_empty():
    assert snippet("", ["x"]) == ""
    assert snippet("   ", ["x"]) == ""


def test_snippet_does_not_cut_the_marked_word():
    out = snippet("start " + "filler " * 40 + "pricing ends here", ["pricing"], width=60)
    assert "<mark>pricing</mark>" in out


def test_snippet_does_not_mark_the_middle_of_a_larger_word():
    out = snippet("A separate note and feedback, with one rate.", ["rate", "fee"], width=200)
    assert out.count("<mark>") == 1
    assert "<mark>rate</mark>" in out
    assert "separate" in out
    assert "feedback" in out


def test_snippet_marks_a_simple_inflection():
    out = snippet("We reviewed the pricing and she reviews it again.", ["review"], width=200)
    assert "<mark>reviewed</mark>" in out
    assert "<mark>reviews</mark>" in out


def test_related_finds_shared_rare_terms_and_skips_numbers():
    target = item(1, "Lumen renewal contract", "The renewal date is 15 January with a discount.")
    others = [
        item(2, "Lumen onboarding", "The renewal date and discount were discussed."),
        item(3, "Unrelated note", "Nothing in common at all."),
        item(4, "Numbers only", "15 January 2026 42."),
    ]
    hits = related([target, *others], target)
    ids = [hit.item.id for hit in hits]
    assert 2 in ids
    assert 3 not in ids
    if 4 in ids:
        assert all(not term.isdigit() for hit in hits if hit.item.id == 4 for term in hit.matched)
    assert len(hits[0].matched) <= 5


def test_related_needs_another_item():
    target = item(1, "Alone", "Nothing shared.")
    assert related([target], target) == []
    assert related([target, item(2, "Empty", "")], target) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", False),
        ("the of and", False),
        ("pricing", True),
        ('"exact phrase"', True),
        ("kind:note", True),
        ("tag:pricing", True),
        ("in:client-work", True),
        ("is:starred", True),
    ],
)
def test_query_active_flags(raw: str, expected: bool):
    assert parse_query(raw).active is expected


def test_search_page_shows_understanding_and_highlights(browser):
    from conftest import add_item

    add_item(browser, title="Pricing review", body="The pricing page needs a calculator.", tags="pricing")
    r = browser.get("/search?q=pricing")
    assert r.status_code == 200
    assert "How this was understood" in r.text
    assert "<mark>pricing</mark>" in r.text
    assert "matched:" in r.text


def test_search_page_with_filters_only(browser):
    from conftest import add_item

    add_item(browser, title="A note", body="text", kind="note")
    add_item(browser, title="An article", body="text", kind="article")
    r = browser.get("/search?kind=note")
    assert "A note" in r.text
    assert "An article" not in r.text


def test_search_help_shows_operators(browser):
    r = browser.get("/search")
    assert "Exact phrase" in r.text
    assert "is:starred" in r.text


def test_search_no_results_offers_a_way_out(browser):
    r = browser.get("/search?q=zzzznotfound")
    assert "Nothing matched" in r.text
    assert "Clear the query" in r.text


def test_library_filters_by_kind_and_star(browser):
    from conftest import add_item

    add_item(browser, title="Note alpha", body="x", kind="note", starred="on")
    add_item(browser, title="Article beta", body="x", kind="article")
    assert "Note alpha" in browser.get("/library?kind=note").text
    assert "Article beta" not in browser.get("/library?kind=note").text
    starred = browser.get("/library?starred=1").text
    assert "Note alpha" in starred
    assert "Article beta" not in starred


def test_library_sorts_by_title(browser):
    from conftest import add_item

    add_item(browser, title="Zebra", body="x")
    add_item(browser, title="Apple", body="x")
    text = browser.get("/library?sort=title").text
    assert text.index("Apple") < text.index("Zebra")
