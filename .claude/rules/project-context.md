# Project Context Rules

## Resume IDs
- CORRECT: resume_id=28 (Resume_10March.pdf, GPA 3.84)
- WRONG: resume_id=2 (ResumeWorded.pdf, GPA 3.5)

## Server startup
- ALWAYS export PATH="/Library/TeX/texbin:$PATH" before uvicorn
- Backend port: 8000, Frontend: 5173, Ollama: 11434

## NVIDIA NIM
- ALWAYS use stream=True in resume_tailor.py
- Model: meta/llama-3.3-70b-instruct
- Timeout: 180 seconds minimum
