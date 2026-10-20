"""Session orchestration and deterministic evidence/role audit."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from threading import Lock

from workbot.llm import ModelError
from workbot.models import AreaEvaluation, Impact, Priority
from workbot.plan import ROLE_ORDER
from workbot.search import candidate_pool, directory_hints, keywords
from workbot.storage import (
    current,
    current_and_visible,
    load_session,
    org_inventory,
    source,
    store_card,
    today,
    visible_directory_source,
    visible_record,
)

log = logging.getLogger(__name__)
MAX_PARALLEL_AREA_CALLS = 6  # Worker threads; an idea has at most six areas.

# What a running request is doing, for the waiting page only: a stage and area
# labels with a done flag. Never people, sources, counts, or model diagnostics.
# In-memory on purpose: a restart loses the run itself, so it loses this too.
_progress: dict[str, dict] = {}
_progress_lock = Lock()


def progress(sid: str) -> dict | None:
    with _progress_lock:
        entry = _progress.get(sid)
        return (
            {"stage": entry["stage"], "areas": [dict(a) for a in entry["areas"]]}
            if entry
            else None
        )


def _report(sid: str, stage: str | None = None, areas=None, done=None) -> None:
    with _progress_lock:
        entry = _progress.setdefault(sid, {"stage": "impact", "areas": []})
        if stage:
            entry["stage"] = stage
        if areas is not None:
            entry["areas"] = areas
        for area in entry["areas"]:
            if area["id"] == done:
                area["done"] = True


def end_progress(sid: str) -> None:
    with _progress_lock:
        _progress.pop(sid, None)


def fail_if_abandoned(db, sid: str) -> bool:
    """Close a `processing` session that no run is working on any more.

    Every live run has a progress entry from before its state becomes
    `processing` until after it leaves that state, so a session without one was
    lost to a restart or a crashed worker and would otherwise wait forever.
    """
    if progress(sid) is not None:
        return False
    changed = db.execute(
        """UPDATE sessions SET state='refusal', question=NULL, card_json=NULL,
        snapshot_json=NULL WHERE id=? AND state='processing'""",
        (sid,),
    )
    db.commit()
    return changed.rowcount == 1


class Conflict(Exception):
    pass


def _refuse(db, sid: str) -> None:
    db.execute(
        "UPDATE sessions SET state='refusal', question=NULL, card_json=NULL, snapshot_json=NULL WHERE id=?",
        (sid,),
    )
    db.commit()


def open_session(db, idem_key: str, sentence: str) -> tuple[str, bool]:
    """Store a new request; the bool is False when this key already has one."""
    if (
        not sentence.strip()
        or len(sentence) > 600
        or not idem_key.strip()
        or len(idem_key) > 120
    ):
        raise ValueError("A project idea and an idempotency key are required")
    sentence = sentence.strip()
    sid = str(uuid.uuid4())
    try:
        with db:
            db.execute(
                """INSERT INTO sessions
                (id, actor, workspace, idem_key, sentence, answers_json, state)
                VALUES (?, 'maya', 'demo', ?, ?, '[]', 'processing')""",
                (sid, idem_key, sentence),
            )
            # Before the commit: a visible `processing` row always has progress.
            _report(sid, "impact")
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT * FROM sessions WHERE actor='maya' AND workspace='demo' AND idem_key=?",
            (idem_key,),
        ).fetchone()
        if row and row["sentence"] == sentence:
            return row["id"], False
        raise Conflict("This request key belongs to a different idea") from None
    return sid, True


def record_answer(db, sid: str, answer: str | None) -> bool:
    """Store a clarification answer; False when the saved session is unusable."""
    session = load_session(db, sid)
    if not session or session["state"] != "question":
        raise Conflict("There is no pending clarification")
    if answer is not None and (not answer.strip() or len(answer) > 500):
        raise ValueError("Keep the answer under 500 characters")
    try:
        answers = json.loads(session["answers_json"])
        if not isinstance(answers, list):
            raise TypeError("Invalid saved answers")
    except (ValueError, TypeError):
        _refuse(db, sid)
        return False
    answers.append(
        {"question": session["question"], "answer": answer.strip() if answer else None}
    )
    with db:
        changed = db.execute(
            """UPDATE sessions SET answers_json=?, state='processing', question=NULL,
            card_json=NULL, snapshot_json=NULL WHERE id=? AND state='question'""",
            (json.dumps(answers), sid),
        )
        if changed.rowcount != 1:
            raise Conflict("This clarification has already been answered")
        # Before the commit: a visible `processing` row always has progress.
        _report(sid, "impact")
    return True


def run_safely(db, sid: str, model, searcher) -> None:
    try:
        run(db, sid, model, searcher)
    except Exception as exc:  # noqa: BLE001 — no raw model or document text in logs.
        log.warning("workflow_failed type=%s", type(exc).__name__)
        _refuse(db, sid)
    finally:
        end_progress(sid)


def run(db, sid: str, model, searcher) -> None:
    session = load_session(db, sid)
    if not session or session["state"] != "processing":
        return
    _report(sid, "impact")
    answers = json.loads(session["answers_json"])
    impact = _ask_impact(db, sid, session, answers, model)
    if impact is None:
        return
    card = {"areas": [], "shared_question": None, "first_conversations": []}
    _review_areas(db, sid, session, answers, impact, card, model, searcher)
    _report(sid, "priority")
    _apply_priority(db, session, answers, card, model)
    try:
        store_card(db, sid, card)
    except ValueError:
        _refuse(db, sid)


def _ask_impact(db, sid: str, session: dict, answers: list, model) -> Impact | None:
    """First model task. None when the request was refused or a question was asked."""
    inventory = org_inventory(db)
    if not inventory:
        _refuse(db, sid)
        return None
    # Skipping a clarification ends the question budget; say so to the model.
    skipped = any(a["answer"] is None for a in answers)
    payload = {
        "idea": session["sentence"],
        "answers": answers,
        "org_units": inventory,
        "directory_hints": directory_hints(
            db,
            " ".join(
                [session["sentence"], *(a["answer"] for a in answers if a["answer"])]
            ),
        ),
        "remaining_questions": 0 if skipped else max(0, 2 - session["questions_asked"]),
    }
    if len(json.dumps(payload)) > 12000:
        _refuse(db, sid)
        return None
    try:
        impact = model.complete("impact", payload)
        if not isinstance(impact, Impact):
            raise ModelError("Invalid impact contract")
        if impact.question:
            if (
                not _safe_question(impact.question)
                or payload["remaining_questions"] == 0
            ):
                raise ModelError("Question budget exhausted")
            db.execute(
                "UPDATE sessions SET state='question', question=?, questions_asked=questions_asked+1 WHERE id=?",
                (impact.question, sid),
            )
            db.commit()
            return None
        org_ids = {item["id"] for item in inventory}
        if any(
            a.mapping == "mapped" and a.org_unit_id not in org_ids for a in impact.areas
        ):
            raise ModelError("Unknown org unit")
    except (ModelError, ValueError):
        _refuse(db, sid)
        return None
    return impact


def _review_areas(
    db,
    sid: str,
    session: dict,
    answers: list,
    impact: Impact,
    card: dict,
    model,
    searcher,
) -> None:
    """Second model task, once per mapped area and all at once; each area fails alone."""
    pending: dict[Future, tuple[dict, dict, list[str]]] = {}
    _report(
        sid,
        "areas",
        areas=[
            {"id": a.id, "label": a.label, "done": a.mapping == "mapping_unresolved"}
            for a in impact.areas
        ],
    )
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_AREA_CALLS) as executor:
        for area in impact.areas:
            item = {
                "id": area.id,
                "label": area.label,
                "rationale": area.rationale,
                "consultation_need": area.consultation_need,
                "mapping": area.mapping,
                "org_unit_id": area.org_unit_id,
                "mapping_reason": area.mapping_reason,
                "status": "mapping_unresolved"
                if area.mapping == "mapping_unresolved"
                else "not_found",
                "people": [],
                "direct_review_incomplete": False,
                "no_visible_work_trace": False,
            }
            card["areas"].append(item)
            if area.mapping == "mapping_unresolved":
                continue
            submitted = False
            try:
                # Search and all permissioned directory reads stay on this thread.
                records = searcher.records(
                    db, [intent.model_dump() for intent in area.search_intents]
                )
                pool = candidate_pool(db, area.model_dump(), records)
                item["no_visible_work_trace"] = pool["no_visible_work_trace"]
                if not pool["people"]:
                    continue
                prompt = {
                    "idea": session["sentence"],
                    "answers": answers,
                    "area": area.model_dump(),
                    "candidates": pool["people"],
                }
                if len(json.dumps(prompt)) > 18000:
                    item["status"] = "review_incomplete"
                    continue
                pending[executor.submit(model.complete, "area", prompt)] = (
                    item,
                    pool,
                    [intent.keyword for intent in area.search_intents],
                )
                submitted = True
            except Exception as exc:  # noqa: BLE001 — search/preparation must fail closed.
                log.warning("area_review_incomplete type=%s", type(exc).__name__)
                item["status"] = "review_incomplete"
                item["people"] = []
            finally:
                if not submitted:
                    _report(sid, done=area.id)
        # Audits run here, on the workflow thread, as each model reply arrives.
        for future in as_completed(pending):
            item, pool, intent_keywords = pending[future]
            try:
                evaluation = future.result()
                if not isinstance(evaluation, AreaEvaluation):
                    raise ModelError("Invalid area contract")
                audit_area(db, item, pool, evaluation, intent_keywords)
            except Exception as exc:  # noqa: BLE001 — each area must fail closed independently.
                log.warning("area_review_incomplete type=%s", type(exc).__name__)
                item["status"] = "review_incomplete"
                item["people"] = []
            finally:
                _report(sid, done=item["id"])


def _apply_priority(db, session: dict, answers: list, card: dict, model) -> None:
    """Third model task. Any failure leaves the card in its original order."""
    try:
        priority = model.complete(
            "priority",
            {
                "idea": session["sentence"],
                "answers": answers,
                "areas": _priority_areas(card["areas"]),
            },
        )
        if (
            isinstance(priority, Priority)
            and len(priority.order) == len(card["areas"])
            and set(priority.order) == {a["id"] for a in card["areas"]}
        ):
            safe_shared_question = (
                priority.shared_question is None
                or _safe_shared_question(db, priority.shared_question, card)
            )
            order = {area_id: index for index, area_id in enumerate(priority.order)}
            card["areas"].sort(key=lambda area: order[area["id"]])
            shown = {p["person_id"] for a in card["areas"] for p in a["people"]}
            card["first_conversations"] = [
                pid
                for pid in dict.fromkeys(priority.first_conversations)
                if pid in shown
            ]
            if safe_shared_question:
                card["shared_question"] = priority.shared_question
    except Exception as exc:  # noqa: BLE001 — no raw model errors may reach user/logs.
        log.warning("priority_fallback type=%s", type(exc).__name__)


def _priority_areas(areas: list[dict]) -> list[dict]:
    """Keep out of the priority call what the model may not see (the expired-duty
    note with its source) and the area's rejection flags."""
    hidden = {"ended_duty", "context_ids"}
    diagnostics = {"direct_review_incomplete", "no_visible_work_trace"}
    return [
        {
            **{k: v for k, v in area.items() if k not in diagnostics},
            "people": [
                {k: v for k, v in person.items() if k not in hidden}
                for person in area["people"]
            ],
        }
        for area in areas
    ]


