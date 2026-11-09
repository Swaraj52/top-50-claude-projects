from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, run_migrations
from app.services import fetcher, youtube

PUBLIC_IP = "93.184.216.34"
DNS = {"internal.example": "10.0.0.5", "localhost": "127.0.0.1", "metadata.example": "169.254.169.254"}

ARTICLE_SLEEP = """<html><head><title>Why sleep matters | Brain Weekly</title>
<meta property="og:site_name" content="Brain Weekly"><meta name="author" content="Dr. Maya Rao">
<meta name="description" content="How sleep consolidates memory."></head>
<body><nav>Home Subscribe Login</nav><article><h1>Why sleep matters for memory</h1>
<p>During deep sleep the hippocampus replays the day's experiences and transfers them to the
neocortex for long-term storage. This consolidation is why students who sleep after studying
remember more than those who stay awake.</p>
<p>A short afternoon nap of twenty minutes improves alertness without causing grogginess, while
naps longer than an hour can leave you groggy because you wake during slow-wave sleep.</p>
<p>Caffeine blocks adenosine receptors, so a coffee after 2pm can delay sleep onset by an hour
and reduce deep sleep, which in turn weakens memory consolidation.</p></article>
<footer>Copyright Brain Weekly</footer></body></html>"""

ARTICLE_HABITS = """<html><head><title>Tiny habits that stick</title></head><body><article>
<h1>Tiny habits that stick</h1>
<p>Habit formation depends on a clear cue, a small routine and an immediate reward. Start with a
habit so small it feels trivial, such as reading one page or doing two push-ups.</p>
<p>Stack the new habit onto an existing one: after I pour my morning coffee, I will write one
sentence in my journal. Consistency matters more than intensity in the first month.</p>
</article></body></html>"""


class FakeWeb:
    """An in-memory web: url -> (status, content-type, body, extra headers)."""

    def __init__(self) -> None:
        self.pages: dict[str, tuple[int, str, bytes, dict]] = {}
        self.requests: list[str] = []

    def add(self, url: str, body: str | bytes, content_type: str = "text/html; charset=utf-8", status: int = 200, headers: dict | None = None) -> None:
        self.pages[url] = (status, content_type, body.encode() if isinstance(body, str) else body, headers or {})

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        key = url if url in self.pages else url.split("?")[0]
        if key not in self.pages:
            return httpx.Response(404, text="not found")
        status, ctype, body, headers = self.pages[key]
        return httpx.Response(status, content=body, headers={"content-type": ctype, **headers})


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("template") / "template.db"
    run_migrations(f"sqlite:///{path.as_posix()}")
    return path


@pytest.fixture
def web(monkeypatch) -> FakeWeb:
    fake = FakeWeb()
    monkeypatch.setattr(fetcher, "resolve_host", lambda host: [DNS.get(host, PUBLIC_IP)])
    monkeypatch.setattr(youtube, "fetch_transcript", lambda vid: None)
    return fake


@pytest.fixture
def settings(tmp_path, migrated_db) -> Settings:
    db_file = tmp_path / "test.db"
    shutil.copy(migrated_db, db_file)
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_file.as_posix()}",
        anthropic_api_key="",
        run_migrations=False,
        frontend_dist=tmp_path / "no-frontend",
    )


@pytest.fixture
def app(settings, web):
    application = create_app(settings)
    application.state.http_transport = httpx.MockTransport(web.handler)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def make_client(app) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(email: str | None = None, name: str = "Rhea") -> TestClient:
        c = TestClient(app, headers={"X-Requested-With": "library"})
        c.__enter__()
        clients.append(c)
        if email:
            r = c.post("/api/auth/register", json={"email": email, "password": "long enough 1", "name": name})
            assert r.status_code == 201, r.text
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client("rhea@example.com")


@pytest.fixture
def save(client, web):
    """Publish a page on the fake web and save it; returns the item JSON."""

    def _save(url: str, html: str = ARTICLE_SLEEP, **extra) -> dict:
        web.add(url.split("#")[0], html)  # browsers never send the fragment
        r = client.post("/api/items/url", json={"url": url, **extra})
        assert r.status_code == 201, r.text
        return r.json()["item"]

    return _save
