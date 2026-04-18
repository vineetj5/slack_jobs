import requests
import concurrent.futures

candidates = [
    # Top AI / ML / Data
    "openai", "anthropic", "scaleai", "databricks", "snowflake", "cohere", "huggingface", "stabilityai", "midjourney", 
    "inflection", "adept", "characterai", "snorkel", "runway", "jasper", "copyai", "mosaicml", "c3ai", "palantir",
    "fivetran", "dbtlabs", "airbyte", "meltano", "montecarlo", "astronomer", "prefect", "dagster", "confluent", "pinecone",
    "weaviate", "qdrant", "milvus", "anyscale", "modal", "baseten", "replicate", "weightsandbiases", "clearml", "cometml",

    # FinTech and Crypto
    "stripe", "plaid", "brex", "ramp", "chime", "robinhood", "coinbase", "kraken", "gemini", "chainalysis",
    "alchemy", "consensys", "circle", "paxos", "ripple", "affirm", "klarna", "afterpay", "block", "square",
    "cashapp", "sofi", "wealthfront", "betterment", "carta", "gusto", "rippling", "deel", "remote", "papayaglobal",
    "monzo", "revolut", "n26", "starling", "checkoutcom", "adyen", "mollie", "gocardless", "kabbage", "fundbox",

    # DevTools & Infra
    "vercel", "netlify", "supabase", "appwrite", "hasura", "apollo", "prisma", "grafana", "datadog", "newrelic",
    "sentry", "honeycomb", "launchdarkly", "split", "posthog", "amplitude", "mixpanel", "heap", "segment", "mparticle",
    "cloudflare", "fastly", "akamai", "nginx", "docker", "hashicorp", "pulumi", "gitlab", "github", "bitbucket",
    "circleci", "travisci", "buildkite", "render", "flyio", "railway", "digitalocean", "linode", "vultr", "heroku",

    # Cybersecurity
    "crowdstrike", "zscaler", "okta", "auth0", "pingidentity", "duosecurity", "1password", "lastpass", "dashlane",
    "sentinelone", "paloaltonetworks", "fortinet", "cyberark", "sailpoint", "varonis", "rapid7", "tenable", "qualys",
    "snyk", "lacework", "wiz", "orca", "sysdig", "illumio", "rubrik", "cohesity", "druva", "veeam", "commvault",

    # HealthTech & BioTech
    "zocdoc", "oscarhealth", "color", "tempus", "roivant", "ginkgo", "recursion", "insitro", "freenome", "grail",
    "23andme", "calico", "verily", "flatironhealth", "ommada", "livongo", "teladoc", "amwell", "doctorondemand",
    "babylonhealth", "carbonhealth", "onemedical", "forward", "heal", "dispatchhealth", "ro", "hims", "numom",

    # E-commerce, Delivery, Marketplace
    "instacart", "doordash", "ubereats", "postmates", "grubhub", "deliveryhero", "wolt", "gorillas", "getir", "gopuff",
    "shopify", "bigcommerce", "magento", "woocommerce", "squarespace", "wix", "weebly", "webflow", "contentful", "sanity",
    "strapi", "builderio", "vtex", "commercetools", "fabric", "bolt", "fast", "klaviyo", "attentive", "yotpo",
    "gorgias", "kustomer", "intercom", "zendesk", "freshworks", "helpscout", "front", "kayako", "happyfox", "userstack",

    # Productivity, Collaboration, HR
    "notion", "airtable", "coda", "smartsheet", "asana", "mondaycom", "clickup", "wrike", "trello", "jira",
    "confluence", "miro", "mural", "lucidchart", "figma", "canva", "invision", "sketch", "balsamiq", "framer",
    "slack", "discord", "zoom", "teams", "webex", "gotomeeting", "bluejeans", "twilio", "sendgrid", "plivo",
    "messagebird", "sinch", "bandwidth", "vonage", "infobip", "kaleyra", "routebyte", "nexmo", "telesign", "nexmo",

    # Space & Hardware
    "spacex", "blueorigin", "relativity", "astra", "rocketlab", "planet", "spire", "iceye", "capellaspace", "hawkeye360",
    "blacksky", "maxar", "satellogic", "descarteslabs", "orbitalinsight", "ursaspace", "rsmetrics", "spaceknow",
    "anduril", "palantir", "shieldai", "skydio", "zipline", "joby", "lilium", "archer", "beta", "volocopter",

    # Mobility & Travel
    "uber", "lyft", "grab", "gojek", "ola", "didi", "cabify", "beat", "99", "careem", "indrive", "yandextaxi",
    "bird", "lime", "spin", "tier", "voi", "dott", "wind", "helbiz", "jump", "skip", "scoot", "revel",
    "airbnb", "vrbo", "homeaway", "kayak", "skyscanner", "trivago", "hopper", "klook", "getyourguide", "viator",

    # More well known AI / SAAS
    "gong", "outreach", "salesloft", "seismic", "highspot", "showpad", "mindtickle", "braintrust", "toptal", "upwork",
    "fiverr", "freelancer", "guru", "peopleperhour", "codementor", "hackerrank", "coderbyte", "codility", "leetcode",
    "algoexpert", "crossover", "turing", "andela", "bairesdev", "globant", "epam", "luxoft", "endava", "softserve",

    # Extra tech unicorns
    "discord", "reddit", "pinterest", "snap", "twitter", "meta", "alphabet", "amazon", "apple", "netflix",
    "canva", "grammarly", "duolingo", "coursera", "udemy", "masterclass", "skillshare", "edx", "pluralsight", "datacamp",
    "roblox", "epicgames", "unity", "niantic", "ea", "activision", "blizzard", "ubisoft", "take2", "zynga",

    # Real Estate & PropTech
    "zillow", "redfin", "opendoor", "offerpad", "compass", "exp", "remax", "kellerwilliams", "coldwellbanker",
    "century21", "sothebys", "christies", "engelvolkers", "savills", "knightfrank", "cbre", "jll", "cushmanwakefield",
    "we-work", "industrious", "convene", "knotel", "regus", "spaces", "impacthub", "wework", "airbnb"

    # Expanded list part 2 (Generating variations for known boards plus common names)
]

