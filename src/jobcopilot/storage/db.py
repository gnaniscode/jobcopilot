"""Async SQLite storage for jobs.

Schema is intentionally minimal for now. We'll add columns
(score, draft, application_status) as later phases need them.
"""
from datetime import datetime
from pathlib import Path

import aiosqlite

from jobcopilot.sources.schemas import Job, JobLocation


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
                # Update fetched_at so we know it's still active
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