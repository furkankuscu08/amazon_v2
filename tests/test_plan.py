"""The first-conversations plan is a pure regrouping of an audited card."""

from workbot.plan import _short, build_plan, placements


def person(pid, role, org, confidence="medium", kind="assignee"):
    return {
        "person_id": pid,
        "name": pid.title(),
        "role": role,
        "confidence": confidence,
        "org_id": org,
        "primary_kind": kind,
    }


def area(label, org, *people, status="people"):
    return {
        "label": label,
        "org_unit_id": org,
        "status": status,
        "people": list(people),
    }


CARD = {
    "areas": [
        area("Platform", "platform", person("nina", "direct_contact", "growth")),
        area("Legal", "legal", status="not_found"),
        area(
            "Growth",
            "growth",
            person("nina", "direct_contact", "growth"),
            person("leo", "advisor", "growth"),
        ),
        area(
            "Finance",
            "finance",
            person("omar", "advisor", "finance"),
            person("tara", "direct_contact", "finance", kind="responsibility"),
        ),
        area("Brand", None, status="mapping_unresolved"),
        area("Commerce", "commerce", person("dan", "routing_contact", "commerce")),
        area("Data", "data", person("omar", "direct_contact", "finance", "high")),
    ]
}


def test_each_person_is_placed_once_where_their_role_is_strongest():
    assert placements(CARD["areas"]) == {
        "nina": 2,
        "leo": 2,
        "omar": 6,  # direct there, only an advisor in their own team's area
        "tara": 3,
        "dan": 5,
    }
    plan = build_plan(CARD)
    assert plan["elsewhere"][0] == {"nina": "Growth"}
    # Equal roles: the area mapped to the person's own team wins.
    assert plan["elsewhere"][2] == {"nina": None, "leo": None}
    assert plan["elsewhere"][3] == {"omar": "Data", "tara": None}
    assert plan["elsewhere"][6] == {"omar": None}


def test_fallback_takes_the_strongest_person_of_each_area_strongest_first():
    plan = build_plan(CARD)
    assert [p["person_id"] for p in plan["first"]] == ["omar", "nina", "tara", "dan"]
    assert [p["label"] for p in plan["first"]] == [
        "Related work",
        "Related work",
        "Current responsibility",
        "Can route you",
    ]
    assert [p["area"] for p in plan["first"]] == [
        "Data",
        "Growth",
        "Finance",
        "Commerce",
    ]
    assert plan["gaps"] == {
        "no_contact": ["Legal"],
        "team_unresolved": ["Brand"],
        "review_incomplete": [],
    }


def test_model_choice_is_kept_in_order_capped_and_limited_to_shown_people():
    card = {
        **CARD,
        "first_conversations": ["tara", "ghost", "nina", "leo", "omar", "dan"],
    }
    plan = build_plan(card)
    assert [p["person_id"] for p in plan["first"]] == ["tara", "nina", "leo", "omar"]
    assert plan["first"][3]["area"] == "Data"  # shown in the home area's role
    assert plan["first"][3]["role"] == "direct_contact"


def test_older_card_without_team_fields_still_builds_a_plan():
    old = {
        "areas": [
            {
                "label": "Growth",
                "org_unit_id": "growth",
                "status": "people",
                "people": [{"person_id": "nina", "name": "Nina", "role": "advisor"}],
            }
        ]
    }
    plan = build_plan(old)
    assert plan["first"][0]["label"] == "Can advise"
    assert build_plan({"areas": []})["first"] == []


def test_ended_duty_note_follows_the_person_to_their_home_area():
    note = "An earlier responsibility ended on 2025-06-30: approver."
    card = {
        "areas": [
            area(
                "Finance",
                "finance",
                {**person("omar", "advisor", "finance"), "ended_duty": note},
            ),
            area("Data", "data", person("omar", "direct_contact", "finance")),
        ]
    }
    plan = build_plan(card)
    assert plan["first"][0]["area"] == "Data"
    assert plan["first"][0]["ended_duty"] == note
    assert plan["people"]["omar"]["ended_duty"] == note


def test_everyone_gets_the_plan_label_and_evidence_linked_to_its_source():
    nina = {
        **person("nina", "direct_contact", "growth"),
        "primary_evidence_id": "slack:b",
        "evidence_ids": ["jira:a", "slack:b", "docs:c"],
        # The audit writes the primary line first; an older card ends with the ID.
        "why": [
            "Author: ‘Text.’ [slack:b].",
            "Current owner: Duty [jira:a].",
            "Remit [EMEA].",
        ],
    }
    old = {**person("leo", "advisor", "growth"), "evidence_ids": ["x"], "why": ["W."]}
    plan = build_plan({"areas": [area("Growth", "growth", nina, old)]})
    assert plan["people"]["nina"]["label"] == "Related work"
    assert plan["people"]["nina"]["evidence"] == [
        {"text": "Author: ‘Text.’", "source_id": "slack:b"},
        {"text": "Current owner: Duty.", "source_id": "jira:a"},
        {"text": "Remit [EMEA].", "source_id": "docs:c"},
    ]
    # Without a recorded primary source the order is unknown, so nothing is linked.
    assert plan["people"]["leo"]["label"] == "Can advise"
    assert plan["people"]["leo"]["evidence"] == [{"text": "W.", "source_id": None}]
    # Lines and citations that do not match one to one are shown without links.
    nina["why"] = nina["why"][:2]
    plan = build_plan({"areas": [area("Growth", "growth", nina)]})
    assert [e["source_id"] for e in plan["people"]["nina"]["evidence"]] == [None, None]


