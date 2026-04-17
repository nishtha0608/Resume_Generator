import os
import re
import logging

from openai import OpenAI
from dotenv import load_dotenv

from ats_rules import (
    extract_keywords,
    calculate_ats_score,
    calculate_ats_score_semantic,
    get_country_rules,
    build_country_instructions,
)

load_dotenv()
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o-mini"

# Stable ID for photo injection — never change this string
_PHOTO_ID = "resume-photo-placeholder"
_PHOTO_HTML = (
    f'<div id="{_PHOTO_ID}" '
    'style="width:90px;height:110px;border:1px solid #ccc;background:#f5f5f5;'
    'display:flex;align-items:center;justify-content:center;font-size:10px;'
    'color:#aaa;text-align:center;flex-shrink:0;margin-left:20px;">'
    'Photo<br>Here</div>'
)


# ---------------------------------------------------------------------------
# Skills HTML builder — Python builds the table, AI copies it verbatim
# ---------------------------------------------------------------------------

def _build_skills_html(skills_text: str) -> str:
    """
    Parse user skills text into a ready-made HTML table.
    Supports:
      - Multi-line: one "Category: Skill1, Skill2" per line
      - Single-line: "Cat1: A, B, Cat2: C, D" — splits on inline Category: patterns
    """
    lines = [ln.strip() for ln in skills_text.strip().splitlines() if ln.strip()]
    if not lines:
        return ""

    rows = []
    for line in lines:
        # Split on ", Word(s):" patterns to handle inline categories
        parts = re.split(r',\s*(?=[A-Za-z][A-Za-z0-9 /&+]*?:\s)', line)
        if len(parts) > 1:
            for part in parts:
                if ":" in part:
                    cat, _, skills_part = part.partition(":")
                    rows.append((cat.strip(), skills_part.strip()))
                else:
                    rows.append(("", part.strip()))
        elif ":" in line:
            cat, _, skills_part = line.partition(":")
            rows.append((cat.strip(), skills_part.strip()))
        else:
            rows.append(("", line.strip()))

    row_html = "".join(
        f'<tr>'
        f'<td style="font-weight:bold;width:30%;padding:4px 8px;vertical-align:top;font-size:11px;">{cat}</td>'
        f'<td style="padding:4px 8px;font-size:11px;">{skills}</td>'
        f'</tr>'
        for cat, skills in rows
    )
    return (
        '<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
        + row_html
        + '</table>'
    )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _t(text: str, max_chars: int) -> str:
    if not text:
        return ""
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _clean(text: str) -> str:
    """Strip trailing whitespace and collapse 3+ blank lines to 1."""
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned, blanks = [], 0
    for ln in lines:
        if ln == "":
            blanks += 1
            if blanks <= 1:
                cleaned.append(ln)
        else:
            blanks = 0
            cleaned.append(ln)
    return "\n".join(cleaned).strip()


