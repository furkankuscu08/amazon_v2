"""Follow-up answers are rule-matched and built only from the plan the page shows."""

import pytest

from workbot.followup import _said, carried, chips, reply, resolve
from workbot.plan import build_plan

NOTE = "An earlier responsibility ended on 2025-06-30: approver."


def person(pid, name, role, org, **extra):
    return {
        "person_id": pid,
        "name": name,
        "role": role,
        "confidence": "medium",
        "org_id": org,
        "primary_kind": "author",
        "primary_evidence_id": f"docs:{pid}",
        "evidence_ids": [f"docs:{pid}"],
        "headline": f"Author of a document record: ‘{name} wrote this. More text.’",
        "why": [f"Author of a document record: ‘{name} wrote this. More text.’"],
        **extra,
    }


TARA = person("tara", "Tara Reed", "direct_contact", "finance")
OMAR = person("omar", "Omar Haddad", "direct_contact", "finance", ended_duty=NOTE)
MARCUS = person("marcus", "Marcus Reed", "advisor", "growth")
HELEN = person(
    "helen",
    "Helen Brooks",
    "routing_contact",
    "finance",
    primary_kind="manager",
    evidence_ids=["directory:finance-manager", "directory:finance-remit"],
    primary_evidence_id="directory:finance-manager",
    headline=None,
    why=["No one was identified from the visible work. Helen Brooks manages Finance."],
)
CARD = {
    "areas": [
        {
            "label": "Finance",
            "org_unit_id": "finance",
            "status": "people",
            "consultation_need": "Which spend limits need a reviewer",
            "people": [TARA, OMAR],
        },
        {
            "label": "Growth Marketing",
            "org_unit_id": "growth",
            "status": "people",
            "consultation_need": "Which campaigns would skip review?",
            "people": [MARCUS, TARA],
        },
        {
            "label": "Legal",
            "org_unit_id": "legal",
            "status": "not_found",
            "people": [],
        },
    ],
    "first_conversations": ["tara", "omar"],
    "shared_question": "Who signs off on the new threshold?",
}
PLAN = build_plan(CARD)


@pytest.mark.parametrize(
    ("question", "kind", "named"),
    [
        ("Why Omar?", "why", ["omar"]),
        ("why is omar haddad on this", "why", ["omar"]),
        ("Tell me about Omar's role", "why", ["omar"]),
        ("Why should I talk to Omar?", "why", ["omar"]),
        ("Prep me for Tara", "prep", ["tara"]),
        ("What should I ask Tara?", "prep", ["tara"]),
        ("prepare me for my meeting with tara reed", "prep", ["tara"]),
        # A name Speak heard slightly wrong still finds the person.
        ("Why Tarah?", "why", ["tara"]),
        ("Who else?", "others", []),
        ("Who else besides Tara?", "others", []),
        ("What's still open?", "open", []),
        ("Is anything missing?", "open", []),
        ("Reed?", "ambiguous", ["tara", "marcus"]),
        ("Why Tara and Omar?", "ambiguous", ["tara", "omar"]),
        # A full name beats a shared surname.
        ("Why Marcus Reed?", "why", ["marcus"]),
        ("What is the weather?", "help", []),
        # Common words never pass for a misheard name.
        ("What should I say first?", "help", []),
    ],
)
def test_questions_are_matched_by_rules_to_a_kind_and_card_people(
    question, kind, named
):
    assert resolve(question, PLAN) == (kind, named)


def test_why_names_the_role_evidence_ended_duty_and_other_areas():
    answer = reply("Why Omar?", PLAN, CARD)
    assert answer["text"] == (
        "Omar Haddad is listed under Finance for related work. Omar wrote a"
        " document: ‘Omar Haddad wrote this.’ Omar's approver role ended in June"
        " 2025."
    )
    assert answer["source_id"] == "docs:omar"
    tara = reply("Why Tara?", PLAN, CARD)["text"]
    assert tara.endswith("Also listed under Growth Marketing.")


