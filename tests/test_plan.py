"""The first-conversations plan is a pure regrouping of an audited card."""

from workbot.plan import _line, _short, build_plan, placements


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
    # A card stored before notes kept their source links nothing.
    assert plan["people"]["omar"]["ended_source"] is None


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
        "context_ids": ["directory:omar-old"],
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
    assert plan["people"]["omar"]["ended_short"] == "Approver role ended in June 2025."
    # The full note stays for the full list, with its date written out.
    assert plan["people"]["omar"]["ended_duty"] == note
    assert plan["people"]["omar"]["ended_full"] == note.replace(
        "2025-06-30", "30 June 2025"
    )
    assert plan["people"]["tara"]["ended_short"] is None
    # The note links the directory source it came from.
    assert plan["people"]["omar"]["ended_source"] == "directory:omar-old"
    assert plan["people"]["tara"]["ended_source"] is None
    # Areas follow their first chosen person; people keep the chosen order, except
    # that Omar, whose approver role has ended, follows Tara.
    groups = [
        (g["area"], g["need"], [e["person_id"] for e in g["people"]])
        for g in plan["groups"]
    ]
    assert groups == [
        ("Growth", "Volumes?", ["marcus"]),
        ("Finance", "Limits?", ["tara", "omar"]),
    ]
    assert [e["initials"] for e in plan["first"]] == ["M", "TR", "O"]
    assert plan["lead"].startswith("Start with Marcus in Growth. Then Tara Lee Reed")
    # An older card without a headline or a question shows neither.
    old = build_plan(
        {"areas": [area("Growth", "growth", person("leo", "advisor", "g"))]}
    )
    assert old["first"][0]["short"] is None
    assert old["groups"][0]["need"] is None


def test_people_whose_duty_ended_are_not_who_to_start_with():
    note = "An earlier responsibility ended on 2025-06-30: approver."
    omar = {**person("omar", "direct_contact", "finance"), "ended_duty": note}
    tara = person("tara", "direct_contact", "finance", kind="responsibility")
    ivan = {**person("ivan", "advisor", "legal"), "ended_duty": note}
    jules = person("jules", "direct_contact", "growth", kind="responsibility")
    card = {
        "areas": [
            area("Legal", "legal", ivan),
            area("Finance", "finance", omar, tara),
            area("Growth", "growth", jules),
        ],
        "first_conversations": ["ivan", "omar", "tara", "jules"],
    }
    plan = build_plan(card)
    # Inside an area the others come first; an area with only such people goes
    # last; everything else keeps the model's order.
    assert [[e["person_id"] for e in g["people"]] for g in plan["groups"]] == [
        ["tara", "omar"],
        ["jules"],
        ["ivan"],
    ]
    assert [e["person_id"] for e in plan["first"]] == ["tara", "omar", "jules", "ivan"]
    # The voice says what the plan shows about them: role and month, after the
    # sentence that names them.
    assert plan["lead"] == (
        "Start with Tara and Omar in Finance. Omar's approver role ended in June"
        " 2025. Then Jules in Growth, and Ivan in Legal. Ivan's approver role ended"
        " in June 2025."
    )
    # The full list is unchanged.
    assert set(plan["people"]) == {"omar", "tara", "ivan", "jules"}
    # Without a usable model choice, an area's pick prefers someone whose duty
    # has not ended, even over a stronger role.
    strong = {**omar, "confidence": "high"}
    advisor = person("tara", "advisor", "finance")
    fallback = build_plan(
        {
            "areas": [area("Finance", "finance", strong, advisor)],
            "first_conversations": [],
        }
    )
    assert [e["person_id"] for e in fallback["first"]] == ["tara"]


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
    # A plan that names someone ends by inviting follow-up questions.
    assert plan["invite"] == "Ask me why anyone is listed, or what to ask them."
    assert plan["spoken"] == f"{plan['headline']} {plan['lead']} {plan['invite']}"
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
    assert plan["invite"] is None
    assert build_plan({"areas": []})["spoken"] == plan["headline"]


def test_spoken_summary_does_not_promise_what_to_find_out_on_older_cards():
    # Cards stored before areas had a consultation need show no such block.
    plan = build_plan({**CARD, "first_conversations": ["tara"]})
    assert plan["lead"] == (
        "Start with Tara in Finance. Four more areas are in the full list. Two areas"
        " are still open."
    )


