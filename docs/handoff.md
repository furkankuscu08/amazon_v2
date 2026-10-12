# WorkBot handoff

Updated 12 October 2026. Read [AGENTS.md](../AGENTS.md) for working rules and [README.md](../README.md) for setup and current behavior.

## Current state

- Application behavior is unchanged from the merged combined baseline: low reasoning for area evaluation, high for impact and priority; a required 5-300-character unverified `contribution`; shared neutral questions on the card.
- The earlier evaluation scripts, captured observations, labels, comparison bundle, and their reports were removed from the tree. They remain at the `archive/pre-cleanup-20261012` tag. The reason: all of it measured a nine-person fixture on which every mapped area retrieved 6-8 of the 8 visible records and saw one of only two candidate pools, so retrieval and candidate selection were never actually tested and role judgments rested on single-sentence records.
- The current code has had no full live web-flow run, and the new fixture has not been exercised by any model call. No live calls are approved. An existing local database must be deleted and reseeded (`python -m workbot.seed`) to pick up the new fixture, because seeding only adds missing rows.

## Goal agreed with the user

Win the hackathon with a prototype that has **no obvious errors**; resolving debatable edge cases is not the goal. The demo itself will be planned later.

## Known issues

| Issue | Status | Where |
| --- | --- | --- |
| Candidate cap ignores retrieval rank; retrieval always fills its 12-record limit with keyword noise | Confirmed in code; not yet seen to drop an expected person | `workbot/search.py` `candidate_pool` |
| Unsupported `direct_contact` roles pass the audit, and roles flip between identical calls | Acceptance mechanism confirmed; cause likely thin evidence (hypothesis) | `workbot/service.py` `audit_area` |
| `contribution` text cut off at the 300-character cap | Strong correlation in 14 observed strings: all five at exactly 300 were incomplete, none below 300 was | `workbot/models.py`, area prompt in `workbot/llm.py` |
| A malformed `ask` drops an otherwise valid person although the text is discarded anyway | Confirmed in code | `workbot/service.py` `audit_area` |
| After a skipped clarification the model is told one question remains, but asking it refuses the whole request | Confirmed in code, untested, never observed live | `workbot/service.py` `run` |
| Synchronous request with no progress view; `processing` state says "Processing was interrupted" | Confirmed in code | `workbot/main.py`, `workbot/templates/session.html` |
| Impact and priority still use high reasoning, which once exhausted the 8,192-token cap on an area call; on impact that would refuse the request | Mechanism observed once on an area call; frequency unknown | `workbot/llm.py` |
| No Alexa+-like conversational framing in the UI; no LICENSE file | Observation; deferred to demo planning | `workbot/templates/`, repository root |

## Agreed next steps

1. **New synthetic fixture** (done): `workbot/fixture/` holds 49 people in 11 org units and 170 work records (165 visible, 5 restricted), loaded by `workbot/seed.py` with no schema change. Sixty records form seven topic clusters with deliberate hard cases; 110 are unrelated background. The old nine-person data lives in `tests/unit_seed.py` for unit tests only. `tests/test_fixture.py` checks validity, and `tests/expectations.json` is the answer key (must show / never show / must not be direct) for six ideas. An offline check with the real embedding model and twelve probe intents retrieved every expected record, produced twelve different candidate pools, kept departed and restricted-only people out, and stayed under half of the 18,000-character area prompt limit. Not yet verified by any model call. Observed while checking: `candidate_pool` keeps the ten work candidates with the strongest and most recent links, ignoring retrieval rank, so a relevant person could be cut when many unrelated records are retrieved.
2. **Small confirmed fixes** (approved): relieve the `contribution` cap problem, stop a malformed `ask` from dropping a person, fix the skipped-clarification contradiction, and correct the `processing` message.
3. **Card content** (assistant's recommendation, accepted for now): show `contribution` labelled as an unverified model summary and keep the role as a label.
4. **One end-to-end live measurement** on the new fixture against the expectations file, counting obvious errors only. Requires a separately approved call budget.
