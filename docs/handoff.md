# WorkBot agent handoff

## Starting point

- Continue from `main` in the repository, not from a required external candidate worktree. The user explicitly approved the combined implementation as the next development baseline, while accepting that semantic quality issues remain unresolved. Read `AGENTS.md` and `README.md` before changing behavior.
- `baseline/pre-combined-candidate-20261012` preserves pre-merge main `33ef28c`. The live-tested combined application code is `e77bee6`; handoff packaging changes documentation/tests/artifacts, not that application code. Keep both actual observed versions identifiable in future comparisons.
- Current behavior: low reasoning for area evaluation, high for impact/priority; a required 5-300-character unverified `contribution`; shared neutral model questions and unchanged verified-evidence card-question selection. No new authentication, real integration, messaging, verifier, retry, fallback, or semantic relevance gate was added.

## What is established

The [matched area comparison](quality-evaluation.md#matched-main-versus-combined-candidate-area-comparison-12-october-2026) used three frozen synthetic needs, identical ordered visible evidence/candidates, and two repetitions per arm. All six calls per arm validated. Candidate median duration was 25.464 s versus 41.011 s; reported total tokens were 13,380 versus 14,770. All 14 candidate asks matched the correct neutral choice. All 12 preselected person/correct-primary controls and both exact-integration supported-direct controls per arm were retained. These are small combined-branch observations, not isolated effort causality, general reliability, billed-cost verification, or independent human validation.

## First unresolved priorities

1. **Source-to-need role calibration:** Decided unsupported direct claims remained four per arm and all survived audit. Growth Owen is still direct even when contribution says operator workflows are not covered. `audit_area` already receives consultation need in `item`; it does not independently test semantic entailment. Merely passing another argument or trusting contribution prose will not solve this. Preserve useful primary-backed advisors and supported direct contacts; do not blanket-convert direct to advisor or require area expertise for advisors. Confirm the next intervention with the user rather than silently adding a fourth verifier or a case-tuned threshold.
2. **Contribution text quality:** Three candidate strings have incomplete/malformed endings, one includes a non-English character, and four Nina summaries mix primary and secondary facts. These were schema-valid `stop` replies, not completion-cap failures. Do not infer provider clipping from a 300-character value, silently repair a live field, add a language detector without a decision, or treat a persuasive explanation as verified support. Keep the text out of cards, sessions, priority and production logs.
3. **Pending judgments:** Historical/Platform Priya's direct boundary, Growth Nina/Jules direct boundaries, Elena's reporter-primary usefulness, and four main-arm ask premises remain genuinely debatable. The advisor rubric is user-approved; these per-case assistant judgments are not human-adjudicated. Do not score pending as success/failure or reject historical work merely for age. The raw provisional direct count was six per arm; the separate review excludes two Priya cases per arm and reports four. Both records are preserved.

These are handoff priorities, not an automatically authorized implementation plan. No extra live calls are approved; the 12-call comparison budget is exhausted. No schema or truncation failures occurred in this comparison, so it did not demonstrate a fix for earlier failures.

## Evidence and preservation

- [Portable comparison bundle](evaluations/20261012-main-vs-combined/README.md): byte-identical allowed synthetic captures, manifests/contexts, summaries, separate audits, terminal markers, frozen references and separate post-review labels. Use the relative bundle paths for offline inspection. Original absolute paths are provenance, not executable instructions or a valid new call budget.
- The original local copy is `/home/furkankuscu08/projects/workbot-live-comparison-20261012/`. The source recovery backup is `/home/furkankuscu08/projects/workbot-recovery-20261012/`; it remains local and is not required to read the bundled comparison.
- Older `/tmp/opencode` preparation freezes/manifests and earlier local observation directories are unavailable. Intermediate OpenCode trees have not been identified as the exact Package 1/Package 2 freezes. Do not present reconstructed artifacts as recovered originals or infer the lost fourth GLM outcome/usage/billing.
- Keep existing `tests/fixtures/` observations and labels immutable. `scripts/historical_models.py` is an explicit offline adapter for uncaptured contribution fields, never a repair path for live responses. A placeholder is unobserved/unscored, not a generated explanation.

## Validation before further changes

```bash
uv run --python 3.12 --no-project --with-requirements requirements.txt python -m pytest -q
uv run --python 3.12 --no-project --with-requirements requirements.txt ruff check workbot tests scripts
uv run --python 3.12 --no-project --with-requirements requirements.txt ruff format --check workbot tests scripts
git diff --check
```

These are offline checks. For live work, obtain a new explicit context/call budget, prepare new per-arm manifests against actual prompt/LLM/schema hashes, retain exact evidence order and original needs, count every start including unknown outcomes, and use separate observation processes/directories with no automatic replacement. Main now contains the combined behavior; referring to an unqualified main arm as the old high-effort implementation would be incorrect.

Handoff preparation passed all 306 offline tests, Ruff lint/format checks, and `git diff --check`; the existing Starlette test-client deprecation warning remains. The 91 bundled JSON files match their local originals byte-for-byte, and the app/prompt/schema code and older fixture/label files are unchanged from the observed combined commit. Packaging and merge preparation added no model calls.
