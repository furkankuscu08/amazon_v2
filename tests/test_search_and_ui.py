import json
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from tests.unit_seed import seed_db
from workbot.main import DemoRateLimiter, app
from workbot.models import AreaEvaluation, Impact, Priority
from workbot.search import Searcher, SetupError, index_visible_records
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
    def check(self, db):
        pass

    def records(self, db, intents):
        return [
            dict(
                db.execute(
                    "SELECT * FROM work_records WHERE id='jira:MKT-482'"
                ).fetchone()
            )
        ]


@pytest.fixture
def web(tmp_path, monkeypatch):
    """A seeded database behind the app; `use(model)` installs a stub and returns a client."""
    path = str(tmp_path / "web.sqlite3")
    db = connect(path)
    seed_db(db)
    db.close()
    monkeypatch.setenv("WORKBOT_DB_PATH", path)
    monkeypatch.setattr(app.state, "searcher", WebSearch(), raising=False)

    def use(model):
        monkeypatch.setattr(app.state, "model", model, raising=False)
        return TestClient(app)

    def search_with(searcher):
        monkeypatch.setattr(app.state, "searcher", searcher)

    return SimpleNamespace(path=path, use=use, search_with=search_with)


def test_web_card_reload_and_source_visibility(web):
    client = web.use(WebModel())
    response = client.get("/")
    assert "simulated Alexa+ experience" in response.text
    # An inline icon, so the browser does not ask for /favicon.ico.
    assert '<link rel="icon" href="data:image/svg+xml,' in response.text
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
    assert "Proposed" not in card.text
    assert f'href="{url}/sources/jira%3AMKT-482"' in card.text
    # No raw source ID is shown as text, and no stock question or search trace.
    assert "jira:MKT-482" not in card.text
    assert "Ask:" not in card.text and "Ask to check" not in card.text
    assert '<span class="label">What to find out</span>' in card.text
    assert 'aria-label="Source for Nina Ellis">Source</a>' in card.text
    assert "Evaluation trace" not in card.text
    assert "Before you start, talk to one person." in card.text
    assert "Related work" in card.text
    assert "Assigned to a Jira issue: ‘" in card.text
    assert "Full list: 1 consultation area and each person's evidence" in card.text
    assert "Model summary (unverified):" in card.text
    assert "Checklist work can clarify pre-launch campaign review scope." in card.text
    assert 'http-equiv="refresh"' not in card.text
    assert client.get(url).text == card.text
    assert client.get(url + "/sources/slack:restricted-plan").status_code == 404
    source_page = client.get(url + "/sources/jira:MKT-482")
    assert source_page.status_code == 200
    assert "<h1>Jira record · " in source_page.text
    assert f'href="{url}">← Back to the plan' in source_page.text
    assert "jira:MKT-482" not in source_page.text
    assert "version" not in source_page.text
    db = connect(web.path)
    saved = db.execute("SELECT card_json FROM sessions WHERE id=?", (sid,)).fetchone()
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
    # An older card without a primary source lists its evidence without links.
    assert "Assignee of jira record" in previous.text
    assert "/sources/" not in previous.text
    db = connect(web.path)
    db.execute(
        """INSERT INTO sessions
        (id, actor, workspace, idem_key, sentence, answers_json, state)
        VALUES ('running', 'maya', 'demo', 'running', 'An idea', '[]', 'processing')"""
    )
    db.commit()
    db.close()
    # No run is working on it (a restart, say): it must not wait forever.
    running = client.get("/sessions/running")
    assert "I could not evaluate this idea" in running.text
    assert "Working on it" not in running.text
    home = client.get("/").text
    assert "Your earlier ideas" in home
    assert "Help plan marketing campaigns" in home
    assert "Plan ready" in home
    db = connect(web.path)
    db.execute("UPDATE people SET active=0 WHERE id='nina'")
    db.commit()
    db.close()
    assert client.get(url).status_code == 410
    assert client.get(url + "/sources/jira:MKT-482").status_code == 410


