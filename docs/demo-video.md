# Demo video script (draft)

**Status: working draft, not final.** Written on 14 October 2026, restructured on 19 October 2026, and rewritten on 20 October 2026 for the new saved plan and the judges' reviews; the user will revisit it. Any line, timing, or decision below may change. Claude will produce the video; recording and editing come after this script is agreed.

The story is told on the **saved marketing-spend plan** on the hosted demo's home page (session `6f661e79…`, made with Amazon Nova 2 Lite on 20 October 2026, the first attempt after the impact-prompt change; it was kept because it passed the answer key, asked no question, and showed Omar with the ended-role note, which 7 of 10 measured runs did), so the video says word for word what the Devpost text quotes and what a judge sees on opening that plan. A **separate live run** of another idea then shows the app working end to end. People, questions, and wording vary from run to run, so the live segment is written after it is recorded, and nothing from it is presented as the saved plan or the other way round.

Facts of the saved plan, as the hosted page shows them on 20 October 2026:

- Idea: "Raise the approval threshold for marketing spend requests so small changes need no review." Alexa asked nothing.
- "Alexa says": "Before you start, talk to four people. Start with Tara Reed and Omar Haddad in Finance. Omar Haddad's approver role ended in June 2025. Then Marcus Reed in Growth Marketing, and Anders Holm in Legal and Compliance. Each card says what to find out. One more area is in the full list. Ask me why anyone is listed, or what to ask them." Read aloud, it takes 21.7 seconds.
- Finance card ("What would change in finance's approval workflow for marketing spends?"): Tara Reed, "Current responsibility", "Current reviewer — reviewing marketing spend requests above the approval threshold."; Omar Haddad, "Related work", "Wrote a document: ‘This budget approval policy was written in 2024 and describes the spend thresholds in force at that time.’" with "Approver role ended in June 2025."
- Growth Marketing: Marcus Reed, "Can advise" (reported the Q4 marketing budget reforecast Jira issue). Legal and Compliance ("Are there compliance risks in adjusting marketing spend approval levels?"): Anders Holm, "Current responsibility", "Current reviewer — compliance review of changes to the spending approval policy."
- Under the cards: "Also in the full list: Brand Review (Priya Singh)." Priya approves advertising claims in campaign copy, a loosely related area; do not show or name it in the video. Nothing is under "Still open", and there is no shared question.
- Suggestions: "Why Omar?", "Prep me for Tara", "Who else?". "Why Omar?" answers, in 14.1 seconds: "Omar Haddad is listed under Finance for related work. Omar wrote a document: ‘This budget approval policy was written in 2024 and describes the spend thresholds in force at that time.’ Omar's approver role ended in June 2025." "Prep me for Tara" answers, in 10.1 seconds: "Tara Reed is a current reviewer — reviewing marketing spend requests above the approval threshold. Ask Tara: What would change in finance's approval workflow for marketing spends?"

## Decisions so far

