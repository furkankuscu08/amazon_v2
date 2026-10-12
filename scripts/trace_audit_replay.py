"""Offline audit-only replay of captured traces against the current audit.

This never calls a model or the network. It rebuilds each mapped area's visible
candidate pool from the captured ``retrieved_ids`` and ``search_intents`` with a
freshly seeded SQLite database, submits the schema-valid captured proposals to
the current ``audit_area``, and reports only audit/UI delta counts and status
transitions. It makes no accuracy or model-behavior claims.
An uncaptured contribution is an explicit, unscored offline placeholder.
"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from scripts.historical_models import historical_evaluation
from scripts.trace_diagnostics import (
    RESTRICTED_MARKERS,
    TRACES,
    _run_with_seeded_db,
    _stage,
    validate_traces,
)
from workbot.models import AreaEvaluation
from workbot.search import candidate_pool
from workbot.service import _grounded_ask, _safe_question, audit_area
from workbot.storage import visible_record

PLACEHOLDER_UNVERIFIED = "Offline replay placeholder; not evaluated."
CARD_AREA_KEYS = {"id", "status", "people", "direct_review_incomplete"}
NEUTRAL_ASKS = {
    _grounded_ask(role, kind)
    for role in ("direct_contact", "advisor", "routing_contact")
    for kind in (
        "assignee",
        "author",
        "contributor",
        "reporter",
        "responsibility",
        "manager",
        "remit",
    )
}
# Diagnostic stage -> replay skip reason; every other stage has parsable output.
SKIP_REASONS = {
    "mapping_unresolved": "mapping_unresolved",
    "no_candidates": "no_candidates",
    "model_truncated": "truncated",
    "model_failed": "model_failed",
}
NOTE = (
    "Offline audit-only replay over captured synthetic runs: counts of audit and UI "
    "deltas plus status transitions only. It does not measure model accuracy, "
    "does not rerun retrieval or generation, and makes no model-behavior claim."
)


def _validate_intents(area: dict) -> None:
    intents = area.get("search_intents")
    if not isinstance(intents, list) or not intents:
        raise ValueError(f"Area {area['id']} is missing captured search intents")
    for intent in intents:
        if not isinstance(intent, dict) or set(intent) != {"keyword", "semantic"}:
            raise ValueError(f"Area {area['id']} has malformed search intents")
        if not all(
            isinstance(intent[field], str) and intent[field]
            for field in ("keyword", "semantic")
        ):
            raise ValueError(f"Area {area['id']} has empty search intents")


def _pool_area(area: dict) -> dict:
    return {
        "id": area["id"],
        "consultation_need": area["consultation_need"],
        "search_intents": area["search_intents"],
        "mapping": area["mapping"],
        "org_unit_id": area["org_unit_id"],
    }


def _reconstruct_pool(db, area: dict) -> tuple[dict, str]:
    records = []
    for record_id in area["retrieved_ids"]:
        record = visible_record(db, record_id)
        if record is None:
            raise ValueError(
                f"Area {area['id']} cites an unavailable record {record_id!r}"
            )
        records.append(record)
    pool = candidate_pool(db, _pool_area(area), records)
    captured = list(area["candidate_ids"])
    reconstructed = [person["person_id"] for person in pool["people"]]
    if reconstructed == captured:
        return pool, "exact_order"
    if set(reconstructed) == set(captured):
        return pool, "set_only"
    raise ValueError(
        f"Candidate mismatch for area {area['id']}: "
        f"captured={captured} reconstructed={reconstructed}"
    )


def _captured_evaluation(area: dict) -> AreaEvaluation:
    people = [
        {
            "person_id": proposal["person_id"],
            "role": proposal["role"],
            "primary_evidence_id": proposal["primary_evidence_id"],
            "relevance": proposal["relevance"],
            "evidence_ids": list(proposal["evidence_ids"]),
            "confidence": proposal["confidence"],
            "ask": proposal["ask"],
            "unverified": PLACEHOLDER_UNVERIFIED,
            **(
                {"contribution": proposal["contribution"]}
                if "contribution" in proposal
                else {}
            ),
        }
        for proposal in area["model_proposals"]
    ]
    return historical_evaluation(people)


def _acceptance(people: list[dict]) -> set:
    return {
        (person["person_id"], person["role"], frozenset(person["evidence_ids"]))
        for person in people
    }


def _check_card_shape(item: dict) -> list[str]:
    telemetry = sorted(set(item) - CARD_AREA_KEYS)
    for person in item["people"]:
        primary = person.get("primary_evidence_id")
        if not primary or primary not in person["evidence_ids"]:
            raise ValueError(
                f"Accepted person {person['person_id']} lacks its primary source"
            )
        if not _safe_question(person["ask"]) or person["ask"] not in NEUTRAL_ASKS:
            raise ValueError(
                f"Accepted person {person['person_id']} lacks a neutral safe ask"
            )
        if f"[{primary}]" not in person["why"][0]:
            raise ValueError(
                f"Accepted person {person['person_id']} does not show its primary first"
            )
    return telemetry


def replay_traces(traces: list[dict], db) -> dict:
    validate_traces(traces, db)
    skipped: Counter = Counter()
    transitions = []
    status_by_area: dict[str, dict] = {}
    acceptance_changed = []
    ui = Counter()
    telemetry_fields: set[str] = set()
    replay_areas = 0
    unchanged = 0
    reconstruction: Counter = Counter()

    for run in traces:
        run_key = f"{run['scenario']}#{run['iteration']}"
        for area in run["areas"]:
            _validate_intents(area)
            key = f"{run_key}/{area['id']}"
            skip_reason = SKIP_REASONS.get(_stage(area))
            if skip_reason:
                skipped[skip_reason] += 1
                status_by_area[key] = {
                    "replayed": False,
                    "skip_reason": skip_reason,
                    "old_status": area["status"],
                    "new_status": None,
                }
                continue

            pool, mode = _reconstruct_pool(db, area)
            reconstruction[mode] += 1
            item = {
                "id": area["id"],
                "status": "not_found",
                "people": [],
                "direct_review_incomplete": False,
            }
            audit_area(db, item, pool, _captured_evaluation(area))
            replay_areas += 1
            telemetry_fields.update(_check_card_shape(item))

            old = _acceptance(area["accepted_people"])
            new = _acceptance(item["people"])
            same = old == new
            unchanged += int(same)
            if not same:
                acceptance_changed.append(
                    {
                        "run": run_key,
                        "area": area["id"],
                        "old": sorted(str(entry) for entry in old),
                        "new": sorted(str(entry) for entry in new),
                    }
                )
            old_asks = {p["person_id"]: p["ask"] for p in area["accepted_people"]}
            for person in item["people"]:
                ui["accepted_people"] += 1
                ui["primary_evidence_id_present"] += int(
                    bool(person.get("primary_evidence_id"))
                )
                ui["neutral_safe_ask"] += int(person["ask"] in NEUTRAL_ASKS)
                ui["ask_changed_from_original"] += int(
                    old_asks.get(person["person_id"]) != person["ask"]
                )
                ui["why_primary_first"] += int(
                    f"[{person['primary_evidence_id']}]" in person["why"][0]
                )
            if area["status"] != item["status"]:
                transitions.append(
                    {
                        "run": run_key,
                        "area": area["id"],
                        "old": area["status"],
                        "new": item["status"],
                    }
                )
            status_by_area[key] = {
                "replayed": True,
                "skip_reason": None,
                "old_status": area["status"],
                "new_status": item["status"],
            }

    result = {
        "source": None,
        "no_model_calls": True,
        "note": NOTE,
        "areas_total": sum(len(run["areas"]) for run in traces),
        "areas_replayed": replay_areas,
        "areas_skipped": {
            "mapping_unresolved": skipped["mapping_unresolved"],
            "no_candidates": skipped["no_candidates"],
            "truncated": skipped["truncated"],
            "model_failed": skipped["model_failed"],
        },
        "candidate_reconstruction": {
            "exact_order": reconstruction["exact_order"],
            "set_only": reconstruction["set_only"],
            "mismatches": 0,
        },
        "acceptance": {
            "areas_unchanged": unchanged,
            "areas_changed": len(acceptance_changed),
            "changed": acceptance_changed,
        },
        "status": {
            "transitions": transitions,
            "transition_count": len(transitions),
            "pairs": dict(
                Counter(f"{entry['old']}->{entry['new']}" for entry in transitions)
            ),
            "by_area": status_by_area,
        },
        "ui": {
            "accepted_people": ui["accepted_people"],
            "primary_evidence_id_present": ui["primary_evidence_id_present"],
            "neutral_safe_ask": ui["neutral_safe_ask"],
            "ask_changed_from_original": ui["ask_changed_from_original"],
            "why_primary_first": ui["why_primary_first"],
        },
        "safety": {
            "restricted_markers_found": [],
            "restricted_people_found": [],
            "card_telemetry_fields": sorted(telemetry_fields),
        },
    }
    serialized = json.dumps(result)
    result["safety"]["restricted_markers_found"] = [
        marker for marker in RESTRICTED_MARKERS if marker in serialized
    ]
    result["safety"]["restricted_people_found"] = [
        person_id for person_id in ("eve",) if f'"{person_id}"' in serialized
    ]
    return result


def run(path: Path = TRACES) -> dict:
    return _run_with_seeded_db(path, replay_traces, "audit_replay.sqlite3")


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=TRACES)
    args = parser.parse_args()
    print(json.dumps(run(args.traces), indent=2))


if __name__ == "__main__":
    main()
