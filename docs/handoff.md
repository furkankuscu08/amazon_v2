# WorkBot handoff

Updated 12 October 2026. Read [AGENTS.md](../AGENTS.md) for working rules and [README.md](../README.md) for setup and current behavior.

## Current state

- Application behavior is unchanged from the merged combined baseline: low reasoning for area evaluation, high for impact and priority; a required 5-300-character unverified `contribution`; shared neutral questions on the card.
- The earlier evaluation scripts, captured observations, labels, comparison bundle, and their reports were removed from the tree. They remain at the `archive/pre-cleanup-20261012` tag. The reason: all of it measured a nine-person fixture on which every mapped area retrieved 6-8 of the 8 visible records and saw one of only two candidate pools, so retrieval and candidate selection were never actually tested and role judgments rested on single-sentence records.
- The current main has had no full live web-flow run. No live calls are approved.

## Goal agreed with the user

Win the hackathon with a prototype that has **no obvious errors**; resolving debatable edge cases is not the goal. The demo itself will be planned later.

## Known issues

| Issue | Status | Where |
| --- | --- | --- |
| Fixture too small for retrieval or candidate selection to discriminate | Confirmed from the removed traces | `workbot/seed.py`, `workbot/search.py` |
| Unsupported `direct_contact` roles pass the audit, and roles flip between identical calls | Acceptance mechanism confirmed; cause likely thin evidence (hypothesis) | `workbot/service.py` `audit_area` |
| `contribution` text cut off at the 300-character cap | Strong correlation in 14 observed strings: all five at exactly 300 were incomplete, none below 300 was | `workbot/models.py`, area prompt in `workbot/llm.py` |
| A malformed `ask` drops an otherwise valid person although the text is discarded anyway | Confirmed in code | `workbot/service.py` `audit_area` |
| After a skipped clarification the model is told one question remains, but asking it refuses the whole request | Confirmed in code, untested, never observed live | `workbot/service.py` `run` |
| Synchronous request with no progress view; `processing` state says "Processing was interrupted" | Confirmed in code | `workbot/main.py`, `workbot/templates/session.html` |
| Impact and priority still use high reasoning, which once exhausted the 8,192-token cap on an area call; on impact that would refuse the request | Mechanism observed once on an area call; frequency unknown | `workbot/llm.py` |
| No Alexa+-like conversational framing in the UI; no LICENSE file | Observation; deferred to demo planning | `workbot/templates/`, repository root |

## Agreed next steps

1. **New synthetic fixture** (approved): about 48 people, 10 org units, and 170 work records of 2-4 sentences (at most 400 characters), stored as JSON under `workbot/fixture/` and loaded by `workbot/seed.py`, with no database schema change. Six topic clusters with hard cases (adjacent topic, expired responsibility, moved or departed people, mention-only, restricted-only evidence, no-trace routing) plus unrelated background records. The existing campaign characters stay in the campaign cluster. The current nine-person data moves into `tests/` as unit-test data. Deliverables include a mechanical validity test, an offline retrieval check, and a small expectations file (must show / must never show / must be `not_found`) for about six ideas. The record skeleton is shown to the user before text generation.
2. **Small confirmed fixes** (approved): relieve the `contribution` cap problem, stop a malformed `ask` from dropping a person, fix the skipped-clarification contradiction, and correct the `processing` message.
3. **Card content** (assistant's recommendation, accepted for now): show `contribution` labelled as an unverified model summary and keep the role as a label.
4. **One end-to-end live measurement** on the new fixture against the expectations file, counting obvious errors only. Requires a separately approved call budget.
