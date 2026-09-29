import json
from copy import deepcopy

import pytest

from scripts.trace_audit_replay import replay_traces, run
from scripts.trace_diagnostics import (
    LOW_TRACES,
    RESTRICTED_MARKERS,
    TRACES,
    load_traces,
)
from workbot.seed import seed_db
from workbot.storage import connect


@pytest.fixture
def traces():
    return load_traces(TRACES)


@pytest.fixture
def db(tmp_path):
    connection = connect(str(tmp_path / "audit_replay.sqlite3"))
    seed_db(connection)
    yield connection
    connection.close()


def raw_area(traces, run_key, area_id):
    scenario, iteration = run_key.split("#")
    entry = next(
        run
        for run in traces
        if run["scenario"] == scenario and run["iteration"] == int(iteration)
    )
    return next(area for area in entry["areas"] if area["id"] == area_id)


EXPECTED_TRANSITIONS = {
    ("baseline#1", "security"): ("not_found", "review_incomplete"),
    ("privacy#1", "security_review"): ("not_found", "review_incomplete"),
}


def test_run_reports_counts_without_any_model_call():
    result = run(TRACES)
    assert result["source"] == str(TRACES)
    assert result["no_model_calls"] is True
    assert result["areas_total"] == 32
    assert result["areas_replayed"] == 26


def test_low_run_audit_replay_preserves_all_accepted_people_and_sources():
    result = run(LOW_TRACES)
    assert result["areas_total"] == 16
    assert result["areas_replayed"] == 11
    assert result["candidate_reconstruction"]["exact_order"] == 11
    assert result["areas_skipped"]["truncated"] == 2
    assert result["acceptance"]["areas_changed"] == 0
    assert result["status"]["transitions"] == []
    assert result["ui"]["accepted_people"] == 17
    assert result["safety"]["card_telemetry_fields"] == []


def test_candidate_pool_reconstruction_matches_captured_order(traces, db):
    result = replay_traces(traces, db)
    reconstruction = result["candidate_reconstruction"]
    assert reconstruction["mismatches"] == 0
    assert reconstruction["exact_order"] == result["areas_replayed"]
    assert reconstruction["set_only"] == 0


def test_acceptance_person_role_evidence_is_unchanged(traces, db):
    result = replay_traces(traces, db)
    assert result["acceptance"]["areas_changed"] == 0
    assert result["acceptance"]["changed"] == []
    assert result["acceptance"]["areas_unchanged"] == result["areas_replayed"]


def test_exactly_two_invalid_advisor_areas_become_review_incomplete(traces, db):
    result = replay_traces(traces, db)
    transitions = {
        (entry["run"], entry["area"]): (entry["old"], entry["new"])
        for entry in result["status"]["transitions"]
    }
    assert transitions == EXPECTED_TRANSITIONS
    assert result["status"]["transition_count"] == 2
    assert result["status"]["pairs"] == {"not_found->review_incomplete": 2}


def test_historical_commerce_remains_review_incomplete(traces, db):
    result = replay_traces(traces, db)
    area = result["status"]["by_area"]["historical#1/commerce"]
    assert area["replayed"] is True
    assert area["old_status"] == "review_incomplete"
    assert area["new_status"] == "review_incomplete"


def test_model_empty_privacy2_security_stays_not_found(traces, db):
    result = replay_traces(traces, db)
    area = result["status"]["by_area"]["privacy#2/security_review"]
    assert area["replayed"] is True
    assert area["skip_reason"] is None
    assert area["old_status"] == "not_found"
    assert area["new_status"] == "not_found"


def test_length_and_mapping_areas_are_not_replayed(traces, db):
    result = replay_traces(traces, db)
    by_area = result["status"]["by_area"]
    assert by_area["integration#1/growth-marketing"]["skip_reason"] == "truncated"
    assert by_area["historical#1/platform"]["skip_reason"] == "truncated"
    assert (
        by_area["integration#1/scheduler-requirements"]["skip_reason"]
        == "mapping_unresolved"
    )
    assert result["areas_skipped"] == {
        "mapping_unresolved": 4,
        "no_candidates": 0,
        "truncated": 2,
        "model_failed": 0,
    }


def test_every_mapped_area_carries_captured_search_intents(traces):
    mapped = [
        area
        for entry in traces
        for area in entry["areas"]
        if area["mapping"] == "mapped"
    ]
    assert mapped
    assert all(area["search_intents"] for area in mapped)
    assert all(
        intent["keyword"] and intent["semantic"]
        for area in mapped
        for intent in area["search_intents"]
    )


def test_ui_shows_primary_source_and_neutral_safe_asks(traces, db):
    result = replay_traces(traces, db)
    ui = result["ui"]
    assert ui["accepted_people"] > 0
    assert ui["primary_evidence_id_present"] == ui["accepted_people"]
    assert ui["neutral_safe_ask"] == ui["accepted_people"]
    assert ui["ask_changed_from_original"] == ui["accepted_people"]
    assert ui["why_primary_first"] == ui["accepted_people"]


def test_no_restricted_ids_or_card_telemetry_in_output(traces, db):
    result = replay_traces(traces, db)
    assert result["safety"]["restricted_markers_found"] == []
    assert result["safety"]["restricted_people_found"] == []
    assert result["safety"]["card_telemetry_fields"] == []
    raw = json.dumps(result)
    for marker in RESTRICTED_MARKERS:
        assert marker not in raw


def test_candidate_mismatch_from_retrieval_tampering_is_detected(traces, db):
    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["retrieved_ids"].remove(
        "docs:campaign-review-2023"
    )
    with pytest.raises(ValueError, match="Candidate mismatch"):
        replay_traces(changed, db)


def test_candidate_mismatch_from_captured_id_tampering_is_detected(traces, db):
    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["candidate_ids"].append("marcus")
    with pytest.raises(ValueError, match="Candidate mismatch"):
        replay_traces(changed, db)


def test_missing_or_malformed_search_intents_are_rejected(traces, db):
    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["search_intents"] = []
    with pytest.raises(ValueError, match="search intents"):
        replay_traces(changed, db)

    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["search_intents"][0] = {
        "keyword": "only keyword"
    }
    with pytest.raises(ValueError, match="malformed search intents"):
        replay_traces(changed, db)


def test_restricted_retrieved_record_is_rejected(traces, db):
    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["retrieved_ids"].append(
        "slack:restricted-plan"
    )
    with pytest.raises(ValueError, match="unavailable"):
        replay_traces(changed, db)


def test_schema_invalid_captured_proposal_is_rejected(traces, db):
    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["model_proposals"][0]["role"] = "owner"
    with pytest.raises(ValueError):
        replay_traces(changed, db)
