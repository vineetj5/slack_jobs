from __future__ import annotations

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    title: str
    company: str
    location: str = "Unknown"
    url: str | None = None
    description: str
    source: str
    posted_at: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_reposted: bool = False
    original_published_at: str | int | float | None = None
    region: str = "Unknown"
