from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .config import AppConfig
from .greenhouse import GREENHOUSE_ROLE_TERMS, check_experience, is_usa_location, role_matches_title
from .models import JobPosting


class AshbyJobExtractor:
    def __init__(
        self,
        config: AppConfig | None = None,
        role_terms: Iterable[str] = GREENHOUSE_ROLE_TERMS,
        posted_within_hours: float = 1.0,
    ) -> None:
        self.config = config or AppConfig()
        self.role_terms = list(dict.fromkeys(role_terms))
        self.posted_within_hours = posted_within_hours

    def collect(self, companies: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self.posted_within_hours)

        for company in companies:
            for job in self._collect_company(company, cutoff=cutoff):
                dedupe_key = job.url or f"{job.company}:{job.title}:{job.location}"
                if dedupe_key in seen_urls:
                    continue
                seen_urls.add(dedupe_key)
                jobs.append(job)

        return jobs

    def _collect_company(self, company_id: str, cutoff: datetime | None = None) -> list[JobPosting]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{company_id}"
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.request_timeout_seconds,
            )
            if response.status_code != 200:
                return []
            payload = response.json()
        except Exception:
            return []

        jobs: list[JobPosting] = []
        for row in payload.get("jobs", []):
            title = row.get("title") or ""
            if not role_matches_title(title, self.role_terms):
                continue

            # --- Recency filter ---
            # Ashby uses 'publishedAt' (ISO8601)
            if cutoff is not None:
                published_raw = row.get("publishedAt")
                if published_raw:
                    ts = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        continue
                else:
                    continue

            location = row.get("location") or "Unknown"
            if not is_usa_location(location):
                continue

            description_html = row.get("descriptionHtml", "")
            description = BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)

            if not check_experience(description):
                continue

            jobs.append(
                JobPosting(
                    title=title,
                    company=company_id.capitalize(),
                    location=location,
                    url=row.get("jobUrl"),
                    description=description,
                    source=f"ashby:{company_id}",
                    posted_at=published_raw,
                    tags=[row.get("department")] if row.get("department") else [],
                )
            )
        return jobs
