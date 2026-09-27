# WorkBot: coding-agent guidance

## Document roles

- [`README.md`](README.md) is the human-facing guide to current setup, behavior, and limitations.
- This file is for coding agents: how to work here and keep documentation accurate.
- [`docs/proposed-stakeholder-routing-design.md`](docs/proposed-stakeholder-routing-design.md) is a **non-binding proposal and roadmap**, not a specification of current behavior or an automatic implementation checklist. Confirm proposed product changes with the user before treating them as requirements.
- [`opencode.jsonc`](opencode.jsonc) configures OpenCode, including the models used by its built-in subagents. Do not duplicate model IDs here. Check the code and tests to establish implemented behavior.

## Competition context

- [`docs/competition.md`](docs/competition.md) is a dated working brief for the hackathon. WorkBot follows the **simulated Alexa+ web experience** route; do not impose the separate Agent Skill/MCP route's requirements on this prototype.
- [`docs/competition-winner-patterns.md`](docs/competition-winner-patterns.md) compares winners from other competitions. Treat its examples as possible inspiration, not contest rules, WorkBot requirements, or proof of what wins.
- For submission or eligibility decisions, recheck the [live official rules](https://amazonappdev2026.devpost.com/rules). They take precedence over the local rules extract and working briefs. Ask the user about unclear or conflicting requirements; if a Rules term itself is ambiguous, recommend written clarification from the organizers rather than resolving it from a less authoritative page. Do not copy dates, prizes, or other changeable rules into agent instructions.

## Product and language boundaries

- WorkBot is a **synthetic, simulated Alexa+ web experience**, not an official Alexa+ or Amazon API integration. It shows consultation areas, evidence-backed people and roles, questions to ask, and uncertainty; it does not send messages, create invitations, or record coordination.
- Do not claim real identity or permission controls, production security or scale, or exhaustive stakeholder discovery. Preserve visibility checks: restricted sources and people known only through them must not enter accessible search, model context, cards, source views, or user-visible signals.
- Preserve the three model task types (impact, per-area evaluation, card-wide priority) and at most two sequential clarifications. Keep `mapping_unresolved`, `not_found`, `review_incomplete`, and request-level refusal distinct.
- **English is the WorkBot operational language.** Write demo project ideas and clarification answers, synthetic work records, search intents, model prompts and requested responses, UI copy, and displayed questions/cards in English. Keep `README.md` and this file in English. The Turkish proposal is not product copy. This is a product and development convention, **not** a claim that the application detects or rejects other languages at runtime.
- Use synthetic inputs only. Never include `.env` secrets in code, logs, tool output, or commits. Live OpenRouter calls transmit prompts and incur cost; run them only when the user explicitly requests a live test, and distinguish their results from offline tests.

## Repository map

`workbot/` is the application package, `tests/` contains offline regression tests, and `docs/` holds design and competition research. Key paths:

- `compose.yaml` runs local Qdrant and, optionally, the app; `.env.example` is the configuration template, while `.gitignore` excludes secrets and generated files. `requirements.in` lists direct dependencies; `requirements.txt` is the compiled Python 3.12 dependency lock.
- `workbot/main.py`: FastAPI routes and server-rendered flow.
- `workbot/models.py`: strict structured-output models and schema validation. Each `Area` carries a `consultation_need`; each `PersonProposal` carries a `primary_evidence_id` (must be one of its citations) and a `relevance` of `direct`/`adjacent`/`weak`. Keep the direct-contact evidence requirement in the audit, not the schema, so one inconsistent field cannot void a whole area review.
- `workbot/service.py`: session orchestration, bounded concurrent per-area model calls, evidence audits, and card states. Keep SQLite/search/permission reads and evidence audits on the request thread; only independent area model requests belong in workers. Wait for all areas before the card-wide priority call, keep area failures isolated as `review_incomplete`, and discard an unsafe shared question without discarding a valid priority order. Check the question before reordering so a guard error leaves the original card order intact. An advisor may cite a current visible responsibility for a narrow question; manager/remit or title alone still cannot justify that role. A `direct_contact` needs a strong work or current-responsibility tie on the model's single `primary_evidence_id`, not merely somewhere in the citation list; a proposal the model itself marks `adjacent`/`weak` is kept as an advisor, and `mention`-only evidence is not proposed. These checks verify visibility and link strength, not area-specific semantic relevance.
- `workbot/search.py`: visible BM25/Qdrant retrieval and directory candidate selection.
- `scripts/quality_eval.py` and `tests/fixtures/quality_baseline.json`: offline replay of sanitized live observations against fresh synthetic fixtures, not a general quality guarantee. Five borderline baseline labels were adjudicated by the user; any future pending labels must not count toward scores. `tests/fixtures/quality_scenarios.json` contains approved synthetic references and one-run target-area observations, not replayable full search/model traces. In candidate selection, title matches without visible evidence must not expose restricted-only people to model context.
- `workbot/storage.py`: SQLite schema, visibility, sources, and reload snapshots.
- `workbot/llm.py`: three structured OpenRouter model tasks, pinned to a tested parameter-compatible provider endpoint with local schema validation. Do not treat a strict JSON-schema request as proof that the provider enforces local cross-field rules; do not log raw provider bodies or silently accept malformed responses.
- `workbot/seed.py`: small synthetic fixtures and index seeding.
- `workbot/templates/`: English server-rendered UI and source views.
- `tests/test_workflow.py`: session states, evidence audits, and visibility rules; `tests/test_search_and_ui.py`: hybrid search and HTTP flow; `tests/test_llm.py`: model request and response contracts; `tests/test_quality_eval.py`: offline replay stage attribution and visibility checks. These are offline tests.
- `docs/competition/`: `rules.md` is a local extract (the live rules supersede it); `alexa.md` distinguishes the two Alexa+ routes; `submission.md` is the submission checklist. Read its judging, mini-challenge, and prizes notes only when relevant. See the document roles and competition context above for the other root-level and `docs/` files.

## Working with the user and other agents

- Inspect the working tree and relevant tests before editing; preserve existing user changes. Do not modify competition rules under `docs/competition/` unless the user explicitly asks.
- If anything about the request, requirements, scope, or intended behavior is unclear, **ask the user before proceeding rather than guessing**. Do not silently turn a roadmap idea into current behavior.
- Delegation is optional and is the main agent's decision. Use the built-in `explore` subagent for focused discovery or `general` for useful independent multi-step work. Independent tasks may run in parallel; dependent tasks may run sequentially. Communicate with subagents in English and integrate and verify their findings yourself. See `opencode.jsonc` for their configuration.

## Validation and documentation upkeep

- Start with tests relevant to the change. For Python changes, check the affected code with `ruff check workbot tests` and `ruff format --check workbot tests`; run broader tests when shared behavior is affected. Run these commands from an activated Python 3.12 environment with `requirements.txt` installed, or prefix them with `uv run --python 3.12 --no-project --with-requirements requirements.txt`. For example, run tests with `uv run --python 3.12 --no-project --with-requirements requirements.txt python -m pytest -q`. Run `git diff --check` after edits. Offline stub tests do not certify live model quality.
- **With every relevant code change, review both `README.md` and `AGENTS.md` and update them in the same change when needed.** Keep human setup, behavior, and limitations in README; keep agent workflow and code guidance here. Do not make unrelated documentation edits merely to touch both files. Preserve the proposal's non-binding status.
- Write Markdown as one logical line per bullet or paragraph; do not manually hard-wrap prose at a fixed column. Keep headings, fenced code blocks, and tables line-structured, and let the editor soft-wrap the display.
