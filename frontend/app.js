/**
 * app.js — ATS Resume Generator
 * Three-page flow: Landing → Country Selection → Main App
 * Each country shows its own unique form sections.
 */

"use strict";

const API_BASE = "";

const LOADING_STEPS = [
  "Extracting keywords from job description...",
  "Analysing country-specific ATS rules...",
  "Rewriting experience with action verbs & metrics...",
  "Weaving ATS keywords into your resume...",
  "Polishing the final HTML layout...",
];

const COUNTRY_META = {
  USA:       { flag: "🇺🇸", label: "USA Resume",       cityPlaceholder: "San Francisco, CA",   cityLabel: "City, State" },
  Canada:    { flag: "🇨🇦", label: "Canada Resume",    cityPlaceholder: "Toronto, ON",          cityLabel: "City, Province" },
  India:     { flag: "🇮🇳", label: "India Resume",     cityPlaceholder: "Bangalore, Karnataka", cityLabel: "Full Address" },
  Australia: { flag: "🇦🇺", label: "Australia Resume", cityPlaceholder: "Sydney, NSW",          cityLabel: "City, State" },
};

// Sections to show per country (section IDs defined in HTML)
const COUNTRY_SECTIONS = {
  USA:       [],
  Canada:    ["sectionVolunteer"],
  India:     ["sectionCareerObjective", "sectionCertifications", "sectionAchievements", "sectionLanguages", "photoUploadWrap"],
  Australia: ["sectionReferees"],
};

// All optional section IDs (used to hide all before showing country-specific ones)
const ALL_OPTIONAL_SECTIONS = [
  "sectionCareerObjective",
  "sectionCertifications",
  "sectionAchievements",
  "sectionLanguages",
  "sectionVolunteer",
  "sectionReferees",
  "photoUploadWrap",
];

// ─── State ───────────────────────────────────────────────────────────────────

const state = {
  selectedCountry: "USA",
  isGenerating:    false,
  currentResume:   null,
  theme:           "dark",
  photoBase64:     null,
};

// ─── DOM ─────────────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const pages = {
  landing: $("pageLanding"),
  country: $("pageCountry"),
  app:     $("pageApp"),
};

// ─── Page navigation ──────────────────────────────────────────────────────────

function showPage(name) {
  Object.entries(pages).forEach(([key, el]) => {
    el.classList.toggle("hidden", key !== name);
  });
  window.scrollTo(0, 0);
}

// ─── Theme ───────────────────────────────────────────────────────────────────

function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("ats-theme", theme);
}

// ─── Country selection ────────────────────────────────────────────────────────

function selectCountry(country) {
  state.selectedCountry = country;
  document.querySelectorAll(".country-card").forEach(card => {
    card.classList.toggle("selected", card.dataset.country === country);
  });
}

function openApp(country) {
  selectCountry(country);
  const meta = COUNTRY_META[country];

  // Update pill
  $("selectedCountryPill").textContent = `${meta.flag} ${meta.label}`;

  // Update city label + placeholder
  $("cityLabel").textContent = meta.cityLabel;
  $("city").placeholder = meta.cityPlaceholder;

  // Hide all optional sections first
  ALL_OPTIONAL_SECTIONS.forEach(id => $( id)?.classList.add("hidden"));

  // Reset photo state when switching away from India
  if (country !== "India") {
    $("includePhotoToggle").checked = false;
    $("photoUploadBox").classList.add("hidden");
    resetPhoto();
  }

  // Show sections for this country
  (COUNTRY_SECTIONS[country] || []).forEach(id => $( id)?.classList.remove("hidden"));

  // Update empty state
  $("emptyCountryFlag").textContent = meta.flag;
  $("emptyTitle").textContent = `Ready to build your ${country} resume`;
  $("emptyDesc").textContent = `Fill in the fields and click Generate. The AI follows ${country} ATS conventions precisely.`;

  // Reset preview panel
  showPanel("empty");
  $("atsBar").style.display = "none";
  $("downloadBtn").disabled = true;
  state.currentResume = null;

  showPage("app");
}

// ─── Form data ───────────────────────────────────────────────────────────────

function val(id) {
  const el = $(id);
  return el ? el.value.trim() : "";
}

function collectFormData() {
  const country = state.selectedCountry;
  const data = {
    name:            val("fullName"),
    email:           val("email"),
    phone:           val("phone"),
    linkedin:        val("linkedin"),
    city:            val("city"),
    country,
    include_photo:   !!state.photoBase64,
    job_description: val("jobDescription"),
    experience:      val("experience"),
    skills:          val("skills"),
    education:       val("education"),
    projects:        val("projects"),
  };

  // India-specific
  if (country === "India") {
    data.career_objective = val("careerObjective");
    data.certifications   = val("certifications");
    data.achievements     = val("achievements");
    data.languages        = val("languages");
  }

  // Canada-specific
  if (country === "Canada") {
    data.volunteer = val("volunteer");
  }

  // Australia-specific: only send referee if at least name is filled
  if (country === "Australia") {
    const ref1Name = val("ref1Name");
    const ref2Name = val("ref2Name");

    data.referee1 = ref1Name ? {
      name:    ref1Name,
      title:   val("ref1Title"),
      company: val("ref1Company"),
      phone:   val("ref1Phone"),
      email:   val("ref1Email"),
    } : null;

    data.referee2 = ref2Name ? {
      name:    ref2Name,
      title:   val("ref2Title"),
      company: val("ref2Company"),
      phone:   val("ref2Phone"),
      email:   val("ref2Email"),
    } : null;
  }

  return data;
}

