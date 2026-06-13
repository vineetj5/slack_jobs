from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .config import AppConfig
from .greenhouse import (
    GREENHOUSE_ROLE_TERMS,
    check_experience,
    get_target_region,
    role_matches_title,
)
from .models import JobPosting

# Amazon Jobs public search JSON endpoint
_SEARCH_URL = "https://www.amazon.jobs/en/search.json"

# Maximum jobs returned per page (Amazon caps at 10 per request typically)
_PAGE_SIZE = 10

# Amazon-specific role terms – includes their generic SDE/SWE titles plus
# the data/ML terms from GREENHOUSE_ROLE_TERMS.
AMAZON_ROLE_TERMS: list[str] = [
    # Generic SDE / SWE titles used heavily at Amazon
    "Software Development Engineer",
    "Software Engineer",
    "SDE",
    "SWE",
    "Software Dev Engineer",
    "Front End Engineer",
    "Frontend Engineer",
    "Backend Engineer",
    "Full Stack Engineer",
    "Systems Development Engineer",
    "Solutions Architect",
    "New Grad",
    "Entry Level",
    "Junior",
    # Data / ML / AI (from GREENHOUSE_ROLE_TERMS)
    *GREENHOUSE_ROLE_TERMS,
]

# Month name → number for posted_date parsing ("June 12, 2026")
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# Regex to detect "about N hours" / "N days" in updated_time
_HOURS_RE = re.compile(r"(\d+)\s+hour", re.IGNORECASE)
_DAYS_RE = re.compile(r"(\d+)\s+day", re.IGNORECASE)


