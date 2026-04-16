"""
resume_builder.py — Core AI engine for ATS Resume Generator.
Uses OpenAI GPT-4o-mini — fast, cheap, and great at structured HTML output.
"""

import os
import re
import logging

from openai import OpenAI
from dotenv import load_dotenv

from ats_rules import (
    extract_keywords,
    calculate_ats_score,
    get_country_rules,
    build_country_instructions,
)

load_dotenv()
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o-mini"


def _t(text: str, max_chars: int) -> str:
    """Truncate text to max_chars."""
    if not text:
        return ""
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _referee_block(ref) -> str:
    """Format a single referee dict into a readable string for the prompt."""
    if not ref or not ref.get("name"):
        return ""
    parts = [ref["name"]]
    if ref.get("title"):   parts.append(ref["title"])
    if ref.get("company"): parts.append(ref["company"])
    contact = " | ".join(filter(None, [ref.get("phone", ""), ref.get("email", "")]))
    if contact: parts.append(contact)
    return " · ".join(parts)


def _build_prompt(data: dict, keywords: list) -> tuple:
    """
    Build system + user prompts.
    Only injects a section when the user provided data for it —
    prevents the AI from printing empty sections or fabricating content.
    """
    country = data.get("country", "USA")
    rules   = get_country_rules(country)
    kw      = ", ".join(keywords[:10]) if keywords else "N/A"

    # ── Photo (India only) ──
    photo_html = ""
    if data.get("include_photo") and rules["photo"]:
        photo_html = (
            '\nPHOTO: Place this placeholder top-right of the header: '
            '<div style="float:right;width:90px;height:110px;border:1px solid #ccc;'
            'display:flex;align-items:center;justify-content:center;font-size:11px;'
            'color:#999;text-align:center;margin-left:20px;">Photo</div>'
        )

    # ── Build optional sections only where user provided data ──
    optional_sections = []

    career_obj   = data.get("career_objective", "").strip()
    certs        = data.get("certifications", "").strip()
    achievements = data.get("achievements", "").strip()
    languages    = data.get("languages", "").strip()
    volunteer    = data.get("volunteer", "").strip()

    if career_obj:   optional_sections.append(f"CAREER OBJECTIVE: {_t(career_obj, 400)}")
    if certs:        optional_sections.append(f"CERTIFICATIONS:\n{_t(certs, 300)}")
    if achievements: optional_sections.append(f"ACHIEVEMENTS:\n{_t(achievements, 300)}")
    if languages:    optional_sections.append(f"LANGUAGES KNOWN: {_t(languages, 150)}")
    if volunteer:    optional_sections.append(f"VOLUNTEER EXPERIENCE:\n{_t(volunteer, 400)}")

    # ── Australia referees ──
    ref1_str = _referee_block(data.get("referee1"))
    ref2_str = _referee_block(data.get("referee2"))
    if ref1_str or ref2_str:
        lines = ["REFEREES (use ONLY these details — do NOT invent names or contacts):"]
        if ref1_str: lines.append(f"  Referee 1: {ref1_str}")
        if ref2_str: lines.append(f"  Referee 2: {ref2_str}")
        optional_sections.append("\n".join(lines))
    elif country == "Australia":
        optional_sections.append(
            'REFEREES: End the resume with one line: "Referees available upon request."'
        )

    optional_block = ("\n\n" + "\n\n".join(optional_sections)) if optional_sections else ""

    # ── Compute final section order ──
    sections = list(rules["sections"])
    if country == "India":
        if not career_obj:   sections = [s for s in sections if s != "Career Objective"]
        if not certs:        sections = [s for s in sections if s != "Certifications"]
        if not achievements: sections = [s for s in sections if s != "Achievements"]
        if not languages:    sections = [s for s in sections if s != "Languages"]
    if country == "Canada" and not volunteer:
        sections = [s for s in sections if s != "Volunteer Experience"]

    country_instructions = build_country_instructions(country, include_photo=bool(data.get("include_photo")))

    system = (
        f"You are an expert resume designer specialising in {country} job applications. "
        "Output ONLY a complete, self-contained HTML resume with ALL CSS written inline (no <style> tags, no external CSS). "
        "No markdown, no code fences, no explanations — just HTML starting with <div. "
        "Font: Georgia (serif), max-width 820px, padding 48px. "
        "CRITICAL VISUAL REQUIREMENT: Each country has a UNIQUE visual design — you MUST follow the exact colors, header style, and section heading style specified in VISUAL DESIGN. "
        "Do NOT use a generic plain-white header for every country — apply the specified header background color and styling. "
        "Every experience bullet MUST start with a strong action verb and include a measurable result. "
        "CRITICAL: Include EVERY piece of candidate data provided — do not omit any field."
    )

    user = f"""Generate a complete ATS-optimized resume strictly following the country rules below.

=== COUNTRY RULES (MUST FOLLOW) ===
{country_instructions}

=== CANDIDATE DATA (include ALL of this — do not skip any field) ===
NAME: {data.get('name', '')}
EMAIL: {data.get('email', '')}
PHONE: {data.get('phone', '')}
LOCATION: {data.get('city', '')}
LINKEDIN: {data.get('linkedin', '')}

WORK EXPERIENCE:
{_t(data.get('experience', ''), 1200)}

SKILLS:
{_t(data.get('skills', ''), 500)}

EDUCATION:
{_t(data.get('education', ''), 400)}

PROJECTS:
{_t(data.get('projects', ''), 500)}{optional_block}

JOB DESCRIPTION (tailor resume to this):
{_t(data.get('job_description', 'Not provided'), 800)}

ATS KEYWORDS TO WEAVE IN NATURALLY: {kw}

=== LAYOUT RULES ===
- Header: name (large, bold) + contact info on one line
{photo_html if photo_html else '- NO photo'}
- Section headings: uppercase, small caps, with a bottom border line
- Experience entries: job title + company (bold) | dates (right-aligned) | bullet points below
- Skills: grouped by category in a 2-column table
- Use inline CSS only. Colors: headings #1a3a5c, body text #1a1a1a, secondary #555

Return ONLY the complete HTML starting with <div."""

    return system, user


def _extract_html(raw: str) -> str:
    """Strip markdown fences if the model wraps its output."""
    text = raw.strip()
    for pattern in [r"```html\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    if text.startswith("<"):
        return text
    m = re.search(r'(<div[\s\S]*</div>)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def generate_resume(data: dict) -> dict:
    country  = data.get("country", "USA")
    keywords = extract_keywords(data.get("job_description", ""), top_n=15)
    logger.info(f"[{country}] Extracted {len(keywords)} keywords")

    system, user = _build_prompt(data, keywords)

    logger.info(f"[{country}] Calling OpenAI model: {MODEL}")

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        raw_content = response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI call failed: {e}")
        raise RuntimeError(
            f"Failed to generate resume. Check your OPENAI_API_KEY in .env\n"
            f"Error: {str(e)}"
        )

    resume_html = _extract_html(raw_content)
    ats_data    = calculate_ats_score(resume_html, keywords)
    logger.info(f"[{country}] ATS Score: {ats_data['score']} ({ats_data['grade']})")

    return {
        "resume_html":      resume_html,
        "ats_score":        ats_data["score"],
        "ats_grade":        ats_data["grade"],
        "ats_feedback":     ats_data["feedback"],
        "matched_keywords": ats_data["matched"],
        "missing_keywords": ats_data["missing"],
        "all_keywords":     keywords,
        "model_used":       MODEL,
        "country":          country,
        "flag":             get_country_rules(country)["flag"],
    }
