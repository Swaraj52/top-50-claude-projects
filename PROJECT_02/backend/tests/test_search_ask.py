import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.routers.common import ai_client
from app.services.text import HIGHLIGHT_END, HIGHLIGHT_START
from tests.conftest import ARTICLE_HABITS


class FakeMessages:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def reply(payload, stop_reason="end_turn"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason, model="claude-opus-5-5")


@pytest.fixture
def with_ai(app, settings):
    settings.anthropic_api_key = "sk-test-not-real"

    def install(outcome):
        messages = FakeMessages(outcome)
        app.dependency_overrides[ai_client] = lambda: SimpleNamespace(beta=SimpleNamespace(messages=messages))
        return messages

    yield install
    app.dependency_overrides.clear()


@pytest.fixture
def library(save):
    sleep = save("https://brainweekly.example/sleep", tags=["sleep"])
    habits = save("https://habits.example/tiny", ARTICLE_HABITS, tags=["habits"])
    return sleep, habits


# --- search ---------------------------------------------------------------------------


def test_search_ranks_and_highlights(client, library):
    sleep, _ = library
    out = client.get("/api/search", params={"q": "naps memory"}).json()
    assert out["mode"] == "all"
    assert [h["item"]["id"] for h in out["hits"]] == [sleep["id"]]
    snippet = out["hits"][0]["snippet"]
    assert f"{HIGHLIGHT_START}nap" in snippet.lower() or f"{HIGHLIGHT_START}memory" in snippet.lower()
    assert HIGHLIGHT_END in snippet


def test_search_uses_stemming_and_prefixes(client, library):
    _, habits = library
    # Prefix matching: "habit" finds "habits"; Porter stemming: "consolidating" finds "consolidation".
    assert [h["item"]["id"] for h in client.get("/api/search", params={"q": "habit"}).json()["hits"]] == [habits["id"]]
    assert client.get("/api/search", params={"q": "consolidating"}).json()["hits"][0]["item"]["id"] == library[0]["id"]


def test_search_falls_back_to_any_word(client, library):
    out = client.get("/api/search", params={"q": "hippocampus journal"}).json()
    assert out["mode"] == "any" and len(out["hits"]) == 2


def test_search_ignores_operators_and_stopwords(client, library):
    assert client.get("/api/search", params={"q": 'the "OR" AND NOT ('}).json()["hits"] == []
    assert client.get("/api/search", params={"q": "sleep* OR -habits"}).status_code == 200


def test_archived_items_are_hidden_from_search_unless_asked(client, library):
    sleep, _ = library
    client.patch(f"/api/items/{sleep['id']}", json={"status": "archived"})
    assert client.get("/api/search", params={"q": "hippocampus"}).json()["hits"] == []
    assert client.get("/api/search", params={"q": "hippocampus", "include_archived": True}).json()["hits"]


# --- ask ------------------------------------------------------------------------------


def test_ask_without_key_returns_ranked_passages(client, library):
    sleep, _ = library
    a = client.post("/api/ask", json={"question": "Does caffeine affect deep sleep?"}).json()
    assert a["source"] == "passages" and a["model"] is None
    assert "No AI answer" in a["answer"]
    assert a["citations"][0]["item_id"] == sleep["id"]
    assert "Caffeine blocks adenosine" in " ".join(c["excerpt"] for c in a["citations"])


def test_ask_with_nothing_relevant_says_so_without_calling_ai(client, library, with_ai):
    messages = with_ai(reply({"answer": "x", "cited_sources": [], "confidence": "low"}))
    a = client.post("/api/ask", json={"question": "quantum chromodynamics lattice"}).json()
    assert "Nothing in your library" in a["answer"] and a["citations"] == []
    assert messages.calls == []


