import requests
import json
import re

url = "https://raw.githubusercontent.com/SimplifyJobs/Summer2024-Internships/dev/README.md"
text = requests.get(url).text
boards = set()
for url_match in re.findall(r'https://(?:boards|boards-api)\.greenhouse\.io/[^/\s"\')]+', text):
    board = url_match.split("/")[-1]
    if "?" in board:
        board = board.split("?")[0]
    boards.add(board)

url2 = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
text2 = requests.get(url2).text
for url_match in re.findall(r'https://(?:boards|boards-api)\.greenhouse\.io/[^/\s"\')]+', text2):
    board = url_match.split("/")[-1]
    if "?" in board:
        board = board.split("?")[0]
    boards.add(board)

print("Found boards from Simplify:", len(boards))
with open("simplify_boards.json", "w") as f:
    json.dump(list(boards), f)
