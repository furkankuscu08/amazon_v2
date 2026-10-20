"""Turn an audited card into a short "talk to these people first" plan.

Pure functions over the stored card: no model, schema, or database access. The
plan only reorders and groups people the audit already accepted.
"""

from __future__ import annotations

import re
from datetime import date

MAX_FIRST_CONVERSATIONS = 4
ROLE_ORDER = {"direct_contact": 0, "advisor": 1, "routing_contact": 2}
_CONFIDENCE = {"high": 0, "medium": 1, "low": 2}
_GAPS = {
    "not_found": "no_contact",
    "mapping_unresolved": "team_unresolved",
    "review_incomplete": "review_incomplete",
}
# Cards stored before the list linked each line ended a line with its source ID,
# such as " [jira:MKT-482]."; other bracketed text is left alone.
_OLD_SOURCE_ID = re.compile(r" \[[a-z]+:[^\]\s]+\]\.$")
# The audit's plan line for a work record and its ended-duty note. Anything else,
# such as a responsibility or routing line, is shown as written.
_RECORD_HEADLINE = re.compile(
    r"^(Author|Assignee|Contributor|Reporter) of an? (\w+) record: ‘(.+)’$"
)
# The audit's full-list line for a work record, rewritten the same way at render
# time so stored cards read the same; a line that does not match is left alone.
_RECORD_LINE = re.compile(
    r"^(Author|Assignee|Contributor|Reporter|Mention) of (\w+) record on (\S+): ‘(.+)’$"
)
_DID = {
    "Author": "Wrote",
    "Assignee": "Assigned to",
    "Contributor": "Contributed to",
    "Reporter": "Reported",
    "Mention": "Mentioned in",
}
_KIND = {
    "jira": "a Jira issue",
    "slack": "a Slack message",
    "document": "a document",
    "github": "a GitHub pull request",
}
# A sentence ends at . ! or ? before a capital letter or the end of the excerpt,
# unless the word before it is an abbreviation such as "e.g.", "Dr." or "U.S.".
_SENTENCE_END = re.compile(r"[.!?](?=\s+[A-Z‘“]|$)")
_ABBREVIATION = re.compile(r"(?:\b(?:[A-Za-z]\.){2,}|\b(?:etc|vs|Dr|Mr|Mrs|Ms)\.)$")
_ENDED = re.compile(r"^An earlier responsibility ended on (\S+): (.+?)(?: — .*)?\.$")
# Spelled out here, not by the locale, so the spoken date never depends on the server.
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _short(headline: str | None) -> str | None:
    """The plan's one-line reason: a record's first sentence when the excerpt holds it."""
    match = _RECORD_HEADLINE.match(headline or "")
    if not match or match[2] not in _KIND:
        return headline
    relation, kind, quote = match.groups()
    return f"{_DID[relation]} {_KIND[kind]}: ‘{_first_sentence(quote)}’"


def _first_sentence(quote: str) -> str:
    for end in _SENTENCE_END.finditer(quote):
        if not _ABBREVIATION.search(quote[: end.end()]):
            return quote[: end.end()]
    return quote


def _date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _month(day: date) -> str:
    return f"{_MONTHS[day.month - 1]} {day.year}"


def _long_date(text: str) -> str:
    """An ISO date as people write it, such as "30 June 2025"; anything else as is."""
    day = _date(text)
    return f"{day.day} {_month(day)}" if day else text


def _ended_short(note: str | None) -> str | None:
    """The plan's ended-duty line: role and month, as Alexa says it."""
    match = _ENDED.match(note or "")
    ended = _date(match[1]) if match else None
    if not ended:
        return note
    return f"{match[2].capitalize()} role ended in {_month(ended)}."


def _ended_full(note: str | None) -> str | None:
    """The full list's directory note, with its date written out."""
    match = re.match(r"^(An earlier responsibility ended on )(\S+)(: .+)$", note or "")
    return f"{match[1]}{_long_date(match[2])}{match[3]}" if match else note


def ended_spoken(name: str, note: str | None) -> str | None:
    """The ended-duty note as a sentence to hear: role and month, not an ISO date."""
    match = _ENDED.match(note or "")
    ended = _date(match[1]) if match else None
    if not ended:
        return None
    return f"{name}'s {match[2]} role ended in {_month(ended)}."


