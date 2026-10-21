# WorkBot

**Amazon Developer Hackathon — Alexa+ track (simulated web experience route)**

Before you change how something works at a company, you need to know who to involve. Job titles and org charts do not say who handles a decision today or who only used to.

WorkBot is a simulated Alexa+ experience: Maya, an employee at a fictional retailer, describes a change to make at work and gets, as a short conversation, a plan of who to talk to first, with evidence-backed contacts, what to find out from each, and explicit gaps, and can then ask follow-up questions about that plan. The home page offers three example ideas that only fill the idea box (sending one is still a live model call) and lists Maya's earlier ideas; a plan whose evidence or access has changed since is not shown when opened and is reported as no longer valid instead. It searches synthetic work traces and a structured directory; it does not make project decisions or contact people.

For example, Maya asks: *"Raise the approval threshold for marketing spend requests so small changes need no review."* In the plan saved for this idea on the hosted demo (Amazon Nova 2 Lite, 20 October 2026), Alexa asked nothing and answered "Before you start, talk to four people. Start with Tara Reed and Omar Haddad in Finance. Omar Haddad's approver role ended in June 2025. Then Marcus Reed in Growth Marketing, and Anders Holm in Legal and Compliance." Tara reviews marketing spend requests above the threshold today; Omar wrote the 2024 budget approval policy, and a directory note says that Omar's approver role ended on 30 June 2025; Anders reviews changes to the spending approval policy for compliance. Each person comes with evidence linked to the source records, and each card says what to find out there. The people and wording vary from run to run. This plan was made before the impact call got directory hints; in ten measured runs of this idea with them, Legal and Compliance and its reviewer were in every plan, but Omar appeared in only 3 (each time with the ended-role note) and never among the first conversations. See [Measured on live runs](#measured-on-live-runs).

> ⚠️ **Disclaimer:** This is **not** an official Alexa integration and uses no Alexa API; Amazon Bedrock serves only as the model provider. Use **synthetic project ideas only**: prompts are sent to Amazon Bedrock (or to OpenRouter when it is selected). The directory and work traces are fictional. No messages or invitations are sent to anyone. WorkBot's input and output language is **English**: enter ideas and clarification answers in English; synthetic records, search intents, prompts, and displayed questions/cards are written in English. This is a product convention, not automatic detection or rejection of other languages at runtime.

## Documentation

