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
import concurrent.futures

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
    "99",
    "accuweather",
    "action",
    "administrative",
    "adyen",
    "affirm",
    "aftership",
    "agency",
    "airbnb",
    "airtable",
    "alchemy",
    "algolia",
    "align",
    "alku",
    "alpaca",
    "amplitude",
    "amwell",
    "android",
    "andurilindustries",
    "anthropic",
    "apollo",
    "apolloio",
    "applications",
    "apptronik",
    "archer",
    "array",
    "asana",
    "attentive",
    "australia",
    "automated",
    "aweber",
    "bandwidth",
    "basic",
    "betterment",
    "bird",
    "bitly",
    "bitmex",
    "bitwarden",
    "blacksky",
    "block",
    "blockchain",
    "branch",
    "brandwatch",
    "brave",
    "brex",
    "bugcrowd",
    "buildkite",
    "bungie",
    "bybit",
    "cabify",
    "calicolabs",
    "calm",
    "canto",
    "capellaspace",
    "carbon",
    "careem",
    "carta",
    "celigo",
    "censys",
    "check",
    "checkr",
    "chicago",
    "chime",
    "circleci",
    "clarifai",
    "clear",
    "client",
    "cloudflare",
    "cloverly",
    "codex",
    "cognism",
    "coinbase",
    "colombia",
    "colorado",
    "commercetools",
    "community",
    "commvault",
    "company",
    "consensys",
    "constantcontact",
    "contentful",
    "contracts",
    "convene",
    "corp",
    "coursera",
    "crisp",
    "dagsterlabs",
    "dashlane",
    "databricks",
    "datacamp",
    "datadog",
    "dbtlabsinc",
    "delete",
    "denver",
    "didi",
    "discord",
    "disney",
    "domains",
    "doordashusa",
    "dragons",
    "dropbox",
    "druva",
    "duolingo",
    "education",
    "embed",
    "embedded",
    "engage",
    "engine",
    "epicgames",
    "events",
    "ever",
    "example",
    "explore",
    "external",
    "faire",
    "fastly",
    "fetch",
    "figma",
    "finance",
    "find",
    "fingerprint",
    "fivetran",
    "flatironhealth",
    "flexport",
    "flickr",
    "focused",
    "forward",
    "found",
    "freelancers",
    "freenome",
    "funds",
    "galileo",
    "gemini",
    "genesis",
    "genius",
    "getyourguide",
    "ghost",
    "ginkgobioworks",
    "gitlab",
    "glide",
    "globalizationpartners",
    "gocardless",
    "godaddy",
    "grafanalabs",
    "grayscale",
    "groww",
    "guild",
    "gusto",
    "hackerrank",
    "harvard",
    "helium",
    "help",
    "highradius",
    "honeycomb",
    "hubspot",
    "icon",
    "imgur",
    "impact",
    "india",
    "indiecampers",
    "industriouslabs",
    "inflectionai",
    "insider",
    "instacart",
    "instructors",
    "insurance",
    "integrated",
    "integrations",
    "inter",
    "intercom",
    "international",
    "ireland",
    "jcdecaux",
    "justworks",
    "kaggle",
    "kasa",
    "kayak",
    "keen",
    "klaviyo",
    "known",
    "korea",
    "lastpass",
    "later",
    "latitude",
    "lattice",
    "launchdarkly",
    "lead",
    "leap",
    "lightmatter",
    "link",
    "linkedin",
    "lithic",
    "location",
    "logos",
    "london",
    "lviv",
    "lyft",
    "magic",
    "make",
    "markets",
    "marqeta",
    "masterclass",
    "mattermost",
    "maven",
    "mcafee",
    "medium",
    "mercury",
    "merge",
    "method",
    "metro",
    "metropolis",
    "mighty",
    "mixpanel",
    "mobility",
    "mongodb",
    "monzo",
    "morty",
    "mozilla",
    "n26",
    "name",
    "national",
    "neo4j",
    "netherlands",
    "netlify",
    "netskope",
    "network",
    "neuralink",
    "newrelic",
    "newton",
    "nexus",
    "nintendo",
    "nothing",
    "observeai",
    "okta",
    "onemedical",
    "opendoor",
    "openly",
    "orca",
    "outschool",
    "pandadoc",
    "parallel",
    "payoneer",
    "paypay",
    "peloton",
    "philippines",
    "pingidentity",
    "pinterest",
    "place",
    "planetlabs",
    "point72",
    "portugal",
    "postman",
    "postscript",
    "privacy",
    "processing",
    "public",
    "purple",
    "quip",
    "radar",
    "range",
    "reach",
    "ready",
    "reddit",
    "redwoodmaterials",
    "relativity",
    "remote",
    "residential",
    "revel",
    "riotgames",
    "ripple",
    "robinhood",
    "roblox",
    "rocketlab",
    "rooted",
    "rubrik",
    "salesloft",
    "sanmar",
    "scaleai",
    "scanner",
    "seamlessai",
    "seatgeek",
    "secure",
    "send",
    "showpad",
    "skyscanner",
    "smartlabs",
    "smartpay",
    "smartsheet",
    "smsbump",
    "snorkelai",
    "sofi",
    "someone",
    "sothebys",
    "space",
    "spacex",
    "spain",
    "spin",
    "spire",
    "sproutsocial",
    "squarespace",
    "stabilityai",
    "stackexchange",
    "staging",
    "statement",
    "stitch",
    "stripe",
    "sunrise",
    "sunset",
    "superset",
    "support",
    "switzerland",
    "system",
    "systems",
    "taiwan",
    "technical",
    "technology",
    "telesign",
    "tenableinc",
    "test",
    "testing",
    "tetra",
    "toast",
    "tomorrow",
    "transcarent",
    "tripadvisor",
    "trivago",
    "trove",
    "truelayer",
    "trustpilot",
    "turing",
    "twilio",
    "twitch",
    "udemy",
    "ultimate",
    "unity3d",
    "university",
    "unlock",
    "upstart",
    "upwork",
    "vacasa",
    "vast",
    "vendor",
    "vercel",
    "verkada",
    "verse",
    "via",
    "vonage",
    "vtex",
    "webflow",
    "wheelhouse",
    "wikimedia",
    "wolt",
    "workato",
    "wrike",
    "yotpo",
    "zenoti",
    "zenrows",
    "ziprecruiter",
    "zocdoc",
    "zoominfo",
    "zscaler",
    "zuora"
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
    
    def process_board(board):
        try:
            jobs = extractor.collect([board])
            return board, jobs, None
        except Exception as exc:
            return board, None, exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_board, board): board for board in BOARDS}
        for future in concurrent.futures.as_completed(futures):
            board, jobs, exc = future.result()
            if exc:
                log.warning("  ✗  %-20s  →  ERROR: %s", board, exc)
            elif jobs:
                log.info("  ✓  %-20s  →  %d job(s)", board, len(jobs))
                all_jobs.extend(jobs)
            else:
                log.info("  –  %-20s  →  0 jobs in the last %.0fh", board, HOURS)

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
