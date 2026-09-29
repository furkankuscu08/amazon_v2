import json
from copy import deepcopy

import pytest

from scripts.trace_diagnostics import (
    LABELS,
    LOW_LABELS,
    LOW_TRACES,
    RESTRICTED_MARKERS,
    TRACES,
    attach_labels,
    evaluate_traces,
    load_traces,
    run,
    validate_traces,
)
from workbot.seed import seed_db
from workbot.storage import connect

EXPECTED_STAGES = {
    "mapping_unresolved_areas": 4,
    "no_candidate_areas": 0,
    "model_empty_areas": 2,
    "model_truncated_areas": 2,
    "model_failed_areas": 0,
    "proposed_but_dropped_areas": 3,
    "proposed_partially_accepted_areas": 3,
    "proposed_accepted_areas": 18,
    "invalid_ask_proposals": 6,
}


@pytest.fixture
def traces():
    return load_traces(TRACES)


@pytest.fixture
def db(tmp_path):
    connection = connect(str(tmp_path / "traces.sqlite3"))
    seed_db(connection)
    yield connection
    connection.close()


def area_of(result, run_key, area_id):
    return next(
        item
        for item in result["areas"]
        if item["run"] == run_key and item["area"] == area_id
    )


def raw_area(traces, run_key, area_id):
    scenario, iteration = run_key.split("#")
    entry = next(
        item
        for item in traces
        if item["scenario"] == scenario and item["iteration"] == int(iteration)
    )
    return next(area for area in entry["areas"] if area["id"] == area_id)


def add_case(traces, run_key, area_id, person_id, **overrides):
    case = {
        "person_id": person_id,
        "expected_visible": None,
        "expected_direct": None,
        "expected_role": None,
        "expected_primary_evidence_ids": [],
        "model_ask_premise_supported": None,
        "card_ask_premise_supported": None,
    }
    case.update(overrides)
    raw_area(traces, run_key, area_id)["adjudication"]["cases"].append(case)
    return case


def cases_by_person(result, run_key, area_id):
    cases = area_of(result, run_key, area_id)["adjudication"]["cases"]
    return {case["person_id"]: case for case in cases}


def test_fixture_covers_six_runs_and_explicit_stage_counts(traces, db):
    result = evaluate_traces(traces, db)
    assert result["run_count"] == 6
    assert result["area_count"] == 32
    assert result["stages"] == EXPECTED_STAGES
    assert result["note"].startswith("These are counts")
    assert "accuracy" not in json.dumps(result["metric_definitions"]).lower()


def test_run_seeds_a_database_and_checks_every_access_invariant():
    result = run(TRACES)
    assert result["run_count"] == 6
    assert result["label_provenance"]["reviewer"] == "assistant"
    assert result["source"] == str(TRACES)
    assert result["access"]["runs_checked"] == 6
    for field, count in result["access"].items():
        if field != "runs_checked":
            assert count == 6


def test_two_length_truncations_are_distinct_from_model_empty(traces, db):
    result = evaluate_traces(traces, db)
    truncated = sorted(
        (item["run"], item["area"])
        for item in result["areas"]
        if item["stage"] == "model_truncated"
    )
    assert truncated == [
        ("historical#1", "platform"),
        ("integration#1", "growth-marketing"),
    ]
    for run_key, area_id in truncated:
        item = area_of(result, run_key, area_id)
        assert item["finish_reason"] == "length"
        assert item["error_type"] == "ModelError"
        assert item["proposals"] == 0
        assert item["candidates"] > 0
    empty = sorted(
        (item["run"], item["area"])
        for item in result["areas"]
        if item["stage"] == "model_empty"
    )
    assert empty == [("historical#1", "finance"), ("privacy#2", "security_review")]


