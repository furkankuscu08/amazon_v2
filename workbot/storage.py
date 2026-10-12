from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS org_units (
            id TEXT PRIMARY KEY, name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS people (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL,
            active INTEGER NOT NULL, org_id TEXT NOT NULL REFERENCES org_units(id)
        );
        CREATE TABLE IF NOT EXISTS directory_sources (
            id TEXT PRIMARY KEY, version TEXT NOT NULL, visibility TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS responsibilities (
            id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES people(id),
            org_id TEXT NOT NULL REFERENCES org_units(id), scope TEXT NOT NULL,
            relation TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT,
            verified_at TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES directory_sources(id)
        );
        CREATE TABLE IF NOT EXISTS team_remits (
            id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES org_units(id),
            scope TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT,
            source_id TEXT NOT NULL REFERENCES directory_sources(id)
        );
        CREATE TABLE IF NOT EXISTS managers (
            org_id TEXT NOT NULL REFERENCES org_units(id),
            person_id TEXT NOT NULL REFERENCES people(id), valid_from TEXT NOT NULL,
            valid_to TEXT, source_id TEXT NOT NULL REFERENCES directory_sources(id),
            PRIMARY KEY (org_id, person_id, source_id)
        );
        CREATE TABLE IF NOT EXISTS work_records (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, occurred_at TEXT NOT NULL,
            text TEXT NOT NULL, visibility TEXT NOT NULL, version TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS work_links (
            record_id TEXT NOT NULL REFERENCES work_records(id),
            person_id TEXT NOT NULL REFERENCES people(id), relation TEXT NOT NULL,
            PRIMARY KEY (record_id, person_id, relation)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS visible_fts USING fts5(
            record_id UNINDEXED, text, tokenize='porter unicode61'
        );
        CREATE TRIGGER IF NOT EXISTS work_fts_insert AFTER INSERT ON work_records
        WHEN NEW.visibility='maya' BEGIN
            INSERT INTO visible_fts(record_id, text) VALUES (NEW.id, NEW.text);
        END;
        CREATE TRIGGER IF NOT EXISTS work_fts_update AFTER UPDATE OF text, visibility ON work_records BEGIN
            DELETE FROM visible_fts WHERE record_id=OLD.id;
            INSERT INTO visible_fts(record_id, text)
                SELECT NEW.id, NEW.text WHERE NEW.visibility='maya';
        END;
        CREATE TRIGGER IF NOT EXISTS work_fts_delete AFTER DELETE ON work_records BEGIN
            DELETE FROM visible_fts WHERE record_id=OLD.id;
        END;
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, actor TEXT NOT NULL, workspace TEXT NOT NULL,
            idem_key TEXT NOT NULL, sentence TEXT NOT NULL, answers_json TEXT NOT NULL,
            questions_asked INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL, question TEXT,
            card_json TEXT, snapshot_json TEXT,
            UNIQUE (actor, workspace, idem_key)
        );
        CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    db.commit()


def visible_record(db: sqlite3.Connection, record_id: str) -> dict | None:
    row = db.execute(
        "SELECT * FROM work_records WHERE id=? AND visibility='maya'", (record_id,)
    ).fetchone()
    return dict(row) if row else None


def visible_directory_source(db: sqlite3.Connection, source_id: str) -> dict | None:
    row = db.execute(
        "SELECT * FROM directory_sources WHERE id=? AND visibility='maya'", (source_id,)
    ).fetchone()
    return dict(row) if row else None


def source(db: sqlite3.Connection, source_id: str) -> dict | None:
    if source_id.startswith("directory:"):
        return visible_directory_source(db, source_id)
    return visible_record(db, source_id)


def current(row: dict, today: str | None = None) -> bool:
    today = today or datetime.now(timezone.utc).date().isoformat()
    return row["valid_from"] <= today and (
        row["valid_to"] is None or today <= row["valid_to"]
    )


def current_managers(db: sqlite3.Connection, org_id: str) -> list[tuple[dict, dict]]:
    """Only active people with visible, current manager relationships are eligible."""
    managers = []
    for relation in db.execute(
        "SELECT * FROM managers WHERE org_id=? ORDER BY person_id, source_id", (org_id,)
    ):
        person = db.execute(
            "SELECT * FROM people WHERE id=? AND org_id=? AND active=1",
            (relation["person_id"], org_id),
        ).fetchone()
        if (
            person
            and current(dict(relation))
            and visible_directory_source(db, relation["source_id"])
        ):
            managers.append((dict(relation), dict(person)))
    return managers


def org_inventory(db: sqlite3.Connection) -> list[dict]:
    return [
        dict(row) for row in db.execute("SELECT id, name FROM org_units ORDER BY id")
    ]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def inventory_version(db: sqlite3.Connection) -> str:
    return _digest(org_inventory(db))


def visible_index_version(db: sqlite3.Connection) -> str:
    """A stale vector collection must not affect results after access changes."""
    rows = [
        dict(row)
        for row in db.execute(
            "SELECT id, text, version FROM work_records WHERE visibility='maya' ORDER BY id"
        )
    ]
    return _digest(rows)


def visible_fts_matches(db: sqlite3.Connection) -> bool:
    records = [
        tuple(row)
        for row in db.execute(
            "SELECT id, text FROM work_records WHERE visibility='maya' ORDER BY id"
        )
    ]
    indexed = [
        tuple(row)
        for row in db.execute(
            "SELECT record_id, text FROM visible_fts ORDER BY record_id"
        )
    ]
    return indexed == records


def dependency_snapshot(db: sqlite3.Connection, card: dict) -> dict | None:
    """Snapshot only relied-on visible facts; never persist restricted content."""
    people_ids = {p["person_id"] for area in card["areas"] for p in area["people"]}
    source_ids = {
        sid
        for area in card["areas"]
        for p in area["people"]
        for sid in [*p["evidence_ids"], *p.get("context_ids", [])]
    }
    # Shown as ended duties, so they must stay visible and unchanged, not current.
    context_ids = {
        sid
        for area in card["areas"]
        for p in area["people"]
        for sid in p.get("context_ids", [])
    }
    people = {}
    for pid in sorted(people_ids):
        row = db.execute(
            "SELECT * FROM people WHERE id=? AND active=1", (pid,)
        ).fetchone()
        if not row:
            return None
        people[pid] = dict(row)
    routing_managers = {}
    for area in card["areas"]:
        routing = [p for p in area["people"] if p["role"] == "routing_contact"]
        if not routing:
            continue
        managers = current_managers(db, area["org_unit_id"])
        if len({person["id"] for _, person in managers}) != 1 or any(
            person["id"] != routing[0]["person_id"] for _, person in managers
        ):
            return None
        routing_managers[area["org_unit_id"]] = _digest(managers)
    sources = {}
    relations = {}
    work_links = {}
    for sid in sorted(source_ids):
        row = source(db, sid)
        if not row:
            return None
        # Hash record contents, not only the caller-supplied version field.
        sources[sid] = _digest(row)
        if sid.startswith("directory:"):
            related = []
            for table, ordering in (
                ("responsibilities", "id"),
                ("team_remits", "id"),
                ("managers", "org_id, person_id, source_id"),
            ):
                related.extend(
                    dict(item)
                    for item in db.execute(
                        f"SELECT * FROM {table} WHERE source_id=? ORDER BY {ordering}",
                        (sid,),
                    )
                )
            if not related or (
                sid not in context_ids and any(not current(item) for item in related)
            ):
                return None
            relations[sid] = _digest(related)
        else:
            linked_people = [
                p
                for area in card["areas"]
                for p in area["people"]
                if sid in p["evidence_ids"]
            ]
            for person in linked_people:
                links = [
                    dict(link)
                    for link in db.execute(
                        "SELECT relation FROM work_links WHERE record_id=? AND person_id=? ORDER BY relation",
                        (sid, person["person_id"]),
                    )
                ]
                if not links:
                    return None
                work_links[sid + "/" + person["person_id"]] = _digest(links)
    snapshot = {
        "inventory": inventory_version(db),
        "people": _digest(people),
        "sources": sources,
        "relations": relations,
        "work_links": work_links,
    }
    if routing_managers:
        snapshot["routing_managers"] = routing_managers
    return snapshot


def store_card(db: sqlite3.Connection, session_id: str, card: dict) -> None:
    snapshot = dependency_snapshot(db, card)
    if snapshot is None:
        raise ValueError("Card dependencies no longer visible or current")
    db.execute(
        "UPDATE sessions SET state='card', question=NULL, card_json=?, snapshot_json=? WHERE id=?",
        (json.dumps(card), json.dumps(snapshot, sort_keys=True), session_id),
    )
    db.commit()


def load_session(db: sqlite3.Connection, session_id: str) -> dict | None:
    row = db.execute(
        "SELECT * FROM sessions WHERE id=? AND actor='maya' AND workspace='demo'",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None


def recent_sessions(db: sqlite3.Connection, limit: int = 6) -> list[dict]:
    """The demo user's latest requests, newest first, with a fail-closed status."""
    rows = db.execute(
        """SELECT * FROM sessions WHERE actor='maya' AND workspace='demo'
        ORDER BY rowid DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    found = []
    for row in rows:
        session = dict(row)
        status = session["state"]
        if status == "card" and valid_card(db, session) is None:
            status = "stale"
        found.append(
            {"id": session["id"], "idea": session["sentence"], "status": status}
        )
    return found


def valid_card(db: sqlite3.Connection, session: dict) -> dict | None:
    if session["state"] != "card" or not session["card_json"]:
        return None
    try:
        card = json.loads(session["card_json"])
        if dependency_snapshot(db, card) != json.loads(session["snapshot_json"]):
            return None
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    return card