def test_spoken_notes_name_ended_duties_and_routing_contacts():
    note = "An earlier responsibility ended on 2025-01-01: operator — running launches."
    elena = {**person("elena", "advisor", "growth"), "ended_duty": note}
    jules = person("jules", "direct_contact", "growth", kind="responsibility")
    anders = person("anders", "routing_contact", "legal")
    dan = person("dan", "routing_contact", "commerce")
    card = {
        "areas": [
            area("Growth", "growth", jules, elena),
            area("Legal and Compliance", "legal", anders),
            area("Commerce", "commerce", dan),
        ],
        "first_conversations": ["jules", "elena", "anders", "dan"],
    }
    plan = build_plan(card)
    # Routing contacts named in the same sentence share one note.
    assert plan["lead"] == (
        "Start with Jules and Elena in Growth. Elena's operator role ended in January"
        " 2025. Then Anders in Legal and Compliance, and Dan in Commerce. Anders and"
        " Dan can point you to the right person."
    )
    # The plan line says the month, as the voice does.
    assert plan["first"][1]["ended_short"] == "Operator role ended in January 2025."
    # A note the plan cannot read adds nothing to the voice; the screen shows it.
    for odd in ("An earlier responsibility ended on soon: operator.", "Moved teams."):
        oddly = {**elena, "ended_duty": odd}
        lead = build_plan(
            {
                "areas": [area("Growth", "growth", jules, oddly)],
                "first_conversations": ["jules", "elena"],
            }
        )
        assert lead["lead"] == "Start with Jules and Elena in Growth."
        assert lead["first"][1]["ended_short"]


def test_areas_left_out_of_the_plan_are_named_below_it():
    plan = build_plan({**CARD, "first_conversations": ["tara", "nina"]})
    # Growth has a card (Nina), Finance too; Commerce and Data have no one chosen.
    # Platform's only person is Nina, who is in the plan, so it is not named.
    assert plan["more"] == [
        {"area": "Commerce", "names": ["Dan"]},
        {"area": "Data", "names": ["Omar"]},
    ]
    assert "Two more areas are in the full list." in plan["lead"]
    # A left-out person is named even when their home is another area.
    alone = build_plan({**CARD, "first_conversations": ["tara", "leo", "dan", "omar"]})
    assert alone["more"] == [{"area": "Platform", "names": ["Nina"]}]
    assert "One more area is in the full list." in alone["lead"]
    # Gaps stay under "Still open" and never count as more areas.
    assert all(m["area"] not in ("Legal", "Brand") for m in plan["more"])


def test_full_list_names_each_area_in_the_plan_order():
    def ids(plan):
        return [[p["person_id"] for p in people] for people in plan["order"]]

    note = "An earlier responsibility ended on 2025-06-30: approver."
    omar = {**person("omar", "direct_contact", "finance"), "ended_duty": note}
    tara = person("tara", "direct_contact", "finance", kind="responsibility")
    ben = person("ben", "advisor", "finance")
    jules = person("jules", "direct_contact", "growth", kind="responsibility")
    card = {
        "areas": [
            area("Finance", "finance", omar, ben, tara),
            area("Growth", "growth", jules, tara),
            area("Legal", "legal", status="not_found"),
        ],
        "first_conversations": ["omar", "tara", "jules"],
    }
    plan = build_plan(card)
    # The plan puts Tara before Omar; the list follows it, then the others in
    # card order, and a person shown in full elsewhere comes last. It only reorders.
    assert ids(plan) == [["tara", "omar", "ben"], ["jules", "tara"], []]
    assert [e["person_id"] for e in plan["first"]] == ["tara", "omar", "jules"]
    # Without a model choice the fallback plan sets the order the same way.
    fallback = build_plan({**card, "first_conversations": None})
    assert [e["person_id"] for e in fallback["first"]] == ["tara", "jules"]
    assert ids(fallback) == [["tara", "omar", "ben"], ["jules", "tara"], []]
    # The line under the cards names left-out people in that same order.
    ivan = person("ivan", "direct_contact", "legal")
    other = build_plan(
        {
            "areas": [
                area("Finance", "finance", tara),
                area("Growth", "growth", tara, jules),
                area("Legal", "legal", ivan),
            ],
            "first_conversations": ["ivan"],
        }
    )
    assert ids(other)[1] == ["jules", "tara"]
    assert other["more"] == [
        {"area": "Finance", "names": ["Tara"]},
        {"area": "Growth", "names": ["Jules", "Tara"]},
    ]


