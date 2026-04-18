import requests
import concurrent.futures
import json
import itertools

# We have 130 currently. We need 370 more. 
# We'll just generate alphabet combinations + common tech prefixes to brute force some, or better, use a wordlist.
# Let's download a top 1000 startup list from a public csv
res = requests.get("https://raw.githubusercontent.com/toddmotto/public-apis/master/README.md")
API_words = []
import re
for word in re.findall(r"[a-zA-Z]{4,}", res.text):
    API_words.append(word.lower())

# Also let's try scraping ycombinator startup list
res2 = requests.get("https://raw.githubusercontent.com/ycombinator/ycombinator.github.io/master/index.html")
for word in re.findall(r"[a-zA-Z]{4,}", res2.text):
    API_words.append(word.lower())

# Also generic tech words
prefixes = ["data", "cloud", "ai", "cyber", "health", "fin", "tech", "smart", "open", "auto", "app", "pay"]
suffixes = ["ai", "tech", "app", "inc", "labs", "hq", "io", "data", "cloud", "health", "pay"]

generated = list(set(API_words))
for p in prefixes:
    for s in suffixes:
        generated.append(p+s)

candidates = list(set(generated))

print(f"Testing {len(candidates)} candidates")

valid = []

def check(board):
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", timeout=2)
        if r.status_code == 200:
            return board
    except:
        pass
    return None

with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    for r in executor.map(check, candidates[:5000]):
        if r:
            valid.append(r)

print(f"Found {len(valid)} new boards")

with open("valid_boards_2.json", "w") as f:
    json.dump(valid, f)
