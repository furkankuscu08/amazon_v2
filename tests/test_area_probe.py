import json
import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import httpx
import pytest

from scripts import area_probe as probe
from workbot import llm
from workbot.search import candidate_pool
from workbot.seed import seed_db
from workbot.storage import connect, visible_record


@pytest.fixture(autouse=True)
def exchange(monkeypatch):
    """All tests, including CLI tests, use canned HTTP and no real credentials."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(probe, "load_dotenv", lambda *args, **kwargs: None)
    response = {
        "content": json.dumps(
            {
                "people": [
                    {
                        "person_id": "owen",
                        "contribution": "Authored the exact scheduler/API integration update and can explain its constraints; new initiative ownership is unknown.",
                        "role": "direct_contact",
                        "relevance": "direct",
                        "primary_evidence_id": "github:campaign-scheduler-76",
                        "evidence_ids": ["github:campaign-scheduler-76"],
                        "confidence": "high",
                        "ask": "What integration constraints should we account for?",
                        "unverified": "Ownership of the new initiative is not established.",
                    }
                ]
            }
        ),
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "total_tokens": 19,
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
    }
    calls = []

    def handle(request):
        calls.append(json.loads(request.content))
        if "exception" in response:
            raise response["exception"]
        return httpx.Response(
            response.get("status", 200),
            json={
                "choices": [
                    {
                        "finish_reason": response["finish_reason"],
                        "message": {"content": response["content"]},
                    }
                ],
                "usage": response["usage"],
            },
        )

    client_class = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle)),
    )
    return response, calls


@pytest.fixture
def manifest():
    db = connect(":memory:")
    seed_db(db)
    area = {
        "id": "platform_api",
        "label": "Platform API integration",
        "rationale": "Consider the integration being changed.",
        "consultation_need": "What constraints would matter for updating this integration?",
        "search_intents": [
            {
                "keyword": "platform API integration",
                "semantic": "Scheduler and platform API integration work",
            }
        ],
        "mapping": "mapped",
        "org_unit_id": "platform",
        "mapping_reason": None,
    }
    retrieved = [
        "github:campaign-scheduler-76",
        "jira:MKT-482",
        "docs:campaign-review-2023",
    ]
    pool = candidate_pool(db, area, [visible_record(db, rid) for rid in retrieved])
    payload = {
        "idea": "We want to update the scheduler and platform API integration.",
        "answers": [],
        "area": area,
        "candidates": pool["people"],
    }
    db.close()
    return probe.prepare_manifest(payload, retrieved)


def run(manifest, output):
    return probe.run_probe(
        manifest, output, approve_live=True, model=llm.OpenRouter("SYNTHETIC_TEST_KEY")
    )


def read(output, name):
    return json.loads((output / f"{name}.json").read_text())


def test_success_records_are_written_in_phase_order(
    manifest, tmp_path, exchange, monkeypatch
):
    output = tmp_path / "run"
    write = probe._atomic_write
    order = []

    def record_write(path, value):
        order.append(path.stem)
        write(path, value)

    monkeypatch.setattr(probe, "_atomic_write", record_write)
    report = run(manifest, output)
    assert order == ["manifest", "attempt", "summary", "response", "audit", "execution"]
    assert report == {
        "started_invocations": 1,
        "approved_max_invocations": 1,
        "stage": "audit",
        "execution_status": "complete",
        "call_outcome": "success",
        "failure_category": None,
        "provider_outcome": "response_observed",
        "usage_available": True,
        "retry_allowed": False,
    }
    assert read(output, "manifest") == manifest
    assert read(output, "attempt")["invocation_started"] is True
    assert read(output, "response")["people"][0]["person_id"] == "owen"
    assert read(output, "summary")["reasoning_tokens"] == 0
    assert output.stat().st_mode & 0o077 == 0
    assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
    audit = read(output, "audit")
    assert audit["status"] == "people"
    assert audit["people"][0]["role"] == "direct_contact"
    assert audit["people"][0]["ask"] != read(output, "response")["people"][0]["ask"]
    assert "failure_category" not in json.dumps(audit)
    assert len(exchange[1]) == 1
    assert exchange[1][0]["messages"][0]["content"] == llm.PROMPTS["area"]
    assert json.loads(exchange[1][0]["messages"][1]["content"]) == manifest["payload"]
    assert exchange[1][0]["model"] == "z-ai/glm-5.3-flash"
    assert exchange[1][0]["max_tokens"] == 8192
    assert exchange[1][0]["reasoning"] == {"effort": "low"}
    assert exchange[1][0]["provider"] == {
        "only": ["open-inference/fp4"],
        "require_parameters": True,
    }


@pytest.mark.parametrize(
    ("change", "category", "provider"),
    [
        ({"content": "{}"}, "schema_invalid", "response_observed"),
        ({"content": '{"people":['}, "invalid_model_json", "response_observed"),
        ({"finish_reason": "length"}, "output_truncated", "response_observed"),
        ({"status": 503}, "http_error", "response_observed"),
        (
            {"exception": httpx.ReadTimeout("SYNTHETIC_PRIVATE_TIMEOUT")},
            "timeout",
            "unknown",
        ),
        (
            {"exception": httpx.ConnectError("SYNTHETIC_PRIVATE_TRANSPORT")},
            "transport_error",
            "unknown",
        ),
    ],
)
def test_observed_model_failures_are_not_retried_or_raw_captured(
    manifest, tmp_path, exchange, change, category, provider
):
    exchange[0].update(change)
    output = tmp_path / "run"
    report = run(manifest, output)
    assert report["failure_category"] == category
    assert report["provider_outcome"] == provider
    assert report["call_outcome"] == "failure"
    assert report["started_invocations"] == 1
    assert not (output / "response.json").exists()
    assert not (output / "audit.json").exists()
    assert read(output, "execution") == {"status": "model_error"}
    assert len(exchange[1]) == 1
    assert "SYNTHETIC_PRIVATE" not in json.dumps(read(output, "summary"))


def test_schema_valid_empty_review_remains_completed_not_found(
    manifest, tmp_path, exchange
):
    exchange[0]["content"] = '{"people":[]}'
    output = tmp_path / "run"
    assert run(manifest, output)["call_outcome"] == "success"
    assert read(output, "audit")["status"] == "not_found"


@pytest.mark.parametrize("phase", ["manifest", "attempt"])
def test_preflight_write_failure_prevents_any_call(
    manifest, tmp_path, exchange, monkeypatch, phase
):
    write = probe._atomic_write

    def fail(path, value):
        if path.stem == phase:
            raise OSError("SYNTHETIC_PRIVATE_STORAGE")
        write(path, value)

    monkeypatch.setattr(probe, "_atomic_write", fail)
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert exchange[1] == []
    assert probe.inspect_probe(output)["started_invocations"] == 0
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert exchange[1] == []


def test_summary_write_failure_does_not_discard_validated_output(
    manifest, tmp_path, exchange, monkeypatch
):
    write = probe._atomic_write

    def fail(path, value):
        if path.stem == "summary":
            raise OSError("SYNTHETIC_PRIVATE_STORAGE")
        write(path, value)

    monkeypatch.setattr(probe, "_atomic_write", fail)
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError, match="Diagnostic record unavailable"):
        run(manifest, output)
    assert read(output, "response")["people"][0]["person_id"] == "owen"
    assert probe.inspect_probe(output)["call_outcome"] == "unknown"
    assert len(exchange[1]) == 1


@pytest.mark.parametrize("phase", ["response", "audit", "execution"])
def test_later_write_failure_preserves_completed_summary(
    manifest, tmp_path, exchange, monkeypatch, phase
):
    write = probe._atomic_write

    def fail(path, value):
        if path.stem == phase:
            raise OSError("SYNTHETIC_PRIVATE_STORAGE")
        write(path, value)

    monkeypatch.setattr(probe, "_atomic_write", fail)
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert read(output, "summary")["outcome"] == "success"
    if phase != "response":
        assert read(output, "response")["people"][0]["person_id"] == "owen"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert len(exchange[1]) == 1


def test_summary_is_on_disk_before_the_model_call_returns(
    manifest, tmp_path, monkeypatch
):
    output = tmp_path / "run"
    complete = llm.OpenRouter.complete

    def interrupted(self, task, payload):
        complete(self, task, payload)
        assert read(output, "summary")["outcome"] == "success"
        raise KeyboardInterrupt

    monkeypatch.setattr(llm.OpenRouter, "complete", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(manifest, output)
    assert probe.inspect_probe(output)["stage"] == "summary"
    assert not (output / "response.json").exists()


def test_audit_interruption_preserves_summary_and_response(
    manifest, tmp_path, monkeypatch
):
    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(probe, "audit_area", interrupted)
    output = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        run(manifest, output)
    assert probe.inspect_probe(output)["stage"] == "response"
    assert read(output, "summary")["outcome"] == "success"
    assert read(output, "response")["people"][0]["person_id"] == "owen"


def test_started_but_unobserved_call_consumes_attempt_and_is_not_timeout(
    manifest, tmp_path, monkeypatch, exchange
):
    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(llm.OpenRouter, "complete", interrupted)
    output = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        run(manifest, output)
    report = probe.inspect_probe(output)
    assert report["started_invocations"] == 1
    assert report["provider_outcome"] == report["call_outcome"] == "unknown"
    assert report["execution_status"] == "interrupted"
    assert report["failure_category"] is None
    assert report["stage"] == "attempt"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert exchange[1] == []


def test_missing_key_and_missing_approval_do_not_start_calls(
    manifest, tmp_path, exchange
):
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError, match="approval"):
        probe.run_probe(manifest, output)
    assert not output.exists()
    with pytest.raises(probe.ProbeError, match="API key"):
        probe.run_probe(manifest, output, approve_live=True)
    assert probe.inspect_probe(output)["started_invocations"] == 0
    assert exchange[1] == []


def test_concurrent_duplicate_directory_claim_allows_only_one_invocation(
    manifest, tmp_path, exchange, monkeypatch
):
    barrier = Barrier(2)
    validate = probe._validate_manifest

    def synchronized(*args):
        result = validate(*args)
        barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(probe, "_validate_manifest", synchronized)
    output = tmp_path / "run"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, manifest, output) for _ in range(2)]
        successes = failures = 0
        for future in futures:
            try:
                assert future.result(timeout=5)["call_outcome"] == "success"
                successes += 1
            except probe.ProbeError:
                failures += 1
    assert successes == failures == len(exchange[1]) == 1


def test_existing_user_directory_is_never_modified(manifest, tmp_path, exchange):
    output = tmp_path / "user_work"
    output.mkdir()
    (output / "notes.txt").write_text("Keep this work")
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert list(output.iterdir()) == [output / "notes.txt"]
    assert (output / "notes.txt").read_text() == "Keep this work"
    assert exchange[1] == []


@pytest.mark.parametrize(
    "mutation",
    [
        "synthetic_false",
        "synthetic_one",
        "hash",
        "restricted_record",
        "duplicate_record",
        "candidate",
        "evidence",
        "extra",
    ],
)
def test_invalid_stale_or_restricted_manifest_fails_before_artifacts_or_calls(
    manifest, tmp_path, exchange, mutation
):
    data = deepcopy(manifest)
    if mutation == "synthetic_false":
        data["synthetic"] = False
    elif mutation == "synthetic_one":
        data["synthetic"] = 1
    elif mutation == "hash":
        data["llm_sha256"] = "0" * 64
    elif mutation == "restricted_record":
        data["retrieved_ids"].append("slack:restricted-plan")
    elif mutation == "duplicate_record":
        data["retrieved_ids"].append(data["retrieved_ids"][0])
    elif mutation == "candidate":
        data["payload"]["candidates"][0]["person_id"] = "eve"
    elif mutation == "evidence":
        data["payload"]["candidates"][0]["evidence"][0]["text"] = (
            "SYNTHETIC_PRIVATE_CHANGED"
        )
    else:
        data["SYNTHETIC_PRIVATE_EXTRA"] = "Do not persist"
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError, match="Invalid or stale"):
        run(data, output)
    assert not output.exists()
    assert exchange[1] == []


@pytest.mark.parametrize(
    "mutation",
    [
        "restricted_name",
        "restricted_person",
        "restricted_source",
        "restricted_contribution",
    ],
)
def test_unsafe_validated_output_is_not_saved(manifest, tmp_path, exchange, mutation):
    content = json.loads(exchange[0]["content"])
    person = content["people"][0]
    if mutation == "restricted_name":
        person["unverified"] = "Eve Restricted owns this initiative."
    elif mutation == "restricted_contribution":
        person["contribution"] = "Eve Restricted owns this initiative."
    elif mutation == "restricted_person":
        person["person_id"] = "eve"
    else:
        person["primary_evidence_id"] = "docs:restricted-budget"
        person["evidence_ids"] = ["docs:restricted-budget"]
    exchange[0]["content"] = json.dumps(content)
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert not (output / "response.json").exists()
    assert read(output, "summary")["outcome"] == "success"
    assert "Restricted" not in (output / "summary.json").read_text()


def test_logger_configuration_is_restored_and_sensitive_values_do_not_escape(
    manifest, tmp_path, exchange, caplog
):
    logger = logging.getLogger("workbot.llm")
    before = (logger.handlers[:], logger.level, logger.propagate, logger.disabled)
    data = deepcopy(manifest)
    marker = "SYNTHETIC_PRIVATE_IDEA"
    data["payload"]["idea"] = marker
    content = json.loads(exchange[0]["content"])
    content["people"][0]["unverified"] = marker
    content["people"][0]["contribution"] = marker
    exchange[0]["content"] = json.dumps(content)
    output = tmp_path / "run"
    run(data, output)
    assert (logger.handlers, logger.level, logger.propagate, logger.disabled) == before
    assert marker not in caplog.text
    assert marker not in (output / "summary.json").read_text()
    assert marker in (output / "response.json").read_text()


def test_summary_writer_drops_non_contract_fields_and_rejects_sensitive_labels(
    tmp_path,
):
    output = tmp_path / "run"
    output.mkdir()
    base = {
        "task": "area",
        "outcome": "failure",
        "failure_category": "schema_invalid",
        "validation_error_types": ["missing"],
        "duration_seconds": 1.0,
        "http_status": 200,
        "finish_reason": "stop",
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "reasoning_tokens": None,
        "SYNTHETIC_PRIVATE_EXTRA": "SYNTHETIC_PRIVATE_BODY",
    }
    writer = probe._SummaryWriter(output)
    writer.emit(
        logging.LogRecord(
            "workbot.llm",
            logging.WARNING,
            "",
            0,
            "model_call_summary %s",
            (json.dumps(base),),
            None,
        )
    )
    assert not writer.failed
    assert "SYNTHETIC_PRIVATE" not in (output / "summary.json").read_text()
    previous = (output / "summary.json").read_bytes()
    base["failure_category"] = "SYNTHETIC_PRIVATE_CATEGORY"
    another = probe._SummaryWriter(output)
    another.emit(
        logging.LogRecord(
            "workbot.llm",
            logging.WARNING,
            "",
            0,
            "model_call_summary %s",
            (json.dumps(base),),
            None,
        )
    )
    assert another.failed
    assert (output / "summary.json").read_bytes() == previous


def test_duplicate_diagnostic_does_not_overwrite_first_summary(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    writer = probe._SummaryWriter(output)
    base = {
        "task": "area",
        "outcome": "success",
        "failure_category": None,
        "validation_error_types": None,
        "duration_seconds": 1.0,
        "http_status": 200,
        "finish_reason": "stop",
        "prompt_tokens": 12,
        "completion_tokens": 7,
        "total_tokens": 19,
        "reasoning_tokens": 0,
    }
    record = logging.LogRecord(
        "workbot.llm",
        logging.INFO,
        "",
        0,
        "model_call_summary %s",
        (json.dumps(base),),
        None,
    )
    writer.emit(record)
    previous = (output / "summary.json").read_bytes()
    writer.emit(record)
    assert writer.failed
    assert (output / "summary.json").read_bytes() == previous


def test_atomic_replace_failure_leaves_prior_artifact_intact(tmp_path, monkeypatch):
    target = tmp_path / "summary.json"
    probe._atomic_write(target, {"old": True})

    def fail(*args):
        raise OSError("SYNTHETIC_PRIVATE_REPLACE")

    monkeypatch.setattr(probe.os, "replace", fail)
    with pytest.raises(OSError):
        probe._atomic_write(target, {"new": True})
    assert json.loads(target.read_text()) == {"old": True}
    assert list(tmp_path.iterdir()) == [target]


def test_inspection_without_usage_does_not_invent_counts(manifest, tmp_path, exchange):
    exchange[0]["usage"] = None
    output = tmp_path / "run"
    assert run(manifest, output)["usage_available"] is False


def test_cli_inspect_is_offline_and_run_requires_approval(tmp_path, exchange, capsys):
    output = tmp_path / "run"
    output.mkdir()
    probe._atomic_write(
        output / "attempt.json",
        {"invocation_started": True, "approved_max_invocations": 1},
    )
    assert probe.main(["inspect", "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["provider_outcome"] == "unknown"
    assert (
        probe.main(
            ["run", "--manifest", "SYNTHETIC_PRIVATE_MISSING", "--output", str(output)]
        )
        == 1
    )
    assert "SYNTHETIC_PRIVATE" not in capsys.readouterr().out
    assert exchange[1] == []


def test_cli_never_prints_raw_manifest_errors_or_tracebacks(tmp_path, exchange, capsys):
    file = tmp_path / "bad.json"
    file.write_text("SYNTHETIC_PRIVATE_MANIFEST")
    assert (
        probe.main(
            [
                "run",
                "--manifest",
                str(file),
                "--output",
                str(tmp_path / "run"),
                "--approve-live",
            ]
        )
        == 1
    )
    printed = capsys.readouterr()
    assert "SYNTHETIC_PRIVATE" not in printed.out + printed.err
    assert "Traceback" not in printed.out + printed.err
    assert exchange[1] == []


def test_summary_survives_abrupt_process_exit(manifest, tmp_path):
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(manifest))
    output = tmp_path / "run"
    code = """