def test_prep_says_why_then_what_to_find_out_in_every_area_and_the_shared_question():
    answer = reply("Prep me for Tara", PLAN, CARD)
    assert answer["text"] == (
        "Tara Reed wrote a document: ‘Tara Reed wrote this.’ Ask Tara: Which spend"
        " limits need a reviewer. Tara is also listed under Growth Marketing; the"
        " full list says what to find out there. Across all areas: Who signs off on"
        " the new threshold?"
    )
    assert answer["source_id"] == "docs:tara"
    omar = reply("What should I ask Omar?", PLAN, CARD)["text"]
    assert "Check first: Omar's approver role ended in June 2025." in omar
    # A shared question that repeats the card's own is not said twice.
    same = {**CARD, "shared_question": "Which spend limits need a reviewer"}
    text = reply("Prep me for Omar", build_plan(same), same)["text"]
    assert "Across all areas" not in text


def test_others_and_open_cover_the_full_list_and_the_gaps():
    assert reply("Who else?", PLAN, CARD)["text"] == (
        "The full list names more people. In Growth Marketing: Marcus Reed."
        " Ask me why any of them is listed."
    )
    assert reply("What's still open?", PLAN, CARD)["text"] == (
        "No contact was found for Legal. That does not mean nobody suitable exists."
    )
    alone = {**CARD, "areas": CARD["areas"][:1]}
    plan = build_plan(alone)
    assert reply("Who else?", plan, alone)["text"] == (
        "Everyone on this plan is in the cards above."
    )
    assert reply("What's open?", plan, alone)["text"] == (
        "Nothing is open: every area has someone to talk to."
    )


def test_a_routing_contact_is_answered_without_a_single_source_link():
    card = {
        "areas": [
            {
                "label": "Finance",
                "org_unit_id": "finance",
                "status": "people",
                "consultation_need": "Limits?",
                "people": [HELEN],
            }
        ]
    }
    plan = build_plan(card)
    answer = reply("Why Helen?", plan, card)
    assert answer["text"].startswith(
        "Helen Brooks is listed under Finance as someone who can route you."
    )
    assert answer["source_id"] is None
    prep = reply("Prep me for Helen", plan, card)
    assert prep["text"] == (
        "No one was identified from the visible work. Helen Brooks manages Finance."
        " Ask Helen: Limits? Helen can point you to the right person."
    )
    assert prep["source_id"] is None


def test_a_name_not_on_the_card_is_answered_alike_for_everyone():
    # Eve is known only through restricted sources; the reply must not differ
    # from one about a person who does not exist, and never repeats the name.
    unlisted = {
        "kind": "unlisted",
        "text": "That name is not on this plan. Start with Tara Reed and Omar"
        " Haddad, or ask me who else is in the full list.",
        "source_id": None,
    }
    for question in ("Why Eve?", "Who is Eve Restricted?", "Prep me for Zed Nobody"):
        assert reply(question, PLAN, CARD) == unlisted
    # Area names and common words are no names; without one Alexa says what it can do.
    for question in ("Why the weather?", "What about Legal?", "why eve?"):
        assert reply(question, PLAN, CARD) == {
            "kind": "help",
            "text": "I can tell you why someone is listed, what to ask them, who"
            " else is in the full list, or what is still open. For example: Why"
            " Tara?",
            "source_id": None,
        }
    empty = build_plan({"areas": [CARD["areas"][2]]})
    assert reply("Why Eve?", empty, CARD)["text"] == (
        "That name is not on this plan, and the plan names no one to talk to."
    )


def test_ambiguous_names_ask_which_person_is_meant():
    assert reply("Reed?", PLAN, CARD)["text"] == (
        "Which one do you mean: Tara Reed or Marcus Reed?"
    )