def test_plan_lines_are_shortened_and_people_grouped_by_area():
    long_record = (
        "Author of a document record: ‘This policy was written in 2024. It lists who"
        " approved budget changes …’"
    )
    cut_record = "Reporter of a jira record: ‘Prepare the reforecast with spend per …’"
    note = (
        "An earlier responsibility ended on 2025-06-30: approver — approving budgets."
    )
    tara = {
        **person("tara", "direct_contact", "finance", kind="responsibility"),
        "name": "Tara Lee Reed",
        "headline": "Current reviewer — reviewing spend requests.",
    }
    omar = {
        **person("omar", "advisor", "finance"),
        "headline": long_record,
        "ended_duty": note,
    }
    marcus = {**person("marcus", "advisor", "growth"), "headline": cut_record}
    card = {
        "areas": [
            {**area("Finance", "finance", tara, omar), "consultation_need": "Limits?"},
            {**area("Growth", "growth", marcus), "consultation_need": "Volumes?"},
        ],
        # The first choice is in the second area, and Omar is chosen before Tara
        # although the area lists Tara first.
        "first_conversations": ["marcus", "omar", "tara"],
    }
    plan = build_plan(card)
    short = {e["person_id"]: e["short"] for e in plan["first"]}
    # A record keeps only its first sentence; without one the excerpt stays whole.
    assert short["omar"] == "Wrote a document: ‘This policy was written in 2024.’"
    assert short["marcus"] == (
        "Reported a Jira issue: ‘Prepare the reforecast with spend per …’"
    )
    assert short["tara"] == "Current reviewer — reviewing spend requests."
    assert plan["people"]["omar"]["ended_short"] == "Approver role ended on 2025-06-30."
    # The full note stays for the full list.
    assert plan["people"]["omar"]["ended_duty"] == note
    assert plan["people"]["tara"]["ended_short"] is None
    # Areas follow their first chosen person; people keep the chosen order.
    groups = [
        (g["area"], g["need"], [e["person_id"] for e in g["people"]])
        for g in plan["groups"]
    ]
    assert groups == [
        ("Growth", "Volumes?", ["marcus"]),
        ("Finance", "Limits?", ["omar", "tara"]),
    ]
    assert [e["initials"] for e in plan["first"]] == ["M", "O", "TR"]
    # An older card without a headline or a question shows neither.
    old = build_plan(
        {"areas": [area("Growth", "growth", person("leo", "advisor", "g"))]}
    )
    assert old["first"][0]["short"] is None
    assert old["groups"][0]["need"] is None


def test_first_sentence_skips_abbreviations():
    cases = {
        "Review e.g. card payment failures before launch.": "Review e.g. card payment"
        " failures before launch.",
        "See Dr. Patel about the budget. She owns the ledger.": "See Dr. Patel about"
        " the budget.",
        "U.S. stores need a new pickup flow. Start with Northgate.": "U.S. stores need"
        " a new pickup flow.",
        "Ship it, e.g. the checkout path, by Friday. Then tell finance.": "Ship it,"
        " e.g. the checkout path, by Friday.",
        "Release v2.1 is out. Next steps follow.": "Release v2.1 is out.",
    }
    for quote, first in cases.items():
        line = _short(f"Author of a document record: ‘{quote}’")
        assert line == f"Wrote a document: ‘{first}’"


def test_spoken_summary_names_only_the_plan_people_and_areas():
    areas = [
        area("Finance", "finance", person("tara", "direct_contact", "finance")),
        area(
            "Growth",
            "growth",
            person("jules", "direct_contact", "growth"),
            person("marcus", "advisor", "growth"),
        ),
        area("Platform", "platform", person("owen", "direct_contact", "platform")),
        area("Legal", "legal", status="not_found"),
    ]
    card = {
        "areas": [{**a, "consultation_need": f"Need for {a['label']}?"} for a in areas],
        "first_conversations": ["tara", "jules", "owen", "marcus"],
    }
    plan = build_plan(card)
    assert plan["headline"] == "Before you start, talk to four people."
    assert plan["lead"] == (
        "Start with Tara in Finance. Then Jules and Marcus in Growth, and Owen in"
        " Platform. Each card says what to find out. One area is still open."
    )
    assert plan["spoken"] == f"{plan['headline']} {plan['lead']}"
    two = build_plan({**card, "first_conversations": ["tara", "owen"]})
    assert two["lead"].startswith("Start with Tara in Finance. Then Owen in Platform.")
    one = build_plan({**card, "first_conversations": ["jules"]})
    assert one["headline"] == "Before you start, talk to one person."
    assert one["lead"].startswith("Start with Jules in Growth. Each card")


def test_spoken_summary_without_people_reports_only_the_open_areas():
    card = {
        "areas": [
            area("Legal", "legal", status="not_found"),
            area("Brand", None, status="mapping_unresolved"),
        ]
    }
    plan = build_plan(card)
    assert plan["headline"] == "I found no one to point you to from the work I can see."
    assert plan["lead"] == "Two areas are still open."
    assert build_plan({"areas": []})["spoken"] == plan["headline"]


def test_spoken_summary_does_not_promise_what_to_find_out_on_older_cards():
    # Cards stored before areas had a consultation need show no such block.
    plan = build_plan({**CARD, "first_conversations": ["tara"]})
    assert plan["lead"] == "Start with Tara in Finance. Two areas are still open."
