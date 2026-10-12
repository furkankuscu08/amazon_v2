"""Mechanical validity of the shipped synthetic company fixture."""

import json
import re
from datetime import date
from pathlib import Path

from workbot.seed import load_fixture, seed_db
from workbot.storage import connect

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
