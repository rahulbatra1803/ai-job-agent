"""
job_scraper.py
--------------
Fetches real jobs from JSearch API (via RapidAPI).
Supports: job type (job/internship), experience level, fresh listings only.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_URL  = "https://jsearch.p.rapidapi.com/search"

# Experience level → query modifier
EXPERIENCE_QUERY = {
    "fresher":  "fresher OR entry level OR 0 years experience",
    "1yr":      "1 year experience",
    "2-3yr":    "2 to 3 years experience",
    "4+yr":     "4+ years experience senior",
}


def fetch_jobs_jsearch(
    job_title: str,
    location: str,
    num_jobs: int = 10,
    job_type: str = "job",          # "job" or "internship"
    experience: str = "fresher"     # "fresher" | "1yr" | "2-3yr" | "4+yr"
) -> list:

    if not RAPIDAPI_KEY:
        print("  ⚠ RAPIDAPI_KEY not found — using demo data.")
        return get_demo_jobs(job_title, location, num_jobs, job_type)

    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": JSEARCH_HOST
    }

    # Build smart query
    base_query = job_title
    if job_type == "internship":
        base_query = f"{job_title} internship"
    exp_modifier = EXPERIENCE_QUERY.get(experience, "")
    full_query   = f"{base_query} {exp_modifier} in {location}".strip()

    params = {
        "query":       full_query,
        "page":        "1",
        "num_pages":   "1",
        "date_posted": "week",   # ✅ week filter — fresh jobs only
        "country":     "in",
        "language":    "en"
    }

    # Add employment type filter for internships
    if job_type == "internship":
        params["employment_types"] = "INTERN"

    try:
        print(f"  JSearch: '{full_query}'  [date: week]")
        resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=15)

        if resp.status_code == 200:
            raw_jobs = resp.json().get("data", [])

            if not raw_jobs:
                print("  No jobs returned — using demo data.")
                return get_demo_jobs(job_title, location, num_jobs, job_type)

            # Priority order: LinkedIn > Naukri > Internshala > Indeed > others
            PRIORITY = ["linkedin", "naukri", "internshala", "indeed"]

            def _priority(job):
                src = (job.get("job_publisher") or "").lower()
                for i, p in enumerate(PRIORITY):
                    if p in src:
                        return i
                return len(PRIORITY)  # others last

            raw_jobs_sorted = sorted(raw_jobs, key=_priority)

            jobs = []
            for j in raw_jobs_sorted[:num_jobs]:
                apply_url = j.get("job_apply_link") or j.get("job_google_link") or ""
                source    = j.get("job_publisher", "JSearch")
                jobs.append({
                    "title":       j.get("job_title", "N/A"),
                    "company":     j.get("employer_name", "N/A"),
                    "location":    _format_location(j),
                    "salary":      _format_salary(j),
                    "url":         apply_url,
                    "source":      source,
                    "source_icon": _source_icon(source),
                    "posted_at":   j.get("job_posted_at_datetime_utc", "")[:10],
                    "job_type":    j.get("job_employment_type", "Full-time"),
                    "is_remote":   j.get("job_is_remote", False),
                    "description": j.get("job_description", "")[:1500],
                    "highlights":  _extract_highlights(j),
                })

            print(f"  ✓ {len(jobs)} jobs fetched. Sources: {[j['source'] for j in jobs[:3]]}")
            return jobs

        elif resp.status_code == 429:
            print("  ⚠ Rate limit — using demo data.")
        else:
            print(f"  ⚠ Status {resp.status_code} — using demo data.")

    except requests.Timeout:
        print("  ⚠ Timeout — using demo data.")
    except Exception as e:
        print(f"  ⚠ Error: {e} — using demo data.")

    return get_demo_jobs(job_title, location, num_jobs, job_type)


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _format_location(job: dict) -> str:
    parts = [p for p in [job.get("job_city",""), job.get("job_state",""), job.get("job_country","")] if p]
    return ", ".join(parts) if parts else "India"

def _format_salary(job: dict) -> str:
    mn, mx = job.get("job_min_salary"), job.get("job_max_salary")
    p = job.get("job_salary_period", "year")
    if mn and mx: return f"₹{int(mn):,} – ₹{int(mx):,} / {p}"
    if mn:        return f"₹{int(mn):,}+ / {p}"
    return "Not disclosed"

def _extract_highlights(job: dict) -> list:
    h = job.get("job_highlights", {})
    return (h.get("Qualifications", []) + h.get("Responsibilities", []))[:5]

def _source_icon(source: str) -> str:
    s = source.lower()
    if "linkedin"    in s: return "🔵 LinkedIn"
    if "naukri"      in s: return "🟠 Naukri"
    if "internshala" in s: return "🟢 Internshala"
    if "indeed"      in s: return "🔴 Indeed"
    if "glassdoor"   in s: return "🟡 Glassdoor"
    return f"⚪ {source}"



# ─────────────────────────────────────────
# DEMO FALLBACK
# ─────────────────────────────────────────

def get_demo_jobs(job_title: str, location: str, num_jobs: int = 10, job_type: str = "job") -> list:
    is_intern = job_type == "internship"
    prefix    = "Internship" if is_intern else "Developer"
    salary    = "₹8,000 – ₹15,000 / month (Stipend)" if is_intern else "₹18,00,000 – ₹28,00,000 / year"

    templates = [
        {"title": f"{job_title} {prefix} — Remote",   "company": "TechCorp India",           "salary": salary, "url": "https://www.linkedin.com/jobs/",  "source": "Demo", "job_type": "INTERN" if is_intern else "Full-time", "is_remote": True},
        {"title": f"Junior {job_title}",               "company": "StartupXYZ",               "salary": salary, "url": "https://www.naukri.com/",          "source": "Demo", "job_type": "INTERN" if is_intern else "Full-time", "is_remote": False},
        {"title": f"{job_title} {prefix} — On-site",  "company": "GlobalSoft",               "salary": salary, "url": "https://www.indeed.co.in/",        "source": "Demo", "job_type": "INTERN" if is_intern else "Full-time", "is_remote": False},
        {"title": f"Senior {job_title}",               "company": "Enterprise Solutions Ltd", "salary": salary, "url": "https://www.glassdoor.co.in/",     "source": "Demo", "job_type": "Full-time",                             "is_remote": False},
        {"title": f"{job_title} Consultant",           "company": "Deloitte India",           "salary": salary, "url": "https://apply.deloitte.com/",      "source": "Demo", "job_type": "Full-time",                             "is_remote": False},
    ]

    return [
        {**t, "location": location, "posted_at": "2026-04-01",
         "description": f"{'Internship' if is_intern else 'Full-time'} {job_title} role at {t['company']}. Strong fundamentals required.", "highlights": []}
        for t in templates[:num_jobs]
    ]


# ─────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────

def scrape_jobs(
    job_title: str,
    location: str = "India",
    num_jobs: int = 10,
    job_type: str = "job",
    experience: str = "fresher"
) -> list:
    print(f"\n  Job search: '{job_title}' | {location} | type={job_type} | exp={experience}")
    return fetch_jobs_jsearch(job_title, location, num_jobs, job_type, experience)