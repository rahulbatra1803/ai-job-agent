"""
job_matcher.py
--------------
Compares resume against job listings using a hybrid scoring approach:
TF-IDF cosine similarity + skill overlap + Groq AI analysis.
"""

import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from utils.groq_client import groq_chat


# ─────────────────────────────────────────
# SIMILARITY SCORING
# ─────────────────────────────────────────

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Computes TF-IDF cosine similarity between resume and job description.
    Returns a float between 0.0 (no overlap) and 1.0 (identical).
    """
    if not text1 or not text2:
        return 0.0
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform([text1, text2])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except Exception:
        return 0.0


def calculate_skill_match(resume_skills: list, job_description: str) -> dict:
    """
    Checks which resume skills appear in the job description.

    Returns:
        matched_skills   : skills found in JD
        missing_skills   : skills not found in JD
        match_percentage : % of resume skills present in JD
    """
    if not resume_skills or not job_description:
        return {"matched_skills": [], "missing_skills": [], "match_percentage": 0}

    jd_lower = job_description.lower()
    matched  = [s for s in resume_skills if s.lower() in jd_lower]
    missing  = [s for s in resume_skills if s.lower() not in jd_lower]
    pct      = round(len(matched) / len(resume_skills) * 100, 1) if resume_skills else 0

    return {"matched_skills": matched, "missing_skills": missing, "match_percentage": pct}


# ─────────────────────────────────────────
# AI ANALYSIS
# ─────────────────────────────────────────

def ai_analyze_match(resume_data: dict, job: dict) -> dict:
    """
    Uses Groq LLaMA to perform a deep recruiter-style match analysis.
    Called only for the top 3 jobs to stay within rate limits.

    Returns a dict with match_score, fit_level, strengths, gaps,
    recommendation, and interview_tips.
    """

    system_prompt = """
You are a senior technical recruiter with 15 years of hiring experience.
Analyze the resume and job description below and evaluate the candidate's fit.

STRICT RULES:
- Respond ONLY in English. Never use Hindi, Hinglish, or any other language.
- Return ONLY a valid JSON object — no explanation, no markdown, no extra text.
- Be specific and honest — do not inflate scores or give generic feedback.
- strengths and gaps must reference actual content from the resume and JD.
- recommendation must be a single actionable sentence (max 20 words).
- interview_tips must be role-specific, not generic.
"""

    resume_block = f"""
Candidate  : {resume_data.get('name', 'Unknown')}
Current Role: {resume_data.get('current_role', 'N/A')}
Experience  : {resume_data.get('total_experience_years', 0)} years
Skills      : {', '.join((resume_data.get('technical_skills') or resume_data.get('skills', []))[:15])}
Summary     : {resume_data.get('summary', '')}
Achievements: {'; '.join(resume_data.get('key_achievements', [])[:3])}
"""

    prompt = f"""
Evaluate this candidate for the role below and return EXACTLY this JSON structure:

{{
    "match_score": <integer 0-100>,
    "fit_level": "<Excellent Fit | Good Fit | Moderate Fit | Low Fit>",
    "strengths": ["<specific strength 1>", "<specific strength 2>", "<specific strength 3>"],
    "gaps": ["<specific gap 1>", "<specific gap 2>"],
    "recommendation": "<one actionable sentence in English>",
    "interview_tips": ["<role-specific tip 1>", "<role-specific tip 2>"]
}}

Scoring guide:
  85-100 → Excellent Fit  (meets nearly all requirements)
  65-84  → Good Fit       (meets most requirements, minor gaps)
  40-64  → Moderate Fit   (meets some requirements, notable gaps)
  0-39   → Low Fit        (significant mismatch)

RESUME:
{resume_block}

