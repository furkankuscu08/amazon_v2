"""Mechanical validity of the shipped synthetic company fixture."""

import html
import json
import re
from datetime import date
from pathlib import Path

from workbot.search import (
    Searcher,
    candidate_pool,
    directory_hints,
    index_visible_records,
)
from workbot.seed import load_fixture, seed_db
from workbot.storage import connect, visible_record

RELATIONS = {"assignee", "author", "contributor", "reporter", "mention"}
KINDS = {"jira", "slack", "github", "document"}
PREFIXES = {
    "jira": "jira:",
    "slack": "slack:",
    "github": "github:",
    "document": "docs:",
}
# Known only through restricted sources; must have no visible footprint at all.
RESTRICTED_ONLY = {"eve", "zoe"}


def _first_name(person: dict) -> str:
    return person["name"].split()[0]


def test_directory_references_are_consistent():
    directory, _ = load_fixture()
    orgs = {unit["id"] for unit in directory["org_units"]}
    people = {person["id"]: person for person in directory["people"]}
    assert len(people) == len(directory["people"])
    assert len({_first_name(p) for p in people.values()}) == len(people)
    assert all(person["org_id"] in orgs for person in people.values())
    for claim in directory["managers"] + directory["responsibilities"]:
        assert people[claim["person_id"]]["org_id"] == claim["org_id"]
        assert people[claim["person_id"]]["active"]
    claims = (
        directory["managers"] + directory["team_remits"] + directory["responsibilities"]
    )
    assert all(claim["org_id"] in orgs for claim in claims)
    assert all(claim["source_id"].startswith("directory:") for claim in claims)
    assert all(claim["visibility"] in {"maya", "restricted"} for claim in claims)
    assert len({claim["source_id"] for claim in claims}) == len(claims)


def test_records_are_well_formed():
    directory, records = load_fixture()
    people = {person["id"]: person for person in directory["people"]}
    assert len({record["id"] for record in records}) == len(records)
    for record in records:
        assert set(record) == {
            "id",
            "kind",
            "occurred_at",
            "text",
            "visibility",
            "links",
        }, record["id"]
        assert record["kind"] in KINDS, record["id"]
        assert record["id"].startswith(PREFIXES[record["kind"]]), record["id"]
        assert record["visibility"] in {"maya", "restricted"}, record["id"]
        assert (
            date(2023, 1, 1)
            <= date.fromisoformat(record["occurred_at"])
            <= date(2026, 10, 12)
        ), record["id"]
        assert 120 <= len(record["text"]) <= 400, record["id"]
        assert record["text"].isascii(), record["id"]
        relations = [relation for _, relation in record["links"]]
        assert record["links"] and set(relations) <= RELATIONS, record["id"]
        assert sum(r in {"assignee", "author"} for r in relations) == 1, record["id"]
        assert len({tuple(link) for link in record["links"]}) == len(record["links"])
        linked = {person_id for person_id, _ in record["links"]}
        assert linked <= set(people), record["id"]
        for person_id, relation in record["links"]:
            if relation == "mention":
                assert _first_name(people[person_id]) in record["text"], record["id"]
        # Naming an unlinked colleague would create evidence the directory cannot audit.
        for person_id, person in people.items():
            if person_id not in linked:
                assert not re.search(rf"\b{_first_name(person)}\b", record["text"]), (
                    record["id"],
                    person_id,
                )


def test_restricted_only_people_have_no_visible_footprint():
    directory, records = load_fixture()
    for record in records:
        if record["visibility"] == "maya":
            assert not {pid for pid, _ in record["links"]} & RESTRICTED_ONLY
    for claim in directory["managers"] + directory["responsibilities"]:
        if claim["person_id"] in RESTRICTED_ONLY:
            assert claim["visibility"] == "restricted"


def test_fixture_seeds_and_indexes_only_visible_records(tmp_path):
    _, records = load_fixture()
    db = connect(str(tmp_path / "fixture.sqlite3"))
    seed_db(db)
    visible = {r["id"] for r in records if r["visibility"] == "maya"}
    indexed = {
        row["record_id"] for row in db.execute("SELECT record_id FROM visible_fts")
    }
    assert indexed == visible
    assert db.execute("SELECT COUNT(*) FROM work_records").fetchone()[0] == len(records)
    db.close()


def test_expectations_refer_to_the_fixture():
    directory, records = load_fixture()
    people = {person["id"]: person for person in directory["people"]}
    expected = json.loads(
        (Path(__file__).parent / "expectations.json").read_text("utf-8")
    )
    hidden = {p for p, person in people.items() if not person["active"]}
    assert set(expected["never_show"]) == hidden | RESTRICTED_ONLY
    claims = (
        directory["managers"] + directory["team_remits"] + directory["responsibilities"]
    )
    restricted = {r["id"] for r in records if r["visibility"] == "restricted"} | {
        claim["source_id"] for claim in claims if claim["visibility"] == "restricted"
    }
    assert set(expected["never_cite"]) == restricted
    for idea in expected["ideas"]:
        named = (
            idea.get("must_show", [])
            + idea.get("must_not_be_direct", [])
            + idea.get("expected_routing", [])
            + [p for group in idea.get("must_show_any", []) for p in group]
        )
        assert named and set(named) <= set(people) - set(expected["never_show"])


def test_every_home_page_example_has_an_answer_key():
    home = (Path(__file__).parent.parent / "workbot/templates/home.html").read_text(
        "utf-8"
    )
    examples = [html.unescape(i) for i in re.findall(r'data-idea="([^"]+)"', home)]
    expected = json.loads(
        (Path(__file__).parent / "expectations.json").read_text("utf-8")
    )
    assert len(examples) == 3
    assert set(examples) <= {idea["idea"] for idea in expected["ideas"]}


