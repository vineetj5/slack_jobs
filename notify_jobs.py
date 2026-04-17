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

# Merged from your existing script and the additional board list you provided.
# Using sorted(set(...)) removes duplicates automatically.
BOARDS = sorted({
    "15five", "99", "abnormal", "accuweather", "action", "administrative",
    "adyen", "affirm", "aftership", "agency", "airbnb", "airtable",
    "alchemy", "algolia", "align", "alku", "aloyoga", "alpac", "alpaca",
    "alteryx", "amazon", "amplitude", "amwell", "anduril", "andurilindustries",
    "android", "angellist", "anthropic", "anyscale", "apollo", "apolloio",
    "applications", "appliedintuition", "apptronik", "arc", "arcadia",
    "archer", "armory", "array", "artifact", "asana", "ashby", "astronomer",
    "atlassian", "attentive", "augury", "australia", "automated", "avenir",
    "aweber", "axiom", "bandwidth", "baseten", "basic", "beam", "beReal",
    "benchling", "bentoml", "betterhelp", "betterment", "bigeye", "bird",
    "bison", "bitgo", "bitly", "bitmex", "bitwarden", "blacksky",
    "blameless", "block", "blockchain", "bluesky", "bolt", "bolttech",
    "bond", "brave", "branch", "brandwatch", "brex", "brighthealth",
    "brightwheel", "browserstack", "bugcrowd", "buildkite", "bungie",
    "bybit", "bytedance", "cabify", "calendly", "calicolabs", "calm",
    "canva", "canto", "capellaspace", "capsule", "carbon", "carbonhealth",
    "careem", "carta", "celigo", "censys", "census", "cerebral", "character",
    "chargebee", "chartHop", "check", "checkout", "checkr", "chicago",
    "chime", "chiliPiper", "circle", "circleci", "clari", "clarifai",
    "clear", "clearbit", "clerk", "client", "clickhouse", "cloudflare",
    "cloudsmith", "clubhouse", "cloverly", "coda", "codacy", "coder",
    "codex", "codium", "cognism", "coinbase", "cointracker", "cohere",
    "cockroach", "colombia", "color", "colorado", "commercetools",
    "commonroom", "community", "commvault", "company", "confuent", "confluent",
    "consensys", "constantcontact", "contentful", "continue", "contracts",
    "convex", "convene", "convoy", "coda", "courier", "coursera", "craft",
    "crisp", "crowdstrike", "cruise", "cultureamp", "cursor", "dagster",
    "dagsterlabs", "dandy", "dashlane", "databricks", "datacamp", "dataiku",
    "datadog", "dbt", "dbtlabsinc", "deel", "delete", "deliverr", "denver",
    "descript", "didi", "digger", "discord", "disco", "disney", "domains",
    "domo", "doordash", "doordashusa", "dovetail", "doximity", "dragons",
    "drata", "drift", "dropbox", "druva", "duolingo", "dune", "elastic",
    "education", "embed", "embedded", "engage", "engine", "eppo",
    "epicgames", "equinix", "ever", "everlaw", "events", "example",
    "expel", "explore", "explorium", "external", "faire", "fal", "fast",
    "fastly", "fastspring", "feather", "fetch", "figma", "figment", "finance",
    "find", "fingerprint", "finix", "fireblocks", "firebolt", "fivetran",
    "flickr", "flatiron", "flatironhealth", "flagship", "fleetsmith", "flexport",
    "flow", "flyio", "flywheel", "focused", "folk", "formlabs", "forward",
    "found", "framer", "freelancers", "freshworks", "freenome", "front",
    "fullstory", "funds", "galileo", "gametime", "gem", "gemini", "generative",
    "genesis", "genius", "getaround", "getir", "getyourguide", "ghost", "ginkgobioworks",
    "gitlab", "glide", "glitch", "glossier", "gocardless", "godaddy", "gong",
    "gorillas", "gorgias", "goPuff", "grafanalabs", "grammarly", "graphite",
    "grayscale", "greenhouse", "grid", "groq", "groww", "growthbook", "gusto",
    "guild", "hackerrank", "harness", "harvard", "hashicorp", "hashnode",
    "hazelcast", "headspace", "headway", "heap", "heaven", "helium", "help",
    "helpScout", "hevo", "hex", "hibob", "highradius", "hims", "homebase",
    "honeycomb", "hopper", "hubspot", "huggingface", "hyper", "immuta",
    "impact", "improbable", "india", "indiecampers", "industriouslabs",
    "inflectionai", "influxdata", "instabase", "instacart", "instructors",
    "insurance", "integrated", "integrations", "inter", "intercom", "international",
    "invisible", "ireland", "ironclad", "iterable", "jcdecaux", "jina", "jokr",
    "jump", "justworks", "kaggle", "kasa", "kayak", "kayako", "keen",
    "keeptruckin", "ketch", "kevel", "king", "klaviyo", "knock", "known",
    "konduit", "korea", "kraken", "kustomer", "laminar", "lastpass", "later",
    "latitude", "lattice", "launchdarkly", "lacework", "lead", "ledger", "leap",
    "lever", "lightricks", "lightmatter", "lime", "linear", "linearb", "link",
    "linkedin", "lithic", "livekit", "location", "logos", "london", "looker",
    "loom", "luma", "lviv", "lyft", "lyra", "magic", "magicbell", "make",
    "mapbox", "markets", "marqeta", "masterclass", "mattermost", "maven", "mcafee",
    "medium", "meilisearch", "mem", "memgraph", "mercury", "merge", "meroxa",
    "metadatabase", "metadata", "method", "metro", "metronome", "metropolis",
    "mezmo", "midjourney", "mighty", "mindbody", "mintlify", "miro", "mixpanel",
    "mobility", "modal", "mode", "monday", "mongodb", "modernhealth", "monzo",
    "moonpay", "morty", "motherduck", "motive", "mparticle", "multiplier", "mux",
    "mutiny", "mygreenhouse", "n26", "name", "nango", "narrative", "national",
    "navattic", "neo4j", "neon", "netherlands", "netlify", "netskope", "network",
    "neuralink", "newrelic", "newton", "nextdoor", "nexla", "nexthink", "nexus",
    "niantic", "nintendo", "nira", "noom", "nomic", "northflank", "notion",
    "nothing", "noyo", "nylas", "observable", "observeai", "octane", "octoai",
    "okta", "ollama", "omni", "onehouse", "onemedical", "openai", "opendoor",
    "openly", "openx", "orca", "orbit", "oscar", "otter", "outerbounds",
    "outreach", "outschool", "overjet", "owner", "oyster", "pachama", "paddle",
    "pagerduty", "palantir", "pandadoc", "pangea", "parabola", "parallel", "paragon",
    "parloa", "parrot", "parsleyhealth", "partiful", "patch", "patreon", "pave",
    "payoneer", "paypay", "paystack", "pear", "peloton", "percona", "perplexity",
    "persona", "phind", "photoroom", "philippines", "pilot", "pingidentity", "pinata",
    "pinterest", "pioneer", "pipedream", "place", "plaid", "plain", "planetscale",
    "planhat", "platform", "plotly", "pleo", "point", "point72", "popmenu",
    "portugal", "posthog", "postman", "postscript", "prefect", "primer", "privacy",
    "privy", "procore", "processing", "productboard", "project44", "propel", "public",
    "pulley", "pulse", "purple", "psyonix", "qualia", "quill", "quip", "quora",
    "radar", "railway", "railz", "ramp", "range", "rapid", "ray", "raycast",
    "reach", "ready", "recharge", "recroom", "reddit", "redpanda", "redwoodmaterials",
    "regal", "rekit", "relativity", "relay", "remote", "render", "remitly", "reonomy",
    "replit", "resend", "residential", "retool", "revel", "revery", "rill", "rippling",
    "riotgames", "ripple", "ro", "roam", "robinhood", "roblox", "rocketlab", "rokt",
    "root", "rooted", "rover", "rubrik", "rudderstack", "runway", "safebase",
    "salesloft", "samsara", "sanmar", "scale", "scaleai", "scopely", "scout",
    "seamlessai", "seatgeek", "secure", "secureframe", "secureworks", "segment",
    "send", "sendbird", "sentry", "sequin", "shadow", "shipbob", "shippo",
    "shiprocket", "shopify", "shopmonkey", "showpad", "signalfx", "signoz",
    "sigma", "singleStore", "skydio", "skyscanner", "slab", "slice", "smartasset",
    "smartlabs", "smartpay", "smartsheet", "smsbump", "snap", "snapdocs", "snorkel",
    "snorkelai", "snowflake", "snowplow", "snyk", "sofi", "solid", "someone",
    "sonder", "sondermind", "sonatype", "sourcegraph", "space", "spacelift", "spacex",
    "spain", "sparkpost", "spekit", "spin", "spire", "split", "springhealth",
    "sprig", "sproutsocial", "squarespace", "square", "stability", "stabilityai",
    "stackblitz", "stackexchange", "staging", "statement", "stedi", "step", "stitch",
    "stormforge", "stream", "stripe", "strongdm", "stytch", "substack", "sumo",
    "sunrise", "sunset", "super", "superblocks", "supercell", "superhuman", "supabase",
    "superset", "support", "sweep", "switzerland", "synack", "synapse", "system",
    "systems", "tailscale", "taiwan", "tangram", "teal", "technical", "technology",
    "teleport", "telesign", "temporal", "tempus", "tenable", "tenableinc", "terminus",
    "tessl", "test", "testing", "textio", "tetr", "tetra", "theorg", "thena",
    "thrasio", "thoughtspot", "tier", "tigergraph", "tiktok", "tilt", "timescale",
    "tines", "toast", "together", "tomorrow", "tonal", "topia", "topstep", "traceable",
    "transcarent", "treasuryprime", "trinsic", "tripadvisor", "trivago", "trove",
    "truebill", "truelayer", "trustpilot", "turing", "turo", "turso", "twitch", "twenty",
    "twilio", "typeform", "uber", "udemy", "ultimate", "unicorn", "unified", "united",
    "unity", "unity3d", "unit", "university", "unlock", "unqork", "upstart", "uplimit",
    "upwork", "v7labs", "vacasa", "valon", "vanta", "vast", "vectorized", "vendor",
    "vercel", "verdant", "verkada", "verse", "verygoodsecurity", "via", "vidyard",
    "vistaprint", "voiceflow", "voltron", "vonage", "voyage", "vowel", "vtex", "vulcan",
    "wandb", "waterfall", "weaviate", "webflow", "wefox", "weightsandbiases", "whatnot",
    "wheelhouse", "whimsical", "wikimedia", "windmill", "wise", "wiz", "wolt", "workato",
    "workday", "workrise", "workstream", "wrike", "xata", "xendit", "yext", "yotpo",
    "yugabyte", "zapier", "zeplin", "zepto", "zendesk", "zenoti", "zenrows", "zeta",
    "ziprecruiter", "zoho", "zocdoc", "zoominfo", "zora", "zscaler", "zuora"
})

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
