# Build, Ship, Shape: Amazon Developer Hackathon

Working brief for the **Alexa+ track**, including both the real Agent Skill/MCP route and the simulated-web-experience route. Both mini-challenges remain possible. Sources checked **2026-09-26**; Rules, FAQs, Updates, and homepage rechecked **2026-10-14** (see [changes found](#changes-found-on-2026-10-14)). Rules and FAQs rechecked **2026-10-18** without changes, and organizer replies in the Discussions read the same day (see [organizer answers](#organizer-answers-read-on-2026-10-18)). Recheck live pages before making a submission because the Rules can change (§11.5).

## Source precedence

1. **[Official Rules](https://amazonappdev2026.devpost.com/rules)** ([local extract](competition/rules.md)) are binding and override other hackathon materials (§11.4). The live page overrides an outdated local extract.
2. [Devpost home](https://amazonappdev2026.devpost.com/), [Resources](https://amazonappdev2026.devpost.com/resources), [FAQs](https://amazonappdev2026.devpost.com/details/faqs), [Updates](https://amazonappdev2026.devpost.com/updates), and the [schedule widget](https://amazonappdev2026.devpost.com/details/dates) are informative, not the contract.
3. Product docs, technical specifications, and staff talks help interpret and implement the Rules. Follow a referenced technical standard (such as the versioned MCP specification for a real MCP server), but do not treat separate Amazon add-on onboarding steps or staff advice as extra hackathon requirements. Local **Recommendations** are planning advice, not rules.

If a Rules term is ambiguous, request clarification **in writing before the deadline** (§11.6). Do not silently resolve a contradiction using a less authoritative page.

## Dates and decisions

| When (Pacific time) | What | Authority |
| --- | --- | --- |
| 31 Aug 2026, 10:15 am | Submission Period began; existing projects must show significant work since then | Rules §§1, 4 |
| 19 Oct 2026, 9:00 am | Office Hours #2 with the Amazon team (registration link in the [update](https://amazonappdev2026.devpost.com/updates/46771-office-hours-schedule)) | Updates |
| ~~21 Oct 2026, 12:00 pm~~ | ~~Request optional $150 AWS Promotional Credits~~: **closed**; the Rules' 7 Oct update says credit codes ran out and no more requests are accepted | Rules §4; [details](competition/mini-challenges.md#aws-credits) |
| **23 Oct 2026, 12:00 pm** | Devpost submission closes | Rules §1 |
| **9–20 Nov 2026** (noon to noon) | Judging; keep project freely available through the end | Rules §§1, 4 |
| On or around **3 Dec 2026, 12:00 pm** | Winners announced | Rules §1 |

The [schedule widget](https://amazonappdev2026.devpost.com/details/dates) still says judging begins **26 Oct**. The **Rules say 9 Nov**; follow the Rules. The homepage's 23 Oct **3:00 pm EDT** deadline is the same instant as noon Pacific.

## Build and submit

- **Alexa+ has two eligible routes:** a working Agent Skill or self-hosted **MCP server** using MCP **2025-11-25** (or a later version once confirmed) over **Streamable HTTP**; **or** a simulated Alexa+ web experience built using any AI/agentic tools. The simulation needs no MCP-shaped surface and is exempt from the track runtime-technology hook, but its source must be in the repo and its experience clearly shown in the video. See [both routes, distinctions, and links](competition/alexa.md).
- **Submission essentials:** working demo, text description, **GitHub** repository with source/assets/run instructions, public YouTube/Vimeo video, product feedback for every tool/API/SDK used, and identification of tracks and any mini-challenges. See the [submission checklist](competition/submission.md). Judges may score only the description, images, and video (§4).
- **Optional mini-challenges:** [AWS Builder and Open Source](competition/mini-challenges.md) attach to the primary-track project. A project can win **one track prize and one mini-challenge prize** (Rules §8); organizers can reassign a project to another category/mini-challenge if applicable (Rules §4).
- [Judging](competition/judging.md) covers the pass/fail screen, four equal criteria, and optional friction-log bonus; [prizes](competition/prizes.md) lists the awards.

The other primary tracks are **Fire TV** (demo-ready Fire OS/Vega OS app on device or simulator), **Bee** (actual Bee/Apple Watch Bee data used in code and video), and **Ring** (working Ring API/SDK/simulator/device app shown via simulator or device). This is only a synopsis; follow [Rules §4](competition/rules.md#4-how-to-enter) if entering one. Theme tags such as AI/Productivity do **not** replace track requirements.

## Changes found on 2026-10-14

The live Rules, FAQs, Updates, and homepage were compared with the 2026-09-26 extract; the files in `competition/` now include these changes.

- **AWS credits closed:** the Rules' 7 Oct update says credit codes ran out. Live Bedrock or other AWS usage is at the entrant's own cost ([details](competition/mini-challenges.md#aws-credits)).
- **Private-repository reviewers:** the Rules' profile list and the FAQs dropped `chris-trag`; the Rules' collaborator sentence and the homepage still include him. Invite all six if the repository stays private ([checklist](competition/submission.md#required)). The rest of the Rules text is unchanged.
- **FAQ wording on the simulated route:** one answer calls a web MCP client "the simulated-experience path". The Rules' separate simulation alternative is unchanged and prevails ([Alexa+ routes](competition/alexa.md#simulated-web-experience-route)).
- **Judges may run the project themselves** (FAQs), so the README setup and the credentials a judge needs must work from a clean checkout ([checklist](competition/submission.md#testing-rights-and-final-checks)).
- **Submission tips** (Updates, informative): name the track's tool in the description, Built With, and video; pitch the problem first; keep keys out of the repository ([judging](competition/judging.md)).

## Organizer answers read on 2026-10-18

The live Rules and FAQs match the files in `competition/`. Replies by the Amazon and Devpost team in the [Discussions](https://amazonappdev2026.devpost.com/forum_topics) are informative, not the contract (see [source precedence](#source-precedence)), but they show how the organizers read the Rules.

- **Alexa+ fit:** a strong entry is something people would actually use on Alexa+ and that is new rather than a latent LLM capability; Alexa+ is mostly consumer-focused, so enterprise use cases are valid but less typical; Alexa is voice-first, not voice-only, and a polished UI that could plausibly run on an Echo device is likely to score higher. Voice, an Alexa-like look, and a live model are not required for the simulated route ([details](competition/alexa.md#organizer-guidance-from-the-discussions)).
- **Judge access:** a judge who wants to try a project should not have to paste in their own token; a labelled replay mode is fine as the default. The FAQs say hosting is not required, while forum replies say a hosted endpoint must stay live until judging ends ([details](competition/submission.md#testing-rights-and-final-checks)).
- **Bedrock on new AWS accounts:** several entrants report blocked or suspended Bedrock access, and the organizers have no escalation path; Claude Code running on Bedrock counts for AWS Builder ([details](competition/mini-challenges.md#aws-builder)).
- **Open Source:** the primary-track project's own repository does not count ([details](competition/mini-challenges.md#open-source)).
- **Friction log:** a link in the description is enough; keeping it in the repository is easier for judges ([checklist](competition/submission.md#optional-but-useful)).

Questions: [Devpost discussions](https://amazonappdev2026.devpost.com/forum_topics), `janet@devpost.com` (homepage), or `support@devpost.com` (Rules). [Discord](https://discord.gg/devpost), `#amazon-developer-checkin`, is for informal help; use a written request for a Rules ambiguity.
