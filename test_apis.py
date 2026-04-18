import requests

# Test Lever (e.g., netflix, figma, netlify, yelp)
try:
    r = requests.get("https://api.lever.co/v0/postings/netflix?mode=json", timeout=3)
    print("Lever (netflix):", r.status_code, len(r.json()))
except Exception as e:
    print("Lever Error:", e)

# Test Ashbyhq (e.g., multion, notion, ramp, linear)
try:
    # Ashbyhq publicly uses their GraphQL API on their careers pages, but they also have a direct API endpoint
    # that some open source scrapers use: https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams
    
    # Actually, a simpler way is checking if the job board page exists and scraping the inline JSON, 
    # but let's check if there's a simple REST endpoint via ashbyhq job board.
    
    # Try the new public endpoint format usually seen
    payload = {"operationName":"ApiJobBoardWithTeams","variables":{"organizationHostedJobsPageName":"linear"},"query":"query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {\n  jobBoard: jobBoardWithTeams(\n    organizationHostedJobsPageName: $organizationHostedJobsPageName\n  ) {\n    teams {\n      id\n      name\n      parentTeamId\n      __typename\n    }\n    jobPostings {\n      id\n      title\n      teamId\n      locationId\n      locationName\n      employmentType\n      secCompensationJobPostingDisplayAttributes {\n        compensationTierDisplayString\n        __typename\n      }\n      compensationTierSummary\n      originalCreatedAt\n      publishedAt\n      isListed\n      isConfidential\n      jobPageUrl\n      jobPageContent\n      __typename\n    }\n    __typename\n  }\n}"}
    r2 = requests.post("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams", json=payload, timeout=3)
    data = r2.json()
    postings = data.get("data", {}).get("jobBoard", {}).get("jobPostings", [])
    print("Ashbyhq (linear):", r2.status_code, len(postings))
except Exception as e:
    print("Ashbyhq Error:", e)
