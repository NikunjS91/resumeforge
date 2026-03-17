# ResumeForge — Pre-Day 5 Comprehensive System Check

---

> **Agent Instructions:** This is a READ-ONLY audit. Do NOT modify any code unless a check explicitly
> says "fix if broken". Your job is to inspect, test, and report. Run every check in order.
> Report PASS or FAIL for each with exact output. At the end produce a summary table.

---

## Section 1 — Infrastructure & Services

### Check 1.1 — Backend server running
```bash
curl -s http://localhost:8000/health
```
**Expected:** `{"status":"healthy"}`

---

### Check 1.2 — Ollama running with correct model
```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool
```
**Expected:** `qwen3:14b` listed. `llama3.2` and `mistral:7b` should NOT be present (deleted).

---

### Check 1.3 — launchd services registered
```bash
launchctl list | grep -E "resumeforge|ollama"
```
**Expected:** Two entries — `com.resumeforge.backend` and `com.ollama.serve`

---

### Check 1.4 — Log files exist and are being written
```bash
ls -la /tmp/resumeforge.log /tmp/resumeforge.error.log /tmp/ollama.log
tail -5 /tmp/resumeforge.log
```
**Expected:** Files exist, log has recent entries.

---

### Check 1.5 — Python dependencies complete
```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
pip list | grep -E "fastapi|uvicorn|sqlalchemy|pdfplumber|python-docx|pydantic|requests|bcrypt|python-jose"
```
**Expected:** All packages listed with version numbers.

---

## Section 2 — Database Integrity

### Check 2.1 — All 6 tables exist with correct structure
```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
tables = ['users', 'resumes', 'resume_sections', 'jobs', 'tailoring_sessions', 'ai_provider_config']
for t in tables:
    cols = [c[1] for c in conn.execute(f'PRAGMA table_info({t})').fetchall()]
    count = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t:25} | rows={count:3} | cols={len(cols):2} | {cols}')
conn.close()
"
```
**Expected:** All 6 tables present. `ai_provider_config` has 4 rows (ollama/claude/openai/gemini).

---

### Check 2.2 — AI provider config seeded correctly
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute('SELECT provider_name, is_enabled, default_model, priority_order FROM ai_provider_config ORDER BY priority_order').fetchall()
for r in rows: print(r)
conn.close()
"
```
**Expected:** 4 rows — ollama(1), claude(2), openai(3), gemini(4).

---

### Check 2.3 — User data integrity
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
users = conn.execute('SELECT id, email, is_active FROM users').fetchall()
print('Users:', users)
resumes = conn.execute('SELECT id, user_id, name, file_format, char_count, page_count FROM resumes').fetchall()
print('Resumes:')
for r in resumes: print(' ', r)
jobs = conn.execute('SELECT id, user_id, company_name, job_title, seniority_level FROM jobs WHERE company_name IS NOT NULL').fetchall()
print('Jobs (with company):')
for j in jobs: print(' ', j)
sessions = conn.execute('SELECT id, user_id, resume_id, job_id, ai_model FROM tailoring_sessions').fetchall()
print('Tailoring sessions:')
for s in sessions: print(' ', s)
conn.close()
"
```
**Expected:** At least 1 user (nikunj@resumeforge.com), resumes with char_count > 0, jobs with company names, tailoring sessions with ai_model=qwen3:14b.

---

## Section 3 — API Routes — All Days

### Get a token first:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token obtained: ${TOKEN:0:20}..."
```

---

### Check 3.1 — Day 1: Auth routes
```bash
# Signup with new user
curl -s -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"systemcheck@test.com","password":"check123","full_name":"System Check"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'signup: id={d.get(\"id\")}, email={d.get(\"email\")}')"

# Login
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'login: token_type={d.get(\"token_type\")}, has_token={bool(d.get(\"access_token\"))}')"

# Auth/me
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'auth/me: id={d.get(\"id\")}, email={d.get(\"email\")}, active={d.get(\"is_active\")}')"
```
**Expected:** signup returns user object, login returns bearer token, auth/me returns nikunj's data.

---

### Check 3.2 — Day 2: Resume Parser
```bash
# Status
curl -s http://localhost:8000/api/parse/status
# Expected: {"status": "not implemented yet", "module": "resume_parser"}

# No auth → 401
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/parse/upload)
echo "No auth status: $STATUS (expected 401)"

# Wrong file type → 422
echo "test" > /tmp/test_check.txt
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_check.txt" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'wrong type: {d.get(\"detail\")}')"

# Upload real resume
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'upload: resume_id={d.get(\"resume_id\")}, section_count={d.get(\"section_count\")}, char_count={d.get(\"char_count\")}')
sections = d.get('sections', [])
types = [s['section_type'] for s in sections]
unknown = [s for s in sections if s['section_type'] == 'unknown']
print(f'section_types: {types}')
print(f'unknown_count: {len(unknown)} (should be 0)')
print(f'skills_count: {types.count(\"skills\")} (should be 1)')
"
```
**Expected:** Status 200, upload returns 6 sections, 0 unknown, 1 skills section.

---

### Check 3.3 — Day 3: Job Description Analyzer
```bash
# Status
curl -s http://localhost:8000/api/analyze/status

