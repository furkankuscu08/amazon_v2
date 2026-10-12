import json
from threading import Event

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from tests.unit_seed import seed_db
from workbot.main import DemoRateLimiter, app
from workbot.models import AreaEvaluation, Impact, Priority
from workbot.search import Searcher, index_visible_records
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
                            "consultation_need": "Who reviews retail campaign launches before go-live.",
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
                            "contribution": "Checklist work can clarify pre-launch campaign review scope.",
                            "role": "direct_contact",
                            "primary_evidence_id": "jira:MKT-482",
                            "relevance": "direct",
                            "evidence_ids": ["jira:MKT-482"],
                            "confidence": "high",
                        }
                    ]
                }
            )
        return Priority.model_validate(
            {"order": ["growth"], "shared_question": None, "first_conversations": []}
        )


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
        app.state.last_run.join(10)
        sid = url.rsplit("/", 1)[-1]
        card = client.get(url)
        assert card.status_code == 200
        assert "Nina Ellis" in card.text
        assert "Eve Restricted" not in card.text
        assert "Proposed direct contact" in card.text
        assert "Primary cited source:" in card.text
        assert f'href="{url}/sources/jira%3AMKT-482"' in card.text
        assert "Ask to check the connection:" in card.text
        assert "Before you start, talk to one person." in card.text
        assert "Related work" in card.text
        assert "Assignee of a jira record:" in card.text
        assert "All 1 consultation areas and everyone considered" in card.text
        assert "Model summary (unverified):" in card.text
        assert (
            "Checklist work can clarify pre-launch campaign review scope." in card.text
        )
        assert 'http-equiv="refresh"' not in card.text
        assert client.get(url).text == card.text
        assert client.get(url + "/sources/slack:restricted-plan").status_code == 404
        assert client.get(url + "/sources/jira:MKT-482").status_code == 200
        db = connect(path)
        saved = db.execute(
            "SELECT card_json FROM sessions WHERE id=?", (sid,)
        ).fetchone()
        old_card = json.loads(saved["card_json"])
        del old_card["areas"][0]["people"][0]["primary_evidence_id"]
        db.execute(
            "UPDATE sessions SET card_json=? WHERE id=?",
            (json.dumps(old_card), sid),
        )
        db.commit()
        db.close()
        previous = client.get(url)
        assert previous.status_code == 200
        assert "Primary cited source:" not in previous.text
        assert "Source IDs and dates" in previous.text
        db = connect(path)
        db.execute(
            """INSERT INTO sessions
            (id, actor, workspace, idem_key, sentence, answers_json, state)
            VALUES ('running', 'maya', 'demo', 'running', 'An idea', '[]', 'processing')"""
        )
        db.commit()
        db.close()
        # No run is working on it (a restart, say): it must not wait forever.
        running = client.get("/sessions/running")
        assert "Unable to evaluate this request safely" in running.text
        assert "Working on it" not in running.text
        home = client.get("/").text
        assert "Your earlier ideas" in home
        assert "Help plan marketing campaigns" in home
        assert "Plan ready" in home
        db = connect(path)
        db.execute("UPDATE people SET active=0 WHERE id='nina'")
        db.commit()
        db.close()
        assert client.get(url).status_code == 410
        assert client.get(url + "/sources/jira:MKT-482").status_code == 410
    finally:
        del app.state.model
        del app.state.searcher


def test_not_found_does_not_expose_retrieved_but_uncited_source(tmp_path, monkeypatch):
    path = str(tmp_path / "no_contact.sqlite3")
    db = connect(path)
    seed_db(db)
    db.close()
    monkeypatch.setenv("WORKBOT_DB_PATH", path)

    class EmptyAreaModel(WebModel):
        def complete(self, task, payload):
            if task == "area":
                return AreaEvaluation.model_validate({"people": []})
            return super().complete(task, payload)

    app.state.model = EmptyAreaModel()
    app.state.searcher = WebSearch()
    try:
        client = TestClient(app)
        response = client.post(
            "/sessions",
            data={"idea": "Help plan marketing campaigns", "idempotency_key": "empty"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        url = response.headers["location"]
        app.state.last_run.join(10)
        page = client.get(url)
        assert page.status_code == 200
        assert "No verified contact found" in page.text
        assert "Accessible records: 1" in page.text
        assert "jira:MKT-482" not in page.text
        assert client.get(url + "/sources/jira:MKT-482").status_code == 404
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


def test_waiting_page_shows_area_progress_without_people(tmp_path, monkeypatch):
    path = str(tmp_path / "progress.sqlite3")
    db = connect(path)
    seed_db(db)
    db.close()
    monkeypatch.setenv("WORKBOT_DB_PATH", path)
    reached_area, release = Event(), Event()

    class SlowAreaModel(WebModel):
        def complete(self, task, payload):
            if task == "area":
                reached_area.set()
                assert release.wait(10)
            return super().complete(task, payload)

    app.state.model = SlowAreaModel()
    app.state.searcher = WebSearch()
    try:
        client = TestClient(app)
        response = client.post(
            "/sessions",
            data={"idea": "Help plan marketing campaigns", "idempotency_key": "slow"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        url = response.headers["location"]
        assert reached_area.wait(10)
        waiting = client.get(url)
        assert "Working on it" in waiting.text
        assert "Checking " in waiting.text
        assert "Nina Ellis" not in waiting.text
        assert "jira:MKT-482" not in waiting.text
        # Resubmitting the same request must not start a second run.
        again = client.post(
            "/sessions",
            data={"idea": "Help plan marketing campaigns", "idempotency_key": "slow"},
            follow_redirects=False,
        )
        assert again.headers["location"] == url
        release.set()
        app.state.last_run.join(10)
        done = client.get(url)
        assert "Before you start, talk to one person." in done.text
        assert "Working on it" not in done.text
        assert app.state.model.__class__ is SlowAreaModel
    finally:
        release.set()
        del app.state.model
        del app.state.searcher