def test_not_found_does_not_expose_retrieved_but_uncited_source(web):

    class EmptyAreaModel(WebModel):
        def __init__(self):
            self.area_inputs = []

        def complete(self, task, payload):
            if task == "area":
                self.area_inputs.append(json.dumps(payload))
                return AreaEvaluation.model_validate({"people": []})
            return super().complete(task, payload)

    model = EmptyAreaModel()
    client = web.use(model)
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
    assert "No contact found." in page.text
    # Search did return the record: the model saw it, the page must not show it.
    assert "jira:MKT-482" in model.area_inputs[0]
    assert "jira:MKT-482" not in page.text
    assert client.get(url + "/sources/jira:MKT-482").status_code == 404


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
    # Errors are shown as pages, and a framework default gets a sentence of its own.
    assert "<h1>That form is too large</h1>" in oversized.text
    assert "Shorten it and try again." in oversized.text
    unknown = client.get("/nowhere")
    assert unknown.status_code == 404
    assert "There is nothing to show at this address." in unknown.text
    # Other framework errors keep their status and headers but do not claim
    # that the address is empty.
    wrong_method = client.post("/", data={})
    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "GET"
    assert "This request could not be completed." in wrong_method.text
    assert "nothing to show" not in wrong_method.text
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


def test_waiting_page_shows_area_progress_without_people(web):
    reached_area, release = Event(), Event()

    class SlowAreaModel(WebModel):
        def complete(self, task, payload):
            if task == "area":
                reached_area.set()
                assert release.wait(10)
            return super().complete(task, payload)

    client = web.use(SlowAreaModel())
    try:
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


class ScriptedModel(WebModel):
    """WebModel with a chosen area reply and an optional first clarification."""

    def __init__(self, people, question=None):
        self.people = people
        self.question = question
        self.calls = 0
        self.area_inputs = []

    def complete(self, task, payload):
        self.calls += 1
        reply = super().complete(task, payload)
        if task == "impact" and self.question and not payload["answers"]:
            return Impact.model_validate({"question": self.question, "areas": []})
        if task == "area":
            self.area_inputs.append(json.dumps(payload))
            return AreaEvaluation.model_validate({"people": self.people})
        return reply


def _person(pid, role, evidence, relevance):
    return {
        "person_id": pid,
        "contribution": "Synthetic summary used only by the page tests.",
        "role": role,
        "primary_evidence_id": evidence[0],
        "relevance": relevance,
        "evidence_ids": evidence,
        "confidence": "medium",
    }


def _submit(web, model):
    client = web.use(model)
    response = client.post(
        "/sessions",
        data={"idea": "Help plan marketing campaigns", "idempotency_key": "pages"},
        follow_redirects=False,
    )
    app.state.last_run.join(10)
    return client, response.headers["location"]


def test_routing_line_and_directory_source_page(web):
    refs = ["directory:growth-manager", "directory:growth-remit"]
    model = ScriptedModel([_person("marcus", "routing_contact", refs, "adjacent")])
    client, url = _submit(web, model)
    card = client.get(url).text
    # Search returned a record, so the line must not claim nothing was found.
    assert "jira:MKT-482" in model.area_inputs[0]
    assert "No one was identified from the visible work on this." in card
    assert "was found" not in card
    remit = client.get(url + "/sources/directory:growth-remit")
    assert remit.status_code == 200
    assert "<h1>Directory record</h1>" in remit.text
    assert "directory:growth-remit" not in remit.text
    # Both routing sources stay reachable from the list without showing their IDs.
    assert f'href="{url}/sources/directory%3Agrowth-manager"' in card
    assert "directory:growth" not in card
    assert "team remit:" in remit.text and "Since " in remit.text
    manager = client.get(url + "/sources/directory:growth-manager").text
    assert "manages" in manager and "Since 2025-01-01." in manager
    assert client.get(url + "/sources/directory:secret-duty").status_code == 404
    assert "Eve Restricted" not in card + remit.text + manager


