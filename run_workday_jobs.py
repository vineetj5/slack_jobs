#!/usr/bin/env python3
"""
Standalone Workday scanner.

Reads company Workday URLs from a YAML file, queries Workday's CXS API, applies
the existing job-notifier role/location/experience filters, and writes JSON/CSV
outputs under output/.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from job_resume_agent.config import AppConfig
from job_resume_agent.greenhouse import (
    GREENHOUSE_ROLE_TERMS,
    check_experience,
    get_target_region,
    role_matches_title,
    role_matches_title_india,
)
from job_resume_agent.models import JobPosting

DEFAULT_YAML = ROOT_DIR / "workday_companies.yaml"
DEFAULT_OUTPUT_JSON = ROOT_DIR / "output" / "workday_jobs.json"
DEFAULT_OUTPUT_CSV = ROOT_DIR / "output" / "workday_jobs.csv"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkdayFeed:
    company: str
    tenant: str
    site: str
    origin: str
    api_base: str
    public_base: str
    search_text: str = ""
    applied_facets: dict[str, list[str]] | None = None


def parse_workday_url(company: str, url: str) -> WorkdayFeed:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid Workday URL for {company}: {url}")

    host = parsed.netloc
    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    search_text = " ".join(query.pop("q", []) + query.pop("searchText", [])).strip()
    applied_facets = {key: values for key, values in query.items() if values}

    if host.endswith(".myworkdayjobs.com"):
        tenant = host.split(".")[0]
        if len(path_parts) >= 5 and path_parts[:2] == ["wday", "cxs"]:
            tenant = path_parts[2]
            site = path_parts[3]
        else:
            if path_parts and _looks_like_locale(path_parts[0]):
                path_parts = path_parts[1:]
            if not path_parts:
                raise ValueError(f"Could not find Workday site in URL for {company}: {url}")
            site = path_parts[0]

        origin = f"{parsed.scheme}://{host}"
        api_base = f"{origin}/wday/cxs/{tenant}/{site}"
        public_base = f"{origin}/{site}"
        return WorkdayFeed(
            company=company,
            tenant=tenant,
            site=site,
            origin=origin,
            api_base=api_base,
            public_base=public_base,
            search_text=search_text,
            applied_facets=applied_facets,
        )

    if host.endswith(".myworkdaysite.com"):
        if len(path_parts) < 3 or path_parts[0] != "recruiting":
            raise ValueError(f"Could not find Workday tenant/site in URL for {company}: {url}")
        tenant = path_parts[1]
        site = path_parts[2]
        origin = f"{parsed.scheme}://{host}"
        api_base = f"{origin}/wday/cxs/{tenant}/{site}"
        public_base = f"{origin}/recruiting/{tenant}/{site}"
        return WorkdayFeed(
            company=company,
            tenant=tenant,
            site=site,
            origin=origin,
            api_base=api_base,
            public_base=public_base,
            search_text=search_text,
            applied_facets=applied_facets,
        )

    raise ValueError(f"Unsupported Workday host for {company}: {url}")


def _looks_like_locale(value: str) -> bool:
    return len(value) == 5 and value[2] == "-"


def load_feeds(path: Path) -> list[WorkdayFeed]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    companies = payload.get("companies", [])
    feeds: list[WorkdayFeed] = []

    for item in companies:
        if not item or item.get("enabled", True) is False:
            continue

        company = str(item.get("name", "")).strip()
        urls = item.get("urls") or item.get("url")
        if not company or not urls:
            continue
        if isinstance(urls, str):
            urls = [urls]

        for url in urls:
            try:
                feeds.append(parse_workday_url(company, str(url)))
            except ValueError as exc:
                log.warning("%s", exc)

    return feeds


class WorkdayUrlScanner:
    def __init__(
        self,
        config: AppConfig | None = None,
        role_terms: Iterable[str] = GREENHOUSE_ROLE_TERMS,
        posted_within_hours: float = 24.0,
        max_pages: int = 20,
        page_size: int = 100,
        max_workers: int = 8,
    ) -> None:
        self.config = config or AppConfig()
        self.role_terms = list(dict.fromkeys(role_terms))
        self.posted_within_hours = posted_within_hours
        self.max_pages = max_pages
        self.page_size = page_size
        self.max_workers = max_workers

    def collect(self, feeds: Iterable[WorkdayFeed]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        seen_urls: set[str] = set()
        feed_list = list(feeds)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_feed = {
                executor.submit(self._collect_feed, feed): feed
                for feed in feed_list
            }
            for future in concurrent.futures.as_completed(future_to_feed):
                feed = future_to_feed[future]
                try:
                    feed_jobs = future.result()
                except Exception as exc:
                    log.warning("%s failed: %s", feed.company, exc)
                    continue

                for job in feed_jobs:
                    dedupe_key = job.url or f"{job.company}:{job.title}:{job.location}"
                    if dedupe_key in seen_urls:
                        continue
                    seen_urls.add(dedupe_key)
                    jobs.append(job)

        return jobs

    def _collect_feed(self, feed: WorkdayFeed) -> list[JobPosting]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.config.user_agent,
        }
        list_url = f"{feed.api_base}/jobs"
        jobs: list[JobPosting] = []

        for page in range(self.max_pages):
            payload = {
                "appliedFacets": feed.applied_facets or {},
                "limit": self.page_size,
                "offset": page * self.page_size,
                "searchText": feed.search_text,
            }
            try:
                response = requests.post(
                    list_url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.request_timeout_seconds,
                )
                if response.status_code != 200:
                    log.warning("%s returned HTTP %s", feed.company, response.status_code)
                    break
                data = response.json()
            except requests.RequestException as exc:
                log.warning("%s request failed: %s", feed.company, exc)
                break

            rows = data.get("jobPostings", [])
            if not rows:
                break

            for row in rows:
                job = self._build_job(feed, row, headers)
                if job:
                    jobs.append(job)

            total = data.get("total")
            if isinstance(total, int) and (page + 1) * self.page_size >= total:
                break
            if len(rows) < self.page_size:
                break

        return jobs

    def _build_job(self, feed: WorkdayFeed, row: dict, headers: dict) -> JobPosting | None:
        title = row.get("title") or ""
        posted_on = str(row.get("postedOn", "")).lower()
        if self.posted_within_hours <= 24 and "today" not in posted_on:
            return None

        location = row.get("locationsText") or "Unknown"
        region = get_target_region(location)
        if not region:
            return None

        if region == "INDIA":
            if not role_matches_title_india(title):
                return None
        elif not role_matches_title(title, self.role_terms):
            return None

        external_path = row.get("externalPath")
        if not external_path:
            return None

        description = self._fetch_description(feed, external_path, headers)
        if description is None:
            return None
        if not check_experience(description, region=region, title=title):
            return None

        return JobPosting(
            title=title,
            company=feed.company,
            location=location,
            url=f"{feed.public_base}{external_path}",
            description=description,
            source=f"workday:{feed.tenant}/{feed.site}",
            posted_at=row.get("postedOn"),
            tags=[row.get("hiringOrganization")] if row.get("hiringOrganization") else [],
            region=region,
        )

    def _fetch_description(self, feed: WorkdayFeed, external_path: str, headers: dict) -> str | None:
        detail_url = f"{feed.api_base}{external_path}"
        try:
            response = requests.get(
                detail_url,
                headers=headers,
                timeout=self.config.request_timeout_seconds,
            )
            if response.status_code != 200:
                return None
            data = response.json()
        except requests.RequestException:
            return None

        html = data.get("jobDescription", "")
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def write_json(jobs: Iterable[JobPosting], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([job.model_dump() for job in jobs], indent=2),
        encoding="utf-8",
    )


def write_csv(jobs: Iterable[JobPosting], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "title",
                "company",
                "location",
                "region",
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
                    "region": job.region,
                    "url": job.url,
                    "source": job.source,
                    "posted_at": job.posted_at,
                    "tags": ", ".join(job.tags),
                    "description": job.description,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Workday jobs from a YAML company URL list.")
    parser.add_argument("--companies-yaml", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()
    started = datetime.now(tz=timezone.utc)

    feeds = load_feeds(args.companies_yaml)
    log.info("Loaded %d Workday feed(s) from %s", len(feeds), args.companies_yaml)

    scanner = WorkdayUrlScanner(
        posted_within_hours=args.hours,
        max_pages=args.max_pages,
        page_size=args.page_size,
        max_workers=args.max_workers,
    )
    jobs = scanner.collect(feeds)
    write_json(jobs, args.output_json)
    write_csv(jobs, args.output_csv)

    log.info("Found %d matching Workday job(s)", len(jobs))
    log.info("Saved JSON to %s", args.output_json.resolve())
    log.info("Saved CSV to %s", args.output_csv.resolve())
    log.info("Completed in %.1fs", (datetime.now(tz=timezone.utc) - started).total_seconds())


if __name__ == "__main__":
    main()
