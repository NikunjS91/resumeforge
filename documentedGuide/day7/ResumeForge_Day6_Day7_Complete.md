# ResumeForge — Days 6 & 7 Complete Build Guide
## PDF Exporter Fix + React Frontend

---

> **Agent Instructions:** Work through ALL sections in order.
> Read every listed file before writing any code.
> Do not skip any step.
> This guide covers everything remaining to complete ResumeForge.

---

## Current System State

| Service | Status |
|---------|--------|
| Backend | Port 8000 — start manually: `cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000` |
| Ollama | Port 11434, model: `qwen3:14b` |
| NVIDIA NIM | `NVIDIA_API_KEY` in `backend/.env` |
| Git | On `dev` branch |

---

## PART 1 — Day 6 Fix: PDF Exporter

### Problem Summary (from visual inspection)

The `tailored_resume.pdf` has 4 bugs:

| # | Bug | Root Cause |
|---|-----|-----------|
| 1 | Skills section appears 3× | `Technologies:` lines in projects still creating extra `skills` sections in the DB |
| 2 | Contact info appears mid-page | Contact section rendered in body AND in header |
| 3 | AI Improvement Summary leaking into body | Notes loaded from wrong source |
| 4 | Technology tags duplicated | Same as bug 1 — duplicate sections rendered |

The `original_resume.pdf` is clean — the bugs only affect the tailored PDF.

---

### Before Writing Any Code — Read These Files

```
backend/modules/export/pdf_builder.py
backend/modules/export/__init__.py
backend/routers/export.py
backend/modules/parse/section_detector.py
backend/models/tailoring_session.py
```

---

### Fix 1 — Section Deduplication in pdf_builder.py

**File:** `backend/modules/export/pdf_builder.py`

In `build_pdf()`, after sorting sections by `position_index`, add this block
BEFORE the contact extraction and BEFORE any rendering:

```python
# ── Deduplicate sections ─────────────────────────────────────────────────
# Keep only the FIRST occurrence of each section_type.
# Exception: allow multiple experience and projects entries.
ALLOW_MULTIPLE = {"experience", "projects"}
seen_types = set()
deduped = []
for s in sorted_sections:
    sec_type = s.get("section_type", "other")
    if sec_type in ALLOW_MULTIPLE:
        deduped.append(s)
    elif sec_type not in seen_types:
        seen_types.add(sec_type)
        deduped.append(s)
    # else: duplicate — skip silently
sorted_sections = deduped
```

---

### Fix 2 — Contact Section Only in Header

**File:** `backend/modules/export/pdf_builder.py`

In `build_pdf()`, find `SKIP_TYPES` and confirm it reads:

```python
SKIP_TYPES = {"contact"}
```

If it's missing `"contact"` or is empty, add it. The contact section must
ONLY appear in the header bar — never rendered as a body section.

---

### Fix 3 — Improvement Notes from Correct Source

**File:** `backend/routers/export.py`

When loading from a tailoring session, improvement_notes must come from the
DB column `tailoring_sessions.improvement_notes_json`, NOT from `tailored_json`.

Find the session loading block and update it:

```python
# Load improvement notes from dedicated DB column (not from tailored_json)
try:
    improvement_notes = json.loads(session.improvement_notes_json or "[]")
except Exception:
    improvement_notes = []
```

Also make sure `sections_data` only uses `tailored_text` for content,
never accidentally including notes or metadata:

```python
sections_data = [
    {
        "section_type":   s.get("section_type"),
        "section_label":  s.get("section_label", ""),
        "content_text":   s.get("tailored_text", s.get("content_text", "")),
        "position_index": s.get("position_index", 0),
    }
    for s in tailored_data.get("sections", [])
    if s.get("tailored_text", s.get("content_text", "")).strip()
]
```

---

### Fix 4 — Final Skills Bleeding Fix in Section Detector

**File:** `backend/modules/parse/section_detector.py`

Find the section splitting loop. Inside it, add a guard that prevents
`Technologies:`, `Tech Stack:`, `Stack:`, `Tools:`, `Frameworks:`, `Languages:`
from being treated as new section headings when inside a `projects` block.

```python
INLINE_CONTENT_PREFIXES = {
    "technologies:", "tech stack:", "stack:", "tools:",
    "frameworks:", "languages:", "built with:", "tech:",
}

# In the loop, before creating a new section:
if current_section_type == "projects":
    candidate_lower = candidate_heading.lower().strip().rstrip(":")
    if any(candidate_lower.startswith(p.rstrip(":")) for p in INLINE_CONTENT_PREFIXES):
        current_block_lines.append(line)
        continue  # treat as content, NOT a new section
```

