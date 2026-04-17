#!/usr/bin/env python3
"""
notify_jobs.py
--------------
Hourly runner: scrapes Greenhouse boards for jobs posted in the last 1 hour
and sends a Slack notification with the results.

Run manually:
    python notify_jobs.py

Or let launchd / cron trigger it every hour automatically.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make src/ importable when invoked from the project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from job_resume_agent.greenhouse import GreenhouseJobExtractor
from job_resume_agent.slack_notifier import send_slack_notification

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

import os

import os
import sys

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# If no webhook is provided, we can either exit or continue without sending a message.
if not SLACK_WEBHOOK_URL:
    print("Warning: SLACK_WEBHOOK_URL environment variable is not set. Slack notifications will be skipped.", file=sys.stderr)


HOURS = 1.0  # look-back window

BOARDS = [
    # --- Verified working Greenhouse board tokens ---
    "airbnb",
    "stripe",
    "databricks",
    "lyft",
    "doordashusa",       # doordash
    "robinhood",
    "coinbase",
    "reddit",
    "discord",
    "figma",
    "anthropic",
    "scaleai",           # scale ai
    "andurilindustries", # anduril
    "brex",
    "chime",
    "faire",
    "lattice",
    "verkada",
    "gusto",
    "klaviyo",
    "hubspot",
    # Note: notion, openai, palantir, plaid, benchling,
    # coda, rippling, zendesk, hashicorp do NOT use Greenhouse.
]

# Set to True to send a Slack message even when 0 jobs are found
NOTIFY_ON_EMPTY = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,   # launchd routes stdout → notify_jobs.log
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    run_at = datetime.now(tz=timezone.utc)
    log.info(
        "=== Hourly job scan started at %s UTC ===",
        run_at.strftime("%Y-%m-%d %H:%M:%S"),
    )

    extractor = GreenhouseJobExtractor(posted_within_hours=HOURS)

    log.info("Querying %d Greenhouse boards (last %.0fh)…", len(BOARDS), HOURS)

    all_jobs = []
    for board in BOARDS:
        try:
            jobs = extractor.collect([board])
            if jobs:
                log.info("  ✓  %-20s  →  %d job(s)", board, len(jobs))
                all_jobs.extend(jobs)
            else:
                log.info("  –  %-20s  →  0 jobs in the last %.0fh", board, HOURS)
        except Exception as exc:  # noqa: BLE001
            log.warning("  ✗  %-20s  →  ERROR: %s", board, exc)

    log.info("Total jobs found: %d", len(all_jobs))

    # ------------------------------------------------------------------
    # Persist results
    # ------------------------------------------------------------------
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "latest_jobs.json"
    json_path.write_text(
        json.dumps([j.model_dump() for j in all_jobs], indent=2),
        encoding="utf-8",
    )
    log.info("Saved JSON  → %s", json_path.resolve())

    csv_path = out_dir / "latest_jobs.csv"
    extractor.write_csv(all_jobs, csv_path)
    log.info("Saved CSV   → %s", csv_path.resolve())

    # ------------------------------------------------------------------
    # Send Slack notification
    # ------------------------------------------------------------------
    log.info("Sending Slack notification…")
    ok = send_slack_notification(
        all_jobs,
        SLACK_WEBHOOK_URL,
        notify_on_empty=NOTIFY_ON_EMPTY,
    )
    if ok:
        log.info("✅  Slack notification sent successfully.")
    else:
        log.error("❌  Slack notification failed — check logs above.")

    log.info("=== Hourly job scan complete ===")


if __name__ == "__main__":
    main()
