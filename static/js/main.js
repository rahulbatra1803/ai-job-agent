/* ─────────────────────────────────────────
   AI Job Agent — main.js
───────────────────────────────────────── */

// ── DOM refs ──
const form          = document.getElementById('jobForm');
const submitBtn     = document.getElementById('submitBtn');
const formPanel     = document.getElementById('formPanel');
const progressPanel = document.getElementById('progressPanel');
const resultsPanel  = document.getElementById('resultsPanel');
const resetBtn      = document.getElementById('resetBtn');
const uploadZone    = document.getElementById('uploadZone');
const resumeFile    = document.getElementById('resumeFile');
const uploadInner   = document.getElementById('uploadInner');
const uploadSelected= document.getElementById('uploadSelected');
const fileNameEl    = document.getElementById('fileName');
const removeFileBtn = document.getElementById('removeFile');

// ── State ──
let currentResults = null;

// ─────────────────────────────────────────
// FILE UPLOAD
// ─────────────────────────────────────────

uploadZone.addEventListener('click', () => resumeFile.click());

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});

resumeFile.addEventListener('change', () => {
  if (resumeFile.files[0]) setFile(resumeFile.files[0]);
});

removeFileBtn.addEventListener('click', e => {
  e.stopPropagation();
  resumeFile.value = '';
  uploadInner.style.display = 'flex';
  uploadSelected.style.display = 'none';
});

function setFile(f) {
  fileNameEl.textContent = f.name;
  uploadInner.style.display = 'none';
  uploadSelected.style.display = 'flex';
}


// ─────────────────────────────────────────
// FORM SUBMIT
// ─────────────────────────────────────────

form.addEventListener('submit', async e => {
  e.preventDefault();

  if (!resumeFile.files[0]) { showFormError('Please upload your resume.'); return; }
  if (!document.getElementById('jobTitle').value.trim()) { showFormError('Job title is required.'); return; }
  if (!document.getElementById('location').value.trim()) { showFormError('Location is required.'); return; }

  const fd = new FormData(form);

  submitBtn.disabled = true;
  submitBtn.querySelector('.btn-text').textContent = 'Starting...';

  try {
    const res  = await fetch('/analyze', { method: 'POST', body: fd });
    const data = await res.json();

    if (!res.ok || data.error) {
      showFormError(data.error || 'Server error. Please try again.');
      resetSubmitBtn();
      return;
    }

    // Show progress panel
    formPanel.style.display = 'none';
    progressPanel.style.display = 'block';
    resultsPanel.style.display = 'none';

    // Start SSE
    listenProgress(data.session_id);

  } catch (err) {
    showFormError('Network error: ' + err.message);
    resetSubmitBtn();
  }
});

// ─────────────────────────────────────────
// SSE PROGRESS
// ─────────────────────────────────────────

function listenProgress(sessionId) {
  const es = new EventSource(`/progress/${sessionId}`);

  es.onmessage = e => {
    const msg = JSON.parse(e.data);

    if (msg.type === 'progress') {
      updateStep(msg.step, msg.message);
    }
    else if (msg.type === 'done') {
      es.close();
      markAllDone();
      setTimeout(() => showResults(msg.resume, msg.jobs), 600);
    }
    else if (msg.type === 'error') {
      es.close();
      progressPanel.style.display = 'none';
      formPanel.style.display = 'block';
      showFormError('Error: ' + msg.message);
      resetSubmitBtn();
    }
  };

  es.onerror = () => {
    es.close();
    progressPanel.style.display = 'none';
    formPanel.style.display = 'block';
    showFormError('Connection lost. Please try again.');
    resetSubmitBtn();
  };
}

function updateStep(step, message) {
  // Mark previous steps done
  for (let i = 1; i < step; i++) {
    const el = document.getElementById(`ps${i}`);
    el.classList.remove('active');
    el.classList.add('done');
    document.getElementById(`pm${i}`).textContent = '✓ Done';
  }
  // Activate current step
  const cur = document.getElementById(`ps${step}`);
  cur.classList.add('active');
  document.getElementById(`pm${step}`).textContent = message;
}

function markAllDone() {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`ps${i}`);
    el.classList.remove('active');
    el.classList.add('done');
    document.getElementById(`pm${i}`).textContent = '✓ Done';
  }
  document.querySelector('.progress-spinner').style.display = 'none';
  document.querySelector('.progress-header h3').textContent = 'Analysis Complete';
}

// ─────────────────────────────────────────
// RESULTS
// ─────────────────────────────────────────