---

### Verify All 4 Fixes

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Check 1 — section bleeding fixed
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
types = [s['section_type'] for s in d['sections']]
print(f'section_count: {d[\"section_count\"]} (target: 6)')
print(f'skills_count:  {types.count(\"skills\")} (target: 1)')
print(f'unknown_count: {sum(1 for t in types if t==\"unknown\")} (target: 0)')
print('PASS' if d['section_count'] == 6 and types.count('skills') == 1 else 'FAIL')
"

# Get latest session ID
SESSION_ID=$(python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
row = conn.execute('SELECT id FROM tailoring_sessions WHERE user_id=3 AND tailored_text != \"\" ORDER BY id DESC LIMIT 1').fetchone()
print(row[0])
conn.close()
")

# Check 2 — export original
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2}' \
  -o /tmp/original_v3.pdf
echo "Original PDF: $(ls -lh /tmp/original_v3.pdf | awk '{print $5}')"

# Check 3 — export tailored
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": $SESSION_ID}" \
  -o /tmp/tailored_v3.pdf
echo "Tailored PDF: $(ls -lh /tmp/tailored_v3.pdf | awk '{print $5}')"

# Open both to visually verify
open /tmp/original_v3.pdf
open /tmp/tailored_v3.pdf
```

**Expected:**
- original_v3.pdf — clean professional resume
- tailored_v3.pdf — same structure, no duplicates, improvement notes only at bottom

---

### Day 6 Git Commit

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add backend/modules/export/pdf_builder.py
git add backend/routers/export.py
git add backend/modules/parse/section_detector.py
git commit -m "fix: Day 6 PDF exporter — deduplicate sections, fix contact/notes/bleeding

- Deduplicate sections in build_pdf() — keeps first occurrence per type
- Contact section only in header, never in body
- Improvement notes loaded from DB column not from tailored_json
- Final fix for Technologies: lines splitting skills sections"

git push origin feature/day6-pdf-exporter
git checkout dev
git merge feature/day6-pdf-exporter
git push origin dev
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

## PART 2 — Day 7: React Frontend

### Stack

- React + Vite + TailwindCSS
- Runs on port 5173
- Talks to backend on port 8000
- JWT stored in localStorage
- No additional packages beyond what Vite scaffolds + axios + react-router-dom

---

### Setup

```bash
cd /Users/nikunjshetye/Documents/resume-forger
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install axios react-router-dom
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

Configure `tailwind.config.js`:
```js
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

Add to `src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

Configure Vite proxy in `vite.config.js` so `/api` calls go to backend:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    }
  }
})
```

---

### File Structure

```
frontend/src/
  api/          axios.js          — axios instance with auth header
  pages/        Login.jsx         — login page
                Dashboard.jsx     — main pipeline page
  components/   ResumeUpload.jsx  — upload + parse
                JobInput.jsx      — paste JD + analyze
                TailorPanel.jsx   — tailor with provider selector
                ATSScore.jsx      — score display
                ExportButton.jsx  — download PDF
  App.jsx       — router
  main.jsx      — entry point
```

---

### api/axios.js

```jsx
import axios from 'axios'

