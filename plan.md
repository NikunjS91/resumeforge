# Day 15 Fix Plan

> Created: 2026-04-02
> Bugs addressed: BUG-020, BUG-021, BUG-022, BUG-023, BUG-024

---

## Fix 1 — BUG-022: Duplicate Leadership Header (5 min)

**File:** `backend/modules/export/latex_generator.py`

`_build_leadership_latex()` starts with `\resumesection{Leadership \& Activities}`.
`_replace_latex_section()` preserves the existing one from LLM output → two headers.

**Change:**
- Remove `\resumesection{Leadership \& Activities}` from `_build_leadership_latex()` return value
- In `post_process_latex` append branch (section not found in LLM output), prepend the header manually before calling `_build_leadership_latex`

---

## Fix 2 — BUG-024: CodeChef Entry Wrong (15 min)

**Files:** `backend/modules/tailor/resume_tailor.py`, `backend/modules/export/latex_generator.py`

**Part A — Stop tailoring Leadership section:**
- Remove `'leadership'` from `tailorable_types` in `resume_tailor.py` (both the set at line ~68 and the fallback set at line ~222)
- Leadership dates and descriptions must not be modified by the LLM

**Part B — Robust heading detection in `_build_leadership_latex`:**
- Currently skips lines without dates (`else: i += 1`)
- Change: if a line has no date BUT looks like an org/role heading (not a description sentence — e.g. starts with a capitalized org name, no leading bullet), treat it as a heading with empty dates instead of silently dropping it

---

## Fix 3 — BUG-020: Section Order Wrong (10 min)

**Files:** `backend/templates/professional.tex`, `backend/modules/export/latex_generator.py`

**Part A — Fix `detect_candidate_type()`:**
- After checking experience length, also check if the education section contains "Expected" (future graduation)
- If degree is still in progress → return `'fresher'` regardless of experience length
- This candidate has Expected May 2026 → should be `'fresher'`

**Part B — Reorder `professional.tex` template:**
- Move `%% EDUCATION` block (LATEX_EDUCATION_BLOCK + LATEX_COURSEWORK_BLOCK) BEFORE `%% EXPERIENCE` (LATEX_EXPERIENCE_BLOCK)
- New order: Header → Education → Skills → Experience → Projects → Leadership

**Part C — Update prompt FINAL REMINDER:**
- `build_stage1_prompt`: line 552 — change section order check to "Education → Skills → Experience → Projects → Leadership"
- `build_template_fill_prompt` FINAL CHECKS: update LATEX_COURSEWORK_BLOCK rule for fresher candidates

---

## Fix 4 — BUG-021/023: Missing Bachelor's + Coursework (25 min)

**File:** `backend/modules/export/latex_generator.py`

Add `_build_education_latex(sections, candidate_type)` post-processor:

1. Read `education` section → Pace University content
2. Read `coursework` section:
   - `section_label` contains the actual coursework subjects ("Relevant Coursework: Distributed Systems...")
   - `content_text` contains the misclassified Bharati Vidyapeeth Bachelor's degree data
3. Parse each block into `\resumesubheading` entries (school, location, degree+GPA, date)
4. For `fresher` candidates, append inline coursework line after Pace entry
5. Return complete `\latex_EDUCATION_BLOCK` LaTeX

Call `_build_education_latex` from `post_process_latex` to replace the LLM-generated education block.

**Parser fix (section label extraction):**
- Extract coursework subjects from `section_label` using regex: `r'Relevant Coursework:\s*(.+)'`
- These subjects are currently only in the label, never passed to the LLM

---

## Implementation Order

1. Fix 1 (BUG-022) — quickest, isolated change
2. Fix 2 (BUG-024) — stops data corruption at the source
3. Fix 3 (BUG-020) — reorders template + detection
4. Fix 4 (BUG-021/023) — adds education post-processor

## Verification

After all fixes, generate a new export and verify:
- [ ] Education comes BEFORE Experience
- [ ] Bharati Vidyapeeth Bachelor's entry present with GPA 3.56/4.0
- [ ] Relevant Coursework shown inline under Pace University
- [ ] Leadership has exactly ONE section header
- [ ] CodeChef entry has dates (Jan 2022 – May 2023) and mentor description
- [ ] AWS Cloud Club is a separate entry from CodeChef
- [ ] GPA 3.84/4.0 unchanged
- [ ] All 6 experience bullets present
- [ ] All 3 projects in correct order with Technologies lines
