#!/usr/bin/env python3
import concurrent.futures
import json
import logging
import requests
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
COMPANIES_FILE = ROOT_DIR / "companies.txt"
GH_FILE = ROOT_DIR / "greenhouse_boards.txt"
SR_FILE = ROOT_DIR / "smartrecruiters_boards.txt"
LV_FILE = ROOT_DIR / "lever_boards.txt"
AS_FILE = ROOT_DIR / "ashby_boards.txt"

WD_FILE = ROOT_DIR / "workday_boards.txt"

def check_greenhouse(name):
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{name}/jobs", timeout=5)
        return name if r.status_code == 200 else None
    except: return None

def check_workday(name):
    # Common Workday site IDs
    sites = ["External", "External_Career_Site", "Workday", "Careers", "Global_External_Career_Site"]
    for s in sites:
        try:
            url = f"https://{name}.myworkdayjobs.com/wday/cxs/{name}/{s}/jobs"
            payload = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
            r = requests.post(url, json=payload, timeout=5)
            if r.status_code == 200:
                return f"{name}/{s}"
        except:
            continue
    return None

def check_smartrecruiters(name):
    try:
        r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{name}/postings?limit=1", timeout=5)
        if r.status_code == 200 and r.json().get("totalFound", 0) > 0:
            return name
    except: return None

def check_lever(name):
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{name}?limit=1", timeout=5)
        if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
            return name
    except: return None

def check_ashby(name):
    try:
        r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{name}", timeout=5)
        if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
            return name
    except: return None

def probe_company(name):
    log.info(f"Probing: {name}")
    if check_greenhouse(name): return name, "greenhouse"
    if check_lever(name): return name, "lever"
    if check_ashby(name): return name, "ashby"
    if check_smartrecruiters(name): return name, "smartrecruiters"
    res = check_workday(name)
    if res: return res, "workday"
    return name, None

def load_list(path):
    if not path.exists(): return set()
    return set(line.strip() for line in path.read_text().splitlines() if line.strip())

def main():
    if not COMPANIES_FILE.exists():
        log.error("companies.txt not found!")
        return

    master_list = load_list(COMPANIES_FILE)
    
    # We will re-scan everything to ensure they are in the RIGHT files
    # (Sometimes companies are mistakenly in the wrong list)
    log.info(f"Re-scanning {len(master_list)} companies to ensure correct categorization...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        results = list(executor.map(probe_company, master_list))

    gh_list = set()
    sr_list = set()
    lv_list = set()
    as_list = set()
    wd_list = set()

    for entry, board_type in results:
        if board_type == "greenhouse": gh_list.add(entry)
        elif board_type == "smartrecruiters": sr_list.add(entry)
        elif board_type == "lever": lv_list.add(entry)
        elif board_type == "ashby": as_list.add(entry)
        elif board_type == "workday": wd_list.add(entry)
        else:
            if entry:
                log.warning(f"  ✗ Could not identify board for: {entry}")

    # Write back sorted
    def write_sorted(path, items):
        path.write_text("\n".join(sorted(list(items))) + "\n")

    write_sorted(GH_FILE, gh_list)
    write_sorted(SR_FILE, sr_list)
    write_sorted(LV_FILE, lv_list)
    write_sorted(AS_FILE, as_list)
    write_sorted(WD_FILE, wd_list)
    
    log.info("Successfully updated all board lists.")
    log.info(f"  Greenhouse: {len(gh_list)}")
    log.info(f"  SmartRecruiters: {len(sr_list)}")
    log.info(f"  Lever: {len(lv_list)}")
    log.info(f"  Ashby: {len(as_list)}")
    log.info(f"  Workday: {len(wd_list)}")

if __name__ == "__main__":
    main()