def test_baseline_security_invalid_asks_versus_valid_proposal(traces, db):
    result = evaluate_traces(traces, db)
    dropped = area_of(result, "baseline#1", "security")
    assert dropped["stage"] == "proposed_but_dropped"
    assert dropped["invalid_ask_dropped"] == 2
    assert dropped["accepted"] == 0
    proposals = raw_area(traces, "baseline#1", "security")["model_proposals"]
    assert sorted(proposal["ask"] for proposal in proposals) == [
        "Elena Park",
        "Nina Ellis",
    ]

    valid = area_of(result, "baseline#2", "security")
    assert valid["stage"] == "proposed_accepted"
    assert valid["invalid_ask_dropped"] == 0
    assert valid["accepted"] == 1
    accepted = raw_area(traces, "baseline#2", "security")["accepted_people"]
    assert [(person["person_id"], person["role"]) for person in accepted] == [
        ("nina", "advisor")
    ]


def test_privacy_security_invalid_asks_versus_truly_empty(traces, db):
    result = evaluate_traces(traces, db)
    dropped = area_of(result, "privacy#1", "security_review")
    assert dropped["stage"] == "proposed_but_dropped"
    assert dropped["invalid_ask_dropped"] == 3
    assert all(
        not proposal["ask"].endswith("?")
        for proposal in raw_area(traces, "privacy#1", "security_review")[
            "model_proposals"
        ]
    )

    empty = area_of(result, "privacy#2", "security_review")
    assert empty["stage"] == "model_empty"
    assert empty["proposals"] == 0
    assert empty["invalid_ask_dropped"] == 0
    assert empty["candidates"] > 0
    assert empty["finish_reason"] == "stop"


def test_historical_commerce_keeps_the_interview_question_drop(traces, db):
    result = evaluate_traces(traces, db)
    item = area_of(result, "historical#1", "commerce")
    assert item["stage"] == "proposed_but_dropped"
    assert item["invalid_ask_dropped"] == 1
    raw = raw_area(traces, "historical#1", "commerce")
    assert raw["status"] == "review_incomplete"
    assert raw["model_proposals"][0]["ask"] == "Interview question"


def test_frozen_observations_remain_pending_without_separate_labels(traces, db):
    result = evaluate_traces(traces, db)
    adjudicated = result["adjudicated"]
    assert adjudicated["areas_decided"] == 0
    assert adjudicated["areas_pending"] == result["area_count"]
    assert adjudicated["cases"] == 0
    assert all(area["adjudication"]["cases"] == [] for area in result["areas"])
    assert all(
        area["adjudication"]["area_need_supported"] is None for area in result["areas"]
    )
    for key in (
        "area_need_cases",
        "reference_cases",
        "candidate_cases",
        "primary_cases",
        "unsupported_direct_cases",
        "hard_negative_cases",
        "model_ask_premise_cases",
        "card_ask_premise_cases",
        "role_cases",
    ):
        assert adjudicated[key] == 0


def test_assistant_labels_keep_ambiguous_contacts_unscored(traces, db):
    attach_labels(traces)
    assert (
        sum(
            case["expected_visible"] is None
            for run in traces
            for area in run["areas"]
            for case in area["adjudication"]["cases"]
        )
        == 3
    )
    result = evaluate_traces(traces, db)
    counts = result["adjudicated"]
    assert counts["areas_decided"] == 32
    assert counts["cases"] == 49
    assert counts["area_need_cases"] == 31
    assert counts["area_need_unsupported"] == 0
    assert counts["reference_cases"] == 43
    assert counts["reference_available"] == 43
    assert counts["primary_shown"] == 33
    assert counts["model_unsupported_direct_violations"] == 13
    assert counts["unsupported_direct_violations"] == 9
    assert counts["hard_negative_cases"] == 3
    assert counts["hard_negative_violations"] == 1
    assert counts["model_ask_premise_cases"] == 40
    assert counts["model_ask_premise_violations"] == 21
    assert counts["card_ask_premise_cases"] == 33
    assert counts["card_ask_premise_violations"] == 15
    undecided = cases_by_person(result, "privacy#2", "campaign_platform")["owen"]
    assert undecided["candidate_present"] is None
    assert undecided["primary_shown"] is None
    assert undecided["role_match"] is None
    assert undecided["model_ask_premise_violation"] is True
    assert undecided["card_ask_premise_violation"] is True
    assert (
        cases_by_person(result, "historical#1", "brand")["priya"]["unsupported_direct"]
        is True
    )
    useful = cases_by_person(result, "privacy#1", "commerce_operations")["nina"]
    assert useful["primary_shown"] is True
    assert useful["hard_negative"] is None
    assert useful["unsupported_direct"] is True
    assert useful["model_ask_premise_violation"] is True
    assert useful["card_ask_premise_violation"] is True
    assert (
        area_of(result, "baseline#1", "finance")["adjudication"]["area_need_supported"]
        is None
    )
    assert (
        area_of(result, "historical#1", "finance")["adjudication"][
            "area_need_supported"
        ]
        is True
    )