function showResults(resume, jobs) {
  progressPanel.style.display = 'none';
  resultsPanel.style.display  = 'block';
  currentResults = { resume, jobs };

  renderSummary(resume, jobs);
  renderResume(resume);
  renderAllJobs(jobs);
  renderCoverLetters(jobs);
  initTabs();

  // Agent confirmation bubble — appears after short delay
  setTimeout(() => renderAgentBubble(resume, jobs), 500);
}

function renderAgentBubble(resume, jobs) {
  const top5    = jobs.slice(0, 5);
  const topJob  = top5[0] || {};
  const name    = resume.name ? resume.name.split(' ')[0] : 'there';
  const total   = jobs.length;

  // Build top 5 mini list
  const miniList = top5.map((j, i) => `
    <div class="agent-job-row">
      <span class="agent-job-num">${i + 1}</span>
      <div class="agent-job-info">
        <span class="agent-job-title">${j.title}</span>
        <span class="agent-job-company">${j.company} · ${j.location}</span>
      </div>
      <span class="agent-match-badge">${j.match_score}%</span>
    </div>
  `).join('');

  const bubble = document.createElement('div');
  bubble.id        = 'agentBubble';
  bubble.className = 'agent-bubble';
  bubble.innerHTML = `
    <div class="agent-avatar">⬡</div>
    <div class="agent-content">
      <p class="agent-name">JobAgent AI</p>
      <p class="agent-msg">
        Hey ${name}! I analyzed <strong>${total} jobs</strong> and found your
        <strong>5 best matches</strong> based on your skills and experience.
        Here's what I recommend:
      </p>
      <div class="agent-job-list" id="agentJobList">
        ${miniList}
      </div>
      <p class="agent-cta-text">Ready to apply? Click below to open each job's application page.</p>
      <div class="agent-actions">
        <button class="agent-apply-btn" onclick="openTop5Apply()">
          🚀 Apply to Top Matches
        </button>
        <button class="agent-dismiss" onclick="dismissBubble()">Maybe later</button>
      </div>
    </div>
  `;

  // Insert before summary bar
  const summaryBar = document.getElementById('summaryBar');
  summaryBar.parentNode.insertBefore(bubble, summaryBar);

  // Animate in
  requestAnimationFrame(() => bubble.classList.add('agent-bubble-visible'));
}

window.openTop5Apply = () => {
  const jobs  = currentResults?.jobs?.slice(0, 5) || [];
  const modal = document.getElementById('top5Modal');

  // Build modal cards
  document.getElementById('top5Cards').innerHTML = jobs.map((job, i) => `
    <div class="t5-card">
      <div class="t5-header">
        <div>
          <p class="t5-title">${job.title}</p>
          <p class="t5-company">${job.company} · ${job.location}</p>
        </div>
        <span class="match-badge ${badgeClass(job.match_score)}">${job.match_score}%</span>
      </div>
      <div class="t5-skills">
        ${(job.strengths || []).map(s => `<span class="skill-chip">${s}</span>`).join('')}
      </div>
      ${job.url
        ? `<a class="apply-btn t5-apply" href="${job.url}" target="_blank" rel="noopener">Apply Now →</a>`
        : `<span style="font-size:0.8rem;color:var(--muted)">No direct link available</span>`
      }
    </div>
  `).join('');

  modal.classList.add('modal-open');
};

window.dismissBubble = () => {
  const b = document.getElementById('agentBubble');
  if (b) { b.classList.remove('agent-bubble-visible'); setTimeout(() => b.remove(), 300); }
};

window.closeTop5Modal = () => {
  document.getElementById('top5Modal').classList.remove('modal-open');
};

function renderSummary(resume, jobs) {
  const emails = jobs.filter(j => j.application_email).length;
  document.getElementById('summaryBar').innerHTML = `
    <div class="summary-card">
      <div class="summary-val">${resume.total_experience_years || 0}</div>
      <div class="summary-lbl">Yrs Experience</div>
    </div>
    <div class="summary-card">
      <div class="summary-val">${(resume.skills || []).length}</div>
      <div class="summary-lbl">Skills Found</div>
    </div>
    <div class="summary-card clickable-card" onclick="scrollToJobs()" title="View matched jobs">
      <div class="summary-val">${jobs.length}</div>
      <div class="summary-lbl">Jobs Matched ↓</div>
    </div>
    <div class="summary-card">
      <div class="summary-val">${emails}</div>
      <div class="summary-lbl">Emails Ready</div>
    </div>
  `;
}

