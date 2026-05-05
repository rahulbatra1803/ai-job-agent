"""
job_matcher.py
--------------
Hybrid scoring: TF-IDF + skill overlap + Groq AI (parallel, top 1 only).
Speed optimized — concurrent.futures for parallel AI calls.
"""

import json
import concurrent.futures
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from utils.groq_client import groq_chat


# ─────────────────────────────────────────
# LAYER 1 — TF-IDF
# ─────────────────────────────────────────

def calculate_text_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform([text1, text2])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except Exception:
        return 0.0


# ─────────────────────────────────────────
# LAYER 2 — SKILL OVERLAP
# ─────────────────────────────────────────

def calculate_skill_match(resume_skills: list, job_description: str) -> dict:
    if not resume_skills or not job_description:
        return {"matched_skills": [], "missing_skills": [], "match_percentage": 0}
    jd      = job_description.lower()
    matched = [s for s in resume_skills if s.lower() in jd]
    missing = [s for s in resume_skills if s.lower() not in jd]
    pct     = round(len(matched) / len(resume_skills) * 100, 1) if resume_skills else 0
    return {"matched_skills": matched, "missing_skills": missing, "match_percentage": pct}


# ─────────────────────────────────────────
# LAYER 3 — GROQ AI (top 1 only)
# ─────────────────────────────────────────

def ai_analyze_match(resume_data: dict, job: dict) -> dict:
    system_prompt = """
You are a senior technical recruiter with 15 years of hiring experience.
STRICT RULES:
- Respond ONLY in English.
- Return ONLY a valid JSON object — no markdown, no extra text.
- Be specific — reference actual content from resume and JD.
- recommendation: single actionable sentence, max 20 words.
"""
    resume_block = f"""
Candidate   : {resume_data.get('name', 'Unknown')}
Current Role: {resume_data.get('current_role', 'N/A')}
Experience  : {resume_data.get('total_experience_years', 0)} years
Skills      : {', '.join((resume_data.get('technical_skills') or resume_data.get('skills', []))[:15])}
Summary     : {resume_data.get('summary', '')}
Achievements: {'; '.join(resume_data.get('key_achievements', [])[:3])}
"""
    prompt = f"""
Return EXACTLY this JSON for the candidate vs job below:

{{
    "match_score": <0-100>,
    "fit_level": "<Excellent Fit|Good Fit|Moderate Fit|Low Fit>",
    "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
    "gaps": ["<gap 1>", "<gap 2>"],
    "recommendation": "<one actionable sentence>",
    "interview_tips": ["<tip 1>", "<tip 2>"]
}}

Scoring: 85-100=Excellent, 65-84=Good, 40-64=Moderate, 0-39=Low

RESUME: {resume_block}
JOB:
Title      : {job.get('title','')}
Company    : {job.get('company','')}
Description: {job.get('description','')[:800]}
"""
    try:
        response = groq_chat(prompt=prompt, system_prompt=system_prompt)
        s = response.find("{"); e = response.rfind("}") + 1
        return json.loads(response[s:e])
    except Exception:
        return {
            "match_score": 50, "fit_level": "Moderate Fit",
            "strengths": ["Relevant background"], "gaps": ["Unable to fully analyze"],
            "recommendation": "Review the job requirements and tailor your application.",
            "interview_tips": ["Review core concepts", "Prepare role-specific examples"]
        }


# ─────────────────────────────────────────
# FAST LOCAL SCORING
# ─────────────────────────────────────────

def _local_analysis(text_score: float, skill_analysis: dict) -> dict:
    base  = int(text_score * 50 + skill_analysis["match_percentage"] * 0.5)
    score = min(base + 30, 92)
    level = ("Good Fit"     if skill_analysis["match_percentage"] > 60 else
             "Moderate Fit" if skill_analysis["match_percentage"] > 30 else
             "Low Fit")
    return {
        "match_score": score, "fit_level": level,
        "strengths":   skill_analysis["matched_skills"][:3],
        "gaps":        skill_analysis["missing_skills"][:2],
        "recommendation": "Highlight your matching skills when applying.",
        "interview_tips": ["Prepare examples for matching skills", "Research the company"]
    }