def test_label_file_cannot_silently_omit_or_add_an_area(traces, tmp_path):
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    labels["areas"].pop("privacy#2/security_review")
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(labels), encoding="utf-8")
    with pytest.raises(ValueError, match="cover each captured area"):
        attach_labels(traces, path)


@pytest.mark.parametrize(
    ("traces_path", "labels_path"), [(TRACES, LABELS), (LOW_TRACES, LOW_LABELS)]
)
def test_label_overlay_changes_only_adjudication(traces_path, labels_path, db):
    observations = load_traces(traces_path)
    before = deepcopy(observations)
    before_result = evaluate_traces(before, db)
    attach_labels(observations, labels_path)
    after_result = evaluate_traces(observations, db)
    for original_run, labeled_run in zip(before, observations, strict=True):
        for original_area, labeled_area in zip(
            original_run["areas"], labeled_run["areas"], strict=True
        ):
            original_area["adjudication"] = labeled_area["adjudication"]
    assert observations == before
    assert after_result["stages"] == before_result["stages"]
    assert after_result["access"] == before_result["access"]
    assert load_traces(traces_path) != observations


def test_low_reasoning_runs_keep_new_needs_and_separate_question_scores():
    low_runs = load_traces(LOW_TRACES)
    assert [entry["scenario"] for entry in low_runs] == [
        "integration",
        "historical",
        "privacy",
    ]
    assert all(entry["provider"] == "Together" for entry in low_runs)
    assert all(entry["requested_reasoning_effort"] == "low" for entry in low_runs)
    assert [entry["elapsed_seconds"] for entry in low_runs] == [
        51.85,
        65.856,
        64.824,
    ]
    assert (
        sum(entry["transport"]["usage_totals"]["total_tokens"] for entry in low_runs)
        == 93138
    )
    assert sum(
        entry["transport"]["reported_cost_usd"] for entry in low_runs
    ) == pytest.approx(0.08855142)
    result = run(LOW_TRACES, LOW_LABELS)
    assert result["label_provenance"]["reviewer"] == "assistant"
    assert "low-reasoning" in result["label_provenance"]["status"]
    counts = result["adjudicated"]
    assert result["run_count"] == 3
    assert result["area_count"] == 16
    assert result["stages"]["model_truncated_areas"] == 2
    assert result["stages"]["invalid_ask_proposals"] == 0
    assert result["access"]["runs_checked"] == 3
    assert all(value == 3 for value in result["access"].values())
    assert counts["areas_pending"] == 0
    assert counts["cases"] == 20
    assert counts["area_need_cases"] == 14
    assert counts["area_need_unsupported"] == 0
    assert counts["reference_available"] == 16
    assert counts["primary_shown"] == 16
    assert counts["model_unsupported_direct_violations"] == 2
    assert counts["unsupported_direct_violations"] == 2
    assert counts["hard_negative_cases"] == 2
    assert counts["hard_negative_violations"] == 0
    assert counts["model_ask_premise_cases"] == 14
    assert counts["model_ask_premise_violations"] == 8
    assert counts["card_ask_premise_violations"] == 0
    assert counts["card_ask_premise_cases"] == 17
    assert counts["role_cases"] == 16
    assert counts["role_matches"] == 14
    assert area_of(result, "privacy#1", "security_review")["accepted"] == 2
    assert area_of(result, "historical#1", "commerce")["accepted"] == 2


