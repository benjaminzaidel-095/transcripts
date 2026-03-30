/**
 * IVD Transcript Tool — frontend logic
 *
 * API_ENDPOINT: Render backend URL.
 * While empty the form shows the CLI equivalent instead.
 */
const API_ENDPOINT = "https://transcripts-f993.onrender.com/process";
const WAKE_URL     = API_ENDPOINT.replace("/process", "/");

// ── Wake up Render on page load (free tier cold-starts in ~30-60s) ────────────
if (API_ENDPOINT) {
  fetch(WAKE_URL, { method: "GET" }).catch(() => {});
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const form            = document.getElementById("transcriptForm");
const fileInput       = document.getElementById("transcriptFile");
const fileDrop        = document.getElementById("fileDrop");
const fileLabel       = document.getElementById("fileDropLabel");
const pasteArea       = document.getElementById("transcriptText");
const submitBtn       = document.getElementById("submitBtn");
const btnText         = submitBtn.querySelector(".btn-text");
const btnSpinner      = submitBtn.querySelector(".btn-spinner");
const stageLabel      = document.getElementById("stageLabel");
const statusBox       = document.getElementById("statusBox");
const cliPanel        = document.getElementById("cliPanel");
const cliBlock        = document.getElementById("cliBlock");
const downloadPanel   = document.getElementById("downloadPanel");
const dlTranscript    = document.getElementById("dlTranscript");
const dlNotes         = document.getElementById("dlNotes");

// CSV / interviewee refs
const csvDrop           = document.getElementById("csvDrop");
const csvFileInput      = document.getElementById("csvFile");
const csvDropLabel      = document.getElementById("csvDropLabel");
const intervieweeGroup  = document.getElementById("intervieweeGroup");
const intervieweeSelect = document.getElementById("intervieweeSelect");

// Auto-fillable fields
const AUTOFILL_IDS = ["role", "setting", "location", "interviewDate", "interviewNum"];

// ── Transcript file drop UX ───────────────────────────────────────────────────
fileDrop.addEventListener("dragover", e => { e.preventDefault(); fileDrop.classList.add("drag-over"); });
fileDrop.addEventListener("dragleave", () => fileDrop.classList.remove("drag-over"));
fileDrop.addEventListener("drop", e => {
  e.preventDefault();
  fileDrop.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) setTranscriptFile(file);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setTranscriptFile(fileInput.files[0]);
});

function setTranscriptFile(file) {
  fileDrop.classList.add("has-file");
  fileLabel.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M5 10l4 4 6-7" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span>${escHtml(file.name)}</span>`;
  hideStatus();
}

// ── CSV drop zone UX ──────────────────────────────────────────────────────────
csvDrop.addEventListener("dragover", e => { e.preventDefault(); csvDrop.classList.add("drag-over"); });
csvDrop.addEventListener("dragleave", () => csvDrop.classList.remove("drag-over"));
csvDrop.addEventListener("drop", e => {
  e.preventDefault();
  csvDrop.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) loadCSV(file);
});
csvFileInput.addEventListener("change", () => {
  if (csvFileInput.files[0]) loadCSV(csvFileInput.files[0]);
});

function loadCSV(file) {
  if (!file.name.endsWith(".csv")) {
    showStatus("Please drop a .csv file for the interviewee list.", "error");
    return;
  }
  const reader = new FileReader();
  reader.onload = e => {
    const rows = parseCSV(e.target.result);
    const contacts = rows.filter(r => (r["First name"] || "").trim() !== "");
    if (!contacts.length) {
      showStatus("No valid contacts found in CSV. Check column headers.", "error");
      return;
    }
    populateIntervieweeDropdown(contacts);
    csvDrop.classList.add("has-file");
    csvDropLabel.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M5 10l4 4 6-7" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>${escHtml(file.name)} — ${contacts.length} contacts loaded</span>`;
  };
  reader.readAsText(file);
}

// ── CSV parser (no external libraries) ───────────────────────────────────────
function parseCSV(text) {
  const lines = text.split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = splitCSVLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const vals = splitCSVLine(line);
    const row = {};
    headers.forEach((h, idx) => { row[h.trim()] = (vals[idx] || "").trim(); });
    rows.push(row);
  }
  return rows;
}

function splitCSVLine(line) {
  const fields = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { field += '"'; i++; }
      else { inQuotes = !inQuotes; }
    } else if (ch === "," && !inQuotes) {
      fields.push(field); field = "";
    } else {
      field += ch;
    }
  }
  fields.push(field);
  return fields;
}

// ── Interviewee dropdown ──────────────────────────────────────────────────────
function populateIntervieweeDropdown(contacts) {
  intervieweeSelect.innerHTML = '<option value="">— choose interviewee —</option>';

  contacts.forEach((c, idx) => {
    const ivNum   = (c["IV#"] || "").trim();
    const first   = (c["First name"] || "").trim();
    const last    = (c["Last name"] || "").trim();
    const role    = (c["Role"] || "").trim();
    const setting = (c["Setting"] || "").trim();
    const label   = `${ivNum ? "IV" + ivNum + " — " : ""}${first} ${last} (${role}, ${setting})`;
    const opt = document.createElement("option");
    opt.value = idx;
    opt.textContent = label;
    intervieweeSelect.appendChild(opt);
  });

  const sep = document.createElement("option");
  sep.disabled = true;
  sep.textContent = "──────────────────────";
  intervieweeSelect.appendChild(sep);

  const other = document.createElement("option");
  other.value = "other";
  other.textContent = "Other / Non-RSS Interview";
  other.style.fontStyle = "italic";
  intervieweeSelect.appendChild(other);

  intervieweeGroup.hidden = false;
  intervieweeSelect._contacts = contacts;
}