- The hook comes first: the video opens on Omar's ended role next to Tara's current one, before any product introduction. This contrast is the moment the judges' reviews said a viewer remembers.
- Two voices: a narrator, and the app's own voice (Amazon Polly reading the plan summary and follow-up answers), recorded from the app itself. The narrator never speaks over the app's voice. Who narrates is decided at recording (the user's own voice, a different Polly voice, or captions only); every narration line below also works as an on-screen caption. Maya is never heard: **Speak** is fed a synthetic voice sample, captioned as such, and the video shows the box filling.
- About 2:50 in all, with about 210 narrated words (about 2.5 words a second); the app's voice takes about 46 seconds on the saved plan.
- The live segment uses another example idea, so the home page does not show the same idea twice; stablecoin payments is the default. If its plan has an open area, show it: the saved plan has none.
- Ideas whose stored cards showed a wrong direct contact (pickup lockers, campaign AI) stay out of the video.
- Claims stay within what the code does: code checks record visibility and the person's link to it, not whether a record answers the area's question; the card shows no model-written summary of a person, and code assembles every sentence Alexa says in the plan summary and follow-up answers; the only model-written text on the page is the area names, what to find out, the shared question, and a clarification question.
- No gendered pronouns for any person, Maya included.

## Timeline

| Time | Screen | Narration (or caption) |
|---|---|---|
| 0:00–0:12 | Close-up of the saved plan's Finance card: Omar's "Related work" badge, the 2024 policy line, and "Approver role ended in June 2025."; then Tara's "Current responsibility" badge | "Omar Haddad wrote the 2024 budget approval policy. That approver role ended in June 2025. Maya wants to raise the threshold for marketing spend. Who should Maya ask now?" |
| 0:12–0:24 | Pull back to the top of the saved plan: Maya's idea and the "Alexa says" panel; the caption "Saved plan from an earlier run" stays on screen whenever this plan is shown | "WorkBot is a simulated Alexa+ experience on Amazon Bedrock, for employees preparing a change other teams will review. Maya says the idea; Alexa answers with who to talk to first." |
| 0:24–0:47 | Press **Listen**; the "Alexa says" panel stays in view | (the app's voice reads the "Alexa says" text above, 21.7 seconds; no narration) |
| 0:47–0:57 | Scroll to the Finance and Legal and Compliance cards; highlight the two badges and "What to find out" | "Tara Reed reviews these requests today. Omar's link is a 2024 document, and that role has ended. Each card says what to find out." |
| 0:57–1:16 | Press "Why Omar?"; the answer appears and Alexa reads it; click its **Source** → the 2024 policy record → the browser's Back button (the page's own "Back to the plan" link reloads the plan and drops the follow-up) | (the app's voice: the "Why Omar?" answer above, 14.1 seconds; no narration) |
| 1:16–1:29 | Press "Prep me for Tara"; the answer appears and Alexa reads it | (the app's voice: the "Prep me for Tara" answer above, 10.1 seconds; no narration) |
| 1:29–1:37 | The conversation on screen | "Code builds every sentence Alexa says from the plan, so the voice never says more than the screen." |
| 1:37–2:15 | Home page; Maya presses **Speak** (caption "Speak · synthetic voice sample") and the box fills with the stablecoin idea; Maya presses **Ask Alexa**; waiting page sped up, caption "Live run · sped up · [DURATION]"; the plan arrives; show its "Alexa says" panel and cards, and "Still open" if the plan has it | "Now a new idea, live. Nova 2 Sonic turns Maya's voice into text, and nothing runs until Maya presses Ask Alexa. Each area the idea touches is reviewed in parallel, over records Maya is allowed to see." (Write the rest after recording. Let Alexa read only the first sentence of the live plan, or mute it under a caption. If Alexa asks a question, press "Continue without answering" and speed up the second wait. Name people only as the recorded plan shows them; a routing contact's card line has no Source link, so do not point at one.) |
| 2:15–2:28 | Architecture diagram (below) | "Under the hood, Nova 2 Lite finds the areas, reviews each one, and picks who goes first. Between steps, code checks that each cited record is visible and tied to that person." |
| 2:28–2:46 | The saved plan again, with its caption | "Why Alexa+? This question comes up just before you act, fits in one sentence, and its answer is a few names. Alexa says them, the cards hold the evidence, and Maya can ask why. A simulation on synthetic data; WorkBot sends no messages." |
| 2:46–2:50 | End card: WorkBot · simulated Alexa+ web experience · synthetic data · Amazon Bedrock · GitHub URL | (silence) |

**Diagram:** use the gallery image "How WorkBot answers": Find the areas (Nova 2 Lite) → Search only records Maya can see (code) → Review each area in parallel (Nova 2 Lite) → Audit the evidence (code) → Choose who to talk to first (Nova 2 Lite) → Build the plan and Alexa's summary (code); side panels for voice (Speak → Nova 2 Sonic, Alexa says → Polly, follow-ups → rules over the plan) and hosting (EC2 from CloudFormation, a role limited to Nova 2 Lite, Nova 2 Sonic, and Polly); footnote "Whether a cited record answers an area's question stays the model's judgment; code checks visibility and the person's link."

## Before recording

- Open the saved plan on the hosted demo and check it still says what "Facts of the saved plan" lists; a plan stops being shown if its evidence changes, so if it is gone or different, rewrite 0:00–1:37 and the Devpost text together.
- Film each suggestion before pressing it, so the chips on screen are the ones the plan offers.
- The live segment needs a separately approved live run (and budget) on the hosted demo; record it uncut, speed up only the waiting page, never the app's voice, and fill in [DURATION] from that run. It adds an idea to the shared home page: ask the user whether to keep it afterwards.
- Quote every question and "Alexa says" text in captions exactly as the app says them.
- 1920×1080, browser zoom 125%.
