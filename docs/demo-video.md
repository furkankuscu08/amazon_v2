# Demo video script (draft)

**Status: working draft, not final.** Written on 14 October 2026 before the move to Amazon Bedrock; the user will revisit it. Any line, timing, or decision below may change. Facts about the demo card come from a stored OpenRouter run and must be rechecked against the card recorded on Bedrock.

## Decisions so far

- One TTS narrator. The app's own voice is its **Listen** button (Amazon Polly reading the plan summary or the clarification question), so record that audio from the app itself; add no other WorkBot voice. The app has no voice input, so Maya's idea is typed, not spoken.
- Under three minutes (target 2:50) with about 330 narrated words, leaving time for silent screen actions.
- The story is the contrast between who handles the decision today (Tara) and who used to (Omar); the other two people get one sentence.
- Ideas whose stored cards showed a wrong direct contact (pickup lockers, campaign AI) stay out of the video.
- Claims stay within what the code does: code checks record visibility and the person's link to it, not whether a record answers the area's question; only person summaries are labelled unverified.

## Timeline

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:12 | Home page, empty prompt | "Before you change how something works at a company, you need to know who to involve. Titles don't tell you who handles it today, or who only used to." |
| 0:12–0:30 | Maya types the idea and sends it | "This is WorkBot, a simulated Alexa+ web experience built on Amazon Bedrock, for employees proposing a change that crosses teams. Maya, at a fictional retailer with synthetic records, wants to raise the approval threshold for marketing spend, so small changes need no review." |
| 0:30–0:38 | Progress page, sped up; caption "Sped up · recorded run: [DURATION]" | "WorkBot maps the teams the idea touches, then reviews each one in parallel, using only records Maya is allowed to see." |
| 0:38–1:00 | Plan appears; highlight the area cards, each with what to find out and the people to ask | "The answer: four people to talk to first. Tara Reed currently reviews marketing spend requests above the threshold. Marcus asked for the Q-four budget reforecast; Ines wrote notes on when supplier contracts still need a wet signature. Each comes with what to find out from their team." |
| 1:00–1:25 | Omar's line → click "source" → 2024 policy record → back → highlight the directory note | "Then there's Omar Haddad. Omar wrote the 2024 approval policy, so Omar is listed as an advisor. A separate directory note says that approver duty ended in June 2025. So Maya sees the difference between who handles this today and who used to." |
| 1:25–1:48 | Open the full list; show "Model summary (unverified)" and source links; 4-second cut to a "No contact found" line on another card, only if a recorded card has one | "The full list shows each person's evidence, with links to the records. Person summaries written by the model are labelled unverified. Restricted records never reach search, the model, or the screen. Where visible records support no one, it shows a gap, not a name." |
| 1:48–1:56 | Home page, earlier ideas | "Earlier ideas stay on the home page, ready to reopen." |
| 1:56–2:22 | Architecture diagram (below) | "Under the hood, three model stages run on Amazon Bedrock: map the areas, review each one in parallel, and choose who to talk to first. Between them, code checks that each cited record is visible and that the person is linked to it. Relevance stays the model's judgment." |
| 2:22–2:45 | Plan again | "Why Alexa+? A short request becomes a short plan, with evidence cards for detail. Next, the same checks could run over real tickets, documents, and a company directory, with their permissions. WorkBot sends no messages and makes no decisions. It shows who to talk to first, and why." |
| 2:45–2:50 | End card: WorkBot · simulated Alexa+ web experience · synthetic data · Amazon Bedrock · GitHub URL | (silence) |

If no recorded card shows a gap, drop the cut and the sentence "Where visible records support no one, it shows a gap, not a name."

**Diagram:** Idea → Map areas (model) → Search: keyword + vector, visible records only → Review each area in parallel (model) → Code check: record visibility + person's link → Choose first conversations (model, accepted people only) → Plan. Footnote: "Relevance is a model judgment, not checked by code." Corner label: "Amazon Bedrock · [MODEL]".

## Before recording

- Record only after the Bedrock migration, from a fresh, separately approved live run; do not present stored OpenRouter output as Bedrock output. Fill in [MODEL] and [DURATION] from that run.
- Check that Tara, Marcus, Ines, and Omar still appear with the same roles and that Omar's ended-duty note is shown; rewrite 0:38–1:25 if not.
- Show only clean Bedrock-generated ideas in the home-page list.
- 1920×1080, browser zoom 125%; type the idea in real time and speed up only the waiting page.