def _parse_posted_date(posted_date: str | None) -> datetime | None:
    """Parse Amazon's human-readable posted_date like 'June 12, 2026' to UTC datetime."""
    if not posted_date:
        return None
    try:
        # Format: "Month D, YYYY"
        parts = posted_date.strip().replace(",", "").split()
        if len(parts) != 3:
            return None
        month = _MONTH_MAP.get(parts[0].lower())
        if month is None:
            return None
        day = int(parts[1])
        year = int(parts[2])
        return datetime(year, month, day, tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def _estimate_posted_hours(updated_time: str | None, posted_date: str | None) -> float | None:
    """
    Estimate how many hours ago the job was posted/updated.

    Amazon provides:
      - updated_time: e.g. "about 20 hours", "1 day", "2 days"
      - posted_date:  e.g. "June 12, 2026"  (date only, no time)

    We prefer updated_time for sub-day precision; fall back to posted_date.
    Returns None if we can't determine the age.
    """
    if updated_time:
        m = _HOURS_RE.search(updated_time)
        if m:
            return float(m.group(1))
        m = _DAYS_RE.search(updated_time)
        if m:
            return float(m.group(1)) * 24.0
        # "about 1 hour" edge-case without a digit
        if "hour" in updated_time.lower():
            return 1.0

    # Fall back to posted_date (treat as start-of-day UTC)
    posted_dt = _parse_posted_date(posted_date)
    if posted_dt:
        now = datetime.now(tz=timezone.utc)
        return max(0.0, (now - posted_dt).total_seconds() / 3600.0)

    return None


class AmazonJobExtractor:
    """
    Scrapes Amazon Jobs (amazon.jobs) via its undocumented-but-public JSON API.

    Usage::

        extractor = AmazonJobExtractor(posted_within_hours=24)
        jobs = extractor.collect()      # no company list needed – Amazon is one board
    """

    BASE_URL = "https://www.amazon.jobs"

    def __init__(
        self,
        config: AppConfig | None = None,
        role_terms: Iterable[str] = AMAZON_ROLE_TERMS,
        posted_within_hours: float = 1.0,
        # Optional: restrict to specific job categories on amazon.jobs
        # e.g. ["software-development", "data-science"]
        categories: Iterable[str] | None = None,
        # Optional: restrict to specific country codes e.g. ["USA"]
        country_codes: Iterable[str] | None = None,
        max_pages: int = 5,
    ) -> None:
        self.config = config or AppConfig()
        self.role_terms = list(dict.fromkeys(role_terms))
        self.posted_within_hours = posted_within_hours
        self.categories = list(categories) if categories else ["software-development"]
        self.country_codes = list(country_codes) if country_codes else []
        self.max_pages = max_pages

    # ------------------------------------------------------------------
    # Public interface – mirrors the other extractors
    # ------------------------------------------------------------------

    def collect(self, _companies: Iterable[str] | None = None) -> list[JobPosting]:
        """
        Collect matching Amazon jobs posted within the configured time window.

        The ``_companies`` argument is accepted for API compatibility with other
        extractors but is ignored – Amazon Jobs is a single unified board.
        """
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()

        for page_offset in range(0, self.max_pages * _PAGE_SIZE, _PAGE_SIZE):
            page_jobs, stop_early = self._fetch_page(
                offset=page_offset,
                result_limit=_PAGE_SIZE,
            )
            for job in page_jobs:
                dedupe_key = job.url or f"{job.company}:{job.title}:{job.location}"
                if dedupe_key in seen_urls:
                    continue
                seen_urls.add(dedupe_key)
                jobs.append(job)

            if stop_early:
                # All remaining results are older than our window; stop paginating
                break

        return jobs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_params(self, offset: int, result_limit: int) -> dict:
        params: dict = {
            "result_limit": result_limit,
            "offset": offset,
            "sort": "recent",
        }
        if self.categories:
            params["category[]"] = self.categories
        if self.country_codes:
            params["country[]"] = self.country_codes
        return params

    def _fetch_page(self, offset: int, result_limit: int) -> tuple[list[JobPosting], bool]:
        """
        Fetch one page of results.

        Returns ``(jobs, stop_early)`` where ``stop_early`` is True when all
        results on this page are older than the time window (no need to fetch
        more pages since results are sorted by recency).
        """
        try:
            response = requests.get(
                _SEARCH_URL,
                params=self._build_params(offset, result_limit),
                headers={
                    "User-Agent": self.config.user_agent,
                    # Disable zstd to avoid urllib3 decompression bug with chunked encoding
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=self.config.request_timeout_seconds,
            )
            if response.status_code != 200:
                return [], True
            payload = response.json()
        except Exception:
            return [], True

        raw_jobs = payload.get("jobs", [])
        if not raw_jobs:
            return [], True

        jobs: list[JobPosting] = []
        stop_early = False
        all_old = True  # tracks whether every job on this page is too old

        for row in raw_jobs:
            title = row.get("title") or ""
            if not role_matches_title(title, self.role_terms):
                continue

            # --- Recency filter ---
            updated_time = row.get("updated_time")   # "about 20 hours", "1 day" …
            posted_date_str = row.get("posted_date")  # "June 12, 2026"

            estimated_hours = _estimate_posted_hours(updated_time, posted_date_str)
            if estimated_hours is not None:
                if estimated_hours > self.posted_within_hours:
                    continue  # job is too old
                else:
                    all_old = False  # at least one job is within our window
            else:
                all_old = False  # unknown age → include conservatively

            # --- Location / region filter ---
            location = row.get("location") or row.get("normalized_location") or "Unknown"
            region = get_target_region(location)
            if not region:
                continue

            # --- Experience filter from description ---
            description_html = (
                row.get("description") or
                row.get("basic_qualifications") or
                ""
            )
            description = BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)

            if not check_experience(description):
                continue

            # --- Build job URL ---
            job_path = row.get("job_path") or ""
            job_url = f"{self.BASE_URL}{job_path}" if job_path else None

            # Prefer the canonical posted_date for posted_at
            posted_at = posted_date_str

            company = row.get("company_name") or "Amazon"
            job_category = row.get("job_category") or row.get("job_family") or ""

            jobs.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    description=description,
                    source="amazon",
                    posted_at=posted_at,
                    tags=[job_category] if job_category else [],
                    is_reposted=False,
                    original_published_at=posted_date_str,
                    region=region,
                )
            )

        # If every job on this page was too old we can stop paginating
        if all_old and len(raw_jobs) > 0:
            stop_early = True

        return jobs, stop_early