def test_chips_fit_the_plan_and_hide_what_was_asked():
    assert chips(PLAN, []) == [
        "Why Omar?",
        "Prep me for Tara",
        "Who else?",
        "What's still open?",
    ]
    # Each suggestion is answered as the kind it promises.
    kinds = [resolve(chip, PLAN)[0] for chip in chips(PLAN, [])]
    assert kinds == ["why", "prep", "others", "open"]
    assert chips(PLAN, ["why omar?", "Who else?"]) == [
        "Prep me for Tara",
        "What's still open?",
    ]
    alone = {**CARD, "areas": CARD["areas"][:1], "first_conversations": ["tara"]}
    plan = build_plan(alone)
    # Omar is on the card but not in the plan; nothing is open.
    assert chips(plan, []) == ["Why Tara?", "Prep me for Tara", "Who else?"]
    empty = build_plan({"areas": [CARD["areas"][2]]})
    assert chips(empty, []) == ["What's still open?"]


def test_chips_use_a_full_name_when_a_first_name_is_shared():
    twin = person("tara2", "Tara Lund", "advisor", "growth")
    card = {
        **CARD,
        "areas": [{**CARD["areas"][0], "people": [TARA, twin]}],
        "first_conversations": ["tara"],
    }
    plan = build_plan(card)
    assert chips(plan, [])[:2] == ["Why Tara Reed?", "Prep me for Tara Reed"]
    assert resolve("Why Tara Reed?", plan) == ("why", ["tara"])


def test_ordinary_words_and_place_names_are_not_taken_for_names():
    jules = person("jules", "Jules Carter", "direct_contact", "growth")
    chloe = {
        **person("chloe", "Chloe Martin", "advisor", "platform"),
        "team": "Campaign Platform",
    }
    card = {
        "areas": [
            {
                "label": "Growth Marketing",
                "org_unit_id": "growth",
                "status": "people",
                "consultation_need": "Launch?",
                "people": [jules, chloe],
            }
        ]
    }
    plan = build_plan(card)
    for question in (
        "What rules apply?",
        "What about Growth Marketing?",
        "What should I ask Marketing?",
        "Why is Campaign Platform involved?",
        # Speak starts every sentence with a capital; acronyms are no names.
        "Okay. Who should I start with?",
        "Is VP approval needed? Thanks.",
    ):
        assert resolve(question, plan) == ("help", []), question
    # A lowercase near miss is not guessed; a capitalized one is.
    assert resolve("why jule?", plan) == ("help", [])
    assert resolve("Why Jule?", plan) == ("why", ["jules"])
    assert resolve("why chloe martin", plan) == ("why", ["chloe"])
    assert resolve("Okay. Why Paul?", plan) == ("unlisted", [])


def test_a_chip_asked_in_other_words_is_not_offered_again():
    assert "Why Omar?" not in chips(PLAN, ["why omar"])


def test_long_earlier_questions_are_dropped_before_the_form_gets_too_large():
    short = [f"Question {n}?" for n in range(7)]
    assert carried(short) == short[-5:]
    wide = ["“Why” ” ’ " * 20] * 5
    kept = carried([*wide, "Why Omar?"])
    assert kept[-1] == "Why Omar?" and len(kept) < 5


@pytest.mark.parametrize(
    ("line", "said"),
    [
        ("Wrote a document: ‘A.’", "Omar wrote a document: ‘A.’"),
        ("Assigned to a Jira issue: ‘A.’", "Omar was assigned a Jira issue: ‘A.’"),
        (
            "Contributed to a GitHub pull request: ‘A.’",
            "Omar contributed to a GitHub pull request: ‘A.’",
        ),
        ("Reported a Jira issue: ‘A.’", "Omar reported a Jira issue: ‘A.’"),
        (
            "Current reviewer — reviewing marketing spend requests.",
            "Omar is the current reviewer — reviewing marketing spend requests.",
        ),
        ("Team remit: budgets", "Team remit: budgets."),
    ],
)
def test_a_plan_line_is_said_with_the_person_as_its_subject(line, said):
    assert _said(line, "Omar") == said