def _referee_block(ref) -> str:
    if not ref or not ref.get("name"):
        return ""
    parts = [ref["name"]]
    if ref.get("title"):   parts.append(ref["title"])
    if ref.get("company"): parts.append(ref["company"])
    contact = " | ".join(filter(None, [ref.get("phone", ""), ref.get("email", "")]))
    if contact: parts.append(contact)
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(data: dict, keywords: list) -> tuple:
    country = data.get("country", "USA")
    rules   = get_country_rules(country)
    kw      = ", ".join(keywords[:10]) if keywords else ""

    # ── Prepare all field values upfront ──
    experience_clean = _t(_clean(data.get("experience",        "")), 1200)
    skills_clean     = _t(_clean(data.get("skills",            "")), 500)
    education_clean  = _t(_clean(data.get("education",         "")), 400)
    projects_clean   = _t(_clean(data.get("projects",          "")), 500)
    career_obj       = _t(_clean(data.get("career_objective",  "")), 400)
    certs            = _t(_clean(data.get("certifications",    "")), 300)
    achievements     = _t(_clean(data.get("achievements",      "")), 300)
    languages        = _t(_clean(data.get("languages",         "")), 150)
    volunteer        = _t(_clean(data.get("volunteer",         "")), 400)

    # ── Compute active sections: Python decides, AI follows ──
    # Start from the country's default order, then remove any section with no data
    active_sections = list(rules["sections"])

    def _drop(name):
        nonlocal active_sections
        active_sections = [s for s in active_sections if s != name]

    if not career_obj:       _drop("Career Objective"); _drop("Summary")
    if not experience_clean: _drop("Experience")
    if not skills_clean:     _drop("Skills")
    if not education_clean:  _drop("Education")
    if not projects_clean:   _drop("Projects")
    if not certs:            _drop("Certifications")
    if not achievements:     _drop("Achievements")
    if not languages:        _drop("Languages")
    if not volunteer:        _drop("Volunteer Experience")

    # Photo
    show_photo = bool(data.get("include_photo")) and rules["photo"]

    # Australia referees
    ref1_str = _referee_block(data.get("referee1"))
    ref2_str = _referee_block(data.get("referee2"))
    has_referees = bool(ref1_str or ref2_str) or (country == "Australia")
    if not has_referees:
        _drop("Referees")

    # ── Contact line ──
    contact_parts = []
    if data.get("email"):    contact_parts.append(data["email"])
    if data.get("phone"):    contact_parts.append(data["phone"])
    if data.get("city"):     contact_parts.append(data["city"])
    if data.get("linkedin"): contact_parts.append(data["linkedin"])
    contact_line = " · ".join(contact_parts)

    # ── Build candidate data block — only present fields, in clear labeled blocks ──
    data_parts = []

    if career_obj:
        label = "CAREER OBJECTIVE" if country == "India" else "PROFESSIONAL SUMMARY"
        data_parts.append(f"{label}:\n{career_obj}")

    if experience_clean:
        data_parts.append(f"WORK EXPERIENCE:\n{experience_clean}")

    if skills_clean:
        skills_html = _build_skills_html(skills_clean)
        data_parts.append(
            "SKILLS — copy this EXACT HTML block verbatim into the Skills section. "
            "Do NOT add, remove, or change any word. Do NOT inject JD keywords here:\n"
            + skills_html
        )

    if education_clean:
        data_parts.append(f"EDUCATION:\n{education_clean}")

    if projects_clean:
        data_parts.append(f"PROJECTS:\n{projects_clean}")

    if certs:        data_parts.append(f"CERTIFICATIONS:\n{certs}")
    if achievements: data_parts.append(f"ACHIEVEMENTS:\n{achievements}")
    if languages:    data_parts.append(f"LANGUAGES: {languages}")
    if volunteer:    data_parts.append(f"VOLUNTEER EXPERIENCE:\n{volunteer}")

    # Referees
    if ref1_str or ref2_str:
        ref_lines = ["REFEREES [use ONLY these — do NOT invent]:"]
        if ref1_str: ref_lines.append(f"  1: {ref1_str}")
        if ref2_str: ref_lines.append(f"  2: {ref2_str}")
        data_parts.append("\n".join(ref_lines))
    elif country == "Australia":
        data_parts.append('REFEREES: "Referees available upon request."')

    data_block = "\n\n".join(data_parts)

    # ── JD + keywords ──
    jd_text = _t(data.get("job_description", ""), 800)
    jd_block = f"JOB DESCRIPTION (tailor tone/bullets — do NOT copy JD skills to Skills section):\n{jd_text}" if jd_text else ""
    kw_block = (
        f"KEYWORDS — weave into WORK EXPERIENCE and PROJECTS bullets ONLY. "
        f"Never add to Skills, Education, header, or any other section:\n{kw}"
    ) if kw else ""

    # ── Photo layout instruction ──
    if show_photo:
        photo_block = (
            f"PHOTO: Header must be a flex container: "
            f'<div style="display:flex;align-items:flex-start;justify-content:space-between;"> '
            f"Place name+contact in a <div> on the LEFT. "
            f"Copy this EXACT HTML on the RIGHT (do NOT use float, do NOT change the id):\n"
            f"{_PHOTO_HTML}"
        )
    else:
        photo_block = "NO PHOTO — do not add any photo placeholder or image."

    # ── Country design instructions ──
    country_instructions = build_country_instructions(country, include_photo=show_photo)


    # ── System prompt ──
    system = (
        f"You are an expert resume designer for {country} job applications. "
        "Output ONLY a complete, self-contained HTML resume with ALL CSS inline (no <style> tags). "
        "Start with <div. No markdown, no code fences, no commentary.\n\n"

        "ABSOLUTE RULES — never break these:\n"
        "1. Render ONLY the sections listed in ACTIVE SECTIONS, in that exact order.\n"
        "2. If a section is NOT in ACTIVE SECTIONS, do not render its heading or any content.\n"
        "3. Never fabricate: no invented jobs, companies, degrees, projects, skills, or facts.\n"
        "4. SKILLS are LOCKED — render exactly what is listed, no additions, no substitutions.\n"
        "5. Keywords go ONLY into Experience/Projects bullet text — never into Skills.\n"
        f"6. CONTENT DENSITY — strictly follow the CONTENT DENSITY rules in COUNTRY DESIGN. "
        f"This resume targets {rules['page_limit']}. "
        "A 1-page resume must be ultra-concise with tight spacing; "
        "a 2–3 page resume must be thorough and detailed.\n\n"

        "TYPOGRAPHY:\n"
        "  • Wrapper: font-family Georgia,'Times New Roman',serif; max-width:820px; margin:0 auto; "
        "padding:40px 48px; color:#1a1a1a; line-height:1.55; font-size:11.5px\n"
        "  • Name: font-size:30px; font-weight:bold; letter-spacing:0.5px\n"
        "  • Contact: font-size:10.5px; letter-spacing:0.2px\n"
        "  • Section headings: font-size:12px; font-weight:bold; text-transform:uppercase; letter-spacing:1.8px\n"
        "  • Job title: font-size:12.5px; font-weight:bold\n"
        "  • Company/dates: font-size:11px\n"
        "  • Bullets: font-size:11.5px; line-height:1.6; margin:3px 0; padding-left:16px\n"
        "  • Skills table cells: font-size:11px; padding:3px 6px\n\n"

        "VISUAL: Every country has a unique design. Follow the exact colors, header background, "
        "and section heading style in COUNTRY DESIGN. Do not use a plain white header "
        f"for {country} — apply the specified background color and typography."
    )

    # ── User prompt ──
    user = f"""=== COUNTRY DESIGN ===
{country_instructions}

=== ACTIVE SECTIONS — render EXACTLY these in this order, nothing else ===
{' → '.join(active_sections)}

=== CANDIDATE DATA ===
NAME: {data.get('name', '')}
CONTACT: {contact_line}

{data_block}

=== TAILORING ===
{jd_block}
{kw_block}

=== LAYOUT ===
{photo_block}
- Section headings: uppercase, bold, with a 2px solid bottom border in the accent color; margin-bottom:8px
- Experience entry format: Job Title (bold) at Company (bold) | Dates (right-aligned); then bullet points
- Every bullet starts with a strong action verb and includes a measurable result
- Skills: the HTML table is already provided in CANDIDATE DATA — copy it verbatim, no changes.
- Inline CSS only. No <style> tags.

Return ONLY the complete HTML starting with <div."""

    return system, user


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