- This `README.md` is the human guide to the current prototype and its limits.
- [`AGENTS.md`](AGENTS.md) guides coding agents working in this repository.
- [`docs/archive/`](docs/archive/) preserves the original non-binding Turkish design proposal; it is not current behavior or an active implementation plan.
- [`docs/competition.md`](docs/competition.md) is a dated working brief for the hackathon; recheck the [live official rules](https://amazonappdev2026.devpost.com/rules) before submitting.
- [`docs/demo-video.md`](docs/demo-video.md) is the demo-video script, matching the cut recorded on 20 October 2026 and re-cut on 22 October; the user may still revisit it.
- [`docs/friction-log.md`](docs/friction-log.md) records the friction met while building on AWS and Amazon Bedrock, for the hackathon's optional friction-log bonus.
- [`docs/competition-winner-patterns.md`](docs/competition-winner-patterns.md) compares other competition winners for inspiration, not requirements or proof of what wins.

## Stack

| Layer | Choice |
| --- | --- |
| Web | FastAPI + Jinja2 templating, served by **uvicorn** (`workbot.main:app`); one inline stylesheet whose light and dark mode follow the device setting |
| LLM | Amazon Bedrock — Amazon Nova 2 Lite through the `global.amazon.nova-2-lite-v1:0` cross-Region inference profile, Converse API with extended thinking at low effort for all three tasks. Fallback: OpenRouter — `z-ai/glm-5.3-flash` (area low; impact/priority high) on the tested `open-inference/fp4` endpoint |
| Vectors | Local Qdrant (Docker, REST 6333, bound to localhost) |
| Speech | Amazon Polly — the plan summary, the clarification question, and follow-up answers read aloud as they arrive or on **Listen**, standard voice `Joanna` in the profile's Region |
| Voice input | Amazon Nova 2 Sonic on Bedrock (`amazon.nova-2-sonic-v1:0`, bidirectional stream through the `aws-sdk-bedrock-runtime` SDK, 16 kHz PCM) — **Speak** next to the idea, answer, and follow-up boxes fills the box with Sonic's transcript of what was said; Amazon Transcribe is not open to this project's account |
| Embeddings | Local FastEmbed / all-MiniLM-L6-v2 (no cloud embedding calls) |
| Relational data | SQLite via `WORKBOT_DB_PATH` (default `data/workbot.sqlite3`) |
| Hosted demo (optional) | One Amazon EC2 server from a CloudFormation template, with an instance role; Docker Compose runs Caddy (automatic TLS), the app, and Qdrant |

## Prerequisites

- Docker (Compose v2.22+) — for Qdrant, and optionally the app container
- Python 3.12 + [uv](https://docs.astral.sh/uv/) (or plain `pip`)
- An AWS account where Amazon Nova 2 Lite can be invoked on Amazon Bedrock, and credentials for it in a named AWS CLI profile (below). Only for the fallback: an OpenRouter API key (https://openrouter.ai/keys)

## Setup

```bash
# 1) Environment & dependencies (the application loads .env automatically)
cp .env.example .env          # then edit: set AWS_PROFILE and AWS_REGION
aws configure --profile workbot   # once: the IAM user's access key, Region, json
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

`.env` needs no AWS key: boto3 finds the credentials of the profile named by `AWS_PROFILE` in `~/.aws/`. WorkBot itself calls only the Bedrock Converse API, which needs `bedrock:InvokeModel`, which also covers Nova 2 Sonic's bidirectional stream for **Speak**, and, for **Listen**, Amazon Polly's `polly:SynthesizeSpeech`, so the profile can belong to an IAM user with no more than this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "polly:SynthesizeSpeech"],
      "Resource": "*"
    }
  ]
}
```

Nova 2 Lite is reached through an inference profile, which can route a request to another Region; `Resource: "*"` covers the profile and the model in each Region it may use. In an AWS account whose Regions are restricted by an organization policy, Bedrock inference must be allowed in those Regions. Polly and Nova 2 Sonic are called in `AWS_REGION` itself; some Regions, such as `eu-north-1`, offer only Polly's standard voices.

### Optional: everything in Docker

```bash
docker compose --profile app up -d --build                     # app on :8000 + Qdrant
docker compose --profile app run --rm app python -m workbot.seed
```

The container does not see your AWS profile. Either set `WORKBOT_MODEL_PROVIDER=openrouter` and `OPENROUTER_API_KEY` in `.env`, or give the container AWS credentials yourself, for example a read-only mount of an AWS config directory at `/home/workbot/.aws`; the image runs as the user `workbot` (uid 10001), which must be able to read those files, and a `~/.aws` with the usual owner-only permissions is not readable to it. The image downloads the embedding model when it is built. A `workbot_data` volume left by an earlier image that ran as root is not writable to that user: remove it with `docker compose down -v` (this deletes the local container's sessions).

### Optional: hosted demo on AWS

`deploy/` puts the demo on one Amazon EC2 server behind HTTPS, as the hackathon's hosted test link; **Speak** needs a secure page, so plain `http` on a public address would lose it. Keep the guards on: a public demo without `WORKBOT_ACCESS_CODE` and `WORKBOT_DAILY_IDEAS` lets anyone spend your Bedrock budget.

1. In the EC2 console of your Region, create a key pair (`.pem`) for SSH.
2. In CloudFormation, create a stack from `deploy/workbot-ec2.yaml`, giving the key pair and your own address as `SshCidr` (for example `203.0.113.7/32`), and allow it to create IAM resources. It creates an Ubuntu 24.04 `t3.small` with a 20 GB encrypted disk and 2 GiB of swap, Docker installed at first boot, an Elastic IP, a security group open to all on ports 80 and 443 and to that address alone on 22, and an instance role allowed only `bedrock:InvokeModel` on Nova 2 Lite (through its global inference profile) and Nova 2 Sonic, and `polly:SynthesizeSpeech`. Instance metadata requires tokens with a hop limit of 2, so the role's credentials reach the app inside its container. The stack's `Hostname` output is `<elastic-ip>.sslip.io`, a public DNS name that resolves to that address, so Caddy can get a Let's Encrypt certificate without a domain of your own.
3. Wait until `ssh ubuntu@<ip> cloud-init status --wait` reports `done` (Docker is installed then; log in again afterwards so the `docker` group applies), and copy the repository to the server without local state, for example `rsync -a --delete --exclude '.env*' --exclude .venv --exclude data --exclude .git --exclude __pycache__ --exclude '.*_cache' ./ ubuntu@<ip>:workbot/`. Excluded files, such as the server's own `.env`, are left in place.
4. On the server, write `workbot/.env` with `AWS_REGION`, `WORKBOT_HOSTNAME`, `WORKBOT_ACCESS_CODE`, and `WORKBOT_DAILY_IDEAS`, and without `AWS_PROFILE`, so boto3 uses the instance role. Then, in `workbot/`:

```bash
docker compose -f deploy/compose.yaml --env-file .env up -d --build
docker compose -f deploy/compose.yaml --env-file .env run --rm app python -m workbot.seed
```

Only Caddy publishes ports; Qdrant and the app are reachable on the Compose network alone, which is why the app may trust forwarded headers from any address there (`--proxy-headers --forwarded-allow-ips=*`). Caddy redirects `http` to `https` and keeps the `Host` header. The app logs each model call's summary line at `INFO` (see `deploy/logging.json`) and no access log; read it with `docker compose -f deploy/compose.yaml --env-file .env logs app` (every command on this file needs `--env-file .env`, because the file requires `WORKBOT_HOSTNAME`). To update the server, copy the tree again and rerun the first command; reseed only when the fixture changed. At on-demand prices the server, its disk, and its public address cost about $21 a month, before model calls; deleting the stack removes all of it, but not the key pair. Do not update the stack to change `SshCidr` when your address changes: its Ubuntu image is looked up again on every update, and a newer one replaces the server with an empty one; edit the security group's SSH rule instead.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `WORKBOT_MODEL_PROVIDER` | `bedrock` | `bedrock`, or `openrouter` for the fallback |
| `AWS_PROFILE` | *(unset)* | AWS CLI profile whose credentials boto3 uses; unset, the standard AWS credential chain applies (for example an instance role) |
| `AWS_REGION` | *(the profile's)* | Region of the Bedrock and Polly endpoints; boto3 itself reads only `AWS_DEFAULT_REGION` or the profile, so WorkBot passes this one explicitly |
| `WORKBOT_BEDROCK_MODEL` | `global.amazon.nova-2-lite-v1:0` | Bedrock model or inference profile ID |
| `WORKBOT_POLLY_VOICE` | `Joanna` | Amazon Polly voice for **Listen** |
| `WORKBOT_POLLY_ENGINE` | `standard` | Polly engine; `neural` or `generative` only where the Region offers them |
| `OPENROUTER_API_KEY` | *(unset)* | OpenRouter API key; needed only with `WORKBOT_MODEL_PROVIDER=openrouter` |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_HOST_PORT` | `6333` | Host port exposed by Compose for local Python |
| `WORKBOT_DB_PATH` | `data/workbot.sqlite3` | SQLite database file |
| `WORKBOT_ACCESS_CODE` | *(unset)* | When set, every page asks for this code first (hosted demo) |
| `WORKBOT_DAILY_IDEAS` | *(unset)* | When set, the most new ideas accepted per UTC day across all visitors |
| `WORKBOT_HOST_PORT` | `8000` | Host port for the optional app container |
| `WORKBOT_HOSTNAME` | *(unset)* | Public hostname of the hosted demo; read only by `deploy/compose.yaml`, which needs it |

`.env` can hold secrets and is **git-ignored** — never commit it. Do not leave `AWS_BEARER_TOKEN_BEDROCK` set but empty: botocore then still sends the request with token authentication.

Both providers cap each reply at 8,192 output tokens and validate it locally against the same Pydantic schemas; a reply cut off at the cap, filtered, or failing the schema produces no card. A reply that arrives but fails the schema or ends without an answer for a reason other than the cap is requested once more with the same input, because Nova 2 Lite does not enforce the schema and such failures are intermittent (1 of 287 calls in one 42-run measurement, none of 251 in the next); if the second reply fails too, the step fails as before. A reply cut off at the cap, or one whose input exceeded the model's context window, is not requested again. The repeat is billed like any request and can double a step's time. On Bedrock, each task is one Converse call whose only tool is the task's schema and whose tool choice forces that tool; Nova 2 Lite rejects both `outputConfig` JSON-schema output and `strict` tools, so the provider does not enforce the schema and the local validation is what does. Its extended thinking runs at low effort for all three tasks: in live runs, medium effort spent up to the whole output cap on reasoning (impact and priority calls of 3,600–8,192 output tokens and 20–46 seconds, two of them cut off), while low effort used 1,300–2,100 tokens and 10–14 seconds for the same impact calls; high effort does not allow an output cap at all. The AWS SDK retries throttling, other transient errors, and read timeouts (90 seconds each), up to three attempts in all, so one slow call can take several minutes and a retried prompt is billed again. On OpenRouter, requests use parameter-compatible routing to the tested `open-inference/fp4` endpoint and strict JSON-schema output; if that endpoint is unavailable, WorkBot fails closed rather than silently selecting an untested provider. Missing setup (no AWS credentials, an unknown profile, no Region, no OpenRouter key, or a `WORKBOT_MODEL_PROVIDER` other than `bedrock` or `openrouter`) fails the call as `not_configured` before any prompt is sent; on a machine with no AWS credentials, boto3's own credential search may still ask the EC2 instance metadata address. Other AWS sign-in problems, such as an expired SSO session, are logged under their exception class name. These settings do not guarantee schema completion or semantic correctness across future responses/model/provider changes. Do not use confidential inputs; live calls consume your own AWS or OpenRouter budget.

## Current behavior and limitations

### The synthetic company

`workbot/fixture/` holds about fifty people in eleven org units and about 170 short work records, built around topic clusters with hard cases: adjacent topics, expired duties, departed or moved people, mention-only links, people known only through restricted sources, and a team with no relevant trace, plus unrelated background records. It is a demonstration dataset, not a claim of exhaustive stakeholder discovery or production scale. Maya, the requester, is a fixed demo identity, not real authentication. If a visible record changes after seeding, search stops safely until `python -m workbot.seed` refreshes the index. Seeding only adds missing rows: it does not reset a changed row or restore a deactivated person. The vector similarity threshold and candidate caps are small-fixture defaults, not measured production thresholds.

### How people are chosen

1. **Areas.** The impact model call names the areas the idea touches, maps each to an org unit, and writes what to find out there. Alongside the org units, it gets up to three directory hints: current duties of active people, recorded in the company directory and visible to Maya, that share at least two words with the idea and its answers (common process words such as "change" or "request" do not count), one per org unit, with no names or source IDs. A hint can point the model to an area it might miss, such as a compliance review of the policy the idea changes; the model may ignore it, a hint is never a reason to ask a question, and the model is asked to write the area's reasons and "What to find out" from the idea, not from the hint. Most ideas get no clarifying question; one is asked only when the areas cannot be told without it, and it stays on the idea itself (what changes, which process or product, who it affects), never on which reviews, rules, teams, or owners are involved, since finding those is WorkBot's job. There are at most two questions, and a skipped one ends them. Every answer is passed to all three model calls.
2. **Search.** Keyword (BM25) and vector search run only over records Maya can see; restricted records are in neither index. Candidates come from work links (not mere mentions), current visible responsibilities, and a team's current manager with a visible remit. Search rank alone never establishes a role.
3. **Review.** One model call per area, all in parallel, proposes people with a role and the record behind each.
4. **Audit.** Code checks every proposal: each cited record must be visible and tied to the person, a cited directory entry must still hold today, and a direct contact needs a strong work or current-duty tie on its main record. A proposal that overclaims is kept as an advisor or dropped, and if that leaves the area with no direct or routing contact, the audit adds the team's manager as "Can route you". A direct proposal that cites something outside the candidates hides any routing contact, and the review is incomplete if no one else remains. These checks cover visibility and link strength, not whether a record is really about the area.
5. **Priority.** A last model call orders the areas and picks up to four already-audited people to talk to first. It cannot add a person or change a role; without a usable choice, the plan takes the strongest person of each area, preferring one whose related duty has not ended.

An area can end as having people, "No contact found" (a completed review with no supportable person; showing someone in every area is not a goal), "Team not identified" (no org unit fits), or "Review incomplete". Before an idea or an answer is accepted, WorkBot checks that Qdrant answers and the seeded data is current; if not, it shows a setup page naming the step to run, and nothing is stored or sent. A run takes about 14 to 46 seconds; the page lists its steps by area name only, and people appear when the whole plan is ready. Progress lives in the single app process, so a request left unfinished by a restart is closed as a refusal when it is next opened. A stored plan is never silently regenerated; if its evidence changes or stops being visible, it is shown as out of date.

### What the plan shows

- **"Alexa says"**: a short summary built by code from the plan, never by the model: "Before you start, talk to four people. Start with Tara Reed and Omar Haddad in Finance. Omar Haddad's approver role ended in June 2025. Then …", the count of areas left to the full list and still open, and an invitation to ask follow-up questions. A pending clarification uses the same panel, labelled "Alexa asks".
- **One card per area that holds someone in the plan**, with its "What to find out" and its people: initials, a plain role label (Current responsibility, Related work, Can advise, Can route you), and one line about the cited record, linked to it. A routing contact's line says that no one was identified from the visible work (or, beside an advisor, that no direct contact was established), built from the manager and remit records. A person whose related duty has ended is listed after the others in their area.
- **Ended duties**: a person who once held a related responsibility that has ended, and holds no current one on the topic, carries a dated directory note ("Approver role ended in June 2025."), linked to its directory record. The note comes from the directory, not from the model.
- **"Also in the full list"** names areas whose people are left out of the plan; **"Still open"** names areas without a contact, team, or finished review; the shared question across areas, when there is one, follows the cards (code drops one that only repeats an area's "What to find out").
- **Full list** (collapsed): every area with its people and all their evidence lines in plain words ("Assigned to a Jira issue on 2 March 2026: ‘…’"), each linked to its source. A person is shown in full in one area (where their role is strongest; between equal roles, their own team's) and as a one-line cross-reference elsewhere. Quotes are shortened at a whole sentence when possible; the source page has the full text, or what a directory record states and its dates. No source ID is shown.

Apart from area names, "What to find out", the shared question, and a clarification question, every sentence on the page is put together by code. Roles are **proposals**, not verified ownership.

### Follow-up questions

Below the summary, Maya can ask about the plan by typing, by **Speak**, or by pressing one of up to four suggestions ("Why Omar?", "Prep me for Tara", "Who else?", "What's still open?"). No model is called: rules match the question to people on the card (a slightly misheard capitalized name such as "Tarah" still finds Tara) and build the answer only from what the page shows. *Why* gives the person's area, role, plan line (linked to its source), and any ended-duty note; *prep* gives the plan line and what to ask; *who else* names people in the full list but not in the plan; *what's still open* names open areas. A name that fits two people gets "which one?", other questions get a line saying what Alexa can answer, and at most six turns are shown. A name that is not on the card gets the same answer whoever it is, so it reveals nothing about people Maya cannot see. The conversation is not stored: reloading the page starts over, and one visitor's questions never appear for another. A plan that is out of date takes no questions.

### Voice

- **Listen** reads the summary, a question, or a follow-up answer with Amazon Polly. A question, plan, or answer that arrives after a click is read aloud at once; "Read answers aloud" turns this off in that browser. Browsers play sound only after a click, so the page swaps in each new page without a full reload; if a browser still refuses, it says "Press Listen to hear it." Checked in Chromium and Firefox; Safari has not been tested. Polly receives only text the page shows, never what the visitor typed; the voice calls each person on the plan by first name (the full name when two share it), while the page shows full names. Without JavaScript nothing is read aloud.
- **Speak**, beside the idea, answer, and follow-up boxes, records up to 20 seconds and sends it to Amazon Nova 2 Sonic; the transcript only fills the box, and the form is sent only when the person presses its button. It needs microphone permission and https or localhost. In live checks, four-second synthetic sentences came back word for word in one to three seconds.
- If Polly or Sonic is unavailable, the page says so and nothing else changes.

### Limits and demo guards

- People and records are synthetic. The plan is a starting point: whether a cited record answers an area's question is the model's judgment, and the people and wording vary between runs (see below).
- Same-origin forms only, and per-address limits: 30 ideas or answers, 20 recordings, and 60 read-aloud answers in 10 minutes.
- For a hosted demo, `WORKBOT_ACCESS_CODE` asks every visitor for a code first (a 30-day cookie holds a digest of it, not the code; ten attempts per address in 10 minutes; changing the code signs everyone out), and `WORKBOT_DAILY_IDEAS` caps new ideas per UTC day across all visitors (kept in the database; answering a clarification does not count; earlier plans stay readable; a value that is not a whole number stops new ideas with a setup message). These are spending guards, not real authentication; without them, keep the app on localhost.
- Behind a TLS reverse proxy, run uvicorn on `127.0.0.1` with `--proxy-headers` and `--forwarded-allow-ips` set to the proxy's address, and let the proxy keep `Host` and send `X-Forwarded-For` and `X-Forwarded-Proto`; otherwise forms are refused as cross-origin, the access cookie is not `Secure`, and all visitors share one address in the limits.
- Each idea runs its area calls six at a time; this is not a global provider concurrency limit across simultaneous sessions.

### Measured on live runs

On 20 October 2026 the seven ideas in `tests/expectations.json` (the answer key: who must be shown, who must never be shown, who must not be a direct contact) were run end to end on Amazon Nova 2 Lite with this version, 42 runs in all: the marketing-spend and spending-policy ideas ten times each, customer scoring and stablecoin five times each, and the other three four times each. In half of the runs Maya would have answered the first clarification and in the other half skipped every one; no run asked one. Each run used a fresh copy of the synthetic company; the criteria were written down before the runs.

| Idea | Runs | Plan produced | Answer key passed | Notes |
|---|---|---|---|---|
| Marketing spend threshold | 10 | 10 | 10 | This idea's answer key requires only the current reviewer, so a pass says nothing about the other areas. The current reviewer of marketing spend requests was in every plan and among the first conversations every time. Legal and Compliance was among the areas in all 10, each time with its reviewer of spending-policy changes as a direct contact (1 of 10 before directory hints). The author of the 2024 policy appeared in only 3 (7 of 10 before hints), each time with the note that this person's approver role ended in June 2025, and never among the first conversations. The growth marketing contact appeared in 3. Brand Review was never added (6 of 10 before hints). |
| Spending policy change | 10 | 10 | 10 | The answer key requires the current reviewer and the policy reviewer in Legal and Compliance; both were in every plan (1 of 3 before hints). |
| Customer scoring | 5 | 5 | 5 | |
| Stablecoin payments | 5 | 5 | 5 | An area was open (no contact found) in 4: Finance in 3, Legal and Compliance in 1. |
| Campaign AI, refund assistant, pickup lockers | 4 each | 12 | 9 | The refund queue owner was missing once. Twice the pickup lockers idea, which has no relevant record by design, made a fulfilment planner a direct contact instead of leaving the team manager as the routing contact. |

In all 42 runs no plan was refused, no area the model named was left without a team, and no question was asked. A run took 14 to 44 seconds and 4 to 8 model calls; none of 251 calls had to be repeated. Areas that are only loosely affected still get reviewed, and the answer key checks only obvious outcomes, so a pass does not mean every person shown is relevant.

### Model call log

`workbot.llm` writes one `model_call_summary` JSON line per model call (`INFO` on success, `WARNING` on failure): task, provider, attempt, outcome, error class or WorkBot's own code, validation error codes, HTTP status, stop reason, truncation, duration, and token counts. It never holds prompts, answers, names, IDs, model text, or keys. To see successful calls, enable `INFO` for the `workbot.llm` logger; uvicorn's `--log-level` alone does not:

```python
import logging
import uvicorn

logging.basicConfig(level=logging.WARNING)
logging.getLogger("workbot.llm").setLevel(logging.INFO)
uvicorn.run("workbot.main:app", host="127.0.0.1", port=8000)
```

Do not enable `DEBUG` for `botocore` or the Sonic SDK's `smithy_*` and `aws_sdk_*` loggers: they log whole requests, including prompts, recordings, and transcripts.

## Development

Run these offline checks from the repository root with the `.venv` from Setup activated. Start with tests relevant to the change, and run the full suite for shared changes.

```bash
source .venv/bin/activate
python -m pytest -q
ruff check workbot tests conftest.py
ruff format --check workbot tests conftest.py
git diff --check
```

The formatting command above only checks files; use `ruff format` on affected files when an edit is needed. Without a `.venv`, prefix each Python command with `uv run --python 3.12 --no-project --with-requirements requirements.txt`, which provides Python 3.12 with the pinned requirements from uv's cache. Tests use offline stubs/local fixtures, including a local in-memory Qdrant client for search tests; `conftest.py` blanks the OpenRouter key, leaves boto3 no AWS credentials to find (no profile files, keys, tokens, or instance and container metadata), and points the database and Qdrant settings away from your real ones for every test. Bedrock tests check each request against the AWS API model with botocore's offline `Stubber`. A live run additionally requires Docker/Qdrant, working Bedrock credentials (or an OpenRouter key for the fallback), and explicit approval of the test scope/budget: submitting a synthetic idea in the web UI makes paid model calls. After approval, inspect its area/source card and reload without regenerating it. Keep this guide current when setup, behavior, or limitations change. Review `AGENTS.md` alongside relevant code changes and update agent instructions when needed; neither file requires an unrelated edit just for the sake of touching it.

`requirements.in` lists direct dependencies (lightweight ONNX/CPU embeddings); `requirements.txt` is the compiled lock file. After changing dependencies:

```bash
uv pip compile requirements.in --python-version 3.12 -o requirements.txt
```

## Layout

```
compose.yaml        # Qdrant (default) + optional app container via `--profile app`
Dockerfile          # app image (also used by the hosted demo)
deploy/             # hosted demo: CloudFormation template, Compose file, Caddyfile, log config
requirements.in/txt # dependency pinning
.env.example        # template; copy to .env (untracked)
workbot/            # application package (app entrypoint: workbot.main:app; follow-up answers in followup.py)
tests/              # pytest suite
docs/               # hackathon brief & design notes
LICENSE             # MIT
```

## License

MIT; see [`LICENSE`](LICENSE). The company, people, and records in `workbot/fixture/` are fictional.
