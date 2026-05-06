"""
app.py — Flask Server
AI Job Application Agent
"""

import os
import json
import tempfile
import threading
import queue
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Per-session progress queues
progress_queues = {}

# ── Fixed job count — 10 is optimal (speed + quality balance)
NUM_JOBS = 10


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        job_title  = request.form.get('job_title', '').strip()
        location   = request.form.get('location', '').strip()
        tone       = request.form.get('tone', 'professional')
        job_type = 'job'
        experience = request.form.get('experience', 'fresher')

        if not job_title:
            return jsonify({'error': 'Job title is required.'}), 400

        if 'resume' not in request.files:
            return jsonify({'error': 'Resume file is required.'}), 400

        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected.'}), 400

        suffix = '.pdf' if file.filename.lower().endswith('.pdf') else '.docx'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        file.save(tmp.name)
        tmp.close()

        session_id = f"sess_{int(time.time() * 1000)}"
        progress_queues[session_id] = queue.Queue()

        t = threading.Thread(
            target=_run_pipeline_thread,
            args=(session_id, tmp.name, job_title, location, tone, job_type, experience),
            daemon=True
        )
        t.start()

        return jsonify({'session_id': session_id})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/progress/<session_id>')
def progress(session_id):
    def event_stream():
        q = progress_queues.get(session_id)
        if not q:
            yield _sse({'type': 'error', 'message': 'Invalid session.'})
            return

        while True:
            try:
                msg = q.get(timeout=120)
                yield _sse(msg)
                if msg.get('type') in ('done', 'error'):
                    progress_queues.pop(session_id, None)
                    break
            except queue.Empty:
                yield _sse({'type': 'error', 'message': 'Pipeline timed out.'})
                break

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/suggest', methods=['POST'])
def suggest():
    try:
        data  = request.get_json()
        field = data.get('field', 'job_title')
        query = data.get('query', '').strip()

        if len(query) < 2:
            return jsonify({'suggestions': []})

        from utils.groq_client import groq_chat

        if field == 'job_title':
            prompt = f"""User is typing a job title: "{query}"
Return exactly 5 relevant job title suggestions as a JSON array of strings.
Examples of good suggestions for "py": ["Python Developer", "Python Backend Engineer", "Python Data Scientist", "Python ML Engineer", "Python Full Stack Developer"]
Return ONLY the JSON array, nothing else."""
        else:
            prompt = f"""User is typing a city/location in India: "{query}"
Return exactly 5 Indian city suggestions as a JSON array of strings.
Examples for "del": ["Delhi", "Delhi NCR", "New Delhi", "Dehradun", "Delhiwala"]
Return ONLY the JSON array, nothing else."""

        response = groq_chat(prompt=prompt, system_prompt="Return only a valid JSON array of 5 strings.")

        start = response.find('[')
        end   = response.rfind(']') + 1
        suggestions = json.loads(response[start:end]) if start != -1 else []
        return jsonify({'suggestions': suggestions[:5]})

    except Exception as e:
        return jsonify({'suggestions': [], 'error': str(e)})


# ─────────────────────────────────────────────
# PIPELINE THREAD
# ─────────────────────────────────────────────

def _run_pipeline_thread(session_id, resume_path, job_title, location, tone, job_type='job', experience='fresher'):
    q = progress_queues.get(session_id)
    if not q:
        return

    def push(type_, **kwargs):
        q.put({'type': type_, **kwargs})

    try:
        from tools.resume_parser   import parse_resume
        from tools.job_scraper     import scrape_jobs
        from tools.job_matcher     import match_jobs
        from tools.email_generator import generate_all_emails

        # Step 1 — Resume
        push('progress', step=1, message='Parsing your resume...')
        resume_data = parse_resume(resume_path)
        push('progress', step=1, message=f'Resume parsed — {len(resume_data.get("skills", []))} skills found.')

        # Step 2 — Jobs (hardcoded NUM_JOBS=10)
        push('progress', step=2, message=f'Searching jobs: {job_title} in {location}...')
        jobs = scrape_jobs(job_title, location, NUM_JOBS, job_type, experience)
        push('progress', step=2, message=f'{len(jobs)} jobs found.')

        # Step 3 — Match
        push('progress', step=3, message='Running AI match analysis...')
        matched_jobs = match_jobs(resume_data, jobs)
        push('progress', step=3, message='Match analysis complete.')

        # Step 4 — Emails
        push('progress', step=4, message='Generating application emails...')
        final_results = generate_all_emails(resume_data, matched_jobs, top_n=5, tone=tone)
        push('progress', step=4, message='Application emails ready.')

        try:
            os.unlink(resume_path)
        except Exception:
            pass

        push('done', resume=resume_data, jobs=final_results)

    except Exception as e:
        push('error', message=str(e))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)