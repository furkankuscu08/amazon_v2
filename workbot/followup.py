"""Answer follow-up questions about a plan from the plan itself.

Pure functions over a built plan and its card: no model, schema, or database
access. A question is matched by rules to one of a few kinds and to people on the
card, and the reply is put together only from text the page already shows (names,
areas, role labels, evidence lines, ended-duty notes, what to find out, the shared
question, and the open areas), so neither the panel nor the voice can say more.
The question itself is never repeated in a reply.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlencode

from workbot.plan import ended_spoken, join_and

# Questions shown in one conversation, the newest included; older ones drop off.
MAX_TURNS = 6
MAX_QUESTION = 200
# A capitalized name heard slightly wrong, such as "Tarah", still finds Tara:
# same first letter, at most one letter longer or shorter, and close enough.
# Shorter or lowercase words must match exactly.
_FUZZY_RATIO = 0.8
_FUZZY_LENGTH = 4
# The earlier questions a follow-up form carries, as at most this many bytes once
# encoded, so the form stays under the 4096-byte limit with a long new question.
_PRIOR_BYTES = 1500
# Common words of fuzzy length that must never be read as a misheard name.
_NOT_NAMES = {
    "about", "anyone", "before", "does", "else", "first", "from", "have", "know",
    "listed", "meet", "meeting", "more", "need", "open", "other", "people",
    "person", "plan", "prep", "prepare", "should", "someone", "start", "still",
    "talk", "tell", "that", "their", "them", "there", "they", "this", "what",
    "when", "where", "which", "with", "would",
}  # fmt: skip
_WHY = {"why", "reason", "evidence", "source"}
_PREP = {"ask", "prep", "prepare", "talk", "meet", "meeting", "discuss", "find"}
_OTHERS = {"else", "other", "others", "anyone", "anybody", "besides", "rest"}
_OPEN = {"open", "missing", "gap", "gaps", "unresolved", "found", "unknown"}
_PHRASE = {
    "Related work": "for related work",
    "Current responsibility": "for a current responsibility",
    "Can advise": "as an advisor",
    "Can route you": "as someone who can route you",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "?", "!", "’")) else text + "."


def _close(word: str, name: str) -> bool:
    return (
        len(word) >= _FUZZY_LENGTH
        and len(name) >= _FUZZY_LENGTH
        and word[0] == name[0]
        and abs(len(word) - len(name)) <= 1
        and SequenceMatcher(None, word, name).ratio() >= _FUZZY_RATIO
    )


def _places(plan: dict) -> set[str]:
    """Words of the area and team names on the page, which are never names."""
    labels = {e["area"] for e in plan["people"].values()}
    labels.update(e.get("team") or "" for e in plan["people"].values())
    labels.update(label for labels in plan["gaps"].values() for label in labels)
    return {word for label in labels for word in _words(label)}


def _named(question: str, plan: dict) -> list[str]:
    """The card people a question names, best match first: exact name words beat
    near ones, and more matching words (a full name) beat fewer. Only a
    capitalized word, never an area or team word or a common one, may be a near
    match, so "rules" is not taken for Jules."""
    skip = _places(plan)
    words = [w for w in _words(question) if w not in skip]
    capitalized = [
        w.lower()
        for w in re.findall(r"[A-Za-z]+", question)
        if w[0].isupper() and w.lower() not in skip | _NOT_NAMES
    ]
    scores = {}
    for exact in (True, False):
        for pid, entry in plan["people"].items():
            names = [w for w in _words(entry["name"]) if len(w) > 1]
            hits = sum(
                any(w == n for w in words)
                if exact
                else any(_close(w, n) for w in capitalized)
                for n in names
            )
            if hits:
                scores[pid] = hits
        if scores:
            break
    best = max(scores.values(), default=0)
    return [pid for pid, score in scores.items() if score == best]


def resolve(question: str, plan: dict) -> tuple[str, list[str]]:
    """The kind of question and the card people it names.

    Kinds: why, prep, others, open, ambiguous (more than one person fits),
    unlisted (a name that is not on the card), and help.
    """
    said = set(_words(question))
    named = _named(question, plan)
    if len(named) > 1:
        return "ambiguous", named
    if named:
        if said & _WHY:
            return "why", named
        if said & _PREP:
            return "prep", named
        if said & _OTHERS:
            return "others", []
        return "why", named
    if said & _OTHERS:
        return "others", []
    if said & _OPEN:
        return "open", []
    if _unlisted(question, plan):
        return "unlisted", []
    return "help", []


def _unlisted(question: str, plan: dict) -> bool:
    """Whether the question seems to name someone who is not on the card: a
    capitalized word, not starting a sentence and not an acronym, that is no area
    or team name or common word. Who that might be is never checked, so a
    restricted person is answered exactly like someone who does not exist."""
    known = _places(plan) | _NOT_NAMES | _WHY | _PREP | _OTHERS | _OPEN
    known |= {"alexa", "maya"}
    for sentence in re.split(r"[.!?]+", question):
        for word in re.findall(r"[A-Za-z]+", sentence)[1:]:
            title = len(word) > 1 and word[0].isupper() and word[1:].islower()
            if title and word.lower() not in known:
                return True
    return False


def _areas_of(pid: str, card: dict) -> list[dict]:
    return [
        area
        for area in card["areas"]
        if any(p["person_id"] == pid for p in area["people"])
    ]


def _why(entry: dict, card: dict) -> tuple[list[str], str | None]:
    name = entry["name"]
    parts = [f"{name} is listed under {entry['area']} {_PHRASE[entry['label']]}."]
    line = entry["short"] or (entry["evidence"][0]["text"] if entry["evidence"] else "")
    if line:
        parts.append(_sentence(line))
    ended = ended_spoken(name, entry["ended_duty"])
    if ended:
        parts.append(ended)
    others = [a["label"] for a in _areas_of(entry["person_id"], card)]
    others = [label for label in others if label != entry["area"]]
    if others:
        parts.append(f"Also listed under {join_and(others)}.")
    # The plan does not link a routing contact's line to a single source either.
    linked = entry["role"] != "routing_contact" and entry.get("primary_evidence_id")
    return parts, linked or None


def _prep(entry: dict, card: dict) -> list[str]:
    name = entry["name"]
    need = entry["need"]
    if need:
        parts = [f"With {name}, find out: {_sentence(need)}"]
    else:
        parts = [f"Ask {name} about {entry['area']}."]
    # Only the card's own question is spelled out, so the answer stays short.
    others = [a["label"] for a in _areas_of(entry["person_id"], card)]
    others = [label for label in others if label != entry["area"]]
    if others:
        parts.append(
            f"{name} is also listed under {join_and(others)}; the full list says"
            " what to find out there."
        )
    ended = ended_spoken(name, entry["ended_duty"])
    if ended:
        parts.append(f"Check first: {ended}")
    if entry["role"] == "routing_contact":
        parts.append(f"{name} can point you to the right person.")
    shared = (card.get("shared_question") or "").strip()
    if shared and shared != (need or "").strip():
        parts.append(f"Across all areas: {_sentence(shared)}")
    return parts


def _others(plan: dict, card: dict) -> list[str]:
    first = {entry["person_id"] for entry in plan["first"]}
    parts = []
    for index, area in enumerate(card["areas"]):
        home = plan["elsewhere"][index]
        names = [
            p["name"]
            for p in plan["order"][index]
            if p["person_id"] not in first and home[p["person_id"]] is None
        ]
        if names:
            parts.append(f"In {area['label']}: {join_and(names)}.")
    if not parts:
        return ["Everyone on this plan is in the cards above."]
    return [
        "The full list names more people.",
        *parts,
        "Ask me why any of them is listed.",
    ]


def _open(plan: dict) -> list[str]:
    gaps = plan["gaps"]
    parts = []
    if gaps["no_contact"]:
        parts.append(f"No contact was found for {join_and(gaps['no_contact'])}.")
    if gaps["team_unresolved"]:
        parts.append(
            f"The team was not identified for {join_and(gaps['team_unresolved'])}."
        )
    if gaps["review_incomplete"]:
        parts.append(
            f"The review did not finish for {join_and(gaps['review_incomplete'])}."
        )
    if not parts:
        return ["Nothing is open: every area has someone to talk to."]
    if gaps["no_contact"]:
        parts.append("That does not mean nobody suitable exists.")
    return parts


def _call(entry: dict, people: dict[str, dict]) -> str:
    """How a chip names a person: the first name, unless someone else shares it."""
    first = entry["name"].split()[0]
    shared = sum(p["name"].split()[0] == first for p in people.values())
    return first if shared == 1 else entry["name"]


def _help(plan: dict) -> str:
    text = (
        "I can tell you why someone is listed, what to ask them, who else is in"
        " the full list, or what is still open."
    )
    if plan["first"]:
        text += f" For example: Why {_call(plan['first'][0], plan['people'])}?"
    return text


def _unlisted_reply(plan: dict) -> str:
    if not plan["first"]:
        return "That name is not on this plan, and the plan names no one to talk to."
    names = join_and([entry["name"] for entry in plan["first"]])
    return (
        f"That name is not on this plan. Start with {names}, or ask me who else"
        " is in the full list."
    )


def reply(question: str, plan: dict, card: dict) -> dict:
    """Alexa's answer, as text shown and read aloud, and the source to link."""
    kind, named = resolve(question, plan)
    people = plan["people"]
    source_id = None
    if kind == "why":
        parts, source_id = _why(people[named[0]], card)
    elif kind == "prep":
        parts = _prep(people[named[0]], card)
    elif kind == "others":
        parts = _others(plan, card)
    elif kind == "open":
        parts = _open(plan)
    elif kind == "ambiguous":
        names = [people[pid]["name"] for pid in named]
        parts = [f"Which one do you mean: {', '.join(names[:-1])} or {names[-1]}?"]
    elif kind == "unlisted":
        parts = [_unlisted_reply(plan)]
    else:
        parts = [_help(plan)]
    return {"kind": kind, "text": " ".join(parts), "source_id": source_id}


def chips(plan: dict, asked: list[str]) -> list[str]:
    """Up to four suggested questions that fit this plan and were not yet asked."""
    first = plan["first"]
    people = plan["people"]
    options = []
    if first:
        ended = [entry for entry in first if entry["ended_duty"]]
        options.append(f"Why {_call((ended or first)[0], people)}?")
        options.append(f"Prep me for {_call(first[0], people)}")
    chosen = {entry["person_id"] for entry in first}
    if any(pid not in chosen for pid in people):
        options.append("Who else?")
    if any(plan["gaps"].values()):
        options.append("What's still open?")
    seen = {tuple(_words(question)) for question in asked}
    return [option for option in options if tuple(_words(option)) not in seen][:4]


def carried(questions: list[str]) -> list[str]:
    """The newest earlier questions the next follow-up form carries: at most
    MAX_TURNS - 1, and fewer when long ones would make the form too large."""
    kept = list(questions)[-(MAX_TURNS - 1) :]
    while (
        kept and len(urlencode({str(i): q for i, q in enumerate(kept)})) > _PRIOR_BYTES
    ):
        kept.pop(0)
    return kept