function scrollToJobs() {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-tab="all"]').classList.add('active');
  document.getElementById('tabAll').classList.remove('hidden');
  document.getElementById('tabTop').classList.add('hidden');
  document.getElementById('tabLetters').classList.add('hidden');
  document.querySelectorAll('.section-title')[1]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderResume(r) {
  const allSkills = [...(r.skills || []), ...(r.technical_skills || [])].slice(0, 16);
  const chipsHtml = allSkills.map(s => `<span class="skill-chip">${s}</span>`).join('');
  document.getElementById('resumeCard').innerHTML = `
    <div>
      <p class="rc-label">Name</p>
      <p class="rc-val">${r.name || 'N/A'}</p>
    </div>
    <div>
      <p class="rc-label">Current Role</p>
      <p class="rc-val">${r.current_role || 'N/A'}</p>
    </div>
    <div style="grid-column: 1/-1">
      <p class="rc-label">Summary</p>
      <p class="rc-val" style="font-size:0.88rem;color:var(--muted)">${r.summary || 'N/A'}</p>
    </div>
    <div style="grid-column: 1/-1">
      <p class="rc-label">Skills</p>
      <div class="skills-wrap">${chipsHtml}</div>
    </div>
  `;
}

function badgeClass(score) {
  if (score >= 75) return 'badge-excellent';
  if (score >= 55) return 'badge-good';
  if (score >= 35) return 'badge-moderate';
  return 'badge-low';
}

function jobCardHtml(job, idx) {
  const score     = job.match_score || 0;
  const strengths = (job.strengths || []).map(s => `<li class="green-li">${s}</li>`).join('');
  const gaps      = (job.gaps || []).map(g => `<li class="red-li">${g}</li>`).join('');
  const applyUrl  = job.url && job.url !== 'https://example.com/job1'
    ? `<a class="apply-btn" href="${job.url}" target="_blank" rel="noopener">Apply Now →</a>`
    : `<span style="font-size:0.8rem;color:var(--muted)">No direct link available</span>`;
  const srcBadge = job.source_icon
    ? `<span class="source-badge">${job.source_icon}</span>`
    : '';

  return `
    <div class="job-card" onclick="toggleJobCard(this)">
      <div class="job-card-header">
        <div>
          <p class="job-title-text">${job.title}</p>
          <p class="job-company">${job.company}</p>
        </div>
        <span class="match-badge ${badgeClass(score)}">${score}% Match</span>
      </div>
      <div class="job-meta">
        <span>📍 ${job.location}</span>
        <span>💰 ${job.salary || 'Not specified'}</span>
        <span>🎯 ${job.fit_level || ''}</span>
        ${srcBadge}
      </div>
      <div class="job-detail">
        <div class="detail-grid">
          <div class="detail-col">
            <p>✅ Strengths</p>
            <ul>${strengths || '<li style="color:var(--muted)">—</li>'}</ul>
          </div>
          <div class="detail-col">
            <p>⚠️ Gaps</p>
            <ul>${gaps || '<li style="color:var(--muted)">None identified</li>'}</ul>
          </div>
        </div>
        ${job.recommendation ? `<div class="rec-box">💡 ${job.recommendation}</div>` : ''}
        ${applyUrl}
      </div>
    </div>
  `;
}

function renderAllJobs(jobs) {
  document.getElementById('tabAll').innerHTML = jobs.map((j, i) => jobCardHtml(j, i)).join('');
}

function renderCoverLetters(jobs) {
  const withLetters = jobs.filter(j => j.cover_letter);
  const container   = document.getElementById('tabLetters');

  if (!withLetters.length) {
    container.innerHTML = '<p style="color:var(--muted);padding:1rem">No cover letters generated.</p>';
    return;
  }

  const btnHtml = withLetters.map((j, i) => `
    <button class="letter-tab-btn ${i === 0 ? 'active' : ''}" onclick="selectLetter(this, ${i})">${j.company}</button>
  `).join('');

  container.innerHTML = `
    <div class="letter-selector">${btnHtml}</div>
    <div class="letter-box" id="letterBox">${escHtml(withLetters[0].cover_letter)}</div>
    <button class="download-btn" onclick="downloadLetter(0)">⬇ Download Cover Letter</button>
  `;

  container._jobs = withLetters;
}

