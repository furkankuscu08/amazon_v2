from copy import deepcopy

import pytest
from pydantic import ValidationError

from scripts.historical_models import (
    CONTRIBUTION_UNOBSERVED,
    historical_evaluation,
)
from scripts.trace_audit_replay import _captured_evaluation
from workbot.models import AreaEvaluation


@pytest.fixture
def captured_person():
    return {
        "person_id": "synthetic-author",
        "primary_evidence_id": "github:synthetic-update",
        "role": "advisor",
        "relevance": "adjacent",
        "evidence_ids": ["github:synthetic-update"],
        "confidence": "medium",
        "ask": "Which undocumented controls already exist?",
        "unverified": "Historical synthetic proposal; original premise is not repaired.",
    }


def test_historical_adapter_is_explicit_and_does_not_mutate_captures(captured_person):
    before = deepcopy(captured_person)
    result = historical_evaluation([captured_person])
    assert result.people[0].contribution == CONTRIBUTION_UNOBSERVED
    serialized = result.people[0].model_dump()
    del serialized["contribution"]
    assert serialized == before
    assert captured_person == before
    result.people[0].evidence_ids.append("github:another-synthetic-update")
    assert captured_person == before


def test_historical_adapter_preserves_an_observed_contribution(captured_person):
    captured_person["contribution"] = "The captured contribution remains unverified."
    result = historical_evaluation([captured_person])
    assert result.people[0].contribution == captured_person["contribution"]


@pytest.mark.parametrize("value", [None, False, "abcd", "x" * 301])
def test_historical_adapter_does_not_repair_explicit_invalid_values(
    captured_person, value
):
    captured_person["contribution"] = value
    before = deepcopy(captured_person)
    with pytest.raises(ValidationError):
        historical_evaluation([captured_person])
    assert captured_person == before


@pytest.mark.parametrize("failure", ["uncited_primary", "duplicate_person", "extra"])
def test_historical_adapter_preserves_original_contract_checks(
    captured_person, failure
):
    people = [captured_person]
    if failure == "uncited_primary":
        captured_person["primary_evidence_id"] = "github:uncited-update"
    elif failure == "duplicate_person":
        people.append(deepcopy(captured_person))
    else:
        captured_person["reasoning_narrative"] = "Not part of the captured schema."
    with pytest.raises(ValidationError):
        historical_evaluation(people)


def test_live_schema_does_not_apply_the_historical_adapter(captured_person):
    with pytest.raises(ValidationError) as error:
        AreaEvaluation.model_validate({"people": [captured_person]})
    assert error.value.errors()[0]["type"] == "missing"
    assert historical_evaluation([]).people == []


@pytest.mark.parametrize("observed", [False, True])
def test_trace_replay_does_not_drop_captured_contributions_or_repair_asks(
    captured_person, observed
):
    if observed:
        captured_person["contribution"] = (
            "An observed but unverified source-to-need summary."
        )
    area = {"model_proposals": [captured_person]}
    before = deepcopy(area)
    result = _captured_evaluation(area)
    assert result.people[0].contribution == (
        captured_person["contribution"] if observed else CONTRIBUTION_UNOBSERVED
    )
    assert result.people[0].ask == captured_person["ask"]
    assert area == before


def test_trace_replay_does_not_overwrite_explicit_invalid_contribution(captured_person):
    captured_person["contribution"] = None
    with pytest.raises(ValidationError):
        _captured_evaluation({"model_proposals": [captured_person]})
