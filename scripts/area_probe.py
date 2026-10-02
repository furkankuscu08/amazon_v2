"""Opt-in, single-area synthetic observation; no retries or raw response capture."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from argparse import ArgumentParser
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator

from scripts.trace_diagnostics import RESTRICTED_MARKERS
from workbot import llm
from workbot.models import Area, AreaEvaluation, StrictModel
from workbot.search import candidate_pool
from workbot.seed import seed_db
from workbot.service import audit_area
from workbot.storage import connect, visible_record

ROOT = Path(__file__).resolve().parents[1]
TokenCount = Annotated[int, Field(ge=0, le=2**63 - 1)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ProbeError(Exception):
    """Only fixed, safe messages may be used by the CLI."""


class Answer(StrictModel):
    question: str
    answer: str | None


class Payload(StrictModel):
    idea: str = Field(min_length=1)
    answers: list[Answer] = Field(max_length=2)
    area: Area
    candidates: list[dict] = Field(min_length=1, max_length=22)


class Manifest(StrictModel):
    synthetic: Literal[True]
    area_prompt_sha256: Digest
    llm_sha256: Digest
    schema_sha256: Digest
    retrieved_ids: list[str] = Field(max_length=20)
    payload: Payload


class Execution(StrictModel):
    status: Literal["complete", "model_error", "interrupted"]


class Summary(StrictModel):
    task: Literal["area"]
    outcome: Literal["success", "failure"]
    failure_category: (
        Literal[
            "configuration_error",
            "timeout",
            "transport_error",
            "http_error",
            "provider_response_invalid",
            "output_truncated",
            "response_incomplete",
            "non_text_response",
            "invalid_model_json",
            "schema_invalid",
        ]
        | None
    )
    validation_error_types: list[str] | None = Field(max_length=14)
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    http_status: int | None = Field(ge=100, le=599)
    finish_reason: str | None
    prompt_tokens: TokenCount | None
    completion_tokens: TokenCount | None
    total_tokens: TokenCount | None
    reasoning_tokens: TokenCount | None

    @field_validator("finish_reason")
    @classmethod
    def known_finish(cls, value):
        if value is not None and value not in llm._FINISH_REASONS | {"other"}:
            raise ValueError("Unknown finish reason")
        return value

    @field_validator("validation_error_types")
    @classmethod
    def known_validation_types(cls, value):
        if value is not None:
            if any(
                code not in llm._VALIDATION_ERROR_TYPES | {"other"} for code in value
            ):
                raise ValueError("Unknown validation type")
            return sorted(set(value))
        return value


def _digests() -> dict[str, str]:
    return {
        "area_prompt_sha256": hashlib.sha256(llm.PROMPTS["area"].encode()).hexdigest(),
        "llm_sha256": hashlib.sha256(Path(llm.__file__).read_bytes()).hexdigest(),
        "schema_sha256": hashlib.sha256(
            json.dumps(AreaEvaluation.model_json_schema(), sort_keys=True).encode()
        ).hexdigest(),
    }


def _require_visible(value) -> None:
    text = json.dumps(value, ensure_ascii=False)
    if any(
        marker.casefold() in text.casefold() for marker in RESTRICTED_MARKERS
    ) or re.search(r"\beve\b", text, re.IGNORECASE):
        raise ProbeError("Restricted synthetic content is not allowed")


def _validate_manifest(data, db) -> tuple[dict, dict]:
    try:
        if not isinstance(data, dict) or data.get("synthetic") is not True:
            raise ValueError("Synthetic declaration required")
        manifest = Manifest.model_validate(data)
        payload = manifest.payload.model_dump()
        if any(
            getattr(manifest, name) != digest for name, digest in _digests().items()
        ):
            raise ValueError("Stale or unapproved manifest")
        area = payload["area"]
        if (
            area["mapping"] != "mapped"
            or not db.execute(
                "SELECT 1 FROM org_units WHERE id=?", (area["org_unit_id"],)
            ).fetchone()
        ):
            raise ValueError("Unknown mapped area")
        if len(manifest.retrieved_ids) != len(set(manifest.retrieved_ids)):
            raise ValueError("Duplicate records")
        records = [visible_record(db, rid) for rid in manifest.retrieved_ids]
        if any(record is None for record in records):
            raise ValueError("Unavailable record")
        pool = candidate_pool(db, area, records)
        if payload["candidates"] != pool["people"] or len(json.dumps(payload)) > 18000:
            raise ValueError("Changed or oversized context")
        _require_visible(payload)
        return manifest.model_dump(), pool
    except Exception:  # noqa: BLE001 — never expose manifest validation inputs.
        raise ProbeError("Invalid or stale synthetic manifest") from None


def prepare_manifest(payload: dict, retrieved_ids: list[str]) -> dict:
    """Offline preparation; caller must supply synthetic idea/answers only."""
    db = connect(":memory:")
    try:
        seed_db(db)
        data = {
            "synthetic": True,
            **_digests(),
            "retrieved_ids": retrieved_ids,
            "payload": payload,
        }
        manifest, _ = _validate_manifest(data, db)
        return manifest
    finally:
        db.close()


def _sync_directory(path: Path) -> None:
    directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _atomic_write(path: Path, value) -> None:
    data = (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class _SummaryWriter(logging.Handler):
    def __init__(self, output: Path):
        super().__init__()
        self.output = output
        self.count = 0
        self.failed = False

    def emit(self, record):
        if record.name != "workbot.llm" or record.msg != "model_call_summary %s":
            return
        self.count += 1
        try:
            if self.count != 1 or record.exc_info is not None:
                raise ValueError("Unexpected diagnostic event")
            raw = json.loads(record.args[0])
            # Drop all non-contract fields; validate values before persistence.
            summary = Summary.model_validate(
                {key: raw[key] for key in Summary.model_fields}
            )
            _atomic_write(self.output / "summary.json", summary.model_dump())
        except Exception:  # noqa: BLE001 — no exception/input text, and no masking the call.
            self.failed = True


@contextmanager
def _capture_summary(writer):
    logger = logging.getLogger("workbot.llm")
    previous = (logger.handlers[:], logger.level, logger.propagate, logger.disabled)
    logger.handlers, logger.propagate, logger.disabled = [writer], False, False
    logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        logger.handlers, level, logger.propagate, logger.disabled = previous
        logger.setLevel(level)


def run_probe(data: dict, output: Path, *, approve_live=False, model=None) -> dict:
    """One invocation per exclusively claimed directory; never resume or retry."""
    if approve_live is not True:
        raise ProbeError("Live invocation requires separate explicit approval")
    claimed = False
    db = connect(":memory:")
    try:
        seed_db(db)
        manifest, pool = _validate_manifest(data, db)
        # mkdir is the cross-process claim. Existing directories are never reused,
        # even after a preflight failure, missing summary, or process interruption.
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        claimed = True
        _sync_directory(output.parent)
        _atomic_write(output / "manifest.json", manifest)
        client = model if model is not None else llm.OpenRouter()
        if not client.api_key:
            raise ProbeError("API key is not configured; no invocation started")
        writer = _SummaryWriter(output)
        _atomic_write(
            output / "attempt.json",
            {"invocation_started": True, "approved_max_invocations": 1},
        )
        payload = manifest["payload"]
        with _capture_summary(writer):
            try:
                evaluation = client.complete("area", payload)
            except llm.ModelError:
                _atomic_write(output / "execution.json", {"status": "model_error"})
                if writer.failed or writer.count != 1:
                    raise ProbeError(
                        "Diagnostic record unavailable; do not repeat this attempt"
                    ) from None
                return inspect_probe(output)
        if not isinstance(evaluation, AreaEvaluation):
            raise ProbeError("Unexpected model contract; do not repeat this attempt")
        response = evaluation.model_dump()
        _require_visible(response)
        candidates = {person["person_id"]: person for person in pool["people"]}
        for person in evaluation.people:
            candidate = candidates.get(person.person_id)
            if candidate is None or not set(person.evidence_ids) <= {
                e["id"] for e in candidate["evidence"]
            }:
                raise ProbeError(
                    "Unsafe output identifiers; validated output was not saved"
                )
        _atomic_write(output / "response.json", response)
        if writer.failed or writer.count != 1:
            raise ProbeError(
                "Diagnostic record unavailable; do not repeat this attempt"
            )
        # Persist the validated model observation BEFORE auditing it.
        item = {
            "id": payload["area"]["id"],
            "status": "not_found",
            "people": [],
            "direct_review_incomplete": False,
        }
        audit_area(db, item, pool, evaluation)
        _require_visible(item)
        _atomic_write(output / "audit.json", item)
        _atomic_write(output / "execution.json", {"status": "complete"})
        return inspect_probe(output)
    except KeyboardInterrupt:
        if claimed and not (output / "execution.json").exists():
            try:
                _atomic_write(output / "execution.json", {"status": "interrupted"})
            except Exception:  # noqa: BLE001, S110 — preserve interruption, not disk errors.
                pass
        raise
    except ProbeError:
        raise
    except Exception:  # noqa: BLE001 — provider/OS/audit messages must not reach CLI.
        raise ProbeError(
            "Probe stopped; inspect existing records and do not repeat this attempt"
        ) from None
    finally:
        db.close()


def inspect_probe(output: Path) -> dict:
    """Offline observation boundary, not a claim that a pending process has died."""
    if not output.is_dir():
        raise ProbeError("Probe directory does not exist")
    started = (output / "attempt.json").exists()
    summary = None
    execution = None
    try:
        if (output / "summary.json").exists():
            summary = Summary.model_validate_json((output / "summary.json").read_text())
        if (output / "execution.json").exists():
            execution = Execution.model_validate_json(
                (output / "execution.json").read_text()
            )
    except Exception:  # noqa: BLE001 — no file contents in error output.
        raise ProbeError(
            "Invalid diagnostic artifact; do not repeat this attempt"
        ) from None
    # A failure event can come from complete()'s finally during interruption.
    # Only a separately recorded, caught ModelError confirms call failure.
    confirmed_failure = (
        summary is not None
        and summary.outcome == "failure"
        and execution is not None
        and execution.status == "model_error"
    )
    stages = ("audit", "response", "summary", "attempt", "manifest")
    stage = next(
        (name for name in stages if (output / f"{name}.json").exists()), "claimed"
    )
    return {
        "started_invocations": int(started),
        "approved_max_invocations": 1,
        "stage": stage,
        "execution_status": execution.status if execution else "unknown",
        "call_outcome": (
            "success"
            if summary and summary.outcome == "success"
            else "failure"
            if confirmed_failure
            else "unknown"
        ),
        "failure_category": summary.failure_category if confirmed_failure else None,
        "provider_outcome": (
            "response_observed"
            if summary and summary.http_status is not None
            else "no_request_observed"
            if not started
            else "unknown"
        ),
        "usage_available": summary is not None
        and any(
            getattr(summary, name) is not None
            for name in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "reasoning_tokens",
            )
        ),
        "retry_allowed": False,
    }


def main(argv=None) -> int:
    parser = ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="One separately approved live area invocation")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--approve-live", action="store_true")
    inspect = sub.add_parser("inspect", help="Offline inspection; never calls a model")
    inspect.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_probe(args.output)
        else:
            if not args.approve_live:
                raise ProbeError("Live invocation requires separate explicit approval")
            data = json.loads(args.manifest.read_text())
            load_dotenv(ROOT / ".env")
            result = run_probe(data, args.output, approve_live=True)
        print(json.dumps(result, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        print(
            "Probe interrupted; provider outcome may be unknown. Do not repeat this attempt."
        )
    except Exception:  # noqa: BLE001 — no exception messages, paths, or tracebacks in CLI.
        print(
            "Probe stopped; check approval, manifest, and offline artifacts. Do not repeat this attempt."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
