# WorkBot

**Amazon Developer Hackathon — Alexa+ track (simulated web experience route)**

WorkBot is a simulated Alexa+ experience: Maya describes a project idea and sees consultation areas, evidence-backed contacts, questions to ask, and explicit gaps. It searches synthetic work traces and a structured directory; it does not make project decisions or contact people.

> ⚠️ **Disclaimer:** This is **not** an official Alexa integration or Amazon API integration. Use **synthetic project ideas only**: prompts are sent to OpenRouter. The directory and work traces are fictional. No messages or invitations are sent to anyone. WorkBot's input and output language is **English**: enter ideas and clarification answers in English; synthetic records, search intents, prompts, and displayed questions/cards are written in English. This is a product convention, not automatic detection or rejection of other languages at runtime.

> **Current development baseline:** Continue from `main`. Area evaluations request low reasoning; impact and priority remain high. Proposals require an unverified `contribution`, and the model is instructed to use shared neutral questions. The audit verifies visibility and personal evidence links, not source-to-need semantics; unsupported direct roles and contribution text defects remain open. The merge is a development starting point, not quality certification. New paid observations require explicit approval.

## Documentation

- This `README.md` is the human guide to the current prototype and its limits.
- [`AGENTS.md`](AGENTS.md) guides coding agents working in this repository.
- [`docs/handoff.md`](docs/handoff.md) gives the next agent the current baseline, unresolved priorities, and evaluation/approval boundaries.
- [`docs/quality-evaluation.md`](docs/quality-evaluation.md) separates the role rubric, latest comparison, and dated experiment history; its recovery section explains which older artifacts are unavailable.
- [Bundled synthetic comparison](docs/evaluations/20261012-main-vs-combined/README.md) preserves the 12 area observations and separate judgments for offline inspection.
- [`docs/archive/`](docs/archive/) preserves historical analysis and non-binding design proposals; these are not current behavior or an active implementation plan.
- [`docs/competition.md`](docs/competition.md) is a dated working brief for the hackathon; recheck the [live official rules](https://amazonappdev2026.devpost.com/rules) before submitting.
- [`docs/competition-winner-patterns.md`](docs/competition-winner-patterns.md) compares other competition winners for inspiration, not requirements or proof of what wins.
- [`opencode.jsonc`](opencode.jsonc) holds OpenCode configuration, including optional built-in subagent model preferences.

## Stack

| Layer | Choice |
| --- | --- |
| Web | FastAPI + Jinja2 templating, served by **uvicorn** (`workbot.main:app`) |
| LLM | OpenRouter — `z-ai/glm-5.3-flash` (area low; impact/priority high), routed to the tested `open-inference/fp4` endpoint via `OPENROUTER_API_KEY` |
| Vectors | Local Qdrant (Docker, REST 6333, bound to localhost) |
| Embeddings | Local FastEmbed / all-MiniLM-L6-v2 (no cloud embedding calls) |
| Relational data | SQLite via `WORKBOT_DB_PATH` (default `data/workbot.sqlite3`) |

## Prerequisites

- Docker (Compose v2.22+) — for Qdrant, and optionally the app container
- Python 3.12 + [uv](https://docs.astral.sh/uv/) (or plain `pip`)
- An OpenRouter API key (https://openrouter.ai/keys)

## Setup

```bash
# 1) Environment & dependencies (the application loads .env automatically)
cp .env.example .env          # then edit: set OPENROUTER_API_KEY
uv venv --python 3.12 && source .venv/bin/activate   # or: python3.12 -m venv .venv
uv pip install -r requirements.txt     # or: pip install -r requirements.txt

# 2) Start Qdrant (app container is optional and excluded by default)
docker compose up -d

# 3) Seed synthetic data (creates/loads the Qdrant collection + SQLite fixtures)
python -m workbot.seed

# 4) Run the app
uvicorn workbot.main:app --host 127.0.0.1 --port 8000
```

Web UI: **http://localhost:8000** — vector DB dashboard: http://localhost:6333/dashboard If host port 6333 is occupied, set `QDRANT_HOST_PORT=6335` and `QDRANT_URL=http://localhost:6335` in `.env` before starting Compose and seeding.

### Optional: everything in Docker

```bash
docker compose --profile app up -d --build                     # app on :8000 + Qdrant
docker compose --profile app run --rm app python -m workbot.seed
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | *(required)* | OpenRouter API key for the LLM |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_HOST_PORT` | `6333` | Host port exposed by Compose for local Python |
| `WORKBOT_DB_PATH` | `data/workbot.sqlite3` | SQLite database file |
| `WORKBOT_HOST_PORT` | `8000` | Host port for the optional app container |

`.env` contains secrets and is **git-ignored** — never commit it. Model requests use parameter-compatible routing to the tested `open-inference/fp4` endpoint, an 8,192-token output cap, and strict JSON-schema requests with local validation. If the pinned endpoint is unavailable, WorkBot fails closed rather than silently selecting an untested provider. These settings do not guarantee schema completion or semantic correctness across future responses/model/provider changes. Do not use confidential inputs; live calls consume your own API budget.

## Current behavior and limitations

This first slice uses a small campaign-focused fixture, not a 2,000–5,000-person directory or a claim of exhaustive stakeholder discovery. Its output distinguishes unmapped areas, completed reviews without a verified contact, and incomplete reviews. The web app uses a fixed **demo Maya/workspace identity**, not real authentication. It accepts same-origin forms and applies a small in-memory model-request budget; these local-demo guards are not production security controls. Keep it on localhost. The card exposes an expandable BM25/Qdrant candidate trace; search rank alone never establishes a person's role. Restricted work records are excluded from both indexes. The initial vector similarity threshold and candidate caps are small-fixture defaults, not measured production thresholds. If a visible record changes after seeding, search stops safely until `python -m workbot.seed` refreshes the vector index. A stored card is not silently regenerated on reload. Seeding preserves modified existing rows; it does not reset a changed fixture to its original text or restore a deactivated person.

Directory title matches only add a candidate when that person also has current visible responsibility evidence; a title with no visible evidence cannot expose a person known only through restricted sources to the model. A current, visible responsibility can also support a narrow `advisor` question about that duty; manager/remit evidence alone does not qualify an advisor. Visible work-trace candidates and current manager/remit routing still use their own evidence checks.

Each area also carries a `consultation_need`, and each proposed person names one `primary_evidence_id` plus the model's own `direct`/`adjacent`/`weak` relevance read. A `direct_contact` needs that single primary source to show a strong work or current-responsibility tie, so a weak tie on the relevant record cannot borrow strength from an unrelated record in the same citation list. When the model marks its own link adjacent or weak, the contact is kept as an `advisor` instead of being dropped or presented as direct; a mention-only mirror is not proposed. These are deterministic checks on visibility and link strength, so they still cannot judge whether a visible source is genuinely on-topic for an area. An area with no supportable person stays `not_found`; showing a contact in every area is not a goal.

The area prompt separates primary-source facts, the person's link, useful contribution to the consultation need, and role selection. It allows an `advisor` to explain a related real process without requiring area expertise, but still requires an explainable source-to-need bridge; a `direct_contact` needs work on this specific need. Historical work can support direct consultation about that work itself. The current implementation also requests a required contribution field, shared neutral model questions, and low area reasoning as described below; audit acceptance, retrieval, model/provider selection, and displayed card questions are unchanged from the pre-merge baseline. Offline contract tests do not establish improved semantic quality. The small combined-branch live comparison below cannot isolate the prompt or effort effects; any further matched observations need separate approval.

On new cards, the model's primary cited source is linked and its evidence is shown first; other citations remain available separately. Roles are explicitly **proposals**, not verified ownership or proof that the source answers the area's specific need. For an accepted contact, WorkBot checks the model's interview question for safe format but displays a neutral, source-type-specific question instead, so an unsupported premise is not copied into the card. A proposal with an unusable question is not automatically rescued: if it is otherwise eligible and no contact survives, the area is `review_incomplete`, not a misleading `not_found`. A genuine completed review with no supportable person remains `not_found`. Legacy cards stored without a primary-source field still render.

After the impact model returns areas, at most two independent per-area model calls run concurrently. Search and permissioned database reads stay on the request thread; completed areas are audited there before the final priority call. Card area order does not depend on completion order. Per-area durations can overlap and should not be summed to estimate total request time. This per-request limit does not guarantee a global provider concurrency limit across simultaneous demo sessions.

### Area output contract

Each area person proposal must include an English `contribution` string of 5-300 characters. The prompt requests a factual summary of the primary source's personal work/current duty, its potential contribution to the actual consultation need, and relevant scope limits, before selecting the role. A routing contribution still needs both current manager and visible remit evidence. The field is a bounded, **unverified model claim**, not an independently checked explanation or semantic score. Length/type checks cannot establish factual correctness; a missing/invalid live field fails the area schema rather than being silently filled. The audit does not use the prose to promote, downgrade, or retain a person, and it is not copied into card/session data, priority inputs, or diagnostic logs. The isolated synthetic probe may save it as part of a safe, validated response, separately from diagnostics.

`workbot/questions.py` is the shared immutable source of the four existing English neutral questions for routing, current responsibility, work, and record clarification. The area prompt asks the model to copy the appropriate question without customization; the card still replaces accepted model asks using the verified role/primary-source relationship. The `ask` field remains a bounded string, not a template enum. A format-valid non-template model question is still audited and replaced, while a malformed otherwise eligible proposal is omitted and can leave `review_incomplete`. Genuine empty/unsupported reviews remain `not_found`. Neither neutral wording nor the contribution field verifies that a cited source actually addresses the specific need.

Old captured proposals do not acquire new observed explanations. Only the offline replay scripts use `scripts/historical_models.py` to adapt missing historical contributions with the explicit unscored sentinel `Historical capture: contribution was not observed or scored.` The adapter preserves original asks/roles/citations and any explicitly captured contribution, including invalid values that must fail validation; it never mutates fixtures or repairs live responses. Existing saved cards need no new field or database migration. See [`docs/quality-evaluation.md`](docs/quality-evaluation.md) for implementation history and the separate offline/live observation boundaries.

### Matched area-only comparison

On 12 October 2026, three fixed synthetic contexts with two repetitions per arm compared pre-merge main `33ef28c` with combined `e77bee6`. All six calls per arm validated; median area-call duration was 41.011 s versus 25.464 s, and all 14 combined-arm asks matched the correct neutral text. Useful person/correct-primary controls and supported direct controls were retained, but decided unsupported direct claims remained four per arm and three contributions had malformed/incomplete endings. Frozen provisional counts, pending labels, original asks/contributions, usage, and separate assistant judgments remain in the [detailed comparison](docs/quality-evaluation.md#matched-main-versus-combined-candidate-area-comparison-12-october-2026) and [bundle](docs/evaluations/20261012-main-vs-combined/README.md).

This is a small combined-branch observation, not independent human validation, isolated effort causality, or a general quality/truncation/schema fix. Both arms already displayed neutral card questions. The merged combined version has not had a new full live UI-flow validation; impact, retrieval and priority were not rerun in this comparison. The approved 12-call budget is exhausted. See [handoff validation scope](docs/handoff.md#validation-scope-at-handoff) and [earlier web-flow history](docs/quality-evaluation.md#early-web-flow-and-provider-observations-before-the-combined-implementation) rather than treating older live cards as validation of current main.

### Model call diagnostics

`workbot.llm` emits one best-effort `model_call_summary` JSON log event per supported model invocation: `INFO` for a locally validated response, `WARNING` for a failure. The event contains only task, outcome, failure category, allowlisted validation error types, monotonic duration, HTTP status, an allowlisted finish reason, and provider-reported prompt/completion/total/reasoning token counts. It does not contain prompts, answers, names, area/session/source IDs, model text, headers, API keys, exception messages, or tracebacks. Service logs still report separate workflow outcomes. No diagnostic metadata is stored in cards or passed to priority.

To see successful events, enable `INFO` for the `workbot.llm` logger and allow it through your logging handlers. For example, in a Python launcher before starting the server:

```python
import logging
import uvicorn

logging.basicConfig(level=logging.WARNING)
logging.getLogger("workbot.llm").setLevel(logging.INFO)
uvicorn.run("workbot.main:app", host="127.0.0.1", port=8000)
```

If logging is already configured, adjust its handlers as well; Uvicorn's `--log-level` alone does not guarantee that the WorkBot logger emits `INFO`. Duration covers request preparation, HTTP, and local validation, not retrieval or the whole workflow. Logging/serialization failures are suppressed without changing the model result or error, so these events are not a guaranteed complete or persistent trace.

Failures distinguish configuration, timeout, transport, HTTP, invalid provider response, token truncation, other incomplete responses, non-text responses, invalid model JSON, and schema violations. A schema-valid empty review is a successful model response, not a transport failure. Missing or invalid usage is `null`, not zero; genuine zero is retained. Only non-negative signed-64-bit integer counts are accepted, without coercion or recomputing totals. Reasoning usage comes only from `usage.completion_tokens_details.reasoning_tokens` when supplied; it is not proof of the requested reasoning setting's effect. Counts are independent provider observations, not an assumed decomposition of the completion budget. Error HTTP bodies are not parsed for usage.

`validation_error_types` is a sorted, deduplicated list of fixed Pydantic codes on local validation failure: `json_invalid`, `missing`, `extra_forbidden`, `literal_error`, `string_type`, `string_too_short`, `string_too_long`, `string_pattern_mismatch`, `list_type`, `too_short`, `too_long`, `model_type`, and `value_error`. Unknown types become `other`; field paths, indices, messages, inputs, and validator context are never emitted. Its length is bounded by this vocabulary plus `other`, not by the number of errors. The field is `null` on success, other failure stages, or diagnostic extraction failure; if extraction fails, validation still raises the same safe `ModelError` with the generic `schema_invalid` category. These are error families, not exact field diagnoses: custom rules such as primary-citation consistency and unique people share `value_error`. The extension is offline-tested and does not recover the violated constraint from an earlier discarded response.

Diagnostics are observational: they do not tune prompts, schemas, audit, retrieval, model/provider settings, retries, or card states, and do not establish a token-cap fix or semantic improvement. Old captures remain unchanged and do not gain missing reasoning details. `httpx.Client(timeout=90)` sets network-operation timeouts, not a hard whole-call deadline. See the [dated GLM probe and lost-result history](docs/quality-evaluation.md#subsequent-four-invocation-glm-observation-30-september-2026-incomplete) for the observation boundary; a new live observation requires separate approval.

### Single-area observation harness

`scripts/area_probe.py` is a separate, opt-in synthetic test runner, not part of the web workflow. Each `run` command can make **at most one area invocation** using its checked-out implementation's `OpenRouter` settings (`area=low` on current main; `area=high` at the preserved pre-merge baseline tag). It does not run impact, retrieval, or priority, start Qdrant, read the demo database, retry, resume, or choose a fallback provider. Implementation/tests do not authorize a live test: obtain separate approval for the context and call budget before using `--approve-live`. The flag is an operator confirmation, not identity/permission enforcement or a global cost cap.

Prepare a single-context manifest **offline** using `prepare_manifest(payload, retrieved_ids)`. `payload` must have exactly `idea`, `answers`, the full current `Area` fields, and `candidates`; `retrieved_ids` must be the ordered captured visible work-record IDs. The helper uses a freshly seeded in-memory synthetic database and requires the supplied candidates, their order, and all evidence/name/title fields to exactly match the visible reconstructed pool. It pins hashes of the area prompt, LLM implementation, and requested area schema; stale manifests are refused, not silently refreshed. `synthetic: true` is a declaration, not automatic detection of real confidential text: keep ideas/answers synthetic and English. It supports the shipped seed fixtures only, not arbitrary real work records.

For example, with an already prepared synthetic context file containing `payload` and `retrieved_ids`, run this in the configured Python environment; it makes no model call:

```python
import json
from pathlib import Path
from scripts.area_probe import prepare_manifest

context = json.loads(Path("/tmp/opencode/probe-context.json").read_text())
manifest = prepare_manifest(context["payload"], context["retrieved_ids"])
with Path("/tmp/opencode/probe-manifest.json").open("x") as file:
    json.dump(manifest, file, indent=2)
```

Only after separate live-call approval:

```bash
uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.area_probe run --manifest /tmp/opencode/probe-manifest.json --output /tmp/opencode/probe-observation-001 --approve-live
```

Use one standalone process per observation. In OpenCode, launch long approved observations with the shell tool's `background: true`; elsewhere use a job runner with an adequate lifetime. Do not place several calls under the earlier shared 420-second foreground deadline. This runner adds no hard total-call deadline and does not change HTTPX's network-operation timeout. Terminating the local process does not establish that provider work or billing stopped.

The output directory must not already exist: an exclusive directory claim prevents concurrent duplicate starts, and an existing directory is never reused, even after a write/preflight failure. `manifest.json` is saved first, then `attempt.json` before invoking the model; `summary.json` is persisted directly from the allowlisted diagnostic event, before the model call returns. Schema-valid, visibility-checked outputs go into `response.json` **before** audit; `audit.json` is separate and `execution.json` marks normal completion, a caught `ModelError`, or best-effort keyboard interruption. JSON files use same-directory atomic replacement, file/directory flushes, and private file permissions. Persistence errors before invocation prevent a call; errors after invocation never cause a retry. A missing diagnostic cannot invalidate the model's return/error, but makes the observation incomplete; an available safe response is still saved before stopping. Abrupt termination or disk failure can still leave incomplete observations, so this is not a guaranteed complete provider trace.

Only the fixed diagnostic contract is copied into `summary.json`; raw bodies, headers, secrets, exception messages/tracebacks, validation inputs/context, and error locations are not captured. Input manifests and validated response/audit files are separate visible **synthetic** observations and can contain synthetic people/source IDs; they are not production diagnostic logs or stored web sessions. Restricted/unknown candidate or citation IDs and known restricted synthetic text prevent response persistence. The runner temporarily isolates the WorkBot summary logger and restores its configuration; do not embed it in a running app or run multiple observations concurrently in the same process.

Inspect artifacts **offline**, including while an observation is pending:

```bash
uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.area_probe inspect --output /tmp/opencode/probe-observation-001
```

`stage` reports the furthest artifact present, not process liveness or semantic quality; `execution_status` reports a separately saved terminal marker or `unknown`. A started invocation without a summary has unknown call/provider outcome, not timeout, truncation, or abstention, and conservatively consumes one approved invocation. The production logger may emit a failure summary from `finally` during interruption, so a failure event alone is not proof that the call returned `ModelError`: `inspect` confirms failure/category only with the caught-`ModelError` execution marker. An unconfirmed failure event remains unchanged in `summary.json`, but reported call outcome is `unknown`; any observed HTTP status/usage remains available. A success summary establishes local schema validation, not that response persistence or audit finished. Recorded transport/timeouts may also leave provider outcome unknown; an HTTP response is reported only when observed. `usage_available` means at least one provider count is present, not complete usage or cost. Exit code zero can include a properly recorded model failure; inspect `call_outcome`/`failure_category`. Do not rerun an interrupted context in a new directory without fresh approval, and count started invocations across directories against the approved experiment limit yourself. The runner neither reconstructs the lost fourth GLM result nor authorizes its replacement.

### Offline quality replay

The [quality evaluation reading guide](docs/quality-evaluation.md#current-status-and-reading-guide) distinguishes current behavior from historical benchmarks and assistant/user labels. The [archived 30 September problem analysis](docs/archive/problem-analysis-20260930.md) is a historical diagnosis, not the next implementation plan. The tools below read existing synthetic observations without paid model calls; they do not rerun model generation or certify semantic quality.

Run `uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.quality_eval` to replay the sanitized 27 September synthetic card against a freshly seeded temporary SQLite database. This replay makes **no OpenRouter or Qdrant request** and does not change the running demo data. It compares captured retrieval IDs, candidates, model role proposals, and the deterministic audit against 17 curated area/person examples, including five user-adjudicated borderline cases. Three further user-approved synthetic ideas were each run live once and have separately recorded **target-area-only observations**; the offline tool validates those observations but cannot replay their missing full model/search context. See [`docs/quality-evaluation.md`](docs/quality-evaluation.md) for the rubric, results, and limitations. A handful of live cards does not establish general model reliability or stakeholder-discovery quality.

Run `uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.trace_diagnostics` for a separate **offline**, sanitized six-run DeepSeek/Nitro diagnostic. It reports stage failures and access checks without rerunning the model. The original observations in `quality_live_traces.json` remain unmodified and unadjudicated; `quality_trace_labels.json` contains **assistant-reviewed**, source-based labels, not independent user sign-off or ground truth. The user-approved advisor rubric allows explaining a related real process to help understand the consultation need or approach the appropriate practitioner, without requiring area expertise. Contact usefulness, unsupported direct claims, and question premises are scored separately; undecided labels are excluded only from their relevant denominators. These captured cards predate the neutral-question/status presentation changes, and the experimental model/provider is **not** the configured application default. See [`docs/quality-evaluation.md`](docs/quality-evaluation.md) for counts, provenance, and limitations.

Run `uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.trace_audit_replay` to apply the **current audit only** to those captured proposals and search results using a fresh synthetic database. It does not rerun impact, retrieval, model generation, or the priority call. The recorded people, roles and sources are unchanged in all 26 replayable areas; two earlier `not_found` outcomes become `review_incomplete` because an otherwise eligible advisor's question was malformed. These are audit/presentation deltas, not evidence that semantic contact quality improved.

For the three historical DeepSeek low-reasoning runs, use `uv run --python 3.12 --no-project --with-requirements requirements.txt python -m scripts.trace_diagnostics --traces tests/fixtures/quality_low_traces.json --labels tests/fixtures/quality_low_labels.json`. The observations and separate assistant labels remain immutable; see the [dated trials and limits](docs/quality-evaluation.md#three-opt-in-low-reasoning-trials). These are not observations of the shipped GLM low-area implementation or a controlled high/low comparison.

## Development

Run these offline checks from the repository root; the `uv run` prefix provides Python 3.12 with the pinned requirements. Start with tests relevant to the change, and run the full suite for shared changes.

```bash
uv run --python 3.12 --no-project --with-requirements requirements.txt python -m pytest -q
uv run --python 3.12 --no-project --with-requirements requirements.txt ruff check workbot tests scripts
uv run --python 3.12 --no-project --with-requirements requirements.txt ruff format --check workbot tests scripts
git diff --check
```

The formatting command above only checks files; use `ruff format` on affected files when an edit is needed. The same checks can run without the `uv run` prefix in an activated Python 3.12 environment with `requirements.txt` installed. Tests use offline stubs/local fixtures, including a local in-memory Qdrant client for search tests. A live run additionally requires Docker/Qdrant, an OpenRouter key, and explicit approval of the test scope/budget: submitting a synthetic idea in the web UI makes paid model calls. After approval, inspect its area/source card and reload without regenerating it. Keep this guide current when setup, behavior, or limitations change. Review `AGENTS.md` alongside relevant code changes and update agent instructions when needed; neither file requires an unrelated edit just for the sake of touching it.

`requirements.in` lists direct dependencies (lightweight ONNX/CPU embeddings); `requirements.txt` is the compiled lock file. After changing dependencies:

```bash
uv pip compile requirements.in --python-version 3.12 -o requirements.txt
```

## Layout

```
compose.yaml        # Qdrant (default) + optional app container via `--profile app`
requirements.in/txt # dependency pinning
.env.example        # template; copy to .env (untracked)
workbot/            # application package (app entrypoint: workbot.main:app)
tests/              # pytest suite
docs/               # hackathon brief & design notes
```
