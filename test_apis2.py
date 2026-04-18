import requests
import json

# Test Lever
try:
    r = requests.get("https://api.lever.co/v0/postings/figma?mode=json", timeout=10)
    print("Lever (figma):", r.status_code, len(r.json()))
    if len(r.json()) > 0:
        print("Keys:", r.json()[0].keys())
        # description text is usually in categories or lists
except Exception as e:
    print("Lever Error:", e)

# Test Ashbyhq
try:
    payload = {"operationName":"ApiJobBoardWithTeams","variables":{"organizationHostedJobsPageName":"ramp"},"query":"query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {\n  jobBoard: jobBoardWithTeams(\n    organizationHostedJobsPageName: $organizationHostedJobsPageName\n  ) {\n    teams {\n      id\n      name\n      parentTeamId\n      __typename\n    }\n    jobPostings {\n      id\n      title\n      teamId\n      locationId\n      locationName\n      employmentType\n      secCompensationJobPostingDisplayAttributes {\n        compensationTierDisplayString\n        __typename\n      }\n      compensationTierSummary\n      originalCreatedAt\n      publishedAt\n      isListed\n      isConfidential\n      jobPageUrl\n      __typename\n    }\n    __typename\n  }\n}"}
    r2 = requests.post("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams", json=payload, timeout=10)
    postings = r2.json().get("data", {}).get("jobBoard", {}).get("jobPostings", [])
    print("Ashbyhq (ramp):", r2.status_code, len(postings))
    if postings:
        print("Keys:", postings[0].keys())
        
    # How to get the description? Probably another API call, or it's included in `jobPageContent` if requested in GraphQL.
    # Let's request it:
    payload2 = {"operationName":"ApiJobPostingDefinition","variables":{"organizationHostedPageName":"ramp", "jobPostingId": postings[0]['id']},"query":"query ApiJobPostingDefinition($organizationHostedPageName: String!, $jobPostingId: String!) {\n  jobPosting(organizationHostedPageName: $organizationHostedPageName, jobPostingId: $jobPostingId) {\n    id\n    title\n    descriptionHtml\n    __typename\n  }\n}"}
    r3 = requests.post("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPostingDefinition", json=payload2, timeout=10)
    print("Ashbyhq Detail:", r3.status_code)
except Exception as e:
    print("Ashbyhq Error:", e)
