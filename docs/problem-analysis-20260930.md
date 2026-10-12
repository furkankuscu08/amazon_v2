# WorkBot problem analysis and solution decisions — 30 September 2026

## Scope and evidence standard

This is an evidence-led diagnosis and discussion plan, not a new product specification or authorization to implement the options below. Separate three questions: did the call complete and validate, is the proposed person/source useful, and are the role and question claims supported? A schema-valid response is not a semantically correct review; a neutral displayed question does not verify the proposed role.

Historical evidence comes from the immutable high/low synthetic trace fixtures, their separate assistant-reviewed labels, the incomplete four-invocation GLM observation, and current offline audit replay. These overlapping campaign-focused examples are not independent human validation or general accuracy estimates. Use each run's actual consultation need, keep genuinely debatable dimensions pending, and do not equate useful advisors with area specialists or verified owners.

## New observation boundary

The user separately approved at most three paid area invocations of the same previously schema-failing Integration/Growth context. The idea, answers, generated need, ordered seven-person candidate pool/evidence, area prompt, model, provider allowlist, requested high reasoning, 8,192-token cap, and HTTPX 90-second network-operation timeout are held fixed. Each observation uses a separate standalone background process and exclusively claimed directory. There is no impact/retrieval/priority rerun, old/new prompt comparison, automatic retry, provider fallback, or application change. A separately scheduled replication consumes another approved invocation; it is not a failed-attempt recovery mechanism.

Artifacts are local under `/tmp/opencode/workbot-schema-observation-20260930/`: the fixed `manifest.json`, `approval.json`, task-start `protected_hashes.json`, separate `observation-001` through `observation-003` directories, offline replay examples, and separate assistant review. The older lost fourth GLM outcome remains unknown and is not replaced or relabeled by these observations.

All three approved invocations started and have retained summaries and terminal markers. The two valid responses and their current-audit outputs were saved separately; the truncated call has no validated response. The three-call budget is exhausted. No paid invocation, retry, or changed-setting comparison is authorized beyond these observations.

| Observation | Outcome | Finish | Duration (s) | Prompt tokens | Completion tokens | Reasoning tokens | Retained proposals/current audit |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 001 | Schema-valid | `stop` | 61.214 | 1,483 | 1,204 | 849 | Nina direct; Elena and Owen advisors; all accepted |
| 002 | Confirmed `output_truncated` | `length` | 299.853 | 1,483 | 8,192 | 8,192 | No validated output; not abstention |
| 003 | Schema-valid | `stop` | 30.687 | 1,483 | 812 | 589 | Owen direct; Nina advisor; both accepted |

All three recorded HTTP 200. Counts are nullable provider-reported observations, not independently verified billing or internal reasoning traces. The 299.853-second reply does not imply that HTTPX ignored its 90-second network-operation timeout; that setting is not a hard total-call deadline. No actual billed-cost record was queried. These are area-call/audit observations, not new full HTTP/UI sessions or measurements of a population failure rate.

**What changed in our knowledge:** The old schema failure did not recur in any of the three observations, so there is still no exact field/rule diagnosis and no new validation error family to interpret. In contrast, a completion-cap failure is now observed with the shipped GLM/request configuration, not just the older experimental DeepSeek configuration. In that one call the provider-reported reasoning count equals its completion count and the requested output cap. This supports reasoning-budget exhaustion as the reported mechanism for this observation; it does not prove that requesting `high` caused it, that lowering effort solves it, or that the older DeepSeek failures had the same cause. The wrapper rejected `length` before parsing content, so no raw body or visible-output-token count was retained or reconstructed.

**Separate semantic observations:** Same-context Owen changed from advisor to direct and Nina from direct to advisor; the output also omitted Elena on observation 003. This establishes observed variability, not which model setting caused it. Source-based assistant review treats Owen as a useful integration-explaining advisor for this generated Growth scheduling/operator need, without evidence of personal operations-work on it; observation 003's stronger direct proposal still passes audit. This does not undo the earlier supported Owen direct control for the different, exact-integration need. Nina's broad operator-expectations/direct-support boundary and Elena's report-primary usefulness remain pending rather than transferring old Commerce labels to Growth. Their unresolved dimensions are not scored.

