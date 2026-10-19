import json
from datetime import datetime, timedelta
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

import workbot.main as main_module
from tests.unit_seed import seed_db
from workbot.main import DemoRateLimiter, app
from workbot.models import AreaEvaluation, Impact, Priority
from workbot.search import Searcher, SetupError, index_visible_records
from workbot.speech import SpeechError
from workbot.storage import connect
from workbot.transcribe import TranscriptionError


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
    # Every test client shares one address, so each test gets its own request limit.
    monkeypatch.setattr(main_module, "demo_limiter", DemoRateLimiter())
    monkeypatch.setattr(main_module, "reply_limiter", DemoRateLimiter(limit=60))

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
    # The model's own summary is never shown.
    assert "Model summary" not in card.text
    assert "pre-launch campaign review scope" not in card.text
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
    # A card stored before summaries were dropped still holds one; it stays hidden.
    old_card["areas"][0]["people"][0]["contribution"] = "OLDER_MODEL_SUMMARY."
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
    assert "OLDER_MODEL_SUMMARY" not in previous.text
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
    assert "Alexa could not evaluate this idea" in running.text
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
    # The routing line is built from both records, so the plan links neither.
    assert "/sources/" not in card.split('<details class="all">')[0]
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


def test_current_responsibility_in_the_plan_links_its_directory_source(web):
    model = ScriptedModel(
        [_person("jules", "direct_contact", ["directory:jules-approval"], "direct")]
    )
    client, url = _submit(web, model)
    plan = client.get(url).text.split('<details class="all">')[0]
    assert "Current responsibility" in plan
    assert f'href="{url}/sources/directory%3Ajules-approval"' in plan
    assert "directory:jules" not in plan


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
    # The direct proposal cites a source that is not in Elena's evidence.
    model = ScriptedModel(
        [_person("elena", "direct_contact", ["jira:NOT-IN-POOL"], "direct")]
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


class StubSpeech:
    """Records the text it is asked to read; `fail` makes Polly unavailable."""

    def __init__(self, fail=False):
        self.texts = []
        self.fail = fail

    def audio(self, text):
        self.texts.append(text)
        if self.fail:
            raise SpeechError("Audio is not available right now.")
        return b"ID3-synthetic-audio"


def test_listen_reads_exactly_the_spoken_plan_on_the_page(web, monkeypatch):
    speech = StubSpeech()
    monkeypatch.setattr(app.state, "speech", speech, raising=False)
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    page = client.get(url).text
    assert '<section class="screen"' in page
    assert f'data-speech="{url}/speech.mp3"' in page
    reply = client.get(url + "/speech.mp3")
    assert reply.status_code == 200
    assert reply.headers["content-type"] == "audio/mpeg"
    assert reply.content == b"ID3-synthetic-audio"
    [text] = speech.texts
    assert text.startswith("Before you start, talk to one person. Start with Nina")
    # Every sentence that is read aloud is also shown in the panel.
    panel = page.split('<section class="screen"', 1)[1].split("</section>", 1)[0]
    assert all(sentence.strip() in panel for sentence in text.split(". "))


def test_listen_reads_the_question_and_nothing_elsewhere(web, monkeypatch):
    speech = StubSpeech()
    monkeypatch.setattr(app.state, "speech", speech, raising=False)
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")],
        question="Which campaigns are in scope?",
    )
    client, url = _submit(web, model)
    assert client.get(url + "/speech.mp3").status_code == 200
    assert speech.texts == [
        "One clarification before searching. Which campaigns are in scope?"
    ]
    missing = client.get("/sessions/nope/speech.mp3")
    assert missing.status_code == 404
    assert "nothing to read aloud" in missing.text


def test_listen_has_nothing_to_read_for_a_stale_or_refused_session(web, monkeypatch):
    speech = StubSpeech()
    monkeypatch.setattr(app.state, "speech", speech, raising=False)
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    db = connect(web.path)
    db.execute("UPDATE people SET active=0 WHERE id='nina'")
    db.execute(
        """INSERT INTO sessions (id, actor, workspace, idem_key, sentence, answers_json, state)
        VALUES ('refused', 'maya', 'demo', 'refused', 'An idea', '[]', 'refusal')"""
    )
    db.commit()
    db.close()
    assert client.get(url).status_code == 410
    assert client.get(url + "/speech.mp3").status_code == 404
    assert client.get("/sessions/refused/speech.mp3").status_code == 404
    assert speech.texts == []