def _extract_html(raw: str) -> str:
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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
            f"Failed to generate resume. Check your OPENAI_API_KEY in .env\nError: {str(e)}"
        )

    resume_html = _extract_html(raw_content)

    # Score against original user content — not AI HTML (AI always embeds all keywords)
    original_content = " ".join(filter(None, [
        data.get("experience",        ""),
        data.get("skills",            ""),
        data.get("education",         ""),
        data.get("projects",          ""),
        data.get("career_objective",  ""),
        data.get("certifications",    ""),
        data.get("achievements",      ""),
    ]))

    if data.get("job_description", "").strip():
        try:
            ats_data = calculate_ats_score_semantic(original_content, keywords, client)
            logger.info(
                f"[{country}] Semantic ATS: {ats_data['score']} ({ats_data['grade']}) "
                f"| semantic_matched={len(ats_data['semantic_matched'])}"
            )
        except Exception as e:
            logger.warning(f"[{country}] Semantic scoring failed, falling back: {e}")
            ats_data = calculate_ats_score(original_content, keywords)
    else:
        ats_data = calculate_ats_score(original_content, keywords)

    logger.info(f"[{country}] ATS Score: {ats_data['score']} ({ats_data['grade']})")

    return {
        "resume_html":      resume_html,
        "ats_score":        ats_data["score"],
        "ats_grade":        ats_data["grade"],
        "ats_feedback":     ats_data["feedback"],
        "matched_keywords": ats_data["matched"],
        "missing_keywords": ats_data["missing"],
        "semantic_matched": ats_data.get("semantic_matched", []),
        "all_keywords":     keywords,
        "model_used":       MODEL,
        "country":          country,
        "flag":             get_country_rules(country)["flag"],
    }

