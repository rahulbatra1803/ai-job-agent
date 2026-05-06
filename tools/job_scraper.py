"""
job_scraper.py
--------------
Fetches real jobs from THREE APIs and merges results:
  1. Jobs Scanner API  — Pure LinkedIn direct links (highest priority)
  2. JSearch API       — Naukri, Indeed, Shine, Apna Jobs
  3. Adzuna API        — Extra results

Priority: Jobs Scanner > JSearch > Adzuna
All three run in parallel, results merged + deduplicated + filtered.
"""

import os
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──
RAPIDAPI_KEY     = os.getenv("RAPIDAPI_KEY")
JOBS_SCANNER_KEY = os.getenv("JOBS_SCANNER_KEY")
ADZUNA_APP_ID    = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY   = os.getenv("ADZUNA_APP_KEY")

# ── Endpoints ──
JSEARCH_HOST     = "jsearch.p.rapidapi.com"
JSEARCH_URL      = "https://jsearch.p.rapidapi.com/search"
JOBS_SCANNER_URL = "https://linkedin-jobs-search.p.rapidapi.com/"
ADZUNA_URL       = "https://api.adzuna.com/v1/api/jobs/in/search/1"

# ── Blocked low-quality aggregators ──
BLOCKED_SOURCES = [
    "talent.com", "bebee", "jobrapido", "theirstack",
    "whatjobs", "jooble", "cutshort", "instahyre",
    "simplyhired", "jobinvent"
]

# ── Platform priority (lower index = higher priority) ──
PRIORITY_PLATFORMS = ["linkedin", "naukri", "indeed", "glassdoor", "internshala", "shine", "apna", "foundit", "adzuna"]


# ─────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────

def scrape_jobs(
    job_title:  str,
    location:   str = "India",
    num_jobs:   int = 10,
    job_type:   str = "job",
    experience: str = "fresher"
) -> list:
    print(f"\n  Job search: '{job_title}' | {location} | type={job_type} | exp={experience}")

    scanner_jobs = []
    jsearch_jobs = []
    adzuna_jobs  = []

    # ── Run all 3 APIs in parallel ──
    def run_scanner():
        nonlocal scanner_jobs
        scanner_jobs = _fetch_jobs_scanner(job_title, location, num_jobs)

    def run_jsearch():
        nonlocal jsearch_jobs
        jsearch_jobs = _fetch_jsearch(job_title, location, num_jobs, job_type, experience)

    def run_adzuna():
        nonlocal adzuna_jobs
        adzuna_jobs = _fetch_adzuna(job_title, location, num_jobs)

    t1 = threading.Thread(target=run_scanner)
    t2 = threading.Thread(target=run_jsearch)
    t3 = threading.Thread(target=run_adzuna)
    t1.start(); t2.start(); t3.start()
    t1.join();  t2.join();  t3.join()

    # ── Merge: Jobs Scanner first (highest priority) ──
    merged = _merge(scanner_jobs, jsearch_jobs, adzuna_jobs, num_jobs)

    if not merged:
        print("  No results from any API — using demo data.")
        return get_demo_jobs(job_title, location, num_jobs, job_type)

    print(f"  ✓ Final: {len(merged)} jobs | Sources: {[j['source_icon'] for j in merged[:5]]}")
    return merged


# ─────────────────────────────────────────
# 1. JOBS SCANNER — LinkedIn only
# ─────────────────────────────────────────

def _fetch_jobs_scanner(job_title: str, location: str, num_jobs: int) -> list:
    if not JOBS_SCANNER_KEY:
        print("  ⚠ Jobs Scanner: JOBS_SCANNER_KEY not set — skipping.")
        return []

    try:
        print(f"  Jobs Scanner: '{job_title}' in '{location}, India'")
        headers = {
            "x-rapidapi-key":  JOBS_SCANNER_KEY,
            "x-rapidapi-host": "linkedin-jobs-search.p.rapidapi.com",
            "Content-Type":    "application/json"
        }
        payload = {
            "search_terms": job_title,
            "location":     f"{location}, India",
            "page":         "1"
        }
        resp = requests.post(JOBS_SCANNER_URL, headers=headers, json=payload, timeout=20)

        if resp.status_code == 200:
            results = resp.json()
            if isinstance(results, list):
                print(f"    → {len(results)} LinkedIn jobs from Jobs Scanner")
                jobs = []
                for j in results[:num_jobs]:
                    url = j.get("linkedin_job_url_cleaned") or j.get("job_url", "")
                    jobs.append({
                        "title":       j.get("job_title", "N/A"),
                        "company":     j.get("company_name", "N/A"),
                        "location":    j.get("job_location", location),
                        "salary":      "Not disclosed",
                        "url":         url,
                        "source":      "LinkedIn",
                        "source_icon": "🔵 LinkedIn",
                        "posted_at":   j.get("posted_date", "")[:10],
                        "job_type":    "Full-time",
                        "is_remote":   "remote" in j.get("job_title", "").lower(),
                        "description": "",
                        "highlights":  [],
                    })
                return jobs
            else:
                print(f"    → Unexpected response format: {str(results)[:200]}")
        else:
            print(f"    → Jobs Scanner HTTP {resp.status_code}: {resp.text[:200]}")

    except requests.Timeout:
        print("    → Jobs Scanner timeout")
    except Exception as e:
        print(f"    → Jobs Scanner error: {e}")

    return []


