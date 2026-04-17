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


class SmartRecruitersJobExtractor:
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

    def _collect_company(self, company_token: str, cutoff: datetime | None = None) -> list[JobPosting]:
        url = f"https://api.smartrecruiters.com/v1/companies/{company_token}/postings"
        try:
            # We fetch up to 50 recent jobs limit
            response = requests.get(
                url,
                params={"limit": 50},
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.request_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            # SmartRecruiters sometimes blocks or 404s if company ID is wrong
            return []

        payload = response.json()
        jobs: list[JobPosting] = []

        for row in payload.get("content", []):
            title = row.get("name") or ""
            if not role_matches_title(title, self.role_terms):
                continue

            # --- Recency filter ---
            if cutoff is not None:
                updated_raw = row.get("releasedDate")
                if not updated_raw or not self._is_within_cutoff(updated_raw, cutoff):
                    continue

            loc_dict = row.get("location", {})
            loc_parts = []
            if loc_dict.get("city"):
                loc_parts.append(loc_dict["city"])
            if loc_dict.get("region"):
                loc_parts.append(loc_dict["region"])
            if loc_dict.get("country"):
                loc_parts.append(loc_dict["country"].upper())
            if loc_dict.get("remote"):
                loc_parts.append("Remote")

            location = ", ".join(loc_parts) or "Unknown"

            if not is_usa_location(location):
                continue

            company_name = row.get("company", {}).get("name") or company_token
            ref_url = row.get("ref")
            absolute_url = row.get("applyUrl") or f"https://jobs.smartrecruiters.com/{company_token}/{row.get('id')}"

            departments = []
            if row.get("department", {}).get("label"):
                departments.append(row["department"]["label"])

            # To do experience filtering properly via regex, we need the description.
            # Smart Recruiters hides description in the individual posting `ref`.
            description = ""
            if ref_url:
                try:
                    ref_resp = requests.get(
                        ref_url,
                        headers={"User-Agent": self.config.user_agent},
                        timeout=self.config.request_timeout_seconds,
                    )
                    if ref_resp.status_code == 200:
                        ref_payload = ref_resp.json()
                        sections = ref_payload.get("jobAd", {}).get("sections", {})
                        
                        html_content = ""
                        # Combine text from typical SR sections
                        if sections.get("jobDescription"):
                            html_content += sections["jobDescription"].get("text", "") + " "
                        if sections.get("qualifications"):
                            html_content += sections["qualifications"].get("text", "") + " "
                            
                        description = BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True)
                except requests.RequestException:
                    pass

            if not check_experience(description):
                continue

            jobs.append(
                JobPosting(
                    title=title,
                    company=company_name,
                    location=location,
                    url=absolute_url,
                    description=description,
                    source=f"smartrecruiters:{company_token}",
                    posted_at=row.get("releasedDate"),
                    tags=departments,
                )
            )

        return jobs

    def _is_within_cutoff(self, updated_raw: str, cutoff: datetime) -> bool:
        """Return True if *updated_raw* (ISO-8601 string) is at or after *cutoff*."""
        try:
            ts = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts >= cutoff
        except (ValueError, AttributeError):
            return True
