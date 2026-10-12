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
    db.executemany(
        "INSERT OR IGNORE INTO org_units VALUES (?, ?)",
        [(unit["id"], unit["name"]) for unit in directory["org_units"]],
    )
    db.executemany(
        "INSERT OR IGNORE INTO people VALUES (?, ?, ?, ?, ?)",
        [
            (p["id"], p["name"], p["title"], int(p["active"]), p["org_id"])
            for p in directory["people"]
        ],
    )
    # Each directory claim carries its own source and visibility.
    claims = (
        directory["managers"] + directory["team_remits"] + directory["responsibilities"]
    )
    db.executemany(
        "INSERT OR IGNORE INTO directory_sources VALUES (?, 'v1', ?)",
        [(claim["source_id"], claim["visibility"]) for claim in claims],
    )
    db.executemany(
        "INSERT OR IGNORE INTO managers VALUES (?, ?, ?, ?, ?)",
        [
            (
                m["org_id"],
                m["person_id"],
                m["valid_from"],
                m["valid_to"],
                m["source_id"],
            )
            for m in directory["managers"]
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO team_remits VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                r["id"],
                r["org_id"],
                r["scope"],
                r["valid_from"],
                r["valid_to"],
                r["source_id"],
            )
            for r in directory["team_remits"]
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO responsibilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                r["id"],
                r["person_id"],
                r["org_id"],
                r["scope"],
                r["relation"],
                r["valid_from"],
                r["valid_to"],
                r["verified_at"],
                r["source_id"],
            )
            for r in directory["responsibilities"]
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO work_records VALUES (?, ?, ?, ?, ?, 'v1')",
        [
            (r["id"], r["kind"], r["occurred_at"], r["text"], r["visibility"])
            for r in records
        ],
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