function validateForm(data) {
  if (!data.name)  return "Please enter your full name.";
  if (!data.email) return "Please enter your email address.";
  return null;
}

// ─── Preview panel helpers ────────────────────────────────────────────────────

function showPanel(which) {
  $("emptyState").style.display    = which === "empty"   ? "flex" : "none";
  $("loadingState").style.display  = which === "loading" ? "flex" : "none";
  $("resumeWrapper").style.display = which === "resume"  ? "flex" : "none";
}

function setIframeContent(html) {
  const doc = `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  *{box-sizing:border-box;}
  body{margin:0;padding:24px;background:white;font-family:Georgia,serif;}
  @media print{body{padding:0;}@page{margin:15mm;}}
</style>
</head><body>${html}</body></html>`;

  const frame = $("resumeFrame");
  frame.srcdoc = doc;
  frame.onload = () => {
    try {
      const h = frame.contentDocument?.body?.scrollHeight;
      if (h) frame.style.height = Math.max(1100, h + 40) + "px";
    } catch (_) { /* sandboxed */ }
  };
}

// ─── Loading animation ────────────────────────────────────────────────────────

let _loadingInterval = null;

function startLoading() {
  let i = 0;
  $("loadingSub").textContent = LOADING_STEPS[0];
  _loadingInterval = setInterval(() => {
    i = (i + 1) % LOADING_STEPS.length;
    $("loadingSub").textContent = LOADING_STEPS[i];
  }, 3000);
}

function stopLoading() {
  clearInterval(_loadingInterval);
  _loadingInterval = null;
}

// ─── Inline error ─────────────────────────────────────────────────────────────

function showError(msg) {
  let el = document.querySelector(".generate-error");
  if (!el) {
    el = document.createElement("div");
    el.className = "generate-error";
    $("generateBtn").parentElement.appendChild(el);
  }
  el.textContent = msg;
  el.style.display = "block";
  setTimeout(() => { el.style.display = "none"; }, 8000);
}

// ─── ATS score ────────────────────────────────────────────────────────────────

function displayAtsScore(result) {
  $("atsBar").style.display = "flex";

  const score = result.ats_score || 0;
  $("atsGrade").textContent    = result.ats_grade || "—";
  $("atsScoreNum").textContent = score + "%";

  const color = score >= 85 ? "#3fb950" : score >= 70 ? "#e3b341" : score >= 50 ? "#f0883e" : "#f85149";
  $("atsGrade").style.color = color;

  requestAnimationFrame(() => { $("atsProgressFill").style.width = score + "%"; });

  $("atsFeedback").textContent = result.ats_feedback || "";

  const semanticSet = new Set(result.semantic_matched || []);

  $("matchedKeywords").innerHTML = (result.matched_keywords || [])
    .map(k => semanticSet.has(k)
      ? `<span class="kw-chip semantic" title="Semantically matched">~${k}</span>`
      : `<span class="kw-chip matched">${k}</span>`)
    .join("");

  $("missingKeywords").innerHTML = (result.missing_keywords || [])
    .map(k => `<span class="kw-chip missing">${k}</span>`).join("");

  if (result.model_used) {
    const semCount = result.semantic_matched?.length || 0;
    $("atsModelInfo").textContent = semCount > 0
      ? `via ${result.model_used} · ${semCount} semantic match${semCount > 1 ? "es" : ""}`
      : `via ${result.model_used}`;
  }
}

// ─── Photo upload ─────────────────────────────────────────────────────────────

function resetPhoto() {
  state.photoBase64 = null;
  const input = $("photoInput");
  if (input) input.value = "";
  const img = $("photoPreviewImg");
  if (img) { img.src = ""; img.style.display = "none"; }
  const prompt = $("photoUploadPrompt");
  if (prompt) prompt.style.display = "flex";
  const btn = $("photoRemoveBtn");
  if (btn) btn.style.display = "none";
}

function injectPhoto(html) {
  if (!state.photoBase64) return html;
  return html.replace(
    /<div[^>]*id="resume-photo-placeholder"[^>]*>[\s\S]*?<\/div>/i,
    `<img src="${state.photoBase64}" style="width:90px;height:110px;object-fit:cover;border-radius:4px;border:1px solid #ddd;flex-shrink:0;" alt="Profile Photo">`
  );
}

// ─── Generate resume ──────────────────────────────────────────────────────────