def _initials(name: str) -> str:
    words = name.split()
    return "".join(word[0] for word in words[:1] + words[1:][-1:]).upper()


def _label(person: dict) -> str:
    if person["role"] == "routing_contact":
        return "Can route you"
    if person["role"] == "advisor":
        return "Can advise"
    if person.get("primary_kind") == "responsibility":
        return "Current responsibility"
    return "Related work"


def _line(text: str) -> str:
    cut = _OLD_SOURCE_ID.sub("", text)
    match = _RECORD_LINE.match(cut)
    if match and match[2] in _KIND:
        relation, kind, when, quote = match.groups()
        return f"{_DID[relation]} {_KIND[kind]} on {_long_date(when)}: ‘{quote}’"
    # A quoted record needs no full stop of its own after the closing quote.
    return cut if cut == text or cut.endswith("’") else cut + "."


def _evidence(person: dict) -> list[dict]:
    """Each audited evidence line with the source it cites, the primary one first."""
    primary = person.get("primary_evidence_id")
    lines = person.get("why", [])
    # The audit writes one line per citation in this order. Without a primary the
    # order is unknown, and a line must never link to a source it does not describe.
    ids = (
        [primary, *(sid for sid in person["evidence_ids"] if sid != primary)]
        if primary
        else []
    )
    if len(ids) != len(lines):
        ids = [None] * len(lines)
    return [
        {"text": _line(text), "source_id": sid}
        for text, sid in zip(lines, ids, strict=True)
    ]


def _strength(person: dict) -> tuple[int, int]:
    return ROLE_ORDER[person["role"]], _CONFIDENCE.get(person.get("confidence"), 3)


def placements(areas: list[dict]) -> dict[str, int]:
    """Give each person one home on the card: the area where their role is
    strongest, preferring the area mapped to their own team between equal roles."""
    best: dict[str, tuple] = {}
    for index, area in enumerate(areas):
        for person in area["people"]:
            own_team = person.get("org_id") is not None and (
                person.get("org_id") == area.get("org_unit_id")
            )
            role, confidence = _strength(person)
            key = (role, not own_team, confidence, index)
            if person["person_id"] not in best or key < best[person["person_id"]]:
                best[person["person_id"]] = key
    return {person_id: key[-1] for person_id, key in best.items()}


# Said after the summary when the plan names someone: the page takes follow-ups.
INVITE = "Ask me why anyone is listed, or what to ask them."
_COUNTS = ["one person", "two people", "three people", "four people"]
_NUMBERS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}


def join_and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _notes(groups: list[dict]) -> list[str]:
    """What the plan shows about these groups' people beyond their names, said
    after the sentence that names them: ended duties, then who can route you."""
    people = [person for group in groups for person in group["people"]]
    notes = [ended_spoken(p["name"], p["ended_duty"]) for p in people]
    routing = [p["name"] for p in people if p["role"] == "routing_contact"]
    if routing:
        notes.append(f"{join_and(routing)} can point you to the right person.")
    return [note for note in notes if note]


def _spoken(groups: list[dict], more: int, open_areas: int) -> tuple[str, str]:
    """The plan's heading and the sentences after it, which together are read aloud.

    Both are built only from what the plan shows, so the voice cannot say more.
    """
    count = sum(len(group["people"]) for group in groups)
    if not count:
        headline = "I found no one to point you to from the work I can see."
        lead = []
    else:
        headline = f"Before you start, talk to {_COUNTS[count - 1]}."
        places = [
            f"{join_and([p['name'] for p in group['people']])} in {group['area']}"
            for group in groups
        ]
        lead = [f"Start with {places[0]}.", *_notes(groups[:1])]
        if len(places) == 2:
            lead.append(f"Then {places[1]}.")
        elif len(places) > 2:
            lead.append(f"Then {', '.join(places[1:-1])}, and {places[-1]}.")
        lead.extend(_notes(groups[1:]))
        if all(group["need"] for group in groups):
            lead.append("Each card says what to find out.")
    if more:
        lead.append(
            "One more area is in the full list."
            if more == 1
            else f"{_NUMBERS.get(more, str(more))} more areas are in the full list."
        )
    if open_areas:
        lead.append(
            "One area is still open."
            if open_areas == 1
            else f"{_NUMBERS.get(open_areas, str(open_areas))} areas are still open."
        )
    return headline, " ".join(lead)