# ─────────────────────────────────────────
# 2. JSEARCH — Naukri, Indeed, Shine
# ─────────────────────────────────────────

def _fetch_jsearch(job_title, location, num_jobs, job_type, experience) -> list:
    if not RAPIDAPI_KEY:
        print("  ⚠ JSearch: RAPIDAPI_KEY not set — skipping.")
        return []

    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": JSEARCH_HOST
    }

    queries = [
        (f"{job_title} in {location}", "week"),
        (f"{job_title} in {location}", "month"),
        (f"{job_title} {location}",    None),
    ]

    for query, date_filter in queries:
        params = {
            "query":     query,
            "page":      "1",
            "num_pages": "1",
            "country":   "in",
            "language":  "en"
        }
        if date_filter:
            params["date_posted"] = date_filter

        print(f"  JSearch: '{query}'")
        raw = _jsearch_call(headers, params)

        if raw:
            # Filter blocked sources
            raw = [j for j in raw if not any(
                b in (j.get("job_publisher") or "").lower() for b in BLOCKED_SOURCES
            )]
            if raw:
                jobs = _parse_jsearch(raw, num_jobs)
                print(f"    → {len(jobs)} jobs from JSearch")
                return jobs

    print("  JSearch: No results.")
    return []


def _jsearch_call(headers, params) -> list:
    try:
        resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            print(f"    → {len(data)} raw results")
            return data
        elif resp.status_code == 429:
            print("    → Rate limited")
        else:
            print(f"    → HTTP {resp.status_code}")
    except requests.Timeout:
        print("    → Timeout")
    except Exception as e:
        print(f"    → Error: {e}")
    return []


def _parse_jsearch(raw_jobs: list, num_jobs: int) -> list:
    sorted_jobs = sorted(raw_jobs, key=lambda j: _priority(j.get("job_publisher", "")))
    jobs = []
    for j in sorted_jobs[:num_jobs]:
        apply_url = j.get("job_apply_link") or j.get("job_google_link") or ""
        source    = j.get("job_publisher", "JSearch")
        jobs.append({
            "title":       j.get("job_title", "N/A"),
            "company":     j.get("employer_name", "N/A"),
            "location":    _fmt_location_jsearch(j),
            "salary":      _fmt_salary_jsearch(j),
            "url":         apply_url,
            "source":      source,
            "source_icon": _source_icon(source),
            "posted_at":   j.get("job_posted_at_datetime_utc", "")[:10],
            "job_type":    j.get("job_employment_type", "Full-time"),
            "is_remote":   j.get("job_is_remote", False),
            "description": j.get("job_description", "")[:1500],
            "highlights":  _extract_highlights_jsearch(j),
        })
    return jobs


# ─────────────────────────────────────────
# 3. ADZUNA — Extra results
# ─────────────────────────────────────────

def _fetch_adzuna(job_title: str, location: str, num_jobs: int) -> list:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("  ⚠ Adzuna: Keys not set — skipping.")
        return []

    try:
        print(f"  Adzuna: '{job_title}' in '{location}'")
        params = {
            "app_id":           ADZUNA_APP_ID,
            "app_key":          ADZUNA_APP_KEY,
            "results_per_page": num_jobs,
            "what":             job_title,
            "sort_by":          "date",
            "content-type":     "application/json",
        }
        if location and location.lower() != "india":
            params["where"] = location

        resp = requests.get(ADZUNA_URL, params=params, timeout=15)

        if resp.status_code == 200:
            results = resp.json().get("results", [])
            print(f"    → {len(results)} jobs from Adzuna")
            jobs = []
            for j in results:
                jobs.append({
                    "title":       j.get("title", "N/A"),
                    "company":     j.get("company", {}).get("display_name", "N/A"),
                    "location":    j.get("location", {}).get("display_name", location),
                    "salary":      _fmt_salary_adzuna(j),
                    "url":         j.get("redirect_url", ""),
                    "source":      "Adzuna",
                    "source_icon": "🟤 Adzuna",
                    "posted_at":   j.get("created", "")[:10],
                    "job_type":    "Full-time",
                    "is_remote":   "remote" in j.get("title", "").lower(),
                    "description": j.get("description", "")[:1500],
                    "highlights":  [],
                })
            return jobs
        else:
            print(f"    → Adzuna HTTP {resp.status_code}")

    except requests.Timeout:
        print("    → Adzuna timeout")
    except Exception as e:
        print(f"    → Adzuna error: {e}")

    return []


