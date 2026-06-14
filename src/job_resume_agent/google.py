from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .amazon import AMAZON_ROLE_TERMS
from .config import AppConfig
from .greenhouse import check_experience, get_target_region, role_matches_title
from .models import JobPosting

# We reuse AMAZON_ROLE_TERMS as they are generic SDE/SWE/ML roles
GOOGLE_ROLE_TERMS = AMAZON_ROLE_TERMS


class GoogleJobExtractor:
    """
    Scrapes Google Careers by extracting embedded JSON from the HTML.

    Usage::

        extractor = GoogleJobExtractor(posted_within_hours=24)
        jobs = extractor.collect()
    """

    # We use the applications results page which returns the newest jobs when sorted by date
    BASE_SEARCH_URL = "https://www.google.com/about/careers/applications/jobs/results"

    def __init__(
        self,
        config: AppConfig | None = None,
        role_terms: Iterable[str] = GOOGLE_ROLE_TERMS,
        posted_within_hours: float = 1.0,
    ) -> None:
        self.config = config or AppConfig()
        self.role_terms = list(dict.fromkeys(role_terms))
        self.posted_within_hours = posted_within_hours

    def collect(self, _companies: Iterable[str] | None = None) -> list[JobPosting]:
        """
        Collect matching Google jobs posted within the configured time window.
        Loops over each role to get the most relevant recent results.
        """
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()

        for role in self.role_terms:
            page_jobs = self._fetch_jobs_for_role(role)
            for job in page_jobs:
                dedupe_key = job.url or f"{job.company}:{job.title}:{job.location}"
                if dedupe_key in seen_urls:
                    continue
                seen_urls.add(dedupe_key)
                jobs.append(job)

        return jobs

    def _fetch_jobs_for_role(self, role: str) -> list[JobPosting]:
        """Fetch the first page of recent results for a given role from Google Careers."""
        encoded_role = quote_plus(f'"{role}"')
        url = f"{self.BASE_SEARCH_URL}?location=United%20States&sort_by=date&q={encoded_role}"

        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.config.user_agent},
                timeout=self.config.request_timeout_seconds,
            )
            if response.status_code != 200:
                return []
            text = response.text
        except Exception:
            return []

        # Find the JSON data array embedded in AF_initDataCallback
        match = re.search(r"AF_initDataCallback\(\{key: 'ds:1',.*?data:(\[.*?\]), sideChannel:.*?\}\);", text, re.DOTALL)
        if not match:
            match = re.search(r"AF_initDataCallback\(\{key: 'ds:1',.*?data:(\[.*?\])\}\);", text, re.DOTALL)

        if not match:
            return []

        try:
            data = json.loads(match.group(1))
            # The structure is usually nested depending on the query state
            raw_jobs = data[0] if isinstance(data[0], list) else data
        except Exception:
            return []

        jobs: list[JobPosting] = []
        now = datetime.now(tz=timezone.utc)

        for j in raw_jobs:
            if not isinstance(j, list) or len(j) < 14:
                continue

            title = j[1]
            if not title or not isinstance(title, str):
                continue
                
            if not role_matches_title(title, self.role_terms):
                continue

            # Extract timestamps (index 12 is usually posted, index 13 is updated)
            posted_ts = j[12][0] if j[12] else None
            updated_ts = j[13][0] if j[13] else None
            
            # Use updated_ts for recency, fallback to posted_ts
            active_ts = updated_ts or posted_ts
            if not active_ts:
                continue

            active_dt = datetime.fromtimestamp(active_ts, tz=timezone.utc)
            hours_ago = (now - active_dt).total_seconds() / 3600.0

            if hours_ago > self.posted_within_hours:
                # Results are sorted by date, so if we hit an old one, 
                # we could technically break, but we'll just continue
                # since we might have mild sorting variations or promoted jobs
                continue

            # Check if reposted (if updated_ts > posted_ts by 48 hours)
            is_reposted = False
            original_published_at = ""
            if posted_ts and updated_ts:
                posted_dt = datetime.fromtimestamp(posted_ts, tz=timezone.utc)
                original_published_at = posted_dt.isoformat()
                if (active_dt - posted_dt).total_seconds() / 3600.0 > 48.0:
                    is_reposted = True

            # Extract location
            location = "Unknown"
            if len(j) > 9 and j[9] and len(j[9]) > 0 and len(j[9][0]) > 0:
                location = j[9][0][0]
            region = get_target_region(location)
            if not region:
                continue

            # Combine descriptions
            desc_html = ""
            if len(j) > 10 and j[10] and len(j[10]) > 1:
                desc_html += j[10][1] or ""
            if len(j) > 4 and j[4] and len(j[4]) > 1:
                desc_html += " " + (j[4][1] or "")

            description = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)
            if not check_experience(description):
                continue

            job_url = j[2]
            company = j[7] if len(j) > 7 and j[7] else "Google"

            jobs.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    description=description,
                    source="google",
                    posted_at=active_dt.isoformat(),
                    tags=["Engineering"],
                    is_reposted=is_reposted,
                    original_published_at=original_published_at,
                    region=region,
                )
            )

        return jobs