intervieweeSelect.addEventListener("change", () => {
  const val = intervieweeSelect.value;
  if (val === "other" || val === "") { clearAutofill(); return; }
  const contacts = intervieweeSelect._contacts || [];
  const c = contacts[parseInt(val, 10)];
  if (!c) return;
  const ivNum = (c["IV#"] || "").trim();
  setAutofill("interviewNum", ivNum ? "IV" + ivNum : "");
  setAutofill("role",         (c["Role"] || "").trim());
  setAutofill("setting",      (c["Setting"] || "").trim());
  setAutofill("location",     (c["Geographies"] || "").trim());
  setAutofill("interviewDate", normalizeDate(c["Date"] || ""));
});

function setAutofill(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.value = value;
  el.classList.add("input--autofilled");
  el.addEventListener("input", () => el.classList.remove("input--autofilled"), { once: true });
}

function clearAutofill() {
  AUTOFILL_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = "";
    el.classList.remove("input--autofilled");
  });
}

// ── Date normalizer ───────────────────────────────────────────────────────────
function normalizeDate(str) {
  if (!str) return "";
  str = str.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) return str;
  const m = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
  const d = new Date(str);
  if (!isNaN(d)) return d.toISOString().slice(0, 10);
  return "";
}

// ── Pipeline steps ────────────────────────────────────────────────────────────
const PIPELINE_STEPS = [
  { id: "parsing",  label: "Parse Transcript", btnLabel: "Parsing transcript…",  pct: 5  },
  { id: "cleaning", label: "Clean Transcript", btnLabel: "Cleaning transcript…", pct: 15 },
  { id: "notes",    label: "Generate Notes",   btnLabel: "Generating notes…",    pct: 45 },
  { id: "building", label: "Build Documents",  btnLabel: "Building documents…",  pct: 88 },
];

// ── Progress panel state ──────────────────────────────────────────────────────
let _stepStartTimes  = {};
let _currentStep     = null;
let _processStart    = null;
let _elapsedTimer    = null;

function initProgressPanel() {
  _stepStartTimes = {};
  _currentStep    = null;
  _processStart   = Date.now();

  PIPELINE_STEPS.forEach(s => _setStepState(s.id, "pending", null));
  _setBar(0);

  const elapsed = document.getElementById("progElapsed");
  if (elapsed) elapsed.textContent = "—";

  clearInterval(_elapsedTimer);
  _elapsedTimer = setInterval(_tickElapsed, 500);
}

function _tickElapsed() {
  if (!_processStart) return;
  const totalSec = ((Date.now() - _processStart) / 1000).toFixed(1);
  const el = document.getElementById("progElapsed");
  if (el) el.textContent = `${totalSec}s elapsed`;

  // Live-update the active step's running time
  if (_currentStep && _stepStartTimes[_currentStep]) {
    const stepSec = ((Date.now() - _stepStartTimes[_currentStep]) / 1000).toFixed(1);
    const meta = document.getElementById(`prog-meta-${_currentStep}`);
    if (meta) meta.textContent = `${stepSec}s`;
  }
}

function _setStepState(stepId, state, duration) {
  const el = document.getElementById(`step-${stepId}`);
  if (!el) return;
  el.className = `prog-step prog-step--${state}`;
  const meta = document.getElementById(`prog-meta-${stepId}`);
  if (!meta) return;
  if (state === "pending")               meta.textContent = "—";
  else if (state === "done" && duration != null) meta.textContent = `${duration.toFixed(1)}s`;
  else if (state === "error")            meta.textContent = "failed";
}

function _setBar(pct) {
  const fill  = document.getElementById("progBarFill");
  const label = document.getElementById("progPct");
  if (fill)  fill.style.width    = `${pct}%`;
  if (label) label.textContent   = `${pct}%`;
}

function _activateStep(stepId) {
  // Complete the previously active step
  if (_currentStep) {
    const dur = (Date.now() - _stepStartTimes[_currentStep]) / 1000;
    _setStepState(_currentStep, "done", dur);
  }
  _currentStep = stepId;
  _stepStartTimes[stepId] = Date.now();
  _setStepState(stepId, "active", null);

  const step = PIPELINE_STEPS.find(s => s.id === stepId);
  if (step) {
    if (stageLabel) stageLabel.textContent = step.btnLabel;
    _setBar(step.pct);
  }
}

function showProgressPanel() {
  document.getElementById("processLayout").classList.add("is-active");
  document.getElementById("progressPanel").hidden = false;
}

