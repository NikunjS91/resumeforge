# ResumeForge — Day 4 Patch Guide
## 3 Fixes: One-Shot Tailoring + Leadership Section + Skills Bleeding

---

> **Agent Instructions:** Work through Fix 1 → Fix 2 → Fix 3 in order.
> Read the listed files before touching any code.
> Run all verification checks at the end.
> Commit to `feature/day4-resume-tailor` branch when all checks pass.

---

## Context — Why These Fixes

After live testing Day 4, 3 issues were found:

| # | Problem | Impact |
|---|---------|--------|
| 1 | Tailoring takes 15+ minutes — 12 sequential LLM calls with qwen3:14b thinking mode | Unusable UX |
| 2 | Leadership section typed as `unknown` → skipped by tailor | Resume incomplete |
| 3 | `Technologies:` lines inside projects detected as new `skills` headings → 3 skills sections instead of 1 | Messy parsing |

---

## Before Writing Any Code — Read These Files

| File | What to look for |
|------|-----------------|
| `backend/modules/tailor/resume_tailor.py` | Current `tailor_section()` loop, `TAILORABLE_SECTIONS`, `DEFAULT_MODEL` |
| `backend/modules/parse/section_detector.py` | `CONTENT_LINE_SIGNALS`, `SECTION_KEYWORDS`, `TAILORABLE_SECTIONS` |

---

## Fix 1 — One-Shot Tailoring (15 min → ~2 min)

**File:** `backend/modules/tailor/resume_tailor.py`

**What changes:** Replace the entire per-section loop with ONE single LLM call
that sends the full resume and gets back all tailored sections as JSON.

### Step 1a — Add import at top of file

```python
import json as json_lib
```

### Step 1b — Add the one-shot function

Add this NEW function after the existing `ollama_call()` function.
Do NOT delete `tailor_section()` yet — keep it as fallback.

```python
def tailor_resume_oneshot(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
) -> list | None:
    """
    Send the ENTIRE resume to qwen3:14b in ONE call.
    Returns list of tailored section dicts or None if failed.

    This replaces 12 sequential calls with 1 call — ~15min → ~2min.
    """
    if not ollama_available():
        return None

    # Build full resume text from sections
    resume_text = "\n\n".join(
        f"{s.get('section_label', s.get('section_type', '').upper())}\n{s.get('content_text', '')}"
        for s in sorted(resume_sections, key=lambda x: x.get('position_index', 0))
        if s.get('content_text', '').strip()
    )

    required_str   = ", ".join(required_skills[:20]) if required_skills else "not specified"
    nicetohave_str = ", ".join(nice_to_have_skills[:10]) if nice_to_have_skills else "none"

    # Sections to tailor — skip contact and education
    tailorable_types = {"experience", "projects", "skills", "summary", "leadership", "unknown"}
    sections_to_tailor = [
        s for s in resume_sections
        if s.get("section_type") in tailorable_types and s.get("content_text", "").strip()
    ]
    section_list = ", ".join(s.get("section_type") for s in sections_to_tailor)

    prompt = (
        "/no_think\n\n"
        f"You are an expert resume tailor. Rewrite the following resume sections "
        f"to better match a {job_title} role at {company_name}.\n\n"
        f"Sections to rewrite: {section_list}\n"
        f"Required skills to emphasize: {required_str}\n"
        f"Nice to have skills: {nicetohave_str}\n\n"
        f"Rules:\n"
        f"- Keep ALL facts accurate — do NOT invent experience or skills\n"
        f"- Use strong action verbs (Led, Built, Architected, Deployed, Optimized)\n"
        f"- Preserve quantified metrics (%, numbers, scale)\n"
        f"- Match keywords from required skills where truthfully applicable\n"
        f"- Keep roughly the same length as the original\n"
        f"- For sections NOT in the list above, return the original text unchanged\n\n"
        f"Return ONLY valid JSON — no explanation, no markdown, no backticks:\n"
        f'{{"sections": [{{"section_type": "skills", "tailored_text": "...", '
        f'"improvement_notes": ["note1", "note2"]}}, ...]}}\n\n'
        f"Full Resume:\n{resume_text[:4000]}"
    )

    response = ollama_call(prompt)
    if not response:
        logger.warning("One-shot tailor failed — Ollama returned empty response")
        return None

    try:
        # Strip markdown fences if present
        if "```" in response:
            parts = response.split("```")
            response = parts[1] if len(parts) > 1 else parts[0]
            if response.startswith("json"):
                response = response[4:]

        data = json_lib.loads(response.strip())
        tailored_map = {
            s["section_type"]: s
            for s in data.get("sections", [])
        }

        # Build result aligned to original sections
        result = []
        for sec in sorted(resume_sections, key=lambda x: x.get("position_index", 0)):
            sec_type = sec.get("section_type", "other")
            tailored = tailored_map.get(sec_type)

            if tailored and sec_type in tailorable_types:
                result.append({
                    "section_type":   sec_type,
                    "section_label":  sec.get("section_label", sec_type.title()),
                    "position_index": sec.get("position_index", 0),
                    "original_text":  sec.get("content_text", ""),
                    "tailored_text":  tailored.get("tailored_text", sec.get("content_text", "")),
                    "was_tailored":   True,
                    "improvement_notes": tailored.get("improvement_notes", []),
                })
            else:
                result.append({
                    "section_type":   sec_type,
                    "section_label":  sec.get("section_label", sec_type.title()),
                    "position_index": sec.get("position_index", 0),
                    "original_text":  sec.get("content_text", ""),
                    "tailored_text":  sec.get("content_text", ""),
                    "was_tailored":   False,
                    "improvement_notes": [],
                })

        logger.info(f"One-shot tailor returned {len(result)} sections")
        return result

    except Exception as e:
        logger.warning(f"One-shot parse failed: {e} | response: {response[:200]}")
        return None