def test_routing_line_in_the_plan_is_not_linked_to_a_work_record(web):
    # The routing line is built from the manager and remit records, so it must not
    # link to a work record the model happened to choose as the primary source.
    db = connect(web.path)
    db.execute(
        "INSERT INTO work_links (record_id, person_id, relation) VALUES (?, ?, ?)",
        ("jira:MKT-482", "marcus", "reporter"),
    )
    db.commit()
    db.close()
    refs = ["jira:MKT-482", "directory:growth-manager", "directory:growth-remit"]
    model = ScriptedModel([_person("marcus", "routing_contact", refs, "adjacent")])
    client, url = _submit(web, model)
    card = client.get(url).text
    plan, full_list = card.split('<details class="all">')
    assert "Can route you" in plan and "Manages the team." in plan
    assert "/sources/" not in plan
    for source_id in ("jira%3AMKT-482", "directory%3Agrowth-manager"):
        assert f'href="{url}/sources/{source_id}"' in full_list
    # One caution sentence closes the list in place of per-person text.
    assert "who owns the new idea, has not been established" in full_list


def test_incomplete_review_does_not_also_promise_remaining_people(web):
    # Elena is only the reporter of this record, so the direct proposal is rejected.
    model = ScriptedModel(
        [_person("elena", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    card = client.get(url).text
    assert "Review incomplete." in card
    assert "so no one is shown for it" in card
    assert "remaining verified people are shown" not in card


def test_repeated_answer_submit_returns_to_the_session(web):
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")],
        question="Which campaigns are in scope?",
    )
    client, url = _submit(web, model)
    assert "Which campaigns are in scope?" in client.get(url).text
    first = client.post(url + "/answer", data={"skip": "1"}, follow_redirects=False)
    app.state.last_run.join(10)
    calls = model.calls
    again = client.post(url + "/answer", data={"skip": "1"}, follow_redirects=False)
    assert (first.status_code, again.status_code) == (303, 303)
    assert again.headers["location"] == url
    assert model.calls == calls
    assert "Before you start, talk to one person." in client.get(url).text
    missing = client.post("/sessions/nope/answer", data={"skip": "1"})
    assert missing.status_code == 404


def test_search_check_reports_missing_index_and_unreachable_qdrant(tmp_path):
    db = connect(str(tmp_path / "check.sqlite3"))
    seed_db(db)
    client = QdrantClient(location=":memory:")
    try:
        search = Searcher("unused", client=client, embed_fn=tiny_embedding)
        with pytest.raises(SetupError, match="missing or out of date") as missing:
            search.check(db)
        assert missing.value.command == "python -m workbot.seed"
        index_visible_records(db, "unused", client=client, embed_fn=tiny_embedding)
        search.check(db)

        class Unreachable:
            def collection_exists(self, name):
                raise ConnectionError("refused")

        with pytest.raises(SetupError, match="did not answer") as down:
            Searcher("unused", client=Unreachable()).check(db)
        assert down.value.command == "docker compose up -d"
    finally:
        client.close()
        db.close()


def test_setup_problem_is_shown_before_anything_is_stored_or_sent(web):
    class NotReady(WebSearch):
        def check(self, db):
            raise SetupError("Qdrant did not answer.", "docker compose up -d")

    model = ScriptedModel([], question="Which market is this for?")
    client, location = _submit(web, model)
    calls = model.calls
    web.search_with(NotReady())
    response = client.post(
        "/sessions", data={"idea": "Another idea", "idempotency_key": "setup"}
    )
    assert response.status_code == 503
    assert "did not answer" in response.text
    assert "<code>docker compose up -d</code>" in response.text
    assert "Review incomplete" not in response.text
    answer = client.post(f"{location}/answer", data={"answer": "Retail"})
    assert answer.status_code == 503
    missing = client.post("/sessions/nope/answer", data={"answer": "Retail"})
    assert missing.status_code == 404
    db = connect(web.path)
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    db.close()
    assert model.calls == calls
