# WorkBot: coding-agent guidance

## Start here

Read this file for working rules, then the code and tests relevant to the task. Use [`README.md`](README.md) for setup and current behavior. Establish implemented behavior from code and tests, not from proposals.

## Document roles

- [`README.md`](README.md) is the human-facing guide to current setup, behavior, and limitations.
- This file is for coding agents: how to work here, where things live, and the rules the code must keep.
- [`docs/archive/proposed-stakeholder-routing-design.md`](docs/archive/proposed-stakeholder-routing-design.md) is the user's original Turkish design draft: a **non-binding idea guide**, not a specification or checklist. Confirm proposed product changes with the user before treating them as requirements.

## Competition context

- [`docs/competition.md`](docs/competition.md) is a dated working brief for the hackathon. WorkBot follows the **simulated Alexa+ web experience** route; do not impose the separate Agent Skill/MCP route's requirements on this prototype.
- [`docs/demo-video.md`](docs/demo-video.md) is a **working draft** of the demo-video script; the user will revisit it. Do not treat its lines or timings as settled, and keep its claims within what the code does. Its story is told on a saved plan on the hosted demo, quoted word for word as the Devpost text quotes it; before recording, recheck that plan against the hosted page, and write the live segment only after a fresh, user-approved live run.
- [`docs/friction-log.md`](docs/friction-log.md) is the friction log submitted for the optional bonus (see [`docs/competition/submission.md`](docs/competition/submission.md#optional-but-useful)). When AWS or Bedrock setup, docs, or SDKs cause friction, add an entry in its format with the exact error text and request IDs, never account IDs, keys, or other secrets.
- [`docs/competition-winner-patterns.md`](docs/competition-winner-patterns.md) compares winners from other competitions: possible inspiration, not contest rules, requirements, or proof of what wins.
- For submission or eligibility decisions, recheck the [live official rules](https://amazonappdev2026.devpost.com/rules); they take precedence over the local extract and working briefs. Ask the user about unclear or conflicting requirements. Do not copy dates, prizes, or other changeable rules into agent instructions. Do not modify `docs/competition/` unless the user explicitly asks.

## Removed evaluation history

The earlier evaluation apparatus (scripts, captured traces and labels, comparison bundles) was deleted on the user's decision, tags included. Do not restore it or rebuild something similar without asking; prefer a few end-to-end checks with pre-written expectations over per-call micro-experiments.

## Product and language boundaries

- WorkBot is a **synthetic, simulated Alexa+ web experience**, not an official Alexa+ integration, and uses no Alexa API; Amazon Bedrock serves only as the model provider. It shows consultation areas, evidence-backed people and roles, what to find out in each area, and uncertainty; it does not send messages, create invitations, or record coordination.
- Do not claim real identity or permission controls, production security or scale, or exhaustive stakeholder discovery.
- **English is the operational language**: demo ideas, clarification answers, synthetic records, search intents, prompts and requested responses, UI copy, questions, and cards; keep `README.md` and this file in English. This is a convention, not runtime language detection.
- Use synthetic inputs only. Never include `.env` secrets in code, logs, tool output, or commits. Live model calls (Amazon Bedrock, or OpenRouter when selected) transmit prompts and incur cost; run them only when the user explicitly approves a live test and its budget, and distinguish their results from offline tests. Submitting an idea through the web UI is a live call, and so is pressing **Listen**, or letting a newly arrived question, plan, or follow-up answer be read aloud (on unless the visitor turns it off), which sends the shown text to Amazon Polly, or using **Speak**, which sends the recording to Amazon Nova 2 Sonic on Bedrock.

## Repository map

- `LICENSE`: MIT (copyright holder: Furkan); keep it at the root so GitHub detects it.
- `compose.yaml`, `Dockerfile`, `.dockerignore`, `.env.example`: local Qdrant and optional app container (non-root, embedding model downloaded at build time; `.env`, `data/`, `.git` kept out of the build context). `requirements.in` lists direct dependencies; `requirements.txt` is the compiled Python 3.12 lock.
- `deploy/`: the optional hosted demo. `workbot-ec2.yaml` is a CloudFormation template for one EC2 server; `compose.yaml` runs Caddy, the app, and Qdrant there.
- `workbot/main.py`: FastAPI routes, the server-rendered flow, the hosted-demo guards (`access_gate`, `WORKBOT_DAILY_IDEAS`), source pages, speech endpoints, `/transcribe`, and follow-ups (`/sessions/{sid}/ask`).
- `workbot/models.py`: strict Pydantic schemas for the three model tasks.
- `workbot/service.py`: session orchestration, the area model calls in parallel, the deterministic evidence audit, card states, and in-memory progress. `run` calls `_ask_impact`, `_review_areas`, `_apply_priority` in order.
- `workbot/search.py`: visible BM25/Qdrant retrieval fused by reciprocal rank (per intent: records both channels returned plus each channel's top three, at most eight per area) and candidate selection (up to ten work-link candidates by link strength then retrieval rank, current visible responsibilities, manager plus remit), and `directory_hints` for the impact call.
- `workbot/plan.py`: pure functions that turn a stored card into the plan at the top of the page (`headline`, `lead`, `spoken`, `invite`, `groups`, `more`, `gaps`, `order`, `people`, per-person `short`, `ended_short`, `ended_full`, `ended_source`) and rewrite evidence lines into plain words at render time.
- `workbot/followup.py`: pure functions for follow-up questions: `resolve` (rule matching to a kind and to people on the card), `reply` (the answer), `chips` (up to four suggestions).
- `workbot/llm.py`: the three structured tasks behind `complete(task, payload)` on two providers: `Bedrock` (default; Converse API on `WORKBOT_BEDROCK_MODEL`, default `global.amazon.nova-2-lite-v1:0`) and `OpenRouter` (`WORKBOT_MODEL_PROVIDER=openrouter`, pinned endpoint, strict JSON schema). Both keep local Pydantic validation: a strict JSON-schema request does not prove the provider enforces the local cross-field rules.
- `workbot/speech.py`: Amazon Polly for **Listen** (`Speech.audio`, last 64 texts cached).
- `workbot/transcribe.py`: Nova 2 Sonic speech to text for **Speak** over Bedrock's bidirectional stream (`aws-sdk-bedrock-runtime` with the CRT transport; boto3 and the SDK's default aiohttp transport cannot stream both ways, and Amazon Transcribe is not open to this account).
- `workbot/storage.py`: SQLite schema, visibility helpers, sources, `directory_claims`, and the dependency snapshot that makes a stored card fail closed.
- `workbot/seed.py` and `workbot/fixture/`: the synthetic company (`directory.json`: org units, people, managers, remits, responsibilities, each claim with its own source and visibility; `records.json`: work records with person links), built around topic clusters with hard cases plus unrelated background records.
- `workbot/templates/`: English server-rendered UI with a single light theme. `base.html` (the only stylesheet, inline plain CSS with custom properties and no framework, build step, or web font; the inline SVG favicon, so no `/favicon.ico` request; the simulation disclaimer; the `#page` wrapper, then `_script.html`, the only script), `home.html`, `session.html`, `source.html`, `access.html`, `setup.html`, `error.html` (every `HTTPException`).
- `tests/`: all offline. `test_workflow.py` (states, audits, visibility), `test_search_and_ui.py` (search and HTTP flow), `test_llm.py` (model contracts, call log, Polly and Sonic clients), `test_plan.py`, `test_followup.py`, `test_fixture.py` (fixture validity and `tests/expectations.json`, the answer key for seven demo ideas; keep it). `tests/unit_seed.py` is a separate nine-person dataset for workflow and search unit tests. The root `conftest.py` blanks provider keys, settings, the access code and daily limit, leaves boto3 no AWS credentials (it deletes `AWS_BEARER_TOKEN_BEDROCK` and the container-credential variables rather than blanking them, because botocore still uses empty ones), and points the database and Qdrant away from real ones, because `workbot.main` loads `.env` on import; keep that guard. Bedrock tests use botocore's `Stubber`.
- `docs/competition/`: local rules extract (the live rules supersede it), Alexa+ routes, submission checklist, judging, mini-challenges, prizes.

## Rules the code must keep

### Visibility and privacy

- Restricted sources, and people known only through them, must not enter accessible search, model context, cards, source views, or user-visible signals. A title match without visible evidence must not expose a restricted-only person; mention-only people are not work candidates.
- A source page opens only a source the valid card cites (a person's `evidence_ids`, or the `context_ids` of an ended-duty note), checks visibility on every view, and never shows the raw source ID; `directory_claims` names only active people.
- A name not on the card gets the same follow-up answer whoever it belongs to, and no reply repeats the question.
- Follow-ups are never stored: earlier questions come back with the form (`prior-0` to `prior-4`), so one visitor's questions never reach another on the shared hosted plans.

### Model tasks and the audit

- Keep the three model task types (impact, per-area evaluation, card-wide priority) and at most two sequential clarifications; a skipped clarification ends the question budget. Follow-up questions call no model: the user chose rule matching over a fourth, selection-only task, so keep it that way unless the user decides otherwise.
- Keep `mapping_unresolved`, `not_found`, `review_incomplete`, and request-level refusal distinct. A review in which the model proposed nobody stays `not_found`.
- The priority call orders areas and may pick up to four already-audited people; it never adds a person or changes a role. A missing or over-long choice is tolerated so it cannot discard the area order. It receives the idea, the clarification answers, and the areas, never `ended_duty`, `context_ids`, rejection flags, or diagnostics; check the shared question before reordering so a guard error leaves the original order. A shared question that nearly repeats an area's `consultation_need` (similarity 0.9 or more after lowercasing and dropping punctuation) is dropped.
- Wait for all areas before the priority call; isolate area failures as `review_incomplete`. Keep SQLite, search, permission reads, and audits on the workflow thread; only independent area model requests go to the worker threads (six). Card area order does not depend on completion order.
- A `direct_contact` needs `relevance=direct` plus a strong work or current-responsibility tie on the single primary source. `adjacent`/`weak` proposals are kept as advisors; an advisor's primary source must be a work, reporter, or current-responsibility tie; `mention`-only evidence is not proposed. A routing contact needs both current manager and visible remit evidence and is hidden when a direct contact exists or a direct proposal was broken.
- A *broken* direct proposal (a person or source outside the pool, an inactive person or one in another team, a source no longer visible or current, an uncited primary, a repeated citation) marks the review unreliable: `review_incomplete` when nobody else is left, and once any direct proposal is broken no manager is added. An *overclaimed* one (real evidence that does not show direct work, or the model's own `adjacent`/`weak`) becomes an advisor when its primary is an advisor tie and is dropped otherwise; if that leaves no direct or routing contact, the audit adds the pool's single current manager with a visible remit.
- The direct-contact evidence requirement lives in the audit, not the schema, so one inconsistent role field cannot void a whole area review. The audit verifies visibility and link strength, **not** whether a source is semantically relevant to the area.
- `PersonProposal.contribution` (5-600 characters; the prompt asks for under 250, before the role) stays in the schema so the model writes it before choosing the role (do not tighten the 600 cap to the prompt's 250: a provider enforcing it would cut sentences), but it is never put on the card, shown, logged, or passed on: shown as an unverified summary it once misstated a record. The model writes no per-person question or caution.
- Evidence lines in `why` name no source ID and are written primary source first, then the other citations in `evidence_ids` order; `plan.py` relies on that order to link each line.
- An `ended_duty` note is attached when an accepted person has a visible responsibility that has ended and shares a word stem with the area (label, `consultation_need`, or keyword search intents; Porter stems as in `search.stems`, without stop and generic process words), unless they hold a current one that also does. The model never sees expired duties; the note's source goes in `context_ids` so the card fails closed if it changes or stops being visible.
- A routing contact's plan line says no one was identified from the visible work (or that no direct contact was established when an advisor is shown beside them); it must not claim the search found nothing, because retrieval always returns records. It is built from the manager and remit records, so the plan never links it to the primary source; the full list links each source.
- `directory_hints` gives the impact call, per org unit, at most one current, visible duty of an active person that shares at least two Porter stems with the idea and answers (stop and generic process words excluded), at most three units, as org unit ID and duty text only: no person, no source ID, never an ended or restricted duty. Like uncited search results, hints are not in a card's snapshot, so a later change to a hinted duty does not mark the card out of date; do not move duties or remits into `org_inventory`, whose digest would fail every stored card closed.
- Prompt rules that live runs depended on: the impact prompt allows a clarification only when the areas cannot be told without it (never for amounts, dates, or details that do not change the areas), keeps it on the idea itself, and forbids asking which reviews, approvals, laws, compliance checks, teams, systems, or owners the idea involves, who handles something today, or repeating an answered question. Directory hints decide only which areas to include: rationale and `consultation_need` come from the idea, because the per-area call receives the rationale, and a rationale copied from a current reviewer's duty made live runs pass over the former approver (Omar was named in 1 of 10 runs, against 7 of 10 before hints). It reserves `mapping_unresolved` for an area no org unit fits; uncertainty or a skipped question is not a reason (the older wording left Legal and Compliance without a team in almost every run). The 110-character `consultation_need` and 160-character shared question are prompt requests only; do not tighten the schema caps to match.

### Plan, voice, and follow-up answers

- `headline`, `lead`, and `spoken` are built only from plan data (names, home areas, a routing contact's role, an `ended_duty` role and month, area and open-area counts), never from model prose, so the voice cannot say more than the panel. They say a person is "in" an area only when everyone named there belongs to its org unit (or the card has no `org_id`), and "for" it otherwise. Follow-up answers likewise use only text the page shows, so panel and voice say the same thing.
- `plan.py` only regroups and reorders, never adds or drops people, and must tolerate older cards without `org_id`, `team`, `primary_kind`, `headline`, `primary_evidence_id`, or `context_ids`, and evidence lines that still end with a bracketed source ID.
- In `followup.py`, near matches for a misheard name are allowed only for a capitalized word with the same first letter and length within one, never for an area or team word or a listed common word; `unlisted` needs a capitalized, non-acronym word that does not start a sentence. Only `why` links its line's source; `prep` does not, because a link after its model-written question would seem to back it.
- Polly receives only text the page shows: `speech.mp3` reads the valid card's `plan.spoken` or the pending question, and `reply.mp3` the answer `followup.reply` builds; the visitor's question is never sent to Polly.
- Show the area's `consultation_need` as "What to find out", the fixed cautions before the full list and at its end, and never the impact model's `rationale` or `mapping_reason`.

### Runtime, hosting, and logging

- `POST /sessions` and `/answer` store the request, start the workflow on a background thread, and redirect at once; only a newly created session starts a run, so a repeated idempotency key cannot start a second one. A new idea or answer first calls `Searcher.check`; a `SetupError` renders `setup.html` (503) before anything is stored or sent, with plain setup advice.
- A live run has a progress entry from before its session becomes `processing` until after it leaves that state; the session page closes a `processing` session without one as a refusal. Keep that ordering and a single app process. Progress holds only a stage and area labels with a done flag, never people, sources, counts, or diagnostics.
- The hosted guards are off when unset and are not real authentication: the access cookie holds an HMAC of the code, never the code; attempts are rate-limited before the comparison; `next` accepts only a path on this site; a bad `WORKBOT_DAILY_IDEAS` stops new ideas with a 503; the daily count is taken before a new session is stored and returned if nothing new was stored, and a known idempotency key is never counted.
- `POST /sessions/{sid}/ask` needs a `card` session (409 otherwise) whose card is still valid (410), and questions of 1 to 200 characters. `/transcribe` is same-origin, size-capped while reading, and rate-limited; its text only fills the box and never starts a run. Every `HTTPException` message must be a plain sentence fit for users.
- `deploy/compose.yaml` publishes only Caddy's ports; the app trusts forwarded headers only because nothing else can reach it, so never publish the app's or Qdrant's port. Keep the instance role's permissions (Nova 2 Lite, Nova 2 Sonic, Polly) in step with what the code calls.
- Bedrock: Nova 2 Lite rejects `outputConfig` and `strict` tools, so each task forces a single tool with the task's schema, local validation enforces it, and a reply counts only with `stopReason` `tool_use` and exactly one call of that tool. Extended thinking stays low (medium spent the whole output cap in live runs; high forbids the cap). Pass `AWS_REGION` explicitly; boto3 reads only `AWS_DEFAULT_REGION`. Missing credentials, profile, Region, key, or an unknown provider fail as `not_configured` before any prompt is sent.
- A reply that fails local validation, or ends without an answer for a reason other than the output cap, is requested once more; a cut-off reply, a context overflow, a service error, an unexpected shape, or missing setup is not.
- Each model request writes one `model_call_summary` line of fixed codes and numbers only; never log prompts, provider text, validation inputs, messages of exceptions WorkBot did not raise, identities, IDs, or secrets, and never put this metadata on cards, sessions, or priority inputs. `speech.py` and `transcribe.py` log only the exception class; `SpeechError` and `TranscriptionError` messages are shown to users and must be plain sentences. Never enable `DEBUG` for botocore or the `smithy_*` and `aws_sdk_*` loggers: they log whole requests, prompts, audio, and transcripts.
- Sonic (`transcribe.py`): credentials and Region come from boto3's chain like the model calls, so the test setup keeps it offline; 16 kHz 16-bit mono PCM of at most 20 seconds; keep only the USER role's `textOutput` across every user turn; stop 1.5 s after the last user text or 8 s after sending with none; time out after 30 s and close the stream within 2 s.

### Templates and script

- `_script.html` runs `setup(root)` on the page and on every page it swaps in, so its code must not assume a fresh document, and no template may put a `<script>` inside `#page`. Forms marked `data-swap` are sent with `fetch` and replace `#page` in place (`history.pushState` when the address changes; a native submission when anything goes wrong); a swap removes parsed `<noscript>` elements, and stops audio, older polls, and any recording. Only a question, plan, or follow-up answer that arrives through a swap is read aloud on its own (the newest answer carries `data-speech-auto`), and only on a page the visitor has clicked.
- Example buttons on `home.html` only fill the idea box and must each be an idea in `tests/expectations.json` (checked by `test_fixture.py`). "Read answers aloud" has no `name`, so it is never sent.
- Tests split the card page on `<details class="all">` to tell the plan from the full list; keep that marker.

### Fixture

- Keep every text within 400 characters, never name a person in a record without linking them, and keep people known only through restricted sources free of any visible footprint; `test_fixture.py` enforces these.
- Anders Holm's tie to spending-policy changes is a directory responsibility only; a work record about it made live runs pass over Omar and his ended-role note, so do not add one.
- Pickup lockers is not an example button: its fixture has no relevant record by design.

## Working with the user and other agents

- Inspect the working tree and relevant tests before editing; preserve existing user changes.
- If the request, scope, or intended behavior is unclear, **ask the user before proceeding rather than guessing**. Do not silently turn a design-draft idea into current behavior.
- The user's quality goal is **no obvious errors**, not resolving every edge case, and the aim is to win the competition. Prefer fixes that remove visible mistakes over further calibration of debatable cases.
- Keep the repository small. Do not add experiment logs, dated reports, or preserved artifacts unless the user asks; delete superseded material instead of archiving it in place (the design draft in `docs/archive/` is kept on purpose).
- Delegation is optional. Communicate with subagents in English and integrate and verify their findings yourself.

## Validation and documentation upkeep

- Start with tests relevant to the change. Run checks with the repository's `.venv` (Python 3.12 with `requirements.txt`, created as in the README's Setup): `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check workbot tests conftest.py`, and `.venv/bin/ruff format --check workbot tests conftest.py`; if formatting is needed, run `ruff format` only on the affected files. Only when there is no `.venv`, prefix the commands with `uv run --python 3.12 --no-project --with-requirements requirements.txt`; do not create or delete the `.venv` without asking. Run `git diff --check` after edits. Offline stub tests do not certify live model quality.
- **With every relevant code change, review `README.md` and this file and update them in the same change when needed.** Keep human setup, behavior, and limitations in README; keep agent workflow, the map, and the rules here. Do not make unrelated documentation edits merely to touch these files.
- After finishing an implementation and before opening a pull request, review your own diff as a reviewer would: correctness, leftover references, weakened tests, and documentation that no longer matches. Fix what you find and tell the user what the review found.
- Write Markdown as one logical line per bullet or paragraph; do not manually hard-wrap prose at a fixed column.