def test_listen_failure_is_a_plain_message(web, monkeypatch):
    monkeypatch.setattr(app.state, "speech", StubSpeech(fail=True), raising=False)
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    reply = client.get(url + "/speech.mp3")
    assert reply.status_code == 503
    assert "Audio is not available right now." in reply.text


def _sessions(path):
    db = connect(path)
    try:
        return db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        db.close()


def test_access_code_gates_every_page_until_it_is_entered(web, monkeypatch):
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", "judge-2026")
    client = web.use(ScriptedModel([]))
    home = client.get("/", follow_redirects=False)
    assert (home.status_code, home.headers["location"]) == (303, "/access?next=%2F")
    for path in (
        "/sessions/any",
        "/sessions/any/speech.mp3",
        "/sessions/any/sources/jira:MKT-482",
    ):
        reply = client.get(path, follow_redirects=False)
        assert reply.status_code == 303
        assert reply.headers["location"].startswith("/access?next=")
    submit = client.post(
        "/sessions",
        data={"idea": "Help plan marketing campaigns", "idempotency_key": "gate"},
        follow_redirects=False,
    )
    assert submit.status_code == 303 and submit.headers["location"].startswith(
        "/access"
    )
    assert _sessions(web.path) == 0
    assert "Enter the demo access code" in client.get("/access?next=%2F").text
    wrong = client.post("/access", data={"code": "judge-2025", "next": "/"})
    assert wrong.status_code == 401
    assert "That code is not right." in wrong.text
    assert main_module.ACCESS_COOKIE not in client.cookies
    # The code is accepted; a target on another site is replaced by the home page.
    right = client.post(
        "/access",
        data={"code": "judge-2026", "next": "//evil.example/x"},
        follow_redirects=False,
    )
    assert (right.status_code, right.headers["location"]) == (303, "/")
    assert "judge-2026" not in right.headers["set-cookie"]
    assert "httponly" in right.headers["set-cookie"].lower()
    assert client.get("/").status_code == 200
    # A new code invalidates cookies issued for the old one.
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", "new-code")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_wrong_access_codes_are_limited(web, monkeypatch):
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", "judge-2026")
    monkeypatch.setattr(main_module, "access_limiter", DemoRateLimiter(2, 600))
    client = web.use(ScriptedModel([]))
    codes = [client.post("/access", data={"code": "x"}).status_code for _ in range(2)]
    assert codes == [401, 401]
    # Once the limit is reached, even the right code waits.
    right = client.post("/access", data={"code": "judge-2026"}, follow_redirects=False)
    assert right.status_code == 429
    assert main_module.ACCESS_COOKIE not in client.cookies


def test_access_code_ignores_surrounding_spaces_and_odd_targets(web, monkeypatch):
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", " judge-2026 \n")
    client = web.use(ScriptedModel([]))
    assert client.get("/access?next=//[").status_code == 200
    reply = client.post(
        "/access",
        data={"code": "judge-2026", "next": "//["},
        follow_redirects=False,
    )
    assert (reply.status_code, reply.headers["location"]) == (303, "/")


@pytest.mark.parametrize("value", ["abc", "-1", "1.5"])
def test_a_bad_daily_limit_stops_new_ideas_with_a_plain_message(
    web, monkeypatch, value
):
    monkeypatch.setenv("WORKBOT_DAILY_IDEAS", value)
    client = web.use(ScriptedModel([]))
    reply = client.post(
        "/sessions",
        data={"idea": "Help plan marketing campaigns", "idempotency_key": "bad"},
    )
    assert reply.status_code == 503
    assert "daily idea limit is not set up correctly" in reply.text
    assert _sessions(web.path) == 0


@pytest.mark.parametrize(
    "target", ["//evil.example/x", "/\\evil.example", "https://evil.example", "/\nx"]
)
def test_access_page_only_returns_to_a_path_on_this_site(web, monkeypatch, target):
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", "judge-2026")
    client = web.use(ScriptedModel([]))
    reply = client.post(
        "/access",
        data={"code": "judge-2026", "next": target},
        follow_redirects=False,
    )
    assert reply.headers["location"] == "/"


def test_non_ascii_code_or_cookie_is_simply_wrong(web, monkeypatch):
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", "judge-2026")
    client = web.use(ScriptedModel([]))
    assert client.post("/access", data={"code": "jüri"}).status_code == 401
    client.cookies.set(main_module.ACCESS_COOKIE, "not-the-digest")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_without_an_access_code_there_is_no_gate(web):
    client = web.use(ScriptedModel([]))
    assert client.get("/").status_code == 200
    reply = client.get("/access?next=%2Fsessions%2Fx", follow_redirects=False)
    assert (reply.status_code, reply.headers["location"]) == (303, "/sessions/x")


