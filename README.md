# ⚡ ATS Resume Generator — AI Powered

> A full-stack web app that uses a **local LLM (Ollama/llama3)** to generate perfectly tailored, ATS-optimized resumes for **USA, Canada, India, and Australia** — with live keyword scoring, country-specific conventions, and one-click PDF export.

![Stack](https://img.shields.io/badge/Backend-Python%20Flask-blue)
![Stack](https://img.shields.io/badge/AI-Ollama%20llama3-purple)
![Stack](https://img.shields.io/badge/Frontend-Vanilla%20JS-yellow)
![Stack](https://img.shields.io/badge/Cost-100%25%20Free-green)

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Browser (frontend/)                             │
│  ┌─────────────────┐   ┌──────────────────────┐ │
│  │   Left Panel    │   │   Right Panel        │ │
│  │  - Input Form   │   │  - Resume Preview    │ │
│  │  - Country UI   │   │  - ATS Score Bar     │ │
│  │  - Batch Btn    │   │  - Keyword Chips     │ │
│  └────────┬────────┘   └──────────────────────┘ │
│           │ POST /generate-resume                 │
└───────────┼──────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────┐
│  Flask Backend (backend/)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │   app.py    │  │resume_builder│  │ats_rules│ │
│  │ HTTP routes │→ │  AI prompts  │→ │keywords │ │
│  │ validation  │  │ Ollama calls │  │ scoring │ │
│  └─────────────┘  └──────┬───────┘  └─────────┘ │
└─────────────────────────┼────────────────────────┘
                           │ ollama.chat()
┌──────────────────────────▼───────────────────────┐
│  Ollama (local LLM server)                       │
│  Model: llama3 / mistral (auto-detected)         │
│  Runs at: http://localhost:11434                 │
└──────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Vanilla JS, no frameworks** | Zero build step, instant demo, easy to explain in interviews |
| **Separated `ats_rules.py`** | Domain logic is isolated and unit-testable independently of the LLM |
| **Sandboxed iframe preview** | Prevents injected HTML from accessing parent DOM (XSS safe) |
| **Model auto-detection** | Gracefully uses whatever Ollama model is installed |
| **Stateless Flask API** | No database needed; each request is fully self-contained |
| **Low temperature (0.3)** | Consistent, structured HTML output from the LLM |

---

## Setup (3 Steps)

### Step 1 — Install Ollama

```bash
# macOS
brew install ollama

# Or download from: https://ollama.ai
```

### Step 2 — Pull the llama3 model

```bash
ollama pull llama3
```

> This downloads ~4GB once. After that, generation is instant and **100% free** — no API keys, no rate limits.

```bash
# Check it works:
ollama list
# Should show: llama3:latest

# Optional: also pull mistral as fallback
ollama pull mistral
```

### Step 3 — Run the backend

```bash
cd backend

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py
```

You should see:
```
============================================================
  ATS Resume Generator — Backend API
  Running at: http://localhost:5000
============================================================
```

### Open the frontend

```bash
# Simply open the HTML file in your browser:
open frontend/index.html

# Or serve it locally (avoids some browser CORS quirks):
cd frontend && python -m http.server 3000
# Then open: http://localhost:3000
```

---

## Docker Setup (Alternative)

```bash
# Build and start both Ollama + Flask in one command:
docker compose up --build

# Ollama will automatically pull llama3 on first start.
# Then open: frontend/index.html
```

---

## API Reference

### `GET /`
Health check.

### `POST /generate-resume`
Generate an ATS-optimized resume.

**Request body:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+1 555 000 0000",
  "linkedin": "linkedin.com/in/janedoe",
  "city": "San Francisco, CA",
  "country": "USA",
  "include_photo": false,
  "job_description": "We are hiring a Senior ML Engineer...",
  "experience": "ML Engineer at Acme Corp 2021-2023...",
  "skills": "Python, PyTorch, AWS, Docker",
  "education": "MS Computer Science, Stanford, 2021",
  "projects": "RAG Chatbot: built with LangChain..."
}
```

**Response:**
```json
{
  "resume_html": "<div class=\"resume\">...</div>",
  "ats_score": 82,
  "ats_grade": "B",
  "ats_feedback": "Good ATS match. Consider adding a few more keywords.",
  "matched_keywords": ["python", "machine learning", "aws"],
  "missing_keywords": ["kubernetes", "mlops"],
  "all_keywords": ["python", "machine learning", "aws", ...],
  "model_used": "llama3",
  "country": "USA",
  "flag": "🇺🇸"
}
```

### `POST /download-pdf`
Server-side PDF generation (requires wkhtmltopdf installed).

### `GET /check-ollama`
Check Ollama availability and list installed models.

---

## Country-Specific Resume Rules

| Country | Pages | Photo | Special Sections |
|---------|-------|-------|-----------------|
| 🇺🇸 USA | 1 (strict) | No | Achievement-focused bullets |
| 🇨🇦 Canada | 1-2 | No | Volunteer Experience |
| 🇮🇳 India | 1-2 | Optional | Career Objective, Personal Details, Declaration |
| 🇦🇺 Australia | 2-3 | No | Referees, Key Achievements |

---

## Features

- **AI keyword extraction** — pulls top 15 ATS keywords from any job description
- **Smart rewriting** — every bullet becomes `[Action Verb] + [What] + [Metric]`
- **Live ATS score** — percentage match + grade (A/B/C/D)
- **Batch generation** — generate all 4 country versions in one click
- **PDF download** — server-side via pdfkit or browser print fallback
- **Model auto-detection** — uses whatever Ollama model you have installed
- **No API costs** — 100% local, runs on your machine

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript (ES2022) |
| Backend | Python 3.12, Flask 3.1, Flask-CORS |
| AI/LLM | Ollama, llama3 (or mistral fallback) |
| PDF | pdfkit + wkhtmltopdf (optional) |
| Container | Docker + Docker Compose |

---

*Built to demonstrate full-stack AI application development with local LLM integration.*
