"""Permission-isolated work-trace search and deterministic directory candidacy."""

from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from threading import Lock

from workbot.storage import (
    current_and_visible,
    current_managers,
    visible_fts_matches,
    visible_index_version,
    visible_record,
)

log = logging.getLogger(__name__)
COLLECTION = "maya_visible_work"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_SEMANTIC_SCORE = 0.38  # Initial small-corpus threshold, not a measured one.
CHANNEL_TOP = 3  # Single-channel hits kept per search intent.
_embedder = None
_embedder_lock = Lock()
_stop = {
    "the",
    "and",
    "that",
    "with",
    "what",
    "which",
    "this",
    "from",
    "about",
    "for",
    "who",
    "can",
    "will",
    "should",
    "into",
    "our",
    "how",
    "are",
    "them",
    "their",
    "find",
    "current",
    "process",
    "review",
}


def embed(text: str) -> list[float]:
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                from fastembed import TextEmbedding

                _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return next(_embedder.embed([text])).tolist()


def index_visible_records(db, url: str, client=None, embed_fn=None) -> int:
    from qdrant_client import QdrantClient, models

    records = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM work_records WHERE visibility='maya' ORDER BY id"
        )
    ]
    client = client or QdrantClient(url=url, timeout=20)
    embed_fn = embed_fn or embed
    vectors = [embed_fn(item["text"]) for item in records]
    if not vectors:
        raise ValueError("There are no visible records to index")
    # The old marker may still match unchanged SQLite rows even if rebuilding
    # Qdrant fails after deleting its collection. Invalidate it first.
    db.execute("DELETE FROM index_meta WHERE key='visible_vector'")
    db.commit()
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(
            size=len(vectors[0]), distance=models.Distance.COSINE
        ),
    )
    client.upsert(
        COLLECTION,
        points=[
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, item["id"])),
                vector=vector,
                payload={"record_id": item["id"], "visibility": "maya"},
            )
            for item, vector in zip(records, vectors, strict=True)
        ],
        wait=True,
    )
    db.execute(
        "INSERT OR REPLACE INTO index_meta(key, value) VALUES ('visible_vector', ?)",
        (visible_index_version(db),),
    )
    db.commit()
    return len(records)


def keywords(text: str) -> list[str]:
    return list(
        dict.fromkeys(
            term
            for term in re.findall(r"[a-z0-9]{3,}", text.lower())
            if term not in _stop
        )
    )[:12]


class SetupError(RuntimeError):
    """Search cannot run yet. Message and command are setup advice safe to show."""

    def __init__(self, message: str, command: str):
        super().__init__(message)
        self.command = command


def _index_is_current(db) -> bool:
    version = db.execute(
        "SELECT value FROM index_meta WHERE key='visible_vector'"
    ).fetchone()
    return bool(
        version
        and version["value"] == visible_index_version(db)
        and visible_fts_matches(db)
    )


class Searcher:
    def __init__(self, url: str, client=None, embed_fn=None):
        self.url = url
        self.client = client
        self.embed_fn = embed_fn or embed
        self._client_lock = Lock()

    def _qdrant(self):
        from qdrant_client import QdrantClient

        if self.client is None:
            with self._client_lock:
                if self.client is None:
                    self.client = QdrantClient(url=self.url, timeout=15)
        return self.client

    def check(self, db) -> None:
        """Raise SetupError before a request starts if search cannot answer it."""
        reseed = SetupError(
            "The search data is missing or out of date. Load it, then try again.",
            "python -m workbot.seed",
        )
        # Qdrant first: seeding needs it too, so it is the first step to fix.
        try:
            indexed = self._qdrant().collection_exists(COLLECTION)
        except Exception as exc:  # noqa: BLE001 — any client failure means Qdrant is unusable.
            log.warning("search_setup_check_failed type=%s", type(exc).__name__)
            raise SetupError(
                "The Qdrant search service did not answer. Start it, then try again.",
                "docker compose up -d",
            ) from None
        if not indexed or not _index_is_current(db):
            raise reseed

    def records(self, db, intents: list[dict], limit: int = 8) -> list[dict]:
        from qdrant_client import models

        if not _index_is_current(db):
            raise RuntimeError("Visible vector index needs reseeding")
        client = self._qdrant()
        scores: dict[str, float] = defaultdict(float)
        channels: dict[str, set[str]] = defaultdict(set)
        for intent in intents:
            ranked: dict[str, list[str]] = {"bm25": [], "qdrant": []}
            terms = keywords(intent["keyword"])
            if terms:
                query = " OR ".join(f'"{term}"' for term in terms)
                rows = db.execute(
                    "SELECT record_id FROM visible_fts WHERE visible_fts MATCH ? ORDER BY bm25(visible_fts), record_id LIMIT 12",
                    (query,),
                ).fetchall()
                ranked["bm25"] = [row["record_id"] for row in rows]
            result = client.query_points(
                COLLECTION,
                query=self.embed_fn(intent["semantic"]),
                limit=12,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="visibility", match=models.MatchValue(value="maya")
                        )
                    ]
                ),
                with_payload=True,
            )
            ranked["qdrant"] = [
                point.payload["record_id"]
                for point in result.points
                if point.score >= MIN_SEMANTIC_SCORE
            ]
            # An OR keyword query matches on any single shared word, so its tail is
            # mostly noise. Keep what both channels agree on plus each channel's
            # best few, which protects a strong hit only one channel can see.
            keep = (
                set(ranked["bm25"]) & set(ranked["qdrant"])
                | set(ranked["bm25"][:CHANNEL_TOP])
                | set(ranked["qdrant"][:CHANNEL_TOP])
            )
            for channel, ids in ranked.items():
                for rank, rid in enumerate(ids):
                    if rid in keep:
                        scores[rid] += 1 / (60 + rank + 1)
                        channels[rid].add(channel)
        found = []
        for rid in sorted(scores, key=lambda item: (-scores[item], item)):
            # A revoked source must not be read, shown, or passed to the model.
            record = visible_record(db, rid)
            if record:
                record["retrieval_channels"] = sorted(channels[rid])
                found.append(record)
            if len(found) == limit:
                break
        return found


