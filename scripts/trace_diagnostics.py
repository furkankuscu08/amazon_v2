"""Offline stage diagnostics for captured live consultation traces.

The input is a sanitized fixture of captured synthetic DeepSeek/Nitro runs and
the output is explicit counts and per-area stage attribution. This module never
calls a model, reads the raw provider capture, or scores a vague "accuracy":
each metric below has a single stated denominator and unit.
"""

from __future__ import annotations

import json
import re
import tempfile
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from workbot.seed import seed_db
from workbot.service import _safe_question
from workbot.storage import connect, current, source, visible_directory_source

TRACES = Path(__file__).resolve().parents[1] / "tests/fixtures/quality_live_traces.json"
LABELS = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/quality_trace_labels.json"
)
LOW_TRACES = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/quality_low_traces.json"
)
LOW_LABELS = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/quality_low_labels.json"
)

AREA_ID = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
ROLES = {"direct_contact", "advisor", "routing_contact"}
MAX_PARALLEL_AREA_CALLS = 2

# Shared by the diagnostics, the audit replay, and their tests: these strings
# must never appear in a visible card, candidate pool, or emitted result.
RESTRICTED_MARKERS = (
    "restricted-plan",
    "restricted-budget",
    "secret-duty",
    "Eve Restricted",
)

# One boolean per access invariant, with the exact message raised when it fails.
ACCESS_CHECKS = {
    "restricted_source_404": "Restricted source did not return 404",
    "restricted_directory_404": "Restricted directory source did not return 404",
    "visible_leak_marker_clear": "A restricted leak marker was visible",
    "restricted_context_blocked_clear": (
        "A restricted-only candidate reached model context"
    ),
    "reload_identical": "Card did not reload identically",
    "peak_parallel_within_bound": "Area concurrency exceeded the two-call bound",
    "source_status_200": "A cited source did not return 200",
}

CASE_METRICS = (
    ("reference_available", "reference_cases", "reference_available"),
    ("candidate_present", "candidate_cases", "candidate_present"),
    ("primary_shown", "primary_cases", "primary_shown"),
    (
        "model_unsupported_direct",
        "model_unsupported_direct_cases",
        "model_unsupported_direct_violations",
    ),
    ("unsupported_direct", "unsupported_direct_cases", "unsupported_direct_violations"),
    ("hard_negative", "hard_negative_cases", "hard_negative_violations"),
    (
        "model_ask_premise_violation",
        "model_ask_premise_cases",
        "model_ask_premise_violations",
    ),
    (
        "card_ask_premise_violation",
        "card_ask_premise_cases",
        "card_ask_premise_violations",
    ),
    ("role_match", "role_cases", "role_matches"),
)

