from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.db import Base
from app.main import create_app
from app.services import extract, text


def test_chunking_respects_size_and_keeps_all_text():
    para = "Sentence number {0} is here. " * 3
    body = "\n\n".join(para.format(i) for i in range(60))
    chunks = text.chunk_text(body, size=400)
    assert all(len(c) <= 400 for c in chunks)
    assert len(chunks) > 5
    assert "Sentence number 59" in chunks[-1]


def test_chunking_splits_huge_paragraphs():
    chunks = text.chunk_text("word " * 1000, size=300)
    assert all(len(c) <= 300 for c in chunks) and len(chunks) >= 15


def test_fts_query_is_safe():
    assert text.fts_query('The "best" OR NOT sleep* tips') == '"best"* AND "sleep"* AND "tips"*'
    assert text.fts_query("sleep tips", mode="or") == '"sleep"* OR "tips"*'
    assert text.fts_query("the and of") is None


def test_normalize_tag():
    assert text.normalize_tag("  Machine Learning ") == "machine-learning"
    assert text.normalize_tag("#AI/ML!") == "aiml"
    assert text.normalize_tag("???") == ""
    assert text.normalize_tag("x" * 80) == "x" * 40


def test_extractive_summary_picks_central_sentences():
    body = (
        "Sleep is essential for memory. Deep sleep consolidates memory in the hippocampus. "
        "The weather was nice that day. Students who sleep after studying remember more of what they learned. "
        "Memory and sleep are deeply linked in every study we reviewed."
    )
    tldr, points = text.extractive_summary(body, n_points=2)
    assert "sleep" in tldr.lower() and "weather" not in tldr.lower()
    assert all("weather" not in p for p in points)


def test_html_extraction_without_metadata_falls_back_to_title_tag():
    data = extract.from_html("<html><head><title>  Bare   page </title></head><body><p>" + "Plain words here. " * 30 + "</p></body></html>")
    assert data.title == "Bare page" and "Plain words here" in data.content


def test_migrations_match_models(migrated_db):
    engine = create_engine(f"sqlite:///{migrated_db.as_posix()}")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"include_object": lambda o, n, t, r, c: not (t == "table" and "_fts" in n)})
        diff = compare_metadata(ctx, Base.metadata)
    engine.dispose()
    assert diff == []


def test_spa_serving(tmp_path, settings):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>shell</html>")
    (dist / "assets" / "a.js").write_text("ok")
    app = create_app(Settings(**{**settings.model_dump(), "frontend_dist": dist}, _env_file=None))
    with TestClient(app) as c:
        assert c.get("/assets/a.js").text == "ok"
        assert c.get("/library").text == "<html>shell</html>"
        assert c.get("/api/nope").status_code == 404
    app.state.engine.dispose()
