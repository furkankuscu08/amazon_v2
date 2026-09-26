import json

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from workbot.main import DemoRateLimiter, app
from workbot.models import AreaEvaluation, Impact, Priority
from workbot.search import Searcher, index_visible_records
from workbot.seed import seed_db
from workbot.storage import connect


def tiny_embedding(text: str) -> list[float]:
    text = text.lower()
    if "loyalty" in text:
        return [0.0, 1.0, 0.0]
    if "launch" in text or "audience" in text:
        return [1.0, 0.0, 0.0]
    return [0.0, 0.0, 1.0]


def test_bm25_and_qdrant_both_search_only_visible_records(tmp_path):
    db = connect(str(tmp_path / "work.sqlite3"))
    seed_db(db)
    client = QdrantClient(location=":memory:")
    try:
        assert (
            index_visible_records(db, "unused", client=client, embed_fn=tiny_embedding)
            == 8
        )
        search = Searcher("unused", client=client, embed_fn=tiny_embedding)
        intents = [
            {
                "keyword": "Finalize audience checklist",
                "semantic": "loyalty points offer",
            }
        ]
        first = search.records(db, intents)
        channels = {record["id"]: record["retrieval_channels"] for record in first}
        assert channels["jira:MKT-482"] == ["bm25"]  # excluded by orthogonal toy vector
        assert channels["docs:wallet-loyalty"] == ["qdrant"]  # no keyword overlap
        assert all(record["visibility"] == "maya" for record in first)
        baseline = [record["id"] for record in first]
        db.execute(
            "INSERT INTO work_records VALUES ('docs:new-restricted','document','2026-09-01',?, 'restricted','v1')",
            ("MKT-482 launch audience preparation by Eve Restricted",),
        )
        db.commit()
        assert (
            index_visible_records(db, "unused", client=client, embed_fn=tiny_embedding)
            == 8
        )
        assert [r["id"] for r in search.records(db, intents)] == baseline
        assert all("restricted" not in json.dumps(r).lower() for r in first)
        db.execute(
            "UPDATE work_records SET visibility='restricted' WHERE id='jira:MKT-482'"
        )
        db.commit()
        assert not db.execute(
            "SELECT 1 FROM visible_fts WHERE record_id='jira:MKT-482'"
        ).fetchone()
        with pytest.raises(RuntimeError, match="reseeding"):
            search.records(db, intents)
        db.execute("UPDATE work_records SET visibility='maya' WHERE id='jira:MKT-482'")
        db.commit()
        index_visible_records(db, "unused", client=client, embed_fn=tiny_embedding)
        db.execute("DELETE FROM visible_fts")
        db.commit()
        with pytest.raises(RuntimeError, match="reseeding"):
            search.records(db, intents)
    finally:
        client.close()
        db.close()


def test_failed_reindex_invalidates_old_search_marker(tmp_path, monkeypatch):
    db = connect(str(tmp_path / "work.sqlite3"))
    seed_db(db)
    client = QdrantClient(location=":memory:")
    try:
        index_visible_records(db, "unused", client=client, embed_fn=tiny_embedding)
        search = Searcher("unused", client=client, embed_fn=tiny_embedding)
        intents = [{"keyword": "launch", "semantic": "launch review"}]
        assert search.records(db, intents)

        def failed_upsert(*args, **kwargs):
            raise RuntimeError("simulated vector rebuild failure")

        with monkeypatch.context() as patch:
            patch.setattr(client, "upsert", failed_upsert)
            with pytest.raises(RuntimeError, match="rebuild failure"):
                index_visible_records(
                    db, "unused", client=client, embed_fn=tiny_embedding
                )
        with pytest.raises(RuntimeError, match="reseeding"):
            search.records(db, intents)

        index_visible_records(db, "unused", client=client, embed_fn=tiny_embedding)
        assert search.records(db, intents)
    finally:
        client.close()
        db.close()


class WebModel:
    def complete(self, task, payload):
        if task == "impact":
            return Impact.model_validate(
                {
                    "question": None,
                    "areas": [
                        {
                            "id": "growth",
                            "label": "Growth Marketing",
                            "rationale": "Campaign approval should be reviewed before launch.",
                            "search_intents": [
                                {
                                    "keyword": "campaign launch",
                                    "semantic": "retail audience launch approval",
                                }
                            ],
                            "mapping": "mapped",
                            "org_unit_id": "growth",
                            "mapping_reason": None,
                        }
                    ],
                }
            )
        if task == "area":
            return AreaEvaluation.model_validate(
                {
                    "people": [
                        {
                            "person_id": "nina",
                            "role": "direct_contact",
                            "evidence_ids": ["jira:MKT-482"],
                            "confidence": "high",
                            "ask": "Who reviews campaign launches?",
                            "unverified": "Ownership remains to be checked.",
                        }
                    ]
                }
            )
        return Priority.model_validate({"order": ["growth"], "shared_question": None})


class WebSearch:
    def records(self, db, intents):
        return [
            dict(
                db.execute(
                    "SELECT * FROM work_records WHERE id='jira:MKT-482'"
                ).fetchone()
            )
        ]


def test_web_card_reload_and_source_visibility(tmp_path, monkeypatch):
    path = str(tmp_path / "web.sqlite3")
    db = connect(path)
    seed_db(db)
    db.close()
    monkeypatch.setenv("WORKBOT_DB_PATH", path)
    app.state.model = WebModel()
    app.state.searcher = WebSearch()
    try:
        client = TestClient(app)
        response = client.get("/")
        assert "simulated Alexa+ experience" in response.text
        response = client.post(
            "/sessions",
            data={"idea": "Help plan marketing campaigns", "idempotency_key": "abc"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        url = response.headers["location"]
        card = client.get(url)
        assert card.status_code == 200
        assert "Nina Ellis" in card.text
        assert "Eve Restricted" not in card.text
        assert client.get(url).text == card.text
        assert client.get(url + "/sources/slack:restricted-plan").status_code == 404
        assert client.get(url + "/sources/jira:MKT-482").status_code == 200
        db = connect(path)
        db.execute("UPDATE people SET active=0 WHERE id='nina'")
        db.commit()
        db.close()
        assert client.get(url).status_code == 410
        assert client.get(url + "/sources/jira:MKT-482").status_code == 410
    finally:
        del app.state.model
        del app.state.searcher


def test_invalid_or_oversized_form_is_rejected_before_model_call():
    client = TestClient(app)
    bad_utf8 = client.post(
        "/sessions",
        content=b"idea=\xff\xfe&idempotency_key=x",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert bad_utf8.status_code == 400
    bad_percent = client.post(
        "/sessions",
        content=b"idea=%FF&idempotency_key=x",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert bad_percent.status_code == 400
    oversized = client.post(
        "/sessions",
        content=b"idea=" + b"a" * 5000,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert oversized.status_code == 413
    cross_site = client.post(
        "/sessions",
        data={"idea": "A project", "idempotency_key": "k"},
        headers={"Origin": "https://other.example"},
    )
    assert cross_site.status_code == 403


def test_demo_rate_limit_resets_after_window():
    limiter = DemoRateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("maya", now=0)
    assert limiter.allow("maya", now=1)
    assert not limiter.allow("maya", now=2)
    assert limiter.allow("other", now=2)
    assert limiter.allow("maya", now=11)