def _candidate(person) -> dict:
    # Every caller reads the person within the area's own unit or by work link, so
    # the person's unit is the one the audit later looks their evidence up in.
    return {
        "person_id": person["id"],
        "name": person["name"],
        "title": person["title"],
        "org_id": person["org_id"],
        "evidence": [],
    }


def candidate_pool(db, area: dict, records: list[dict]) -> dict:
    """No vector similarity over directory people; keyword match grants candidacy only."""
    candidates: dict[str, dict] = {}
    for rank, record in enumerate(records):
        # Re-read from the permissioned store, never trust a stale search payload.
        fresh = visible_record(db, record["id"])
        if (
            not fresh
            or fresh["version"] != record["version"]
            or fresh["text"] != record["text"]
        ):
            raise RuntimeError("Search result changed before candidate evaluation")
        record = fresh
        links = db.execute(
            "SELECT person_id, relation FROM work_links WHERE record_id=? ORDER BY person_id, relation",
            (record["id"],),
        ).fetchall()
        for link in links:
            row = db.execute(
                "SELECT * FROM people WHERE id=? AND active=1", (link["person_id"],)
            ).fetchone()
            if row:
                candidates.setdefault(row["id"], _candidate(row))["evidence"].append(
                    {
                        "id": record["id"],
                        "kind": record["kind"],
                        "date": record["occurred_at"],
                        "relation": link["relation"],
                        "text": record["text"],
                        "rank": rank,
                    }
                )
    strength = {
        "assignee": 0,
        "author": 0,
        "contributor": 0,
        "reporter": 1,
        "mention": 2,
    }

    # Records arrive in fused retrieval order. Keep the people tied most strongly
    # to the best-ranked records; a mention alone can never support a role, so it
    # does not take one of the ten places.
    def best(item: dict) -> tuple[int, int]:
        return min(
            (strength.get(e["relation"], 3), e["rank"]) for e in item["evidence"]
        )

    work = sorted(
        (item for item in candidates.values() if best(item)[0] < 2),
        key=lambda item: (*best(item), item["person_id"]),
    )[:10]
    for item in work:
        for evidence in item["evidence"]:
            del evidence["rank"]
    people = {item["person_id"]: item for item in work}
    terms = set(keywords(" ".join(i["keyword"] for i in area["search_intents"])))
    org = area["org_unit_id"]
    org_options = []
    for row in db.execute(
        "SELECT * FROM people WHERE org_id=? AND active=1 ORDER BY id", (org,)
    ):
        responsibility_evidence = []
        for resp in db.execute(
            "SELECT * FROM responsibilities WHERE person_id=? AND org_id=? ORDER BY id",
            (row["id"], org),
        ):
            if current_and_visible(db, resp):
                responsibility_evidence.append(
                    {
                        "id": resp["source_id"],
                        "kind": "responsibility",
                        "relation": resp["relation"],
                        "date": resp["verified_at"],
                        "text": resp["scope"],
                    }
                )
        title_match = bool(terms & set(keywords(row["title"])))
        duty_match = any(
            terms & set(keywords(e["text"])) for e in responsibility_evidence
        )
        # A title alone is not citeable evidence. In particular, it must not
        # expose someone whose only duty source is restricted to the model.
        if responsibility_evidence and (title_match or duty_match):
            org_options.append(
                (0 if duty_match else 1, row["id"], dict(row), responsibility_evidence)
            )
    for _, pid, row, evidence in sorted(org_options)[:11]:
        item = people.setdefault(pid, _candidate(row))
        item["evidence"].extend(
            e
            for e in evidence
            if e["id"] not in {old["id"] for old in item["evidence"]}
        )
    # Reserve a separate slot for a manager, conditional on an actual, visible team remit.
    remits = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM team_remits WHERE org_id=? ORDER BY id", (org,)
        )
        if current_and_visible(db, row) and terms & set(keywords(row["scope"]))
    ]
    managers = current_managers(db, org)
    if remits and len({row["id"] for _, row in managers}) == 1:
        manager, row = managers[0]
        item = people.setdefault(row["id"], _candidate(row))
        item["evidence"].extend(
            [
                {
                    "id": manager["source_id"],
                    "kind": "manager",
                    "relation": "manages",
                    "date": manager["valid_from"],
                    "text": "Currently manages " + org,
                },
                *(
                    {
                        "id": remit["source_id"],
                        "kind": "remit",
                        "relation": "team_scope",
                        "date": remit["valid_from"],
                        "text": remit["scope"],
                    }
                    for remit in remits
                ),
            ]
        )
    return {"people": list(people.values()), "no_visible_work_trace": not records}
