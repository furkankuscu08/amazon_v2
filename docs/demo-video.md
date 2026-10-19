# Demo video script (draft)

**Status: working draft, not final.** Written on 14 October 2026; the user will revisit it. Any line, timing, or decision below may change. On 18 October 2026 the facts about the demo card were rechecked against a run on the hosted demo with Amazon Nova 2 Lite: a clarification question, then three people (Omar Haddad and Tara Reed in Finance, Jules Carter in Growth Marketing; the plan now names Tara before Omar because his approver role has ended), about 30 seconds after the answer. People, questions, and wording vary from run to run, so recheck them against the run that is recorded. On 19 October 2026 the impact prompt stopped asking which reviews or approvals an idea needs; in five live runs of this idea afterwards no clarification was asked, and Legal and Compliance (Anders Holm, who reviews changes to the spending approval policy) appeared in three (those runs still had a policy-review document for him, removed the same day; in four later runs without it he appeared in one, and Omar with his ended-role note in two). The question in the 0:30–0:52 row comes from the old prompt: unless the recorded run asks one, follow the no-question instruction under "Before recording".

## Decisions so far

- One TTS narrator. The app's own voice is Amazon Polly reading the clarification question, the plan summary, and follow-up answers aloud as each arrives (or on **Listen**), so record that audio from the app itself; add no other WorkBot voice. Maya can speak her idea with **Speak** (Amazon Nova 2 Sonic fills the box, and she sends it herself); if the recording is used, show the box filling, not an added voice.
- Under three minutes (target 2:50) with about 300 narrated words, leaving time for the app's own voice (Listen) and silent screen actions.
- The story is the contrast between who handles the decision today (Tara) and who used to (Omar); Jules gets one sentence.
- Ideas whose stored cards showed a wrong direct contact (pickup lockers, campaign AI) stay out of the video.
- Claims stay within what the code does: code checks record visibility and the person's link to it, not whether a record answers the area's question; the card shows no model-written summary of a person.

## Timeline

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:12 | Home page, empty prompt | "Before you change how something works at a company, you need to know who to involve. Titles don't tell you who handles it today, or who only used to." |
| 0:12–0:30 | Maya types the idea and sends it | "This is WorkBot, a simulated Alexa+ web experience built on Amazon Bedrock, for employees proposing a change that crosses teams. Maya, at a fictional retailer with synthetic records, wants to raise the approval threshold for marketing spend, so small changes need no review." |
| 0:30–0:52 | First waiting page, sped up; the clarification question appears and Alexa reads it aloud; Maya types her answer (sped up) and continues | (the app's voice: "One clarification before searching. Does changing the marketing spend approval threshold require compliance review for policy updates?") "Maya answers: the threshold is set in the spending approval policy." |
| 0:52–0:58 | Second waiting page, sped up; caption "Sped up · recorded run: [DURATION] after the answer" | "Each team the idea touches is reviewed in parallel, over records Maya may see." |
| 0:58–1:16 | Plan appears and Alexa reads the "Alexa says" panel aloud; then highlight the two area cards | (the app's voice: "Before you start, talk to three people. Start with Tara Reed and Omar Haddad in Finance. Omar Haddad's approver role ended in June 2025. Then Jules Carter in Growth Marketing. Each card says what to find out. One more area is in the full list. Ask me why anyone is listed, or what to ask them.") "Tara Reed currently reviews marketing spend requests above the threshold. Jules Carter reviews campaign launch approvals." |
| 1:16–1:38 | Maya presses the "Why Omar?" suggestion; Alexa answers aloud in a new "Alexa says" panel; click its "Source" → 2024 policy record → back | (the app's voice: the recorded answer, for example "Omar Haddad is listed under Finance as an advisor. Wrote a document: ‘This budget approval policy was written in 2024 …’ Omar Haddad's approver role ended in June 2025.") "Tara approves requests today; Omar only used to." (Start the narration after the app voice ends; re-time this row against the recorded answer.) |
| 1:38–1:58 | Open the full list; show the evidence lines and source links; 4-second cut to a "No contact found" line on another card, only if a recorded card has one | "The full list shows each person's evidence, with links to the records. Restricted records never reach search, the model, or the screen." |
| 1:58–2:04 | Home page, earlier ideas | "Earlier ideas stay on the home page, ready to reopen." |
| 2:04–2:26 | Architecture diagram (below) | "Under the hood, Amazon Nova 2 Lite on Bedrock maps the areas, reviews each in parallel, and chooses who to talk to first. Between stages, code checks that each cited record is visible and linked to the person. Relevance stays the model's judgment. Nova 2 Sonic turns speech into text; Polly reads the answers aloud. Follow-up answers are built by code from the plan, so Alexa never says more than the screen." |
| 2:26–2:46 | Plan again | "Why Alexa+? A short request becomes a short spoken plan, with evidence cards for detail. Next, the same checks could run over real tickets, documents, and a company directory, with their permissions. WorkBot sends no messages and makes no decisions. It shows who to talk to first, and why." |
| 2:46–2:50 | End card: WorkBot · simulated Alexa+ web experience · synthetic data · Amazon Bedrock · GitHub URL | (silence) |

The reference run had no gap, so the 1:38–1:58 row has no gap sentence. If the recorded card shows one under "Still open", add the cut and "Where visible records support no one, it shows a gap, not a name."

**Diagram:** Idea → Map areas (model) → Search: keyword + vector, visible records only → Review each area in parallel (model) → Code check: record visibility + person's link → Choose first conversations (model, accepted people only) → Plan. Footnote: "Relevance is a model judgment, not checked by code." Corner label: "Amazon Bedrock · Amazon Nova 2 Lite". Side note for voice: "Speak → Nova 2 Sonic (speech to text) · Listen → Amazon Polly · Follow-ups → rules over the plan, no model".

## Before recording

- Record from a fresh, separately approved live run (the hosted demo works); do not present stored OpenRouter output as Bedrock output. Fill in [DURATION] from that run.
- Check that Omar appears as "Related work" with the note "Approver role ended on 2025-06-30.", that Tara and Jules appear as "Current responsibility", and whether a clarification question is asked; rewrite 0:30–1:38 to match the recorded run, including the number of people in the spoken plan. Without a question, cut the 0:30–0:52 row to the first waiting page and give the time to the plan. Quote the question and the "Alexa says" text in captions exactly as the app says them.
- Show only clean Bedrock-generated ideas in the home-page list.
- 1920×1080, browser zoom 125%; type the idea in real time; speed up only the two waiting pages and the typing of the answer.
