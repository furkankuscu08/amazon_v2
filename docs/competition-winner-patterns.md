# Competition Winner Patterns: Evidence-Backed Case Studies

**Purpose:** Examine ten winning projects from the AWS AI Agent Global Hackathon, Alexa Prize TaskBot Challenges, Gemini Live Agent Challenge, Hack for Humanity | 2026, and a TreeHacks sponsor track. Award announcements establish placements; project submissions and team papers describe implementations. Reported features and results are not independent performance measurements. The comparisons below describe these winners, not a universal recipe for winning.

## 1. Winner Evidence Matrix

| # | Winner | Competition and award | Reported approach | Award evidence | Implementation evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | **EcoLafaek** | AWS AI Agent Global Hackathon (2025), 1st place | Multimodal waste reporting; AgentCore chains SQL, visualization, and map tools | [Winners announcement](https://aws-agent-hackathon.devpost.com/updates/38140-congratulations-to-the-winners-of-the-aws-ai-agent-global-hackathon) | [Submission](https://devpost.com/software/ecolafaek) |
| 2 | **AegisAgent** | AWS AI Agent Global Hackathon (2025), 2nd place | Insurance evidence curation, policy interpretation, review, and a decision packet | [Winners announcement](https://aws-agent-hackathon.devpost.com/updates/38140-congratulations-to-the-winners-of-the-aws-ai-agent-global-hackathon) | [Submission](https://devpost.com/software/aegisagent-an-insurance-claim-app-fully-developed-by-kiro) |
| 3 | **Province** | AWS AI Agent Global Hackathon (2025), 3rd place | Conversational tax intake and iterative mapping into Form 1040 | [Winners announcement](https://aws-agent-hackathon.devpost.com/updates/38140-congratulations-to-the-winners-of-the-aws-ai-agent-global-hackathon) | [Submission](https://devpost.com/software/province) |
| 4 | **AgentShell** | AWS AI Agent Global Hackathon (2025), Best Strands SDK Implementation | Strands and AgentCore coordinate local camera tools through MCP | [Winners announcement](https://aws-agent-hackathon.devpost.com/updates/38140-congratulations-to-the-winners-of-the-aws-ai-agent-global-hackathon) | [Submission](https://devpost.com/software/agent-shell) |
| 5 | **AI-Driven Multi-Agent Fraud Alert Triage System** | AWS AI Agent Global Hackathon (2025), Best Amazon Bedrock AgentCore Implementation | Triage, investigation, and reporting agents; analyst-facing escalation | [Winners announcement](https://aws-agent-hackathon.devpost.com/updates/38140-congratulations-to-the-winners-of-the-aws-ai-agent-global-hackathon) | [Submission](https://devpost.com/software/ai-driven-multi-agent-fraud-alert-triage-system) |
| 6 | **GRILLBot** | Alexa Prize TaskBot Challenge 1 (winner announced 2022), 1st place | TaskGraphs, grounded dialogue, and voice-screen task guidance | [Amazon Science announcement](https://www.amazon.science/alexa-prize/taskbot-challenge/2021) | [Team paper](https://www.amazon.science/alexa-prize/proceedings/grillbot-a-flexible-conversational-agent-for-solving-complex-real-world-tasks) |
| 7 | **TWIZ-v2** | Alexa Prize TaskBot Challenge 2 (winner announced 2023), 1st place | TWIZ-LLM, visual aids, voice video navigation, and zero-shot flows | [Amazon Science announcement](https://www.amazon.science/alexa-prize/taskbot-challenge/2022) | [Team paper](https://arxiv.org/abs/2310.02118) |
| 8 | **ORION** | Gemini Live Agent Challenge (2026), Grand Prize | Gemini Live audio, ADK specialist agents, and on-demand visual assistance | [Winners announcement](https://geminiliveagentchallenge.devpost.com/updates/41944-announcing-the-challenge-winners) | [Submission](https://devpost.com/software/orion-operating-room-intelligent-orchestration-node) |
| 9 | **Sibyl** | Hack for Humanity \| 2026 (environment-focused event), First Place and Best use of AI/ML | Paragraph-level retrieval, specialist investigations, and evidence review | [Event winner gallery](https://hack-for-humanity-26.devpost.com/project-gallery?page=2) and [submission award badges](https://devpost.com/software/sibyl-x8gpor) | [Submission](https://devpost.com/software/sibyl-x8gpor), [team repository](https://github.com/HackForHumanity2026/Sibyl) |
| 10 | **AgentPlace** | TreeHacks 2026, Fetch.ai sponsor track: Best Overall AI Agent Solution | Client–contractor agent negotiation with human deal approval | [Sponsor winner announcement](https://www.linkedin.com/posts/fetch-ai-innovation-lab_hackathon-winner-announcement-activity-7429198966405308416-PRhP) | [Submission](https://devpost.com/software/agentplace), [team repository](https://github.com/patidararnav/agentplace) |

The TaskBot Challenge 1 and 2 pages use their **launch years** (2021 and 2022) in their URLs; the winners were announced in **2022 and 2023**, respectively. The AWS award amounts, when relevant, are listed in the [2025 competition rules](https://aws-agent-hackathon.devpost.com/rules); the TaskBot first-place prizes were $500,000 each according to their award announcements.

## 2. Winning Case Studies

### 1. EcoLafaek — 1st place, AWS AI Agent Global Hackathon

- **Context & Problem:** The project addresses uncollected waste in Dili, Timor-Leste. The submission and organizer announcement cite more than 100 tons per day; this background figure is not independently measured here.
- **Architecture & Multi-Agent Pattern:**
  - Client: Flutter mobile app (cross-platform, offline SQLite cache).
  - Backend API: FastAPI integrated with Amazon Bedrock AgentCore runtime (`agentcore_app.run()`).
  - Intelligence: Amazon Nova-Pro v1.0 for multi-modal waste classification and tool orchestration; Amazon Titan Embed for 1024-d image similarity.
  - Tools: Multi-round autonomous tool chaining across 5 custom tools (`execute_sql_query`, `generate_visualization`, `create_map_visualization`, `scrape_webpage_with_browser`, `get_ecolafaek_info`).
- **Reported demonstration:** A citizen photo is classified, and the public dashboard answers queries using SQL, charts, and maps. The organizer's winner announcement specifically highlights multimodal reasoning and tool chaining. The submission describes a deployed site, but its availability and impact are not independently assessed here.



### 2. AegisAgent — 2nd place, AWS AI Agent Global Hackathon

- **Context & Problem:** Insurance claim coverage decisions require cross-referencing photos, invoices, and first-notice-of-loss forms against policy exclusions. The project addresses the risk of unsupported coverage decisions.
- **Architecture & Multi-Agent Pattern:**
  - Specialized Agents:
    1. *Evidence Curator:* Normalizes damage observations, EXIF timestamps, invoice line items.
    2. *Policy Interpreter:* Semantic retrieval across FAISS-indexed policy corpus.
    3. *Compliance Reviewer:* Adversarially challenges assumptions and raises objections.
  - Orchestration: Multi-round debate with a bounded termination strategy. If an objection is unresolvable without further evidence, the agent triggers a **pause-and-resume flow**, outputting a missing-evidence checklist.
  - Output: Structured, auditable **decision packet** (coverage stance, rationale, cited policy clauses, resolved/unresolved objections, memo draft).
- **Reported demonstration:** Its Kiro-built proof of concept exposes intermediate objections and citations rather than only a binary coverage stance. The organizer's announcement calls out the evidence, policy, and compliance roles. The submission says its code was AI-generated with both Kiro and Codex; that is a team-reported development detail, not a measured quality result.



### 3. Province — 3rd place, AWS AI Agent Global Hackathon

- **Context & Problem:** Tax filing involves detailed intake and yearly changes to IRS forms, making static questionnaires and hardcoded PDF field mappings hard to maintain.
- **Architecture & Multi-Agent Pattern:**
  - Multi-Agent Orchestration via **Strands SDK**:
    1. *Intake Agent:* One-question-at-a-time conversational intake, maintaining state across sessions.
    2. *Tax Planner Agent:* Deterministic tax calculation based on 2024 brackets.
    3. *FormMapping Agent:* Four-phase iterative mapping (initial mapping $\to$ gap identification $\to$ filling $\to$ validation). The submission mentions a 90% coverage target, 141 extracted fields, and 21/21 correctly filled fields in an example; these are different denominators, not a single independently tested accuracy rate.
    4. *Review Agent:* Audits the filled return against IRS publication rules indexed in ElasticSearch.
  - Infrastructure: AWS Bedrock Claude 3.5 Sonnet, DynamoDB, S3 versioning (`v001`...`v033`), Lambda event triggers.
- **Reported demonstration:** Conversational W-2 intake leads to explained tax calculations and a filled Form 1040 PDF. The submission reports coping with a two-requests-per-minute Bedrock limit using exponential backoff. Its example field results should not be conflated with independently tested accuracy across the entire form.



### 4. AgentShell — Best Strands SDK Implementation, AWS AI Agent Global Hackathon

- **Context & Problem:** The project proposes on-demand camera control while limiting continuous monitoring and avoiding exposed inbound camera ports.
- **Architecture & Multi-Agent Pattern:**
  - Core Concept: "One Mind, Many Bodies" — a central cloud consciousness (Bedrock AgentCore) selectively inhabits local camera hardware.
  - Tech Stack: Strands Agents SDK orchestrates FastMCP servers exposing 7 tools per camera (`analyze_camera_image`, `speak_on_camera`, `listen_on_camera`, `move_camera`, `nod_head`, `shake_head`, `reset_position`).
  - Security: Zero exposed incoming camera ports; outbound secure tunneling via ngrok/cloudflared; authenticated remote MCP.
- **Reported demonstration:** A voice trigger selects a camera, inspects its scene, performs camera movements, and speaks back. The submission describes outbound tunneling rather than opening camera inbound ports. This is an entrant-reported security design, not an independent security audit.



### 5. AI-Driven Multi-Agent Fraud Alert Triage System — Best Amazon Bedrock AgentCore Implementation

- **Context & Problem:** The project addresses fraud-alert volume and the work of correlating account data across systems.
- **Architecture & Multi-Agent Pattern:**
  - Three specialized agents deployed on AWS Bedrock AgentCore Runtime:
    1. *Alert-Triage Agent:* Enriches incoming alerts via Amazon Athena, evaluates allowlists, and computes a composite hybrid score (rule-based + LLM).
    2. *Investigation Agent:* Executes graph-like cross-account link analysis and transaction velocity tracking to discover typologies.
    3. *Report Agent:* Drafts formal Suspicious Activity Reports (SARs) and stores them in Amazon S3.
- **Reported demonstration:** Athena-backed alert enrichment leads to an explainable escalation and an analyst-facing React dashboard with approval before filing. The submission describes rule-based plus LLM scoring; its reported fraud-reduction figures are not independently validated in the cited material.



### 6. GRILLBot — 1st place, Alexa Prize TaskBot Challenge 1 ($500,000)

- **Context & Problem:** The TaskBot challenge asks assistants to guide multi-step cooking and DIY tasks despite detours, missing ingredients or tools, and mid-task questions.
- **Architecture & Multi-Agent Pattern:**
  - Dynamic **TaskGraphs:** Unified representation linking sequential procedural steps, conditional tool requirements, and domain knowledge.
  - Neural dialogue management combined with knowledge-grounded question answering and web information extraction.
  - Multimodal synchronization: Voice guidance coordinated with Echo Show screen graphics and video snippets.
- **Evidence and limits:** The [team paper](https://www.amazon.science/alexa-prize/proceedings/grillbot-a-flexible-conversational-agent-for-solving-complex-real-world-tasks) documents TaskGraphs, grounded QA, and multimodal elements. Handling missing ingredients or tools was also a challenge requirement, not proof that every proposed substitution worked. A [challenge overview](https://arxiv.org/abs/2209.06321) reports roughly 24 weeks of live-interaction evaluation for the inaugural competition, followed by finals. Later [team work](https://arxiv.org/abs/2402.07647) describes adaptation and latency tradeoffs across deployments, rather than guaranteed successful rewrites.



### 7. TWIZ-v2 — 1st place, Alexa Prize TaskBot Challenge 2 ($500,000)

- **Context & Problem:** The team explores how spoken guidance and visual aids can support complex manual tasks, including unfamiliar requests and mid-task detours.
- **Architecture & Multi-Agent Pattern:**
  - Three research themes: Humanly-Shaped Conversations, Multimodal Stimulus, and Zero-shot Conversational Flows.
  - Specialized domain model: **TWIZ-LLM**, fine-tuned for procedural dialogue, combined with multimodal curiosity prompts and voice-driven video navigation.
- **Evidence and limits:** The [team paper](https://arxiv.org/abs/2310.02118) describes APL screens, video navigation by voice, contextual prompts, and a stateful conversational flow. Its reported headless rating (3.47/5) exceeds its multimodal rating (3.27/5), so the evidence does not show that the voice–screen tradeoff was solved. The [award announcement](https://www.amazon.science/alexa-prize/taskbot-challenge/2022) establishes first place; the team paper establishes the described features and evaluations.



### 8. ORION — Grand Prize, Gemini Live Agent Challenge (2026)

- **Context & Problem:** Surgeons in robotic operating rooms cannot touch keyboards or screens without breaking sterility. They need immediate procedural data, safety check verification, and operative logging without losing focus.
- **Architecture & Multi-Agent Pattern:**
  - Nine-agent hierarchy described in the submission, built on Google ADK:
    - Root: `ORION_Orchestrator` handles real-time bidirectional audio stream, wake-word filtering, and 22 single-action direct tools.
    - 8 Specialist Sub-Agents: `Briefing_Agent`, `Timeout_Agent`, `Report_Agent`, `Complication_Advisor`, `EBL_Tracker`, `Drug_Checker`, `Anatomy_Spotter`, `Handoff_Agent`.
    - Visual Intelligence: `Screen_Advisor` is described separately from the nine-agent hierarchy; it receives live surgical video (320x240 @ 1 fps) and desktop screen capture (768x768 @ 1 fps).
  - Audio Routing: Solved complex sub-agent audio emission in live bidirectional streams so specialist agents speak directly to the surgeon.
- **Reported demonstration:** Spoken requests update a surgical checklist and console without requiring a touch interaction. The team also describes enabling visual streams only when needed to control cost, and fixing an audio-routing bug that initially silenced specialist responses. These are submission claims about a prototype, not evidence of clinical validation or verified patient data.



### 9. Sibyl — First Place & Best use of AI/ML, Hack for Humanity | 2026

- **Context & Problem:** The project compares sustainability disclosures with external evidence and identifies gaps in reported information.
- **Architecture & Multi-Agent Pattern:**
  - Multi-Agent Verification Loop:
    - *Bron (Orchestrator):* Generates investigation plans and dispatches claims to specialized RAG sub-agents.
    - *Judy (Judge):* Uses four weighted assessment dimensions: sufficiency (30%), consistency (25%), quality (25%, including source-authority weights), and completeness (20%). This is model-based assessment, not a deterministic verdict formula.
    - *Re-investigation Loop:* If Judy's confidence score is $<0.7$, the system requests targeted re-investigation from Bron, with up to three cycles before a verdict.
- **Reported demonstration:** Corporate claims are compared with paragraph-level evidence, citations, and disclosure gaps. Its separate arithmetic tool is described as deterministic; that property does not extend to Judy's evidence judgments. This winner belongs to the environment-focused [Hack for Humanity | 2026](https://hack-for-humanity-26.devpost.com/) event.



### 10. AgentPlace — Best Overall AI Agent Solution, Fetch.ai track at TreeHacks (2026)

- **Context & Problem:** Freelance contractor hiring involves tedious, manual back-and-forth haggling over scope, hourly rates, availability, and payment terms.
- **Architecture & Multi-Agent Pattern:**
  - Bilateral Agent Negotiation built on Fetch.ai uAgents & AgentVerse:
    - Client Agent: Formulates project requirements, budget ceilings, and desired timelines.
    - Contractor Agents: Maintain individual worker preferences (wages, travel distance, past ratings, calendar).
    - Negotiation Protocol: The [team repository](https://github.com/patidararnav/agentplace) describes Fetch.ai Chat Protocol, AgentVerse mailbox/discovery, an orchestrator, and contractor agents.
    - Human Gate & Payment: The client can approve a negotiated deal; the team describes an optional Agent Payment Protocol flow.
- **Reported demonstration:** Client and contractor agents exchange offers while the interface displays negotiation progress and the proposed deal for approval. The [sponsor announcement](https://www.linkedin.com/posts/fetch-ai-innovation-lab_hackathon-winner-announcement-activity-7429198966405308416-PRhP) confirms **Best Overall AI Agent Solution** in the Fetch.ai track.

## 3. Observations Across These Winners

These are comparisons among the named projects, not requirements shared by all winners or proof of why judges chose them:

- **Different ways to bound a task:** AegisAgent divides insurance review among evidence, policy, and compliance roles; Sibyl uses an investigator–judge loop; ORION describes specialist agents for voice-directed operating-room tasks. GRILLBot's TaskGraphs and TWIZ-v2's conversational state and flows show that the TaskBot winners use different structures from a hierarchy of debating agents.
- **Grounding and checks take different forms:** AegisAgent presents policy citations and unresolved objections; Province reports deterministic tax calculations with a reference corpus; Sibyl pairs model-based evidence judgments with a separate arithmetic tool; TWIZ-v2 draws on task and knowledge sources. None of these examples establishes that every winning project uses a deterministic verdict engine.
- **Uncertainty can remain visible:** AegisAgent reports a missing-evidence pause, Sibyl describes bounded re-investigation before a verdict, and GRILLBot's later work evaluates task adaptations that do not always succeed. These are distinct behaviors, not a common refusal or approval protocol.
- **Interfaces serve different tasks:** EcoLafaek reports maps and visualizations, the TaskBot winners combine spoken guidance and screens, ORION describes a voice-directed console, and AgentPlace exposes negotiation progress. TWIZ-v2's reported headless/multimodal ratings caution against treating more screen content as an automatic improvement. ORION's team reports activating visual streams only when needed to limit token use.
- **Outputs and human gates are not universal:** AegisAgent describes a decision packet, Province a tax PDF, Sibyl a cited report, and the fraud-triage project a report reviewed by an analyst. AgentPlace presents a deal for client approval. GRILLBot and TWIZ-v2 focus instead on task guidance and interaction quality; a durable record or approval card is not evidenced as a requirement of their wins.

Award listings establish *who won*. Submissions and team papers establish *what their authors say they built or measured*. Neither source type alone reveals private judge scores, causal reasons for a particular placement, or independently validated deployment outcomes.

## 4. Sources and Method

- **Placement and award category:** The matrix links to the AWS hackathon's organizer announcement, Amazon Science's TaskBot winner announcements, the Gemini Live Agent Challenge's organizer announcement, the specific Hack for Humanity | 2026 event's winner gallery plus Sibyl's award badges, and Fetch.ai's TreeHacks sponsor announcement. A project submission on its own is not evidence that a named category was won.
- **Implementation and results:** The matrix separately links to entrant submissions, team repositories, or TaskBot team papers. Their architecture, demo, performance, and impact claims are attributed to those authors. Organizer summaries sometimes repeat entrant claims; repetition is not independent validation.
- **Limits of comparison:** These projects competed in different events with different assessment methods. The [AWS AI Agent Global Hackathon rules](https://aws-agent-hackathon.devpost.com/rules) weight technical execution and demo, while the [TaskBot Challenge 2 announcement](https://www.amazon.science/alexa-prize/taskbot-challenge/2022) describes customer ratings and final live interactions. Neither establishes that a particular implementation detail caused a win across all ten cases. No private score breakdowns, clinical assessments, fraud pilot data, or independently audited deployment results are used here.