def test_spoken_summary_stays_short_with_four_people_and_every_note():
    note = "An earlier responsibility ended on 2025-06-30: approver."
    people = [
        {
            **person(pid, "routing_contact", pid),
            "name": f"{pid.title()} Example",
            "ended_duty": note,
        }
        for pid in ("aa", "bb", "cc", "dd")
    ]
    areas = [
        {
            **area(f"Team {p['person_id']}", p["person_id"], p),
            "consultation_need": "Need?",
        }
        for p in people
    ]
    areas += [area("Spare", "spare", person("ee", "advisor", "spare"))]
    areas += [area(f"Gap {n}", None, status="not_found") for n in range(3)]
    plan = build_plan({"areas": areas, "first_conversations": ["aa", "bb", "cc", "dd"]})
    # Every note at once is unlikely; even then the voice stays under a minute.
    assert len(plan["spoken"].split()) <= 120


def test_full_list_lines_are_written_in_plain_words_with_dates_written_out():
    lines = {
        "Assignee of jira record on 2026-03-02: ‘Fix it.’": "Assigned to a Jira issue"
        " on 2 March 2026: ‘Fix it.’",
        "Author of document record on 2024-11-30: ‘Policy.’": "Wrote a document on"
        " 30 November 2024: ‘Policy.’",
        "Contributor of github record on 2026-01-05: ‘PR.’": "Contributed to a GitHub"
        " pull request on 5 January 2026: ‘PR.’",
        "Reporter of jira record on 2025-07-01: ‘Bug.’": "Reported a Jira issue on"
        " 1 July 2025: ‘Bug.’",
        "Mention of slack record on 2026-08-10: ‘Hi.’": "Mentioned in a Slack message"
        " on 10 August 2026: ‘Hi.’",
        # Older cards ended the line with the source ID; it is dropped first.
        "Mention of slack record on 2026-08-10: ‘Hi.’ [slack:x].": "Mentioned in a"
        " Slack message on 10 August 2026: ‘Hi.’",
        # Anything else, such as a directory line or an unknown kind, is left alone.
        "Current reviewer: spend.": "Current reviewer: spend.",
        "Author of wiki record on 2026-08-10: ‘Hi.’": "Author of wiki record on"
        " 2026-08-10: ‘Hi.’",
        # A cut excerpt ends at its last whole sentence, not mid-sentence.
        "Author of document record on 2024-11-30: ‘Policy. Readers should treat it"
        " as a …’": "Wrote a document on 30 November 2024: ‘Policy. …’",
        "Author of document record on 2024-11-30: ‘Policy. …’": "Wrote a document"
        " on 30 November 2024: ‘Policy. …’",
        # A period after an abbreviation or an initial does not end a sentence.
        "Author of document record on 2024-11-30: ‘Spoke to Dr. Lee. Then a …’": "Wrote a document on 30 November 2024: ‘Spoke to Dr. Lee. …’",
        "Author of document record on 2024-11-30: ‘Done. Ask J. Smith about …’": "Wrote a document on 30 November 2024: ‘Done. …’",
        # Without a whole sentence, or an abbreviation alone, it stays as stored.
        "Author of document record on 2024-11-30: ‘Spend per …’": "Wrote a document"
        " on 30 November 2024: ‘Spend per …’",
        "Author of document record on 2024-11-30: ‘Ask Dr. Lee about …’": "Wrote a"
        " document on 30 November 2024: ‘Ask Dr. Lee about …’",
    }
    for stored, shown in lines.items():
        assert _line(stored) == shown


def test_the_voice_puts_people_in_an_area_only_when_it_is_their_team():
    spoken = build_plan(CARD)["spoken"]
    assert "Start with Omar for Data." in spoken  # Omar is in Finance
    assert "Nina in Growth" in spoken and "Tara in Finance" in spoken
    # Older cards without org_id keep the earlier wording.
    old = {
        "areas": [
            {
                **a,
                "people": [
                    {k: v for k, v in p.items() if k != "org_id"} for p in a["people"]
                ],
            }
            for a in CARD["areas"]
        ]
    }
    assert "Start with Omar in Data." in build_plan(old)["spoken"]
