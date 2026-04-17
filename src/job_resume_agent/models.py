from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class JobPosting(BaseModel):
    title: str
    company: str
    location: str = "Unknown"
    url: str | None = None
    description: str
    source: str
    posted_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str
    role: str
    achievements: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    name: str
    title: str
    location: str
    email: str
    phone: str
    linkedin: str
    summary: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    preferred_keywords: list[str] = Field(default_factory=list)


class JobMatch(BaseModel):
    job: JobPosting
    score: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    rationale: str


class ResumeDraft(BaseModel):
    headline: str
    summary: list[str]
    skills: list[str]
    selected_experience: list[ExperienceItem]
    tailored_bullets: list[str]
    target_job_title: str
    target_company: str


class WorkflowArtifacts(BaseModel):
    jobs: list[JobPosting]
    matches: list[JobMatch]
    resume: ResumeDraft
    notes: str
    report: str


@dataclass
class AgentStepResult:
    name: str
    objective: str
    status: Literal["completed", "skipped", "failed"]
    details: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime = field(default_factory=datetime.utcnow)

