# Frozen synthetic main-versus-combined area comparison

This is the portable copy of the separately approved 12-call comparison described in [quality-evaluation.md](../../quality-evaluation.md#matched-main-versus-combined-candidate-area-comparison-12-october-2026). It contains synthetic inputs and schema-valid visible model observations, not confidential company data, raw provider/error bodies, headers, credentials, exception dumps, or full UI/search traces. All 12 allowed starts completed; the approval is exhausted. No executable dispatch script is included. Do not interpret saved approval or a currently valid manifest as permission to invoke a model again.

## Files

- `approval-and-plan.json`: original approval scope, frozen commits, counterbalanced schedule and manifest hashes. The old absolute worktree/output paths are provenance only; never blindly execute them.
- `contexts/` and `manifests/`: three exact synthetic needs/pools and separately hashed baseline/candidate manifests. These are new frozen comparison inputs, not recovery of the older lost temporary manifests. The pre-merge baseline is `33ef28c`; the observed combined code is `e77bee6`.
- `observations/`: one exclusively claimed directory per invocation, with byte-identical `attempt.json`, `manifest.json`, allowlisted `summary.json`, validated `response.json`, separate `audit.json`, and terminal `execution.json`. Original asks, contributions, source order and uncertainty strings are preserved, including text defects. Do not repair or overwrite captured observations.
- `protected-hashes.json`, `immutable-capture-hashes.json`, and `completion-verification.json`: original repository/capture hashes and completed retention checks. Protected repository hashes refer to the frozen observed commits, not to later documentation or app changes.
- `frozen-review-references.json` and `artifact-comparison.json`: original assistant pre-observation references and preliminary descriptive/provisional counts. Their six-versus-six direct count includes Priya's provisional not-direct label.
- `manual-review.json` and `reviewed-comparison.json`: separate assistant post-observation source review. Priya's historical direct boundary is left pending, so decided unsupported direct counts are four per arm; other pending dimensions are also excluded. This correction is explicit, not a rewrite of the freeze or independent human adjudication. Primary-backed usefulness, direct support, original ask premises and completion are independent dimensions.
- `scheduler-started.json` and `scheduler-state.json`: original one-time dispatch/retention records, not a resumable job or new authorization.
- `bundle-index.json`: SHA-256 inventory of the 91 unchanged JSON files. This guide and the index itself are not original observations.

## Offline inspection

From the repository root, this reads one existing observation without making a model call:

```bash
uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.area_probe inspect --output docs/evaluations/20261012-main-vs-combined/observations/002-growth_scheduling-candidate-r1
uv run --python 3.12 --no-project --with-requirements requirements.txt python -m pytest -q tests/test_handoff_comparison.py
```

Do not use `run --approve-live` to replay this bundle. New separately authorized experiments must create new contexts/manifests/output directories without changing these records or relaxing stale checks. Baseline responses intentionally have no contribution field; only explicit offline historical normalization may insert an unscored placeholder on a copy. Missing contribution in a live reply remains a schema failure.

## Limits

Three reused synthetic contexts and two repetitions per arm cannot establish general model quality, independent package causality, production permission guarantees, a truncation/schema fix, or verified cost/usage accounting. All candidate asks used the correct neutral text, but unsupported direct claims persisted. Incomplete contribution strings at 300 characters and a non-English character were observed in `stop` replies; neither length nor template membership verifies role relevance. Read the [handoff](../../handoff.md) before changing the next development baseline.
