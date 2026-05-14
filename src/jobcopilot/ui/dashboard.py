"""Streamlit dashboard for browsing matches and managing applications."""
import json
import os
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

# Demo mode: when JOBCOPILOT_DEMO=1, use seeded sample data instead of real data.
# Streamlit Cloud sets this in app settings; locally you stay in normal mode.
DEMO_MODE = os.getenv("JOBCOPILOT_DEMO", "").lower() in ("1", "true", "yes")

if DEMO_MODE:
    DB_PATH = Path("demo/jobcopilot.db")
    DRAFTS_DIR = Path("demo/drafts")
else:
    DB_PATH = Path("data/jobcopilot.db")
    DRAFTS_DIR = Path("drafts")

st.title("JobCopilot")
if DEMO_MODE:
    st.info(
        "🎭 **Demo Mode** — This is a public demo with sample data. "
        "The fictional candidate is a senior GenAI engineer; jobs are sample postings "
        "to showcase how the matching engine works. "
        "Source code: [github.com/gnaniscode/jobcopilot](https://github.com/gnaniscode/jobcopilot)"
    )

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:60]


@st.cache_data(ttl=10)
def load_matches(min_score: int, max_results: int, days_back: int | None) -> list[dict]:
    """Return matches sorted by score, optionally filtered by recency.

    days_back=None means no time filter (all jobs).
    days_back=1 means jobs first seen in the last 24 hours.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT j.dedup_key, j.company, j.title, j.location_raw, j.url,
               j.application_status, j.first_seen_at, j.posted_at,
               s.score, s.tier, s.result_json
        FROM match_scores s
        JOIN jobs j ON j.dedup_key = s.dedup_key
        WHERE s.model = ? AND s.score >= ?
    """
    params: list = ["claude-haiku-4-5", min_score]

    if days_back is not None:
        # Use first_seen_at — when WE first saw the job, more reliable
        # than posted_at which sources sometimes don't populate
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        query += " AND j.first_seen_at >= ?"
        params.append(cutoff)

    query += " ORDER BY s.score DESC, j.first_seen_at DESC LIMIT ?"
    params.append(max_results)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_status(dedup_key: str, status: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE jobs SET application_status = ? WHERE dedup_key = ?",
        (status, dedup_key),
    )
    conn.commit()
    conn.close()
    st.cache_data.clear()


@st.cache_data(ttl=30)
def load_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    total_scored = conn.execute(
        "SELECT COUNT(*) FROM match_scores WHERE model != 'prefilter'"
    ).fetchone()[0]
    total_cost = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM match_scores"
    ).fetchone()[0]
    last_24h = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= datetime('now', '-1 day')"
    ).fetchone()[0]
    by_status = dict(conn.execute(
        "SELECT application_status, COUNT(*) FROM jobs "
        "WHERE dedup_key IN (SELECT dedup_key FROM match_scores WHERE score >= 70 AND model != 'prefilter') "
        "GROUP BY application_status"
    ).fetchall())
    conn.close()
    return {
        "total_jobs": total_jobs,
        "total_scored": total_scored,
        "total_cost": total_cost,
        "last_24h_jobs": last_24h,
        "by_status": by_status,
    }


def find_draft_path(score: int, company: str, title: str) -> Path | None:
    slug = slugify(f"{score}-{company}-{title}")
    candidate = DRAFTS_DIR / f"{slug}.md"
    if candidate.exists():
        return candidate
    prefix = slugify(f"{score}-{company}")
    for f in DRAFTS_DIR.glob("*.md"):
        if f.stem.startswith(prefix):
            return f
    return None


