"""
job_scraper.py
--------------
Fetches real jobs from JSearch API (via RapidAPI).
Supports: job type (job/internship), experience level, fresh listings only.

Fixes:
  - Removed employment_types=INTERN filter (breaks India results)
  - Smart retry: simpler query if first attempt returns 0 results
  - Demo data uses real search URLs instead of homepages
  - Source icon shown on every job card
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_URL  = "https://jsearch.p.rapidapi.com/search"

# Experience level → query modifier (kept short for better JSearch India results)
EXPERIENCE_QUERY = {
    "fresher": "fresher entry level",
    "1yr":     "1 year experience",
    "2-3yr":   "2 3 years experience",
    "4+yr":    "senior",
}

# Platform priority order (lower index = higher priority)
PRIORITY_PLATFORMS = ["linkedin", "naukri", "internshala", "indeed"]


def _priority(job: dict) -> int:
    src = (job.get("job_publisher") or "").lower()
    for i, p in enumerate(PRIORITY_PLATFORMS):
        if p in src:
            return i
    return len(PRIORITY_PLATFORMS)


def _build_query(job_title: str, location: str, job_type: str, experience: str) -> str:
    """Build a smart JSearch query string — kept short for better India results."""
    if job_type == "internship":
        # For internships, experience modifier not needed — internship keyword is enough
        return f"{job_title} internship in {location}"
    else:
        exp = EXPERIENCE_QUERY.get(experience, "")
        return f"{job_title} {exp} in {location}".strip()


def _parse_jobs(raw_jobs: list, num_jobs: int) -> list:
    """Sort by platform priority and parse into standard format."""
    sorted_jobs = sorted(raw_jobs, key=_priority)
    jobs = []
    for j in sorted_jobs[:num_jobs]:
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
    return jobs


def fetch_jobs_jsearch(
    job_title: str,
    location:  str,
    num_jobs:  int  = 10,
    job_type:  str  = "job",
    experience: str = "fresher"
) -> list:

    if not RAPIDAPI_KEY:
        print("  ⚠ RAPIDAPI_KEY not found — using demo data.")
        return get_demo_jobs(job_title, location, num_jobs, job_type)

    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": JSEARCH_HOST
    }

    # ── Attempt 1: Full query with experience modifier ──
    query_1 = _build_query(job_title, location, job_type, experience)
    params  = {
        "query":       query_1,
        "page":        "1",
        "num_pages":   "1",
        "date_posted": "week",   # Fresh jobs only — last 7 days
        "country":     "in",
        "language":    "en"
        # NOTE: employment_types=INTERN removed — JSearch India ignores it
        #       and it causes 0 results for internship searches.
        #       We rely on query keywords instead ("internship", "fresher" etc.)
    }

    raw_jobs = _api_call(headers, params, query_1)

    # ── Attempt 2: Simpler query if no results ──
    if not raw_jobs:
        query_2 = f"{job_title} internship in {location}" if job_type == "internship" else f"{job_title} in {location}"
        print(f"  Retry with simpler query: '{query_2}'")
        params["query"]       = query_2
        params["date_posted"] = "month"   # Widen date range on retry
        raw_jobs = _api_call(headers, params, query_2)

    # ── Attempt 3: Bare title + location, no date filter ──
    if not raw_jobs:
        query_3 = f"{job_title} {location}"
        print(f"  Retry bare query: '{query_3}'")
        params["query"] = query_3
        params.pop("date_posted", None)
        raw_jobs = _api_call(headers, params, query_3)

    if not raw_jobs:
        print("  No results after 3 attempts — using demo data.")
        return get_demo_jobs(job_title, location, num_jobs, job_type)

    jobs = _parse_jobs(raw_jobs, num_jobs)
    print(f"  ✓ {len(jobs)} jobs fetched. Top sources: {[j['source'] for j in jobs[:3]]}")
    return jobs


def _api_call(headers: dict, params: dict, label: str) -> list:
    """Makes one JSearch API call. Returns raw job list or [] on failure."""
    try:
        print(f"  JSearch query: '{label}'")
        resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=15)

        if resp.status_code == 200:
            data = resp.json().get("data", [])
            print(f"    → {len(data)} results")
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


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _format_location(job: dict) -> str:
    parts = [p for p in [
        job.get("job_city", ""),
        job.get("job_state", ""),
        job.get("job_country", "")
    ] if p]
    return ", ".join(parts) if parts else "India"


def _format_salary(job: dict) -> str:
    mn = job.get("job_min_salary")
    mx = job.get("job_max_salary")
    p  = job.get("job_salary_period", "year")
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
    if "foundit"     in s: return "🔵 Foundit"
    if "shine"       in s: return "🟣 Shine"
    return f"⚪ {source}"


# ─────────────────────────────────────────
# DEMO FALLBACK  (used only when API fails)
# ─────────────────────────────────────────

def get_demo_jobs(job_title: str, location: str, num_jobs: int = 10, job_type: str = "job") -> list:
    is_intern = job_type == "internship"

    # Real search URLs instead of homepages
    encoded_title    = job_title.replace(" ", "%20")
    encoded_location = location.replace(" ", "%20")

    linkedin_url    = f"https://www.linkedin.com/jobs/search/?keywords={encoded_title}%20{'internship' if is_intern else ''}&location={encoded_location}"
    naukri_url      = f"https://www.naukri.com/{job_title.lower().replace(' ', '-')}-jobs-in-{location.lower().replace(' ', '-')}"
    internshala_url = f"https://internshala.com/internships/{job_title.lower().replace(' ', '-')}-internship-in-{location.lower().replace(' ', '-')}/"
    indeed_url      = f"https://in.indeed.com/jobs?q={encoded_title}{'%20internship' if is_intern else ''}&l={encoded_location}"

    salary = "₹8,000 – ₹15,000 / month (Stipend)" if is_intern else "₹18,00,000 – ₹28,00,000 / year"
    jtype  = "Internship" if is_intern else "Full-time"

    templates = [
        {
            "title":       f"{job_title} {'Intern' if is_intern else 'Developer'} — Remote",
            "company":     "TechCorp India",
            "salary":      salary,
            "url":         linkedin_url,
            "source":      "LinkedIn (Demo)",
            "source_icon": "🔵 LinkedIn",
            "job_type":    jtype,
            "is_remote":   True,
            "description": f"{'Internship' if is_intern else 'Full-time'} {job_title} role. Strong fundamentals required. {'Stipend provided.' if is_intern else 'Competitive salary.'}",
            "highlights":  ["Strong fundamentals", "Team player", "Good communication"]
        },
        {
            "title":       f"Junior {job_title}",
            "company":     "StartupXYZ",
            "salary":      salary,
            "url":         naukri_url,
            "source":      "Naukri (Demo)",
            "source_icon": "🟠 Naukri",
            "job_type":    jtype,
            "is_remote":   False,
            "description": f"Junior {job_title} opportunity at a fast-growing startup. Great learning environment with mentorship.",
            "highlights":  ["Mentorship provided", "Fast-growing startup", "Learning culture"]
        },
        {
            "title":       f"{job_title} {'Intern' if is_intern else 'Developer'} — On-site",
            "company":     "GlobalSoft",
            "salary":      salary,
            "url":         internshala_url if is_intern else indeed_url,
            "source":      "Internshala (Demo)" if is_intern else "Indeed (Demo)",
            "source_icon": "🟢 Internshala" if is_intern else "🔴 Indeed",
            "job_type":    jtype,
            "is_remote":   False,
            "description": f"On-site {job_title} {'internship' if is_intern else 'role'}. Work with experienced professionals.",
            "highlights":  ["On-site role", "Experienced team", "Growth opportunity"]
        },
        {
            "title":       f"Senior {job_title}",
            "company":     "Enterprise Solutions Ltd",
            "salary":      "₹35,00,000 – ₹50,00,000 / year",
            "url":         linkedin_url,
            "source":      "LinkedIn (Demo)",
            "source_icon": "🔵 LinkedIn",
            "job_type":    "Full-time",
            "is_remote":   False,
            "description": f"Lead {job_title} role. 7+ years experience required. Architecture design and stakeholder management.",
            "highlights":  ["7+ years experience", "Team leadership", "Architecture design"]
        },
        {
            "title":       f"{job_title} Consultant",
            "company":     "Deloitte India",
            "salary":      "₹25,00,000 – ₹40,00,000 / year",
            "url":         indeed_url,
            "source":      "Indeed (Demo)",
            "source_icon": "🔴 Indeed",
            "job_type":    "Full-time",
            "is_remote":   False,
            "description": f"Consultant role for {job_title} at a top firm. Client-facing, 5+ years experience required.",
            "highlights":  ["Client-facing role", "5+ years experience", "Consulting mindset"]
        },
    ]

    return [
        {**t, "location": location, "posted_at": "2026-05-01"}
        for t in templates[:num_jobs]
    ]


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
    return fetch_jobs_jsearch(job_title, location, num_jobs, job_type, experience)


if __name__ == "__main__":
    jobs = scrape_jobs("Python Developer", "Bangalore", 5, "job", "fresher")
    for j in jobs:
        print(f"\n{j['title']} @ {j['company']}")
        print(f"  Source  : {j['source_icon']}")
        print(f"  Location: {j['location']}")
        print(f"  Salary  : {j['salary']}")
        print(f"  Apply   : {j['url']}")