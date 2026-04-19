from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .config import AppConfig
from .greenhouse import GREENHOUSE_ROLE_TERMS, check_experience, is_usa_location, role_matches_title
from .models import JobPosting

log = logging.getLogger(__name__)

class WorkdayJobExtractor:
    def __init__(
        self,
        config: AppConfig | None = None,
        role_terms: Iterable[str] = GREENHOUSE_ROLE_TERMS,
        posted_within_hours: float = 1.0,
    ) -> None:
        self.config = config or AppConfig()
        self.role_terms = list(dict.fromkeys(role_terms))
        self.posted_within_hours = posted_within_hours

    def collect(self, boards: Iterable[str]) -> list[JobPosting]:
        """
        'boards' elements should be in format 'tenant/site_id' or just 'tenant' (defaulting site_id to 'External')
        """
        all_jobs: list[JobPosting] = []
        seen_urls: set[str] = set()

        for board_info in boards:
            if not board_info.strip():
                continue
            parts = board_info.strip().split("/", 1)
            tenant = parts[0]
            site_id = parts[1] if len(parts) > 1 else "External"

            try:
                company_jobs = self._collect_board(tenant, site_id)
                for job in company_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
            except Exception as e:
                log.debug(f"Failed to collect Workday board {board_info}: {e}")

        return all_jobs

    def _collect_board(self, tenant: str, site_id: str) -> list[JobPosting]:
        api_base = f"https://{tenant}.myworkdayjobs.com/wday/cxs/{tenant}/{site_id}"
        list_url = f"{api_base}/jobs"
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
        }
        
        payload = {
            "appliedFacets": {},
            "limit": 20,
            "offset": 0,
            "searchText": ""
        }

        try:
            resp = requests.post(list_url, json=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception:
            return []

        jobs: list[JobPosting] = []
        for row in data.get("jobPostings", []):
            title = row.get("title") or ""
            if not role_matches_title(title, self.role_terms):
                continue

            # Workday recency: Posted Today, Posted Yesterday, etc.
            posted_on = str(row.get("postedOn", "")).lower()
            # If posted_within_hours is small (<= 24), we only care about roles posted 'today'
            # Note: Workday precision is limited, so 'today' is our best proxy for hourly notify.
            if "today" not in posted_on and self.posted_within_hours <= 24:
                continue

            # Location: Workday uses 'locationsText' in results
            location = row.get("locationsText") or "Unknown"
            if not is_usa_location(location):
                continue

            # Need detail for description
            external_path = row.get("externalPath") # e.g. /job/Salesforce/Software-Engineer_JR123
            if not external_path:
                continue
            
            detail_url = f"{api_base}{external_path}"
            try:
                detail_resp = requests.get(detail_url, headers=headers, timeout=10)
                if detail_resp.status_code != 200:
                    continue
                detail_data = detail_resp.json()
                job_desc_data = detail_data.get("jobDescription", "")
            except Exception:
                continue

            description = BeautifulSoup(job_desc_data, "html.parser").get_text(" ", strip=True)
            if not check_experience(description):
                continue

            # public URL format
            # from: /job/tenant/ID
            # to: https://tenant.myworkdayjobs.com/en-US/tenant/job/ID
            public_url = f"https://{tenant}.myworkdayjobs.com{external_path}"

            jobs.append(
                JobPosting(
                    title=title,
                    company=tenant.capitalize(),
                    location=location,
                    url=public_url,
                    description=description,
                    source=f"workday:{tenant}",
                    posted_at=row.get("postedOn"),
                    tags=[row.get("hiringOrganization")] if row.get("hiringOrganization") else [],
                )
            )

        return jobs
