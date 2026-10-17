"""English-language, server-rendered simulated Alexa+ experience."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import defaultdict, deque
from functools import lru_cache
from http import HTTPStatus
from threading import Lock, Thread
from urllib.parse import parse_qs

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from workbot.llm import OpenRouter
from workbot.plan import build_plan
from workbot.search import Searcher, SetupError
from workbot.service import (
    Conflict,
    end_progress,
    fail_if_abandoned,
    open_session,
    progress,
    record_answer,
    run_safely,
)
from workbot.storage import (
    connect,
    directory_claims,
    initialize,
    load_session,
    recent_sessions,
    source,
    valid_card,
)

load_dotenv()
app = FastAPI(title="Workbot — simulated Alexa+ experience")
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


_ERROR_TITLES = {
    400: "Request not accepted",
    403: "Request refused",
    404: "Not found",
    405: "Request not accepted",
    409: "Request not accepted",
    410: "No longer available",
    413: "That form is too large",
    415: "Request not accepted",
    429: "Please wait a moment",
}


@app.exception_handler(StarletteHTTPException)
async def error_page(request: Request, exc: StarletteHTTPException):
    """Show an error as a page; a framework default such as "Not Found" gets a sentence."""
    try:
        default = exc.detail == HTTPStatus(exc.status_code).phrase
    except ValueError:
        default = not exc.detail
    if not default:
        message = exc.detail
    elif exc.status_code == 404:
        message = "There is nothing to show at this address."
    else:
        message = "This request could not be completed. Go back to the Workbot page and try again."
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "title": _ERROR_TITLES.get(exc.status_code, "Something went wrong"),
            "message": message,
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


class DemoRateLimiter:
    """A local-demo spending guard, not authentication or distributed rate limiting."""

    def __init__(self, limit: int = 30, window_seconds: int = 600):
        self.limit = limit
        self.window_seconds = window_seconds
        self.hits = defaultdict(deque)
        self.lock = Lock()

    def allow(self, client: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self.lock:
            hits = self.hits[client]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


demo_limiter = DemoRateLimiter()


def _guard_model_request(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Requests from other sites are not accepted.")
    if not demo_limiter.allow(request.client.host if request.client else "unknown"):
        raise HTTPException(
            429,
            "The demo request limit was reached. Wait a few minutes, then try again.",
        )


def _db():
    db = connect(os.getenv("WORKBOT_DB_PATH", "data/workbot.sqlite3"))
    initialize(db)
    return db


def _model():
    return getattr(app.state, "model", None) or OpenRouter()


@lru_cache(maxsize=1)
def _default_searcher():
    return Searcher(os.getenv("QDRANT_URL", "http://localhost:6333"))


def _searcher():
    return getattr(app.state, "searcher", None) or _default_searcher()


async def _form(request: Request) -> dict[str, str]:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].lower()
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415, "Send the idea from the Workbot page.")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 4096:
            raise HTTPException(413, "The form is too large. Shorten it and try again.")
        chunks.append(chunk)
    try:
        fields = parse_qs(
            b"".join(chunks).decode("utf-8"), keep_blank_values=True, errors="strict"
        )
    except UnicodeError:
        raise HTTPException(
            400, "The form could not be read. Try again from the Workbot page."
        ) from None
    return {key: values[0] for key, values in fields.items()}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    db = _db()
    try:
        recent = recent_sessions(db)
    finally:
        db.close()
    return templates.TemplateResponse(
        request, "home.html", {"key": str(uuid.uuid4()), "recent": recent}
    )


def _run(sid: str, model, searcher) -> None:
    try:
        db = _db()
        try:
            run_safely(db, sid, model, searcher)
        finally:
            db.close()
    finally:
        # Whatever went wrong, the session page must stop reporting a live run.
        end_progress(sid)


def _start(sid: str) -> None:
    """Run the workflow off the request so the page can show progress meanwhile."""
    thread = Thread(target=_run, args=(sid, _model(), _searcher()), daemon=True)
    app.state.last_run = thread
    thread.start()


def _setup_page(request: Request, exc: SetupError):
    return templates.TemplateResponse(
        request,
        "setup.html",
        {"message": str(exc), "command": exc.command},
        status_code=503,
    )


def _create(key: str, idea: str) -> str:
    db = _db()
    try:
        # Checked before anything is stored or sent to the model.
        _searcher().check(db)
        sid, created = open_session(db, key, idea)
    finally:
        db.close()
    if created:
        _start(sid)
    return sid


@app.post("/sessions")
async def post_session(request: Request):
    form = await _form(request)
    _guard_model_request(request)
    try:
        sid = await run_in_threadpool(
            _create, form.get("idempotency_key", ""), form.get("idea", "")
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from None
    except SetupError as exc:
        return _setup_page(request, exc)
    return RedirectResponse(f"/sessions/{sid}", status_code=303)


def _get_session(sid: str):
    db = _db()
    try:
        session = load_session(db, sid)
        if session and session["state"] == "processing" and fail_if_abandoned(db, sid):
            session = load_session(db, sid)
        card = (
            valid_card(db, session) if session and session["state"] == "card" else None
        )
        return session, card
    finally:
        db.close()


def _answers(session: dict) -> list[dict]:
    try:
        answers = json.loads(session["answers_json"])
        return [
            {"question": str(a["question"]), "answer": a["answer"]} for a in answers
        ]
    except (ValueError, TypeError, KeyError):
        return []


@app.get("/sessions/{sid}", response_class=HTMLResponse)
def show_session(request: Request, sid: str):
    session, card = _get_session(sid)
    if not session:
        raise HTTPException(404, "There is no idea at this address.")
    if session["state"] == "card" and card is None:
        return templates.TemplateResponse(
            request,
            "session.html",
            {
                "session": session,
                "stale": True,
                "card": None,
                "answers": _answers(session),
            },
            status_code=410,
        )
    return templates.TemplateResponse(
        request,
        "session.html",
        {
            "session": session,
            "card": card,
            "stale": False,
            "answers": _answers(session),
            "plan": build_plan(card) if card else None,
            "progress": progress(sid) if session["state"] == "processing" else None,
        },
    )


def _answer(sid: str, answer: str | None):
    db = _db()
    try:
        # Only a pending question can start a run, so only then must search be ready.
        session = load_session(db, sid)
        if session and session["state"] == "question":
            _searcher().check(db)
        recorded = record_answer(db, sid, answer)
    except Conflict:
        # A repeated submit: nothing is pending, so show the session as it is now.
        if not load_session(db, sid):
            raise HTTPException(404, "There is no idea at this address.") from None
        recorded = False
    finally:
        db.close()
    if recorded:
        _start(sid)


@app.post("/sessions/{sid}/answer")
async def answer(request: Request, sid: str):
    form = await _form(request)
    _guard_model_request(request)
    skipped = form.get("skip") == "1"
    try:
        await run_in_threadpool(
            _answer, sid, None if skipped else form.get("answer", "")
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except SetupError as exc:
        return _setup_page(request, exc)
    return RedirectResponse(f"/sessions/{sid}", status_code=303)


@app.get("/sessions/{sid}/sources/{source_id:path}", response_class=HTMLResponse)
def show_source(request: Request, sid: str, source_id: str):
    db = _db()
    try:
        session = load_session(db, sid)
        if not session or session["state"] != "card":
            raise HTTPException(404, "This source is not available.")
        card = valid_card(db, session)
        if card is None:
            raise HTTPException(
                410, "This plan is out of date, so its sources are no longer shown."
            )
        cited = {
            source_id
            for area in card["areas"]
            for person in area["people"]
            for source_id in person["evidence_ids"]
        }
        if source_id not in cited:
            raise HTTPException(404, "This source is not available.")
        item = source(db, source_id)
        if not item:
            raise HTTPException(404, "This source is not available.")
        # A work record shows its text; a directory source shows what it records.
        return templates.TemplateResponse(
            request,
            "source.html",
            {
                "item": item,
                "claims": directory_claims(db, source_id),
                "session_id": sid,
            },
        )
    finally:
        db.close()
