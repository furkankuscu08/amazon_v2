"""Session orchestration and deterministic evidence/role audit."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from workbot.llm import ModelError
from workbot.models import AreaEvaluation, Impact, Priority
from workbot.search import candidate_pool
from workbot.storage import (
    current,
    load_session,
    org_inventory,
    source,
    store_card,
    visible_directory_source,
    visible_record,
)

log = logging.getLogger(__name__)
MAX_PARALLEL_AREA_CALLS = 2


class Conflict(Exception):
    pass


def _state(db, sid: str, state: str, question: str | None = None) -> None:
    db.execute(
        "UPDATE sessions SET state=?, question=?, card_json=NULL, snapshot_json=NULL WHERE id=?",
        (state, question, sid),
    )
    db.commit()


def create_session(db, idem_key: str, sentence: str, model, searcher) -> str:
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
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT * FROM sessions WHERE actor='maya' AND workspace='demo' AND idem_key=?",
            (idem_key,),
        ).fetchone()
        if row and row["sentence"] == sentence:
            return row["id"]
        raise Conflict("This request key belongs to a different idea") from None
    run_safely(db, sid, model, searcher)
    return sid


def answer_question(db, sid: str, answer: str | None, model, searcher) -> None:
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
        _state(db, sid, "refusal")
        return
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
    run_safely(db, sid, model, searcher)


def run_safely(db, sid: str, model, searcher) -> None:
    try:
        run(db, sid, model, searcher)
    except Exception as exc:  # noqa: BLE001 — no raw model or document text in logs.
        log.warning("workflow_failed type=%s", type(exc).__name__)
        _state(db, sid, "refusal")


def _collect_area_reviews(
    db, card: dict, pending: dict[Future, tuple[dict, dict, float]]
) -> None:
    done, _ = wait(pending, return_when=FIRST_COMPLETED)
    for future in done:
        item, pool, started = pending.pop(future)
        try:
            evaluation = future.result()
            if not isinstance(evaluation, AreaEvaluation):
                raise ModelError("Invalid area contract")
            audit_area(db, item, pool, evaluation)
        except Exception as exc:  # noqa: BLE001 — each area must fail closed independently.
            log.warning("area_review_incomplete type=%s", type(exc).__name__)
            item["status"] = "review_incomplete"
            item["people"] = []
        finally:
            card["duration_seconds"][item["id"]] = round(time.monotonic() - started, 3)


def run(db, sid: str, model, searcher) -> None:
    session = load_session(db, sid)
    if not session or session["state"] != "processing":
        return
    inventory = org_inventory(db)
    if not inventory:
        _state(db, sid, "refusal")
        return
    impact_started = time.monotonic()
    payload = {
        "idea": session["sentence"],
        "answers": json.loads(session["answers_json"]),
        "org_units": inventory,
        "remaining_questions": max(0, 2 - session["questions_asked"]),
    }
    if len(json.dumps(payload)) > 12000:
        _state(db, sid, "refusal")
        return
    try:
        impact = model.complete("impact", payload)
        if not isinstance(impact, Impact):
            raise ModelError("Invalid impact contract")
        if impact.question:
            if (
                not _safe_question(impact.question)
                or session["questions_asked"] >= 2
                or any(a["answer"] is None for a in payload["answers"])
            ):
                raise ModelError("Question budget exhausted")
            db.execute(
                "UPDATE sessions SET state='question', question=?, questions_asked=questions_asked+1 WHERE id=?",
                (impact.question, sid),
            )
            db.commit()
            return
        org_ids = {item["id"] for item in inventory}
        if any(
            a.mapping == "mapped" and a.org_unit_id not in org_ids for a in impact.areas
        ):
            raise ModelError("Unknown org unit")
    except (ModelError, ValueError):
        _state(db, sid, "refusal")
        return

    card = {
        "idea": session["sentence"],
        "areas": [],
        "shared_question": None,
        "priority_applied": False,
        "calls": {"impact": 1, "area": 0, "priority": 0},
        "duration_seconds": {"impact": round(time.monotonic() - impact_started, 3)},
    }
    pending: dict[Future, tuple[dict, dict, float]] = {}
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
                "retrieval": {
                    "bm25": 0,
                    "qdrant": 0,
                    "visible_records": 0,
                    "candidates": 0,
                },
            }
            card["areas"].append(item)
            if area.mapping == "mapping_unresolved":
                continue
            if len(pending) == MAX_PARALLEL_AREA_CALLS:
                _collect_area_reviews(db, card, pending)
            started = time.monotonic()
            submitted = False
            try:
                # Search and all permissioned directory reads stay on this thread.
                records = searcher.records(
                    db, [intent.model_dump() for intent in area.search_intents]
                )
                item["retrieval"] = {
                    "bm25": sum(
                        "bm25" in record.get("retrieval_channels", [])
                        for record in records
                    ),
                    "qdrant": sum(
                        "qdrant" in record.get("retrieval_channels", [])
                        for record in records
                    ),
                    "visible_records": len(records),
                    "candidates": 0,
                }
                pool = candidate_pool(db, area.model_dump(), records)
                item["retrieval"]["candidates"] = len(pool["people"])
                item["no_visible_work_trace"] = pool["no_visible_work_trace"]
                if not pool["people"]:
                    continue
                prompt = {
                    "idea": session["sentence"],
                    "answers": payload["answers"],
                    "area": area.model_dump(),
                    "candidates": pool["people"],
                }
                if len(json.dumps(prompt)) > 18000:
                    item["status"] = "review_incomplete"
                    continue
                future = executor.submit(model.complete, "area", prompt)
                pending[future] = (item, pool, started)
                submitted = True
                card["calls"]["area"] += 1
            except Exception as exc:  # noqa: BLE001 — search/preparation must fail closed.
                log.warning("area_review_incomplete type=%s", type(exc).__name__)
                item["status"] = "review_incomplete"
                item["people"] = []
            finally:
                if not submitted:
                    card["duration_seconds"][area.id] = round(
                        time.monotonic() - started, 3
                    )
        while pending:
            _collect_area_reviews(db, card, pending)

    priority_started = time.monotonic()
    try:
        card["calls"]["priority"] = 1
        priority = model.complete(
            "priority", {"idea": session["sentence"], "areas": card["areas"]}
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
            if safe_shared_question:
                card["shared_question"] = priority.shared_question
            card["priority_applied"] = True
    except Exception as exc:  # noqa: BLE001 — no raw model errors may reach user/logs.
        log.warning("priority_fallback type=%s", type(exc).__name__)
    card["duration_seconds"]["priority"] = round(time.monotonic() - priority_started, 3)
    try:
        store_card(db, sid, card)
    except ValueError:
        _state(db, sid, "refusal")


def _safe_question(text: str) -> bool:
    return (
        0 < len(text) <= 300
        and text.endswith("?")
        and not re.search(
            r"(?:https?://|\b[\w.+-]+@[\w.-]+\.|\b(?:jira|slack|docs|github|directory):)",
            text,
            re.IGNORECASE,
        )
    )


def _safe_shared_question(db, text: str, card: dict) -> bool:
    if not _safe_question(text):
        return False
    shown = {person["person_id"] for area in card["areas"] for person in area["people"]}
    lowered = text.casefold()
    return not any(
        row["name"].casefold() in lowered and row["id"] not in shown
        for row in db.execute("SELECT id, name FROM people")
    )


def _evidence(db, candidate: dict, evidence_id: str) -> tuple[str, str] | None:
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
        if (
            not row
            or not current(dict(row))
            or not visible_directory_source(db, evidence_id)
        ):
            return None
        if evidence["kind"] == "responsibility":
            return (
                "responsibility",
                f"Currently {row['relation']} for {row['scope']} [{evidence_id}].",
            )
        if evidence["kind"] == "manager":
            return ("manager", f"Currently manages the relevant team [{evidence_id}].")
        return ("remit", f"The team covers {row['scope']} [{evidence_id}].")
    record = visible_record(db, evidence_id)
    link = db.execute(
        "SELECT relation FROM work_links WHERE record_id=? AND person_id=? AND relation=?",
        (evidence_id, pid, evidence["relation"]),
    ).fetchone()
    if not record or not link:
        return None
    description = f"{evidence['relation'].capitalize()} of {record['kind']} record on {record['occurred_at']}: ‘{record['text'][:220]}’ [{evidence_id}]."
    return evidence["relation"], description


WORK_STRONG = {"assignee", "author", "contributor"}
DIRECT_KINDS = WORK_STRONG | {"responsibility"}
ADVISOR_KINDS = WORK_STRONG | {"responsibility", "reporter"}


def audit_area(db, item: dict, pool: dict, evaluation: AreaEvaluation) -> None:
    candidates = {p["person_id"]: p for p in pool["people"]}
    accepted = []
    rejected_direct = False
    for proposal in evaluation.people:
        candidate = candidates.get(proposal.person_id)
        if (
            not candidate
            or not _safe_question(proposal.ask)
            or len(set(proposal.evidence_ids)) != len(proposal.evidence_ids)
            or proposal.primary_evidence_id not in proposal.evidence_ids
        ):
            rejected_direct |= proposal.role == "direct_contact"
            continue
        person = db.execute(
            "SELECT * FROM people WHERE id=? AND active=1", (proposal.person_id,)
        ).fetchone()
        if not person or person["org_id"] != candidate["org_id"]:
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
            # The model itself judged the link adjacent or weak. Keep an explainable
            # contact as an advisor rather than dropping it or asserting a direct tie.
            elif (
                proposal.relevance in {"adjacent", "weak"}
                and primary_kind in ADVISOR_KINDS
            ):
                role = "advisor"
            else:
                rejected_direct = True
                continue
        elif role == "advisor" and not kinds & ADVISOR_KINDS:
            # A mention-only mirror of a name is not a useful consultation contact.
            continue
        elif role == "routing_contact" and not {"manager", "remit"} <= kinds:
            continue
        accepted.append(
            {
                "person_id": proposal.person_id,
                "name": candidate["name"],
                "role": role,
                "confidence": proposal.confidence,
                "evidence_ids": proposal.evidence_ids,
                "why": [fact[1] for fact in facts.values()],
                "ask": proposal.ask,
                # The model must acknowledge uncertainty in its schema, but its
                # untrusted free text is replaced by a stable, role-specific caution.
                "unverified": (
                    "Ownership of the new idea and subject expertise have not been established."
                    if role == "routing_contact"
                    else "Ownership of the new initiative and applicability of prior work have not been established."
                ),
            }
        )
    has_direct = any(p["role"] == "direct_contact" for p in accepted)
    accepted = [
        p
        for p in accepted
        if p["role"] != "routing_contact" or (not has_direct and not rejected_direct)
    ]
    role_order = {"direct_contact": 0, "advisor": 1, "routing_contact": 2}
    item["people"] = sorted(
        accepted, key=lambda p: (role_order[p["role"]], p["person_id"])
    )
    item["direct_review_incomplete"] = rejected_direct and not has_direct
    item["status"] = (
        "people"
        if item["people"]
        else ("review_incomplete" if rejected_direct else "not_found")
    )
