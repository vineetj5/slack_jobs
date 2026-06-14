from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .amazon import AMAZON_ROLE_TERMS
from .config import AppConfig
from .greenhouse import check_experience, get_target_region, role_matches_title
from .models import JobPosting

# Re-use the same broad role terms
META_ROLE_TERMS = AMAZON_ROLE_TERMS

# Meta's US office locations from the user-supplied URL
META_US_OFFICES = [
    "San Francisco, CA",
    "Mountain View, CA",
    "Menlo Park, CA",
    "Irvine, CA",
    "Fremont, CA",
    "San Diego, CA",
    "Sunnyvale, CA",
    "Los Angeles, CA",
    "Santa Clara, CA",
    "San Mateo, CA",
    "Newark, CA",
    "Foster City, CA",
    "Redmond, WA",
    "Seattle, WA",
    "Bellevue, WA",
    "Washington, DC",
    "Vancouver, WA",
    "Austin, TX",
    "Houston, TX",
    "Fort Worth, TX",
    "Chandler, AZ",
    "Mesa, AZ",
    "New York, NY",
    "Durham, NC",
    "Denver, CO",
    "Forest City, NC",
    "Ashburn, VA",
    "Sterling, VA",
    "Richmond, VA",
    "Boston, MA",
    "Cambridge, MA",
    "Pittsburgh, PA",
    "Detroit, MI",
    "Atlanta, GA",
    "Miami, Florida",
]

# GraphQL doc_id for CPJobSearchSourceQuery (extracted from Meta's JS bundle)
_SEARCH_DOC_ID = "27807005005556827"

# GraphQL API endpoint
_GRAPHQL_URL = "https://www.metacareers.com/api/graphql/"

# Job detail page base URL
_JOB_BASE_URL = "https://www.metacareers.com/jobs"

# Max workers for concurrent detail-page fetches
_DETAIL_WORKERS = 5


def _get_lsd_token(session: requests.Session, user_agent: str) -> str:
    """Fetch the LSD CSRF token required by Meta's GraphQL API."""
    try:
        resp = session.get(
            "https://www.metacareers.com/jobs",
            headers={"User-Agent": user_agent},
            timeout=15,
        )
        match = re.search(r'"LSD",\[\],\{"token":"(.*?)"', resp.text)
        return match.group(1) if match else ""
    except Exception:
        return ""


def _search_jobs(
    session: requests.Session,
    lsd_token: str,
    user_agent: str,
    role_query: str,
    timeout: int,
) -> list[dict]:
    """
    Call Meta's GraphQL search endpoint for a given role query.
    Returns a list of raw job dicts with id, title, locations.
    """
    variables = {
        "search_input": {
            "q": role_query,
            "results_per_page": "TEN",
            "sort_by_new": True,
        }
    }
    data = {
        "doc_id": _SEARCH_DOC_ID,
        "variables": json.dumps(variables),
        "lsd": lsd_token,
    }
    headers = {
        "User-Agent": user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.metacareers.com",
        "Referer": "https://www.metacareers.com/",
        "X-FB-LSD": lsd_token,
    }
    try:
        resp = session.post(_GRAPHQL_URL, data=data, headers=headers, timeout=timeout)
        payload = resp.json()
        return (
            payload.get("data", {})
            .get("job_search_with_featured_jobs", {})
            .get("all_jobs", [])
        ) or []
    except Exception:
        return []


def _fetch_job_detail(
    session: requests.Session,
    job_id: str,
    user_agent: str,
    timeout: int,
) -> dict | None:
    """
    Fetch a job detail page and extract the JSON-LD schema which contains:
      - datePosted  (ISO 8601 – the first published date)
      - validThrough (ISO 8601 – expiry / last-refreshed date, used as updated time)
      - description, qualifications, jobLocation
    Returns None on any failure.
    """
    url = f"{_JOB_BASE_URL}/{job_id}/"
    try:
        resp = session.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", type="application/ld+json")
        if not script or not script.string:
            return None
        data = json.loads(script.string)
        data["_job_url"] = url
        return data
    except Exception:
        return None


