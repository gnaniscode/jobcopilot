"""Streamlit dashboard for browsing matches and managing applications."""
import json
import re
import sqlite3
from pathlib import Path

import streamlit as st


DB_PATH = Path("data/jobcopilot.db")
DRAFTS_DIR = Path("drafts")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:60]


@st.cache_data(ttl=10)
def load_matches(min_score: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT j.dedup_key, j.company, j.title, j.location_raw, j.url,
               j.application_status,
               s.score, s.tier, s.result_json
        FROM match_scores s JOIN jobs j ON j.dedup_key = s.dedup_key
        WHERE s.model = ? AND s.score >= ?
        ORDER BY s.score DESC, j.first_seen_at DESC
        """,
        ("claude-haiku-4-5", min_score),
    ).fetchall()
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
        "by_status": by_status,
    }


def find_draft_path(score: int, company: str, title: str) -> Path | None:
    slug = slugify(f"{score}-{company}-{title}")
    candidate = DRAFTS_DIR / f"{slug}.md"
    if candidate.exists():
        return candidate
    # Fallback: scan for any draft starting with this score+company
    prefix = slugify(f"{score}-{company}")
    for f in DRAFTS_DIR.glob("*.md"):
        if f.stem.startswith(prefix):
            return f
    return None


# --- App ---
st.set_page_config(page_title="JobCopilot", layout="wide")
st.title("JobCopilot")

# Sidebar — stats and filters
stats = load_stats()
with st.sidebar:
    st.header("Stats")
    st.metric("Total jobs ingested", stats["total_jobs"])
    st.metric("Scored by Claude", stats["total_scored"])
    st.metric("Total API spend", f"${stats['total_cost']:.2f}")

    st.divider()
    st.subheader("Pipeline")
    for status in ["new", "saved", "applied", "interview", "rejected"]:
        st.write(f"**{status}**: {stats['by_status'].get(status, 0)}")

    st.divider()
    min_score = st.slider("Minimum score", 0, 100, 70, step=5)
    company_filter = st.text_input("Company contains", "")
    status_filter = st.multiselect(
        "Status",
        ["new", "saved", "applied", "interview", "rejected"],
        default=["new", "saved", "applied"],
    )

# Main area
matches = load_matches(min_score)
if company_filter:
    matches = [m for m in matches if company_filter.lower() in m["company"].lower()]
if status_filter:
    matches = [m for m in matches if (m["application_status"] or "new") in status_filter]

st.subheader(f"{len(matches)} matches")

for m in matches:
    status = m["application_status"] or "new"
    result = json.loads(m["result_json"])
    score_color = "🟢" if m["score"] >= 80 else ("🟡" if m["score"] >= 75 else "🟠")

    with st.expander(
        f"{score_color} **{m['score']}** — [{m['company']}] {m['title']}  ·  {m['location_raw']}  ·  *{status}*"
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

        # Draft viewer
        draft_path = find_draft_path(m["score"], m["company"], m["title"])
        if draft_path:
            with st.expander("📝 View draft"):
                st.markdown(draft_path.read_text())
        else:
            st.caption("_No draft generated for this job yet (score < 75 threshold)._")