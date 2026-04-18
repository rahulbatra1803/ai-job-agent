# 🤖 AI Job Application Agent

An autonomous AI agent that automates your entire job search — from resume parsing to personalized application emails.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![Groq](https://img.shields.io/badge/Groq-LLaMA3-orange) ![RapidAPI](https://img.shields.io/badge/RapidAPI-JSearch-red)

---

## What It Does

1. **Parses your resume** (PDF/DOCX) using Groq LLaMA 3 to extract skills, experience, and achievements
2. **Searches real jobs** via RapidAPI JSearch (LinkedIn, Indeed, Glassdoor)
3. **Ranks matches** using a hybrid scoring engine (TF-IDF + skill overlap + Groq AI)
4. **Generates unique emails** tailored to each job's specific requirements
5. **Suggests top 5 matches** via an agent confirmation UI with direct apply links

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| AI/LLM | Groq SDK (LLaMA 3-70B) |
| Job Search | RapidAPI JSearch |
| ML Matching | scikit-learn (TF-IDF, Cosine Similarity) |
| Resume Parsing | PyPDF2, python-docx |
| Frontend | HTML, CSS, JavaScript |
| Streaming | Flask SSE + Background Threading |

---

## Project Structure

```
job-agent/
├── app.py                  # Flask server + SSE streaming + /suggest route
├── agent.py                # Pipeline orchestrator
├── tools/
│   ├── resume_parser.py    # PDF/DOCX → structured JSON via Groq
│   ├── job_scraper.py      # RapidAPI JSearch integration
│   ├── job_matcher.py      # TF-IDF + skill overlap + Groq AI scoring
│   └── email_generator.py  # Per-job unique email generation
├── utils/
│   └── groq_client.py      # Groq API wrapper
├── templates/
│   └── index.html          # Frontend UI
├── static/
│   ├── css/style.css
│   └── js/main.js
├── .env                    # API keys (not committed)
└── requirements.txt
```

---

## Setup & Run

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/ai-job-agent.git
cd ai-job-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API keys
Create a `.env` file in the root directory:
```
GROQ_API_KEY=your_groq_api_key_here
RAPIDAPI_KEY=your_rapidapi_key_here
```

Get your keys:
- **Groq API** (free): https://console.groq.com
- **RapidAPI JSearch** (free tier): https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

### 4. Run
```bash
python app.py
```

Open `http://localhost:5000` in your browser.

---

## How It Works

```
Resume Upload → Groq AI Parse → RapidAPI Job Search → ML Match Scoring → Email Generation → Apply
```

Pipeline runs in a **background thread** while the frontend receives live updates via **Server-Sent Events (SSE)** — no page reloads.

---

## Key Features

- Live progress streaming via SSE
- Real job listings with direct apply URLs
- Hybrid match scoring — TF-IDF + skill overlap + Groq AI
- Unique application email per job
- In-browser email editing before download
- Groq-powered autocomplete for job title and location
- Agent confirmation UI — top 5 recommendations with one-click apply

---

## License

MIT License