"""Schemas for application drafts (cover letter + Q&A + pitch)."""
from pydantic import BaseModel, Field


class CoverLetterDraft(BaseModel):
    """A complete tailored application draft for one job."""

    cover_letter: str = Field(
        description="Full cover letter, 250-380 words, ready to paste"
    )

    pitch: str = Field(
        description="3-sentence elevator pitch, useful for LinkedIn outreach or recruiter intro"
    )

    why_this_company: str = Field(
        description="2-3 sentence answer to 'why do you want to work at <company>?'"
    )

    why_this_role: str = Field(
        description="2-3 sentence answer to 'why this specific role?'"
    )

    proudest_project: str = Field(
        description="3-4 sentence answer about a relevant project from the resume "
        "with specific tech and impact"
    )