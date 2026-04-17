"""
ats_rules.py — ATS keyword extraction, scoring, and country resume rules.
"""

import re
from collections import Counter

import numpy as np


def _cosine(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


COUNTRY_RULES = {
    "USA": {
        "page_limit": "1 page strictly",
        "photo": False,
        "address_format": "City, State only (e.g., San Francisco, CA)",
        "sections": ["Summary", "Skills", "Experience", "Projects", "Education"],
        "style": "Compact, 1-page, achievement-focused. No personal info (DOB/marital status). Strong action verbs + metrics on every bullet.",
        "flag": "🇺🇸",
        "design": {
            "accent": "#2c3e50",
            "header_bg": "#2c3e50",
            "header_text": "#ffffff",
            "section_color": "#2c3e50",
            "body_text": "#1a1a1a",
            "secondary": "#555555",
            "layout": "single-column",
            "header_style": "Full-width dark navy header band containing name (white, 32px, bold) and contact info (white, 11px) on one line below the name. Section headings: uppercase, bold, color #2c3e50, with a 2px solid #2c3e50 bottom border, font-size 13px. Skills in a 2-column table, no outer border. Tight spacing, compact bullets.",
        },
    },
    "Canada": {
        "page_limit": "1-2 pages",
        "photo": False,
        "address_format": "City, Province only (e.g., Toronto, ON)",
        "sections": ["Summary", "Skills", "Experience", "Projects", "Education", "Volunteer Experience"],
        "style": "Similar to USA but include a Volunteer Experience section. Emphasise soft skills. No personal info.",
        "flag": "🇨🇦",
        "design": {
            "accent": "#c0392b",
            "header_bg": "#ffffff",
            "header_text": "#1a1a1a",
            "section_color": "#c0392b",
            "body_text": "#1a1a1a",
            "secondary": "#555555",
            "layout": "single-column",
            "header_style": "White header, name in bold 34px #c0392b (Canada red), contact info in 11px #555 on one line. Left red vertical sidebar accent: each section heading has a 4px left border in #c0392b, uppercase bold 13px #c0392b, no underline. Skills in a 2-column table. Volunteer section visually identical to Experience.",
        },
    },
    "India": {
        "page_limit": "1-2 pages",
        "photo": True,
        "address_format": "City, State, PIN code",
        "sections": ["Career Objective", "Skills", "Experience", "Projects", "Education", "Certifications", "Achievements", "Languages"],
        "style": "Start with Career Objective. Include photo placeholder (top-right). Add Achievements, Certifications, and Languages sections. No declaration at the bottom.",
        "flag": "🇮🇳",
        "design": {
            "accent": "#1a5276",
            "header_bg": "#eaf4fb",
            "header_text": "#1a1a1a",
            "section_color": "#1a5276",
            "body_text": "#1a1a1a",
            "secondary": "#555555",
            "layout": "single-column with photo",
            "header_style": "Light blue (#eaf4fb) header background, name in bold 30px #1a5276, contact info in 11px below name. If photo: header is display:flex justify-content:space-between — name+contact on the LEFT, photo box on the RIGHT (flex-shrink:0, no float). Section headings: background #1a5276, white text, padding 4px 8px, uppercase bold 12px, full width. Skills in a 3-column table. Languages as inline pills.",
        },
    },
    "Australia": {
        "page_limit": "2-3 pages",
        "photo": False,
        "address_format": "City, State only (e.g., Sydney, NSW)",
        "sections": ["Summary", "Skills", "Experience", "Projects", "Education", "Referees"],
        "style": "More detailed — 3-4 bullets per role with Key Achievements sub-section. Use Australian English (colour, optimise). End with 2 referee entries.",
        "flag": "🇦🇺",
        "design": {
            "accent": "#1e6b3c",
            "header_bg": "#1e6b3c",
            "header_text": "#ffffff",
            "section_color": "#1e6b3c",
            "body_text": "#1a1a1a",
            "secondary": "#555555",
            "layout": "single-column",
            "header_style": "Full-width dark green (#1e6b3c) header band, name in white bold 32px, contact info in white 11px on one line. Section headings: uppercase bold 13px #1e6b3c, with a 2px solid #1e6b3c bottom border. Each experience role has a 'Key Achievements:' sub-heading in italic before its bullets. Skills in 2-column table. Referees section lists 2 referee cards side-by-side.",
        },
    },
}


# Words that are meaningless as ATS keywords — generic English verbs, adjectives, nouns
STOP_WORDS = {
    # Articles / prepositions / conjunctions
    "the", "and", "for", "with", "this", "that", "from", "into", "onto",
    "about", "above", "after", "before", "between", "during", "under",
    # Generic verbs
    "have", "will", "are", "was", "were", "been", "being", "has", "had",
    "use", "used", "using", "work", "working", "build", "building",
    "make", "making", "create", "creating", "help", "helping", "help",
    "get", "give", "take", "put", "set", "run", "see", "look", "come",
    "analyze", "analyse", "seeking", "develop", "implement", "manage",
    "support", "ensure", "maintain", "provide", "improve", "design",
    "define", "identify", "resolve", "deliver", "drive", "execute",
    # Generic adjectives
    "good", "great", "strong", "complex", "large", "small", "high", "low",
    "new", "key", "main", "primary", "secondary", "various", "multiple",
    "relevant", "related", "required", "preferred", "minimum", "ideal",
    "excellent", "proven", "solid", "proficient", "effective",
    # Generic nouns
    "team", "role", "job", "work", "task", "project", "system", "tool",
    "process", "way", "part", "type", "area", "field", "domain", "space",
    "candidate", "position", "opportunity", "company", "organization",
    "environment", "ability", "knowledge", "experience", "skill", "skills",
    "year", "years", "month", "time", "day", "week",
    # Job-posting filler
    "you", "your", "our", "their", "we", "its", "not", "all", "any",
    "would", "should", "must", "can", "may", "also", "well", "etc",
    "including", "such", "other", "plus", "bonus", "join", "looking",
    "responsibilities", "qualifications", "requirements", "basis",
    "full", "part", "level", "senior", "junior", "mid", "lead", "staff",
    "scientist", "engineer", "developer", "manager", "analyst", "specialist",
    "datasets", "dataset", "data",  # too generic — only match as bigrams
}

# Known high-value tech/professional keywords — these get a 3x score boost
POWER_KEYWORDS = {
    # Languages
    "python", "javascript", "typescript", "java", "golang", "rust", "kotlin",
    "swift", "c++", "ruby", "php", "scala", "r", "matlab", "bash", "shell",
    # AI / ML
    "machine learning", "deep learning", "nlp", "llm", "rag", "langchain",
    "tensorflow", "pytorch", "scikit-learn", "transformers", "xgboost",
    "huggingface", "openai", "vector database", "embedding", "fine-tuning",
    "prompt engineering", "computer vision", "reinforcement learning",
    "neural network", "gradient boosting", "random forest",
    # Data
    "sql", "nosql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "spark", "hadoop", "kafka", "airflow", "dbt", "snowflake", "bigquery",
    "pandas", "numpy", "matplotlib", "seaborn", "tableau", "power bi",
    "data pipeline", "etl", "data warehouse", "feature engineering",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "devops", "mlops", "serverless", "microservices", "rest api", "graphql",
    "github actions", "jenkins", "ansible", "helm",
    # Web
    "react", "vue", "angular", "node", "fastapi", "flask", "django",
    "spring boot", "express", "next.js", "tailwind",
    # Soft skills ATS scans
    "agile", "scrum", "cross-functional", "stakeholder", "mentoring",
}


def extract_keywords(job_description: str, top_n: int = 15) -> list[str]:
    """
    Extract meaningful ATS keywords from a job description.

    Strategy:
    - Only keep words that are EITHER in POWER_KEYWORDS OR appear 2+ times
    - Bigrams of non-stop words are always candidates
    - This filters out one-off generic words like 'seeking', 'complex', 'datasets'
    """
    if not job_description or not job_description.strip():
        return []

    text = job_description.lower()

    # Tokenize
    words = re.findall(r'\b[a-z][a-z0-9+#\-\.]*[a-z0-9]\b', text)
    clean_words = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    # Unigram frequency
    unigram_freq = Counter(clean_words)

    # Bigrams of consecutive clean words
    bigrams = []
    for i in range(len(clean_words) - 1):
        bigrams.append(f"{clean_words[i]} {clean_words[i+1]}")
    bigram_freq = Counter(bigrams)

    # Score everything
    scored = {}

    # Bigrams — ONLY if they are a known POWER_KEYWORD phrase (e.g. "machine learning")
    # Generic adjacent-word bigrams like "involves collecting" are noise, skip them
    for bg, count in bigram_freq.items():
        if bg in POWER_KEYWORDS:
            scored[bg] = count * 3.0

    # Unigrams — only include if power keyword OR appears 2+ times
    for word, count in unigram_freq.items():
        if word in POWER_KEYWORDS:
            scored[word] = count * 3.0
        elif count >= 2:
            scored[word] = count * 1.0
        # single-occurrence generic words are ignored entirely

    # Sort by score
    sorted_kws = sorted(scored.items(), key=lambda x: x[1], reverse=True)

    # Deduplicate: skip a unigram if it's already inside a selected bigram
    seen = set()
    result = []
    for kw, _ in sorted_kws:
        if any(kw in selected for selected in result):
            continue
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
        if len(result) >= top_n:
            break

    return result


def calculate_ats_score(resume_text: str, keywords: list[str]) -> dict:
    """Score the resume against extracted keywords."""
    if not keywords:
        return {
            "score": 0, "matched": [], "missing": [],
            "grade": "N/A", "feedback": "No keywords extracted from job description.",
        }

    resume_lower = resume_text.lower()
    matched = [kw for kw in keywords if kw.lower() in resume_lower]
    missing = [kw for kw in keywords if kw.lower() not in resume_lower]

    raw_score = len(matched) / len(keywords) * 100

    # Bonus for matching power keywords (up to +10 pts)
    power_matched = sum(1 for kw in matched if kw in POWER_KEYWORDS)
    score = min(100, int(raw_score + min(10, power_matched * 2)))

    if score >= 85:
        grade, feedback = "A", "Excellent ATS match! Your resume is well-optimized for this role."
    elif score >= 70:
        grade, feedback = "B", "Good match. Consider adding a few more keywords from the missing list."
    elif score >= 50:
        grade, feedback = "C", "Average match. Weave more job-specific keywords into your experience bullets."
    else:
        grade, feedback = "D", "Low match. The resume needs more keywords from the job description."

    return {
        "score": score,
        "matched": matched,
        "missing": missing[:6],
        "grade": grade,
        "feedback": feedback,
    }


def calculate_ats_score_semantic(resume_text: str, keywords: list[str], openai_client) -> dict:
    """
    ATS scoring using OpenAI text-embedding-3-small.
    Exact matches are found first; remaining keywords are checked via
    cosine similarity against resume lines (threshold 0.72).
    """
    if not keywords:
        return {
            "score": 0, "matched": [], "missing": [], "semantic_matched": [],
            "grade": "N/A", "feedback": "No keywords extracted from job description.",
        }

    resume_lower = resume_text.lower()

    exact_matched = [kw for kw in keywords if kw.lower() in resume_lower]
    to_check      = [kw for kw in keywords if kw.lower() not in resume_lower]

    semantic_matched = []

    if to_check:
        chunks = [s.strip() for s in re.split(r"\n+", resume_text) if len(s.strip()) > 8]
        if not chunks:
            chunks = [resume_text[:2000]]

        all_texts = to_check + chunks
        resp = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=all_texts,
        )
        embeddings      = [e.embedding for e in resp.data]
        kw_embeddings   = embeddings[:len(to_check)]
        chunk_embeddings = embeddings[len(to_check):]

        THRESHOLD = 0.72
        for i, kw in enumerate(to_check):
            max_sim = max(_cosine(kw_embeddings[i], ce) for ce in chunk_embeddings)
            if max_sim >= THRESHOLD:
                semantic_matched.append(kw)

    matched = exact_matched + semantic_matched
    missing = [kw for kw in keywords if kw not in matched]

    raw_score     = len(matched) / len(keywords) * 100
    power_matched = sum(1 for kw in matched if kw in POWER_KEYWORDS)
    score         = min(100, int(raw_score + min(10, power_matched * 2)))

    if score >= 85:
        grade, feedback = "A", "Excellent ATS match! Your resume is well-optimized for this role."
    elif score >= 70:
        grade, feedback = "B", "Good match. Consider adding a few more keywords from the missing list."
    elif score >= 50:
        grade, feedback = "C", "Average match. Weave more job-specific keywords into your experience bullets."
    else:
        grade, feedback = "D", "Low match. The resume needs more keywords from the job description."

    return {
        "score":            score,
        "matched":          matched,
        "missing":          missing[:6],
        "semantic_matched": semantic_matched,
        "grade":            grade,
        "feedback":         feedback,
    }