import json
import logging
import os
import sys
from pathlib import Path
from scripts.area_probe import run_probe

class OfflineModel:
    api_key = 'SYNTHETIC_TEST_KEY'
    def complete(self, task, payload):
        summary = {
            'task': 'area', 'outcome': 'success', 'failure_category': None,
            'validation_error_types': None, 'duration_seconds': 1.0,
            'http_status': 200, 'finish_reason': 'stop', 'prompt_tokens': 12,
            'completion_tokens': 7, 'total_tokens': 19, 'reasoning_tokens': 0,
        }
        logging.getLogger('workbot.llm').info('model_call_summary %s', json.dumps(summary))
        os._exit(17)

run_probe(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]),
          approve_live=True, model=OfflineModel())
"""
    process = subprocess.run(
        [sys.executable, "-c", code, str(input_file), str(output)],
        cwd=probe.ROOT,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert process.returncode == 17
    assert process.stdout == process.stderr == b""
    assert read(output, "summary")["outcome"] == "success"
    assert probe.inspect_probe(output)["stage"] == "summary"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)


def test_cli_success_is_mocked_and_prints_only_observation_boundary(
    manifest, tmp_path, exchange, monkeypatch, capsys
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "SYNTHETIC_PRIVATE_KEY")
    input_file = tmp_path / "input.json"
    data = deepcopy(manifest)
    data["payload"]["idea"] = "SYNTHETIC_PRIVATE_IDEA"
    input_file.write_text(json.dumps(data))
    output = tmp_path / "run"
    assert (
        probe.main(
            [
                "run",
                "--manifest",
                str(input_file),
                "--output",
                str(output),
                "--approve-live",
            ]
        )
        == 0
    )
    printed = capsys.readouterr()
    report = json.loads(printed.out)
    assert report["call_outcome"] == "success"
    assert "SYNTHETIC_PRIVATE" not in printed.out + printed.err
    assert "SYNTHETIC_PRIVATE" not in (output / "summary.json").read_text()
    assert len(exchange[1]) == 1


def test_preflight_directory_sync_failure_prevents_calls(
    manifest, tmp_path, exchange, monkeypatch
):
    def fail(*args):
        raise OSError("SYNTHETIC_PRIVATE_FSYNC")

    monkeypatch.setattr(probe, "_sync_directory", fail)
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert probe.inspect_probe(output)["stage"] == "claimed"
    assert exchange[1] == []


def test_real_client_interruption_does_not_misclassify_finally_failure_summary(
    manifest, tmp_path, exchange
):
    exchange[0]["exception"] = KeyboardInterrupt()
    output = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        run(manifest, output)
    # Preserve exactly the observed production event, but do not mistake its
    # current-stage default for a confirmed provider/JSON failure.
    assert read(output, "summary")["failure_category"] == "provider_response_invalid"
    report = probe.inspect_probe(output)
    assert report["execution_status"] == "interrupted"
    assert report["provider_outcome"] == report["call_outcome"] == "unknown"
    assert report["failure_category"] is None
    assert len(exchange[1]) == 1


def test_failure_summary_without_terminal_record_remains_unconfirmed(
    manifest, tmp_path, exchange, monkeypatch
):
    exchange[0]["content"] = "{}"
    write = probe._atomic_write

    def fail_terminal(path, value):
        if path.stem == "execution":
            raise OSError("SYNTHETIC_PRIVATE_STORAGE")
        write(path, value)

    monkeypatch.setattr(probe, "_atomic_write", fail_terminal)
    output = tmp_path / "run"
    with pytest.raises(probe.ProbeError):
        run(manifest, output)
    assert read(output, "summary")["failure_category"] == "schema_invalid"
    report = probe.inspect_probe(output)
    assert report["call_outcome"] == "unknown"
    assert report["failure_category"] is None
    assert report["provider_outcome"] == "response_observed"
    assert report["usage_available"] is True
