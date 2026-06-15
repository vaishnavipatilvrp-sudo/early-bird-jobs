# Early Bird — Daily Job Alerts

Tracks fresh job postings (last 24 hours) for your target roles across your
list of target companies. Updates a website every morning and emails you
the new ones, so you can apply first.

---

## 1. Get a free JSearch API key (5 min)

1. Go to https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
2. Sign up (free) and subscribe to the **free Basic plan** (200 requests/month).
3. Copy your `X-RapidAPI-Key` from the "Endpoints" tab.

With 4 search titles run once a day, that's ~120 requests/month - well
within the free tier, with room to add a couple more titles.

## 2. Create a GitHub repo

1. Create a **public** repo (e.g. `early-bird-jobs`).
2. Upload everything in this project, keeping the folder structure:
   `.github/workflows/`, `docs/`, `fetch_jobs.py`, `company_sources.py`,
   `config.json`, etc.

## 3. Set up email (Gmail)

1. Enable **2-Step Verification** on your Google Account if not already on.
2. Go to https://myaccount.google.com/apppasswords and create an **App
   Password** (Mail / Other).
3. Copy the 16-character password.

## 4. Add secrets to your repo

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret name      | Value                                  |
|-------------------|----------------------------------------|
| `RAPIDAPI_KEY`    | the key from Step 1                    |
| `EMAIL_FROM`      | your Gmail address                     |
| `EMAIL_PASSWORD`  | the app password from Step 3           |
| `EMAIL_TO`        | where alerts go (can be the same Gmail)|

## 5. Enable GitHub Pages

1. **Settings → Pages**
2. Source: "Deploy from a branch" → branch `main`, folder `/docs`
3. Save. Site goes live at `https://<your-username>.github.io/<repo-name>/`

## 6. Test it

**Actions tab → "Daily Job Fetch" → Run workflow**. Check your email and the
GitHub Pages site. After this it runs daily at 12:00 UTC automatically.

---

## How your company list is handled

`config.json` has two parts:

### `jsearch.target_companies`
A list of ~65 companies (your full list, deduped and normalized). These cost
**nothing extra** - JSearch is queried once per role title
(`jsearch.search_titles`), and results are filtered down to companies whose
name contains one of these strings. Feel free to add/remove companies here
freely; it doesn't change your API usage.

**Coverage caveat**: JSearch only returns what's indexed in Google for Jobs
for that title+date query. If a specific company posted something today but
it's not in the top results for "Software Engineer posted today", it may not
show up. This is "best effort, zero cost" coverage across your whole list.

### `direct_sources`
Companies that publish jobs via Greenhouse, Lever, or Ashby get fetched
**directly and completely** - guaranteed same-day coverage, no API key
needed. Currently includes Pinterest.

**To add more companies here**, run:

```bash
pip install requests
python find_direct_source.py <guess-token>
```

The token is usually the company name lowercase with no spaces (check their
careers page URL - if it's `boards.greenhouse.io/something`,
`jobs.lever.co/something`, or `jobs.ashbyhq.com/something`, "something" is
the token). If found, copy the suggested line into `config.json`'s
`direct_sources` array.

Worth checking from your list: Lattice Semiconductor, Fetch, Foundry, Eigen X,
New Math Data, Sybridge, MegaZone Cloud, AmpCus, HiLabs - smaller/newer tech
companies are more likely to use these systems. Large enterprises (Goldman
Sachs, Ford, Pfizer, Bank of America, etc.) almost always use Workday/Taleo/
SuccessFactors instead, which don't have public APIs - for those, the
JSearch list is your coverage.

## Customizing your roles

Edit `config.json` -> `match_keywords`. A job is only kept if its title
contains at least one of these (case-insensitive). Current defaults:

```json
"match_keywords": [
  "software engineer", "software development engineer", "sde", "swe",
  "data analyst", "data scientist", "machine learning", "ml engineer",
  "ai engineer", "database administrator", "dba"
]
```

Add or remove freely - e.g. add `"program manager"` or remove `"dba"` if
you're not currently targeting those.

## Dashboard filters

The website now has a search box plus dropdowns for role category and
company, so with 65 companies you can quickly narrow down to "just Database
Administrator roles" or "just Goldman Sachs" without scrolling.

## Notes & limits

- Company name matching is a simple substring check, so "L&T" matches
  "L&T Technology Services Limited", "Amazon" matches "Amazon.com Services
  LLC" and "Amazon Web Services", etc.
- If you hit the JSearch 200/month limit, reduce `search_titles` or run every
  other day (`cron: '0 12 */2 * *'` in the workflow file).
- "Posted Today" data for Greenhouse/Lever/Ashby is based on the job's
  `updated_at`/`createdAt` field - for brand-new postings this matches the
  actual post date.