_UNSAFE_TEXT = re.compile(
    r"(?:https?://|\b[\w.+-]+@[\w.-]+\.|\b(?:jira|slack|docs|github|directory):)",
    re.IGNORECASE,
)


def _safe_question(text: str) -> bool:
    return 0 < len(text) <= 300 and text.endswith("?") and not _UNSAFE_TEXT.search(text)


def _lower_first(text: str) -> str:
    return text[0].lower() + text[1:]


def _excerpt(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " …"


def _safe_shared_question(db, text: str, card: dict) -> bool:
    if not _safe_question(text):
        return False
    shown = {person["person_id"] for area in card["areas"] for person in area["people"]}
    lowered = text.casefold()
    return not any(
        row["name"].casefold() in lowered and row["id"] not in shown
        for row in db.execute("SELECT id, name FROM people")
    )


def _evidence(db, candidate: dict, evidence_id: str) -> tuple[str, str, str] | None:
    evidence = next((e for e in candidate["evidence"] if e["id"] == evidence_id), None)
    if not evidence or not source(db, evidence_id):
        return None
    pid = candidate["person_id"]
    if evidence_id.startswith("directory:"):
        if evidence["kind"] == "responsibility":
            row = db.execute(
                """SELECT * FROM responsibilities WHERE person_id=? AND org_id=? AND source_id=?""",
                (pid, candidate["org_id"], evidence_id),
            ).fetchone()
        elif evidence["kind"] == "manager":
            row = db.execute(
                "SELECT * FROM managers WHERE person_id=? AND org_id=? AND source_id=?",
                (pid, candidate["org_id"], evidence_id),
            ).fetchone()
        elif evidence["kind"] == "remit":
            row = db.execute(
                "SELECT * FROM team_remits WHERE org_id=? AND source_id=?",
                (candidate["org_id"], evidence_id),
            ).fetchone()
        else:
            return None
        if not row or not current_and_visible(db, row):
            return None
        if evidence["kind"] == "responsibility":
            return (
                "responsibility",
                f"Current {row['relation']}: {row['scope']}.",
                f"Current {row['relation']} — {_lower_first(row['scope'])}.",
            )
        if evidence["kind"] == "manager":
            return (
                "manager",
                "Currently manages the relevant team.",
                "Currently manages the team.",
            )
        return (
            "remit",
            f"Team remit: {row['scope']}.",
            f"Team remit: {row['scope']}.",
        )
    record = visible_record(db, evidence_id)
    link = db.execute(
        "SELECT relation FROM work_links WHERE record_id=? AND person_id=? AND relation=?",
        (evidence_id, pid, evidence["relation"]),
    ).fetchone()
    if not record or not link:
        return None
    description = f"{evidence['relation'].capitalize()} of {record['kind']} record on {record['occurred_at']}: ‘{_excerpt(record['text'])}’"
    headline = f"{evidence['relation'].capitalize()} of a {record['kind']} record: ‘{_excerpt(record['text'], 120)}’"
    return evidence["relation"], description, headline


WORK_STRONG = {"assignee", "author", "contributor"}
DIRECT_KINDS = WORK_STRONG | {"responsibility"}
ADVISOR_KINDS = WORK_STRONG | {"responsibility", "reporter"}


def _ended_duty(db, person_id: str, topic: set[str]) -> dict | None:
    """A visible responsibility that has ended and shares a word with the area.

    The model never sees expired duties. This is a directory fact shown beside a
    person so an outdated owner is not mistaken for the current one. It is left
    out when the person holds a current duty on the topic, such as a renewal.
    """
    rows = [
        dict(row)
        for row in db.execute(
            """SELECT * FROM responsibilities WHERE person_id=?
            ORDER BY valid_to DESC, id""",
            (person_id,),
        )
        if topic & set(keywords(row["scope"]))
        and visible_directory_source(db, row["source_id"])
    ]
    if any(current(row) for row in rows):
        return None
    now = today()
    for row in rows:
        if row["valid_to"] and row["valid_to"] < now:
            return {
                "source_id": row["source_id"],
                "text": f"An earlier responsibility ended on {row['valid_to']}: {row['relation']} — {_lower_first(row['scope'])}.",
            }
    return None


def audit_area(
    db,
    item: dict,
    pool: dict,
    evaluation: AreaEvaluation,
    intent_keywords: list[str] | None = None,
) -> None:
    candidates = {p["person_id"]: p for p in pool["people"]}
    # The area's words for the ended-duty note: its label and need, plus its keyword
    # search intents, since a short need alone can miss the duty's words.
    topic = set(keywords(f"{item['label']} {item['consultation_need']}"))
    topic.update(term for text in intent_keywords or [] for term in keywords(text))
    teams = {row["id"]: row["name"] for row in db.execute("SELECT * FROM org_units")}
    accepted = []
    # A direct proposal that names a person or source outside the pool, a person
    # who is inactive or in another team, or a source no longer visible or current:
    # the review itself is unreliable.
    rejected_direct = False
    # A direct proposal on real evidence that does not show direct work. The prompt
    # tells the model to propose a manager only when it has no direct contact, so
    # the manager it held back may be added from the directory below.
    overclaimed = False

    def accept(candidate, role, primary, evidence_ids, facts, confidence):
        headline = facts[primary][2]
        if role == "routing_contact":
            # The reason for routing is added below, once the area's people are known.
            remit = next(f[2] for f in facts.values() if f[0] == "remit")
            headline = f"Manages the team. {remit}"
        ended = _ended_duty(db, candidate["person_id"], topic)
        accepted.append(
            {
                "person_id": candidate["person_id"],
                "name": candidate["name"],
                "title": candidate["title"],
                "org_id": candidate["org_id"],
                "team": teams.get(candidate["org_id"], candidate["org_id"]),
                "role": role,
                "primary_kind": facts[primary][0],
                # One short audited line for the plan at the top of the card.
                "headline": headline,
                # A directory fact the model did not see; its source is tracked so
                # the card fails closed if that source stops being visible.
                "ended_duty": ended["text"] if ended else None,
                "context_ids": [ended["source_id"]] if ended else [],
                "confidence": confidence,
                "primary_evidence_id": primary,
                "evidence_ids": evidence_ids,
                "why": [facts[primary][1]]
                + [fact[1] for sid, fact in facts.items() if sid != primary],
            }
        )

    def active_in_team(person_id: str, candidate: dict) -> bool:
        person = db.execute(
            "SELECT * FROM people WHERE id=? AND active=1", (person_id,)
        ).fetchone()
        return bool(person) and person["org_id"] == candidate["org_id"]

    for proposal in evaluation.people:
        candidate = candidates.get(proposal.person_id)
        if (
            not candidate
            or len(set(proposal.evidence_ids)) != len(proposal.evidence_ids)
            or proposal.primary_evidence_id not in proposal.evidence_ids
        ):
            rejected_direct |= proposal.role == "direct_contact"
            continue
        if not active_in_team(proposal.person_id, candidate):
            rejected_direct |= proposal.role == "direct_contact"
            continue
        facts = {sid: _evidence(db, candidate, sid) for sid in proposal.evidence_ids}
        if any(fact is None for fact in facts.values()):
            rejected_direct |= proposal.role == "direct_contact"
            continue
        kinds = {fact[0] for fact in facts.values()}
        primary_kind = facts[proposal.primary_evidence_id][0]
        role = proposal.role
        if role == "direct_contact":
            # A direct contact needs a strong work tie on its *primary* source, so
            # that a weak link on the relevant record cannot borrow strength from an
            # unrelated record in the same citation list.
            if proposal.relevance == "direct" and primary_kind in DIRECT_KINDS:
                pass
            # The model judged the link adjacent or weak, or claimed more than the
            # primary source shows. Keep an explainable contact as an advisor.
            elif primary_kind in ADVISOR_KINDS:
                overclaimed = True
                role = "advisor"
            else:
                overclaimed = True
                continue
        elif role == "advisor" and primary_kind not in ADVISOR_KINDS:
            # A mention or a manager line as the primary source is not a useful
            # consultation tie, whatever the other citations are.
            continue
        elif role == "routing_contact" and not {"manager", "remit"} <= kinds:
            continue
        accept(
            candidate,
            role,
            proposal.primary_evidence_id,
            proposal.evidence_ids,
            facts,
            proposal.confidence,
        )
    shown = {p["person_id"] for p in accepted}
    if (
        overclaimed
        and not rejected_direct
        and not any(
            p["role"] in {"direct_contact", "routing_contact"} for p in accepted
        )
    ):
        # The pool holds at most one manager: the team's single current manager,
        # with each visible remit that shares a word with the area's search intents.
        manager = next(
            (
                c
                for c in pool["people"]
                if any(e["kind"] == "manager" for e in c["evidence"])
            ),
            None,
        )
        if manager and manager["person_id"] not in shown:
            refs = [e["id"] for e in manager["evidence"] if e["kind"] == "manager"]
            refs += [e["id"] for e in manager["evidence"] if e["kind"] == "remit"]
            facts = {sid: _evidence(db, manager, sid) for sid in refs}
            if all(facts.values()) and active_in_team(manager["person_id"], manager):
                accept(manager, "routing_contact", refs[0], refs, facts, "low")
    has_direct = any(p["role"] == "direct_contact" for p in accepted)
    accepted = [
        p
        for p in accepted
        if p["role"] != "routing_contact" or (not has_direct and not rejected_direct)
    ]
    # Say why a manager is listed without contradicting an advisor shown beside them.
    reason = (
        "No direct contact for this was established."
        if any(p["role"] == "advisor" for p in accepted)
        else "No one was identified from the visible work on this."
    )
    for person in accepted:
        if person["role"] == "routing_contact":
            person["headline"] = f"{reason} {person['headline']}"
    item["people"] = sorted(
        accepted, key=lambda p: (ROLE_ORDER[p["role"]], p["person_id"])
    )
    item["direct_review_incomplete"] = rejected_direct and not has_direct
    item["status"] = (
        "people"
        if item["people"]
        else ("review_incomplete" if rejected_direct else "not_found")
    )