window.selectLetter = (btn, idx) => {
  const container = document.getElementById('tabLetters');
  container.querySelectorAll('.letter-tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('letterBox').textContent = container._jobs[idx].cover_letter;
  container.querySelector('.download-btn').onclick = () => downloadLetter(idx);
};

window.downloadLetter = (idx) => {
  const container = document.getElementById('tabLetters');
  const job = container._jobs[idx];
  const blob = new Blob([job.cover_letter], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `cover_letter_${job.company.replace(/\s+/g, '_')}.txt`;
  a.click();
};

window.toggleJobCard = (card) => {
  card.classList.toggle('expanded');
};

// ─────────────────────────────────────────
// TABS
// ─────────────────────────────────────────

function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.getElementById('tabAll').classList.toggle('hidden',     tab !== 'all');
      document.getElementById('tabLetters').classList.toggle('hidden', tab !== 'letters');
    });
  });
}

// ─────────────────────────────────────────
// RESET
// ─────────────────────────────────────────

resetBtn.addEventListener('click', () => {
  resultsPanel.style.display  = 'none';
  progressPanel.style.display = 'none';
  formPanel.style.display     = 'block';
  form.reset();
  uploadInner.style.display   = 'flex';
  uploadSelected.style.display= 'none';

  // Reset progress steps
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`ps${i}`);
    el.classList.remove('active', 'done');
    document.getElementById(`pm${i}`).textContent = 'Waiting...';
  }
  document.querySelector('.progress-spinner').style.display = 'block';
  document.querySelector('.progress-header h3').textContent = 'Agent Running';

  resetSubmitBtn();
});

// ─────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────

function showFormError(msg) {
  const existing = formPanel.querySelector('.error-panel');
  if (existing) existing.remove();
  const div = document.createElement('div');
  div.className = 'error-panel';
  div.textContent = msg;
  form.prepend(div);
  setTimeout(() => div.remove(), 5000);
}

function resetSubmitBtn() {
  submitBtn.disabled = false;
  submitBtn.querySelector('.btn-text').textContent = 'Run Agent';
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ─────────────────────────────────────────
   AUTOCOMPLETE — Job Title & Location
───────────────────────────────────────── */

let debounceTimer = null;

function setupAutocomplete(inputId, suggestId, field) {
  const input   = document.getElementById(inputId);
  const box     = document.getElementById(suggestId);
  let   selIdx  = -1;
  let   items   = [];

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) { closeBox(); return; }

    // Show loading
    box.innerHTML = '<div class="suggest-loading">Fetching suggestions...</div>';
    box.classList.add('open');

    debounceTimer = setTimeout(async () => {
      try {
        const res  = await fetch('/suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field, query: q })
        });
        const data = await res.json();
        items  = data.suggestions || [];
        selIdx = -1;
        renderSuggestions(items, box, input);
      } catch {
        closeBox();
      }
    }, 400); // 400ms debounce — so Groq call doesn't fire on every keystroke
  });

  input.addEventListener('keydown', e => {
    if (!box.classList.contains('open')) return;
    if (e.key === 'ArrowDown') { selIdx = Math.min(selIdx + 1, items.length - 1); highlight(box, selIdx); e.preventDefault(); }
    if (e.key === 'ArrowUp')   { selIdx = Math.max(selIdx - 1, 0); highlight(box, selIdx); e.preventDefault(); }
    if (e.key === 'Enter' && selIdx >= 0) { input.value = items[selIdx]; closeBox(); e.preventDefault(); }
    if (e.key === 'Escape') closeBox();
  });

  document.addEventListener('click', e => {
    if (!box.contains(e.target) && e.target !== input) closeBox();
  });

  function closeBox() { box.classList.remove('open'); box.innerHTML = ''; selIdx = -1; }

  function renderSuggestions(list, box, input) {
    if (!list.length) { closeBox(); return; }
    box.innerHTML = list.map((s, i) =>
      `<div class="suggest-item" data-idx="${i}">${s}</div>`
    ).join('');
    box.classList.add('open');
    box.querySelectorAll('.suggest-item').forEach(el => {
      el.addEventListener('mousedown', e => {
        e.preventDefault();
        input.value = el.textContent;
        closeBox();
      });
    });
  }

  function highlight(box, idx) {
    box.querySelectorAll('.suggest-item').forEach((el, i) => {
      el.classList.toggle('selected', i === idx);
    });
  }
}

// Init both fields
setupAutocomplete('jobTitle', 'jobSuggest', 'job_title');
setupAutocomplete('location', 'locSuggest', 'location');


/* ─────────────────────────────────────────
   EMAIL RENDERING — replaces cover letters
───────────────────────────────────────── */

