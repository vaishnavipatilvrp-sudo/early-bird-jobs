"""
company_sources.py

Fetchers for companies that publish their job listings via a public
applicant-tracking-system API. These need no API key and are more
reliable than aggregator-based search, but only work for companies
that use one of these three systems.

Each fetcher returns a list of normalized dicts:
  {
    "job_id": str (globally unique),
    "employer_name": str,
    "job_title": str,
    "location": str,
    "apply_link": str,
    "posted_at": str (ISO8601 UTC) or None,
  }
"""

import requests


def fetch_greenhouse(company_name, token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])

    out = []
    for j in jobs:
        out.append({
            "job_id": f"greenhouse_{token}_{j['id']}",
            "employer_name": company_name,
            "job_title": j.get("title"),
            "location": (j.get("location") or {}).get("name", ""),
            "apply_link": j.get("absolute_url"),
            "posted_at": j.get("updated_at"),
        })
    return out


def fetch_lever(company_name, token):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    jobs = resp.json()

    out = []
    for j in jobs:
        posted_at = None
        created_ms = j.get("createdAt")
        if created_ms:
            from datetime import datetime, timezone
            posted_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat()

        out.append({
            "job_id": f"lever_{token}_{j.get('id')}",
            "employer_name": company_name,
            "job_title": j.get("text"),
            "location": (j.get("categories") or {}).get("location", ""),
            "apply_link": j.get("hostedUrl"),
            "posted_at": posted_at,
        })
    return out


def fetch_ashby(company_name, token):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])

    out = []
    for j in jobs:
        out.append({
            "job_id": f"ashby_{token}_{j.get('id')}",
            "employer_name": company_name,
            "job_title": j.get("title"),
            "location": j.get("location", ""),
            "apply_link": j.get("jobUrl") or j.get("applyUrl"),
            "posted_at": j.get("publishedAt") or j.get("updatedAt"),
        })
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


def fetch_direct_source(source):
    """source: {"name": str, "type": "greenhouse"|"lever"|"ashby", "token": str}"""
    fetcher = FETCHERS.get(source["type"])
    if not fetcher:
        raise ValueError(f"Unknown source type: {source['type']}")
    return fetcher(source["name"], source["token"])
