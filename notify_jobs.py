#!/usr/bin/env python3
"""
notify_jobs.py
--------------
Hourly runner: scrapes Greenhouse boards for jobs posted in the last N hours
and sends a Slack notification with the results.

Run manually:
    python notify_jobs.py
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make src/ importable when invoked from the project root
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from job_resume_agent.greenhouse import GreenhouseJobExtractor
from job_resume_agent.smartrecruiters import SmartRecruitersJobExtractor
from job_resume_agent.slack_notifier import send_slack_notification

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
HOURS = 1.0
MAX_WORKERS = 20
NOTIFY_ON_EMPTY = False

def load_boards(filename: str) -> list[str]:
    path = ROOT_DIR / filename
    if not path.exists():
        log.warning("Could not find %s", filename)
        return []
    lines = path.read_text("utf-8").splitlines()
    return sorted(list(set(line.strip() for line in lines if line.strip())))

BOARDS = load_boards("greenhouse_boards.txt")
SMARTRECRUITERS_BOARDS = load_boards("smartrecruiters_boards.txt")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_job_key(job) -> str:
    title = getattr(job, "title", "") or ""
    company = getattr(job, "company", "") or ""
    location = getattr(job, "location", "") or ""
    url = getattr(job, "url", "") or getattr(job, "absolute_url", "") or ""
    posted_at = getattr(job, "posted_at", "") or ""
    return " | ".join([
        title.strip(),
        company.strip(),
        location.strip(),
        str(url).strip(),
        str(posted_at).strip(),
    ])


def dedupe_jobs(jobs: list) -> list:
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = get_job_key(job)
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    return unique_jobs


def process_greenhouse_board(board: str, hours: float):
    try:
        extractor = GreenhouseJobExtractor(posted_within_hours=hours)
        jobs = extractor.collect([board])
        return f"GH:{board}", jobs, None
    except Exception as exc:
        return f"GH:{board}", [], exc

def process_smartrecruiters_board(board: str, hours: float):
    try:
        extractor = SmartRecruitersJobExtractor(posted_within_hours=hours)
        jobs = extractor.collect([board])
        return f"SR:{board}", jobs, None
    except Exception as exc:
        return f"SR:{board}", [], exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_at = datetime.now(tz=timezone.utc)
    log.info("=== Hourly job scan started at %s UTC ===", run_at.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Querying %d Greenhouse boards (last %.0fh)...", len(BOARDS), HOURS)

    if not SLACK_WEBHOOK_URL:
        log.warning("SLACK_WEBHOOK_URL is not set. Slack notifications will be skipped.")

    all_jobs = []
    failures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for board in BOARDS:
            futures.append(executor.submit(process_greenhouse_board, board, HOURS))
        for board in SMARTRECRUITERS_BOARDS:
            futures.append(executor.submit(process_smartrecruiters_board, board, HOURS))

        for future in concurrent.futures.as_completed(futures):
            board, jobs, exc = future.result()
            if exc:
                failures.append((board, str(exc)))
                log.warning("  ✗  %-20s  →  ERROR: %s", board, exc)
            elif jobs:
                log.info("  ✓  %-20s  →  %d job(s)", board, len(jobs))
                all_jobs.extend(jobs)
            else:
                log.info("  –  %-20s  →  0 jobs in the last %.0fh", board, HOURS)

    all_jobs = dedupe_jobs(all_jobs)

    log.info("Total unique jobs found: %d", len(all_jobs))
    log.info("Boards with errors: %d", len(failures))

    out_dir = ROOT_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "latest_jobs.json"
    json_path.write_text(
        json.dumps(
            [job.model_dump() if hasattr(job, "model_dump") else job.__dict__ for job in all_jobs],
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    log.info("Saved JSON  → %s", json_path.resolve())

    csv_path = out_dir / "latest_jobs.csv"
    extractor_for_csv = GreenhouseJobExtractor(posted_within_hours=HOURS)
    extractor_for_csv.write_csv(all_jobs, csv_path)
    log.info("Saved CSV   → %s", csv_path.resolve())

    if SLACK_WEBHOOK_URL:
        log.info("Sending Slack notification...")
        ok = send_slack_notification(
            all_jobs,
            SLACK_WEBHOOK_URL,
            notify_on_empty=NOTIFY_ON_EMPTY,
        )
        if ok:
            log.info("✅ Slack notification sent successfully.")
        else:
            log.error("❌ Slack notification failed — check logs above.")
    else:
        log.info("Skipping Slack notification because webhook is not configured.")

    log.info("=== Hourly job scan complete ===")


if __name__ == "__main__":
    main()
