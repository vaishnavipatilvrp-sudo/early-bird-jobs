"""
find_direct_source.py

Helper to check whether a company publishes jobs via Greenhouse, Lever,
or Ashby (the three systems with public, no-key-needed APIs), so you
can add it to config.json's "direct_sources" list for guaranteed
same-day coverage instead of relying on JSearch.

Usage:
    python find_direct_source.py <guess-token>

The "token" is usually the company name, lowercase, no spaces -
e.g. "airbnb", "stripe", "openai". If a company's careers page URL
looks like:
    boards.greenhouse.io/<token>
    jobs.lever.co/<token>
    jobs.ashbyhq.com/<token>
...then <token> is what you want.

If you're not sure, try a few variations: "lattice", "lattice-semi",
"latticesemi", etc.

Example:
    python find_direct_source.py pinterest
    -> Found 1 jobs via greenhouse for token 'pinterest'

If nothing is found, the company likely uses a different system
(Workday, Taleo, SuccessFactors, custom) and you'll need to rely on
the JSearch-based feed instead - just add the company name to
config.json -> jsearch -> target_companies (no extra API cost).
"""

import sys
import requests


def try_greenhouse(token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        jobs = r.json().get("jobs", [])
        return len(jobs)
    return None


def try_lever(token):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        jobs = r.json()
        if isinstance(jobs, list):
            return len(jobs)
    return None


def try_ashby(token):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        jobs = r.json().get("jobs", [])
        return len(jobs)
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_direct_source.py <guess-token>")
        sys.exit(1)

    token = sys.argv[1]
    found_any = False

    for name, fn in [("greenhouse", try_greenhouse), ("lever", try_lever), ("ashby", try_ashby)]:
        count = fn(token)
        if count is not None:
            print(f"FOUND: {count} jobs via {name} for token '{token}'")
            print(f'   Add to config.json: {{"name": "<Company Name>", "type": "{name}", "token": "{token}"}}')
            found_any = True

    if not found_any:
        print(f"Not found: no Greenhouse/Lever/Ashby board for token '{token}'.")
        print("Try a different token guess, or add the company name to")
        print("config.json -> jsearch -> target_companies instead.")


if __name__ == "__main__":
    main()
