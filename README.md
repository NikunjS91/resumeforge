# ResumeForge 🔨

Local AI-powered resume tailoring tool. 100% free, runs on your machine.

## Stack
- **Ollama** (local LLM — mistral:7b)
- **Streamlit** (browser UI)
- **ReportLab** (ATS-friendly PDF)
- **PyMuPDF** (resume PDF parsing)

## Quick Start

### 1. Install (one-time setup)
```bash
chmod +x install.sh
./install.sh
```

This will:
- Install Ollama (if not present)
- Pull mistral:7b model (~4GB)
- Install Python dependencies
- Set up directory structure

### 2. Configure Your Profile
```bash
# Edit your work history profile
code data/profile.md  # or use any editor
```

Fill in your work experience, projects, and skills. The more detail you provide, the better the tailored resumes will be.

### 3. Run Ollama (in one terminal)
```bash
ollama serve
```

### 4. Start ResumeForge (in another terminal)
```bash
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Project Structure

```
/Users/nikunjshetye/Project/ResumeForge/
│
├── README.md                    ← You are here
├── install.sh                   ← One-click setup script
├── requirements.txt             ← Python dependencies
│
├── config/
│   └── settings.py              ← Configuration (model, paths, settings)
│
├── data/
│   ├── resume/                  ← Drop your base resume PDF/DOCX here
│   │   └── README.md
│   ├── profile.md               ← Your work history (edit this!)
│   └── jobs/                    ← Auto-created per application
│       └── company-role-YYYY-MM-DD/
│           ├── posting.md       ← Job description
│           ├── resume.md        ← Tailored resume (markdown)
│           └── resume.pdf       ← ATS-friendly PDF export
│
├── prompts/
│   ├── tailor_resume.md         ← Resume tailoring prompt
│   ├── analyze_job.md           ← Job requirement extraction prompt
│   └── ats_score.md             ← ATS scoring prompt
│
├── src/
│   ├── __init__.py
│   ├── ollama_client.py         ← Ollama API interface
│   ├── resume_parser.py         ← PDF/DOCX resume reader
│   ├── job_analyzer.py          ← Job description parser
│   ├── tailor_agent.py          ← Main AI tailoring logic
│   ├── ats_scorer.py            ← Keyword matching & ATS scoring
│   └── pdf_exporter.py          ← Generates ATS-friendly PDFs
│
└── app.py                       ← Streamlit UI (main entry point)
```

## Usage

1. **Paste a job description** into the text area
2. **Click "Tailor Resume"** to generate a customized version
3. **Review the ATS score** and keyword matches
4. **Download the PDF** ready for submission

## Features

✅ **100% Local** - No data leaves your machine  
✅ **ATS-Optimized** - Clean formatting that passes Applicant Tracking Systems  
✅ **Keyword Matching** - Highlights matched/missing keywords from job posting  
✅ **Achievement Focus** - Emphasizes quantifiable accomplishments  
✅ **Version History** - Saves each tailored resume with job description  

## Model Options

Default: `mistral:7b` (best for M3 Mac, 4GB)

Alternatives:
```bash
# Lighter/faster option
export OLLAMA_MODEL="llama3.2:3b"

# Alternative quality model
export OLLAMA_MODEL="qwen2.5:7b"
```

## Tips for Best Results

1. **Fill out `data/profile.md` thoroughly** - The more detail, the better
2. **Include metrics** - Quantify achievements whenever possible
3. **Review & edit** - AI is a starting point, not the final product
4. **Customize per role** - Emphasize different experiences for different jobs

## Requirements

- macOS/Linux (Windows via WSL)
- 8GB+ RAM (16GB recommended for M3)
- 5GB free disk space
- Python 3.10+

## Troubleshooting

### "Could not connect to ollama server"
Make sure Ollama is running: `ollama serve`

### Model not found
Pull the model: `ollama pull mistral:7b`

### Out of memory
Try a smaller model: `ollama pull llama3.2:3b`

## License

MIT - Free to use, modify, and distribute.