class MetaJobExtractor:
    """
    Scrapes Meta Careers via their GraphQL API + JSON-LD detail pages.

    Strategy:
      1. For each role term, call the GraphQL search API to get job IDs & titles.
      2. For each matching job ID, fetch the detail page and extract JSON-LD.
      3. JSON-LD provides exact ISO 8601 timestamps:
           - datePosted   → first published date (used as original_published_at)
           - validThrough → expiry/refresh date (used as updated / posted_at)
      4. Apply recency, region, experience, and repost filters.

    Usage::

        extractor = MetaJobExtractor(posted_within_hours=24)
        jobs = extractor.collect()
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        role_terms: Iterable[str] = META_ROLE_TERMS,
        posted_within_hours: float = 1.0,
        offices: list[str] | None = None,
        max_detail_workers: int = _DETAIL_WORKERS,
    ) -> None:
        self.config = config or AppConfig()
        self.role_terms = list(dict.fromkeys(role_terms))
        self.posted_within_hours = posted_within_hours
        self.offices = offices if offices is not None else META_US_OFFICES
        self.max_detail_workers = max_detail_workers

    def collect(self, _companies: Iterable[str] | None = None) -> list[JobPosting]:
        """
        Collect matching Meta jobs posted within the configured time window.
        _companies is accepted for API compatibility but ignored.
        """
        session = requests.Session()
        lsd_token = _get_lsd_token(session, self.config.user_agent)

        # Step 1: Gather job IDs for all roles (deduplicated)
        raw_jobs: dict[str, dict] = {}  # job_id → {title, locations}
        for role in self.role_terms:
            results = _search_jobs(
                session, lsd_token, self.config.user_agent,
                role, self.config.request_timeout_seconds
            )
            for raw in results:
                job_id = str(raw.get("id", ""))
                if not job_id or job_id in raw_jobs:
                    continue
                title = raw.get("title") or ""
                if not role_matches_title(title, self.role_terms):
                    continue
                # Pre-filter: at least one location must be in our target offices
                locations = raw.get("locations") or []
                if not self._has_us_location(locations):
                    continue
                raw_jobs[job_id] = {"title": title, "locations": locations}

        if not raw_jobs:
            return []

        # Step 2: Fetch detail pages concurrently
        jobs: list[JobPosting] = []
        now = datetime.now(tz=timezone.utc)

        def _fetch(job_id: str, meta: dict):
            detail = _fetch_job_detail(
                session, job_id, self.config.user_agent,
                self.config.request_timeout_seconds
            )
            return job_id, meta, detail

        with ThreadPoolExecutor(max_workers=self.max_detail_workers) as executor:
            futures = {
                executor.submit(_fetch, jid, jmeta): jid
                for jid, jmeta in raw_jobs.items()
            }
            for future in as_completed(futures):
                job_id, meta, detail = future.result()
                if not detail:
                    continue

                job = self._build_posting(job_id, meta, detail, now)
                if job:
                    jobs.append(job)

        return jobs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_us_location(self, locations: list[str]) -> bool:
        """Return True if any location string matches one of our target US offices."""
        for loc in locations:
            for office in self.offices:
                if office.lower() in loc.lower() or loc.lower() in office.lower():
                    return True
        return False

    def _build_posting(
        self,
        job_id: str,
        meta: dict,
        detail: dict,
        now: datetime,
    ) -> JobPosting | None:
        """Convert raw GraphQL + JSON-LD data into a JobPosting, applying all filters."""
        title = detail.get("title") or meta.get("title") or ""

        # --- Timestamps from JSON-LD ---
        date_posted_str = detail.get("datePosted")    # first published ISO datetime
        valid_through_str = detail.get("validThrough")  # expiry date, refreshed when job is reposted

        def _parse_iso(s: str | None) -> datetime | None:
            if not s:
                return None
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                return None

        posted_dt = _parse_iso(date_posted_str)
        valid_through_dt = _parse_iso(valid_through_str)

        # Use datePosted for recency check (this is when the job first went live)
        active_dt = posted_dt
        if not active_dt:
            return None

        hours_ago = (now - active_dt).total_seconds() / 3600.0
        if hours_ago > self.posted_within_hours:
            return None

        # --- Reposted logic ---
        # Meta doesn't expose an explicit "updated" timestamp separately.
        # We use validThrough as a proxy: if it's been extended significantly
        # beyond the original expiry window (i.e. job was refreshed), flag as reposted.
        is_reposted = False
        original_published_at = active_dt.isoformat()
        if valid_through_dt:
            # A typical Meta posting has validThrough ~60 days after datePosted.
            # If the gap between datePosted and validThrough is much larger, it was refreshed.
            gap_days = (valid_through_dt - active_dt).days
            # If the job was originally posted more than 7 days ago but validThrough is recent
            # (within the next 60 days from now) it likely got re-promoted
            now_plus_60 = now.timestamp() + 60 * 86400
            if gap_days > 90 and valid_through_dt.timestamp() < now_plus_60:
                is_reposted = True


        # --- Location / region filter ---
        locations = detail.get("jobLocation") or []
        location_str = "Unknown"
        if locations:
            loc0 = locations[0]
            if isinstance(loc0, dict):
                location_str = loc0.get("name") or location_str
            elif isinstance(loc0, str):
                location_str = loc0
        # multi-location display
        if len(locations) > 1:
            location_str += f" +{len(locations)-1} more"

        region = get_target_region(location_str)
        if not region:
            return None

        # --- Experience filter ---
        desc_html = detail.get("description") or ""
        quals_html = detail.get("qualifications") or ""
        description = BeautifulSoup(desc_html + " " + quals_html, "html.parser").get_text(" ", strip=True)
        if not check_experience(description):
            return None

        job_url = detail.get("_job_url") or f"{_JOB_BASE_URL}/{job_id}/"
        company = (detail.get("hiringOrganization") or {}).get("name") or "Meta"
        dept = (detail.get("employmentType") or "Engineering")

        return JobPosting(
            title=title,
            company=company,
            location=location_str,
            url=job_url,
            description=description,
            source="meta",
            posted_at=active_dt.isoformat(),
            tags=[dept] if dept else [],
            is_reposted=is_reposted,
            original_published_at=original_published_at,
            region=region,
        )