METRIC_DEFINITIONS = {
    "run_count": "Number of captured runs in the fixture; each is one live HTTP session.",
    "area_count": "Number of consultation areas across all runs.",
    "mapping_unresolved_areas": "Areas the impact stage left unmapped; no retrieval or area call happened.",
    "no_candidate_areas": "Mapped areas with an empty visible candidate pool; no area model call happened.",
    "model_empty_areas": "Areas with visible candidates whose area call returned a valid response naming zero people (finish_reason is not 'length'). This is genuine model abstention, not an audit drop.",
    "model_truncated_areas": "Areas whose area call ended with finish_reason 'length'; the response was truncated and had no parsed people.",
    "model_failed_areas": "Areas whose area call returned a non-length transport error and therefore had no parsable people.",
    "proposed_but_dropped_areas": "Areas where the model named at least one person and the deterministic audit accepted none.",
    "proposed_partially_accepted_areas": "Areas where the audit accepted at least one and dropped at least one model proposal.",
    "proposed_accepted_areas": "Areas where every model proposal was accepted.",
    "invalid_ask_proposals": "Dropped model proposals whose ask fails the deterministic _safe_question format check (1-300 chars, ends with '?', no leaked IDs). This is a contributing reason a proposal was dropped; a valid ask alone does not establish semantic relevance or a supported premise.",
    "areas_decided": "Areas with at least one adjudication case or a non-null area_need_supported.",
    "areas_pending": "Areas with an empty case list and a null area_need_supported; excluded from every adjudicated denominator.",
    "cases": "Total per-person adjudication cases across all areas; each case is one person in one area.",
    "area_need_cases": "Areas whose area_need_supported was adjudicated.",
    "area_need_unsupported": "Of area_need_cases, how many marked the area's consultation need unsupported.",
    "reference_cases": "Positive cases (expected_visible true) with a non-empty expected_primary_evidence_ids list.",
    "reference_available": "Of reference_cases, how many had at least one acceptable primary source visible, linked to the person, and (for work records) retrieved for that area.",
    "candidate_cases": "Cases adjudicated expected_visible true (a positive person).",
    "candidate_present": "Of candidate_cases, how many positive people were in the area's visible candidate_ids.",
    "primary_cases": "Positive cases (expected_visible true) with a non-empty expected_primary_evidence_ids list; the primary coverage denominator.",
    "primary_shown": "Of primary_cases, how many showed the correct primary source in the accepted card: the model proposal matching the accepted person id must name a primary inside expected_primary_evidence_ids, and that same source must appear in the accepted person's evidence_ids. A positive person the card did not accept counts as not shown. Role is ignored and secondary-only citations do not satisfy this metric.",
    "model_unsupported_direct_cases": "Cases explicitly labeled not direct (expected_direct false) or expected to be absent (expected_visible false); evaluated at the model proposal stage.",
    "model_unsupported_direct_violations": "Of model_unsupported_direct_cases, how many the model proposed as direct_contact, whether or not the audit later accepted them.",
    "unsupported_direct_cases": "Cases explicitly labeled not direct (expected_direct false) or expected to be absent (expected_visible false).",
    "unsupported_direct_violations": "Of unsupported_direct_cases, how many the card nevertheless accepted as direct_contact. Distinct from the model's unsupported direct proposals.",
    "hard_negative_cases": "Cases adjudicated expected_visible false (the person should not be shown in that area).",
    "hard_negative_violations": "Of hard_negative_cases, how many the card accepted in any role.",
    "model_ask_premise_cases": "Cases with a non-null model_ask_premise_supported whose person has a captured model proposal (shown or dropped).",
    "model_ask_premise_violations": "Of model_ask_premise_cases, how many marked the model-generated ask premise unsupported.",
    "card_ask_premise_cases": "Cases with a non-null card_ask_premise_supported whose person is shown on the accepted card.",
    "card_ask_premise_violations": "Of card_ask_premise_cases, how many marked the user-visible card ask premise unsupported. Counted separately from the model ask.",
    "role_cases": "Cases with a non-null expected_role whose person is shown on the accepted card.",
    "role_matches": "Of role_cases, how many accepted the expected exact role. Reported separately and never folded into primary_shown.",
}

NOTE = (
    "These are counts over captured synthetic runs, not accuracy, precision, "
    "or recall estimates. Pending adjudication is excluded from every adjudicated "
    "denominator, so a zero denominator means 'not yet reviewed', not 'all clean'."
)


def load_traces(path: Path = TRACES) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def attach_labels(traces: list[dict], path: Path = LABELS) -> dict:
    """Keep the frozen observations separate from assistant-reviewed judgments."""
    labels = json.loads(path.read_text(encoding="utf-8"))
    if labels["provenance"]["reviewer"] != "assistant":
        raise ValueError("Trace label provenance must identify its reviewer")
    areas = {
        f"{run['scenario']}#{run['iteration']}/{area['id']}": area
        for run in traces
        for area in run["areas"]
    }
    if set(labels["areas"]) != set(areas):
        raise ValueError("Trace labels must cover each captured area exactly once")
    for key, annotation in labels["areas"].items():
        cases = annotation["cases"]
        if not isinstance(cases, dict):
            raise TypeError(f"Malformed cases in {key}")
        areas[key]["adjudication"] = {
            "area_need_supported": annotation["area_need_supported"],
            "cases": [
                {
                    "person_id": person_id,
                    "expected_visible": case.get("expected_visible"),
                    "expected_direct": case.get("expected_direct"),
                    "expected_role": case.get("expected_role"),
                    "expected_primary_evidence_ids": case.get(
                        "expected_primary_evidence_ids", []
                    ),
                    "model_ask_premise_supported": case.get(
                        "model_ask_premise_supported"
                    ),
                    "card_ask_premise_supported": case.get(
                        "card_ask_premise_supported"
                    ),
                }
                for person_id, case in cases.items()
            ],
        }
    return labels["provenance"]


