from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .config import AppConfig
from .models import JobPosting


class JobScraper:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def collect(self, sources: Iterable[str]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for source in sources:
            jobs.extend(self._collect_single(source))
        return jobs

    def _collect_single(self, source: str) -> list[JobPosting]:
        if source.startswith("http://") or source.startswith("https://"):
            return self._parse_html(
                self._fetch_url(source),
                source_name=source,
                default_url=source,
            )

        path = Path(source)
        if path.suffix.lower() == ".json":
            return self._parse_json(path)

        return self._parse_html(
            path.read_text(encoding="utf-8"),
            source_name=str(path),
            default_url=None,
        )

    def _fetch_url(self, url: str) -> str:
        response = requests.get(
            url,
            headers={"User-Agent": self.config.user_agent},
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    def _parse_json(self, path: Path) -> list[JobPosting]:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return [JobPosting(**row) for row in rows]

    def _parse_html(self, html: str, source_name: str, default_url: str | None) -> list[JobPosting]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("[data-job-card], .job-card, article.job, li.job")
        jobs: list[JobPosting] = []

        for card in cards:
            title = self._text(card.select_one("[data-job-title], .job-title, h2, h3"))
            company = self._text(card.select_one("[data-company], .company"))
            location = self._text(card.select_one("[data-location], .location")) or "Unknown"
            description = self._text(
                card.select_one("[data-description], .description, .job-description, p")
            )
            link_node = card.select_one("a[href]")
            url = link_node.get("href") if link_node else default_url
            tags = [node.get_text(" ", strip=True) for node in card.select(".tag, .skill, [data-tag]")]

            if not title or not company or not description:
                continue

            jobs.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=description,
                    source=source_name,
                    tags=tags,
                )
            )
        return jobs

    @staticmethod
    def _text(node) -> str:
        return node.get_text(" ", strip=True) if node else ""