def test_daily_limit_counts_each_new_idea_once(web, monkeypatch):
    monkeypatch.setenv("WORKBOT_DAILY_IDEAS", "1")
    client = web.use(
        ScriptedModel([_person("nina", "direct_contact", ["jira:MKT-482"], "direct")])
    )

    def submit(key, idea="Help plan marketing campaigns"):
        return client.post(
            "/sessions",
            data={"idea": idea, "idempotency_key": key},
            follow_redirects=False,
        )

    # A rejected form counts nothing.
    assert submit("empty", idea=" ").status_code == 400
    first = submit("first")
    assert first.status_code == 303
    app.state.last_run.join(10)
    # Submitting the same form again starts nothing and counts nothing.
    assert submit("first").headers["location"] == first.headers["location"]
    second = submit("second")
    assert second.status_code == 429
    assert "limit of new ideas for this demo has been reached" in second.text
    assert client.get(first.headers["location"]).status_code == 200
    assert _sessions(web.path) == 1

    class Tomorrow(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(days=1)

    monkeypatch.setattr(main_module, "datetime", Tomorrow)
    assert submit("next-day").status_code == 303
    app.state.last_run.join(10)


class StubTranscriber:
    def __init__(self, text="Let customers pause their plan.", error=None):
        self.calls = []
        self.reply = text
        self.error = error

    async def text(self, pcm):
        self.calls.append(pcm)
        if self.error:
            raise TranscriptionError(self.error)
        return self.reply


def _pcm(seconds=1.0):
    return b"\x00\x01" * int(16000 * seconds)


def test_speak_fills_the_box_only_and_starts_nothing(web, monkeypatch):
    stub = StubTranscriber()
    monkeypatch.setattr(app.state, "transcriber", stub, raising=False)
    client = web.use(ScriptedModel([]))
    home = client.get("/").text
    assert 'data-voice-for="idea"' in home and "/transcribe" in home
    reply = client.post(
        "/transcribe",
        content=_pcm(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert reply.status_code == 200
    assert reply.json() == {"text": "Let customers pause their plan."}
    assert stub.calls == [_pcm()]
    assert _sessions(web.path) == 0


def test_speak_refuses_bad_or_foreign_requests(web, monkeypatch):
    stub = StubTranscriber()
    monkeypatch.setattr(app.state, "transcriber", stub, raising=False)
    client = web.use(ScriptedModel([]))
    octet = {"Content-Type": "application/octet-stream"}
    assert client.post("/transcribe", content=_pcm(), headers={}).status_code == 415
    too_long = client.post("/transcribe", content=_pcm(20.5), headers=octet)
    assert too_long.status_code == 413
    assert "under 20 seconds" in too_long.json()["error"]
    foreign = client.post(
        "/transcribe",
        content=_pcm(),
        headers={**octet, "Origin": "https://evil.example"},
    )
    assert foreign.status_code == 403
    assert stub.calls == []
    monkeypatch.setattr(main_module, "transcribe_limiter", DemoRateLimiter(1, 600))
    assert client.post("/transcribe", content=_pcm(), headers=octet).status_code == 200
    assert client.post("/transcribe", content=_pcm(), headers=octet).status_code == 429


def test_speak_failure_is_a_plain_message(web, monkeypatch):
    stub = StubTranscriber(error="No speech was recognized. Try again or type it.")
    monkeypatch.setattr(app.state, "transcriber", stub, raising=False)
    client = web.use(ScriptedModel([]))
    reply = client.post(
        "/transcribe",
        content=_pcm(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert reply.status_code == 503
    assert reply.json() == {"error": "No speech was recognized. Try again or type it."}


def test_speak_is_behind_the_access_code(web, monkeypatch):
    monkeypatch.setenv("WORKBOT_ACCESS_CODE", "judge-2026")
    stub = StubTranscriber()
    monkeypatch.setattr(app.state, "transcriber", stub, raising=False)
    client = web.use(ScriptedModel([]))
    reply = client.post(
        "/transcribe",
        content=_pcm(),
        headers={"Content-Type": "application/octet-stream"},
        follow_redirects=False,
    )
    assert reply.status_code == 303
    assert stub.calls == []


def test_question_form_offers_speak_for_the_answer(web):
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")],
        question="Which campaigns are in scope?",
    )
    client, url = _submit(web, model)
    page = client.get(url).text
    assert 'data-voice-for="answer"' in page
    # Alexa asks in the same panel as the plan, with the words Listen reads.
    panel = page.split('<section class="screen"', 1)[1].split("</section>", 1)[0]
    assert "Alexa asks" in panel
    assert "One clarification before searching." in panel
    assert "Which campaigns are in scope?" in panel
    client.post(url + "/answer", data={"answer": "Retail"}, follow_redirects=False)
    app.state.last_run.join(10)
    assert "Alexa asked</span><p>Which campaigns are in scope?" in client.get(url).text


def _swappable(page):
    # The script swaps #page in place, so it must sit outside it, once, after it.
    assert page.count('id="page"') == 1 and page.count("<script") == 1
    assert page.index("</main>") < page.index("<script")


def test_pages_are_swapped_in_place_by_the_one_script(web):
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")],
        question="Which campaigns are in scope?",
    )
    client = web.use(model)
    home = client.get("/").text
    _swappable(home)
    assert (
        '<form class="panel stack tight" action="/sessions" method="post" data-swap>'
        in home
    )
    # Read aloud is the visitor's own choice, shown by script and never sent.
    toggle = home.split('<label class="toggle"', 1)[1].split("</label>", 1)[0]
    assert toggle.startswith(" hidden>") and 'id="read-aloud" checked' in toggle
    assert "name=" not in toggle
    # The script sends forms as a browser would, with a charset in the type.
    reply = client.post(
        "/sessions",
        content="idea=Help+plan+marketing+campaigns&idempotency_key=swap",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "http://testserver",
        },
        follow_redirects=False,
    )
    assert reply.status_code == 303
    url = reply.headers["location"]
    app.state.last_run.join(10)
    question = client.get(url).text
    _swappable(question)
    # Continue, and Continue without answering.
    assert question.split("<script")[0].count("data-swap") == 2
    client.post(url + "/answer", data={"answer": "Retail"}, follow_redirects=False)
    app.state.last_run.join(10)
    _swappable(client.get(url).text)


def test_plan_names_the_areas_it_leaves_to_the_full_list(web, monkeypatch):
    build_plan = main_module.build_plan

    def with_more(card):
        plan = build_plan(card)
        plan["more"] = [
            {"area": "Legal and Compliance", "names": ["Anders Holm", "Zoe Park"]},
            {"area": "Data", "names": []},
        ]
        return plan

    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    monkeypatch.setattr(main_module, "build_plan", with_more)
    plan, _ = client.get(url).text.split('<details class="all">')
    assert (
        "Also in the full list: Legal and Compliance (Anders Holm, Zoe Park); Data."
        in plan
    )


def _ask(client, url, question, *prior, origin="http://testserver"):
    data = {f"prior-{index}": q for index, q in enumerate(prior)}
    return client.post(
        url + "/ask",
        data={**data, "q": question},
        headers={"Origin": origin},
        follow_redirects=False,
    )


def test_follow_ups_are_answered_in_the_page_without_a_model(web):
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    calls = model.calls
    page = client.get(url).text.split("<script")[0]
    panel = page.split('<section class="screen"', 1)[1].split("</section>", 1)[0]
    assert "Ask me why anyone is listed, or what to ask them." in panel
    assert f'action="{url}/ask" data-swap' in page
    assert '<input type="hidden" name="q" value="Why Nina?">' in page
    assert 'data-voice-for="q"' in page and "data-speech-auto" not in page
    first = _ask(client, url, "Why Nina?")
    # The answer is the page itself, at the same address, not a redirect.
    assert first.status_code == 200
    _swappable(first.text)
    plan, _ = first.text.split('<details class="all">')
    assert "Maya asked</span><p>Why Nina?</p>" in plan
    assert "Nina Ellis is listed under Growth Marketing for related work." in plan
    assert f'href="{url}/sources/jira%3AMKT-482">Source</a></p>' in plan
    assert plan.count("data-speech-auto") == 1
    # The next question carries this one, and its chip is gone.
    assert '<input type="hidden" name="prior-0" value="Why Nina?">' in plan
    assert '<input type="hidden" name="q" value="Why Nina?">' not in plan
    second = _ask(client, url, "Prep me for Nina", "Why Nina?").text.split("<script")[0]
    assert second.count("Maya asked") == 2
    assert second.index("Why Nina?</p>") < second.index("Prep me for Nina</p>")
    # Only the newest answer is read aloud on its own.
    assert second.count("data-speech-auto") == 1
    assert second.index("Prep me for Nina</p>") < second.index("data-speech-auto")
    assert "With Nina Ellis, find out: Who reviews retail campaign launches" in second
    assert model.calls == calls


def test_a_follow_up_conversation_keeps_only_the_newest_questions(web):
    client, url = _submit(
        web,
        ScriptedModel([_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]),
    )
    prior = [f"Question {n}?" for n in range(6)]
    page = _ask(client, url, "Who else?", *prior).text
    # prior-5 is not read: five earlier questions and the new one are shown.
    assert page.count("Maya asked") == 6
    assert "Question 5?" not in page and "Question 0?" in page
    assert 'name="prior-4" value="Who else?"' in page
    assert 'name="prior-5"' not in page and 'Question 0?">' not in page


def test_follow_ups_refuse_bad_stale_or_foreign_requests(web):
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    assert _ask(client, url, "  ").status_code == 400
    assert _ask(client, url, "x" * 201).status_code == 400
    assert _ask(client, url, "Why Nina?", "y" * 201).status_code == 400
    assert _ask(client, url, "Why Nina?", origin="https://elsewhere").status_code == 403
    assert _ask(client, "/sessions/nope", "Why Nina?").status_code == 404
    db = connect(web.path)
    db.execute(
        """INSERT INTO sessions (id, actor, workspace, idem_key, sentence, answers_json, state, question)
        VALUES ('asking', 'maya', 'demo', 'asking', 'An idea', '[]', 'question', 'Which?')"""
    )
    db.execute("UPDATE people SET active=0 WHERE id='nina'")
    db.commit()
    db.close()
    waiting = _ask(client, "/sessions/asking", "Why Nina?")
    assert waiting.status_code == 409
    assert "There is no plan to ask about." in waiting.text
    db = connect(web.path)
    db.execute(
        """INSERT INTO sessions (id, actor, workspace, idem_key, sentence, answers_json, state)
        VALUES ('refused', 'maya', 'demo', 'refused', 'An idea', '[]', 'refusal')"""
    )
    db.commit()
    db.close()
    assert _ask(client, "/sessions/refused", "Why Nina?").status_code == 409
    stale = _ask(client, url, "Why Nina?")
    assert stale.status_code == 410
    assert "This plan is out of date" in stale.text
    assert "Nina" not in stale.text


def test_follow_up_speech_reads_only_the_answer_built_from_the_plan(web, monkeypatch):
    speech = StubSpeech()
    monkeypatch.setattr(app.state, "speech", speech, raising=False)
    model = ScriptedModel(
        [_person("nina", "direct_contact", ["jira:MKT-482"], "direct")]
    )
    client, url = _submit(web, model)
    page = _ask(client, url, "Why Nina?").text
    assert f'data-speech="{url}/reply.mp3?q=Why%20Nina%3F" data-speech-auto' in page
    reply = client.get(url + "/reply.mp3?q=Why%20Nina%3F")
    assert reply.status_code == 200 and reply.content == b"ID3-synthetic-audio"
    [text] = speech.texts
    assert text.startswith("Nina Ellis is listed under Growth Marketing")
    answer = page.split("data-speech-auto", 1)[1].split('<p class="answer">', 1)[1]
    assert answer.startswith(text)
    # A question naming someone known only through restricted sources gets the
    # same answer as one naming nobody, and the question itself is never read.
    client.get(url + "/reply.mp3?q=Why%20Eve%20Restricted%3F")
    client.get(url + "/reply.mp3?q=Why%20Zed%20Nobody%3F")
    assert speech.texts[1] == speech.texts[2]
    assert "Eve" not in speech.texts[1] and "Zed" not in speech.texts[1]
    assert client.get(url + "/reply.mp3").status_code == 404
    assert client.get(url + "/reply.mp3?q=" + "x" * 201).status_code == 404
    assert client.get("/sessions/nope/reply.mp3?q=Why").status_code == 404
    assert len(speech.texts) == 3
    # Reading answers aloud is limited per address, like Speak.
    monkeypatch.setattr(main_module, "reply_limiter", DemoRateLimiter(limit=0))
    limited = client.get(url + "/reply.mp3?q=Why%20Nina%3F")
    assert limited.status_code == 429 and len(speech.texts) == 3
    # A stale plan has nothing to read.
    db = connect(web.path)
    db.execute("UPDATE people SET active=0 WHERE id='nina'")
    db.commit()
    db.close()
    assert client.get(url + "/reply.mp3?q=Why%20Nina%3F").status_code == 404
