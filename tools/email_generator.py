"""
email_generator.py
------------------
Generates unique, job-specific application emails.
Each email is tailored to the exact role, company, and candidate profile.
"""

from utils.groq_client import groq_chat


def generate_application_email(resume_data: dict, job: dict) -> str:

    name         = resume_data.get("name", "[Your Name]")
    role         = resume_data.get("current_role", "Professional")
    experience   = resume_data.get("total_experience_years", 0)
    tech_skills  = resume_data.get("technical_skills", [])
    soft_skills  = resume_data.get("soft_skills", [])
    all_skills   = (tech_skills + soft_skills)[:10]
    achievements = resume_data.get("key_achievements", [])
    email_addr   = resume_data.get("email", "")
    phone        = resume_data.get("phone", "")
    linkedin     = resume_data.get("linkedin", "")

    # Build sign-off — only include fields that exist
    signoff_parts = [name]
    if phone:      signoff_parts.append(phone)
    if email_addr: signoff_parts.append(email_addr)
    signoff_line  = " | ".join(signoff_parts)
    linkedin_line = f"LinkedIn: {linkedin}" if linkedin else ""

    # Top 2 achievements for context
    ach_text = "\n".join(f"- {a}" for a in achievements[:2]) if achievements else "None listed"

    system_prompt = f"""
You are a professional job application email writer.

YOUR ONLY JOB: Write ONE unique email for THIS specific candidate applying to THIS specific job.

CRITICAL RULES:
1. DO NOT copy or reuse any example or template from your training data.
2. The email MUST mention the exact company name: {job.get('company', 'the company')}
3. The email MUST mention the exact job title: {job.get('title', 'the role')}
4. Paragraph 2 MUST reference skills/experience that directly appear in the job description provided — not generic skills.
5. NEVER use: "I am writing to express", "passionate", "dynamic", "I hope this email finds you", "Please find attached".
6. Keep it under 175 words total (excluding subject and sign-off).
7. Sound like a real human wrote it — confident, direct, specific.

SIGN-OFF FORMAT (use exactly as given, do not modify):
Best regards,
{signoff_line}
{linkedin_line}
"""

    prompt = f"""
Write a job application email. Use ONLY the information below — do not invent anything.

━━━ CANDIDATE ━━━
Full Name     : {name}
Current Role  : {role}
Experience    : {experience} years
Skills        : {", ".join(all_skills)}
Achievements  :
{ach_text}

━━━ JOB ━━━
Title         : {job.get('title', 'N/A')}
Company       : {job.get('company', 'N/A')}
Location      : {job.get('location', 'N/A')}
Requirements  :
{job.get('description', '')[:900]}

━━━ INSTRUCTIONS ━━━
- Subject line: Application for {job.get('title', 'N/A')} – {name}
- Paragraph 1 (2 sentences): State who you are, your experience, and that you are applying for THIS role at THIS company.
- Paragraph 2 (2-3 sentences): Pick 2 skills or achievements from the candidate data that DIRECTLY match the job requirements above. Be specific — mention the actual skill and how it relates to what this company needs.
- Paragraph 3 (1 sentence): Express interest in discussing further.
- End with the sign-off exactly as instructed in system prompt.

Write the email now. First line = Subject:
"""

    response = groq_chat(prompt=prompt, system_prompt=system_prompt)
    return response.strip()


def generate_all_emails(resume_data: dict, matched_jobs: list,
                        top_n: int = 5, tone: str = "professional") -> list:
    print(f"\n  Generating {top_n} unique application emails...")
    results = []

    for i, job in enumerate(matched_jobs):
        if i < top_n:
            print(f"    Email {i+1}/{top_n}: {job.get('title')} @ {job.get('company')}...")
            email = generate_application_email(resume_data, job)
            results.append({**job, "application_email": email})
        else:
            results.append({**job, "application_email": None})

    print(f"  Done — {top_n} emails generated.")
    return results