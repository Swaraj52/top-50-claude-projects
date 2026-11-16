from __future__ import annotations

from conftest import add_item

LONG_BODY = (
    "Attendees: Priya, Arjun and Meera. We reviewed the pricing page and agreed the Starter plan "
    "keeps its current price until the January renewal cycle. The Growth plan moves to usage-based "
    "pricing, reviewed monthly with a cap for the first two months. Priya will test a calculator "
    "inside the trial signup with five customers. Open question: does the annual discount stay at "
    "fifteen percent, or should a two-year commitment get twenty?"
)


def ask(browser, question: str):
    return browser.post("/ask", {"q": question})


def test_ask_page_explains_the_pipeline(browser):
    r = browser.get("/ask")
    assert r.status_code == 200
    assert "What happens when you ask" in r.text
    assert "Claude is not enabled" in r.text


def test_ask_requires_a_meaningful_word(browser):
    r = ask(browser, "the and of")
    assert r.status_code == 200
    assert "at least one meaningful word" in r.text


def test_ask_with_no_matching_item_says_so(browser):
    r = ask(browser, "quantum chromodynamics")
    assert "Nothing in this library matches" in r.text
    assert "nothing to quote" in r.text


def test_ask_returns_a_local_answer_with_citations(browser):
    add_item(browser, title="Q4 pricing review", body=LONG_BODY, tags="pricing, q4")
    r = ask(browser, "what did we decide about pricing in January")
    assert r.status_code == 200
    assert "Local extract" in r.text
    assert "Q4 pricing review" in r.text
    assert "Citations" in r.text


def test_answer_quotes_a_sentence_from_the_item(browser):
    add_item(browser, title="Q4 pricing review", body=LONG_BODY, tags="pricing")
    r = ask(browser, "what is the annual discount")
    assert "fifteen percent" in r.text or "annual discount" in r.text


def test_answer_subject_uses_words_not_stems(browser):
    add_item(browser, title="Pricing review", body=LONG_BODY, tags="pricing")
    r = ask(browser, "pricing decisions")
    assert "Matched words: pricing, decisions" in r.text
    assert "pric," not in r.text


def test_ask_with_filters_is_understood(browser):
    add_item(browser, title="Pricing note", body=LONG_BODY, tags="pricing")
    add_item(browser, title="Pricing article", body=LONG_BODY, tags="pricing", kind="article")
    r = ask(browser, "kind:article pricing")
    assert "kind: article" in r.text
    assert "Pricing article" in r.text


def test_ask_requires_csrf(browser):
    r = browser.post("/ask", {"q": "pricing"}, csrf=False)
    assert r.status_code == 403


def test_ask_does_not_leak_another_users_items(make_browser):
    a = make_browser().register(email="a@example.com")
    add_item(a, title="A secret pricing memo", body=LONG_BODY, tags="pricing")
    b = make_browser().register(email="b@example.com", name="B")
    r = ask(b, "what did we decide about pricing")
    assert "Nothing in this library matches" in r.text
    assert "A secret pricing memo" not in r.text


def test_best_sentence_prefers_term_overlap():
    from app.services.ask import best_sentence

    body = (
        "The meeting opened with a short update. "
        "The annual discount stays at fifteen percent for now. "
        "Lunch was late."
    )
    assert "fifteen percent" in best_sentence(body, ["discount"])


def test_best_sentence_falls_back_to_the_first_sentence():
    from app.services.ask import best_sentence

    body = "First sentence is about doors. A second sentence follows here too."
    assert best_sentence(body, ["absent"]).startswith("First sentence")


def test_best_sentence_on_empty_text():
    from app.services.ask import best_sentence

    assert best_sentence("", ["x"]) == ""
    assert best_sentence("short", ["x"]) == "short"


def test_best_sentence_clamps_long_sentences():
    from app.services.ask import best_sentence

    out = best_sentence("pricing " * 200, ["pricing"], fallback=120)
    assert len(out) <= 121


def test_compose_caps_citations_at_three():
    from app.models import Item
    from app.services.ask import compose
    from app.services.search import parse_query, search

    from datetime import datetime, timezone

    items = [
        Item(
            id=index,
            user_id=1,
            title=f"Pricing item {index}",
            body="We agreed the pricing review happens in January. " * 2,
            tags="pricing",
            kind="note",
            created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            origin="written",
        )
        for index in range(1, 6)
    ]
    query = parse_query("pricing review")
    answer = compose("pricing review", query, search(items, query))
    assert len(answer.citations) == 3
    assert answer.source == "local"
    assert answer.read == 3


def test_compose_without_hits_is_honest():
    from app.services.ask import compose
    from app.services.search import parse_query

    query = parse_query("quantum")
    answer = compose("quantum", query, [])
    assert answer.citations == []
    assert answer.read == 0
    assert "nothing to quote" in answer.note


def test_passages_for_model_trims_and_keeps_titles():
    from app.models import Item
    from app.services.ask import passages_for_model
    from app.services.search import Hit

    from datetime import datetime, timezone

    body = "word " * 400
    item = Item(
        id=1,
        user_id=1,
        title="Long note",
        body=body,
        tags="",
        kind="note",
        created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        origin="written",
    )
    passages = passages_for_model([Hit(item, 1.0, [], "")], limit=2, width=50)
    assert passages[0]["title"] == "Long note"
    assert passages[0]["kind"] == "note"
    assert len(passages[0]["text"]) <= 51
    assert passages[0]["text"].endswith("…")