// Override the cover letters tab render
function renderCoverLetters(jobs) {
  const withEmails = jobs.filter(j => j.application_email);
  const container  = document.getElementById('tabLetters');

  if (!withEmails.length) {
    container.innerHTML = '<p style="color:var(--muted);padding:1rem">No emails generated.</p>';
    return;
  }

  container.innerHTML = withEmails.map((job, i) => {
    const lines   = job.application_email.split('\n');
    const subjLine = lines.find(l => l.toLowerCase().startsWith('subject:')) || '';
    const subject  = subjLine.replace(/^subject:\s*/i, '');
    const body     = lines.filter(l => !l.toLowerCase().startsWith('subject:')).join('\n').trim();

    return `
      <div class="email-card" style="animation-delay:${i * 0.06}s">
        <div class="email-header">
          <div class="email-job-info">
            <span class="email-job-title">${job.title}</span>
            <span class="email-company">${job.company} · ${job.location}</span>
          </div>
          <span class="email-score-badge">${job.match_score}% match</span>
        </div>
        ${subject ? `<div class="email-subject">📧 Subject: ${subject}</div>` : ''}
        <div class="email-body" id="emailBody_${i}">${escHtml(body)}</div>
        <div class="email-actions">
          <button class="email-copy-btn" onclick="copyEmail(${i}, this)">Copy</button>
          <button class="email-copy-btn" id="editBtn_${i}" onclick="toggleEdit(${i})">✏️ Edit</button>
          <button class="download-btn" onclick="downloadEmail(${i}, '${job.company.replace(/'/g,"\\'")}')">Download</button>
        </div>
      </div>
    `;
  }).join('');

  container._jobs = withEmails;

  // Back to search button at bottom
  const backDiv = document.createElement('div');
  backDiv.className = 'email-back-home';
  backDiv.innerHTML = `
    <button class="email-back-home-btn" onclick="scrollToTop()">
      ← Back to Job Search
    </button>
  `;
  container.appendChild(backDiv);
}

window.copyEmail = (idx, btn) => {
  const container = document.getElementById('tabLetters');
  const text = container._jobs[idx].application_email;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy Email'; btn.classList.remove('copied'); }, 2000);
  });
};

window.downloadEmail = (idx, company) => {
  const container = document.getElementById('tabLetters');
  const text = container._jobs[idx].application_email;
  const blob = new Blob([text], { type: 'text/plain' });
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = `email_${company.replace(/\s+/g,'_')}.txt`;
  a.click();
};

/* ─────────────────────────────────────────
   EMAIL EDIT FEATURE
───────────────────────────────────────── */

window.toggleEdit = (idx) => {
  const body    = document.getElementById(`emailBody_${idx}`);
  const editBtn = document.getElementById(`editBtn_${idx}`);
  const isEditing = body.contentEditable === "true";

  if (isEditing) {
    // Save mode
    body.contentEditable = "false";
    body.style.outline   = "none";
    body.style.background = "";
    editBtn.textContent  = "✏️ Edit";
    editBtn.classList.remove("editing");

    // Sync edited content back to _jobs
    const container = document.getElementById('tabLetters');
    container._jobs[idx].application_email = body.innerText;
  } else {
    // Edit mode
    body.contentEditable = "true";
    body.style.outline   = "1px solid rgba(99,211,255,0.4)";
    body.style.background = "rgba(99,211,255,0.03)";
    body.focus();
    editBtn.textContent  = "💾 Save";
    editBtn.classList.add("editing");
  }
};

/* ─────────────────────────────────────────
   LOGO 3D ANIMATION
───────────────────────────────────────── */
window.animateLogo = () => {
  const btn = document.getElementById('aiLogoBtn');
  btn.classList.remove('spinning');
  void btn.offsetWidth; // reflow to restart
  btn.classList.add('spinning');
  setTimeout(() => btn.classList.remove('spinning'), 800);
};

/* ─────────────────────────────────────────
   BACK TO EMAILS BUTTON
───────────────────────────────────────── */
window.switchToEmails = () => {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-tab="letters"]').classList.add('active');
  document.getElementById('tabAll').classList.add('hidden');
  document.getElementById('tabLetters').classList.remove('hidden');
  document.getElementById('backToEmailsBtn').style.display = 'none';
  document.getElementById('tabLetters').scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// Show back button when on All Jobs tab, hide on Emails tab
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.tab-btn');
  if (!btn) return;
  const backBtn = document.getElementById('backToEmailsBtn');
  if (!backBtn) return;
  backBtn.style.display = btn.dataset.tab === 'all' ? 'block' : 'none';
});

/* ── SCROLL TO TOP (Back to Search) ── */
window.scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

/* ── TOGGLE HELPER ── */
window.setToggle = (groupId, btn, hiddenId) => {
  document.querySelectorAll(`#${groupId} .toggle-btn`).forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(hiddenId).value = btn.dataset.value;
};