# Analyze a real JD
curl -s -X POST http://localhost:8000/api/analyze/job \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "Senior Cloud Engineer at TechCorp, Austin TX. Requirements: AWS EC2 ECS Lambda S3, Python, Docker, Kubernetes, Terraform, CI/CD GitHub Actions. Nice to have: Prometheus, Grafana, Redis. Salary: $140,000 - $170,000. On-site role."}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'job_id:        {d.get(\"job_id\")}')
print(f'company:       {d.get(\"company_name\")}')
print(f'title:         {d.get(\"job_title\")}')
print(f'seniority:     {d.get(\"seniority_level\")}')
print(f'is_remote:     {d.get(\"is_remote\")} (should be False)')
print(f'salary:        {d.get(\"salary_range\")}')
print(f'required:      {d.get(\"required_count\")} skills — {d.get(\"required_skills\")}')
print(f'nice_to_have:  {d.get(\"nicetohave_count\")} skills')
passed = d.get('company_name') and d.get('job_title') and d.get('required_count', 0) > 0 and not d.get('is_remote')
print(f'PASS' if passed else 'FAIL')
"
```
**Expected:** company/title/skills extracted, is_remote=False, required_count > 5.

---

### Check 3.4 — Day 4: Resume Tailor
```bash
# Get latest resume_id and job_id for nikunj
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
resume = conn.execute('SELECT id, name FROM resumes WHERE user_id=3 ORDER BY id DESC LIMIT 1').fetchone()
job = conn.execute('SELECT id, company_name, job_title FROM jobs WHERE user_id=3 AND company_name IS NOT NULL ORDER BY id DESC LIMIT 1').fetchone()
print(f'Latest resume: id={resume[0]}, name={resume[1]}')
print(f'Latest job:    id={job[0]}, company={job[1]}, title={job[2]}')
conn.close()
"

# Use those IDs — replace RESUME_ID and JOB_ID with actual values
RESUME_ID=$(python3 -c "import sqlite3; conn=sqlite3.connect('data/resumeforge.db'); print(conn.execute('SELECT id FROM resumes WHERE user_id=3 ORDER BY id DESC LIMIT 1').fetchone()[0])")
JOB_ID=$(python3 -c "import sqlite3; conn=sqlite3.connect('data/resumeforge.db'); print(conn.execute('SELECT id FROM jobs WHERE user_id=3 AND company_name IS NOT NULL ORDER BY id DESC LIMIT 1').fetchone()[0])")

echo "Using resume_id=$RESUME_ID, job_id=$JOB_ID"

# Time the tailor call — should complete in < 5 minutes
time curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resume_id\": $RESUME_ID, \"job_id\": $JOB_ID}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'session_id:        {d.get(\"session_id\")}')
print(f'ai_model:          {d.get(\"ai_model\")}')
print(f'sections_tailored: {d.get(\"sections_tailored\")}')
print(f'total_sections:    {d.get(\"total_sections\")}')
for s in d.get('tailored_sections', []):
    print(f'  [{s[\"position_index\"]}] {s[\"section_type\"]:15} | tailored={s[\"was_tailored\"]}')
