# Friction log: AWS and Amazon Bedrock

Friction met while moving WorkBot's model calls to Amazon Bedrock during the hackathon, recorded as it happened. Each entry gives the task, the steps, what was expected and what happened, a severity, the workaround, and a suggestion. Severity: **High** blocks the task until worked around; **Medium** costs real time or risks a wrong setup; **Low** is a papercut. Error texts are quoted as shown; account IDs are left out.

Setup at the time: a new account created through AWS Settings (projects owned by an AWS Builder ID, signed in with Google), AWS Free plan, project Region `eu-north-1` (Stockholm), AWS CLI 2.38.1, boto3/botocore 1.43.114, model Amazon Nova 2 Lite. All dates are 18 October 2026.

## 1. The console search for Bedrock leads to a retired product

- **Task:** open Amazon Bedrock to try a model.
- **Steps:** typed "Bedrock" in the console search and chose the first result.
- **Expected:** the Amazon Bedrock console with its model catalog.
- **Actual:** the Agents Classic page with the banner "Agents Classic will no longer be open to new customers starting on July 30, 2026", which then forwarded to the Amazon Bedrock AgentCore overview. Neither page showed a Region selector; the Region (`eu-north-1`) was visible only in the URL.
- **Severity:** Low.
- **Workaround:** edited the URL to `/bedrock/home#/model-catalog`; later picked the result named exactly "Amazon Bedrock".
- **Suggestion:** rank the Amazon Bedrock console above retired or adjacent products in search, and show the Region on every Bedrock page.

## 2. Every third-party model is denied on the Free plan, with no reason given

- **Task:** say "Hello" to a model in the Bedrock playground.
- **Steps:** opened several third-party models in the model catalog (for example `openai.gpt-6-luna`) and ran a prompt.
- **Expected:** a reply, or an error naming what is missing.
- **Actual:** `AccessDeniedException` — "openai.gpt-6-luna is not available for this account. You can explore other available models on Amazon Bedrock. For additional access options, contact AWS Sales". The same happened for every third-party model. Amazon Nova models worked.
- **Severity:** High (until Nova was tried).
- **Workaround:** used Amazon Nova. The AWS Billing guide says the Free plan excludes AWS Marketplace, through which third-party Bedrock models are subscribed; the error does not say so.
- **Suggestion:** state in the error and on the model card that the model needs the Paid plan, and link the upgrade page instead of AWS Sales.

## 3. Anthropic's use-case form assumes a company

- **Task:** enable Claude Haiku 5.5.
- **Steps:** opened the model in the catalog.
- **Expected:** access, or a short consent step.
- **Actual:** a "Submit use case details for Anthropic" form asking for a company name, company website, industry, and intended users, before any invocation; it is shared with Anthropic.
- **Severity:** Low.
- **Workaround:** entered "Individual developer" and a GitHub profile URL. (Access was blocked by entry 2 in any case.)
- **Suggestion:** offer an "individual developer / hackathon" path, and say on the form whether the account's plan allows the model at all.

## 4. Searching for "credentials" opens the Builder ID profile

- **Task:** create an access key for an IAM user to call Bedrock from code.
- **Steps:** typed "credentials" in the console search.
- **Expected:** IAM access keys.
- **Actual:** the AWS Builder ID "Security" page (sign-in method, MFA devices, signed-in devices).
- **Severity:** Low.
- **Workaround:** IAM → IAM users → the user → **Security credentials** → **Create access key**.
- **Suggestion:** list "IAM user access keys" among the search results for "credentials" and "access key".

## 5. `aws configure` asks to install agent tooling

- **Task:** store the new access key in a named profile.
- **Steps:** `aws configure --profile workbot`.
- **Expected:** the four usual prompts.
- **Actual:** after the output format a fifth prompt: "Configure AWS skills and the AWS MCP server for your AI coding agent(s)? [y/n/never]".
- **Severity:** Low.
- **Workaround:** answered `n`.
- **Suggestion:** keep credential setup to credentials, and offer agent tooling as a separate command, with a note on which files it would change.

## 6. The catalog's model ID cannot be invoked in this Region

- **Task:** call Nova 2 Lite from the CLI and boto3.
- **Steps:** used the ID the playground showed, `amazon.nova-2-lite-v1:0`; then listed the models with `aws bedrock list-foundation-models`.
- **Expected:** the playground's ID works on-demand.
- **Actual:** in `eu-north-1` the model supports only `INFERENCE_PROFILE`; the API needs `eu.amazon.nova-2-lite-v1:0` or `global.amazon.nova-2-lite-v1:0`. With the profile ID, Converse answered in 349 ms (55 input / 8 output tokens; request ID `2b8a53a9-8ea0-45de-b51d-6a8e35c26be8`).
- **Severity:** Medium.
- **Workaround:** WorkBot uses `global.amazon.nova-2-lite-v1:0` by default, which also works from other Regions.
- **Suggestion:** show the invocable ID (or inference profile IDs) for the current Region on the model card and in the playground.

## 7. The project's Region is locked, and nothing in the console says so

- **Task:** use Amazon Polly neural voices for spoken answers.
- **Steps:** `aws polly describe-voices --engine neural` in `eu-north-1`, then in `eu-central-1`, `eu-west-1`, and `us-east-1`.
- **Expected:** neural English voices in at least one Region.
- **Actual:** `eu-north-1` lists only standard voices. Every other Region: `AccessDeniedException` "… is not authorized to perform: polly:DescribeVoices with an explicit deny in a service control policy". The SCP comes from the AWS-managed organization behind AWS Settings projects. The guide exempts Bedrock inference from it, and listing Bedrock models in `us-east-1` worked; Polly is not exempt. The AWS Account Management guide documents this "RegionFloor" policy; the console never mentions it.
- **Severity:** Medium.
- **Workaround:** Polly standard voices in `eu-north-1`.
- **Suggestion:** show the project's Region restriction in the console and name the policy in the error.