```

### Step 1c — Replace the `tailor_resume()` main function

Replace the existing `tailor_resume()` function with this updated version
that tries one-shot first and falls back to per-section if it fails:

```python
def tailor_resume(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
) -> dict:
    """
    Full tailoring pipeline — one-shot approach for speed.

    Strategy:
    1. Try one-shot: send full resume in ONE LLM call → ~2 minutes
    2. If one-shot fails: fall back to per-section → ~15 minutes
    """
    if not ollama_available():
        raise RuntimeError("Ollama is not available. Cannot tailor resume.")

    logger.info(
        f"Starting one-shot tailor for {job_title} at {company_name} "
        f"({len(resume_sections)} sections)"
    )

    # ── Try one-shot first ───────────────────────────────────────────
    tailored_sections = tailor_resume_oneshot(
        resume_sections=resume_sections,
        job_title=job_title,
        company_name=company_name,
        required_skills=required_skills,
        nice_to_have_skills=nice_to_have_skills,
    )

    # ── Fallback to per-section if one-shot failed ───────────────────
    if not tailored_sections:
        logger.warning("One-shot failed — falling back to per-section tailoring")
        tailored_sections = []
        for section in sorted(resume_sections, key=lambda s: s.get("position_index", 0)):
            section_type = section.get("section_type", "other")
            content = section.get("content_text", "")

            if section_type in TAILORABLE_SECTIONS and content.strip():
                result = tailor_section(
                    section_type=section_type,
                    section_content=content,
                    job_title=job_title,
                    company_name=company_name,
                    required_skills=required_skills,
                    nice_to_have_skills=nice_to_have_skills,
                )
                tailored_sections.append({
                    "section_type":    section_type,
                    "section_label":   section.get("section_label", section_type.title()),
                    "position_index":  section.get("position_index", 0),
                    "original_text":   result["original_text"],
                    "tailored_text":   result["tailored_text"],
                    "was_tailored":    True,
                    "improvement_notes": result["improvement_notes"],
                })
            else:
                tailored_sections.append({
                    "section_type":    section_type,
                    "section_label":   section.get("section_label", section_type.title()),
                    "position_index":  section.get("position_index", 0),
                    "original_text":   content,
                    "tailored_text":   content,
                    "was_tailored":    False,
                    "improvement_notes": [],
                })

    # ── Build full tailored text ─────────────────────────────────────
    full_tailored = "\n\n".join(
        f"{s['section_label']}\n{s['tailored_text']}"
        for s in sorted(tailored_sections, key=lambda s: s["position_index"])
        if s["tailored_text"]
    )

    all_notes = [
        note
        for s in tailored_sections
        for note in s.get("improvement_notes", [])
    ]

    return {
        "tailored_sections":  tailored_sections,
        "tailored_full_text": full_tailored,
        "sections_tailored":  sum(1 for s in tailored_sections if s["was_tailored"]),
        "total_sections":     len(tailored_sections),
        "improvement_notes":  all_notes,
    }
