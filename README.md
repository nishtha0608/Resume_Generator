# ⚡ ResumeAI — ATS Resume Generator

> A full-stack web app that uses **OpenAI GPT-4o-mini** + **semantic similarity scoring** to generate perfectly tailored, ATS-optimized resumes for **USA, Canada, India, and Australia** — with live keyword scoring, country-specific conventions, and one-click PDF export.

![Stack](https://img.shields.io/badge/Backend-Python%20Flask-blue)
![Stack](https://img.shields.io/badge/AI-OpenAI%20GPT--4o--mini-purple)
![Stack](https://img.shields.io/badge/Scoring-Semantic%20Similarity-orange)
![Stack](https://img.shields.io/badge/Frontend-Vanilla%20JS-yellow)
![Stack](https://img.shields.io/badge/Deploy-Docker-2496ED)

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Browser (frontend/)                             │
│  ┌─────────────────┐   ┌──────────────────────┐ │
│  │   Left Panel    │   │   Right Panel        │ │
│  │  - Input Form   │   │  - Resume Preview    │ │
│  │  - Country UI   │   │  - ATS Score Bar     │ │
│  │  - Country Tabs │   │  - Keyword Chips     │ │
│  └────────┬────────┘   └──────────────────────┘ │
│           │ POST /generate-resume                 │
└───────────┼──────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────┐
│  Flask Backend (backend/)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │   app.py    │  │resume_builder│  │ats_rules│ │
│  │ HTTP routes │→ │ GPT-4o-mini  │→ │keywords │ │
│  │ validation  │  │  prompts     │  │semantic │ │
│  └─────────────┘  └──────┬───────┘  │ scoring │ │
└─────────────────────────┼───────────└─────────┘─┘
                           │ OpenAI API
┌──────────────────────────▼───────────────────────┐
│  OpenAI API                                      │
│  Resume gen:   gpt-4o-mini  (chat completions)  │
│  ATS scoring:  text-embedding-3-small            │
└──────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **GPT-4o-mini** | Fast, cheap, and excellent at structured HTML output |
| **Semantic ATS scoring** | Uses `text-embedding-3-small` to catch synonyms — "ML" matches "machine learning" |
| **Score user input, not AI output** | AI always weaves in all keywords; scoring original content gives honest gap analysis |
| **Vanilla JS, no frameworks** | Zero build step, instant demo, easy to explain in interviews |
| **Separated `ats_rules.py`** | Domain logic is isolated and unit-testable independently of the LLM |
| **Sandboxed iframe preview** | Prevents injected HTML from accessing parent DOM (XSS safe) |
| **Stateless Flask API** | No database needed; each request is fully self-contained |
| **Low temperature (0.3)** | Consistent, structured HTML output from the LLM |

---

## Setup

### Prerequisites

- Docker & Docker Compose installed
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Step 1 — Add your API key

Create a `.env` file in the project root:

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

### Step 2 — Start with Docker

```bash
docker compose up --build -d
```

### Step 3 — Open the frontend

```bash
open frontend/index.html
```

The status dot in the top-right turns green when the API key is valid.

---

## Local Development (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
python app.py
# → Running at http://localhost:5001
```

---

## API Reference

### `GET /`
Health check.

**Response:** `{ "status": "ok", "service": "ATS Resume Generator API" }`

### `GET /check-openai`
Verify OpenAI API key is configured.

**Response:** `{ "available": true, "model": "gpt-4o-mini" }`

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

Country-specific optional fields:
- **India:** `career_objective`, `certifications`, `achievements`, `languages`
- **Canada:** `volunteer`
- **Australia:** `referee1`, `referee2` (objects with `name`, `title`, `company`, `phone`, `email`)

**Response:**
```json
{
  "resume_html": "<div>...</div>",
  "ats_score": 74,
  "ats_grade": "B",
  "ats_feedback": "Good match. Consider adding a few more keywords.",
  "matched_keywords": ["python", "machine learning", "aws"],
  "missing_keywords": ["kubernetes", "mlops"],
  "semantic_matched": ["ml", "deep learning"],
  "all_keywords": ["python", "machine learning", "aws", "..."],
  "model_used": "gpt-4o-mini",
  "country": "USA",
  "flag": "🇺🇸"
}
```

### `POST /download-pdf`
Server-side PDF generation (requires `wkhtmltopdf`). Falls back with `501` — frontend uses `window.print()` in that case.

---

## ATS Scoring — How It Works

Scoring runs on the **user's original input** (not the AI-generated resume) to give honest keyword gap analysis.

1. **Extract keywords** from the job description using `POWER_KEYWORDS` + frequency filtering (no garbage bigrams)
2. **Exact match** — check if each keyword appears literally in the user's experience/skills text
3. **Semantic match** — for keywords not found exactly, embed them with `text-embedding-3-small` and compare cosine similarity against resume lines (threshold 0.72)
4. **Score** = matched / total × 100, with a +10 bonus for matching high-value power keywords

In the UI, exact matches show as green chips, semantic matches as blue `~keyword` chips.

---

## Country-Specific Resume Rules

| Country | Pages | Photo | Special Sections | Design |
|---------|-------|-------|-----------------|--------|
| 🇺🇸 USA | 1 (strict) | No | — | Dark navy header |
| 🇨🇦 Canada | 1–2 | No | Volunteer Experience | White header, red accents |
| 🇮🇳 India | 1–2 | Optional | Career Objective, Certifications, Achievements, Languages | Light blue header |
| 🇦🇺 Australia | 2–3 | No | Referees, Key Achievements | Dark green header |

---

## Features

- **GPT-4o-mini resume generation** — fast, structured, ATS-ready HTML
- **Semantic ATS scoring** — catches synonyms via OpenAI embeddings
- **Honest score** — measured against user's raw input, not AI output
- **AI keyword extraction** — top 15 keywords from any job description
- **Smart rewriting** — every bullet becomes `[Action Verb] + [What] + [Metric]`
- **Live ATS score** — percentage, letter grade (A/B/C/D), matched vs missing chips
- **Typography optimized** — precise font sizing, spacing, and hierarchy per country
- **PDF download** — server-side pdfkit or browser print fallback
- **Dark/light theme** — persisted in localStorage
- **Dockerized** — one command to run everything

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript (ES2022) |
| Backend | Python 3.12, Flask 3.1, Flask-CORS |
| Resume AI | OpenAI GPT-4o-mini (chat completions) |
| ATS Scoring | OpenAI text-embedding-3-small + NumPy cosine similarity |
| PDF | pdfkit + wkhtmltopdf (optional) |
| Container | Docker + Docker Compose |

---

*Built to demonstrate full-stack AI application development with OpenAI API integration, semantic search, and country-specific document generation.*
