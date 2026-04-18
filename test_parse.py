import re

def is_usa_location(location: str) -> bool:
    loc = location.lower()
    
    # Common US indicators
    us_terms = [" us", "usa", "united states", "remote - us", "remote (us)", "remote, us"]
    if any(t in loc for t in us_terms) or loc == "us":
        return True
    
    # US States
    states = [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", 
        "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", 
        "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska", 
        "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", 
        "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", 
        "texas", "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
        " al", " ak", " az", " ar", " ca", " co", " ct", " de", " fl", " ga", " hi", " id", " il", " in", " ia", " ks", 
        " ky", " la", " me", " md", " ma", " mi", " mn", " ms", " mo", " mt", " ne", " nv", " nh", " nj", " nm", " ny", 
        " nc", " nd", " oh", " ok", " or", " pa", " ri", " sc", " sd", " tn", " tx", " ut", " vt", " va", " wa", " wv", 
        " wi", " wy",
        ", ca", ", ny", ", tx" # common
    ]
    if any(s in loc for s in states):
        # Double check it isn't "canada", "mexico", "india", "uk", "kingdom", "europe" if just matching abbreviations
        return True
        
    # If the location is just "Remote" or empty, it could be US, but let's be strict or lenient?
    if loc == "remote" or loc == "unknown":
        return True # Many companies don't specify, assume US for broad boards.
        
    return False

def check_experience(description: str) -> bool:
    # Extracts the minimum experience mentioned
    # Returns True if missing or <= 3, False if > 3
    pattern = re.compile(r'(\d+)\s*(?:\+|-|to)?\s*(?:\d*\s*)\+?\s*(?:years?|yrs?)[^.?!]{0,40}experience', re.IGNORECASE)
    matches = pattern.finditer(description)
    
    # Also look for phrases like "experience of X years", "X+ years of engineering experience"
    # Actually just checking digits before "years" followed by "experience"
    
    yoes = []
    for m in matches:
        try:
            val = int(m.group(1))
            yoes.append(val)
        except:
            pass
            
    # Fallback to another pattern "experience ... X+ years"
    pattern2 = re.compile(r'experience[^.?!]{0,40}?(\d+)\s*(?:\+|-|to)?\s*(?:\d*\s*)\+?\s*(?:years?|yrs?)', re.IGNORECASE)
    matches2 = pattern2.finditer(description)
    for m in matches2:
        try:
            val = int(m.group(1))
            yoes.append(val)
        except:
            pass

    if not yoes:
        return True # not mentioned
        
    # If there are any mentions of YOE, let's see if the relevant minimum is <= 3.
    # Often descriptions mention "10+ years of total experience" and "2+ years of python".
    # Or "minimum 5 years".
    # We should extract all small numbers. If all mentioned numbers > 3, we reject.
    # What if they say "1 year of python, 5 years overall"? The user wants "less than or equal to 3 years".
    # To be safe, if the lowest mentioned experience is <= 3, we accept. Or maybe if the max mentioned is <= 3? 
    # Usually "minimum 5 years" means min(yoes) == 5. So if min(yoes) <= 3, return True.
    if min(yoes) <= 3:
        return True
    
    return False

print(is_usa_location("San Francisco, CA"))
print(is_usa_location("London, UK"))
print(is_usa_location("Remote - US"))
print(is_usa_location("Canada"))

print(check_experience("Requires 5+ years of software engineering experience"))
print(check_experience("Looking for 1-3 years of experience in Python"))
print(check_experience("Must have 4 years experience with JS and 2+ years experience with React"))
print(check_experience("No experience required"))
