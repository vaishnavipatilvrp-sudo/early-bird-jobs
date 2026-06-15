"""
fetch_jobs.py

1. Queries JSearch once per search title (config.jsearch.search_titles),
   filtered to postings from the last 24h, then keeps only results from
   companies in config.jsearch.target_companies.
2. Queries any "direct_sources" (Greenhouse/Lever/Ashby boards), which
   return ALL open jobs at that company - these are filtered by
   config.match_keywords and recency.
3. Applies config.match_keywords to everything (a job is kept only if
   its title contains at least one keyword).
4. Tags each job with a role category (for the website filter dropdown).
5. Dedupes against seen_jobs.json, writes docs/data.json, emails new jobs.

Required environment variables (set as GitHub Actions secrets):
  RAPIDAPI_KEY     - your RapidAPI key for JSearch
  EMAIL_FROM       - sender Gmail address
  EMAIL_PASSWORD   - Gmail app password (NOT your normal password)
  EMAIL_TO         - recipient address (can be same as EMAIL_FROM)
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
import smtplib
from email.mime.text import MIMEText

import requests

from company_sources import fetch_direct_source

CONFIG_PATH = "config.json"
SEEN_PATH = "seen_jobs.json"
DATA_PATH = "docs/data.json"

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HOST = "jsearch.p.rapidapi.com"

# Role category tags shown on the dashboard. First match wins.
CATEGORY_RULES = [
    ("ML / AI Engineer", ["machine learning", "ml engineer", "ai engineer", "applied scientist", "research scientist"]),
    ("Data Scientist", ["data scientist"]),
    ("Data Analyst", ["data analyst", "business analyst", "bi analyst"]),
    ("Data Engineer", ["data engineer", "etl"]),
    ("Database Administrator", ["database administrator", "dba"]),
    ("Software Engineer", ["software engineer", "software development engineer", "sde", "swe", "software developer"]),
    ("DevOps / Cloud", ["devops", "site reliability", "cloud engineer", "infrastructure engineer"]),
    ("Other", []),
]


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def classify(job_title):
    title_lower = (job_title or "").lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in title_lower for kw in keywords):
            return category
    return "Other"


def matches_keywords(job_title, keywords):
    if not job_title:
        return False
    title_lower = job_title.lower()
    return any(kw in title_lower for kw in keywords)


def is_recent(posted_at_str, max_age_hours):
    if not posted_at_str:
        return False
    try:
        posted_dt = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00"))
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    return (now - posted_dt) <= timedelta(hours=max_age_hours)


def fetch_jsearch(search_title, location, api_key):
    query = f"{search_title} in {location}" if location else search_title
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }
    params = {
        "query": query,
        "page": "1",
        "num_pages": "1",
        "date_posted": "today",
    }
    resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def send_email(new_jobs, email_from, email_password, email_to):
    if not new_jobs:
        return

    lines = []
    for job in new_jobs:
        lines.append(
            f"[{job['category']}] {job['employer_name']} - {job['job_title']}\n"
            f"{job.get('location', '')}\n"
            f"Apply: {job['apply_link']}\n"
        )

    body = "New job postings (last 24h) matching your roles:\n\n" + "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = f"New job alerts: {len(new_jobs)} posting(s) - apply early!"
    msg["From"] = email_from
    msg["To"] = email_to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_from, email_password)
        server.sendmail(email_from, [email_to], msg.as_string())


def main():
    config = load_json(CONFIG_PATH, {})
    max_age_hours = config.get("max_age_hours", 24)
    match_keywords = [k.lower() for k in config.get("match_keywords", [])]

    seen_ids = set(load_json(SEEN_PATH, []))

    all_jobs = []
    new_jobs = []

    # ---- 1. JSearch (broad company list) ----
    jsearch_cfg = config.get("jsearch", {})
    api_key = os.environ.get("RAPIDAPI_KEY")

    if api_key:
        target_companies = [c.lower() for c in jsearch_cfg.get("target_companies", [])]
        location_filter = jsearch_cfg.get("location_filter", "")

        for search_title in jsearch_cfg.get("search_titles", []):
            try:
                results = fetch_jsearch(search_title, location_filter, api_key)
            except requests.RequestException as e:
                print(f"JSearch error for '{search_title}': {e}")
                continue

            for job in results:
                employer = (job.get("employer_name") or "").lower()
                if not any(c in employer for c in target_companies):
                    continue
                if not is_recent(job.get("job_posted_at_datetime_utc"), max_age_hours):
                    continue
                if not matches_keywords(job.get("job_title"), match_keywords):
                    continue

                location = ", ".join(filter(None, [job.get("job_city"), job.get("job_state")])) or job.get("job_country", "")

                all_jobs.append({
                    "job_id": job["job_id"],
                    "employer_name": job.get("employer_name"),
                    "job_title": job.get("job_title"),
                    "location": location,
                    "apply_link": job.get("job_apply_link"),
                    "posted_at": job.get("job_posted_at_datetime_utc"),
                    "category": classify(job.get("job_title")),
                    "source": "jsearch",
                })

            time.sleep(1)
    else:
        print("RAPIDAPI_KEY not set, skipping JSearch.")

    # ---- 2. Direct sources (Greenhouse/Lever/Ashby) ----
    for source in config.get("direct_sources", []):
        try:
            jobs = fetch_direct_source(source)
        except requests.RequestException as e:
            print(f"Direct source error for '{source['name']}': {e}")
            continue
        except ValueError as e:
            print(f"Config error: {e}")
            continue

        for job in jobs:
            if not is_recent(job.get("posted_at"), max_age_hours):
                continue
            if not matches_keywords(job.get("job_title"), match_keywords):
                continue

            all_jobs.append({
                "job_id": job["job_id"],
                "employer_name": job.get("employer_name"),
                "job_title": job.get("job_title"),
                "location": job.get("location", ""),
                "apply_link": job.get("apply_link"),
                "posted_at": job.get("posted_at"),
                "category": classify(job.get("job_title")),
                "source": source["type"],
            })

    # ---- Dedup + sort ----
    for job in all_jobs:
        if job["job_id"] not in seen_ids:
            new_jobs.append(job)
            seen_ids.add(job["job_id"])

    all_jobs.sort(key=lambda j: j["posted_at"] or "", reverse=True)

    save_json(DATA_PATH, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": all_jobs,
    })
    save_json(SEEN_PATH, list(seen_ids))

    print(f"Total matching jobs (last {max_age_hours}h): {len(all_jobs)}")
    print(f"New jobs since last run: {len(new_jobs)}")

    email_from = os.environ.get("EMAIL_FROM")
    email_password = os.environ.get("EMAIL_PASSWORD")
    email_to = os.environ.get("EMAIL_TO")

    if email_from and email_password and email_to:
        send_email(new_jobs, email_from, email_password, email_to)
    else:
        print("Email credentials not set, skipping email step.")


if __name__ == "__main__":
    main()
