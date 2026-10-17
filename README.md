# WorkBot

**Amazon Developer Hackathon — Alexa+ track (simulated web experience route)**

Before you change how something works at a company, you need to know who to involve. Job titles and org charts do not say who handles a decision today or who only used to.

WorkBot is a simulated Alexa+ experience: Maya describes a project idea and gets, as a short conversation, a plan of who to talk to first, with evidence-backed contacts, what to find out from each, and explicit gaps. The home page offers three example ideas that only fill the idea box (sending one is still a live model call) and lists her earlier ideas; a plan whose evidence or access has changed since is not shown when opened and is reported as no longer valid instead. It searches synthetic work traces and a structured directory; it does not make project decisions or contact people.

For example, Maya asks: *"Raise the approval threshold for marketing spend requests so small changes need no review."* In one stored run, WorkBot answered "Before you start, talk to four people." These were the Finance reviewer who currently handles such requests, the author of the 2024 approval policy (shown with a directory note that this person's approver duty has ended), the marketer who requested the Q4 budget reforecast, and a Legal colleague who wrote notes on when supplier agreements still need a wet signature. Each comes with its evidence, linked to the source records, and what to find out from that area. The people and wording vary from run to run.

> ⚠️ **Disclaimer:** This is **not** an official Alexa integration or Amazon API integration. Use **synthetic project ideas only**: prompts are sent to OpenRouter. The directory and work traces are fictional. No messages or invitations are sent to anyone. WorkBot's input and output language is **English**: enter ideas and clarification answers in English; synthetic records, search intents, prompts, and displayed questions/cards are written in English. This is a product convention, not automatic detection or rejection of other languages at runtime.

## Documentation

- This `README.md` is the human guide to the current prototype and its limits.
- [`AGENTS.md`](AGENTS.md) guides coding agents working in this repository.
- [`docs/archive/`](docs/archive/) preserves the original non-binding Turkish design proposal; it is not current behavior or an active implementation plan.
- [`docs/competition.md`](docs/competition.md) is a dated working brief for the hackathon; recheck the [live official rules](https://amazonappdev2026.devpost.com/rules) before submitting.
- [`docs/demo-video.md`](docs/demo-video.md) is a working draft of the demo-video script; it is not final and will change.
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

# 3) Seed synthetic data (creates/loads the Qdrant collection + SQLite fixtures).
#    Seeding only adds missing rows: delete an older data/workbot.sqlite3 first.
python -m workbot.seed

# 4) Run the app (one process: run progress is kept in memory, so do not add --workers)
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

The synthetic company in `workbot/fixture/` has about fifty people in eleven org units and about 170 short work records; it is a demonstration dataset, not a claim of exhaustive stakeholder discovery or production scale. Its output distinguishes unmapped areas, completed reviews without a verified contact, and incomplete reviews. The web app uses a fixed **demo Maya/workspace identity**, not real authentication. It accepts same-origin forms and applies a small in-memory model-request budget; these local-demo guards are not production security controls. Keep it on localhost. For each search intent, WorkBot keeps the records both the keyword and vector channels returned plus the three best of each channel, and passes at most eight fused records per area on to candidate selection; the rest of the keyword list is dropped because an OR keyword query matches on any single shared word. Search rank alone never establishes a person's role. Restricted work records are excluded from both indexes. The initial vector similarity threshold and candidate caps are small-fixture defaults, not measured production thresholds. If a visible record changes after seeding, search stops safely until `python -m workbot.seed` refreshes the vector index. Before an idea or an answer is accepted, WorkBot checks that the seeded search data is current and that Qdrant answers; if not, it shows a setup page naming the step to run, and nothing is stored or sent to the model. A stored card is not silently regenerated on reload. Seeding preserves modified existing rows; it does not reset a changed fixture to its original text or restore a deactivated person.

Directory title matches only add a candidate when that person also has current visible responsibility evidence; a title with no visible evidence cannot expose a person known only through restricted sources to the model. A current, visible responsibility can also support a narrow `advisor` question about that duty; manager/remit evidence alone does not qualify an advisor, and an advisor's primary source must itself be a work link, a reporter link, or a current responsibility, not a mention. Visible work-trace candidates and current manager/remit routing still use their own evidence checks. At most ten work-trace candidates reach the model: those with the strongest link to the best-ranked retrieved records. A person linked only by a mention is not a work-trace candidate.

Each area also carries a `consultation_need`, and each proposed person names one `primary_evidence_id` plus the model's own `direct`/`adjacent`/`weak` relevance read. A `direct_contact` needs that single primary source to show a strong work or current-responsibility tie, so a weak tie on the relevant record cannot borrow strength from an unrelated record in the same citation list. When the model marks its own link adjacent or weak, the contact is kept as an `advisor` instead of being dropped or presented as direct; a mention-only mirror is not proposed. These are deterministic checks on visibility and link strength, so they still cannot judge whether a visible source is genuinely on-topic for an area. An area with no supportable person stays `not_found`; showing a contact in every area is not a goal.

The area prompt separates primary-source facts, the person's link, useful contribution to the consultation need, and role selection. It allows an `advisor` to explain a related real process without requiring area expertise, but still requires an explainable source-to-need bridge; a `direct_contact` needs work on this specific need. Historical work can support direct consultation about that work itself. The current implementation also requests a required contribution field and low area reasoning as described below. Offline contract tests do not establish improved semantic quality. Any live observation needs separate approval.

A card opens with a short plan: "Before you start, talk to N people", at most four, each shown once. They are grouped into one card per area: the card opens with the area's "What to find out" (its consultation need, written by the impact model call), then lists its people, each with initials, a plain role label, and one audited line about the cited source (linked to it, except for a routing contact or a person whose primary source is a directory record; those sources are linked in the full list). Area cards follow their highest-ranked person, and people keep the priority call's order inside a card. For a work record that line keeps only the record's first sentence when the excerpt holds one, such as "Wrote a document: ‘…’". The open question across areas, when there is one, follows the cards. The priority model call picks these people from those the audit already accepted; WorkBot drops any ID not on the card, and without a usable choice it takes the strongest person of each area. Areas with no contact, no identified team, or an incomplete review are named under "Still open"; the block is left out when there are none. Two directory facts are stated in plain words: a routing contact's line says that no one was identified from the visible work on the topic (or, when an advisor is listed beside them, that no direct contact was established); this reports the review's outcome, not that the search returned nothing, and a person who once held a related responsibility that has since ended, and holds no current one on the topic, carries a note with the end date, so an outdated owner is not mistaken for the current one (shortened in the plan to the role and date, for example "Approver role ended on 2025-06-30."). That note comes from the directory, not from the model, and a card showing it stops being served if its source changes or is no longer visible. The note stays with the person wherever they are shown in full, even if it was found for another area. The full list of areas and people sits below in a collapsed section, each area collapsible on its own, where a person is shown in full only in one area (where their role is strongest; between equal roles, their own team's area) and as a one-line cross-reference elsewhere. The plan is a selection, not a verification: a wrongly proposed role can still appear in it.

In the full list each person carries the same role label as in the plan, the unverified model summary, and their audited evidence lines, the primary source first; each line links to its source, and no source ID is shown as text. Each source page links back to the plan. A work record's page shows its text; a directory source's page states what it records (the responsibility, team remit, or manager relationship and its dates). Roles are explicitly **proposals**, not verified ownership or proof that the source answers the area's specific need. The model writes no question for a person, so it cannot copy an unsupported premise into one. Quoted record text on the card is shortened at a word boundary and marked with an ellipsis; the full text is on the source page. A completed review with no supportable person is `not_found`; a review whose direct-contact proposal failed the audit with nobody else left is `review_incomplete`. Legacy cards stored without a primary-source field still render, with their evidence lines unlinked.

A clarification can be skipped. Skipping ends the question budget: the model is told no questions remain, and a further question refuses the request. Submitting an answer again when nothing is pending returns to the session page and starts nothing. Submitting an idea or an answer returns at once and the work continues in the background. Meanwhile the session page lists the steps: understanding the idea, each consultation area as it is being checked or has been checked, and choosing who to talk to first. It shows only area names, never people or sources, and people appear only when the whole card is ready. The page asks for an update every two seconds, one request at a time, and says the connection was lost when a request fails. This progress lives in the memory of the single app process; a request that no run is working on any more, for example after a restart, is closed as a refusal the next time its page is opened, so it does not wait forever. The list of earlier ideas on the home page shows each request's stored state; whether a plan's evidence still holds is checked when the plan is opened. Errors such as an unknown address, an oversized form, or the demo request limit are shown as short pages in the same layout.

After the impact model returns areas, all per-area model calls of the idea run concurrently, six at a time (an idea has at most six areas). Search and permissioned database reads stay on the thread that runs the workflow; completed areas are audited there before the final priority call. Card area order does not depend on completion order. This per-request limit does not guarantee a global provider concurrency limit across simultaneous demo sessions.

### Area output contract

Each area person proposal must include an English `contribution` string of 5-600 characters. The prompt asks for at most two complete sentences under 250 characters; the schema cap is deliberately higher so that a provider enforcing it does not cut a sentence short. The prompt requests a factual summary of the primary source's personal work/current duty, its potential contribution to the actual consultation need, and relevant scope limits, before selecting the role. A routing contribution still needs both current manager and visible remit evidence. The field is a bounded, **unverified model claim**, not an independently checked explanation or semantic score. Length/type checks cannot establish factual correctness; a missing/invalid live field fails the area schema rather than being silently filled. The audit does not use the prose to promote, downgrade, or retain a person. The card shows it under the label **Model summary (unverified)**, only when it ends as a complete sentence; a cut-off summary, or one containing a URL, email address, or source ID, is hidden while the person stays. It is not passed to the priority model or written to diagnostic logs.

The contribution field does not verify that a cited source actually addresses the specific need.

### Model call log

`workbot.llm` writes one `model_call_summary` JSON log line per model call: `INFO` on success, `WARNING` on failure. It holds the task, the outcome, an `error` (the exception class name, or WorkBot's own `not_configured` or `incomplete`), `validation_error_types` (Pydantic's codes such as `missing` or `json_invalid` when a reply fails the schema), the HTTP status, whether the reply was cut off at the token cap, the duration, and the provider-reported prompt, completion, and reasoning token counts (`null` unless the provider sent a non-negative integer). It never holds prompts, answers, names, IDs, model or provider text, or keys, and nothing from it is stored in cards or passed to the priority call. It tells you how a call went, not why WorkBot proposed a person.

To see successful calls, enable `INFO` for the `workbot.llm` logger, for example in a Python launcher:

```python
import logging
import uvicorn

logging.basicConfig(level=logging.WARNING)
logging.getLogger("workbot.llm").setLevel(logging.INFO)
uvicorn.run("workbot.main:app", host="127.0.0.1", port=8000)
```

Uvicorn's `--log-level` alone does not make this logger emit `INFO`. `httpx.Client(timeout=90)` sets network-operation timeouts, not a hard whole-call deadline.

## Development

Run these offline checks from the repository root with the `.venv` from Setup activated. Start with tests relevant to the change, and run the full suite for shared changes.

```bash
source .venv/bin/activate
python -m pytest -q
ruff check workbot tests conftest.py
ruff format --check workbot tests conftest.py
git diff --check
```

The formatting command above only checks files; use `ruff format` on affected files when an edit is needed. Without a `.venv`, prefix each Python command with `uv run --python 3.12 --no-project --with-requirements requirements.txt`, which provides Python 3.12 with the pinned requirements from uv's cache. Tests use offline stubs/local fixtures, including a local in-memory Qdrant client for search tests; `conftest.py` blanks the OpenRouter key and points the database and Qdrant settings away from your real ones for every test. A live run additionally requires Docker/Qdrant, an OpenRouter key, and explicit approval of the test scope/budget: submitting a synthetic idea in the web UI makes paid model calls. After approval, inspect its area/source card and reload without regenerating it. Keep this guide current when setup, behavior, or limitations change. Review `AGENTS.md` alongside relevant code changes and update agent instructions when needed; neither file requires an unrelated edit just for the sake of touching it.

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
LICENSE             # MIT
```

## License

MIT; see [`LICENSE`](LICENSE). The company, people, and records in `workbot/fixture/` are fictional.
