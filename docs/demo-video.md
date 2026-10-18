# Demo video script (draft)

**Status: working draft, not final.** Written on 14 October 2026; the user will revisit it. Any line, timing, or decision below may change. On 18 October 2026 the facts about the demo card were rechecked against a run on the hosted demo with Amazon Nova 2 Lite: a clarification question, then three people (Omar Haddad and Tara Reed in Finance, Jules Carter in Growth Marketing), about 30 seconds after the answer. People, questions, and wording vary from run to run, so recheck them against the run that is recorded.

## Decisions so far

- One TTS narrator. The app's own voice is its **Listen** button (Amazon Polly reading the plan summary or the clarification question), so record that audio from the app itself; add no other WorkBot voice. Maya can speak her idea with **Speak** (Amazon Nova 2 Sonic fills the box, and she sends it herself); if the recording is used, show the box filling, not an added voice.
- Under three minutes (target 2:50) with about 330 narrated words, leaving time for silent screen actions.
- The story is the contrast between who handles the decision today (Tara) and who used to (Omar); Jules gets one sentence.
- Ideas whose stored cards showed a wrong direct contact (pickup lockers, campaign AI) stay out of the video.
- Claims stay within what the code does: code checks record visibility and the person's link to it, not whether a record answers the area's question; only person summaries are labelled unverified.

## Timeline

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:12 | Home page, empty prompt | "Before you change how something works at a company, you need to know who to involve. Titles don't tell you who handles it today, or who only used to." |
| 0:12–0:30 | Maya types the idea and sends it | "This is WorkBot, a simulated Alexa+ web experience built on Amazon Bedrock, for employees proposing a change that crosses teams. Maya, at a fictional retailer with synthetic records, wants to raise the approval threshold for marketing spend, so small changes need no review." |
| 0:30–0:40 | The clarification question; press **Listen** and let it play, then Maya types her answer and continues | (the app's voice reads the question: does changing the threshold require compliance review?) "Maya answers: the threshold is set in the spending approval policy." |
| 0:40–0:46 | Progress page, sped up; caption "Sped up · recorded run: [DURATION]" | "Each team the idea touches is reviewed in parallel, over records Maya may see." |
| 0:46–1:00 | Plan appears; press **Listen** on the "Alexa says" panel and let it play, then highlight the two area cards | (the app's voice: "Before you start, talk to three people. Start with Omar Haddad and Tara Reed in Finance. Then Jules Carter in Growth Marketing. Each card says what to find out.") "Tara Reed currently reviews marketing spend requests above the threshold. Jules Carter reviews campaign launch approvals. Each card says what to find out from that team." |
| 1:00–1:25 | Omar's line → click "source" → 2024 policy record → back → highlight the directory note | "Then there's Omar Haddad. Omar wrote the 2024 approval policy, so Omar is listed as an advisor. A separate directory note says that approver duty ended in June 2025. So Maya sees the difference between who handles this today and who used to." |
| 1:25–1:48 | Open the full list; show "Model summary (unverified)" and source links; 4-second cut to a "No contact found" line on another card, only if a recorded card has one | "The full list shows each person's evidence, with links to the records. Person summaries written by the model are labelled unverified. Restricted records never reach search, the model, or the screen. Where visible records support no one, it shows a gap, not a name." |
| 1:48–1:56 | Home page, earlier ideas | "Earlier ideas stay on the home page, ready to reopen." |
| 1:56–2:22 | Architecture diagram (below) | "Under the hood, Amazon Nova 2 Lite on Bedrock maps the areas, reviews each in parallel, and chooses who to talk to first. Between stages, code checks that each cited record is visible and linked to the person. Relevance stays the model's judgment. Nova 2 Sonic turns speech into text; Polly reads the answer aloud." |
| 2:22–2:45 | Plan again | "Why Alexa+? A short request becomes a short plan, with evidence cards for detail. Next, the same checks could run over real tickets, documents, and a company directory, with their permissions. WorkBot sends no messages and makes no decisions. It shows who to talk to first, and why." |
| 2:45–2:50 | End card: WorkBot · simulated Alexa+ web experience · synthetic data · Amazon Bedrock · GitHub URL | (silence) |

If no recorded card shows a gap, drop the cut and the sentence "Where visible records support no one, it shows a gap, not a name."

**Diagram:** Idea → Map areas (model) → Search: keyword + vector, visible records only → Review each area in parallel (model) → Code check: record visibility + person's link → Choose first conversations (model, accepted people only) → Plan. Footnote: "Relevance is a model judgment, not checked by code." Corner label: "Amazon Bedrock · Amazon Nova 2 Lite". Side note for voice: "Speak → Nova 2 Sonic (speech to text) · Listen → Amazon Polly".

## Before recording

- Record from a fresh, separately approved live run (the hosted demo works); do not present stored OpenRouter output as Bedrock output. Fill in [DURATION] from that run.
- Check that Omar, Tara, and Jules still appear with the same roles and that Omar's ended-duty note is shown, and that a clarification question is asked; rewrite 0:30–1:25 if not. Without a question, drop the 0:30–0:40 row and give its time to the plan.
- Show only clean Bedrock-generated ideas in the home-page list.
- 1920×1080, browser zoom 125%; type the idea in real time and speed up only the waiting page.