def get_country_rules(country: str) -> dict:
    return COUNTRY_RULES.get(country, COUNTRY_RULES["USA"])


def build_country_instructions(country: str, include_photo: bool = False) -> str:
    rules = get_country_rules(country)
    show_photo = rules["photo"] and include_photo
    d = rules["design"]
    lines = [
        f"COUNTRY: {country} {rules['flag']}",
        f"PAGE LIMIT: {rules['page_limit']}",
        f"PHOTO: {'Include a photo placeholder div (top-right, 90x110px, border:1px solid #ccc, label Photo Placeholder)' if show_photo else 'NO photo — do not add any photo placeholder'}",
        f"ADDRESS FORMAT: {rules['address_format']}",
        f"SECTIONS (in this order): {' → '.join(rules['sections'])}",
        f"CONTENT STYLE: {rules['style']}",
        f"",
        f"VISUAL DESIGN — follow EXACTLY (inline CSS only, no <style> tags):",
        f"  Accent color: {d['accent']}",
        f"  Header background: {d['header_bg']} | Header text: {d['header_text']}",
        f"  Section heading color: {d['section_color']}",
        f"  Body text: {d['body_text']} | Secondary text: {d['secondary']}",
        f"  Layout: {d['layout']}",
        f"  Header & section heading instructions: {d['header_style']}",
    ]
    return "\n".join(lines)