def test_revised_advisor_labels_keep_security_premise_and_commerce_role_failures():
    result = run(LOW_TRACES, LOW_LABELS)
    brand = area_of(result, "historical#1", "brand")["adjudication"]
    assert brand["area_need_supported"] is None
    priya = cases_by_person(result, "historical#1", "brand")["priya"]
    assert priya["role_match"] is True
    assert priya["model_ask_premise_violation"] is False
    security = cases_by_person(result, "privacy#1", "security_review")
    assert security["elena"]["role_match"] is True
    assert security["elena"]["model_ask_premise_violation"] is False
    assert security["nina"]["role_match"] is True
    assert security["nina"]["model_ask_premise_violation"] is True
    assert security["nina"]["card_ask_premise_violation"] is False
    for area_id in ("security_review", "campaign_platform"):
        pending = cases_by_person(result, "privacy#1", area_id)["owen"]
        assert pending["primary_shown"] is None
        assert pending["role_match"] is None
    for run_key, area_id in (
        ("historical#1", "commerce"),
        ("privacy#1", "commerce_operations"),
    ):
        useful = cases_by_person(result, run_key, area_id)["nina"]
        assert useful["primary_shown"] is True
        assert useful["hard_negative"] is None
        assert useful["model_unsupported_direct"] is True
        assert useful["unsupported_direct"] is True
        assert useful["model_ask_premise_violation"] is True
        assert useful["card_ask_premise_violation"] is False


def test_advisor_relabel_does_not_rescue_malformed_questions_or_manager_advisor():
    result = run()
    for person_id in ("nina", "elena"):
        dropped = cases_by_person(result, "baseline#1", "security")[person_id]
        assert dropped["reference_available"] is True
        assert dropped["candidate_present"] is True
        assert dropped["shown"] is False
        assert dropped["primary_shown"] is False
        assert dropped["model_ask_premise_violation"] is None
    assert area_of(result, "baseline#1", "security")["invalid_ask_dropped"] == 2
    routing = cases_by_person(result, "baseline#2", "growth")["marcus"]
    assert routing["reference_available"] is True
    assert routing["shown"] is False
    assert routing["model_ask_premise_violation"] is True
    assert routing["role_match"] is None


def test_reviewed_on_date_and_method_identify_relabel_not_a_new_capture():
    for path in (LABELS, LOW_LABELS):
        provenance = json.loads(path.read_text(encoding="utf-8"))["provenance"]
        assert provenance["reviewed_on"] == "2026-09-30"
        assert provenance["previous_reviewed_on"] == "2026-09-27"
        assert "user-approved advisor rubric" in provenance["status"]
        assert "without seeing prior labels" in provenance["review_method"]
        assert "not independent human validation" in provenance["review_method"]


