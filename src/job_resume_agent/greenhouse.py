from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import AppConfig
from .models import JobPosting


GREENHOUSE_ROLE_TERMS = [
    "Data Science",
    "Machine Learning Engineer",
    "Data Analyst",
    "Deep Learning Engineer",
    "Data Engineer",
    "Big Data Engineer",
    "AI Engineer",
    "Python Engineer",
    "New Grad",
    "Data Scientist",
    "C/C++ Engineer",
    "ETL Developer",
    "Power BI Developer",
    "Business/BI Analyst",
    "Data Warehouse Engineer",
    "Machine Learning/AI Researcher",
    "Machine Learning",
    "Deep Learning",
    "LLM Engineer",
    "Model Training",
    "Computer Vision",
    "MLOps",
    "ML Ops",
    "Machine Learning Operations",
    "Search System",
    "Machine Learning Infrastructure",
    "Machine Learning Ads",
    "University Grad",
    "Backend Engineer",
    "Java Engineer",
    "DevOps",
    "Business Analyst",
    "Healthcare Data Analyst",
    "Healthcare Data Scientist",
    "Full Stack Engineer",
]


def normalize_greenhouse_board(board: str) -> str:
    """Return the Greenhouse board token from a token or public board URL."""
    board = board.strip()
    parsed = urlparse(board)
    if not parsed.netloc:
        return board.strip("/")

    path_parts = [part for part in parsed.path.split("/") if part]
    if "boards-api.greenhouse.io" in parsed.netloc and "boards" in path_parts:
        board_index = path_parts.index("boards")
        if len(path_parts) > board_index + 1:
            return path_parts[board_index + 1]

    if parsed.netloc in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and path_parts:
        return path_parts[0]

    raise ValueError(f"Could not find a Greenhouse board token in {board!r}")


def role_matches_title(title: str, role_terms: Iterable[str] = GREENHOUSE_ROLE_TERMS) -> bool:
    normalized_title = _normalize_text(title)
    return any(_normalize_text(term) in normalized_title for term in role_terms)


class GreenhouseJobExtractor:
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
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self.posted_within_hours)

        for board in boards:
            board_token = normalize_greenhouse_board(board)
            for job in self._collect_board(board_token, cutoff=cutoff):
                dedupe_key = job.url or f"{job.company}:{job.title}:{job.location}"
                if dedupe_key in seen_urls:
                    continue
                seen_urls.add(dedupe_key)
                jobs.append(job)

        return jobs

    def write_json(self, jobs: Iterable[JobPosting], output: str | Path) -> None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([job.model_dump() for job in jobs], indent=2),
            encoding="utf-8",
        )

    def write_csv(self, jobs: Iterable[JobPosting], output: str | Path) -> None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "title",
                    "company",
                    "location",
                    "url",
                    "source",
                    "posted_at",
                    "tags",
                    "description",
                ],
            )
            writer.writeheader()
            for job in jobs:
                writer.writerow(
                    {
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "url": job.url,
                        "source": job.source,
                        "posted_at": job.posted_at,
                        "tags": ", ".join(job.tags),
                        "description": job.description,
                    }
                )

    def _collect_board(self, board_token: str, cutoff: datetime | None = None) -> list[JobPosting]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        response = requests.get(
            url,
            params={"content": "true"},
            headers={"User-Agent": self.config.user_agent},
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        company = payload.get("meta", {}).get("name") or board_token
        jobs: list[JobPosting] = []
        for row in payload.get("jobs", []):
            title = row.get("title") or ""
            if not role_matches_title(title, self.role_terms):
                continue

            # --- Recency filter ---
            if cutoff is not None:
                updated_raw = row.get("updated_at")
                if not updated_raw or not _is_within_cutoff(updated_raw, cutoff):
                    continue

            offices = [office.get("name") for office in row.get("offices", []) if office.get("name")]
            location = ", ".join(offices) or "Unknown"

            if not is_usa_location(location):
                continue
                
            departments = [
                department.get("name")
                for department in row.get("departments", [])
                if department.get("name")
            ]
            content = row.get("content") or ""
            description = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)

            if not check_experience(description):
                continue

            jobs.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    url=row.get("absolute_url"),
                    description=description,
                    source=f"greenhouse:{board_token}",
                    posted_at=row.get("updated_at"),
                    tags=departments,
                )
            )
        return jobs


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", value.lower()).strip()


def _is_within_cutoff(updated_raw: str, cutoff: datetime) -> bool:
    """Return True if *updated_raw* (ISO-8601 string) is at or after *cutoff*."""
    try:
        # Python 3.7+ fromisoformat does not handle the trailing 'Z'
        ts = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
        # Make cutoff timezone-aware if it isn't already
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= cutoff
    except (ValueError, AttributeError):
        # If we cannot parse the timestamp, include the job to be safe
        return True


def is_usa_location(location: str) -> bool:
    loc = location.lower()
    
    non_us = [
        "emea", "apac", "uk", "london", "canada", "toronto", "vancouver", "ontario",
        "india", "bengaluru", "bangalore", "delhi", "mumbai", "europe", "germany",
        "berlin", "france", "paris", "australia", "sydney", "melbourne", "ireland",
        "dublin", "singapore", "mexico", "brazil", "spain", "poland"
    ]
    if any(country in loc for country in non_us) and "us" not in loc and "united states" not in loc:
        return False

    us_terms = [" us", ", us", "usa", "united states", "remote - us", "remote (us)", "remote, us"]
    if any(t in loc for t in us_terms) or loc == "us" or loc == "remote" or "remote" in loc:
        return True
        
    states = [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", 
        "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", 
        "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska", 
        "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", 
        "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", 
        "texas", "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
        ", al", ", ak", ", az", ", ar", ", ca", ", co", ", ct", ", de", ", fl", ", ga", ", hi", ", id", ", il", ", in", ", ia", ", ks", 
        ", ky", ", la", ", me", ", md", ", ma", ", mi", ", mn", ", ms", ", mo", ", mt", ", ne", ", nv", ", nh", ", nj", ", nm", ", ny", 
        ", nc", ", nd", ", oh", ", ok", ", or", ", pa", ", ri", ", sc", ", sd", ", tn", ", tx", ", ut", ", vt", ", va", ", wa", ", wv", 
        ", wi", ", wy", "san francisco", "new york", "seattle", "austin", "boston", "chicago", "los angeles", "atlanta"
    ]
    if any(s in loc for s in states):
        return True
        
    return True

def check_experience(description: str) -> bool:
    pattern = re.compile(r'(\d+)\s*(?:\+|-|to)?\s*(?:\d*\s*)\+?\s*(?:years?|yrs?)[^.?!]{0,40}experience', re.IGNORECASE)
    matches = pattern.finditer(description)
    
    yoes = []
    for m in matches:
        try:
            val = int(m.group(1))
            if 0 <= val <= 25:
                yoes.append(val)
        except:
            pass
            
    pattern2 = re.compile(r'experience[^.?!]{0,40}?(\d+)\s*(?:\+|-|to)?\s*(?:\d*\s*)\+?\s*(?:years?|yrs?)', re.IGNORECASE)
    matches2 = pattern2.finditer(description)
    for m in matches2:
        try:
            val = int(m.group(1))
            if 0 <= val <= 25:
                yoes.append(val)
        except:
            pass

    if not yoes:
        return True
        
    return min(yoes) <= 3

