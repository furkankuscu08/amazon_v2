"""Offline replay of a reviewed synthetic quality snapshot; never calls a model."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from workbot.models import AreaEvaluation
from workbot.search import candidate_pool
from workbot.seed import seed_db
from workbot.service import audit_area
from workbot.storage import connect, current, source, visible_record

BASELINE = Path(__file__).resolve().parents[1] / "tests/fixtures/quality_baseline.json"
SCENARIOS = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/quality_scenarios.json"
)
ROLES = {"direct_contact", "advisor", "routing_contact", "none"}


def _people_with_visible_evidence(db) -> set[str]:
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


def evaluate(snapshot: dict, db) -> dict:
    """Keep pending decisions out of scores; separate retrieval, candidacy and roles."""
    visible_people = _people_with_visible_evidence(db)
    areas = {}
    for area in snapshot["areas"]:
        area_id = area["id"]
        if area_id in areas:
            raise ValueError("Duplicate area in quality snapshot")
        records = [visible_record(db, rid) for rid in area["retrieved_ids"]]
        if any(record is None for record in records):
            raise ValueError("Snapshot contains an unavailable work record")
        if len(set(area["retrieved_ids"])) != len(records):
            raise ValueError("Duplicate retrieved work record")
        pool = candidate_pool(db, area, records)
        if any(p["person_id"] not in visible_people for p in pool["people"]):
            raise ValueError("Candidate has no visible person evidence")
        evaluation = AreaEvaluation.model_validate(
            {
                "people": [
                    {
                        **proposal,
                        "confidence": "medium",
                        "ask": "What did you do on the cited work?",
                        "unverified": "Current ownership is not established.",
                    }
                    for proposal in area["model_proposals"]
                ]
            }
        )
        item = {"people": [], "status": "not_found", "direct_review_incomplete": False}
        audit_area(db, item, pool, evaluation)
        audited = {p["person_id"]: p["role"] for p in item["people"]}
        observed = sorted(area["observed_people"])
        replayed = sorted(f"{pid}:{role}" for pid, role in audited.items())
        areas[area_id] = {
            "candidate_ids": {p["person_id"] for p in pool["people"]},
            "proposed": {p.person_id: p.role for p in evaluation.people},
            "audited": audited,
            "retrieved_ids": set(area["retrieved_ids"]),
            "observed_matches_replay": observed == replayed
            and area["observed_status"] == item["status"],
        }

    cases = []
    seen = set()
    for case in snapshot["cases"]:
        area_id, person_id = case["area_id"], case["person_id"]
        if area_id not in areas or (area_id, person_id) in seen:
            raise ValueError("Unknown area or duplicate person in quality cases")
        if person_id not in visible_people:
            raise ValueError("Quality case has no visible person evidence")
        seen.add((area_id, person_id))
        expected = case["expected_role"]
        if expected is not None and expected not in ROLES:
            raise ValueError("Unknown quality role")
        refs = case.get("reference_evidence_ids", [])
        if any(source(db, sid) is None for sid in refs):
            raise ValueError("Quality reference cites an unavailable source")
        area = areas[area_id]
        found = (
            all(
                sid.startswith("directory:") or sid in area["retrieved_ids"]
                for sid in refs
            )
            if refs
            else None
        )
        model_role = area["proposed"].get(person_id, "none")
        audit_role = area["audited"].get(person_id, "none")
        if expected is None:
            diagnosis = "needs_review"
        elif expected != "none" and not found:
            diagnosis = "retrieval_missing"
        elif expected != "none" and person_id not in area["candidate_ids"]:
            diagnosis = "candidate_missing"
        elif model_role != expected and audit_role == expected:
            diagnosis = "model_error_caught"
        elif model_role != expected:
            diagnosis = "model_error_not_caught"
        elif audit_role != expected:
            diagnosis = "audit_changed_correct_role"
        else:
            diagnosis = "matched"
        cases.append(
            {
                "area": area_id,
                "person": person_id,
                "expected": expected,
                "reference_available": found,
                "candidate": person_id in area["candidate_ids"],
                "model": model_role,
                "audit": audit_role,
                "diagnosis": diagnosis,
            }
        )

    decided = [case for case in cases if case["expected"] is not None]
    positive = [case for case in decided if case["expected"] != "none"]
    return {
        "provenance": snapshot["provenance"],
        "area_count": len(areas),
        "replay_matches_observed": all(
            area["observed_matches_replay"] for area in areas.values()
        ),
        "counts": {
            "total": len(cases),
            "labeled_cases": len(decided),
            "needs_review": len(cases) - len(decided),
            "positive_references_available": sum(
                case["reference_available"] for case in positive
            ),
            "positive_candidates_present": sum(case["candidate"] for case in positive),
            "positive_cases": len(positive),
            "model_role_matches": sum(
                case["model"] == case["expected"] for case in decided
            ),
            "audited_role_matches": sum(
                case["audit"] == case["expected"] for case in decided
            ),
            "unsupported_direct_model": sum(
                case["model"] == "direct_contact"
                and case["expected"] != "direct_contact"
                for case in decided
            ),
            "unsupported_direct_audited": sum(
                case["audit"] == "direct_contact"
                and case["expected"] != "direct_contact"
                for case in decided
            ),
        },
        "cases": cases,
    }


def summarize_scenarios(scenarios: list[dict], db) -> dict:
    """Check curated references and compare only observed target-area roles."""
    visible_people = _people_with_visible_evidence(db)
    orgs = {row["id"] for row in db.execute("SELECT id FROM org_units")}
    seen = set()
    summary = {
        "total": len(scenarios),
        "observed_once": 0,
        "unrun": 0,
        "positive_role_matches": 0,
        "positive_role_cases": 0,
        "hard_negative_violations": 0,
        "hard_negative_cases": 0,
        "no_contact_target_matches": 0,
    }
    for scenario in scenarios:
        if (
            scenario["id"] in seen
            or scenario["status"] not in {"draft_not_run", "observed_once"}
            or scenario["consultation_org"] not in orgs
            or not scenario["idea"].strip()
        ):
            raise ValueError("Invalid draft quality scenario")
        seen.add(scenario["id"])
        for example in [
            *scenario["positive_examples"],
            *scenario["hard_negatives"],
        ]:
            if (
                example["person_id"] not in visible_people
                or not example["evidence_ids"]
            ):
                raise ValueError("Draft example has no visible person evidence")
            if "role" in example and example["role"] not in ROLES - {"none"}:
                raise ValueError("Invalid positive role in draft example")
            for sid in example["evidence_ids"]:
                if not source(db, sid):
                    raise ValueError("Draft example cites an unavailable source")
                linked = db.execute(
                    "SELECT 1 FROM work_links WHERE record_id=? AND person_id=?",
                    (sid, example["person_id"]),
                ).fetchone()
                if not linked:
                    raise ValueError("Draft example source does not link to person")
        if scenario["status"] == "draft_not_run":
            summary["unrun"] += 1
            continue
        summary["observed_once"] += 1
        observation = scenario["observation"]
        if any(
            visible_record(db, rid) is None
            for rid in observation["target_retrieved_ids"]
        ):
            raise ValueError("Observed target retrieval includes an unavailable source")
        if (
            observation["restricted_source_status"] != 404
            or observation["reload_same_html"] is not True
            or observation["peak_parallel_areas"] > 2
        ):
            raise ValueError("Observed run fails access or concurrency checks")
        if (observation["target_status"] == "people") != bool(
            observation["target_people"]
        ):
            raise ValueError("Observed target status disagrees with contacts")
        observed = {}
        for person in observation["target_people"]:
            pid = person["person_id"]
            if (
                pid in observed
                or pid not in visible_people
                or person["role"] not in ROLES - {"none"}
            ):
                raise ValueError("Invalid observed target contact")
            if not person["evidence_ids"] or any(
                source(db, sid) is None for sid in person["evidence_ids"]
            ):
                raise ValueError("Observed target cites an unavailable source")
            if any(
                sid not in observation["target_retrieved_ids"]
                or not db.execute(
                    "SELECT 1 FROM work_links WHERE record_id=? AND person_id=?",
                    (sid, pid),
                ).fetchone()
                for sid in person["evidence_ids"]
            ):
                raise ValueError(
                    "Observed target citation lacks a retrieved person link"
                )
            observed[pid] = person["role"]
        for example in scenario["positive_examples"]:
            summary["positive_role_cases"] += 1
            summary["positive_role_matches"] += (
                observed.get(example["person_id"]) == example["role"]
            )
        for example in scenario["hard_negatives"]:
            summary["hard_negative_cases"] += 1
            summary["hard_negative_violations"] += example["person_id"] in observed
        if not scenario["positive_examples"]:
            summary["no_contact_target_matches"] += (
                observation["target_status"] == "not_found" and not observed
            )
    return summary


def run_baseline(path: Path = BASELINE) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        db = connect(str(Path(directory) / "quality.sqlite3"))
        try:
            seed_db(db)
            result = evaluate(snapshot, db)
            result["scenario_summary"] = summarize_scenarios(scenarios, db)
            return result
        finally:
            db.close()


if __name__ == "__main__":
    print(json.dumps(run_baseline(), indent=2))
