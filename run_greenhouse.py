#!/usr/bin/env python3
"""
Fetch the latest Greenhouse jobs (posted in the last 1 hour)
across a curated list of companies.
Results are written to output/latest_jobs.json and output/latest_jobs.csv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make sure the src package is importable when running from the project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from job_resume_agent.greenhouse import GreenhouseJobExtractor

# -------------------------------------------------------------------
# Company Greenhouse board tokens  (add or remove as needed)
# -------------------------------------------------------------------
BOARDS = [
    "airbnb",
    "stripe",
    "databricks",
    "lyft",
    "doordash",
    "robinhood",
    "coinbase",
    "reddit",
    "discord",
    "figma",
    "notion",
    "anthropic",
    "openai",
    "scale",
    "anduril",
    "palantir",
    "brex",
    "plaid",
    "chime",
    "faire",
    "lattice",
    "benchling",
    "coda",
    "verkada",
    "rippling",
    "gusto",
    "zendesk",
    "klaviyo",
    "hubspot",
    "hashicorp",
]

HOURS = 1.0  # change to widen the window


def main() -> None:
    extractor = GreenhouseJobExtractor(posted_within_hours=HOURS)

    print(f"Querying {len(BOARDS)} Greenhouse boards for jobs posted in the last {HOURS:.0f} hour(s)…\n")

    all_jobs = []
    for board in BOARDS:
        try:
            jobs = extractor.collect([board])
            if jobs:
                print(f"  ✓  {board:20s}  →  {len(jobs)} job(s)")
                all_jobs.extend(jobs)
            else:
                print(f"  –  {board:20s}  →  0 jobs in the last {HOURS:.0f}h")
        except Exception as exc:
            print(f"  ✗  {board:20s}  →  ERROR: {exc}")

    print(f"\nTotal jobs found: {len(all_jobs)}\n")

    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = out_dir / "latest_jobs.json"
    json_path.write_text(
        json.dumps([j.model_dump() for j in all_jobs], indent=2),
        encoding="utf-8",
    )
    print(f"Saved JSON  → {json_path.resolve()}")

    # Write CSV
    csv_path = out_dir / "latest_jobs.csv"
    extractor.write_csv(all_jobs, csv_path)
    print(f"Saved CSV   → {csv_path.resolve()}")

    if all_jobs:
        print("\n--- Top results ---")
        for job in all_jobs[:10]:
            print(f"  [{job.company}] {job.title} | {job.location} | {job.posted_at}")


if __name__ == "__main__":
    main()
