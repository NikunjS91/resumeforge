# Anti-Hallucination Rules for ResumeForge

## When editing LaTeX generation code:
- NEVER invent metrics or percentages not in source data
- ALWAYS use ════ separators in LLM prompts
- ALWAYS add FINAL REMINDER block after data block
- Test with resume_id=28 only

## When editing the export pipeline:
- Check .tex file before looking at PDF
- Run: LATEST=$(ls -t backend/data/exports/*.tex | head -1) && grep -E "GPA|[0-9]+%" "$LATEST"
- GPA in output MUST be 3.84 exactly
- LinkedIn/GitHub must be real URLs not placeholders

## When adding new API endpoints:
- Add to CLAUDE.md Key API Endpoints table
- Test with the Standard Verification Pattern
- Always check for master_latex column existence
