# WorkBot handoff

Updated 12 October 2026. Read [AGENTS.md](../AGENTS.md) for working rules and [README.md](../README.md) for setup and current behavior.

## Current state

- Low reasoning for area evaluation, high for impact and priority. The card shows each person's role label, the model's `contribution` labelled as an unverified model summary, the audited evidence, and a neutral question chosen by WorkBot. The model no longer writes `ask` or `unverified` text.
- The earlier evaluation scripts, captured observations, labels, comparison bundle, and their reports were removed from the tree. They remain at the `archive/pre-cleanup-20261012` tag. The reason: all of it measured a nine-person fixture on which every mapped area retrieved 6-8 of the 8 visible records and saw one of only two candidate pools, so retrieval and candidate selection were never actually tested and role judgments rested on single-sentence records.
- The current code has had no full live web-flow run, and neither the new fixture nor the changed area prompt has been exercised by any model call. No live calls are approved. An existing local database must be deleted and reseeded (`python -m workbot.seed`) to pick up the new fixture, because seeding only adds missing rows.

## Goal agreed with the user

Win the hackathon with a prototype that has **no obvious errors**; resolving debatable edge cases is not the goal. The demo itself will be planned later.

## Known issues

| Issue | Status | Where |
| --- | --- | --- |
| Unsupported `direct_contact` roles pass the audit, and roles flip between identical calls | Acceptance mechanism confirmed; cause likely thin evidence (hypothesis) | `workbot/service.py` `audit_area` |
| Some unrelated records still reach the model as candidate evidence, mainly when no record is relevant at all | Reduced, not removed: on six hand-labelled offline probes, noise records fell from 33 to 4 with no expected record or person lost; the probes and labels were the assistant's own, not model-written intents | `workbot/search.py` `Searcher.records` |
| The shown `contribution` is unverified model text; whether it is cut off less often under the new 600-character cap and 250-character request is unmeasured | Hypothesis until a live run | `workbot/models.py`, `workbot/llm.py`, `workbot/service.py` `_shown_contribution` |
| Synchronous request with no progress view; the `processing` page only says the request is running or was interrupted and refreshes itself | Confirmed in code; a real progress view is deferred to demo planning | `workbot/main.py`, `workbot/templates/session.html` |
| Impact and priority still use high reasoning, which once exhausted the 8,192-token cap on an area call; on impact that would refuse the request | Mechanism observed once on an area call; frequency unknown | `workbot/llm.py` |
| No Alexa+-like conversational framing in the UI; no LICENSE file | Observation; deferred to demo planning | `workbot/templates/`, repository root |

## Agreed next steps

1. **New synthetic fixture** (done): `workbot/fixture/` holds 49 people in 11 org units and 170 work records (165 visible, 5 restricted), loaded by `workbot/seed.py` with no schema change. Sixty records form seven topic clusters with deliberate hard cases; 110 are unrelated background. The old nine-person data lives in `tests/unit_seed.py` for unit tests only. `tests/test_fixture.py` checks validity, and `tests/expectations.json` is the answer key (must show / never show / must not be direct) for six ideas. An offline check with the real embedding model and twelve probe intents retrieved every expected record, produced twelve different candidate pools, kept departed and restricted-only people out, and stayed under half of the 18,000-character area prompt limit. Not yet verified by any model call.
2. **Small confirmed fixes** (done, offline only): the `contribution` cap is 600 with a 250-character request; `ask` and `unverified` were removed from the area schema and prompt; a skipped clarification sends `remaining_questions=0`; the `processing` page no longer claims an interruption; the candidate cap follows retrieval rank and excludes mention-only people; quoted record text is cut at a word boundary with an ellipsis. Retrieval keeps, per intent, records both channels returned plus each channel's top three, at most eight per area (approved by the user after an offline comparison with a score floor and a two-term rule).
3. **Card content** (done; assistant's recommendation, accepted for now): `contribution` is shown as "Model summary (unverified)", trimmed to complete sentences or hidden, and kept out of the priority call. The role stays a label.
4. **One end-to-end live measurement** (next) on the new fixture against the expectations file, counting obvious errors only. Requires a separately approved call budget.
