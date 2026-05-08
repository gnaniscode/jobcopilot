"""Generate a tailored cover letter + Q&A + pitch for one job."""
import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from jobcopilot.drafting.prompts import PROMPT_VERSION, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from jobcopilot.drafting.schemas import CoverLetterDraft
from jobcopilot.matching.schemas import MatchResult
from jobcopilot.resume.schemas import Resume
from jobcopilot.sources.schemas import Job


load_dotenv()

MODEL = "claude-haiku-4-5"

# Haiku 4.5 pricing (per million tokens)
INPUT_COST_PER_MTOK = 1.00
OUTPUT_COST_PER_MTOK = 5.00


def _build_tool_schema() -> dict[str, Any]:
    return {
        "name": "record_draft",
        "description": "Record the tailored application draft.",
        "input_schema": CoverLetterDraft.model_json_schema(),
    }


def _truncate_description(text: str | None, max_chars: int = 3500) -> str:
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


def draft_for_job(
    resume: Resume,
    job: Job,
    match: MatchResult,
    *,
    client: Anthropic | None = None,
) -> tuple[CoverLetterDraft, dict]:
    """Generate a complete application package for a single job."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")

    client = client or Anthropic(api_key=api_key)

    user_message = USER_PROMPT_TEMPLATE.format(
        resume_json=resume.model_dump_json(indent=2),
        company=job.company,
        title=job.title,
        location=job.location.raw,
        description=_truncate_description(job.description_text),
        score=match.score,
        tier=match.tier,
        one_line_reason=match.one_line_reason,
        strengths="; ".join(match.matching_strengths) or "(none listed)",
        gaps="; ".join(match.skill_gaps) or "(none listed)",
    )

    tool = _build_tool_schema()

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_draft"},
        messages=[{"role": "user", "content": user_message}],
    )

    if response.stop_reason != "tool_use":
        raise RuntimeError(f"Expected tool_use, got {response.stop_reason}")

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        raise RuntimeError("No tool_use block in response")

    draft = CoverLetterDraft.model_validate(tool_block.input)

    telemetry = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": calculate_cost(response.usage.input_tokens, response.usage.output_tokens),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
    }

    return draft, telemetry