```

---

## Fix 2 — Leadership Section Typed as `unknown`

Two targeted changes — one in the section detector (root cause),
one in the tailor (safety net).

### Fix 2a — Section Detector (Root Cause)

**File:** `backend/modules/parse/section_detector.py`

In `SECTION_KEYWORDS`, find the `"leadership"` entry and expand it:

```python
"leadership": [
    "leadership",
    "activities",
    "volunteer",
    "extracurricular",
    "community",
    "involvement",
    "clubs",
    "organizations",
    "leadership & activities",
    "activities & leadership",
    "leadership and activities",    # add this
    "activities and leadership",    # add this
    "awards",                       # add this
    "honors",                       # add this
],
```

### Fix 2b — Tailor Safety Net

**File:** `backend/modules/tailor/resume_tailor.py`

Find `TAILORABLE_SECTIONS` and add `"unknown"` and `"leadership"`:

```python
TAILORABLE_SECTIONS = {
    "experience",
    "projects",
    "skills",
    "summary",
    "leadership",
    "unknown",      # add this — catches any unrecognised but valuable sections
}
```

---

## Fix 3 — Skills Bleeding (Technologies: lines splitting sections)

**File:** `backend/modules/parse/section_detector.py`

Find `CONTENT_LINE_SIGNALS` and add these entries:

```python
CONTENT_LINE_SIGNALS = [
    " - ",
    " – ",
    " — ",
    "github",
    "http",
    "www.",
    "@",
    "•",
    "technologies:",     # already there ✅
    "tech stack:",       # add this
    "stack:",            # add this
    "tools:",            # add this
    "frameworks:",       # add this
    "languages:",        # add this — avoid splitting on language lists
    "jan ", "feb ", "mar ", "apr ", "may ", "jun ",
    "jul ", "aug ", "sep ", "oct ", "nov ", "dec ",
]
```

---

## Verification — Run All Checks After All 3 Fixes

### Check 1 — Speed test (most important)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Time the request — should complete in under 3 minutes
time curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2, "job_id": 1}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'session_id:        {data[\"session_id\"]}')
print(f'sections_tailored: {data[\"sections_tailored\"]}')
print(f'total_sections:    {data[\"total_sections\"]}')
for s in data['tailored_sections']:
    print(f'  [{s[\"position_index\"]}] {s[\"section_type\"]:15} | tailored={s[\"was_tailored\"]}')
unknown = [s for s in data['tailored_sections'] if s['section_type'] == 'unknown']
leadership = [s for s in data['tailored_sections'] if s['section_type'] == 'leadership']
print(f'unknown sections:    {len(unknown)}')
print(f'leadership sections: {len(leadership)}')
"
```

**Expected:**
- Completes in < 3 minutes (vs 15+ before)
- `sections_tailored` ≥ 4
- No `unknown` sections with `was_tailored: false` that should be leadership
- Leadership section present and `was_tailored: true`

---

### Check 2 — Section detection improved (re-upload resume)

```bash
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'section_count: {data[\"section_count\"]}')
for s in data['sections']:
    print(f'  [{s[\"position_index\"]}] {s[\"section_type\"]:15} | {s[\"section_label\"]}')
skills_count = sum(1 for s in data['sections'] if s['section_type'] == 'skills')
unknown_count = sum(1 for s in data['sections'] if s['section_type'] == 'unknown')
print(f'skills sections: {skills_count} (should be 1)')
print(f'unknown sections: {unknown_count} (should be 0)')
print('PASS' if skills_count == 1 and unknown_count == 0 else 'FAIL')
"
```

**Expected:**
- `skills_count: 1` — single clean skills section
- `unknown_count: 0` — leadership correctly typed
- `section_count: 6` — same as original correct parsing

---

### Check 3 — One-shot log confirmation

```bash
tail -20 /tmp/resumeforge.log | grep -i "one-shot\|tailor\|section"
```

**Expected:** Log line showing `"Starting one-shot tailor"` and
`"One-shot tailor returned X sections"` — NOT the fallback warning.

---

### Check 4 — Server still healthy, all routes intact

```bash
for route in /health /api/parse/status /api/analyze/status /api/tailor/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
# Expected: all 200
```

---

## Git — After All Checks Pass

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add backend/modules/tailor/resume_tailor.py
git add backend/modules/parse/section_detector.py
git commit -m "fix: Day 4 patch — one-shot tailoring, leadership section, skills bleeding

- Fix 1: Replace per-section loop with single one-shot LLM call
  15min → ~2min, /no_think prefix added for qwen3:14b
  Per-section fallback retained if one-shot fails
- Fix 2: Add 'unknown' to TAILORABLE_SECTIONS
  Add 'leadership and activities' variants to keyword map
- Fix 3: Add technologies/stack/tools/frameworks to CONTENT_LINE_SIGNALS
  Prevents project tech stacks from splitting into new skills sections"

git push origin feature/day4-resume-tailor

# Merge to dev
git checkout dev
git merge feature/day4-resume-tailor
git push origin dev
```

---

## What Is NOT Changed

- `routers/tailor.py` — no changes needed
- `routers/parse.py` — no changes needed
- `models/` — no changes
- DB — existing rows untouched, new tailor calls use improved pipeline

---

> ✅ **Patch complete when:**
> - Check 1 completes in < 3 minutes
> - Check 2 shows `skills_count=1, unknown_count=0`
> - Check 3 shows one-shot log line
> - Check 4 shows all routes 200
