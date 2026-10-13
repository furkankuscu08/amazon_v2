"""Load the synthetic company fixture; preserve modified rows and rebuild visible indexes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from workbot.storage import connect, initialize

FIXTURE_DIR = Path(__file__).parent / "fixture"


def load_fixture() -> tuple[dict, list[dict]]:
    directory = json.loads((FIXTURE_DIR / "directory.json").read_text("utf-8"))
    records = json.loads((FIXTURE_DIR / "records.json").read_text("utf-8"))
    return directory, records


def seed_db(db) -> None:
    initialize(db)
    directory, records = load_fixture()

    def insert(table: str, columns: str, rows: list[dict]) -> None:
        # Fixture keys carry the column names; keys that are not columns are ignored.
        values = ", ".join(":" + column for column in columns.split(", "))
        db.executemany(
            f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({values})", rows
        )

    insert("org_units", "id, name", directory["org_units"])
    insert(
        "people",
        "id, name, title, active, org_id",
        # Stored as 0 or 1; int() fails on a non-numeric value such as "yes".
        [{**person, "active": int(person["active"])} for person in directory["people"]],
    )
    # Each directory claim carries its own source and visibility.
    db.executemany(
        "INSERT OR IGNORE INTO directory_sources VALUES (:source_id, 'v1', :visibility)",
        directory["managers"]
        + directory["team_remits"]
        + directory["responsibilities"],
    )
    insert(
        "managers",
        "org_id, person_id, valid_from, valid_to, source_id",
        directory["managers"],
    )
    insert(
        "team_remits",
        "id, org_id, scope, valid_from, valid_to, source_id",
        directory["team_remits"],
    )
    insert(
        "responsibilities",
        "id, person_id, org_id, scope, relation, valid_from, valid_to, verified_at, source_id",
        directory["responsibilities"],
    )
    db.executemany(
        "INSERT OR IGNORE INTO work_records VALUES (:id, :kind, :occurred_at, :text, :visibility, 'v1')",
        records,
    )
    db.executemany(
        "INSERT OR IGNORE INTO work_links VALUES (?, ?, ?)",
        [
            (record["id"], person_id, relation)
            for record in records
            for person_id, relation in record["links"]
        ],
    )
    # Also repairs an older seed's visible index; this happens before requests.
    db.execute("DELETE FROM visible_fts")
    db.execute(
        "INSERT INTO visible_fts(record_id, text) SELECT id, text FROM work_records WHERE visibility='maya'"
    )
    db.commit()


def main() -> None:
    from dotenv import load_dotenv

    from workbot.search import index_visible_records

    load_dotenv()
    db = connect(os.getenv("WORKBOT_DB_PATH", "data/workbot.sqlite3"))
    seed_db(db)
    count = index_visible_records(db, os.getenv("QDRANT_URL", "http://localhost:6333"))
    print(f"Seeded synthetic directory and {count} searchable visible records.")


if __name__ == "__main__":
    main()