# Provide variations and fallback names common on greenhouse
expanded = []
for name in set(candidates):
    expanded.extend([name, f"{name}inc", f"{name}hq", f"{name}app", f"{name}ai", f"{name}labs"])

# Some very common known ones that might not be in the direct guess list
more = [
    "verkada", "lyft", "andurilindustries", "discord", "databricks", "coinbase", "faire", "scaleai",
    "chime", "brex", "reddit", "robinhood", "stripe", "lattice", "hubspot", "klaviyo", "gusto", "figma",
    "doordashusa", "anthropic", "airbnb", "roblox", "twitch", "discord", "plaid", "openai", "peloton", "splunk",
    "cisco", "vmware", "servicenow", "workday", "adp", "intuit", "paypal", "ebay", "adobe", "salesforce", "oracle",
    "ibm", "microsoft", "google", "facebook", "tesla", "palantir", "uber", "twitter", "snapchat", "pinterest",
    "box", "dropbox", "atlassian", "slack", "zoom", "docusign", "smartsheet", "zendesk", "hubspot", "shopify",
    "wix", "squarespace", "godaddy", "mailchimp", "canva", "invision", "sketch", "figma", "framer", "webflow",
    "airtable", "notion", "coda", "evernote", "trello", "asana", "mondaycom", "clickup", "wrike", "smartsheet",
    "jira", "confluence", "bitbucket", "github", "gitlab", "circleci", "travisci", "jenkins", "docker", "kubernetes",
    "aws", "gcp", "azure", "digitalocean", "linode", "vultr", "heroku", "netlify", "vercel", "cloudflare",
    "fastly", "akamai", "nginx", "apache", "mongodb", "redis", "elasticsearch", "kafka", "rabbitmq", "mysql",
    "postgresql", "sqlite", "mariadb", "cassandra", "neo4j", "couchbase", "couchdb", "dynamodb", "cosmosdb",
    "firebase", "supabase", "appwrite", "hasura", "apollo", "prisma", "graphql", "rest", "grpc", "trpc",
    "react", "vue", "angular", "svelte", "ember", "backbone", "jquery", "bootstrap", "tailwind", "materialui",
    "chakraui", "antdesign", "bulma", "foundation", "uikit", "semanticui", "less", "sass", "stylus", "postcss",
    "webpack", "rollup", "parcel", "esbuild", "vite", "babel", "typescript", "flow", "eslint", "prettier",
    "jest", "mocha", "jasmine", "karma", "cypress", "puppeteer", "playwright", "selenium", "webdriverio",
    "appium", "detox", "expo", "reactnative", "flutter", "ionic", "cordova", "phonegap", "xamarin", "nativescript"
]
expanded.extend(more)

# Remove dupes
unique_boards = list(set(expanded))

valid = []

def check(board):
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", timeout=2)
        if r.status_code == 200:
            return board
    except:
        pass
    return None

if __name__ == "__main__":
    print(f"Testing {len(unique_boards)} boards...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(check, unique_boards)
        valid = [r for r in results if r is not None]
    
    print(len(valid))
    import json
    with open("valid_boards.json", "w") as f:
        json.dump(sorted(list(set(valid))), f)
    print("Done")
