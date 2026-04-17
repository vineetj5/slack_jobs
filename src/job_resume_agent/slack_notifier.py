"""
slack_notifier.py
-----------------
Sends Greenhouse job alerts to a Slack channel via an Incoming Webhook.
Uses Block Kit for rich, readable formatting.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

import requests

from .models import JobPosting

logger = logging.getLogger(__name__)

# Maximum jobs to include in a single Slack message batch
# (keeps messages readable and avoids hitting Slack's 50-block limit)
_MAX_JOBS_PER_MESSAGE = 10


def _format_posted_at(posted_at: str | None) -> str:
    """Return a human-friendly relative time string."""
    if not posted_at:
        return "unknown time"
    try:
        ts = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        now = datetime.now(tz=timezone.utc)
        diff_minutes = int((now - ts).total_seconds() / 60)
        if diff_minutes < 2:
            return "just now"
        if diff_minutes < 60:
            return f"{diff_minutes}m ago"
        hours = diff_minutes // 60
        return f"{hours}h ago"
    except (ValueError, AttributeError):
        return posted_at


def _build_job_block(job: JobPosting) -> list[dict]:
    """Return Block Kit blocks for a single job posting."""
    company_display = job.company.upper()
    tags_text = f"  •  _{', '.join(job.tags)}_" if job.tags else ""
    location = job.location or "Remote / Unknown"
    posted = _format_posted_at(job.posted_at)

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*<{job.url}|{job.title}>*\n"
                    f":office: *{company_display}*{tags_text}\n"
                    f":round_pushpin: {location}   :clock1: {posted}"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Apply →"},
                "url": job.url or "https://greenhouse.io",
                "action_id": f"apply_{job.company}_{hash(job.title) % 9999:04d}",
            },
        },
        {"type": "divider"},
    ]
    return blocks


def _build_header_block(job_count: int, run_at: datetime) -> list[dict]:
    """Return the header Block Kit section."""
    time_str = run_at.strftime("%b %d, %Y  %H:%M UTC")
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚀  {job_count} New Job{'s' if job_count != 1 else ''} in the Last Hour",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":calendar: Scanned at *{time_str}*  |  Greenhouse boards",
                }
            ],
        },
        {"type": "divider"},
    ]


def _build_no_jobs_block(run_at: datetime) -> list[dict]:
    """Block to send when no new jobs are found."""
    time_str = run_at.strftime("%b %d, %Y  %H:%M UTC")
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":mag: *No new matching jobs in the last hour.*\n"
                    f"_Scanned at {time_str} — will check again next hour._"
                ),
            },
        }
    ]


def send_slack_notification(
    jobs: Iterable[JobPosting],
    webhook_url: str,
    *,
    notify_on_empty: bool = False,
) -> bool:
    """
    Post job alerts to Slack via *webhook_url*.

    Parameters
    ----------
    jobs:
        The job postings to announce.
    webhook_url:
        Slack Incoming Webhook URL.
    notify_on_empty:
        If True, post a "no new jobs" message when *jobs* is empty.

    Returns
    -------
    bool
        True if all payloads were sent successfully.
    """
    job_list = list(jobs)
    run_at = datetime.now(tz=timezone.utc)
    success = True

    if not job_list:
        if notify_on_empty:
            payload = {"blocks": _build_no_jobs_block(run_at)}
            success = _post(webhook_url, payload)
        else:
            logger.info("No jobs to notify about — skipping Slack message.")
        return success

    # Split into batches of _MAX_JOBS_PER_MESSAGE
    for batch_start in range(0, len(job_list), _MAX_JOBS_PER_MESSAGE):
        batch = job_list[batch_start : batch_start + _MAX_JOBS_PER_MESSAGE]

        blocks: list[dict] = []

        # Only put the header on the first batch
        if batch_start == 0:
            blocks += _build_header_block(len(job_list), run_at)

        for job in batch:
            blocks += _build_job_block(job)

        # Slack limits blocks to 50 per message
        blocks = blocks[:50]

        payload = {
            "text": f"🚀 {len(job_list)} new job(s) posted in the last hour on Greenhouse!",
            "blocks": blocks,
        }

        if not _post(webhook_url, payload):
            success = False

    return success


def _post(webhook_url: str, payload: dict) -> bool:
    """POST *payload* to *webhook_url* and return True on success."""
    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200 and resp.text == "ok":
            logger.info("Slack notification sent successfully.")
            return True
        logger.error(
            "Slack webhook returned %s: %s", resp.status_code, resp.text
        )
        return False
    except requests.RequestException as exc:
        logger.error("Failed to send Slack notification: %s", exc)
        return False
