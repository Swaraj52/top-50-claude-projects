from fastapi.testclient import TestClient

from tests.conftest import ARTICLE_HABITS


def ids(client, **params):
    return [i["id"] for i in client.get("/api/items", params=params).json()["items"]]


def test_inbox_triage_and_filters(client, save):
    a = save("https://brainweekly.example/sleep", tags=["sleep"])
    b = save("https://habits.example/tiny", ARTICLE_HABITS, tags=["habits"])
    assert ids(client, status="inbox") == [b["id"], a["id"]]
    assert ids(client) == []  # default view is the library

    client.patch(f"/api/items/{a['id']}", json={"status": "library", "favorite": True})
    assert ids(client) == [a["id"]]
    assert ids(client, status="all", favorite=True) == [a["id"]]
    assert ids(client, status="all", tag="habits") == [b["id"]]
    assert ids(client, status="all", kind="video") == []
    assert ids(client, status="all", sort="title") == [b["id"], a["id"]]  # "Tiny…" < "Why…"

    stats = client.get("/api/items/stats").json()
    assert stats == {"inbox": 1, "library": 1, "archived": 0, "favorites": 1, "by_kind": {"article": 2}, "tags": 2, "questions": 0}


def test_editing_tags_reindexes_search(client, save):
    item = save("https://brainweekly.example/sleep")
    client.patch(f"/api/items/{item['id']}", json={"tags": ["Neuro Science"]})
    hit = client.get("/api/search", params={"q": "neuro"}).json()["hits"]
    assert [h["item"]["id"] for h in hit] == [item["id"]]
    assert hit[0]["item"]["tags"] == ["neuro-science"]


def test_tag_rename_merge_and_delete(client, save):
    a = save("https://brainweekly.example/sleep", tags=["ml"])
    b = save("https://habits.example/tiny", ARTICLE_HABITS, tags=["machine-learning"])
    tags = {t["name"]: t for t in client.get("/api/tags").json()}
    # Renaming onto an existing name merges the tags.
    merged = client.patch(f"/api/tags/{tags['ml']['id']}", json={"name": "Machine Learning"}).json()
    assert merged == {"id": tags["machine-learning"]["id"], "name": "machine-learning", "count": 2}
    assert [t["name"] for t in client.get("/api/tags").json()] == ["machine-learning"]

    client.delete(f"/api/tags/{merged['id']}")
    assert client.get("/api/tags").json() == []
    assert client.get(f"/api/items/{a['id']}").json()["tags"] == []
    assert client.get("/api/search", params={"q": "machine learning"}).json()["hits"] == []
    assert client.get(f"/api/items/{b['id']}").status_code == 200


def test_unused_tags_disappear(client, save):
    item = save("https://brainweekly.example/sleep", tags=["temp"])
    client.patch(f"/api/items/{item['id']}", json={"tags": []})
    assert client.get("/api/tags").json() == []


def test_delete_removes_item_from_search(client, save):
    item = save("https://brainweekly.example/sleep")
    assert client.get("/api/search", params={"q": "hippocampus"}).json()["hits"]
    assert client.delete(f"/api/items/{item['id']}").status_code == 204
    assert client.get("/api/search", params={"q": "hippocampus"}).json()["hits"] == []
    assert client.get(f"/api/items/{item['id']}").status_code == 404


def test_validation(client, save):
    item = save("https://brainweekly.example/sleep")
    assert client.patch(f"/api/items/{item['id']}", json={"status": "deleted"}).status_code == 422
    assert client.patch(f"/api/items/{item['id']}", json={"tags": [f"t{i}" for i in range(21)]}).status_code == 422
    assert client.post("/api/items/text", json={"content": ""}).status_code == 422


def test_items_are_private(client, save, make_client):
    item = save("https://brainweekly.example/sleep", tags=["sleep"])
    bob = make_client("bob@example.com", name="Bob")
    assert bob.get("/api/items", params={"status": "all"}).json() == {"items": [], "total": 0}
    assert bob.get(f"/api/items/{item['id']}").status_code == 404
    assert bob.patch(f"/api/items/{item['id']}", json={"title": "x"}).status_code == 404
    assert bob.post(f"/api/items/{item['id']}/summarize").status_code == 404
    assert bob.get("/api/search", params={"q": "hippocampus"}).json()["hits"] == []
    assert bob.get("/api/tags").json() == []
    tag_id = client.get("/api/tags").json()[0]["id"]
    assert bob.delete(f"/api/tags/{tag_id}").status_code == 404
    # The same URL can be saved independently by another user.
    bob_item = bob.post("/api/items/url", json={"url": "https://brainweekly.example/sleep"})
    assert bob_item.status_code == 201 and bob_item.json()["item"]["id"] != item["id"]


def test_auth_basics(app, client, make_client):
    assert client.get("/api/auth/me").json()["email"] == "rhea@example.com"
    anon = make_client()
    assert anon.get("/api/items").status_code == 401
    bad = anon.post("/api/auth/login", json={"email": "rhea@example.com", "password": "wrong"})
    assert bad.status_code == 401
    assert anon.post("/api/auth/login", json={"email": "RHEA@example.com", "password": "long enough 1"}).status_code == 200
    raw = TestClient(app, cookies=anon.cookies)
    assert raw.post("/api/items/text", json={"content": "x"}).status_code == 403  # no CSRF header
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client, make_client):
    anon = make_client()
    for _ in range(10):
        anon.post("/api/auth/login", json={"email": "rhea@example.com", "password": "nope"})
    assert anon.post("/api/auth/login", json={"email": "rhea@example.com", "password": "long enough 1"}).status_code == 429
