# Demo video script (draft)

**Status: working draft, not final.** Written on 14 October 2026 and restructured on 19 October 2026; the user will revisit it. Any line, timing, or decision below may change. Claude will produce the video; when is not decided yet.

The story is told on the **saved marketing-spend plan** on the hosted demo's home page (session `98cd71eb…`, made with Amazon Nova 2 Lite on 19 October 2026), so the video says word for word what the Devpost text quotes and what a judge sees on opening that plan. A **separate live run** of another idea then shows the app working end to end. People, questions, and wording vary from run to run, so the live segment is written after it is recorded, and nothing from it is presented as the saved plan or the other way round.

Facts of the saved plan, as the hosted page shows them on 19 October 2026:

- Idea: "Raise the approval threshold for marketing spend requests so small changes need no review." Alexa asked "Does raising the approval threshold involve any compliance or regulatory changes?" and Maya continued without answering.
- "Alexa says": "Before you start, talk to two people. Start with Tara Reed and Omar Haddad in Finance. Omar Haddad's approver role ended in June 2025. Each card says what to find out. One area is still open. Ask me why anyone is listed, or what to ask them."
- Finance card: Tara Reed, "Current responsibility", "Current reviewer — reviewing marketing spend requests above the approval threshold."; Omar Haddad, "Can advise", "Wrote a document: ‘This budget approval policy was written in 2024 and describes the spend thresholds in force at that time.’" with "Approver role ended on 2025-06-30."
- "Still open": "Team not identified for: Legal and Compliance." This is a mapping gap, not a search that found no one: the impact model left the area without a team because Maya skipped its compliance question (its reason, kept on the card but no longer shown: "Answer about compliance/regulatory changes is pending but questions exhausted"). The fixture's Legal and Compliance team exists, and other runs of this idea named someone there.
- Suggestions: "Why Omar?", "Prep me for Tara", "What's still open?". "Why Omar?" answers: "Omar Haddad is listed under Finance as an advisor. Wrote a document: ‘This budget approval policy was written in 2024 and describes the spend thresholds in force at that time.’ Omar Haddad's approver role ended in June 2025." "What's still open?" answers: "The team was not identified for Legal and Compliance."

## Decisions so far

- Two voices only: a narrator, and the app's own voice (Amazon Polly reading the plan summary, a clarification question, and follow-up answers). Record the app's voice from the app itself, and give the narrator a different voice so the two are never confused (which one is open). Maya speaks only through **Speak** (Amazon Nova 2 Sonic fills the box, and she sends it herself); show the box filling, not an added voice.
- Under three minutes (target 2:57) with about 220 narrated words, leaving time for the app's voice and silent screen actions.
- The story is the contrast between who handles the decision today (Tara) and who used to (Omar), told on the saved plan; a caption marks it as a plan saved from an earlier run.
- The live segment uses another example idea, so the home page does not show the same idea twice; stablecoin payments is the default.
- Ideas whose stored cards showed a wrong direct contact (pickup lockers, campaign AI) stay out of the video.
- Claims stay within what the code does: code checks record visibility and the person's link to it, not whether a record answers the area's question; the card shows no model-written summary of a person, and code assembles every sentence Alexa says in the plan summary and follow-up answers; the only model-written text on the page is the area names, what to find out, the shared question, and a clarification question.

## Timeline

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:10 | Home page | "Before you change how something works at a company, you need to know who to involve. Titles don't tell you who handles it today, or who only used to." |
| 0:10–0:20 | Open the saved marketing-spend idea from "Your earlier ideas"; the caption "Saved plan from an earlier run" stays on screen whenever this plan is shown | "This is WorkBot, a simulated Alexa+ experience on Amazon Bedrock. Maya, at a fictional retailer, wants to raise the approval threshold for marketing spend." |
| 0:20–0:42 | Press **Listen** on "Alexa says"; then highlight the Finance card | (the app's voice reads the "Alexa says" text above, about 19 seconds) "Tara Reed reviews these requests today." |
| 0:42–1:08 | Press "Why Omar?"; the answer appears and Alexa reads it; click its **Source** → the 2024 policy record → the browser's Back button (the page's own "Back to the plan" link reloads the plan and drops the follow-up) | (the app's voice: the "Why Omar?" answer above, about 15 seconds) "Omar wrote the policy, but his approver role ended. Tara handles it today." |
| 1:08–1:18 | Press "What's still open?"; then the "Still open" box | (the app's voice: "The team was not identified for Legal and Compliance.") "Maya skipped Alexa's compliance question, so that area stays open, with no name guessed." |
| 1:18–2:02 | Home page; Maya presses **Speak** and says the stablecoin idea; the box fills; she presses **Ask Alexa**; waiting page sped up, caption "Live run · sped up · [DURATION]"; the plan arrives and Alexa reads it aloud | "Now a new idea, live. Nova 2 Sonic turns Maya's voice into text in the box; nothing runs until she presses Ask Alexa. Each area the idea touches is reviewed in parallel, over records Maya may see." (Rewrite after recording. If Alexa asks a question, press "Continue without answering", keep only the first sentence of its spoken question, and speed up the second wait.) |
| 2:02–2:18 | The new plan: its cards, then the full list with evidence lines and source links | "Every person comes with evidence, linked to the record behind it. Restricted records never reach search, the model, or the screen." (Name people only as the recorded plan shows them; a routing contact's card line has no Source link, so do not point at one.) |
| 2:18–2:38 | Architecture diagram (below) | "Under the hood, Amazon Nova 2 Lite finds the areas, reviews each in parallel, and chooses who to talk to first. Code checks that each cited record is visible and linked to the person. Polly speaks, and follow-up answers are built by code from the plan." |
| 2:38–2:53 | The saved plan again, with its caption | "Why Alexa+? A short idea becomes a short spoken plan, with cards for detail and a conversation about it. WorkBot sends no messages. It shows who to talk to first, and why." |
| 2:53–2:57 | End card: WorkBot · simulated Alexa+ web experience · synthetic data · Amazon Bedrock · GitHub URL | (silence) |

**Diagram:** use the gallery image "How WorkBot answers": Find the areas (Nova 2 Lite) → Search visible records only (code) → Review each area in parallel (Nova 2 Lite) → Audit the evidence (code) → Choose who to talk to first (Nova 2 Lite) → Build the plan and Alexa's summary (code); side panels for voice (Speak → Nova 2 Sonic, Alexa says → Polly, follow-ups → rules over the plan) and hosting (EC2 from CloudFormation, a role limited to Nova 2 Lite, Nova 2 Sonic, and Polly); footnote "Whether a cited record answers an area's question stays the model's judgment; code checks visibility and the person's link."

## Before recording

- Open the saved plan on the hosted demo and check it still says what "Facts of the saved plan" lists, and that its full list still shows Legal and Compliance as "Team not identified" (if not, drop the 1:08–1:18 row); a plan stops being shown if its evidence changes, so if it is gone or different, rewrite 0:10–1:16 and the Devpost text together.
- The live segment needs a separately approved live run (and budget) on the hosted demo; record it uncut, speed up only the waiting page, and fill in [DURATION] from that run. It adds an idea to the shared home page: ask the user whether to keep it afterwards.
- Quote every question and "Alexa says" text in captions exactly as the app says them.
- 1920×1080, browser zoom 125%.