def test_reference_availability_and_candidacy_when_adjudicated(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "brand",
        "priya",
        expected_visible=True,
        expected_primary_evidence_ids=["docs:campaign-review-2023"],
    )
    result = evaluate_traces(changed, db)
    case = cases_by_person(result, "baseline#1", "brand")["priya"]
    assert case["reference_available"] is True
    assert case["candidate_present"] is True
    assert result["adjudicated"]["reference_cases"] == 1
    assert result["adjudicated"]["reference_available"] == 1
    assert result["adjudicated"]["candidate_cases"] == 1
    assert result["adjudicated"]["candidate_present"] == 1
    assert result["adjudicated"]["areas_decided"] == 1
    assert result["adjudicated"]["areas_pending"] == 31

    # A positive reference that was not retrieved for the area.
    missing = deepcopy(traces)
    add_case(
        missing,
        "baseline#1",
        "brand",
        "priya",
        expected_visible=True,
        expected_primary_evidence_ids=["docs:campaign-review-2023"],
    )
    raw_area(missing, "baseline#1", "brand")["retrieved_ids"].remove(
        "docs:campaign-review-2023"
    )
    case = cases_by_person(evaluate_traces(missing, db), "baseline#1", "brand")["priya"]
    assert case["reference_available"] is False

    # A positive person who is visible but not in this area's candidate pool.
    non_candidate = deepcopy(traces)
    add_case(
        non_candidate,
        "baseline#1",
        "brand",
        "marcus",
        expected_visible=True,
        expected_primary_evidence_ids=["directory:growth-manager"],
    )
    case = cases_by_person(evaluate_traces(non_candidate, db), "baseline#1", "brand")[
        "marcus"
    ]
    assert case["reference_available"] is True
    assert case["candidate_present"] is False


def test_current_manager_can_cite_visible_team_remit_only_for_that_team(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "growth",
        "marcus",
        expected_visible=True,
        expected_primary_evidence_ids=["directory:growth-remit"],
    )
    case = cases_by_person(evaluate_traces(changed, db), "baseline#1", "growth")[
        "marcus"
    ]
    assert case["reference_available"] is True

    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "growth",
        "nina",
        expected_primary_evidence_ids=["directory:growth-remit"],
    )
    with pytest.raises(ValueError, match="does not belong"):
        validate_traces(changed, db)


def test_alternative_primary_references_need_only_one_retrieved_source(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "growth",
        "nina",
        expected_visible=True,
        expected_primary_evidence_ids=[
            "jira:MKT-482",
            "slack:retail-814",
        ],
    )
    raw_area(changed, "baseline#1", "growth")["retrieved_ids"].remove(
        "slack:retail-814"
    )
    # The second acceptable source need not be retrieved if the first is.
    case = cases_by_person(evaluate_traces(changed, db), "baseline#1", "growth")["nina"]
    assert case["reference_available"] is True


def test_primary_metric_ignores_role_and_requires_the_primary_source(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "commerce",
        "nina",
        expected_visible=True,
        expected_direct=False,
        expected_role="advisor",
        expected_primary_evidence_ids=["jira:MKT-482"],
    )
    result = evaluate_traces(changed, db)
    case = cases_by_person(result, "baseline#1", "commerce")["nina"]
    assert case["model_primary_evidence_id"] == "jira:MKT-482"
    assert case["primary_shown"] is True
    assert case["role_match"] is False
    assert case["model_unsupported_direct"] is True
    assert case["unsupported_direct"] is True
    assert result["adjudicated"]["primary_cases"] == 1
    assert result["adjudicated"]["primary_shown"] == 1
    assert result["adjudicated"]["role_cases"] == 1
    assert result["adjudicated"]["role_matches"] == 0
    assert result["adjudicated"]["unsupported_direct_violations"] == 1
    assert result["adjudicated"]["model_unsupported_direct_violations"] == 1

    # A secondary-only citation does not satisfy the primary metric.
    secondary = deepcopy(traces)
    accepted = raw_area(secondary, "baseline#1", "commerce")["accepted_people"]
    next(p for p in accepted if p["person_id"] == "nina")["evidence_ids"] = [
        "slack:retail-814"
    ]
    add_case(
        secondary,
        "baseline#1",
        "commerce",
        "nina",
        expected_visible=True,
        expected_primary_evidence_ids=["jira:MKT-482"],
    )
    case = cases_by_person(evaluate_traces(secondary, db), "baseline#1", "commerce")[
        "nina"
    ]
    assert case["model_primary_evidence_id"] == "jira:MKT-482"
    assert case["primary_shown"] is False