# ─────────────────────────────────────────
# MERGE + DEDUP
# ─────────────────────────────────────────

def _merge(scanner: list, jsearch: list, adzuna: list, num_jobs: int) -> list:
    """Priority: Jobs Scanner > JSearch > Adzuna. Dedup by title+company."""
    seen   = set()
    merged = []
    for job in scanner + jsearch + adzuna:
        key = f"{job['title'].strip().lower()}_{job['company'].strip().lower()}"
        if key not in seen:
            seen.add(key)
            merged.append(job)
    return merged[:num_jobs]


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _priority(source: str) -> int:
    s = source.lower()
    for i, p in enumerate(PRIORITY_PLATFORMS):
        if p in s:
            return i
    return len(PRIORITY_PLATFORMS)


def _source_icon(source: str) -> str:
    s = source.lower()
    if "linkedin"    in s: return "🔵 LinkedIn"
    if "naukri"      in s: return "🟠 Naukri"
    if "indeed"      in s: return "🔴 Indeed"
    if "glassdoor"   in s: return "🟡 Glassdoor"
    if "internshala" in s: return "🟢 Internshala"
    if "shine"       in s: return "🟣 Shine"
    if "apna"        in s: return "🔵 Apna Jobs"
    if "foundit"     in s: return "🔵 Foundit"
    if "adzuna"      in s: return "🟤 Adzuna"
    return f"⚪ {source}"


def _fmt_location_jsearch(job: dict) -> str:
    parts = [p for p in [
        job.get("job_city", ""),
        job.get("job_state", ""),
        job.get("job_country", "")
    ] if p]
    return ", ".join(parts) if parts else "India"


def _fmt_salary_jsearch(job: dict) -> str:
    mn = job.get("job_min_salary")
    mx = job.get("job_max_salary")
    p  = job.get("job_salary_period", "year")
    if mn and mx: return f"₹{int(mn):,} – ₹{int(mx):,} / {p}"
    if mn:        return f"₹{int(mn):,}+ / {p}"
    return "Not disclosed"


def _fmt_salary_adzuna(job: dict) -> str:
    mn = job.get("salary_min")
    mx = job.get("salary_max")
    if mn and mx: return f"₹{int(mn):,} – ₹{int(mx):,} / year"
    if mn:        return f"₹{int(mn):,}+ / year"
    return "Not disclosed"


def _extract_highlights_jsearch(job: dict) -> list:
    h = job.get("job_highlights", {})
    return (h.get("Qualifications", []) + h.get("Responsibilities", []))[:5]


# ─────────────────────────────────────────
# DEMO FALLBACK
# ─────────────────────────────────────────

def get_demo_jobs(job_title: str, location: str, num_jobs: int = 10, job_type: str = "job") -> list:
    is_intern    = job_type == "internship"
    encoded_t    = job_title.replace(" ", "%20")
    encoded_l    = location.replace(" ", "%20")
    linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_t}&location={encoded_l}"
    naukri_url   = f"https://www.naukri.com/{job_title.lower().replace(' ','-')}-jobs-in-{location.lower().replace(' ','-')}"
    indeed_url   = f"https://in.indeed.com/jobs?q={encoded_t}&l={encoded_l}"
    salary       = "₹8,000 – ₹15,000 / month" if is_intern else "₹18,00,000 – ₹28,00,000 / year"
    jtype        = "Internship" if is_intern else "Full-time"

    templates = [
        {"title": f"{job_title} Developer — Remote",  "company": "TechCorp India",           "url": linkedin_url, "source_icon": "🔵 LinkedIn"},
        {"title": f"Junior {job_title}",              "company": "StartupXYZ",               "url": naukri_url,   "source_icon": "🟠 Naukri"},
        {"title": f"{job_title} Developer — On-site", "company": "GlobalSoft",               "url": indeed_url,   "source_icon": "🔴 Indeed"},
        {"title": f"Senior {job_title}",              "company": "Enterprise Solutions Ltd", "url": linkedin_url, "source_icon": "🔵 LinkedIn"},
        {"title": f"{job_title} Consultant",          "company": "Deloitte India",           "url": indeed_url,   "source_icon": "🔴 Indeed"},
    ]
    return [
        {**t, "location": location, "salary": salary, "source": t["source_icon"],
         "posted_at": "2026-05-01", "job_type": jtype, "is_remote": False,
         "description": f"{jtype} {job_title} role at {t['company']}.", "highlights": []}
        for t in templates[:num_jobs]
    ]


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    jobs = scrape_jobs("Python Developer", "Bangalore", 10, "job", "fresher")
    print(f"\n{'='*60}")
    for j in jobs:
        print(f"\n{j['title']} @ {j['company']}")
        print(f"  Source  : {j['source_icon']}")
        print(f"  Location: {j['location']}")
        print(f"  Salary  : {j['salary']}")
        print(f"  Apply   : {j['url']}")