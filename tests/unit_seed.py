"""Small nine-person dataset for unit tests; not the application's seed data."""

from __future__ import annotations

from workbot.storage import initialize


def seed_db(db) -> None:
    initialize(db)
    db.executemany(
        "INSERT OR IGNORE INTO org_units VALUES (?, ?)",
        [
            ("growth", "Growth Marketing"),
            ("brand", "Brand Review"),
            ("platform", "Campaign Platform"),
            ("security", "Security Review"),
            ("commerce", "Commerce Operations"),
            ("finance", "Finance"),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO people VALUES (?, ?, ?, ?, ?)",
        [
            ("nina", "Nina Ellis", "Campaign Operations Specialist", 1, "growth"),
            ("elena", "Elena Park", "Campaign Analyst", 1, "growth"),
            ("marcus", "Marcus Reed", "Growth Marketing Manager", 1, "growth"),
            ("priya", "Priya Singh", "Brand Review Lead", 1, "brand"),
            ("owen", "Owen Blake", "Platform Engineer", 1, "platform"),
            ("jules", "Jules Carter", "Operations Coordinator", 1, "growth"),
            ("former", "Former Employee", "Marketing Specialist", 0, "growth"),
            ("eve", "Eve Restricted", "Operations Associate", 1, "growth"),
            ("tara", "Tara Reed", "Finance Analyst", 1, "finance"),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO directory_sources VALUES (?, ?, ?)",
        [
            ("directory:growth-manager", "v1", "maya"),
            ("directory:growth-remit", "v1", "maya"),
            ("directory:jules-approval", "v1", "maya"),
            ("directory:elena-old", "v1", "maya"),
            ("directory:priya-current", "v1", "maya"),
            ("directory:secret-duty", "v1", "restricted"),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO managers VALUES (?, ?, ?, ?, ?)",
        [
            ("growth", "marcus", "2025-01-01", None, "directory:growth-manager"),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO team_remits VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "growth-remit",
                "growth",
                "Campaign planning and launch approval review",
                "2025-01-01",
                None,
                "directory:growth-remit",
            ),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO responsibilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "jules-approval",
                "jules",
                "growth",
                "Reviewing campaign launch approvals",
                "reviewer",
                "2026-01-01",
                None,
                "2026-09-01",
                "directory:jules-approval",
            ),
            (
                "elena-old",
                "elena",
                "growth",
                "Managing campaign launch approvals",
                "operator",
                "2024-01-01",
                "2025-01-01",
                "2025-01-01",
                "directory:elena-old",
            ),
            (
                "eve-secret",
                "eve",
                "growth",
                "Campaign budget authorization",
                "owner",
                "2026-01-01",
                None,
                "2026-09-01",
                "directory:secret-duty",
            ),
        ],
    )
    records = [
        (
            "jira:MKT-482",
            "jira",
            "2026-08-10",
            "Finalize the retail campaign audience approval checklist before launch.",
            "maya",
            "v1",
        ),
        (
            "slack:retail-814",
            "slack",
            "2026-08-11",
            "I will coordinate the retail campaign launch review with channel owners.",
            "maya",
            "v1",
        ),
        (
            "jira:MKT-483",
            "jira",
            "2026-08-12",
            "Campaign performance report and post-launch metrics.",
            "maya",
            "v1",
        ),
        (
            "docs:campaign-review-2023",
            "document",
            "2023-05-10",
            "Retail campaign review and approval process for the previous team.",
            "maya",
            "v1",
        ),
        (
            "github:campaign-scheduler-76",
            "github",
            "2026-08-13",
            "Update integration between the campaign scheduler and the platform API.",
            "maya",
            "v1",
        ),
        (
            "slack:mention-55",
            "slack",
            "2026-07-04",
            "Someone mentioned Elena when discussing launch approval; no assignment was made.",
            "maya",
            "v1",
        ),
        (
            "jira:old-employee",
            "jira",
            "2025-02-01",
            "Retired employee owned the former launch flow.",
            "maya",
            "v1",
        ),
        (
            "docs:wallet-loyalty",
            "document",
            "2026-06-01",
            "Wallet loyalty points campaign promotion, unrelated to checkout payment processing.",
            "maya",
            "v1",
        ),
        (
            "slack:restricted-plan",
            "slack",
            "2026-08-11",
            "Eve Restricted is secretly responsible for the new AI campaign proposal.",
            "restricted",
            "v1",
        ),
        (
            "docs:restricted-budget",
            "document",
            "2026-07-01",
            "Confidential campaign budget owner Eve Restricted.",
            "restricted",
            "v1",
        ),
    ]
    db.executemany(
        "INSERT OR IGNORE INTO work_records VALUES (?, ?, ?, ?, ?, ?)", records
    )
    db.executemany(
        "INSERT OR IGNORE INTO work_links VALUES (?, ?, ?)",
        [
            ("jira:MKT-482", "nina", "assignee"),
            ("jira:MKT-482", "elena", "reporter"),
            ("slack:retail-814", "nina", "author"),
            ("jira:MKT-483", "elena", "assignee"),
            ("docs:campaign-review-2023", "priya", "author"),
            ("github:campaign-scheduler-76", "owen", "author"),
            ("slack:mention-55", "elena", "mention"),
            ("jira:old-employee", "former", "assignee"),
            ("docs:wallet-loyalty", "tara", "author"),
            ("slack:restricted-plan", "eve", "author"),
            ("docs:restricted-budget", "eve", "author"),
        ],
    )
    # Also repairs an older seed's visible index; this happens before requests.
    db.execute("DELETE FROM visible_fts")
    db.execute(
        "INSERT INTO visible_fts(record_id, text) SELECT id, text FROM work_records WHERE visibility='maya'"
    )
    db.commit()