def test_rejected_person_does_not_get_an_inferred_primary(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "growth",
        "elena",
        expected_visible=True,
        expected_primary_evidence_ids=["jira:MKT-482"],
    )
    result = evaluate_traces(changed, db)
    case = cases_by_person(result, "baseline#1", "growth")["elena"]
    assert case["shown"] is False
    assert case["candidate_present"] is True
    assert case["reference_available"] is True
    assert case["model_primary_evidence_id"] is None
    assert case["primary_shown"] is False
    assert result["adjudicated"]["primary_cases"] == 1
    assert result["adjudicated"]["primary_shown"] == 0


def test_model_ask_false_but_card_ask_true_in_one_case(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "commerce",
        "nina",
        expected_visible=True,
        model_ask_premise_supported=False,
        card_ask_premise_supported=True,
    )
    result = evaluate_traces(changed, db)
    case = cases_by_person(result, "baseline#1", "commerce")["nina"]
    assert case["shown"] is True
    assert case["model_ask_premise_violation"] is True
    assert case["card_ask_premise_violation"] is False
    assert result["adjudicated"]["model_ask_premise_cases"] == 1
    assert result["adjudicated"]["model_ask_premise_violations"] == 1
    assert result["adjudicated"]["card_ask_premise_cases"] == 1
    assert result["adjudicated"]["card_ask_premise_violations"] == 0


@pytest.mark.parametrize("expected_visible", [True, None])
def test_advisor_usefulness_or_uncertainty_does_not_erase_other_failures(
    db, expected_visible
):
    observations = load_traces(LOW_TRACES)
    add_case(
        observations,
        "privacy#1",
        "commerce_operations",
        "nina",
        expected_visible=expected_visible,
        expected_direct=False,
        expected_role="advisor" if expected_visible else None,
        expected_primary_evidence_ids=["jira:MKT-482"] if expected_visible else [],
        model_ask_premise_supported=False,
        card_ask_premise_supported=True,
    )
    result = evaluate_traces(observations, db)
    case = cases_by_person(result, "privacy#1", "commerce_operations")["nina"]
    assert case["shown"] is True
    assert case["hard_negative"] is None
    assert case["model_unsupported_direct"] is True
    assert case["unsupported_direct"] is True
    assert case["model_ask_premise_violation"] is True
    assert case["card_ask_premise_violation"] is False
    assert case["primary_shown"] is (True if expected_visible else None)
    assert case["role_match"] is (False if expected_visible else None)
    counts = result["adjudicated"]
    assert counts["hard_negative_cases"] == 0
    assert counts["candidate_cases"] == int(expected_visible is True)
    assert counts["primary_cases"] == int(expected_visible is True)
    assert counts["role_cases"] == int(expected_visible is True)
    assert counts["model_unsupported_direct_violations"] == 1
    assert counts["unsupported_direct_violations"] == 1
    assert counts["model_ask_premise_violations"] == 1
    assert counts["card_ask_premise_cases"] == 1


