"""
agent.py
--------
Core pipeline orchestrator for the AI Job Application Agent.
Coordinates resume parsing, job search, matching, and cover letter generation.
"""

import os
import json
import tempfile
from dotenv import load_dotenv

from tools.resume_parser import parse_resume
from tools.job_scraper   import scrape_jobs
from tools.job_matcher   import match_jobs
from tools.email_generator import generate_all_emails

load_dotenv()

# ─────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────

def run_pipeline(
    resume_file_path: str,
    job_title: str,
    location: str = "India",
    num_jobs: int = 10,
    email_tone: str = "professional"
) -> dict:
    """
    Runs the full job search pipeline in 4 steps:
      1. Parse resume
      2. Search jobs
      3. AI match analysis
      4. Generate cover letters

    Returns a results dict with status, resume_data, and matched_jobs.
    """
    results = {
        "status":       "running",
        "resume_data":  None,
        "jobs":         [],
        "matched_jobs": [],
        "error":        None
    }

    try:
        # ── Step 1: Resume ──
        print("\n[1/4] Parsing resume...")
        resume_data = parse_resume(resume_file_path)
        results["resume_data"] = resume_data
        print(f"      Done — {len(resume_data.get('skills', []))} skills extracted.")

        # ── Step 2: Job Search ──
        print(f"\n[2/4] Searching jobs: '{job_title}' in '{location}'...")
        jobs = scrape_jobs(job_title, location, num_jobs)
        results["jobs"] = jobs
        print(f"      Done — {len(jobs)} jobs found.")

        # ── Step 3: Matching ──
        print("\n[3/4] Running AI match analysis...")
        matched_jobs = match_jobs(resume_data, jobs)
        print(f"      Done — top match: {matched_jobs[0]['title']} ({matched_jobs[0]['match_score']}%)")

        # ── Step 4: Cover Letters ──
        print("\n[4/4] Generating cover letters...")
        final_results = generate_all_emails(
            resume_data,
            matched_jobs,
            top_n=5,
            tone=email_tone
        )
        letters_count = sum(1 for j in final_results if j.get("cover_letter"))
        print(f"      Done — {letters_count} cover letters generated.")

        results["matched_jobs"] = final_results
        results["status"]       = "success"
        print("\n✓ Pipeline complete.\n")

    except Exception as e:
        results["status"] = "error"
        results["error"]  = str(e)
        print(f"\n✗ Pipeline error: {e}\n")

    return results


if __name__ == "__main__":
    print("Agent module loaded. Run via: python app.py")