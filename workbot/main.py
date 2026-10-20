"""English-language, server-rendered simulated Alexa+ experience."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import lru_cache
from http import HTTPStatus
from threading import Lock, Thread
from urllib.parse import parse_qs, quote, urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from workbot.followup import MAX_QUESTION, MAX_TURNS, carried, chips, reply
from workbot.llm import default_model
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
from workbot.speech import Speech, SpeechError
from workbot.storage import (
    connect,
    directory_claims,
    has_session_key,
    initialize,
    load_session,
    recent_sessions,
    return_daily_idea,
    source,
    take_daily_idea,
    valid_card,
)
from workbot.transcribe import MAX_BYTES, Transcriber, TranscriptionError

load_dotenv()
app = FastAPI(title="WorkBot — simulated Alexa+ experience")
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
    503: "Not available right now",
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
        message = "This request could not be completed. Go back to the WorkBot page and try again."
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
# Voice inputs per client: each one is a paid Nova 2 Sonic request.
transcribe_limiter = DemoRateLimiter(limit=20, window_seconds=600)
# Follow-up answers read aloud per client: each new text is a Polly request.
reply_limiter = DemoRateLimiter(limit=60, window_seconds=600)
# Wrong access codes per client: enough for typos, too few to guess a code.
access_limiter = DemoRateLimiter(limit=10, window_seconds=600)
ACCESS_COOKIE = "workbot_access"


def _access_code() -> str:
    return os.getenv("WORKBOT_ACCESS_CODE", "").strip()


def _daily_limit() -> int:
    """0 when unset; a value that is not a whole number stops new ideas."""
    value = (os.getenv("WORKBOT_DAILY_IDEAS") or "").strip()
    if not value:
        return 0
    if not value.isdigit():
        raise HTTPException(
            503,
            "This demo's daily idea limit is not set up correctly, so no new idea "
            "can be accepted. Earlier plans can still be opened.",
        )
    return int(value)


def _access_token(code: str) -> str:
    # The cookie holds a digest, not the code; a new code invalidates old cookies.
    return hmac.new(code.encode(), b"workbot-access", hashlib.sha256).hexdigest()


def _matches(given: str, expected: str) -> bool:
    # Bytes, because compare_digest refuses non-ASCII text.
    return hmac.compare_digest(given.encode(), expected.encode())


@app.middleware("http")
async def access_gate(request: Request, call_next):
    """With WORKBOT_ACCESS_CODE set, every page waits for the code; unset, none does."""
    code = _access_code()
    if not code or request.url.path == "/access":
        return await call_next(request)
    if _matches(request.cookies.get(ACCESS_COOKIE, ""), _access_token(code)):
        return await call_next(request)
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse("/access?next=" + quote(target, safe=""), status_code=303)


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Requests from other sites are not accepted.")


def _guard_model_request(request: Request) -> None:
    _same_origin(request)
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
    return getattr(app.state, "model", None) or default_model()


@lru_cache(maxsize=1)
def _default_searcher():
    return Searcher(os.getenv("QDRANT_URL", "http://localhost:6333"))


def _searcher():
    return getattr(app.state, "searcher", None) or _default_searcher()


def _transcriber():
    return getattr(app.state, "transcriber", None) or Transcriber()


@lru_cache(maxsize=1)
def _default_speech():
    return Speech()


def _speech():
    return getattr(app.state, "speech", None) or _default_speech()


async def _form(request: Request) -> dict[str, str]:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].lower()
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415, "Send the idea from the WorkBot page.")
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
            400, "The form could not be read. Try again from the WorkBot page."
        ) from None
    return {key: values[0] for key, values in fields.items()}


def _next(target: str) -> str:
    # Only a path on this site: browsers read "//host" and "/\\host" as another host.
    try:
        parts = urlsplit(target)
    except ValueError:
        return "/"
    safe = target.startswith("/") and not (parts.scheme or parts.netloc)
    return target if safe and "\\" not in target and target.isprintable() else "/"


@app.get("/access", response_class=HTMLResponse)
def access_page(request: Request, next: str = "/"):
    if not _access_code():
        return RedirectResponse(_next(next), status_code=303)
    return templates.TemplateResponse(
        request, "access.html", {"next": _next(next), "wrong": False}
    )


@app.post("/access", response_class=HTMLResponse)
async def access_submit(request: Request):
    form = await _form(request)
    _same_origin(request)
    code = _access_code()
    target = _next(form.get("next", "/"))
    if not code:
        return RedirectResponse(target, status_code=303)
    # Every attempt counts, so a right guess after many wrong ones is refused too.
    if not access_limiter.allow(request.client.host if request.client else "unknown"):
        raise HTTPException(
            429, "Too many attempts. Wait a few minutes, then try again."
        )
    if _matches(form.get("code", "").strip(), code):
        response = RedirectResponse(target, status_code=303)
        response.set_cookie(
            ACCESS_COOKIE,
            _access_token(code),
            max_age=30 * 24 * 3600,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return response
    return templates.TemplateResponse(
        request, "access.html", {"next": target, "wrong": True}, status_code=401
    )


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
        limit = _daily_limit()
        day = datetime.now(timezone.utc).date().isoformat()
        # A repeated submit of the same form starts nothing and counts nothing.
        counted = bool(limit) and not has_session_key(db, key)
        if counted and not take_daily_idea(db, day, limit):
            raise HTTPException(
                429,
                "Today's limit of new ideas for this demo has been reached. Earlier "
                "plans can still be opened; new ideas are accepted again after "
                "midnight UTC.",
            )
        try:
            sid, created = open_session(db, key, idea)
        except BaseException:
            if counted:
                return_daily_idea(db, day)
            raise
        if counted and not created:
            return_daily_idea(db, day)  # The same form, submitted twice at once.
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


def _session_page(request: Request, session: dict, card, questions=()):
    """The session page; `questions` are the follow-ups asked about its plan."""
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
    plan = build_plan(card) if card else None
    return templates.TemplateResponse(
        request,
        "session.html",
        {
            "session": session,
            "card": card,
            "stale": False,
            "answers": _answers(session),
            "plan": plan,
            "turns": [{"question": q, **reply(q, plan, card)} for q in questions],
            # Carried by the next follow-up's form, so the conversation is kept
            # in the page and never stored.
            "prior": carried(list(questions)),
            "chips": chips(plan, list(questions)) if plan else [],
            "progress": progress(session["id"])
            if session["state"] == "processing"
            else None,
        },
    )


@app.get("/sessions/{sid}", response_class=HTMLResponse)
def show_session(request: Request, sid: str):
    session, card = _get_session(sid)
    if not session:
        raise HTTPException(404, "There is no idea at this address.")
    return _session_page(request, session, card)


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


def _question(text: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(400, "Type or say a question about the plan first.")
    if len(text) > MAX_QUESTION:
        raise HTTPException(400, "Keep the question under 200 characters.")
    return text


@app.post("/sessions/{sid}/ask", response_class=HTMLResponse)
async def ask(request: Request, sid: str):
    """A follow-up question about the plan, answered from the plan with no model.

    The earlier questions come back with the form, so nothing is stored and one
    visitor's questions never appear for another.
    """
    form = await _form(request)
    _same_origin(request)
    prior = [form.get(f"prior-{index}", "") for index in range(MAX_TURNS - 1)]
    questions = [_question(q) for q in prior if q.strip()]
    questions.append(_question(form.get("q", "")))
    session, card = await run_in_threadpool(_get_session, sid)
    if not session:
        raise HTTPException(404, "There is no idea at this address.")
    if session["state"] != "card":
        raise HTTPException(409, "There is no plan to ask about.")
    if card is None:
        raise HTTPException(
            410,
            "This plan is out of date, so Alexa cannot answer questions about it."
            " Ask about the idea again to get a current plan.",
        )
    return _session_page(request, session, card, questions[-MAX_TURNS:])


@app.post("/transcribe")
async def transcribe(request: Request):
    """Speech for the idea, answer, or follow-up box: 16 kHz 16-bit mono PCM in, JSON text out.

    The text only fills the box; the person still reads it and sends the form.
    """
    _same_origin(request)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/octet-stream":
        return JSONResponse({"error": "Record from the WorkBot page."}, 415)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BYTES:
            return JSONResponse({"error": "Keep the recording under 20 seconds."}, 413)
        chunks.append(chunk)
    if not transcribe_limiter.allow(
        request.client.host if request.client else "unknown"
    ):
        return JSONResponse(
            {"error": "Voice input was used often. Wait a few minutes, or type it."},
            429,
        )
    try:
        text = await _transcriber().text(b"".join(chunks))
    except TranscriptionError as exc:
        return JSONResponse({"error": str(exc)}, 503)
    return JSONResponse({"text": text})


@app.get("/sessions/{sid}/speech.mp3")
def speech(sid: str):
    """The page's spoken text, read by Polly: the plan summary or the question."""
    session, card = _get_session(sid)
    if session and card:
        text = build_plan(card)["spoken"]
    elif session and session["state"] == "question" and session["question"]:
        text = f"One clarification before searching. {session['question']}"
    else:
        raise HTTPException(404, "There is nothing to read aloud at this address.")
    return _audio(text)


@app.get("/sessions/{sid}/reply.mp3")
def reply_speech(request: Request, sid: str, q: str = ""):
    """A follow-up answer, read by Polly. Only the answer built from the plan is
    sent; the question is used to choose it and is never read itself."""
    session, card = _get_session(sid)
    question = q.strip()
    if not (session and card) or not 0 < len(question) <= MAX_QUESTION:
        raise HTTPException(404, "There is nothing to read aloud at this address.")
    if not reply_limiter.allow(request.client.host if request.client else "unknown"):
        raise HTTPException(
            429, "Answers were read aloud often. Wait a few minutes, then try again."
        )
    return _audio(reply(question, build_plan(card), card)["text"])


def _audio(text: str) -> Response:
    try:
        audio = _speech().audio(text)
    except SpeechError as exc:
        raise HTTPException(503, str(exc)) from None
    return Response(
        audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"}
    )


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
        # A person's cited sources, and the directory source of an ended-duty note.
        cited = {
            source_id
            for area in card["areas"]
            for person in area["people"]
            for source_id in [*person["evidence_ids"], *person.get("context_ids", [])]
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
