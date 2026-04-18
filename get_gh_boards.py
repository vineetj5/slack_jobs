import requests
import re
import json

boards = set()
for page in range(1, 11):
    try:
        res = requests.get(
            f"https://api.github.com/search/code?q=boards.greenhouse.io+in:file&per_page=100&page={page}",
            headers={"Accept": "application/vnd.github.v3+json"}
        )
        if res.status_code != 200:
            break
        
        data = res.json()
        for item in data.get("items", []):
            url = item.get("html_url", "")
            # Just rough matching across github code
            pass
    except:
        pass
    
# Or let's download a known compiled list of greenhouse jobs and extract the boards.
# E.g. simplify-jobs/Summer2024-Internships
res = requests.get("https://raw.githubusercontent.com/simplifyjobs/Summer2024-Internships/dev/.github/scripts/data.json")
if res.status_code == 200:
    for item in res.json():
        url = item.get("link", "")
        if "greenhouse.io" in url:
            m = re.search(r"boards\.greenhouse\.io/([^/]+)", url)
            if m:
                boards.add(m.group(1))

res = requests.get("https://raw.githubusercontent.com/Pitt-CSC/Summer2024-Internships/dev/README.md")
if res.status_code == 200:
    for m in re.finditer(r"boards\.greenhouse\.io/([^/]+?)/", res.text):
        boards.add(m.group(1))

print(len(boards))
with open("boards_from_github.json", "w") as f:
    json.dump(list(boards), f)
