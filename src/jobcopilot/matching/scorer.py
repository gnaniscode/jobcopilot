"""Score a single job against the resume using Claude with tool use + caching."""
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from jobcopilot.matching.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, PROMPT_VERSION
from jobcopilot.matching.schemas import MatchResult
from jobcopilot.resume.schemas import Resume
from jobcopilot.sources.schemas import Job


load_dotenv()

MODEL = "claude-haiku-4-5"

# Haiku 4.5 pricing (per million tokens, approximate)
INPUT_COST_PER_MTOK = 1.00
OUTPUT_COST_PER_MTOK = 5.00
CACHE_WRITE_COST_PER_MTOK = 1.25
CACHE_READ_COST_PER_MTOK = 0.10


def _build_tool_schema() -> dict[str, Any]:
    schema = MatchResult.model_json_schema()
    return {
        "name": "record_match",
        "description": "Record the structured match assessment.",
        "input_schema": schema,
    }


def _truncate_description(text: str | None, max_chars: int = 2000) -> str:
    if not text:
        return "(No description provided)"
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * INPUT_COST_PER_MTOK
        + output_tokens / 1_000_000 * OUTPUT_COST_PER_MTOK
    )


def calculate_cost_with_cache(
    standard_input: int, cache_create: int, cache_read: int, output: int,
) -> float:
    return (
        standard_input / 1_000_000 * INPUT_COST_PER_MTOK
        + cache_create / 1_000_000 * CACHE_WRITE_COST_PER_MTOK
        + cache_read / 1_000_000 * CACHE_READ_COST_PER_MTOK
        + output / 1_000_000 * OUTPUT_COST_PER_MTOK
    )


def _make_call(
    client: Anthropic,
    cached_system: list,
    user_message: str,
    tool: dict,
):
    """Single API call. Returns (response, parsed_result_or_None, error_or_None)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=cached_system,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_match"},
        messages=[{"role": "user", "content": user_message}],
    )
    if response.stop_reason != "tool_use":
        return response, None, RuntimeError(
            f"Expected tool_use, got {response.stop_reason}"
        )
    block = next((b for b in response.content if b.type == "tool_use"), None)
    if block is None:
        return response, None, RuntimeError("No tool_use block in response")
    try:
        result = MatchResult.model_validate(block.input)
        return response, result, None
    except Exception as e:
        return response, None, e


def _usage_dict(response) -> dict:
    return {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
    }


def score_job(resume: Resume, job: Job, *, client: Anthropic | None = None) -> tuple[MatchResult, dict]:
    """Score a single job. Returns (result, telemetry_dict).

    Caching: the system prompt + resume are marked as ephemeral cache.
    Retry: if Haiku produces a malformed tool call, retry once.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")

    client = client or Anthropic(api_key=api_key)

    cached_system = [
        {"type": "text", "text": SYSTEM_PROMPT},
        {
            "type": "text",
            "text": f"\n\n# CANDIDATE RESUME (structured)\n{resume.model_dump_json(indent=2)}",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    user_message = (
        f"Assess this candidate-job match.\n\n"
        f"# JOB POSTING\n"
        f"Company: {job.company}\n"
        f"Title: {job.title}\n"
        f"Location: {job.location.raw}\n"
        f"Department: {job.department or '(unspecified)'}\n\n"
        f"Description:\n{_truncate_description(job.description_text)}\n\n"
        f"Score this match using the record_match tool. "
        f"All list fields must be plain JSON arrays of strings."
    )

    tool = _build_tool_schema()

    # Attempt 1
    response, result, err = _make_call(client, cached_system, user_message, tool)
    usage = _usage_dict(response)

    # Retry once if validation failed
    if err is not None:
        response2, result, err2 = _make_call(client, cached_system, user_message, tool)
        usage2 = _usage_dict(response2)
        # Sum the usage from both attempts so cost is honestly tracked
        for k in usage:
            usage[k] += usage2[k]
        if err2 is not None:
            raise err2  # both attempts failed, give up

    telemetry = {
        "input_tokens": usage["input_tokens"],
        "cache_read_tokens": usage["cache_read_tokens"],
        "cache_creation_tokens": usage["cache_creation_tokens"],
        "output_tokens": usage["output_tokens"],
        "cost_usd": calculate_cost_with_cache(
            usage["input_tokens"],
            usage["cache_creation_tokens"],
            usage["cache_read_tokens"],
            usage["output_tokens"],
        ),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
    }

    return result, telemetry


if __name__ == "__main__":
    """Quick smoke test: score one Anthropic Applied AI job."""
    import sqlite3
    from datetime import datetime
    from pathlib import Path

    from jobcopilot.resume.parser import load_or_parse_resume
    from jobcopilot.sources.schemas import Job, JobLocation

    resume = load_or_parse_resume(Path("data/resume.docx"))

    conn = sqlite3.connect("data/jobcopilot.db")
    row = conn.execute(
        """
        SELECT dedup_key, source, source_id, company, title,
               location_raw, remote, country, url,
               description, department, posted_at
        FROM jobs
        WHERE company='anthropic' AND title LIKE '%Applied AI%'
        LIMIT 1
        """
    ).fetchone()

    if row is None:
        print("No Applied AI job found. Run fetch_all first.")
        raise SystemExit(1)

    job = Job(
        source=row[1], source_id=row[2], company=row[3], title=row[4],
        location=JobLocation(raw=row[5], remote=bool(row[6]), country=row[7]),
        url=row[8], description_text=row[9], department=row[10],
        posted_at=datetime.fromisoformat(row[11]) if row[11] else None,
    )

    print(f"Scoring: [{job.company}] {job.title}")
    print(f"  -> {job.url}\n")

    result, telemetry = score_job(resume, job)

    print(f"Score: {result.score}/100  ({result.tier})")
    print(f"One-liner: {result.one_line_reason}\n")
    print("Strengths:")
    for s in result.matching_strengths:
        print(f"  + {s}")
    if result.skill_gaps:
        print("Gaps:")
        for g in result.skill_gaps:
            print(f"  - {g}")
    if result.red_flags:
        print("Red flags:")
        for r in result.red_flags:
            print(f"  ! {r}")
    print(
        f"\nCost: ${telemetry['cost_usd']:.4f}  "
        f"({telemetry['input_tokens']} in / "
        f"{telemetry['cache_creation_tokens']} cache-write / "
        f"{telemetry['cache_read_tokens']} cache-read / "
        f"{telemetry['output_tokens']} out)"
    )
