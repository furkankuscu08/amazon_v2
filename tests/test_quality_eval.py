import json
from copy import deepcopy

import pytest

from scripts.quality_eval import (
    BASELINE,
    SCENARIOS,
    evaluate,
    run_baseline,
    summarize_scenarios,
)
from workbot.seed import seed_db
from workbot.storage import connect


@pytest.fixture
def snapshot():
    return json.loads(BASELINE.read_text(encoding="utf-8"))


@pytest.fixture
def db(tmp_path):
    connection = connect(str(tmp_path / "quality.sqlite3"))
    seed_db(connection)
    yield connection
    connection.close()


def case_for(result, area, person):
    return next(
        case
        for case in result["cases"]
        if case["area"] == area and case["person"] == person
    )


def test_offline_baseline_replays_visible_decisions_and_user_adjudications():
    result = run_baseline()
    assert result["replay_matches_observed"] is True
    assert result["scenario_summary"] == {
        "total": 3,
        "observed_once": 3,
        "unrun": 0,
        "positive_role_matches": 1,
        "positive_role_cases": 2,
        "hard_negative_violations": 0,
        "hard_negative_cases": 4,
        "no_contact_target_matches": 1,
    }
    assert result["counts"] == {
        "total": 17,
        "labeled_cases": 17,
        "needs_review": 0,
        "positive_references_available": 8,
        "positive_candidates_present": 8,
        "positive_cases": 8,
        "model_role_matches": 10,
        "audited_role_matches": 12,
        "unsupported_direct_model": 6,
        "unsupported_direct_audited": 4,
    }
    assert case_for(result, "platform-1", "nina")["diagnosis"] == (
        "model_error_not_caught"
    )
    assert case_for(result, "growth-1", "elena")["diagnosis"] == ("model_error_caught")
    assert case_for(result, "commerce-1", "nina")["diagnosis"] == (
        "model_error_not_caught"
    )
    assert "secret-duty" not in json.dumps(result)


def test_new_unadjudicated_case_is_displayed_but_not_scored(snapshot, db):
    changed = deepcopy(snapshot)
    changed["cases"][0]["expected_role"] = None
    result = evaluate(changed, db)
    assert result["counts"]["needs_review"] == 1
    assert result["counts"]["labeled_cases"] == 16
    assert case_for(result, "growth-1", "nina")["diagnosis"] == "needs_review"


def test_missing_retrieval_is_not_misdiagnosed_as_a_model_error(snapshot, db):
    changed = deepcopy(snapshot)
    platform = next(a for a in changed["areas"] if a["id"] == "platform-1")
    platform["retrieved_ids"].remove("jira:MKT-482")
    result = evaluate(changed, db)
    case = case_for(result, "platform-1", "nina")
    assert case["reference_available"] is False
    assert case["diagnosis"] == "retrieval_missing"
    assert result["replay_matches_observed"] is False


def test_visible_directory_source_can_still_fail_candidate_selection(snapshot, db):
    changed = deepcopy(snapshot)
    growth = next(a for a in changed["areas"] if a["id"] == "growth-1")
    growth["search_intents"] = [{"keyword": "unrelated", "semantic": "unrelated"}]
    jules = next(
        case
        for case in changed["cases"]
        if case["area_id"] == "growth-1" and case["person_id"] == "jules"
    )
    jules["expected_role"] = "direct_contact"  # Exercise diagnosis, not a gold label.
    case = case_for(evaluate(changed, db), "growth-1", "jules")
    assert case["reference_available"] is True
    assert case["candidate"] is False
    assert case["diagnosis"] == "candidate_missing"


@pytest.mark.parametrize("field", ["retrieved_ids", "reference_evidence_ids"])
def test_hidden_source_cannot_become_a_quality_reference(snapshot, db, field):
    changed = deepcopy(snapshot)
    if field == "retrieved_ids":
        changed["areas"][0][field].append("slack:restricted-plan")
    else:
        changed["cases"][0][field].append("slack:restricted-plan")
    with pytest.raises(ValueError, match="unavailable"):
        evaluate(changed, db)


def test_restricted_only_person_cannot_appear_in_benchmark_output(snapshot, db):
    changed = deepcopy(snapshot)
    changed["cases"][0]["person_id"] = "eve"
    with pytest.raises(ValueError, match="no visible person evidence"):
        evaluate(changed, db)


def test_observed_scenarios_have_visible_sources_and_target_only_comparisons(db):
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    assert summarize_scenarios(scenarios, db)["observed_once"] == 3
    changed = deepcopy(scenarios)
    changed[0]["positive_examples"][0]["evidence_ids"] = ["slack:restricted-plan"]
    with pytest.raises(ValueError, match="unavailable"):
        summarize_scenarios(changed, db)
    changed = deepcopy(scenarios)
    changed[0]["positive_examples"][0]["evidence_ids"] = ["jira:MKT-482"]
    with pytest.raises(ValueError, match="does not link"):
        summarize_scenarios(changed, db)
    changed = deepcopy(scenarios)
    changed[2]["observation"]["target_people"] = [
        {"person_id": "nina", "role": "advisor", "evidence_ids": ["jira:MKT-482"]}
    ]
    changed[2]["observation"]["target_status"] = "people"
    assert summarize_scenarios(changed, db)["hard_negative_violations"] == 1