def _visible_people(db) -> set[str]:
    """Mirror the visibility rule used by candidate selection and the audit."""
    people = {
        row["person_id"]
        for row in db.execute(
            """SELECT DISTINCT link.person_id FROM work_links AS link
            JOIN work_records AS record ON record.id=link.record_id
            JOIN people AS person ON person.id=link.person_id
            WHERE record.visibility='maya' AND person.active=1"""
        )
    }
    for table in ("responsibilities", "managers"):
        for row in db.execute(
            f"""SELECT relation.* FROM {table} AS relation
            JOIN directory_sources AS source ON source.id=relation.source_id
            JOIN people AS person ON person.id=relation.person_id
            WHERE source.visibility='maya' AND person.active=1"""
        ):
            if current(dict(row)):
                people.add(row["person_id"])
    return people


def _flag(value) -> bool:
    return value is None or value is True or value is False


def _person_source(db, source_id: str, person_id: str) -> bool:
    """True when a visible source is actually linked to the visible person."""
    if source_id.startswith("directory:"):
        if visible_directory_source(db, source_id) is None:
            return False
        for table in ("responsibilities", "managers"):
            row = db.execute(
                f"SELECT * FROM {table} WHERE source_id=? AND person_id=?",
                (source_id, person_id),
            ).fetchone()
            if row and current(dict(row)):
                return True
        # A current manager may cite a current remit for their team as routing
        # evidence; that remit is tied to the managed org, not the person row.
        for row in db.execute(
            """SELECT remit.*, manager.source_id AS manager_source,
            manager.valid_from AS manager_from, manager.valid_to AS manager_to
            FROM team_remits AS remit JOIN managers AS manager
            ON manager.org_id=remit.org_id
            WHERE remit.source_id=? AND manager.person_id=?""",
            (source_id, person_id),
        ):
            if (
                current(dict(row))
                and current(
                    {"valid_from": row["manager_from"], "valid_to": row["manager_to"]}
                )
                and visible_directory_source(db, row["manager_source"]) is not None
            ):
                return True
        return False
    if source(db, source_id) is None:
        return False
    return (
        db.execute(
            "SELECT 1 FROM work_links WHERE record_id=? AND person_id=?",
            (source_id, person_id),
        ).fetchone()
        is not None
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _access_checks(run: dict) -> dict[str, bool]:
    access = run["access"]
    return {
        "restricted_source_404": access["restricted_source_status"] == 404,
        "restricted_directory_404": access["restricted_directory_status"] == 404,
        "visible_leak_marker_clear": access["visible_leak_marker"] is False,
        "restricted_context_blocked_clear": access["restricted_context_blocked"]
        is False,
        "reload_identical": access["reload_identical"] is True,
        "peak_parallel_within_bound": (
            1 <= access["peak_parallel_areas"] <= MAX_PARALLEL_AREA_CALLS
        ),
        "source_status_200": all(
            status == 200 for status in run["source_statuses"].values()
        ),
    }


def _validate_access(run: dict) -> None:
    for field, passed in _access_checks(run).items():
        _require(passed, ACCESS_CHECKS[field])


def _validate_area(area: dict, db, visible: set[str]) -> None:
    area_id = area["id"]
    _require(
        _flag(area["adjudication"]["area_need_supported"]),
        f"Area {area_id} has a malformed need label",
    )
    _require(
        isinstance(area_id, str) and AREA_ID.fullmatch(area_id) is not None,
        f"Malformed area id {area_id!r}",
    )
    for person_id in area["candidate_ids"]:
        _require(person_id in visible, f"Area {area_id} has no visible person evidence")
    for source_id in area["retrieved_ids"]:
        _require(
            source(db, source_id) is not None,
            f"Area {area_id} cites an unavailable source",
        )
    for proposal in area["model_proposals"]:
        _require(
            proposal["person_id"] in visible,
            f"Proposal in {area_id} has no visible person evidence",
        )
        _require(proposal["role"] in ROLES, f"Unknown proposal role in area {area_id}")
        _require(
            proposal["primary_evidence_id"] in proposal["evidence_ids"],
            f"Proposal primary is not cited in area {area_id}",
        )
        for source_id in proposal["evidence_ids"]:
            _require(
                source(db, source_id) is not None,
                f"Proposal in {area_id} cites an unavailable source",
            )
    for person in area["accepted_people"]:
        _require(
            person["person_id"] in visible,
            f"Accepted person in {area_id} lacks visible evidence",
        )
        _require(
            _safe_question(person["ask"]),
            f"Accepted ask in {area_id} fails the format contract",
        )
        for source_id in person["evidence_ids"]:
            _require(
                source(db, source_id) is not None,
                f"Accepted person in {area_id} cites an unavailable source",
            )
            _require(
                _person_source(db, source_id, person["person_id"]),
                f"Accepted person in {area_id} cites a source not linked to them",
            )

    seen_cases: set[str] = set()
    for case in area["adjudication"]["cases"]:
        person_id = case["person_id"]
        _require(
            person_id not in seen_cases,
            f"Area {area_id} has a duplicate case person",
        )
        seen_cases.add(person_id)
        _validate_case(area_id, case, db, visible)


def _validate_case(area_id: str, case: dict, db, visible: set[str]) -> None:
    person_id = case["person_id"]
    _require(
        person_id in visible,
        f"Area {area_id} has a case for a person without visible evidence",
    )
    _require(
        _flag(case["expected_visible"]),
        f"Area {area_id} has a malformed expected visibility",
    )
    _require(
        _flag(case["expected_direct"]),
        f"Area {area_id} has a malformed expected direct label",
    )
    role = case["expected_role"]
    _require(
        role is None or role in ROLES | {"none"},
        f"Area {area_id} has an unknown expected role",
    )
    _require(
        _flag(case["model_ask_premise_supported"]),
        f"Area {area_id} has a malformed model ask premise label",
    )
    _require(
        _flag(case["card_ask_premise_supported"]),
        f"Area {area_id} has a malformed card ask premise label",
    )
    for source_id in case["expected_primary_evidence_ids"]:
        _require(
            source(db, source_id) is not None,
            f"Area {area_id} references an unavailable source",
        )
        _require(
            _person_source(db, source_id, person_id),
            f"Area {area_id} references a source that does not belong to the person",
        )
    _validate_case_labels(area_id, person_id, case)


def _validate_case_labels(area_id: str, person_id: str, case: dict) -> None:
    """Reject per-person labels that contradict each other before scoring."""
    visible = case["expected_visible"]
    direct = case["expected_direct"]
    role = case["expected_role"]
    prefix = f"Area {area_id} case {person_id}"
    if visible is False:
        if role in ROLES:
            raise ValueError(f"{prefix} marks an absent person as {role}")
        if direct is True:
            raise ValueError(f"{prefix} marks an absent person as direct")
        if case["expected_primary_evidence_ids"]:
            raise ValueError(
                f"{prefix} marks an absent person with expected primary evidence"
            )
    if visible is True:
        if role == "none":
            raise ValueError(f"{prefix} marks a positive person as none")
        if direct is False and role == "direct_contact":
            raise ValueError(
                f"{prefix} marks a positive person as not direct "
                "but expects direct_contact"
            )
    if direct is True and role in {"advisor", "none"}:
        raise ValueError(f"{prefix} marks direct as acceptable while expecting {role}")


def _validate_run(run: dict, db, visible: set[str], seen_runs: set) -> None:
    scenario = run["scenario"]
    iteration = run["iteration"]
    key = (scenario, iteration)
    _require(key not in seen_runs, f"Duplicate run {scenario}#{iteration}")
    seen_runs.add(key)
    for source_id in run["source_statuses"]:
        _require(
            source(db, source_id) is not None,
            f"Run {scenario}#{iteration} reports an unavailable source",
        )
    _validate_access(run)

    seen_areas: set[str] = set()
    for area in run["areas"]:
        _require(
            area["id"] not in seen_areas,
            f"Duplicate area id {area['id']!r} in run {scenario}#{iteration}",
        )
        seen_areas.add(area["id"])
        _validate_area(area, db, visible)


def validate_traces(traces: list[dict], db) -> None:
    """Reject duplicate or malformed fixture ids and restricted-only content."""
    visible = _visible_people(db)
    seen_runs: set = set()
    for run in traces:
        _validate_run(run, db, visible, seen_runs)


def _reference_available(area: dict, source_id: str, person_id: str, db) -> bool:
    if not _person_source(db, source_id, person_id):
        return False
    if source_id.startswith("directory:"):
        return True
    return source_id in area["retrieved_ids"]


def _case_outcome(area: dict, case: dict, db) -> dict:
    person_id = case["person_id"]
    accepted = next(
        (p for p in area["accepted_people"] if p["person_id"] == person_id), None
    )
    proposal = next(
        (p for p in area["model_proposals"] if p["person_id"] == person_id), None
    )
    expected_visible = case["expected_visible"]
    expected_primary = case["expected_primary_evidence_ids"]
    shown = accepted is not None
    outcome = {
        "person_id": person_id,
        "shown": shown,
        "accepted_role": accepted["role"] if accepted else None,
        "model_primary_evidence_id": None,
        "reference_available": None,
        "candidate_present": None,
        "primary_shown": None,
        "model_unsupported_direct": None,
        "unsupported_direct": None,
        "hard_negative": None,
        "model_ask_premise_violation": None,
        "card_ask_premise_violation": None,
        "role_match": None,
    }
    if expected_visible is True:
        outcome["candidate_present"] = person_id in area["candidate_ids"]
        if expected_primary:
            outcome["reference_available"] = any(
                _reference_available(area, sid, person_id, db)
                for sid in expected_primary
            )
            if accepted is None or proposal is None:
                # A rejected person gets no inferred primary; coverage fails.
                outcome["primary_shown"] = False
            else:
                primary = proposal["primary_evidence_id"]
                outcome["model_primary_evidence_id"] = primary
                outcome["primary_shown"] = (
                    primary in expected_primary and primary in accepted["evidence_ids"]
                )
    if expected_visible is False:
        outcome["hard_negative"] = shown
    if case["expected_direct"] is False or expected_visible is False:
        outcome["model_unsupported_direct"] = (
            proposal is not None and proposal["role"] == "direct_contact"
        )
        outcome["unsupported_direct"] = shown and accepted["role"] == "direct_contact"
    model_ask = case["model_ask_premise_supported"]
    if model_ask is not None and proposal is not None:
        outcome["model_ask_premise_violation"] = model_ask is False
    card_ask = case["card_ask_premise_supported"]
    if card_ask is not None and shown:
        outcome["card_ask_premise_violation"] = card_ask is False
    if case["expected_role"] is not None and shown:
        outcome["role_match"] = accepted["role"] == case["expected_role"]
    return outcome


def _adjudicate(area: dict, db) -> dict:
    adjudication = area["adjudication"]
    return {
        "area_need_supported": adjudication["area_need_supported"],
        "cases": [_case_outcome(area, case, db) for case in adjudication["cases"]],
    }


def _stage(area: dict) -> str:
    if area["mapping"] == "mapping_unresolved":
        return "mapping_unresolved"
    if not area["candidate_ids"]:
        return "no_candidates"
    if area["finish_reason"] == "length":
        return "model_truncated"
    if area["error_type"]:
        return "model_failed"
    if not area["model_proposals"]:
        return "model_empty"
    if not area["accepted_people"]:
        return "proposed_but_dropped"
    if len(area["accepted_people"]) < len(area["model_proposals"]):
        return "proposed_partially_accepted"
    return "proposed_accepted"


def _diagnose_area(run: dict, area: dict, db) -> dict:
    accepted_ids = {person["person_id"] for person in area["accepted_people"]}
    invalid = [
        person
        for person in area["model_proposals"]
        if not _safe_question(person["ask"])
    ]
    return {
        "run": f"{run['scenario']}#{run['iteration']}",
        "area": area["id"],
        "status": area["status"],
        "stage": _stage(area),
        "finish_reason": area["finish_reason"],
        "error_type": area["error_type"],
        "candidates": len(area["candidate_ids"]),
        "proposals": len(area["model_proposals"]),
        "accepted": len(area["accepted_people"]),
        "invalid_ask_dropped": sum(
            person["person_id"] not in accepted_ids for person in invalid
        ),
        "adjudication": _adjudicate(area, db),
    }


def _tally_case(totals: dict, case: dict) -> None:
    for field, case_key, hit_key in CASE_METRICS:
        value = case[field]
        if value is None:
            continue
        totals[case_key] += 1
        totals[hit_key] += int(value)


def evaluate_traces(traces: list[dict], db) -> dict:
    validate_traces(traces, db)
    stages: Counter = Counter()
    invalid_ask_total = 0
    areas = []
    access_totals = dict.fromkeys(ACCESS_CHECKS, 0)
    adjudicated = {
        "areas_decided": 0,
        "areas_pending": 0,
        "cases": 0,
        "area_need_cases": 0,
        "area_need_unsupported": 0,
        "reference_cases": 0,
        "reference_available": 0,
        "candidate_cases": 0,
        "candidate_present": 0,
        "primary_cases": 0,
        "primary_shown": 0,
        "model_unsupported_direct_cases": 0,
        "model_unsupported_direct_violations": 0,
        "unsupported_direct_cases": 0,
        "unsupported_direct_violations": 0,
        "hard_negative_cases": 0,
        "hard_negative_violations": 0,
        "model_ask_premise_cases": 0,
        "model_ask_premise_violations": 0,
        "card_ask_premise_cases": 0,
        "card_ask_premise_violations": 0,
        "role_cases": 0,
        "role_matches": 0,
    }
    for run in traces:
        for field, passed in _access_checks(run).items():
            access_totals[field] += int(passed)
        for area in run["areas"]:
            diagnosis = _diagnose_area(run, area, db)
            stages[diagnosis["stage"]] += 1
            invalid_ask_total += diagnosis["invalid_ask_dropped"]
            areas.append(diagnosis)
            adjudication = diagnosis["adjudication"]
            cases = adjudication["cases"]
            adjudicated["cases"] += len(cases)
            if cases or adjudication["area_need_supported"] is not None:
                adjudicated["areas_decided"] += 1
            else:
                adjudicated["areas_pending"] += 1
            if adjudication["area_need_supported"] is not None:
                adjudicated["area_need_cases"] += 1
                adjudicated["area_need_unsupported"] += int(
                    adjudication["area_need_supported"] is False
                )
            for case in cases:
                _tally_case(adjudicated, case)
    return {
        "run_count": len(traces),
        "area_count": len(areas),
        "note": NOTE,
        "metric_definitions": METRIC_DEFINITIONS,
        "access": {"runs_checked": len(traces), **access_totals},
        "stages": {
            "mapping_unresolved_areas": stages["mapping_unresolved"],
            "no_candidate_areas": stages["no_candidates"],
            "model_empty_areas": stages["model_empty"],
            "model_truncated_areas": stages["model_truncated"],
            "model_failed_areas": stages["model_failed"],
            "proposed_but_dropped_areas": stages["proposed_but_dropped"],
            "proposed_partially_accepted_areas": stages["proposed_partially_accepted"],
            "proposed_accepted_areas": stages["proposed_accepted"],
            "invalid_ask_proposals": invalid_ask_total,
        },
        "adjudicated": adjudicated,
        "areas": areas,
    }


def _run_with_seeded_db(
    path: Path, evaluate, db_name: str, labels_path: Path | None = None
) -> dict:
    """Seed a throwaway database, evaluate the fixture, and stamp the source."""
    traces = load_traces(path)
    provenance = None
    if labels_path is not None:
        provenance = attach_labels(traces, labels_path)
    with tempfile.TemporaryDirectory() as directory:
        db = connect(str(Path(directory) / db_name))
        try:
            seed_db(db)
            result = evaluate(traces, db)
        finally:
            db.close()
    result["source"] = str(path)
    if provenance is not None:
        result["label_provenance"] = provenance
    return result


def run(path: Path = TRACES, labels_path: Path = LABELS) -> dict:
    return _run_with_seeded_db(path, evaluate_traces, "traces.sqlite3", labels_path)


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=TRACES)
    parser.add_argument("--labels", type=Path, default=LABELS)
    args = parser.parse_args()
    print(json.dumps(run(args.traces, args.labels), indent=2))


if __name__ == "__main__":
    main()