const api = axios.create({ baseURL: '/' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api
```

---

### pages/Login.jsx

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      const res = await axios.post('/auth/login',
        new URLSearchParams({ username: email, password }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }}
      )
      localStorage.setItem('token', res.data.access_token)
      navigate('/dashboard')
    } catch {
      setError('Invalid credentials')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md">
        <h1 className="text-3xl font-bold text-center text-indigo-700 mb-2">ResumeForge</h1>
        <p className="text-center text-gray-500 mb-6">AI-powered resume tailoring</p>
        {error && <p className="text-red-500 text-sm mb-4 text-center">{error}</p>}
        <form onSubmit={handleLogin} className="space-y-4">
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <input type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <button type="submit"
            className="w-full bg-indigo-600 text-white py-2 rounded-lg font-semibold hover:bg-indigo-700 transition">
            Sign In
          </button>
        </form>
      </div>
    </div>
  )
}
```

---

### pages/Dashboard.jsx

This is the main pipeline page. It walks the user through 5 steps in order:

```
Step 1 → Upload Resume
Step 2 → Analyze Job Description
Step 3 → Tailor Resume (choose provider)
Step 4 → ATS Score
Step 5 → Download PDF
```

Each step unlocks after the previous completes.

```jsx
import { useState } from 'react'
import ResumeUpload from '../components/ResumeUpload'
import JobInput from '../components/JobInput'
import TailorPanel from '../components/TailorPanel'
import ATSScore from '../components/ATSScore'
import ExportButton from '../components/ExportButton'

export default function Dashboard() {
  const [resumeId, setResumeId]     = useState(null)
  const [jobId, setJobId]           = useState(null)
  const [sessionId, setSessionId]   = useState(null)
  const [atsScore, setAtsScore]     = useState(null)

  const steps = [
    { num: 1, label: 'Upload Resume',   done: !!resumeId },
    { num: 2, label: 'Analyze JD',      done: !!jobId },
    { num: 3, label: 'Tailor Resume',   done: !!sessionId },
    { num: 4, label: 'ATS Score',       done: atsScore !== null },
    { num: 5, label: 'Download PDF',    done: false },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <nav className="bg-indigo-700 text-white px-8 py-4 flex items-center justify-between shadow">
        <h1 className="text-xl font-bold tracking-wide">⚡ ResumeForge</h1>
        <button onClick={() => { localStorage.removeItem('token'); window.location.href = '/' }}
          className="text-sm opacity-80 hover:opacity-100">Sign out</button>
      </nav>

      {/* Progress Steps */}
      <div className="max-w-4xl mx-auto mt-8 px-4">
        <div className="flex items-center justify-between mb-8">
          {steps.map((s, i) => (
            <div key={s.num} className="flex items-center">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold
                ${s.done ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-600'}`}>
                {s.done ? '✓' : s.num}
              </div>
              <span className="ml-2 text-sm text-gray-600 hidden sm:block">{s.label}</span>
              {i < steps.length - 1 && <div className="w-8 h-px bg-gray-300 mx-3" />}
            </div>
          ))}
        </div>

        {/* Pipeline Steps */}
        <div className="space-y-6">
          <ResumeUpload onUpload={setResumeId} />

          {resumeId && (
            <JobInput onAnalyze={setJobId} />
          )}

          {resumeId && jobId && (
            <TailorPanel resumeId={resumeId} jobId={jobId} onTailored={setSessionId} />
          )}

          {sessionId && (
            <ATSScore resumeId={resumeId} jobId={jobId} sessionId={sessionId} onScored={setAtsScore} />
          )}

          {sessionId && (
            <ExportButton resumeId={resumeId} sessionId={sessionId} />
          )}
        </div>
      </div>
    </div>
  )
}
```

---

### components/ResumeUpload.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'

export default function ResumeUpload({ onUpload }) {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/parse/upload', form)
      setResult(res.data)
      onUpload(res.data.resume_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">📄 Step 1 — Upload Resume</h2>
      {!result ? (
        <div className="space-y-3">
          <input type="file" accept=".pdf,.docx"
            onChange={e => setFile(e.target.files[0])}
            className="block w-full text-sm text-gray-600 border rounded-lg p-2" />
          <button onClick={handleUpload} disabled={!file || loading}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
            {loading ? 'Parsing...' : 'Upload & Parse'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✅ {result.resume_name} parsed successfully</p>
          <p className="text-sm text-gray-600 mt-1">
            {result.section_count} sections · {result.char_count.toLocaleString()} characters
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            {result.sections?.map(s => (
              <span key={s.position_index}
                className="bg-indigo-100 text-indigo-700 text-xs px-2 py-1 rounded-full">
                {s.section_label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

---

### components/JobInput.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'

export default function JobInput({ onAnalyze }) {
  const [jdText, setJdText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleAnalyze = async () => {
    if (!jdText.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/analyze/job', { jd_text: jdText })
      setResult(res.data)
      onAnalyze(res.data.job_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">🔍 Step 2 — Analyze Job Description</h2>
      {!result ? (
        <div className="space-y-3">
          <textarea rows={6} value={jdText}
            onChange={e => setJdText(e.target.value)}
            placeholder="Paste the full job description here..."
            className="w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none" />
          <button onClick={handleAnalyze} disabled={!jdText.trim() || loading}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
            {loading ? 'Analyzing...' : 'Analyze JD'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✅ {result.job_title} at {result.company_name}</p>
          <p className="text-sm text-gray-600 mt-1">
            {result.required_count} required skills · {result.nicetohave_count} nice-to-have
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            {result.required_skills?.slice(0, 10).map(s => (
              <span key={s} className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

---

### components/TailorPanel.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'

export default function TailorPanel({ resumeId, jobId, onTailored }) {
  const [provider, setProvider] = useState('ollama')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleTailor = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/tailor/resume', { resume_id: resumeId, job_id: jobId, provider })
      setResult(res.data)
      onTailored(res.data.session_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Tailoring failed')
    } finally {
      setLoading(false)
    }
  }

  const providerInfo = {
    ollama: { label: 'Local (Ollama)', desc: 'qwen3:14b · ~2-3 min · 100% private', color: 'green' },
    nvidia: { label: 'NVIDIA NIM', desc: 'llama-3.3-70b · ~15-20s · cloud', color: 'blue' },
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">✂️ Step 3 — Tailor Resume</h2>
      {!result ? (
        <div className="space-y-4">
          {/* Provider selector */}
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(providerInfo).map(([key, info]) => (
              <button key={key} onClick={() => setProvider(key)}
                className={`border-2 rounded-lg p-3 text-left transition
                  ${provider === key
                    ? `border-${info.color}-500 bg-${info.color}-50`
                    : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="font-medium text-sm text-gray-800">{info.label}</p>
                <p className="text-xs text-gray-500 mt-1">{info.desc}</p>
              </button>
            ))}
          </div>
          {provider === 'ollama' && (
            <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
              ⏱ Local mode takes 2-3 minutes. Keep this window open.
            </p>
          )}
          <button onClick={handleTailor} disabled={loading}
            className="w-full bg-indigo-600 text-white py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
            {loading
              ? `Tailoring with ${providerInfo[provider].label}...`
              : `Tailor with ${providerInfo[provider].label}`}
          </button>
          {loading && provider === 'ollama' && (
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div className="bg-indigo-600 h-1.5 rounded-full animate-pulse w-1/3" />
            </div>
          )}
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✅ Resume tailored with {result.ai_model}</p>
          <p className="text-sm text-gray-600 mt-1">{result.sections_tailored} sections improved</p>
          <ul className="mt-2 space-y-1">
            {result.improvement_notes?.slice(0, 3).map((note, i) => (
              <li key={i} className="text-xs text-gray-600">• {note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

---

### components/ATSScore.jsx

```jsx
import { useState, useEffect } from 'react'
import api from '../api/axios'

export default function ATSScore({ resumeId, jobId, sessionId, onScored }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (sessionId) scoreIt()
  }, [sessionId])

  const scoreIt = async () => {
    setLoading(true)
    try {
      const res = await api.post('/api/score/ats', {
        resume_id: resumeId,
        job_id: jobId,
        session_id: sessionId
      })
      setResult(res.data)
      onScored(res.data.ats_score)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const scoreColor = (score) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const scoreRing = (score) => {
    if (score >= 80) return 'border-green-500'
    if (score >= 60) return 'border-yellow-500'
    return 'border-red-500'
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">📊 Step 4 — ATS Score</h2>
      {loading && <p className="text-gray-500 text-sm">Scoring your resume...</p>}
      {result && (
        <div className="flex gap-6 items-start">
          {/* Score circle */}
          <div className={`flex-shrink-0 w-24 h-24 rounded-full border-4 ${scoreRing(result.ats_score)}
            flex items-center justify-center`}>
            <span className={`text-3xl font-bold ${scoreColor(result.ats_score)}`}>
              {result.ats_score}
            </span>
          </div>
          {/* Details */}
          <div className="flex-1">
            <p className="text-sm text-gray-600 mb-2">{result.recommendation}</p>
            <div className="flex gap-4 text-sm">
              <div>
                <p className="font-medium text-green-700 mb-1">✅ Matched ({result.matched_count})</p>
                <div className="flex flex-wrap gap-1">
                  {result.matched_keywords?.map(k => (
                    <span key={k} className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                  ))}
                </div>
              </div>
              {result.missing_keywords?.length > 0 && (
                <div>
                  <p className="font-medium text-red-700 mb-1">❌ Missing ({result.missing_keywords.length})</p>
                  <div className="flex flex-wrap gap-1">
                    {result.missing_keywords?.map(k => (
                      <span key={k} className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

---

### components/ExportButton.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'

export default function ExportButton({ resumeId, sessionId }) {
  const [loading, setLoading] = useState(null) // 'original' | 'tailored' | null

  const download = async (type) => {
    setLoading(type)
    try {
      const body = type === 'tailored' ? { session_id: sessionId } : { resume_id: resumeId }
      const res = await api.post('/api/export/pdf', body, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = type === 'tailored' ? 'tailored_resume.pdf' : 'original_resume.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">📥 Step 5 — Download PDF</h2>
      <div className="flex gap-3">
        <button onClick={() => download('tailored')} disabled={loading === 'tailored'}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
          {loading === 'tailored' ? 'Generating...' : '⬇ Download Tailored Resume'}
        </button>
        <button onClick={() => download('original')} disabled={loading === 'original'}
          className="flex-1 border-2 border-gray-300 text-gray-700 py-3 rounded-lg font-medium hover:border-indigo-400 disabled:opacity-50 transition">
          {loading === 'original' ? 'Generating...' : '⬇ Download Original'}
        </button>
      </div>
    </div>
  )
}
```

---

### App.jsx

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

const PrivateRoute = ({ children }) => {
  return localStorage.getItem('token') ? children : <Navigate to="/" />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
```

---

### Start the Frontend

```bash
cd /Users/nikunjshetye/Documents/resume-forger/frontend
npm run dev
# Opens at http://localhost:5173
```

---

### Day 7 Verification Checks

```bash
# Check 1 — Frontend builds without errors
cd /Users/nikunjshetye/Documents/resume-forger/frontend
npm run build
# Expected: no errors, dist/ folder created

# Check 2 — Dev server starts
npm run dev
# Expected: server running on http://localhost:5173

# Check 3 — Manual flow test
# Open http://localhost:5173
# Login with nikunj@resumeforge.com / securepass123
# Upload Resume_10March.pdf → should show 6 sections
# Paste any cloud engineer JD → should extract skills
# Tailor with Ollama OR NVIDIA → should show improvement notes
# ATS Score → should show 80+ score
# Download tailored PDF → should be professional and clean

# Check 4 — All backend routes still work
for route in /health /api/parse/status /api/analyze/status /api/tailor/status /api/score/status /api/export/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
```

---

### Day 7 Git Commit

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add frontend/
git commit -m "feat: Day 7 — React frontend with full pipeline UI

- Login page with JWT auth
- Dashboard with 5-step pipeline progress tracker
- ResumeUpload: drag & drop PDF/DOCX, shows parsed sections
- JobInput: paste JD, shows extracted skills
- TailorPanel: choose Ollama (local) or NVIDIA NIM (fast)
- ATSScore: 0-100 score with matched/missing keyword badges
- ExportButton: download tailored or original PDF
- Vite proxy configured for backend API"

git push origin feature/day7-frontend
git checkout dev
git merge feature/day7-frontend
git push origin dev
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

## Final Project State After Day 7

### Complete API Surface

| Route | Method | Day | Description |
|-------|--------|-----|-------------|
| `/auth/signup` | POST | 1 | Create account |
| `/auth/login` | POST | 1 | Get JWT token |
| `/auth/me` | GET | 1 | Current user |
| `/api/parse/upload` | POST | 2 | Upload + parse resume |
| `/api/analyze/job` | POST | 3 | Analyze job description |
| `/api/tailor/resume` | POST | 4 | Tailor resume (ollama/nvidia) |
| `/api/score/ats` | POST | 5 | ATS keyword score |
| `/api/export/pdf` | POST | 6 | Export professional PDF |

### Complete User Flow

```
http://localhost:5173
       ↓
   Login Page
       ↓
   Dashboard
       ↓
1. Upload Resume PDF
       ↓
2. Paste Job Description
       ↓
3. Tailor (Ollama or NVIDIA)
       ↓
4. ATS Score (instant)
       ↓
5. Download Tailored PDF
```

### Git Branch Strategy (final)

```
main ← stable, all days merged
dev  ← integration branch
feature/day6-pdf-exporter ← merged
feature/day7-frontend     ← merged
feature/nvidia-nim-provider ← merged
feature/day5-ats-scorer   ← merged
feature/day4-resume-tailor ← merged
```

---

> ✅ **ResumeForge is complete when:**
> - PDF exports are clean (no duplicates, professional layout)
> - Frontend runs at http://localhost:5173
> - Full pipeline works end-to-end in the browser
> - All code merged to main
