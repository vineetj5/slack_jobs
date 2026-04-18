import re

with open('notify_jobs.py', 'r') as f:
    content = f.read()

# Add SmartRecruiters import
if 'SmartRecruitersJobExtractor' not in content:
    content = content.replace(
        'from job_resume_agent.greenhouse import GreenhouseJobExtractor',
        'from job_resume_agent.greenhouse import GreenhouseJobExtractor\nfrom job_resume_agent.smartrecruiters import SmartRecruitersJobExtractor'
    )

# Add SmartRecruiters Boards list
sr_boards = [
    "ubisoft2", "square", "twitter", "avaloq", "biogen", "bosch", "bose",
    "cern", "colliers", "equinox", "ikea", "kpmg", "lvmh", "mcdonalds", "nokia",
    "skechers", "tacobell", "averydennison", "albertsons", "adevinta", "criteo",
    "datadog", "hootsuite", "kinaxis", "sodexo", "wabtec", "xerox", "zalando", "strava", "endava", "roblox"
]

formatted_sr_boards = "SMARTRECRUITERS_BOARDS = [\n    " + ",\n    ".join(f'"{b}"' for b in sorted(sr_boards)) + "\n]\n\n"

if 'SMARTRECRUITERS_BOARDS' not in content:
    content = re.sub(r'(BOARDS = sorted\(\{.*?\})\n', r'\1\n\n' + formatted_sr_boards, content, flags=re.DOTALL)


# Update the processing logic to handle both
new_processing_logic = """
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
"""

if 'def process_board(' in content:
    content = re.sub(r'def process_board\(.*?\):.*?return board, \[\], exc', new_processing_logic.strip(), content, flags=re.DOTALL)


new_main_logic = """
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
"""

if 'executor.submit(process_board, board, HOURS)' in content:
    content = re.sub(r'    with concurrent.futures.ThreadPoolExecutor.*?log.info\("  –.*?HOURS\)', new_main_logic.strip(), content, flags=re.DOTALL)

with open('notify_jobs.py', 'w') as f:
    f.write(content)