**Question examples:** Observation 001 asks how launch coordination depends on the integration, though that dependency is not recorded. Observation 003 asks Owen “should automated fixes be triggered now?”, introducing an undocumented operational mechanism/action, and attributes planned scheduling activities to Nina although her source establishes launch-review coordination. These are assistant-reviewed unsupported original premises, not proof the people are useless. Current-audit questions are neutral replacements. Nina's literal `unverified: "None"` is also schema-valid but does not satisfy the prompt's uncertainty instruction; the audit replaces it with its fixed caution. The safe JSON structure and the semantic/instruction failures must remain separate.

## Problems and root-cause confidence

### 1. Supported source/person links can still yield unsupported direct roles

**Observed problem:** Historical high/low labels identify 13 + two unsupported model `direct_contact` proposals; nine + two survived their captured audits. The low historical Commerce and privacy Commerce Nina proposals also survive replay against today's code as `direct_contact`. Nina can be a useful advisor; the failure is the stronger direct claim, not necessarily showing Nina at all.

**Concrete evidence:** In privacy/Commerce, the primary record only says “Finalize the retail campaign audience approval checklist before launch.” It establishes Nina's assignee link, not her work on the generated need's operational data sources or audience definitions. In historical/Commerce, coordinating a current launch review does not establish work comparing the former process's operational assumptions. See `tests/fixtures/quality_low_labels.json`, `tests/fixtures/quality_low_traces.json`, and the new local `audit_examples.json` replay.

**Confirmed acceptance mechanism:** `audit_area` accepts a direct proposal when the model says `relevance=direct` and the primary source has an eligible strong personal link. It verifies access and link type but does not independently test source-to-need semantic entailment. The normal workflow already supplies the full consultation need in the area item; the audit does not use it for semantic validation, so merely adding an argument would not close this boundary. Thus a model's mistaken semantic assertion can pass unchanged; role confidence and a warning about uncertainty do not repair that assertion.

**Not established:** Why the model made a particular overclaim—prompt wording, provider/model behavior, sparse source detail, candidate distraction, or their interaction. The code boundary explains acceptance, not the model's internal generation cause. The current prompt already explicitly distinguishes strong links from work on the need; more wording is not automatically a remedy.

### 2. Original model questions assert facts absent from their citations

**Observed problem:** Historical assistant review marked unsupported premises in 21/40 high and 8/14 low scored original questions. Examples include undocumented checklist consent/control contents, API launch signals, or differences a coordinator is supposedly already finding. In the earlier valid GLM historical/Platform response, useful Nina/Priya advisors still had unsupported questions about an interface or retired steps. These counts concern captured model asks, not today's neutral card questions.

**Confirmed observable failure:** A model extends a brief work record into a specific system/process claim not established by that record. Ending in `?` does not make the premise an open inquiry: “Which checks are part of it?” assumes the checks exist; “Does it include any checks?” need not. `workbot/models.py:66` checks length, and `workbot/service.py:285` checks format/IDs, not semantic premises.

**Current mitigation and remaining boundary:** Accepted card questions are replaced by `_grounded_ask`, and model uncertainty text is replaced by a stable caution. Replay confirms these presentation guards; they do not improve the model's original reasoning or downgrade an unsupported direct role. The particular generation trigger remains unproven. Do not remove the format-drop contract or claim that neutral wording solves contact relevance.

### 3. A completed provider reply can fail the local schema

**Observed problem:** The previous GLM Integration/Growth reply finished with `stop` and 1,940 completion tokens but failed local validation. It was not a token-cap failure. Its precise violated field/rule was not retained and cannot be reconstructed retrospectively.

