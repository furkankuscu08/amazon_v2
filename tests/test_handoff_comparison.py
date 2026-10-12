import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.area_probe import Summary, inspect_probe
from scripts.trace_diagnostics import RESTRICTED_MARKERS

BUNDLE = (
    Path(__file__).resolve().parents[1] / "docs/evaluations/20261012-main-vs-combined"
)


def load(name):
    return json.loads((BUNDLE / name).read_text())


def test_bundle_integrity_and_immutable_source_captures():
    index = load("bundle-index.json")
    assert index["approval_exhausted"] is True
    assert index["started"] == index["approved_limit"] == 12
    assert index["dispatch_script_included"] is False
    assert len(index["files"]) == 91
    assert len({entry["path"] for entry in index["files"]}) == 91
    for entry in index["files"]:
        path = Path(entry["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert path.suffix == ".json" and not path.name.startswith(".env")
        data = (BUNDLE / path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert not any(
            marker.casefold() in data.decode().casefold()
            for marker in RESTRICTED_MARKERS
        )
    for name, digest in load("immutable-capture-hashes.json").items():
        assert hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() == digest
    repository = Path(__file__).resolve().parents[1]
    for name, digest in load("protected-hashes.json")["main"].items():
        if name.startswith("tests/fixtures/"):
            assert (
                hashlib.sha256((repository / name).read_bytes()).hexdigest() == digest
            )


def test_twelve_retained_calls_and_identical_paired_contexts():
    plan = load("approval-and-plan.json")
    assert plan["approved_max_invocations"] == len(plan["schedule"]) == 12
    assert Counter(row["arm"] for row in plan["schedule"]) == {
        "main": 6,
        "candidate": 6,
    }
    assert len(list((BUNDLE / "observations").glob("*/attempt.json"))) == 12
    for context in plan["contexts"]:
        baseline = load(f"manifests/{context['name']}-main.json")
        candidate = load(f"manifests/{context['name']}-candidate.json")
        assert baseline["payload"] == candidate["payload"]
        assert baseline["retrieved_ids"] == candidate["retrieved_ids"]
        for key in ("area_prompt_sha256", "llm_sha256", "schema_sha256"):
            assert baseline[key] != candidate[key]
    for row in plan["schedule"]:
        output = BUNDLE / "observations" / Path(row["directory"]).name
        inspection = inspect_probe(output)
        assert inspection["started_invocations"] == 1
        assert inspection["call_outcome"] == "success"
        assert inspection["execution_status"] == "complete"
        assert inspection["retry_allowed"] is False
        summary_data = json.loads((output / "summary.json").read_text())
        assert set(summary_data) == set(Summary.model_fields)
        summary = Summary.model_validate(summary_data)
        assert summary.finish_reason == "stop"
        assert summary.http_status == 200
        response = json.loads((output / "response.json").read_text())
        audit = json.loads((output / "audit.json").read_text())
        assert "contribution" not in json.dumps(audit)
        for person in response["people"]:
            assert person["primary_evidence_id"] in person["evidence_ids"]
            assert ("contribution" in person) == (row["arm"] == "candidate")


def test_provisional_and_pending_reviews_remain_separate():
    frozen = load("frozen-review-references.json")
    preliminary = load("artifact-comparison.json")
    manual = load("manual-review.json")
    reviewed = load("reviewed-comparison.json")
    assert frozen["frozen_before_new_outputs"] is True
    assert (
        frozen["reference_controls"]["historical_platform"]["priya"]["direct_supported"]
        is False
    )
    for case in ("03/priya", "04/priya", "09/priya", "10/priya"):
        assert manual["cases"][case]["direct_supported"] is None
    for arm in ("main", "candidate"):
        controls = preliminary["aggregates"][arm][
            "frozen_control_counts_conditional_on_retained_valid_outputs"
        ]
        assert controls["unsupported_model_direct"] == 6
        assert reviewed["counts"][arm]["unsupported_model_direct"] == 4
        assert reviewed["counts"][arm]["supported_direct"] == 2
        assert reviewed["preselected_primary_controls"][arm] == {
            "preserved": 12,
            "total": 12,
        }
    assert reviewed["counts"]["main"]["original_ask_pending"] == 4
    assert reviewed["counts"]["main"]["original_ask_decided"] == 12
    assert reviewed["counts"]["main"]["original_ask_unsupported"] == 2
    assert reviewed["counts"]["candidate"]["original_ask_decided"] == 14
    assert reviewed["counts"]["candidate"]["original_ask_unsupported"] == 0
