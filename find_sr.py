import requests
import concurrent.futures
import json

candidates = [
    "Ubisoft2", "Visa", "Square", "Twitter", "Avaloq", "Biogen", "Bosch", "Bose", 
    "Cern", "Colliers", "Equinox", "Ikea", "KPMG", "LVMH", "McDonalds", "Nokia", 
    "Skechers", "TacoBell", "AveryDennison", "Albertsons", "Adevinta", "Criteo", 
    "Datadog", "Hootsuite", "Kinaxis", "Sodexo", "Wabtec", "Xerox", "Zalando",
    "Bazaarvoice", "Canva", "Collibra", "Deliveroo", "Endava", "Etsy", "Eventbrite", 
    "Figma", "Gitlab", "Hulu", "Instacart", "Klaviyo", "Mulesoft", "Miro", 
    "Optimizely", "Outreach", "Patreon", "Peloton", "Plaid", "Qualtrics", 
    "Reddit", "Robinhood", "Roku", "Vimeo", "Zendesk", "Zapier", "Tiktok", 
    "Revolut", "Strava", "Dropbox", "Slack", "Palantir", "Opendoor", "Notion"
]

# Let's add more from the simplified list or variations
candidates += [c.lower() for c in candidates] + [c.capitalize() for c in candidates]
unique = list(set(candidates))

valid = []

def check(board):
    try:
        r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{board}/postings?limit=1", timeout=2)
        if r.status_code == 200:
            return board
    except:
        pass
    return None

with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    results = executor.map(check, unique[:2000])
    valid = [r for r in results if r]

print("Found SR boards:", len(valid))
print(valid)