**Confirmed validation boundary:** `workbot/llm.py:191` requests strict JSON schema, then `workbot/llm.py:252` validates locally. `PersonProposal.primary_is_cited` and `AreaEvaluation.unique_people` add relational checks not represented by the exported ordinary field schema. Provider parameter compatibility and `strict: true` do not prove those Python rules were enforced upstream. Ordinary length/type/enum violations are also possible; the older failure alone does not identify which occurred.

**Diagnostic limitation:** The current safe diagnostics identify allowlisted error families, not fields/indices, messages, or rule names. Offline examples of both uncited primary evidence and duplicate people yield `value_error`; therefore a live `value_error` would not distinguish them. It would be invalid to infer an exact custom rule, save raw validation inputs, or tighten role/relevance combinations based on that family alone. Whether the new observations narrow this problem is recorded separately above.

### 4. Some older experimental replies exhausted the completion cap

**Observed problem and proximate cause:** Two high and two low experimental DeepSeek/Nitro area replies stopped with `finish_reason=length` at the 8,192-token cap. Truncation prevents a complete locally validated area result and produces an incomplete review. A card produced from other areas does not mean all areas were reviewed.

**New evidence and remaining uncertainty:** The older captures still have no reasoning-token breakdown and do not establish excessive internal reasoning versus verbose final output. The earlier three observed GLM replies had no `length` finish; the fourth was unobserved. The new observation 002 does establish cap exhaustion with the shipped request settings and reports all 8,192 completion tokens as reasoning. [OpenRouter's official reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens#reasoning-tokens-and-max_tokens), checked on 30 September 2026, explains that on most providers reasoning and visible output share `max_tokens` and that reasoning can exhaust the budget before a completed answer. This is consistent with the new retained counts, not an independent verification of provider accounting, visible content, or the effect of the requested effort. Do not infer the older DeepSeek failure mechanism, a general GLM failure rate, or a global budget/provider change from this one context.

### 5. The old probe lost one started invocation's observation

**Confirmed root cause of the missing local record:** The previous four-call batch shared a 420-second foreground command deadline and buffered diagnostics before saving a result after audit. The command ended during its fourth invocation, leaving no retained summary/result for it. This is an observation-process failure, not an established HTTP timeout, token-cap failure, provider abstention, or billing outcome.

**Implemented mitigation:** The single-area harness persists the start before invocation, summary in the logger callback, safe validated response before audit, and terminal execution separately. Standalone background processes avoid the shared foreground deadline. The exclusive directory claim prevents duplicate reuse; storage/interruption can still leave partial observations. A failure event emitted from the production wrapper's `finally` is not a confirmed call failure without a caught-`ModelError` marker. The new observations test actual artifact retention on completed calls, not guaranteed recovery from every possible kill or disk failure.

### 6. Earlier measurement conflated usefulness, direct support, and failures

**Confirmed evaluation problem:** Some former negative labels required area expertise even for an advisor, or treated absent source details as a false conditional impact hypothesis. Some old empty cards followed malformed proposed asks rather than true model abstention. Re-review changed labels/denominators, not application outputs. Today's workflow distinguishes a malformed otherwise eligible review from genuine empty/unsupported results.

**Correction:** Keep person plus correct-primary coverage, unsupported direct claims, original-question premises, format drops, schema/transport failures, and actual abstention separate. The user approved the advisor rubric, not each assistant judgment. Retain pending judgments without counting them as successes or failures. This correction explains improved historical scores, not improved model quality.

## Tempting explanations that are not yet root causes

- **Retrieval noise:** Broad BM25 `OR` terms and overlapping candidate pools are observable (`workbot/search.py:150`), but the positive references in the scored historical examples were available. Related records can legitimately support advisors across teams. Noise may distract the model; no ablation establishes that causal effect, so an org-only filter or arbitrary semantic threshold risks losing useful contacts.
- **Missing context:** Synthetic work records are deliberately short and do not enumerate system controls or process contents. This limits what can be evidenced; it does not authorize inventing detail. Richer synthetic evidence could help, but would change the task and cannot be called a prompt fix.
- **Model/provider choice and reasoning effort:** Observations across different needs, pools, models, settings, and code versions are confounded. They are not evidence that one provider or reasoning setting caused better semantic quality. Do not change these together with prompt/search changes.
- **Role/relevance contradiction:** An advisor marked `relevance=direct` conflicts with the prompt convention but is intentionally schema-valid. It is not itself an unsupported `direct_contact` role and does not explain a separate schema failure.

## Recommended solution discussion

The highest-priority contact-quality issue is **semantic overclaim**, not simply invalid JSON; the newly observed shipped-model cap exhaustion is a separate concrete reliability issue. Preserve useful people and correct primary sources while reducing unsupported direct claims and question premises. Do not force every area to contain a person or conflate reliable completion with correct meaning.

| Option | Benefit | Cost/risk | Recommendation |
| --- | --- | --- | --- |
| Isolated requested `high` versus `low` reasoning comparison, with the same 8,192 cap and prompt | Tests the newly supported operational hypothesis without simultaneously changing prompt/retrieval/provider | Lower effort may harm quality or still exhaust tokens; catalog support is not proof of its effect | First reliability discussion; separate approval and an isolated experimental arm are needed, not a production default switch |
| Evaluate the already implemented prompt against its predecessor on matched fixed contexts | Tests the least invasive semantic intervention without changing the application contract | Requires separately approved repeated paid observations; selected cases are still not a general quality benchmark | First semantic decision; hold reasoning fixed across prompt arms and do not overlap it with an effort experiment |
| If overclaims persist, trial one short source-to-need contribution field | Makes the claimed bridge observable and easier to review; could reduce silent jumps from role/title to relevance | More output/schema surface; explanations can also be fabricated and are not independent verification | Conditional later experiment, not an automatic implementation |
| Candidate pruning/retrieval ablation | Can test whether distracting evidence causes failures | Cross-team advisors and historical authors may be lost; relevance thresholds require broader labels | Defer unless a fixed-prompt ablation demonstrates a need |
| Raise the completion cap or change provider | Could allow a longer completion or target a measured provider issue | More cost/latency; a larger cap may merely permit longer reasoning, and a different provider confounds the diagnosis | Not the first choice on these observations; no automatic fallback or budget increase |

Do not start with a fourth model verifier, blanket direct-to-advisor conversion, blanket historical-source rejection, silent partial-JSON salvage, or automatic retries. These either change the approved product behavior or conceal the original failure instead of testing the suspected mechanism.

The read-only public [model catalog](https://openrouter.ai/api/v1/models) currently lists GLM 5.3 Flash reasoning as mandatory and supported efforts as `max`, `high`, and `low`; the [pinned endpoint metadata](https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints) advertises reasoning/structured-output support. These were checked without a paid generation or credentials. Do not prescribe `none`, assume `medium` or an exact `reasoning.max_tokens` cap is supported, or treat catalog metadata as proof the endpoint's effort effect was validated. An effort trial must assess schema completion, `length`, latency/available usage, useful primary-backed contacts, direct support, and original premises separately. Three unchanged-setting observations do not validate any candidate solution.

For a later matched prompt comparison, preselect known failures, useful advisors, a supported exact-integration direct control, hard negatives, and fresh synthetic references. Hold needs, candidates/evidence/order, audit, and request settings fixed; repeat both arms and counterbalance order. Judge usefulness/primary coverage independently of direct support and original question premises, excluding pending dimensions. Favor a change only if it reduces overclaims without losing useful advisors or supported direct contacts. The current three observations are one diagnostic arm, not that comparison.

## Validation boundary

During this diagnosis, 156 related offline harness/LLM/audit-replay tests passed. They verify observation/request/audit behavior, not live semantic quality. Task-start hashes confirm that application code, prompts, schemas, retrieval, settings, tests, immutable traces, historical labels, and prior dirty work remain unchanged; only the related documentation and new local observation/review artifacts were added or updated. The current observation has no matched alternate effort or old-prompt arm, and no candidate solution has been implemented or validated.