## 8. A new project cannot choose its Region

- **Task:** get a project in a Region that has Polly neural voices.
- **Steps:** AWS Settings → Projects → **Create project**.
- **Expected:** a Region choice.
- **Actual:** the dialog asks only for a name; the new project (a separate AWS account) was again placed in Europe (Stockholm) `eu-north-1`.
- **Severity:** Medium.
- **Workaround:** none without activating advanced features; the extra project was not used.
- **Suggestion:** let the creator pick the project Region, or say how it is chosen.

## 9. Advanced-feature activation sends a code to an address it then refuses

- **Task:** explore activating advanced features (it lifts the Region restriction).
- **Steps:** AWS Settings → Projects → **Continue to activation** → Step 3, management account email.
- **Expected:** the form either accepts the address or rejects it before sending a code.
- **Actual:** the form pre-filled the Builder ID email and showed "The email address … is already associated with an existing AWS account. Enter a different email address for your management account.", yet still sent a verification code to it ("Code sent"). Only at **Review and complete activation** did it fail: "Unable to assign the email address provided to the specified account."
- **Severity:** Low (nothing was changed).
- **Workaround:** stopped; activation is irreversible and removes spend limits, which this prototype does not need.
- **Suggestion:** do not pre-fill or send a code to an address that cannot be used.

## 10. The spend limit's consequence is not shown where it is set

- **Task:** plan a demo that stays up through judging.
- **Steps:** opened the project menu.
- **Expected:** the effect of the limit next to it.
- **Actual:** "Monthly spend limit $0 / $20", with no hint that, per the AWS Account Management guide, a project nearing its limit gets SCPs that deny creating or invoking resources, Bedrock included.
- **Severity:** Medium.
- **Workaround:** read the guide; the limit has to be raised before a hosted demo.
- **Suggestion:** say beside the limit what stops working when it is reached.

## 11. Nova 2 Lite supports neither structured-output mechanism in the guide

- **Task:** get schema-conforming JSON for WorkBot's three tasks.
- **Steps:** followed the Bedrock structured-output guide: Converse with `outputConfig.textFormat` (JSON schema), then a tool with `strict: true`.
- **Expected:** at least one of them works with an Amazon model.
- **Actual:** `ValidationException` — "This model doesn't support the outputConfig field. Remove outputConfig and try again." and "This model doesn't support the strict field. Remove strict and try again." The errors were clear and fast (0.2–0.5 s); the guide lists supported models only through the model cards.
- **Severity:** Medium.
- **Workaround:** forced tool use (`toolChoice.tool`) without `strict`, with the full JSON schema as the tool's input schema, and local Pydantic validation of the reply. This works together with extended thinking: an area call at low effort took 2.7 s (1,978 input / 258 output tokens), an impact call at medium effort 10.5 s (1,773 / 1,267).
- **Suggestion:** list the supported models in the structured-output guide itself, and support it for Amazon's own models.

## 12. Medium reasoning effort fills the output cap

- **Task:** run WorkBot's six answer-key ideas end to end on Nova 2 Lite.
- **Steps:** extended thinking at `low` for area calls and `medium` for impact and priority, with `maxTokens` 8,192 (the `high` setting forbids `maxTokens`).
- **Expected:** a few thousand output tokens per call at most.
- **Actual:** impact and priority calls returned 3,600–8,192 output tokens in 20–46 seconds; two priority calls stopped at `max_tokens` and two impact calls ended after about 46 seconds without a tool call and with zero reported tokens (not reproducible: the same two ideas succeeded four times in a row afterwards). Reasoning tokens are counted in `outputTokens` and redacted, so it is not visible how much of the cap went to reasoning. At `low`, the same impact calls used 1,300–2,100 tokens in 10–14 seconds and stayed valid.
- **Severity:** Medium (two of six ideas were refused, and two plans fell back to the default choice of whom to talk to first).
- **Workaround:** `low` effort for all tasks, and the stop reason is now logged.
- **Suggestion:** report reasoning tokens separately in `usage`, and document typical output sizes per effort level.

## 13. An empty bearer-token variable still sends the request

- **Task:** make WorkBot's offline tests unable to reach AWS.
- **Steps:** set `AWS_BEARER_TOKEN_BEDROCK=""` (and the other credential variables) in the test environment, then called Converse.
- **Expected:** `NoCredentialsError` before any network request.
- **Actual:** botocore treated the empty variable as a configured token and sent the request, payload included, to `bedrock-runtime`. An empty `AWS_CONTAINER_CREDENTIALS_RELATIVE_URI` likewise made it call the container credential endpoint `169.254.170.2`.
- **Severity:** Medium (data leaves the machine with no credentials configured).
- **Workaround:** the test setup deletes these variables instead of blanking them.
- **Suggestion:** treat empty values as unset.

## 14. boto3 ignores `AWS_REGION`

- **Task:** configure the Region for WorkBot's Bedrock client.
- **Steps:** set `AWS_REGION=eu-north-1` with no profile, which the AWS CLI v2 honors.
- **Expected:** the client uses `eu-north-1`.
- **Actual:** `boto3.session.Session().region_name` is `None` and the call fails with `NoRegionError`; boto3 reads only `AWS_DEFAULT_REGION` or the profile's Region.
- **Severity:** Low.
- **Workaround:** WorkBot passes `region_name=os.getenv("AWS_REGION")` explicitly.
- **Suggestion:** honor `AWS_REGION` in boto3 as the AWS CLI v2 does.