async function generateResume() {
  if (state.isGenerating) return;

  const data = collectFormData();
  const err  = validateForm(data);
  if (err) { showError(err); return; }

  state.isGenerating = true;
  const genBtn = $("generateBtn");
  genBtn.disabled = true;
  genBtn.querySelector(".btn-text").textContent = "Generating...";
  $("downloadBtn").disabled = true;
  $("atsBar").style.display = "none";

  showPanel("loading");
  startLoading();

  try {
    const res = await fetch(`${API_BASE}/generate-resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    const result = await res.json();
    if (!res.ok) throw new Error(result.error || `Server error ${res.status}`);

    const processedHtml = injectPhoto(result.resume_html);
    state.currentResume = { ...result, resume_html: processedHtml };

    setIframeContent(processedHtml);
    showPanel("resume");
    displayAtsScore(result);
    $("downloadBtn").disabled = false;

  } catch (e) {
    showPanel("empty");
    showError("Generation failed: " + (
      e.message.includes("fetch") ? "Cannot reach backend. Is Flask running on port 5001?" : e.message
    ));
  } finally {
    state.isGenerating = false;
    genBtn.disabled = false;
    genBtn.querySelector(".btn-text").textContent = "Generate ATS Resume";
    stopLoading();
  }
}

// ─── PDF download ─────────────────────────────────────────────────────────────

async function downloadPDF() {
  if (!state.currentResume?.resume_html) return;

  const name     = (val("fullName") || "candidate").replace(/\s+/g, "_");
  const country  = state.currentResume.country || state.selectedCountry;
  const filename = `resume_${name}_${country}.pdf`;

  try {
    const res = await fetch(`${API_BASE}/download-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ html: state.currentResume.resume_html, filename }),
    });
    if (res.ok) {
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
      return;
    }
  } catch (_) { /* fall through to print */ }

  // Browser print fallback
  const win = window.open("", "_blank", "width=900,height=1200");
  win.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{margin:0;padding:20px;font-family:Georgia,serif;}@page{margin:15mm;size:A4;}</style>
</head><body>${state.currentResume.resume_html}</body></html>`);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 500);
}

// ─── Status check ─────────────────────────────────────────────────────────────

async function checkStatus() {
  const dot  = $("statusDot");
  const text = $("statusText");
  dot.className    = "status-dot checking";
  text.textContent = "Checking...";
  try {
    const res  = await fetch(`${API_BASE}/check-openai`, { signal: AbortSignal.timeout(5000) });
    const data = await res.json();
    if (data.available) {
      dot.className    = "status-dot online";
      text.textContent = `AI ready · ${data.model}`;
    } else {
      dot.className    = "status-dot offline";
      text.textContent = "API key missing";
    }
  } catch {
    dot.className    = "status-dot offline";
    text.textContent = "Backend offline";
  }
}

// ─── Events ──────────────────────────────────────────────────────────────────

function initEvents() {
  $("btnStart").addEventListener("click", () => showPage("country"));
  $("btnBackToLanding").addEventListener("click", () => showPage("landing"));
  $("btnBackToCountry").addEventListener("click", () => showPage("country"));

  $("themeToggle").addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark");
  });

  // Country card click = highlight
  document.querySelectorAll(".country-card").forEach(card => {
    card.addEventListener("click", () => selectCountry(card.dataset.country));
  });

  // "Select & Continue" button
  document.querySelectorAll(".btn-select-country").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openApp(btn.closest(".country-card").dataset.country);
    });
  });

  // India photo toggle
  $("includePhotoToggle").addEventListener("change", (e) => {
    if (e.target.checked) {
      $("photoUploadBox").classList.remove("hidden");
    } else {
      $("photoUploadBox").classList.add("hidden");
      resetPhoto();
    }
  });

  $("photoInput").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { showError("Photo must be under 2MB."); return; }
    const reader = new FileReader();
    reader.onload = (ev) => {
      state.photoBase64 = ev.target.result;
      const img = $("photoPreviewImg");
      img.src = state.photoBase64;
      img.style.display = "block";
      $("photoUploadPrompt").style.display = "none";
      $("photoRemoveBtn").style.display = "inline-block";
    };
    reader.readAsDataURL(file);
  });

  $("photoRemoveBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    resetPhoto();
  });

  $("photoUploadBox").addEventListener("click", (e) => {
    if (e.target !== $("photoRemoveBtn")) $("photoInput").click();
  });

$("generateBtn").addEventListener("click", generateResume);
  $("downloadBtn").addEventListener("click", downloadPDF);

  // Ctrl/Cmd + Enter shortcut
  document.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      if (!pages.app.classList.contains("hidden")) generateResume();
    }
  });
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────

function init() {
  applyTheme(localStorage.getItem("ats-theme") === "light" ? "light" : "dark");
  showPage("landing");
  initEvents();
  checkStatus();
  setInterval(checkStatus, 30_000);
}

document.readyState === "loading"
  ? document.addEventListener("DOMContentLoaded", init)
  : init();