JOB:
Title      : {job.get('title', '')}
Company    : {job.get('company', '')}
Description: {job.get('description', '')[:1000]}
"""

    response = groq_chat(prompt=prompt, system_prompt=system_prompt)

    try:
        start = response.find("{")
        end   = response.rfind("}") + 1
        return json.loads(response[start:end])
    except Exception:
        return {
            "match_score":     50,
            "fit_level":       "Moderate Fit",
            "strengths":       ["Relevant background"],
            "gaps":            ["Unable to fully analyze"],
            "recommendation":  "Review the job requirements and tailor your application.",
            "interview_tips":  ["Review core technical concepts", "Prepare role-specific examples"]
        }


# ─────────────────────────────────────────
# FAST LOCAL SCORING (jobs 4–N)
# ─────────────────────────────────────────

def _local_analysis(text_score: float, skill_analysis: dict) -> dict:
    """
    Lightweight analysis for jobs beyond the top 3.
    No API call — uses skill overlap and TF-IDF score only.
    """
    base   = int(text_score * 50 + skill_analysis["match_percentage"] * 0.5)
    score  = min(base + 30, 92)
    level  = (
        "Good Fit"     if skill_analysis["match_percentage"] > 60 else
        "Moderate Fit" if skill_analysis["match_percentage"] > 30 else
        "Low Fit"
    )
    return {
        "match_score":    score,
        "fit_level":      level,
        "strengths":      skill_analysis["matched_skills"][:3],
        "gaps":           skill_analysis["missing_skills"][:2],
        "recommendation": "Review the job description and highlight matching skills in your application.",
        "interview_tips": ["Prepare examples for your top matching skills",
                           "Research the company before applying"]
    }


# ─────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────

def match_jobs(resume_data: dict, jobs: list) -> list:
    """
    Scores all jobs against the resume using a 3-layer hybrid approach:
      Layer 1 — TF-IDF cosine similarity       (fast, lexical)
      Layer 2 — Skill keyword overlap           (fast, precise)
      Layer 3 — Groq AI recruiter analysis      (deep, top 3 only)

    Final score = AI(50%) + Skill(30%) + TF-IDF(20%)

    Returns jobs sorted by match_score descending.
    """
    print(f"\n  Matching {len(jobs)} jobs against resume...")

    resume_text = " ".join(filter(None, [
        resume_data.get("summary", ""),
        " ".join(resume_data.get("skills", [])),
        " ".join(resume_data.get("technical_skills", [])),
        resume_data.get("raw_text", "")[:1000]
    ]))

    all_skills = list(dict.fromkeys(
        resume_data.get("skills", []) +
        resume_data.get("technical_skills", [])
    ))

    results = []

    for i, job in enumerate(jobs):
        print(f"    [{i+1}/{len(jobs)}] {job.get('title', 'Unknown')} @ {job.get('company', '')}")

        jd = job.get("description", "")

        # Layer 1 — TF-IDF
        text_score = calculate_text_similarity(resume_text, jd)

        # Layer 2 — Skill overlap
        skill_analysis = calculate_skill_match(all_skills, jd)

        # Layer 3 — AI (top 3 only to avoid timeouts)
        if jd and len(jd) > 50 and i < 3:
            try:
                analysis = ai_analyze_match(resume_data, job)
            except Exception:
                analysis = _local_analysis(text_score, skill_analysis)
        else:
            analysis = _local_analysis(text_score, skill_analysis)

        # Composite score
        final_score = round(
            analysis["match_score"]            * 0.50 +
            skill_analysis["match_percentage"] * 0.30 +
            text_score * 100                   * 0.20
        )

        results.append({
            **job,
            "match_score":  final_score,
            "ai_score":     analysis["match_score"],
            "skill_match":  skill_analysis,
            "fit_level":    analysis["fit_level"],
            "strengths":    analysis["strengths"],
            "gaps":         analysis["gaps"],
            "recommendation": analysis["recommendation"],
            "interview_tips": analysis["interview_tips"]
        })

    results.sort(key=lambda x: x["match_score"], reverse=True)
    print(f"\n  Top match: {results[0]['title']} — {results[0]['match_score']}%")
    return results


# ─────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    dummy_resume = {
        "name": "Rahul Sharma",
        "skills": ["Python", "Machine Learning", "SQL", "FastAPI"],
        "technical_skills": ["TensorFlow", "Docker", "Git"],
        "summary": "Python developer with 3 years of ML and backend experience.",
        "total_experience_years": 3,
        "current_role": "Software Engineer"
    }
    dummy_job = {
        "title": "Python Developer",
        "company": "TechCorp",
        "description": "Seeking Python developer with ML experience. FastAPI, SQL, Docker required."
    }
    result = match_jobs(dummy_resume, [dummy_job])
    print(f"Score : {result[0]['match_score']}%")
    print(f"Level : {result[0]['fit_level']}")
    print(f"Rec   : {result[0]['recommendation']}")