def build_plan(card: dict) -> dict:
    areas = card["areas"]
    home = placements(areas)
    # An ended-duty note is found per area; keep it wherever the person is shown.
    notes: dict[str, str] = {}
    for area in areas:
        for person in area["people"]:
            if person.get("ended_duty"):
                notes.setdefault(person["person_id"], person["ended_duty"])
    entries = {
        person["person_id"]: {
            **person,
            "ended_duty": notes.get(person["person_id"]),
            "ended_short": _ended_short(notes.get(person["person_id"])),
            "ended_full": _ended_full(notes.get(person["person_id"])),
            "short": _short(person.get("headline")),
            "initials": _initials(person["name"]),
            "label": _label(person),
            "evidence": _evidence(person),
            "area": area["label"],
            "need": area.get("consultation_need"),
        }
        for index, area in enumerate(areas)
        for person in area["people"]
        if home[person["person_id"]] == index
    }
    chosen = [pid for pid in card.get("first_conversations") or [] if pid in entries]
    if not chosen:
        # No usable model choice: the strongest person of each area, strongest first,
        # preferring someone whose related responsibility has not ended.
        best = []
        for index in range(len(areas)):
            here = [e for pid, e in entries.items() if home[pid] == index]
            if here:
                best.append(
                    min(here, key=lambda e: (bool(e["ended_duty"]), _strength(e)))
                )
        chosen = [e["person_id"] for e in sorted(best, key=_strength)]
    chosen = list(dict.fromkeys(chosen))[:MAX_FIRST_CONVERSATIONS]
    # One group per home area, with what to find out there. Groups follow their
    # first chosen person, and people keep the chosen order within a group, except
    # that someone whose related responsibility has ended is not who to start
    # with: they follow the others in their area, and an area with only such
    # people follows the areas that have someone else.
    groups: dict[str, dict] = {}
    for pid in chosen:
        entry = entries[pid]
        groups.setdefault(
            entry["area"],
            {"area": entry["area"], "need": entry["need"], "people": []},
        )["people"].append(entry)
    ordered = sorted(
        groups.values(), key=lambda g: all(e["ended_duty"] for e in g["people"])
    )
    for group in ordered:
        group["people"].sort(key=lambda e: bool(e["ended_duty"]))
    first = [entry for group in ordered for entry in group["people"]]
    # The full list names first the people it shows in full in an area, then those
    # it refers elsewhere; the plan's people lead each part, in the plan's order.
    rank = {entry["person_id"]: index for index, entry in enumerate(first)}
    order = [
        sorted(
            area["people"],
            key=lambda p: (
                home[p["person_id"]] != index,
                rank.get(p["person_id"], len(rank)),
            ),
        )
        for index, area in enumerate(areas)
    ]
    # Areas with people where nobody chosen has their home and somebody was left
    # out, named with those people under the cards so the plan does not seem to
    # have lost them.
    shown = {home[pid] for pid in chosen}
    more = [
        {
            "area": area["label"],
            # In the full list's order, so the two name them alike.
            "names": [p["name"] for p in order[index] if p["person_id"] not in chosen],
        }
        for index, area in enumerate(areas)
        if area["status"] == "people"
        and index not in shown
        and any(p["person_id"] not in chosen for p in area["people"])
    ]
    gaps: dict[str, list[str]] = {name: [] for name in _GAPS.values()}
    for area in areas:
        if area["status"] in _GAPS:
            gaps[_GAPS[area["status"]]].append(area["label"])
    headline, lead = _spoken(ordered, len(more), sum(map(len, gaps.values())))
    invite = INVITE if first else None
    return {
        "headline": headline,
        # Said after the headline, then the invite; the three are the text read aloud.
        "lead": lead,
        "invite": invite,
        "spoken": " ".join(part for part in (headline, lead, invite) if part),
        "first": first,
        "groups": ordered,
        "more": more,
        "gaps": gaps,
        # Everyone on the card once, as shown in their home area.
        "people": entries,
        # Per area: its people in the order the full list shows them.
        "order": order,
        # Per area: where each listed person is shown in full (None = here).
        "elsewhere": [
            {
                person["person_id"]: None
                if home[person["person_id"]] == index
                else areas[home[person["person_id"]]]["label"]
                for person in area["people"]
            }
            for index, area in enumerate(areas)
        ],
    }
