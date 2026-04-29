"""Normalized job schemas — what every source must produce."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


JobSourceName = Literal["greenhouse", "lever"]


class JobLocation(BaseModel):
    """A job's location — normalized."""
    raw: str = Field(description="Original location string from the source")
    remote: bool = False
    country: Optional[str] = None


class Job(BaseModel):
    """A job posting normalized across all sources.

    The (source, source_id) pair must be globally unique — that's the dedup key.
    """
    source: JobSourceName
    source_id: str = Field(description="ID from the source system; unique within that source")
    company: str
    title: str
    location: JobLocation
    url: HttpUrl = Field(description="Public application URL")
    description_html: Optional[str] = None
    description_text: Optional[str] = None
    department: Optional[str] = None
    posted_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def dedup_key(self) -> str:
        return f"{self.source}:{self.source_id}"