# ─────────────────────────────────────────
# MAIN ENTRY — OPTIMIZED
# ─────────────────────────────────────────

def match_jobs(resume_data: dict, jobs: list) -> list:
    """
    Optimized pipeline:
    - Layer 1 + 2: All jobs simultaneously (vectorized, no API)
    - Layer 3 AI:  Only TOP 1 job (fastest path, best accuracy where it matters)
    - Parallel:    TF-IDF computed once for all jobs via batch transform
    """
    print(f"\n  Matching {len(jobs)} jobs...")

    resume_text = " ".join(filter(None, [
        resume_data.get("summary", ""),
        " ".join(resume_data.get("skills", [])),
        " ".join(resume_data.get("technical_skills", [])),
        resume_data.get("raw_text", "")[:800]
    ]))

    all_skills = list(dict.fromkeys(
        resume_data.get("skills", []) +
        resume_data.get("technical_skills", [])
    ))

    # ── Batch TF-IDF (all jobs at once — much faster than one-by-one) ──
    descriptions = [job.get("description", "") for job in jobs]
    all_texts    = [resume_text] + descriptions

    try:
        vectorizer  = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        resume_vec   = tfidf_matrix[0:1]
        job_vecs     = tfidf_matrix[1:]
        similarities = cosine_similarity(resume_vec, job_vecs)[0]
    except Exception:
        similarities = [0.0] * len(jobs)

    # ── Layer 2: Skill overlap for all jobs ──
    skill_results = [calculate_skill_match(all_skills, j.get("description","")) for j in jobs]

    # ── Local scoring for all jobs first ──
    results = []
    for i, job in enumerate(jobs):
        text_score     = float(similarities[i]) if i < len(similarities) else 0.0
        skill_analysis = skill_results[i]
        analysis       = _local_analysis(text_score, skill_analysis)
        final_score    = round(
            analysis["match_score"]            * 0.50 +
            skill_analysis["match_percentage"] * 0.30 +
            text_score * 100                   * 0.20
        )
        results.append({
            **job,
            "match_score":    final_score,
            "ai_score":       analysis["match_score"],
            "skill_match":    skill_analysis,
            "fit_level":      analysis["fit_level"],
            "strengths":      analysis["strengths"],
            "gaps":           analysis["gaps"],
            "recommendation": analysis["recommendation"],
            "interview_tips": analysis["interview_tips"],
            "_text_score":    text_score,
            "_skill":         skill_analysis,
        })

    # Sort first
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # ── Layer 3: AI only for TOP 1 job ──
    if results and results[0].get("description","") and len(results[0].get("description","")) > 50:
        print(f"    AI analysis: {results[0]['title']} @ {results[0]['company']}...")
        try:
            ai = ai_analyze_match(resume_data, results[0])
            ts = results[0]["_text_score"]
            sk = results[0]["_skill"]
            results[0].update({
                "match_score":    round(ai["match_score"]*0.50 + sk["match_percentage"]*0.30 + ts*100*0.20),
                "ai_score":       ai["match_score"],
                "fit_level":      ai["fit_level"],
                "strengths":      ai["strengths"],
                "gaps":           ai["gaps"],
                "recommendation": ai["recommendation"],
                "interview_tips": ai["interview_tips"],
            })
        except Exception:
            pass

    # Clean internal keys
    for r in results:
        r.pop("_text_score", None)
        r.pop("_skill", None)

    # Re-sort after AI update
    results.sort(key=lambda x: x["match_score"], reverse=True)
    print(f"  ✓ Top: {results[0]['title']} — {results[0]['match_score']}%")
    return results