def test_unshown_proposal_scores_model_ask_but_not_card_ask(traces, db):
    changed = deepcopy(traces)
    # elena is proposed in baseline#1 growth but dropped by the audit.
    add_case(
        changed,
        "baseline#1",
        "growth",
        "elena",
        model_ask_premise_supported=False,
        card_ask_premise_supported=False,
    )
    result = evaluate_traces(changed, db)
    case = cases_by_person(result, "baseline#1", "growth")["elena"]
    assert case["shown"] is False
    assert case["model_ask_premise_violation"] is True
    assert case["card_ask_premise_violation"] is None
    assert result["adjudicated"]["model_ask_premise_cases"] == 1
    assert result["adjudicated"]["model_ask_premise_violations"] == 1
    assert result["adjudicated"]["card_ask_premise_cases"] == 0
    assert result["adjudicated"]["card_ask_premise_violations"] == 0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"expected_visible": False, "expected_role": "advisor"},
            "absent person as advisor",
        ),
        (
            {"expected_visible": False, "expected_role": "direct_contact"},
            "absent person as direct_contact",
        ),
        (
            {"expected_visible": False, "expected_direct": True},
            "absent person as direct",
        ),
        (
            {
                "expected_visible": False,
                "expected_primary_evidence_ids": ["jira:MKT-482"],
            },
            "absent person with expected primary evidence",
        ),
        (
            {"expected_visible": True, "expected_role": "none"},
            "positive person as none",
        ),
        (
            {
                "expected_visible": True,
                "expected_direct": False,
                "expected_role": "direct_contact",
            },
            "not direct but expects direct_contact",
        ),
        (
            {"expected_direct": True, "expected_role": "advisor"},
            "direct as acceptable while expecting advisor",
        ),
        (
            {"expected_direct": True, "expected_role": "none"},
            "direct as acceptable while expecting none",
        ),
    ],
)
def test_contradictory_case_labels_are_rejected(traces, db, overrides, message):
    changed = deepcopy(traces)
    add_case(changed, "baseline#1", "commerce", "nina", **overrides)
    with pytest.raises(ValueError, match=message):
        validate_traces(changed, db)


def test_unsupported_direct_covers_shown_and_none_labels(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "growth",
        "nina",
        expected_visible=True,
        expected_direct=False,
    )
    add_case(
        changed,
        "baseline#1",
        "growth",
        "elena",
        expected_visible=True,
        expected_direct=False,
    )
    result = evaluate_traces(changed, db)
    cases = cases_by_person(result, "baseline#1", "growth")
    assert cases["nina"]["unsupported_direct"] is True
    assert cases["elena"]["unsupported_direct"] is False
    assert cases["nina"]["model_unsupported_direct"] is True
    assert result["adjudicated"]["unsupported_direct_cases"] == 2
    assert result["adjudicated"]["unsupported_direct_violations"] == 1


def test_model_direct_claim_can_fail_even_when_audit_drops_person(traces, db):
    changed = deepcopy(traces)
    add_case(
        changed,
        "historical#1",
        "commerce",
        "nina",
        expected_direct=False,
    )
    case = cases_by_person(evaluate_traces(changed, db), "historical#1", "commerce")[
        "nina"
    ]
    assert case["shown"] is False
    assert case["model_unsupported_direct"] is True
    assert case["unsupported_direct"] is False


def test_hard_negative_person_expected_false(traces, db):
    changed = deepcopy(traces)
    add_case(changed, "baseline#1", "brand", "nina", expected_visible=False)
    add_case(changed, "baseline#1", "brand", "tara", expected_visible=False)
    result = evaluate_traces(changed, db)
    cases = cases_by_person(result, "baseline#1", "brand")
    assert cases["nina"]["hard_negative"] is True
    assert cases["tara"]["hard_negative"] is False
    assert cases["nina"]["unsupported_direct"] is False
    assert result["adjudicated"]["hard_negative_cases"] == 2
    assert result["adjudicated"]["hard_negative_violations"] == 1
    assert result["adjudicated"]["unsupported_direct_cases"] == 2
    assert result["adjudicated"]["unsupported_direct_violations"] == 0


def test_area_need_decision_is_counted_separately(traces, db):
    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "security")["adjudication"][
        "area_need_supported"
    ] = False
    result = evaluate_traces(changed, db)
    assert result["adjudicated"]["area_need_cases"] == 1
    assert result["adjudicated"]["area_need_unsupported"] == 1
    assert result["adjudicated"]["areas_decided"] == 1
    assert result["adjudicated"]["areas_pending"] == 31


