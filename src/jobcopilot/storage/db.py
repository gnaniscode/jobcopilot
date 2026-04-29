"""Async SQLite storage for jobs and match scores."""
from datetime import datetime
from pathlib import Path

import aiosqlite

from jobcopilot.sources.schemas import Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    dedup_key       TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    location_raw    TEXT NOT NULL,
    remote          INTEGER NOT NULL,
    country         TEXT,
    url             TEXT NOT NULL,
    description     TEXT,
    department      TEXT,
    posted_at       TEXT,
    fetched_at      TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_company   ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at);

CREATE TABLE IF NOT EXISTS match_scores (
    dedup_key       TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    model           TEXT NOT NULL,
    score           INTEGER NOT NULL,
    tier            TEXT NOT NULL,
    result_json     TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL,
    cost_usd        REAL    NOT NULL,
    scored_at       TEXT    NOT NULL,
    PRIMARY KEY (dedup_key, prompt_version, model),
    FOREIGN KEY (dedup_key) REFERENCES jobs(dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_scores_score ON match_scores(score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_tier  ON match_scores(tier);
"""


class JobStore:
    def __init__(self, db_path: Path = Path("data/jobcopilot.db")):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def upsert(self, job: Job) -> bool:
        """Insert a job, or no-op if we've seen it before. Returns True if new."""
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM jobs WHERE dedup_key = ?", (job.dedup_key,)
            )
            exists = await cursor.fetchone() is not None
            if exists:
                await db.execute(
                    "UPDATE jobs SET fetched_at = ? WHERE dedup_key = ?",
                    (now, job.dedup_key),
                )
                await db.commit()
                return False

            await db.execute(
                """
                INSERT INTO jobs (
                    dedup_key, source, source_id, company, title,
                    location_raw, remote, country, url,
                    description, department,
                    posted_at, fetched_at, first_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.dedup_key,
                    job.source,
                    job.source_id,
                    job.company,
                    job.title,
                    job.location.raw,
                    int(job.location.remote),
                    job.location.country,
                    str(job.url),
                    job.description_text,
                    job.department,
                    job.posted_at.isoformat() if job.posted_at else None,
                    now,
                    now,
                ),
            )
            await db.commit()
            return True

    async def count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM jobs")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def has_score(self, dedup_key: str, prompt_version: str, model: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM match_scores WHERE dedup_key=? AND prompt_version=? AND model=?",
                (dedup_key, prompt_version, model),
            )
            return await cursor.fetchone() is not None

    async def save_score(
        self,
        *,
        dedup_key: str,
        prompt_version: str,
        model: str,
        score: int,
        tier: str,
        result_json: str,
        input_tokens: int,
        cache_read_tokens: int,
        cache_creation_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO match_scores (
                    dedup_key, prompt_version, model,
                    score, tier, result_json,
                    input_tokens, cache_read_tokens, cache_creation_tokens, output_tokens,
                    cost_usd, scored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dedup_key, prompt_version, model,
                    score, tier, result_json,
                    input_tokens, cache_read_tokens, cache_creation_tokens, output_tokens,
                    cost_usd, now,
                ),
            )
            await db.commit()

    async def list_unscored_jobs(self, prompt_version: str, model: str) -> list[dict]:
        """Return all jobs that haven't been scored under this (prompt_version, model)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT j.*
                FROM jobs j
                LEFT JOIN match_scores s
                  ON s.dedup_key = j.dedup_key
                 AND s.prompt_version = ?
                 AND s.model = ?
                WHERE s.dedup_key IS NULL
                ORDER BY j.first_seen_at DESC
                """,
                (prompt_version, model),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]