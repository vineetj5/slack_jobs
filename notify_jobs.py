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
from job_resume_agent.lever import LeverJobExtractor
from job_resume_agent.ashby import AshbyJobExtractor
from job_resume_agent.workday import WorkdayJobExtractor
from job_resume_agent.slack_notifier import send_slack_notification

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
SLACK_INDIA_WEBHOOK_URL = os.environ.get("SLACK_INDIA_WEBHOOK_URL", "").strip()
DEFAULT_HOURS = 1.0
MAX_WORKERS = 20
NOTIFY_ON_EMPTY = False
LAST_RUN_FILE = ROOT_DIR / "last_run.txt"


def compute_hours_since_last_run() -> float:
    """Read the last run timestamp from last_run.txt and return hours elapsed.
    Falls back to DEFAULT_HOURS if the file doesn't exist or can't be parsed."""
    if not LAST_RUN_FILE.exists():
        return DEFAULT_HOURS
    try:
        raw = LAST_RUN_FILE.read_text("utf-8").strip()
        last_run = datetime.fromisoformat(raw)
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(tz=timezone.utc) - last_run).total_seconds() / 3600.0
        # Clamp: at least 0.25h (15 min) and at most 24h to avoid huge windows
        return max(0.25, min(elapsed, 24.0))
    except (ValueError, OSError):
        return DEFAULT_HOURS


def save_last_run_time(run_at: datetime) -> None:
    """Persist the current run timestamp to last_run.txt."""
    LAST_RUN_FILE.write_text(run_at.isoformat(), encoding="utf-8")

def load_boards(filename: str) -> list[str]:
    path = ROOT_DIR / filename
    if not path.exists():
        log.warning("Could not find %s", filename)
        return []
    lines = path.read_text("utf-8").splitlines()
    return sorted(list(set(line.strip() for line in lines if line.strip())))

BOARDS = load_boards("greenhouse_boards.txt")
SMARTRECRUITERS_BOARDS = load_boards("smartrecruiters_boards.txt")
LEVER_BOARDS = load_boards("lever_boards.txt")
ASHBY_BOARDS = load_boards("ashby_boards.txt")
WORKDAY_BOARDS = load_boards("workday_boards.txt")

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

def process_lever_board(board: str, hours: float):
    try:
        extractor = LeverJobExtractor(posted_within_hours=hours)
        jobs = extractor.collect([board])
        return f"LV:{board}", jobs, None
    except Exception as exc:
        return f"LV:{board}", [], exc

def process_ashby_board(board: str, hours: float):
    try:
        extractor = AshbyJobExtractor(posted_within_hours=hours)
        jobs = extractor.collect([board])
        return f"AS:{board}", jobs, None
    except Exception as exc:
        return f"AS:{board}", [], exc

def process_workday_board(board: str, hours: float):
    try:
        extractor = WorkdayJobExtractor(posted_within_hours=hours)
        jobs = extractor.collect([board])
        return f"WD:{board}", jobs, None
    except Exception as exc:
        return f"WD:{board}", [], exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_at = datetime.now(tz=timezone.utc)
    HOURS = compute_hours_since_last_run()
    log.info("=== Job scan started at %s UTC ===", run_at.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Scrape window: %.2f hours (since last run)", HOURS)
    log.info("Querying %d Greenhouse boards...", len(BOARDS))
    log.info("Querying %d SmartRecruiters boards...", len(SMARTRECRUITERS_BOARDS))
    log.info("Querying %d Lever boards...", len(LEVER_BOARDS))
    log.info("Querying %d Ashby boards...", len(ASHBY_BOARDS))
    log.info("Querying %d Workday boards...", len(WORKDAY_BOARDS))

    if not SLACK_WEBHOOK_URL:
        log.warning("SLACK_WEBHOOK_URL is not set. USA Slack notifications will be skipped.")
    if not SLACK_INDIA_WEBHOOK_URL:
        log.warning("SLACK_INDIA_WEBHOOK_URL is not set. India Slack notifications will be skipped.")

    all_jobs = []
    failures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for board in BOARDS:
            futures.append(executor.submit(process_greenhouse_board, board, HOURS))
        for board in SMARTRECRUITERS_BOARDS:
            futures.append(executor.submit(process_smartrecruiters_board, board, HOURS))
        for board in LEVER_BOARDS:
            futures.append(executor.submit(process_lever_board, board, HOURS))
        for board in ASHBY_BOARDS:
            futures.append(executor.submit(process_ashby_board, board, HOURS))
        for board in WORKDAY_BOARDS:
            futures.append(executor.submit(process_workday_board, board, HOURS))

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

    usa_jobs = [j for j in all_jobs if j.region == "USA"]
    india_jobs = [j for j in all_jobs if j.region == "INDIA"]

    log.info("Total unique jobs found: %d (%d USA, %d India)", len(all_jobs), len(usa_jobs), len(india_jobs))
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
        log.info("Sending USA Slack notification (%d jobs)...", len(usa_jobs))
        ok = send_slack_notification(
            usa_jobs,
            SLACK_WEBHOOK_URL,
            notify_on_empty=NOTIFY_ON_EMPTY,
        )
        if ok:
            log.info("✅ USA Slack notification sent successfully.")
        else:
            log.error("❌ USA Slack notification failed — check logs above.")
    else:
        log.info("Skipping USA Slack notification because webhook is not configured.")

    if SLACK_INDIA_WEBHOOK_URL:
        log.info("Sending India Slack notification (%d jobs)...", len(india_jobs))
        ok_india = send_slack_notification(
            india_jobs,
            SLACK_INDIA_WEBHOOK_URL,
            notify_on_empty=NOTIFY_ON_EMPTY,
        )
        if ok_india:
            log.info("✅ India Slack notification sent successfully.")
        else:
            log.error("❌ India Slack notification failed — check logs above.")
    else:
        log.info("Skipping India Slack notification because webhook is not configured.")

    # Persist the current run time for next invocation
    save_last_run_time(run_at)
    log.info("Saved last run time: %s", run_at.isoformat())
    log.info("=== Job scan complete ===")


if __name__ == "__main__":
    main()