def test_restricted_only_person_or_source_injection_is_rejected(traces, db):
    changed = deepcopy(traces)
    add_case(changed, "baseline#1", "security", "eve", expected_visible=True)
    with pytest.raises(ValueError, match="without visible evidence"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "security",
        "nina",
        expected_visible=True,
        expected_primary_evidence_ids=["slack:restricted-plan"],
    )
    with pytest.raises(ValueError, match="unavailable source"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "security",
        "nina",
        expected_visible=True,
        expected_primary_evidence_ids=["directory:secret-duty"],
    )
    with pytest.raises(ValueError, match="unavailable source"):
        validate_traces(changed, db)

    # A visible source that is not linked to the person is rejected.
    changed = deepcopy(traces)
    add_case(
        changed,
        "baseline#1",
        "security",
        "nina",
        expected_visible=True,
        expected_primary_evidence_ids=["docs:campaign-review-2023"],
    )
    with pytest.raises(ValueError, match="does not belong"):
        validate_traces(changed, db)

    # Accepted card evidence must link to its person.
    changed = deepcopy(traces)
    accepted = raw_area(changed, "baseline#1", "commerce")["accepted_people"]
    next(p for p in accepted if p["person_id"] == "nina")["evidence_ids"] = [
        "jira:MKT-483"
    ]
    with pytest.raises(ValueError, match="not linked to them"):
        validate_traces(changed, db)


def test_duplicate_and_malformed_fixture_ids_are_rejected(traces, db):
    changed = deepcopy(traces)
    changed.append(deepcopy(changed[0]))
    with pytest.raises(ValueError, match="Duplicate run"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    duplicate = deepcopy(raw_area(changed, "baseline#1", "brand"))
    changed[0]["areas"].append(duplicate)
    with pytest.raises(ValueError, match="Duplicate area id"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    raw_area(changed, "baseline#1", "brand")["id"] = "Bad Id"
    with pytest.raises(ValueError, match="Malformed area id"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    proposal = raw_area(changed, "baseline#1", "brand")["model_proposals"][0]
    proposal["primary_evidence_id"] = "jira:MKT-483"
    with pytest.raises(ValueError, match="primary is not cited"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    proposal = raw_area(changed, "baseline#1", "brand")["model_proposals"][0]
    proposal["role"] = "owner"
    with pytest.raises(ValueError, match="Unknown proposal role"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    add_case(changed, "baseline#1", "brand", "nina", expected_visible=True)
    add_case(changed, "baseline#1", "brand", "nina", expected_visible=False)
    with pytest.raises(ValueError, match="duplicate case person"):
        validate_traces(changed, db)

    changed = deepcopy(traces)
    case = add_case(changed, "baseline#1", "brand", "nina", expected_visible=True)
    case["expected_visible"] = "yes"
    with pytest.raises(ValueError, match="malformed expected visibility"):
        validate_traces(changed, db)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("restricted_source_status", 200, "Restricted source did not return 404"),
        (
            "restricted_directory_status",
            200,
            "Restricted directory source did not return 404",
        ),
        ("visible_leak_marker", True, "restricted leak marker"),
        ("restricted_context_blocked", True, "restricted-only candidate"),
        ("reload_identical", False, "reload identically"),
        ("peak_parallel_areas", 3, "concurrency exceeded"),
    ],
)
def test_access_invariant_violations_are_rejected(traces, db, field, value, message):
    changed = deepcopy(traces)
    changed[0]["access"][field] = value
    with pytest.raises(ValueError, match=message):
        validate_traces(changed, db)


def test_source_response_violation_is_rejected(traces, db):
    changed = deepcopy(traces)
    changed[0]["source_statuses"]["jira:MKT-482"] = 500
    with pytest.raises(ValueError, match="cited source did not return 200"):
        validate_traces(changed, db)


def test_fixtures_carry_no_restricted_or_provider_artifacts():
    for path in (TRACES, LABELS, LOW_TRACES, LOW_LABELS):
        raw = path.read_text(encoding="utf-8")
        for forbidden in (*RESTRICTED_MARKERS, "api_key", "Bearer"):
            assert forbidden not in raw