def test_candidate_cap_follows_retrieval_rank_not_recency(tmp_path):
    db = connect(str(tmp_path / "rank.sqlite3"))
    seed_db(db)
    # The best-ranked record is the oldest; eleven newer, unrelated records with
    # other authors follow it. Its author must keep a place among the ten.
    ranked = [
        "docs:campaign-review-2023",
        "docs:support-floor-office-move",
        "slack:data-602",
        "docs:growth-quarterly-themes",
        "docs:finance-team-offsite-agenda",
        "slack:growth-604",
        "slack:support-803",
        "slack:plt-88",
        "jira:MOB-779",
        "docs:campaign-calendar-q4",
        "slack:commerce-601",
        "jira:PAY-171",
    ]
    area = {
        "org_unit_id": "brand",
        "search_intents": [{"keyword": "zzzz", "semantic": "zzzz"}],
    }
    pool = candidate_pool(db, area, [visible_record(db, rid) for rid in ranked])
    people = [person["person_id"] for person in pool["people"]]
    assert len(people) == 10
    assert people[0] == "priya"
    assert "ben" not in people
    assert "rank" not in json.dumps(pool)
    db.close()


def test_keyword_tail_is_dropped_unless_the_vector_channel_agrees(tmp_path):
    from qdrant_client import QdrantClient

    def toy_embedding(text: str) -> list[float]:
        return [1.0, 0.0] if "refund" in text.lower() else [0.0, 1.0]

    db = connect(str(tmp_path / "tail.sqlite3"))
    seed_db(db)
    client = QdrantClient(location=":memory:")
    try:
        index_visible_records(db, "unused", client=client, embed_fn=toy_embedding)
        intents = [{"keyword": "refund customers checklist", "semantic": "refund"}]
        keyword_hits = db.execute(
            """SELECT COUNT(*) FROM visible_fts
            WHERE visible_fts MATCH '"refund" OR "customers" OR "checklist"'"""
        ).fetchone()[0]
        found = Searcher("unused", client=client, embed_fn=toy_embedding).records(
            db, intents
        )
        assert keyword_hits >= 12
        assert 0 < len(found) <= 8
        # Only the three best keyword-only hits may lack vector agreement.
        assert sum("refund" not in r["text"].lower() for r in found) <= 3
        assert any(r["retrieval_channels"] == ["bm25", "qdrant"] for r in found)
    finally:
        client.close()
        db.close()


SPEND_DUTY = "Reviewing marketing spend requests above the approval threshold"
POLICY_DUTY = "Compliance review of changes to the spending approval policy"
DIRECTORY_HINTS = {
    "campaign-ai": {
        "growth": "Reviewing campaign launch approvals",
        "brand": "Approving advertising claims in campaign copy",
    },
    "stablecoin": {},
    "refund-assistant": {},
    "pickup-lockers": {},
    "customer-scoring": {},
    "spend-threshold": {"finance": SPEND_DUTY, "legal": POLICY_DUTY},
    "spend-policy": {"finance": SPEND_DUTY, "legal": POLICY_DUTY},
}


def test_directory_hints_for_the_demo_ideas(tmp_path):
    db = connect(str(tmp_path / "fixture.sqlite3"))
    seed_db(db)
    expected = json.loads(
        (Path(__file__).parent / "expectations.json").read_text("utf-8")
    )
    assert {idea["id"] for idea in expected["ideas"]} == set(DIRECTORY_HINTS)
    for idea in expected["ideas"]:
        hints = directory_hints(db, idea["idea"])
        assert all(set(hint) == {"org_unit_id", "current_duty"} for hint in hints)
        assert {h["org_unit_id"]: h["current_duty"] for h in hints} == (
            DIRECTORY_HINTS[idea["id"]]
        ), idea["id"]
    db.close()


def test_directory_hints_skip_ended_restricted_and_inactive_duties(tmp_path):
    db = connect(str(tmp_path / "fixture.sqlite3"))
    seed_db(db)
    # Each text matches its duty word for word, so only the filters keep it out.
    ended = "Approving marketing budget changes"
    assert ended not in json.dumps(directory_hints(db, ended))
    assert directory_hints(db, "Privacy impact assessments for customer scoring") == []
    assert directory_hints(db, "Campaign budget authorization") == []  # restricted
    assert {"org_unit_id": "finance", "current_duty": SPEND_DUTY} in (
        directory_hints(db, SPEND_DUTY)
    )
    # A duty counts only for an active person still in that org unit.
    db.execute("UPDATE people SET org_id='growth' WHERE id='tara'")
    assert "finance" not in {h["org_unit_id"] for h in directory_hints(db, SPEND_DUTY)}
    db.execute("UPDATE people SET org_id='finance', active=0 WHERE id='tara'")
    assert "finance" not in {h["org_unit_id"] for h in directory_hints(db, SPEND_DUTY)}
    assert "directory:" not in json.dumps(directory_hints(db, POLICY_DUTY))
    db.close()


def test_directory_duties_name_no_person():
    # Duty texts reach the impact call as hints with no person attached.
    directory, _ = load_fixture()
    for claim in directory["responsibilities"] + directory["team_remits"]:
        for person in directory["people"]:
            assert not re.search(rf"\b{_first_name(person)}\b", claim["scope"]), (
                claim["id"],
                person["id"],
            )
