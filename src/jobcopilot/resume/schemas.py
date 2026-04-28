"""Pydantic schemas for structured resume data."""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class Experience(BaseModel):
    """A single work experience entry."""
    company: str
    title: str
    location: Optional[str] = None
    start_date: Optional[str] = Field(None, description="YYYY-MM or 'Present'")
    end_date: Optional[str] = Field(None, description="YYYY-MM or 'Present'")
    description: Optional[str] = Field(None, description="Bullet points or paragraph summary")
    achievements: list[str] = Field(default_factory=list, description="Quantifiable wins")


class Education(BaseModel):
    """A single education entry."""
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[int] = None
    gpa: Optional[float] = None


class Project(BaseModel):
    """A notable project worth mentioning in applications."""
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class Resume(BaseModel):
    """Structured resume data extracted from PDF."""
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio_url: Optional[str] = None

    summary: Optional[str] = Field(None, description="Professional summary or objective")

    skills: list[str] = Field(default_factory=list, description="Technical and soft skills")
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)