def generate_draft_for(dedup_key: str) -> tuple[bool, str]:
    """Generate a cover letter for a single job. Returns (success, message)."""
    try:
        from jobcopilot.drafting.cover_letter import draft_for_job
        from jobcopilot.matching.schemas import MatchResult
        from jobcopilot.resume.parser import load_or_parse_resume
        from jobcopilot.sources.schemas import Job, JobLocation

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT j.*, s.score, s.tier, s.result_json
            FROM match_scores s JOIN jobs j ON j.dedup_key = s.dedup_key
            WHERE j.dedup_key = ? AND s.model = 'claude-haiku-4-5'
            """,
            (dedup_key,),
        ).fetchone()
        conn.close()

        if row is None:
            return False, "Job not found"

        resume = load_or_parse_resume(Path("data/resume.docx"))
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
        draft, telem = draft_for_job(resume, job, match)

        from jobcopilot.drafting.run import _render_markdown
        DRAFTS_DIR.mkdir(exist_ok=True)
        slug = slugify(f"{row['score']}-{job.company}-{job.title}")
        outpath = DRAFTS_DIR / f"{slug}.md"
        outpath.write_text(_render_markdown(job, row["score"], draft))

        return True, f"Saved to {outpath.name} (cost: ${telem['cost_usd']:.4f})"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# --- App ---
st.set_page_config(page_title="JobCopilot", layout="wide")
st.title("JobCopilot")

# Sidebar
stats = load_stats()
with st.sidebar:
    st.header("Stats")
    st.metric("Total jobs ingested", stats["total_jobs"])
    st.metric("Jobs added in last 24h", stats["last_24h_jobs"])
    st.metric("Scored by Claude", stats["total_scored"])
    st.metric("Total API spend", f"${stats['total_cost']:.2f}")

    st.divider()
    st.subheader("Pipeline")
    for status in ["new", "saved", "applied", "interview", "rejected"]:
        st.write(f"**{status}**: {stats['by_status'].get(status, 0)}")

    st.divider()
    st.subheader("Filters")
    time_window = st.selectbox(
        "Time window",
        ["All time", "Last 24 hours", "Last 3 days", "Last 7 days", "Last 30 days"],
        index=0,
    )
    days_back_map = {
        "All time": None,
        "Last 24 hours": 1,
        "Last 3 days": 3,
        "Last 7 days": 7,
        "Last 30 days": 30,
    }
    days_back = days_back_map[time_window]

    min_score = st.slider("Minimum score", 0, 100, 70, step=5)
    max_results = st.slider("Max results", 10, 200, 50, step=10)
    company_filter = st.text_input("Company contains", "")
    status_filter = st.multiselect(
        "Status",
        ["new", "saved", "applied", "interview", "rejected"],
        default=["new", "saved", "applied"],
    )

# Main area
matches = load_matches(min_score, max_results, days_back)
if company_filter:
    matches = [m for m in matches if company_filter.lower() in m["company"].lower()]
if status_filter:
    matches = [m for m in matches if (m["application_status"] or "new") in status_filter]

# Header summary
header_parts = [f"**{len(matches)} matches**"]
if days_back is not None:
    header_parts.append(f"posted in {time_window.lower()}")
header_parts.append(f"sorted by score (top {max_results})")
st.markdown(" • ".join(header_parts))
st.divider()

if not matches:
    st.info(
        "No jobs match the current filters. "
        "Try widening the time window or lowering the minimum score."
    )

for m in matches:
    status = m["application_status"] or "new"
    result = json.loads(m["result_json"])
    score_color = "🟢" if m["score"] >= 80 else ("🟡" if m["score"] >= 75 else "🟠")

    # Show how recent the job is
    try:
        seen_at = datetime.fromisoformat(m["first_seen_at"])
        age_hours = (datetime.utcnow() - seen_at).total_seconds() / 3600
        if age_hours < 24:
            age_label = f"{int(age_hours)}h ago"
        elif age_hours < 24 * 7:
            age_label = f"{int(age_hours / 24)}d ago"
        else:
            age_label = seen_at.strftime("%b %d")
    except Exception:
        age_label = "—"

    with st.expander(
        f"{score_color} **{m['score']}** — [{m['company']}] {m['title']}  "
        f"·  {m['location_raw']}  ·  *{status}*  ·  {age_label}"
    ):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**Why this score:** {result.get('one_line_reason', '')}")

            if result.get("matching_strengths"):
                st.markdown("**Strengths**")
                for s in result["matching_strengths"]:
                    st.markdown(f"- {s}")

            if result.get("skill_gaps"):
                st.markdown("**Gaps**")
                for g in result["skill_gaps"]:
                    st.markdown(f"- {g}")

            if result.get("red_flags"):
                st.markdown("**Red flags**")
                for r in result["red_flags"]:
                    st.markdown(f"- {r}")

            st.markdown(f"[Open job posting ↗]({m['url']})")

        with col2:
            st.markdown("**Mark as:**")
            cols = st.columns(2)
            for i, new_status in enumerate(["saved", "applied", "interview", "rejected"]):
                with cols[i % 2]:
                    if st.button(
                        new_status.capitalize(),
                        key=f"{m['dedup_key']}-{new_status}",
                        use_container_width=True,
                    ):
                        update_status(m["dedup_key"], new_status)
                        st.rerun()

        # Draft viewer / generator
        draft_path = find_draft_path(m["score"], m["company"], m["title"])
        if draft_path:
            with st.expander("📝 View draft"):
                st.markdown(draft_path.read_text())
        else:
            if DEMO_MODE:
                st.caption(
                    "_Cover letter generation is disabled in demo mode. "
                    "Clone the repo and run locally to use this feature._"
                )
            else:
                if st.button(
                    "✨ Generate cover letter draft (~$0.01)",
                    key=f"{m['dedup_key']}-generate",
                ):
                    with st.spinner("Calling Claude to draft your cover letter..."):
                        ok, msg = generate_draft_for(m["dedup_key"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(f"Failed: {msg}")