notes = d.get('improvement_notes', [])
print(f'improvement_notes: {len(notes)}')
passed = d.get('session_id') and d.get('sections_tailored', 0) >= 4 and d.get('ai_model') == 'qwen3:14b'
print('PASS' if passed else 'FAIL')
"
```
**Expected:** session_id present, sections_tailored >= 4, ai_model=qwen3:14b, completes in < 5 min.

---

### Check 3.5 — All stub routes still respond
```bash
for route in /api/score/status /api/export/status /api/providers/status; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route)
  BODY=$(curl -s http://localhost:8000$route)
  echo "$route: $STATUS — $BODY"
done
```
**Expected:** All 200 with `"not implemented yet"` messages.

---

## Section 4 — Code Quality Checks

### Check 4.1 — No syntax errors in any module
```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
python3 -m py_compile modules/parse/extractor.py && echo "extractor.py OK"
python3 -m py_compile modules/parse/section_detector.py && echo "section_detector.py OK"
python3 -m py_compile modules/analyze/jd_analyzer.py && echo "jd_analyzer.py OK"
python3 -m py_compile modules/tailor/resume_tailor.py && echo "resume_tailor.py OK"
python3 -m py_compile routers/auth.py && echo "auth.py OK"
python3 -m py_compile routers/parse.py && echo "parse.py OK"
python3 -m py_compile routers/analyze.py && echo "analyze.py OK"
python3 -m py_compile routers/tailor.py && echo "tailor.py OK"
```
**Expected:** All print `OK` with no errors.

---

### Check 4.2 — File structure is complete
```bash
find /Users/nikunjshetye/Documents/resume-forger/backend -name "*.py" | sort | grep -v __pycache__ | grep -v venv
```
**Expected output includes:**
```
backend/main.py
backend/config.py
backend/database.py
backend/seed.py
backend/models/user.py
backend/models/resume.py
backend/models/resume_section.py
backend/models/job.py
backend/models/tailoring_session.py
backend/models/ai_provider_config.py
backend/schemas/user.py
backend/schemas/resume.py
backend/schemas/job.py
backend/schemas/tailoring_session.py
backend/routers/auth.py
backend/routers/parse.py
backend/routers/analyze.py
backend/routers/tailor.py
backend/routers/score.py
backend/routers/export.py
backend/routers/providers.py
backend/modules/parse/__init__.py
backend/modules/parse/extractor.py
backend/modules/parse/section_detector.py
backend/modules/analyze/__init__.py
backend/modules/analyze/jd_analyzer.py
backend/modules/tailor/__init__.py
backend/modules/tailor/resume_tailor.py
```

---

### Check 4.3 — Uploads directory exists and has files
```bash
ls /Users/nikunjshetye/Documents/resume-forger/backend/data/uploads/
find /Users/nikunjshetye/Documents/resume-forger/backend/data/uploads -name "*.pdf" | wc -l
```
**Expected:** At least one user directory with uploaded PDF files.

---

### Check 4.4 — .env file exists and has required keys
```bash
# Check .env exists and has the required keys (without printing values)
python3 -c "
from pathlib import Path
env = Path('/Users/nikunjshetye/Documents/resume-forger/backend/.env').read_text()
required_keys = ['SECRET_KEY', 'DATABASE_URL', 'ALGORITHM']
for k in required_keys:
    present = k in env
    print(f'{k}: {\"PRESENT\" if present else \"MISSING\"}')"
```
**Expected:** All keys present.

---

### Check 4.5 — requirements.txt is complete
```bash
cat /Users/nikunjshetye/Documents/resume-forger/backend/requirements.txt
```
**Expected:** Includes fastapi, uvicorn, sqlalchemy, pdfplumber, python-docx, requests, python-jose, passlib, bcrypt, pydantic, pydantic-settings.

---

## Section 5 — Git & GitHub

### Check 5.1 — Git status is clean
```bash
cd /Users/nikunjshetye/Documents/resume-forger
git status
git log --oneline -5
```
**Expected:** Working tree clean. Last 5 commits visible.

---

### Check 5.2 — All branches exist and are synced
```bash
git branch -a
git log --oneline dev -3
git log --oneline main -3
```
**Expected:** `main`, `dev`, `feature/day4-resume-tailor` all present. `dev` is ahead of `main`.

---

### Check 5.3 — .gitignore is protecting sensitive files
```bash
cd /Users/nikunjshetye/Documents/resume-forger
git check-ignore -v backend/.env backend/data/resumeforge.db backend/data/uploads/
```
**Expected:** All 3 paths are gitignored.

---

## Section 6 — Known Issues to Carry into Day 5

After all checks complete, report these known issues and their status:

```bash
python3 -c "
known_issues = [
    ('Skills bleeding', 'Technologies: lines in projects still create extra skills sections', 'Fix in Day 5 pre-task'),
    ('Section count', 'Resume currently produces 8 sections instead of clean 6', 'Fix in Day 5 pre-task'),
    ('Leadership label', 'LEADERSHIP & ACTIVITIES still typed as unknown in some uploads', 'Monitor in Day 5'),
    ('DB cleanup', 'Multiple test resumes/jobs from testing — no impact but worth noting', 'Cosmetic only'),
]
print('Known Issues:')
for issue, desc, plan in known_issues:
    print(f'  [{issue}] {desc} → {plan}')
"
```

---

## Final Summary Report

After running all checks, produce this summary table:

```
=== PRE-DAY 5 SYSTEM CHECK REPORT ===

Section 1 — Infrastructure
  1.1 Backend server:        PASS/FAIL
  1.2 Ollama + model:        PASS/FAIL
  1.3 launchd services:      PASS/FAIL
  1.4 Log files:             PASS/FAIL
  1.5 Dependencies:          PASS/FAIL

Section 2 — Database
  2.1 All 6 tables:          PASS/FAIL
  2.2 AI provider config:    PASS/FAIL
  2.3 User data integrity:   PASS/FAIL

Section 3 — API Routes
  3.1 Day 1 — Auth:          PASS/FAIL
  3.2 Day 2 — Parser:        PASS/FAIL
  3.3 Day 3 — Analyzer:      PASS/FAIL
  3.4 Day 4 — Tailor:        PASS/FAIL
  3.5 Stub routes:           PASS/FAIL

Section 4 — Code Quality
  4.1 No syntax errors:      PASS/FAIL
  4.2 File structure:        PASS/FAIL
  4.3 Uploads directory:     PASS/FAIL
  4.4 .env keys:             PASS/FAIL
  4.5 requirements.txt:      PASS/FAIL

Section 5 — Git
  5.1 Git status clean:      PASS/FAIL
  5.2 Branches synced:       PASS/FAIL
  5.3 Gitignore protecting:  PASS/FAIL

Overall: X/18 checks passed
System is READY / NOT READY for Day 5
```

> **Note:** Do NOT fix any failures unless they are critical blockers
> (e.g. server down, DB corrupted, missing files). Log all issues and
> report them — fixes will be handled as Day 5 pre-tasks.
