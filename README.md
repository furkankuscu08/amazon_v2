# WorkBot

**Amazon Developer Hackathon — Alexa+ track (simulated web experience route)**

WorkBot is a simulated Alexa+ experience: Maya describes a project idea and sees consultation areas, evidence-backed contacts, questions to ask, and explicit gaps. It searches synthetic work traces and a structured directory; it does not make project decisions or contact people.

> ⚠️ **Disclaimer:** This is **not** an official Alexa integration or Amazon API integration. Use **synthetic project ideas only**: prompts are sent to OpenRouter. The directory and work traces are fictional. No messages or invitations are sent to anyone. WorkBot's input and output language is **English**: enter ideas and clarification answers in English; synthetic records, search intents, prompts, and displayed questions/cards are written in English. This is a product convention, not automatic detection or rejection of other languages at runtime.

## Documentation

- This `README.md` is the human guide to the current prototype and its limits.
- [`AGENTS.md`](AGENTS.md) guides coding agents working in this repository.
- [`docs/proposed-stakeholder-routing-design.md`](docs/proposed-stakeholder-routing-design.md) is a **non-binding proposal and roadmap**, not a description of current behavior.
- [`docs/competition.md`](docs/competition.md) is a dated working brief for the hackathon; recheck the [live official rules](https://amazonappdev2026.devpost.com/rules) before submitting.
- [`docs/competition-winner-patterns.md`](docs/competition-winner-patterns.md) compares other competition winners for inspiration, not requirements or proof of what wins.
- [`opencode.jsonc`](opencode.jsonc) holds OpenCode configuration, including optional built-in subagent model preferences.

## Stack

| Layer | Choice |
| --- | --- |
| Web | FastAPI + Jinja2 templating, served by **uvicorn** (`workbot.main:app`) |
| LLM | OpenRouter — `z-ai/glm-5.3-flash` (high reasoning) via `OPENROUTER_API_KEY` |
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

This first slice uses a small campaign-focused fixture, not a 2,000–5,000-person directory or a claim of exhaustive stakeholder discovery. Its output distinguishes unmapped areas, completed reviews without a verified contact, and incomplete reviews. The web app uses a fixed **demo Maya/workspace identity**, not real authentication. It accepts same-origin forms and applies a small in-memory model-request budget; these local-demo guards are not production security controls. Keep it on localhost. The card exposes an expandable BM25/Qdrant candidate trace; search rank alone never establishes a person's role. Restricted work records are excluded from both indexes. The initial vector similarity threshold and candidate caps are small-fixture defaults, not measured production thresholds. If a visible record changes after seeding, search stops safely until `python -m workbot.seed` refreshes the vector index. A stored card is not silently regenerated on reload. Seeding preserves modified existing rows; it does not reset a changed fixture to its original text or restore a deactivated person.

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

`.env` contains secrets and is **git-ignored** — never commit it. On 26 September 2026, two opt-in runs with synthetic campaign input exercised the real OpenRouter model, local Qdrant and the web request → card → reload → source flow. OpenRouter accepted the strict JSON-schema request and returned locally validated output; this is not a guarantee across future model/provider changes. The first run (7 model calls, ~140 s) incorrectly proposed a budget contact using a loyalty-promotion record and a commerce contact using launch coordination evidence. After tightening area-specific evidence instructions, the second run (6 calls, ~99 s) did not repeat those two suggestions and returned four areas instead of six. This single follow-up is **not** evidence of reliable semantic relevance or recall. Neither live run asked a clarification; that path remains covered by deterministic tests only. Do not use confidential inputs; live calls consume your own API budget.

## Development

```bash
pytest          # tests
ruff check .    # lint
ruff format .   # format
```

The tests use a local in-memory Qdrant client and model stubs; a repeatable live run additionally requires Docker/Qdrant and an OpenRouter key. Open the web UI after setup, submit a synthetic idea, inspect the area/source card, then reload. Keep this guide current when setup, behavior, or limitations change. Review `AGENTS.md` alongside relevant code changes and update agent instructions when needed; neither file requires an unrelated edit just for the sake of touching it.

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
