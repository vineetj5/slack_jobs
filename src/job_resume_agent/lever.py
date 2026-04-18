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


class LeverJobExtractor:
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
        url = f"https://api.lever.co/v0/postings/{company_id}"
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

        if not isinstance(payload, list):
            return []

        jobs: list[JobPosting] = []
        for row in payload:
            title = row.get("text") or ""
            if not role_matches_title(title, self.role_terms):
                continue

            # --- Recency filter ---
            # Lever uses 'createdAt' (millis)
            if cutoff is not None:
                created_at_ms = row.get("createdAt")
                if created_at_ms:
                    ts = datetime.fromtimestamp(created_at_ms / 1000.0, tz=timezone.utc)
                    if ts < cutoff:
                        continue
                else:
                    # If no timestamp, assume old to be safe or just include? 
                    # Usually we want new ones only.
                    continue

            location = row.get("categories", {}).get("location") or "Unknown"
            if not is_usa_location(location):
                continue

            # Construct description from description + lists
            description_html = row.get("description", "")
            for item in row.get("lists", []):
                description_html += f"\n{item.get('text')}\n{item.get('content')}"
            
            description = BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)

            if not check_experience(description):
                continue

            jobs.append(
                JobPosting(
                    title=title,
                    company=company_id.capitalize(), # Lever doesn't provide company name in list
                    location=location,
                    url=row.get("hostedUrl"),
                    description=description,
                    source=f"lever:{company_id}",
                    posted_at=datetime.fromtimestamp(created_at_ms / 1000.0, tz=timezone.utc).isoformat() if created_at_ms else None,
                    tags=[row.get("categories", {}).get("team")] if row.get("categories", {}).get("team") else [],
                )
            )
        return jobs
