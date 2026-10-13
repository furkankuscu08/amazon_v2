"""The first-conversations plan is a pure regrouping of an audited card."""

from workbot.plan import build_plan, placements


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
    assert plan["notes"] == {"omar": note}