// ── SSE event handler ─────────────────────────────────────────────────────────
function handleSSEEvent(data) {
  if (data.event === "stage") {
    _activateStep(data.stage);

  } else if (data.event === "done") {
    // Mark last active step done
    if (_currentStep) {
      const dur = (Date.now() - _stepStartTimes[_currentStep]) / 1000;
      _setStepState(_currentStep, "done", dur);
      _currentStep = null;
    }
    _setBar(100);
    clearInterval(_elapsedTimer);
    const totalSec = ((Date.now() - _processStart) / 1000).toFixed(1);
    const elapsed = document.getElementById("progElapsed");
    if (elapsed) elapsed.textContent = `Done in ${totalSec}s`;

    // Wire up download buttons
    dlTranscript.onclick = () =>
      downloadB64(data.transcript_b64, data.transcript_filename,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    dlNotes.onclick = () =>
      downloadB64(data.notes_b64, data.notes_filename,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document");

    downloadPanel.hidden = false;
    showStatus("✓ Processing complete — your files are ready below.", "success");

  } else if (data.event === "error") {
    if (_currentStep) {
      _setStepState(_currentStep, "error", null);
      _currentStep = null;
    }
    clearInterval(_elapsedTimer);
    showStatus(`Error: ${data.detail}`, "error");
  }
}

// ── Form submit ───────────────────────────────────────────────────────────────
form.addEventListener("submit", async e => {
  e.preventDefault();

  const file      = fileInput.files[0];
  const pasteText = pasteArea.value.trim();
  const role      = val("role");
  const setting   = val("setting");
  const location  = val("location");
  const date      = val("interviewDate");
  const num       = val("interviewNum");

  if (!file && !pasteText) return showStatus("Please upload a file or paste transcript text.", "error");
  if (!role)     return showStatus("Interviewee Role is required.", "error");
  if (!setting)  return showStatus("Setting is required.", "error");
  if (!location) return showStatus("Location is required.", "error");

  setLoading(true);
  downloadPanel.hidden = true;
  cliPanel.hidden = true;
  hideStatus();

  if (API_ENDPOINT) {
    const fd = new FormData();
    if (file) {
      fd.append("transcript", file);
    } else {
      fd.append("transcript", new Blob([pasteText], { type: "text/plain" }), "pasted_transcript.txt");
    }
    fd.append("role",     role);
    fd.append("setting",  setting);
    fd.append("location", location);
    if (date) fd.append("date", date);
    if (num)  fd.append("interview_num", num);

    showProgressPanel();
    initProgressPanel();

    try {
      const res = await fetch(API_ENDPOINT, { method: "POST", body: fd });
      if (!res.ok) {
        const msg = await res.text().catch(() => res.statusText);
        throw new Error(msg || `HTTP ${res.status}`);
      }

      // Stream SSE events from the server
      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      let buf      = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let pos;
        while ((pos = buf.indexOf("\n\n")) !== -1) {
          const chunk = buf.slice(0, pos).trim();
          buf = buf.slice(pos + 2);
          if (chunk.startsWith("data: ")) {
            try { handleSSEEvent(JSON.parse(chunk.slice(6))); } catch (_) {}
          }
        }
      }

    } catch (err) {
      clearInterval(_elapsedTimer);
      if (_currentStep) { _setStepState(_currentStep, "error", null); _currentStep = null; }
      showStatus(`Error: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }

  } else {
    // ── CLI fallback ──────────────────────────────────────────────────────────
    const src      = file ? file.name : "pasted_transcript.txt";
    const dateFlag = date ? `  --date "${date}"` : "";
    const numFlag  = num  ? `  --interview-num "${num}"` : "";
    const cmd = [
      `python ivd_clean.py \\`,
      `  --transcript "${src}" \\`,
      `  --role "${role}" \\`,
      `  --setting "${setting}" \\`,
      `  --location "${location}"` + (dateFlag || numFlag ? " \\" : ""),
      dateFlag ? (numFlag ? dateFlag + " \\" : dateFlag) : null,
      numFlag  ? numFlag : null,
    ].filter(l => l !== null).join("\n");
    cliBlock.textContent = cmd;
    cliPanel.hidden = false;
    showStatus("API not configured yet — copy the command below to run locally.", "info");
    setLoading(false);
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function val(id) { return document.getElementById(id).value.trim(); }
function escHtml(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function setLoading(on) {
  submitBtn.disabled = on;
  btnText.hidden     = on;
  btnSpinner.hidden  = !on;
  if (on && stageLabel) stageLabel.textContent = "Processing…";
}

function showStatus(msg, type = "info") {
  statusBox.textContent = msg;
  statusBox.className   = `status-box ${type}`;
  statusBox.hidden      = false;
}

function hideStatus() {
  statusBox.hidden    = true;
  statusBox.className = "status-box";
}

function downloadB64(b64, filename, mimeType) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const blob  = new Blob([bytes], { type: mimeType });
  const url   = URL.createObjectURL(blob);
  const a     = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function copyCmd() {
  navigator.clipboard.writeText(cliBlock.textContent)
    .then(() => {
      const btn = document.getElementById("copyBtn");
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = "Copy"; }, 1800);
    });
}
