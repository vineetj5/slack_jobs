import json

with open('all_boards.json', 'r') as f:
    boards = json.load(f)

# Because doing multi_replace_file_content with a gigantic list of 360+ lines can be error prone,
# let's write a python script to parse notify_jobs.py, inject the updated boards and add ThreadPoolExecutor.

with open('notify_jobs.py', 'r') as f:
    content = f.read()

import re

# Swap the BOARDS list
formatted_boards = "BOARDS = [\n    " + ",\n    ".join(f'"{b}"' for b in boards) + "\n]"
content = re.sub(r'BOARDS = \[.*?\]', formatted_boards, content, flags=re.DOTALL)

# Also add the ThreadPoolExecutor logic
if 'import concurrent.futures' not in content:
    content = content.replace('from pathlib import Path', 'from pathlib import Path\nimport concurrent.futures')

loop_logic = """
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
"""

content = re.sub(r'    log.info\("Querying.*?Total jobs found[^\n]+', loop_logic.strip() + '\n', content, flags=re.DOTALL)

with open('notify_jobs.py', 'w') as f:
    f.write(content)
