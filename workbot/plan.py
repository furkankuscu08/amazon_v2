"""Turn an audited card into a short "talk to these people first" plan.

Pure functions over the stored card: no model, schema, or database access. The
plan only reorders and groups people the audit already accepted.
"""

from __future__ import annotations

MAX_FIRST_CONVERSATIONS = 4
ROLE_ORDER = {"direct_contact": 0, "advisor": 1, "routing_contact": 2}
_CONFIDENCE = {"high": 0, "medium": 1, "low": 2}
_GAPS = {
    "not_found": "no_contact",
    "mapping_unresolved": "team_unresolved",
    "review_incomplete": "review_incomplete",
}


def _label(person: dict) -> str:
    if person["role"] == "routing_contact":
        return "Can route you"
    if person["role"] == "advisor":
        return "Can advise"
    if person.get("primary_kind") == "responsibility":
        return "Current responsibility"
    return "Related work"


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
            "label": _label(person),
            "area": area["label"],
            "need": area.get("consultation_need"),
        }
        for index, area in enumerate(areas)
        for person in area["people"]
        if home[person["person_id"]] == index
    }
    chosen = [pid for pid in card.get("first_conversations") or [] if pid in entries]
    if not chosen:
        # No usable model choice: the strongest person of each area, strongest first.
        best = []
        for index in range(len(areas)):
            here = [e for pid, e in entries.items() if home[pid] == index]
            if here:
                best.append(min(here, key=_strength))
        chosen = [e["person_id"] for e in sorted(best, key=_strength)]
    chosen = list(dict.fromkeys(chosen))[:MAX_FIRST_CONVERSATIONS]
    gaps: dict[str, list[str]] = {name: [] for name in _GAPS.values()}
    for area in areas:
        if area["status"] in _GAPS:
            gaps[_GAPS[area["status"]]].append(area["label"])
    return {
        "first": [entries[pid] for pid in chosen],
        "gaps": gaps,
        "notes": notes,
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
