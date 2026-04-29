"""Schemas for job match scoring."""
from typing import Literal
from pydantic import BaseModel, Field


FitTier = Literal["strong_match", "good_match", "stretch", "poor_match", "skip"]


class MatchResult(BaseModel):
    """Claude's structured assessment of a job vs the resume."""

    score: int = Field(ge=0, le=100, description="Overall fit score 0-100")
    tier: FitTier = Field(description="Categorical recommendation")

    matching_strengths: list[str] = Field(
        description="Specific resume points that align with the role (3-6 bullets)"
    )
    skill_gaps: list[str] = Field(
        default_factory=list,
        description="Required/preferred skills the candidate lacks (empty if none)",
    )
    seniority_fit: str = Field(
        description="One sentence: does the candidate's level match the role?"
    )
    location_fit: str = Field(
        description="One sentence on location/remote alignment"
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Concerns: visa, security clearance, on-call, domain mismatch, etc.",
    )

    one_line_reason: str = Field(
        description="Single sentence summary the candidate could glance at"
    )


class ScoringRecord(BaseModel):
    """What we persist for each scored job."""

    dedup_key: str
    score: int
    tier: FitTier
    result_json: str  # full MatchResult serialized
    prompt_version: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    scored_at: str  # ISO timestamp