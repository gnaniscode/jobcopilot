"""Generate cover letter drafts for all top-matched jobs."""
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from jobcopilot.drafting.cover_letter import draft_for_job
from jobcopilot.matching.schemas import MatchResult
from jobcopilot.resume.parser import load_or_parse_resume
from jobcopilot.sources.schemas import Job, JobLocation


SCORE_THRESHOLD = 75  # only draft for jobs scoring this or higher
DRAFTS_DIR = Path("drafts")


def _slugify(s: str) -> str:
    """Make a safe filename slug."""
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:60]


def _render_markdown(job: Job, score: int, draft) -> str:
    """Format the draft as a readable markdown file."""
    return f"""# {job.title} — {job.company}

**Match score:** {score}/100
**Location:** {job.location.raw}
**URL:** {job.url}

---

## Cover Letter

{draft.cover_letter}

---

## 30-Second Pitch

{draft.pitch}

---

## Common Application Questions

### Why this company?

{draft.why_this_company}

### Why this role?

{draft.why_this_role}

### A project you're proud of

{draft.proudest_project}

---

*Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} — review and personalize before sending.*
"""


def main() -> None:
    DRAFTS_DIR.mkdir(exist_ok=True)
    resume = load_or_parse_resume(Path("data/resume.docx"))

    conn = sqlite3.connect("data/jobcopilot.db")
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT j.*, s.score, s.tier, s.result_json
        FROM match_scores s JOIN jobs j ON j.dedup_key = s.dedup_key
        WHERE s.model = ? AND s.score >= ?
        ORDER BY s.score DESC, j.first_seen_at DESC
        """,
        ("claude-haiku-4-5", SCORE_THRESHOLD),
    ).fetchall()

    print(f"Found {len(rows)} jobs scoring >= {SCORE_THRESHOLD}.\n")

    if not rows:
        print("Nothing to draft. Lower SCORE_THRESHOLD or run more scoring.")
        return

    total_cost = 0.0
    written = 0
    skipped = 0

    for i, row in enumerate(rows, 1):
        job = Job(
            source=row["source"], source_id=row["source_id"],
            company=row["company"], title=row["title"],
            location=JobLocation(
                raw=row["location_raw"], remote=bool(row["remote"]),
                country=row["country"],
            ),
            url=row["url"], description_text=row["description"],
            department=row["department"],
            posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
        )
        match = MatchResult.model_validate_json(row["result_json"])

        slug = _slugify(f"{row['score']}-{job.company}-{job.title}")
        outpath = DRAFTS_DIR / f"{slug}.md"

        if outpath.exists():
            skipped += 1
            continue

        try:
            draft, telem = draft_for_job(resume, job, match)
            outpath.write_text(_render_markdown(job, row["score"], draft))
            total_cost += telem["cost_usd"]
            written += 1
            print(
                f"  [{i:2d}/{len(rows)}] ${total_cost:5.3f}  "
                f"[{job.company}] {job.title[:55]} -> {outpath.name}"
            )
        except Exception as e:
            print(f"  ✗ {job.dedup_key}: {type(e).__name__}: {str(e)[:120]}")

    print(
        f"\n  Done. Wrote {written} drafts, skipped {skipped} existing, "
        f"total cost ${total_cost:.4f}"
    )
    print(f"  Open {DRAFTS_DIR}/ to review.")


if __name__ == "__main__":
    main()