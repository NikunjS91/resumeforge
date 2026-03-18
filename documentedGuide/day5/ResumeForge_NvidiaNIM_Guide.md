# ResumeForge — NVIDIA NIM Integration Guide
## Add NVIDIA NIM API as External LLM Provider

---

> **Agent Instructions:** Work through Steps 1 → 7 sequentially. Do not skip.
> Read all listed files before writing any code.
> The NVIDIA API key is already set in `backend/.env` as `NVIDIA_API_KEY`.
> Do NOT print or log the API key at any point.
> Integration is complete only when all 5 verification checks pass.

---

## What This Does

Adds NVIDIA NIM API as an optional provider for the Resume Tailor.
The user can now choose between:
- `"provider": "ollama"` — local qwen3:14b (~2-3 minutes, free, private)
- `"provider": "nvidia"` — NVIDIA NIM cloud API (~10 seconds, higher quality)

The NVIDIA NIM API is **OpenAI-compatible** — same `/v1/chat/completions` format,
different base URL and API key.

**Model used:** `meta/llama-3.3-70b-instruct` (free endpoint on NVIDIA NIM)

---

## Before Writing Any Code — Read These Files

| File | Why |
|------|-----|
| `backend/modules/tailor/resume_tailor.py` | Add nvidia_nim_call() + update tailor_resume_oneshot() + tailor_resume() |
| `backend/routers/tailor.py` | Update TailorRequest schema + pass provider through |
| `backend/.env` | NVIDIA_API_KEY is already set here — do NOT modify |
| `backend/config.py` | Check how other env vars are loaded |

---

## Step 1 — Install openai SDK

The NVIDIA NIM API uses the OpenAI-compatible format.
The `openai` Python SDK works with it directly.

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
pip install openai
pip show openai | grep Version
```

**Expected:** `openai` package installed, version shown.

Also add to requirements.txt:
```bash
echo "openai" >> requirements.txt
```

---

## Step 2 — Create Feature Branch

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git checkout dev
git checkout -b feature/nvidia-nim-provider
```

---

## Step 3 — Update resume_tailor.py

**File:** `backend/modules/tailor/resume_tailor.py`

### 3a — Add imports at the top of the file

Add these imports if not already present:
```python
import os
from openai import OpenAI
```

### 3b — Add NVIDIA NIM constants after existing constants

Add these right after `DEFAULT_MODEL = "qwen3:14b"` and `TIMEOUT = 180`:

```python
NVIDIA_NIM_BASE  = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL     = "meta/llama-3.3-70b-instruct"
NVIDIA_TIMEOUT   = 60
```

### 3c — Add nvidia_nim_call() function

Add this new function immediately after the existing `ollama_call()` function:

```python
def nvidia_nim_call(prompt: str) -> str | None:
    """
    Call NVIDIA NIM API using OpenAI-compatible format.
    ~10x faster than local Ollama for resume tailoring.
    Falls back to Ollama if key not set or call fails.
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        logger.warning("NVIDIA_API_KEY not found in environment — cannot use NVIDIA NIM")
        return None
    try:
        client = OpenAI(
            base_url=NVIDIA_NIM_BASE,
            api_key=api_key,
        )
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
            timeout=NVIDIA_TIMEOUT,
        )
        result = response.choices[0].message.content.strip()
        # Strip any think tags just in case
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        logger.info(f"NVIDIA NIM call successful — model={NVIDIA_MODEL}")
        return result if result else None
    except Exception as e:
        logger.warning(f"NVIDIA NIM call failed: {e}")
        return None
```

### 3d — Update tailor_resume_oneshot() signature

Find the existing `tailor_resume_oneshot()` function.
Add `provider: str = "ollama"` as the last parameter:

```python
def tailor_resume_oneshot(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
    provider: str = "ollama",   # ← add this
) -> list | None:
```

Inside the function, find the line that calls `ollama_call(prompt)` and replace it with:

```python
# Route to the correct provider
if provider == "nvidia":
    logger.info("Using NVIDIA NIM for one-shot tailoring")
    response = nvidia_nim_call(prompt)
    if not response:
        logger.warning("NVIDIA NIM failed — falling back to Ollama")
        response = ollama_call(prompt)
else:
    response = ollama_call(prompt)
```

### 3e — Update tailor_resume() signature

Find the existing `tailor_resume()` function.
Add `provider: str = "ollama"` as the last parameter:

```python
def tailor_resume(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
    provider: str = "ollama",   # ← add this
) -> dict:
```

Inside the function, pass `provider=provider` to `tailor_resume_oneshot()`:

```python
tailored_sections = tailor_resume_oneshot(
    resume_sections=resume_sections,
    job_title=job_title,
    company_name=company_name,
    required_skills=required_skills,
    nice_to_have_skills=nice_to_have_skills,
    provider=provider,          # ← add this
)
```

---

## Step 4 — Update routers/tailor.py

**File:** `backend/routers/tailor.py`

### 4a — Update imports at top

Add to imports:
```python
from typing import Optional
from modules.tailor.resume_tailor import DEFAULT_MODEL, NVIDIA_MODEL
```

### 4b — Update TailorRequest schema

Find the existing `TailorRequest` class and add the `provider` field:

```python
class TailorRequest(BaseModel):
    resume_id: int
    job_id:    int
    provider:  Optional[str] = "ollama"  # "ollama" or "nvidia"

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": 2,
                "job_id":    1,
                "provider":  "ollama"
            }
        }
```

### 4c — Update tailor_resume() call in endpoint

Find the `tailor_resume(...)` call inside the endpoint and add `provider=request.provider`:

```python
result = tailor_resume(
    resume_sections=sections_data,
    job_title=job.job_title or "the role",
    company_name=job.company_name or "the company",
    required_skills=required_skills,
    nice_to_have_skills=nice_to_have_skills,
    provider=request.provider,    # ← add this
)
```

### 4d — Update ai_model saved to DB

Find where `ai_model` is set for the session record and update it:

```python
ai_model = NVIDIA_MODEL if request.provider == "nvidia" else DEFAULT_MODEL
```

Then use `ai_model` when creating the `TailoringSession` record instead of hardcoded `DEFAULT_MODEL`.

---

## Step 5 — Verify Server Reloaded

Since uvicorn runs with `--reload`, it auto-reloads on file save.
Confirm no syntax errors:

```bash
curl -s http://localhost:8000/health
# Expected: {"status":"healthy"}

curl -s http://localhost:8000/api/tailor/status
# Expected: 200
```

---

## Verification Checks (All 5 Must Pass)

Get a token first:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

### Check 1 — openai package installed

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
pip show openai | grep -E "Name|Version"
# Expected: Name: openai, Version: X.X.X
```

---

### Check 2 — NVIDIA_API_KEY loaded by server (without printing it)

```bash
python3 -c "
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
key = os.getenv('NVIDIA_API_KEY', '')
print(f'NVIDIA_API_KEY set: {bool(key)} (length={len(key)})')
"
# Expected: NVIDIA_API_KEY set: True (length > 10)
```

---

### Check 3 — Ollama provider still works (default behaviour unchanged)

```bash
time curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2, "job_id": 1, "provider": "ollama"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'provider: ollama')
print(f'ai_model:          {d[\"ai_model\"]}')
print(f'sections_tailored: {d[\"sections_tailored\"]}')
print('PASS' if d.get('ai_model') == 'qwen3:14b' else 'FAIL')
"
# Expected: ai_model=qwen3:14b, sections_tailored >= 4, PASS
```

---

### Check 4 — NVIDIA NIM provider works and is FASTER

```bash
echo "Testing NVIDIA NIM provider..."
time curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2, "job_id": 1, "provider": "nvidia"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'provider: nvidia')
print(f'ai_model:          {d[\"ai_model\"]}')
print(f'sections_tailored: {d[\"sections_tailored\"]}')
print(f'improvement_notes: {d[\"improvement_notes\"][:2]}')
print('PASS' if 'llama' in d.get('ai_model', '').lower() and d.get('sections_tailored', 0) >= 4 else 'FAIL')
"
# Expected:
# - Completes in < 30 seconds (vs 2-3 min for Ollama)
# - ai_model contains "llama-3.3-70b"
# - sections_tailored >= 4
# - PASS
```

---

### Check 5 — provider field visible in Swagger UI

```bash
curl -s http://localhost:8000/openapi.json \
  | python3 -c "
import sys, json
schema = json.load(sys.stdin)
tailor_schema = schema.get('components', {}).get('schemas', {}).get('TailorRequest', {})
props = tailor_schema.get('properties', {})
print(f'TailorRequest fields: {list(props.keys())}')
print('PASS' if \"provider\" in props else 'FAIL — provider field missing from schema')
"
# Expected: TailorRequest fields includes 'provider', PASS
```

---

## Git — After All 5 Checks Pass

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add backend/modules/tailor/resume_tailor.py
git add backend/routers/tailor.py
git add backend/requirements.txt
git commit -m "feat: add NVIDIA NIM API provider for resume tailoring

- POST /api/tailor/resume now accepts optional 'provider' field
- provider='nvidia' uses NVIDIA NIM meta/llama-3.3-70b-instruct
- provider='ollama' (default) uses local qwen3:14b — unchanged
- NVIDIA NIM is ~10x faster than local Ollama (~10s vs ~2-3min)
- Automatic fallback to Ollama if NVIDIA call fails
- ai_model saved correctly per provider in tailoring_sessions"

git push origin feature/nvidia-nim-provider
```

---

## Speed Comparison Expected

| Provider | Model | Expected Time |
|----------|-------|--------------|
| `ollama` | qwen3:14b (local) | ~2-3 minutes |
| `nvidia` | meta/llama-3.3-70b-instruct | ~10-20 seconds |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `AuthenticationError: 401` | Check NVIDIA_API_KEY in .env is correct and not expired |
| `ModuleNotFoundError: openai` | Run `pip install openai` in venv |
| `nvidia_nim_call returns None` | Check server logs — NVIDIA_API_KEY may not be loading from .env |
| Ollama default broken | Check `DEFAULT_MODEL` import — should still be `qwen3:14b` |
| `provider` not in Swagger | Server didn't reload — save the file again or restart uvicorn |

---

## What Is NOT Changed

- `routers/parse.py` — untouched
- `routers/analyze.py` — untouched
- `routers/score.py` — untouched
- DB schema — untouched
- qwen3:14b default behaviour — untouched (backward compatible)

---

> ✅ **Integration complete when all 5 checks pass and both providers tested.**
