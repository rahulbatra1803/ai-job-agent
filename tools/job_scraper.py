"""
job_scraper.py
--------------
Fetches real jobs from JSearch API (via RapidAPI).
Returns actual job listings with direct apply links.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
JSEARCH_HOST  = "jsearch.p.rapidapi.com"
JSEARCH_URL   = "https://jsearch.p.rapidapi.com/search"


def fetch_jobs_jsearch(job_title: str, location: str, num_jobs: int = 10) -> list:
    """
    Fetches real jobs from JSearch API.

    Args:
        job_title : e.g. "Python Developer"
        location  : e.g. "Bangalore"
        num_jobs  : how many jobs to return (max 10 per page)

    Returns:
        List of job dicts
    """
    if not RAPIDAPI_KEY:
        print("  ⚠ RAPIDAPI_KEY not found in .env — falling back to demo data.")
        return get_demo_jobs(job_title, location, num_jobs)

    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": JSEARCH_HOST
    }

    params = {
        "query":       f"{job_title} in {location}",
        "page":        "1",
        "num_pages":   "1",
        "date_posted": "month",       # jobs posted in last 30 days
        "country":     "in",          # India
        "language":    "en"
    }

    try:
        print(f"  Calling JSearch API: '{job_title}' in '{location}'...")
        response = requests.get(
            JSEARCH_URL,
            headers=headers,
            params=params,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            raw_jobs = data.get("data", [])

            if not raw_jobs:
                print("  No jobs returned by API — using demo data.")
                return get_demo_jobs(job_title, location, num_jobs)

            jobs = []
            for j in raw_jobs[:num_jobs]:
                # Build direct apply URL — prefer direct link over JSearch redirect
                apply_url = (
                    j.get("job_apply_link") or
                    j.get("job_google_link") or
                    ""
                )

                # Salary info
                salary = _format_salary(j)

                jobs.append({
                    "title":       j.get("job_title", "N/A"),
                    "company":     j.get("employer_name", "N/A"),
                    "location":    _format_location(j),
                    "salary":      salary,
                    "url":         apply_url,
                    "source":      j.get("job_publisher", "JSearch"),
                    "posted_at":   j.get("job_posted_at_datetime_utc", "")[:10],
                    "job_type":    j.get("job_employment_type", "Full-time"),
                    "is_remote":   j.get("job_is_remote", False),
                    "description": j.get("job_description", "")[:1500],
                    "highlights":  _extract_highlights(j),
                })

            print(f"  ✓ {len(jobs)} real jobs fetched from JSearch.")
            return jobs

        elif response.status_code == 429:
            print("  ⚠ Rate limit hit — using demo data.")
            return get_demo_jobs(job_title, location, num_jobs)

        else:
            print(f"  ⚠ JSearch returned {response.status_code} — using demo data.")
            return get_demo_jobs(job_title, location, num_jobs)

    except requests.Timeout:
        print("  ⚠ JSearch request timed out — using demo data.")
        return get_demo_jobs(job_title, location, num_jobs)

    except Exception as e:
        print(f"  ⚠ JSearch error: {e} — using demo data.")
        return get_demo_jobs(job_title, location, num_jobs)


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _format_location(job: dict) -> str:
    city    = job.get("job_city", "")
    state   = job.get("job_state", "")
    country = job.get("job_country", "")
    parts   = [p for p in [city, state, country] if p]
    return ", ".join(parts) if parts else "India"


def _format_salary(job: dict) -> str:
    min_s  = job.get("job_min_salary")
    max_s  = job.get("job_max_salary")
    period = job.get("job_salary_period", "")

    if min_s and max_s:
        return f"₹{int(min_s):,} – ₹{int(max_s):,} / {period or 'year'}"
    elif min_s:
        return f"₹{int(min_s):,}+ / {period or 'year'}"
    return "Not disclosed"


def _extract_highlights(job: dict) -> list:
    """Pulls out key requirement bullets from JSearch highlights."""
    highlights = job.get("job_highlights", {})
    quals      = highlights.get("Qualifications", [])
    resps      = highlights.get("Responsibilities", [])
    return (quals + resps)[:5]


# ─────────────────────────────────────────
# DEMO FALLBACK
# ─────────────────────────────────────────

def get_demo_jobs(job_title: str, location: str, num_jobs: int = 10) -> list:
    """Returns demo jobs when API is unavailable."""
    templates = [
        {
            "title":       f"Senior {job_title}",
            "company":     "TechCorp India",
            "salary":      "₹18,00,000 – ₹28,00,000 / year",
            "url":         "https://www.linkedin.com/jobs/",
            "source":      "Demo",
            "job_type":    "Full-time",
            "is_remote":   False,
            "description": f"We are looking for a Senior {job_title} with 4+ years experience. Must have strong Python, SQL, and cloud skills. Work with cross-functional teams to build scalable systems.",
            "highlights":  ["4+ years experience", "Strong Python skills", "Cloud platform experience"]
        },
        {
            "title":       f"{job_title} — Remote",
            "company":     "GlobalSoft",
            "salary":      "₹22,00,000 – ₹35,00,000 / year",
            "url":         "https://www.naukri.com/",
            "source":      "Demo",
            "job_type":    "Full-time",
            "is_remote":   True,
            "description": f"Remote {job_title} role. Competitive pay, flexible hours. 3+ years required. Strong communication and problem-solving skills needed.",
            "highlights":  ["Remote work", "3+ years experience", "Flexible hours"]
        },
        {
            "title":       f"Junior {job_title}",
            "company":     "StartupXYZ",
            "salary":      "₹6,00,000 – ₹10,00,000 / year",
            "url":         "https://www.indeed.co.in/",
            "source":      "Demo",
            "job_type":    "Full-time",
            "is_remote":   False,
            "description": f"Junior {job_title} opportunity at a fast-growing startup. 0-2 years experience. Great learning environment with mentorship.",
            "highlights":  ["0-2 years experience", "Mentorship provided", "Fast-growing startup"]
        },
        {
            "title":       f"{job_title} Lead",
            "company":     "Enterprise Solutions Ltd",
            "salary":      "₹35,00,000 – ₹50,00,000 / year",
            "url":         "https://www.glassdoor.co.in/",
            "source":      "Demo",
            "job_type":    "Full-time",
            "is_remote":   False,
            "description": f"Lead {job_title} to manage a team of 5-8 engineers. 7+ years experience required. Architecture design and stakeholder management skills essential.",
            "highlights":  ["7+ years experience", "Team leadership", "Architecture design"]
        },
        {
            "title":       f"{job_title} Consultant",
            "company":     "Deloitte India",
            "salary":      "₹25,00,000 – ₹40,00,000 / year",
            "url":         "https://apply.deloitte.com/",
            "source":      "Demo",
            "job_type":    "Full-time",
            "is_remote":   False,
            "description": f"Consultant role for {job_title} at Deloitte. Client-facing role, 5+ years experience. Strong communication and analytical skills.",
            "highlights":  ["Client-facing role", "5+ years experience", "Consulting mindset"]
        },
    ]

    results = []
    for i, t in enumerate(templates[:num_jobs]):
        results.append({
            **t,
            "location":  location,
            "posted_at": "2025-01-01",
        })
    return results


# ─────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────

def scrape_jobs(job_title: str, location: str = "India", num_jobs: int = 10) -> list:
    """
    Main entry point for job search.
    Uses JSearch API if RAPIDAPI_KEY is set, else demo data.
    """
    print(f"\n  Job search: '{job_title}' in '{location}' ({num_jobs} jobs)")
    return fetch_jobs_jsearch(job_title, location, num_jobs)


if __name__ == "__main__":
    jobs = scrape_jobs("Python Developer", "Bangalore", 5)
    for j in jobs:
        print(f"\n{j['title']} @ {j['company']}")
        print(f"  Location : {j['location']}")
        print(f"  Salary   : {j['salary']}")
        print(f"  Apply    : {j['url']}")
        print(f"  Remote   : {j['is_remote']}")