# Job Notifier

A Python job-board scanner that finds recently posted early-career software, data, AI/ML, analytics, backend, DevOps, and related roles, writes the results locally, and sends Slack alerts.

The project now keeps only the job notification flow. The previous resume-tailoring agent workflow has been removed.

## What It Scans

The main runner, `notify_jobs.py`, checks:

- Greenhouse boards from `greenhouse_boards.txt`
- SmartRecruiters boards from `smartrecruiters_boards.txt`
- Lever boards from `lever_boards.txt`
- Ashby boards from `ashby_boards.txt`
- Workday boards from `workday_boards.txt`
- Amazon Jobs
- Google Careers
- Meta Careers

Each extractor normalizes results into a shared `JobPosting` model, filters by recency, target region, role title, and experience level, then returns jobs to the notifier.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Optional Slack webhook environment variables:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export SLACK_INDIA_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

If a webhook is not set, that Slack notification is skipped, but JSON and CSV output are still written.

## Run The Notifier

```bash
python notify_jobs.py
```

The script:

1. Reads `last_run.txt` to determine the scan window.
2. Loads all board list files.
3. Scrapes all providers concurrently.
4. Deduplicates jobs.
5. Splits jobs into USA and India notifications.
6. Writes `output/latest_jobs.json` and `output/latest_jobs.csv`.
7. Sends Slack notifications when webhook URLs are configured.
8. Updates `last_run.txt` for the next run.

## Refresh Board Lists

Use `sync_boards.py` after editing `companies.txt`:

```bash
python sync_boards.py
```

It probes each company against supported job-board APIs and rewrites the provider-specific board files.

## Greenhouse-Only Runner

For a smaller manual scan, `run_greenhouse.py` checks a curated in-file Greenhouse board list:

```bash
python run_greenhouse.py
```

## Outputs

- `output/latest_jobs.json`: full normalized job payloads
- `output/latest_jobs.csv`: spreadsheet-friendly job list
- `last_run.txt`: timestamp used to compute the next incremental scan window

## Project Layout

```text
notify_jobs.py                 # Main multi-provider Slack notifier
sync_boards.py                 # Rebuilds provider board lists from companies.txt
run_greenhouse.py              # Manual Greenhouse-only scanner
src/job_resume_agent/
  amazon.py
  ashby.py
  config.py
  google.py
  greenhouse.py
  lever.py
  meta.py
  models.py
  slack_notifier.py
  smartrecruiters.py
  workday.py
tests/
  test_greenhouse.py
```