def test_ask_with_ai_cites_only_real_sources(client, library, with_ai):
    sleep, _ = library
    messages = with_ai(
        reply({"answer": "Yes: caffeine after 2pm delays sleep [S1] and weakens consolidation [S9].", "cited_sources": [1, 9], "confidence": "high"})
    )
    a = client.post("/api/ask", json={"question": "Does caffeine affect deep sleep?"}).json()
    assert a["source"] == "ai" and a["model"] == "claude-opus-5-5" and a["confidence"] == "high"
    assert "[S9]" not in a["answer"] and "[S1]" in a["answer"]
    assert [c["n"] for c in a["citations"]] == [1] and a["citations"][0]["item_id"] == sleep["id"]

    [call] = messages.calls
    assert call["output_config"]["format"]["type"] == "json_schema" and call["output_config"]["effort"] == "medium"
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    assert "[S1] Why sleep matters for memory" in call["messages"][0]["content"]


def test_ask_can_be_limited_to_a_tag(client, library):
    _, habits = library
    a = client.post("/api/ask", json={"question": "habit memory coffee", "tag": "habits"}).json()
    assert {c["item_id"] for c in a["citations"]} == {habits["id"]}
    assert client.post("/api/ask", json={"question": "anything", "tag": "nope"}).status_code == 404


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (reply("not json"), "unexpected format"),
        (reply({"answer": "", "cited_sources": [], "confidence": "low"}), "empty answer"),
        (reply({"answer": "x", "cited_sources": [], "confidence": "low"}, stop_reason="refusal"), "declined"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), "could not be reached"),
    ],
)
def test_ask_ai_failures_fall_back_to_passages(client, library, with_ai, outcome, expected):
    with_ai(outcome)
    a = client.post("/api/ask", json={"question": "caffeine and sleep"}).json()
    assert a["source"] == "passages" and expected in a["note"] and a["citations"]


def test_history_and_forget(client, library, make_client):
    first = client.post("/api/ask", json={"question": "naps"}).json()
    client.post("/api/ask", json={"question": "habits"})
    assert [q["question"] for q in client.get("/api/ask/history").json()] == ["habits", "naps"]
    bob = make_client("bob@example.com", name="Bob")
    assert bob.get("/api/ask/history").json() == []
    assert bob.delete(f"/api/ask/{first['id']}").status_code == 404
    assert client.delete(f"/api/ask/{first['id']}").status_code == 204
    assert len(client.get("/api/ask/history").json()) == 1


def test_ask_is_rate_limited(client, library):
    for _ in range(10):
        client.post("/api/ask", json={"question": "naps"})
    assert client.post("/api/ask", json={"question": "naps"}).status_code == 429


# --- summaries ----------------------------------------------------------------------------


def test_extractive_summary_without_key(client, library):
    sleep, _ = library
    item = client.post(f"/api/items/{sleep['id']}/summarize").json()
    s = item["summary"]
    assert s["source"] == "extractive" and s["model"] is None and s["note"] is None
    assert s["tldr"] and len(s["key_points"]) >= 1
    assert "sleep" in s["suggested_tags"]
    assert client.get("/api/items", params={"status": "inbox"}).json()["items"][-1]["tldr"] == s["tldr"]


def test_ai_summary_is_validated(client, library, with_ai):
    sleep, _ = library
    messages = with_ai(reply({"tldr": "Sleep consolidates memory.", "key_points": ["Naps help", "  ", "Avoid late coffee"], "suggested_tags": ["Sleep Science", "#memory", "sleep science"]}))
    s = client.post(f"/api/items/{sleep['id']}/summarize").json()["summary"]
    assert s["source"] == "ai" and s["model"] == "claude-opus-5-5"
    assert s["key_points"] == ["Naps help", "Avoid late coffee"]
    assert s["suggested_tags"] == ["sleep-science", "memory"]
    assert messages.calls[0]["output_config"]["effort"] == "low"
    assert "hippocampus" in messages.calls[0]["messages"][0]["content"]


def test_ai_summary_failure_falls_back_with_note(client, library, with_ai):
    sleep, _ = library
    with_ai(reply({"tldr": "", "key_points": [], "suggested_tags": []}))
    s = client.post(f"/api/items/{sleep['id']}/summarize").json()["summary"]
    assert s["source"] == "extractive" and "AI summary unavailable" in s["note"]


def test_editing_content_clears_stale_summary(client, library):
    sleep, _ = library
    client.post(f"/api/items/{sleep['id']}/summarize")
    item = client.patch(f"/api/items/{sleep['id']}", json={"content": "Totally new text about tides."}).json()
    assert item["summary"] is None
