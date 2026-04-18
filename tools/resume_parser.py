"""
resume_parser.py
----------------
Extracts and analyzes resume content from PDF or DOCX files.
Uses a chain-of-thought prompt for maximum extraction accuracy.
"""

import PyPDF2
import docx
import json
from utils.groq_client import groq_chat


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def extract_text_from_docx(file_path: str) -> str:
    doc  = docx.Document(file_path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return text.strip()


def extract_text(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        return extract_text_from_docx(file_path)
    raise ValueError("Only PDF and DOCX files are supported.")


def analyze_resume(resume_text: str) -> dict:
    """
    Uses a chain-of-thought prompt to extract structured data
    from raw resume text with high accuracy.
    """

    system_prompt = """
You are a senior technical recruiter and resume parsing specialist.
Your task is to extract EVERY piece of information from the resume — 
do NOT skip any skill, role, achievement, or date mentioned.

STRICT RULES:
- Extract skills exactly as written — do not rename or generalize.
- Dates must be copied verbatim from the resume.
- If a field is missing, use null — never guess or fabricate.
- For total_experience_years: calculate from earliest job start to latest end (or present).
- Return ONLY valid JSON. No explanation, no markdown, no extra text.
"""

    prompt = f"""
Read the resume below carefully. Think step by step:

STEP 1 — Identify personal info (name, email, phone, LinkedIn, GitHub).
STEP 2 — List ALL technical skills exactly as written (languages, frameworks, tools, platforms).
STEP 3 — List ALL soft skills mentioned.
STEP 4 — Extract each work experience entry (company, role, start date, end date, key points).
STEP 5 — Extract education entries (degree, institution, year, GPA if present).
STEP 6 — Extract certifications, projects, awards if any.
STEP 7 — Calculate total years of experience from the earliest start date to today.
STEP 8 — Write a 2-sentence professional summary based ONLY on what is in the resume.

Return this exact JSON structure (no extra fields, no missing fields):

{{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "linkedin": "string or null",
  "github": "string or null",
  "total_experience_years": number,
  "current_role": "most recent job title or null",
  "current_company": "most recent company or null",
  "skills": ["all skills combined list"],
  "technical_skills": ["languages, frameworks, tools, cloud, databases"],
  "soft_skills": ["communication, leadership, etc."],
  "experience": [
    {{
      "company": "string",
      "role": "string",
      "start_date": "string",
      "end_date": "string or Present",
      "duration": "string",
      "highlights": ["bullet point 1", "bullet point 2"]
    }}
  ],
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "year": "string",
      "gpa": "string or null"
    }}
  ],
  "certifications": ["cert1", "cert2"],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "tech_used": ["tech1", "tech2"]
    }}
  ],
  "key_achievements": ["achievement1", "achievement2"],
  "summary": "2-sentence professional summary",
  "job_search_keywords": ["keyword1", "keyword2"]
}}

RESUME TEXT:
{resume_text}
"""

    response = groq_chat(prompt=prompt, system_prompt=system_prompt, model="llama-3.3-70b-versatile")

    try:
        start = response.find("{")
        end   = response.rfind("}") + 1
        return json.loads(response[start:end])
    except json.JSONDecodeError:
        # Fallback — return minimal structure with raw text
        return {
            "name": None, "email": None, "phone": None,
            "total_experience_years": 0, "current_role": None,
            "skills": [], "technical_skills": [], "soft_skills": [],
            "experience": [], "education": [], "certifications": [],
            "projects": [], "key_achievements": [],
            "summary": resume_text[:300],
            "job_search_keywords": [],
            "raw_text": resume_text
        }


def parse_resume(file_path: str) -> dict:
    """
    Main entry point. Accepts a file path, returns structured resume data.
    """
    print(f"  Extracting text from: {file_path}")
    raw_text = extract_text(file_path)
    print(f"  Extracted {len(raw_text)} characters.")

    print("  Running AI analysis...")
    data = analyze_resume(raw_text)
    data["raw_text"] = raw_text
    return data