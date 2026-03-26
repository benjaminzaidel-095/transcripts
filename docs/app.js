/**
 * IVD Transcript Tool — frontend logic
 *
 * API_ENDPOINT: Render backend URL. Set after deploying server.py to Render.
 * While empty, the form builds and shows the equivalent CLI command instead.
 */
const API_ENDPOINT = "https://transcripts-f993.onrender.com/process";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const form           = document.getElementById("transcriptForm");
const fileInput      = document.getElementById("transcriptFile");
const fileDrop       = document.getElementById("fileDrop");
const fileLabel      = document.getElementById("fileDropLabel");
const pasteArea      = document.getElementById("transcriptText");
const submitBtn      = document.getElementById("submitBtn");
const btnText        = submitBtn.querySelector(".btn-text");
const btnSpinner     = submitBtn.querySelector(".btn-spinner");
const statusBox      = document.getElementById("statusBox");
const cliPanel       = document.getElementById("cliPanel");
const cliBlock       = document.getElementById("cliBlock");

// CSV / interviewee refs
const csvDrop        = document.getElementById("csvDrop");
const csvFileInput   = document.getElementById("csvFile");
const csvDropLabel   = document.getElementById("csvDropLabel");
const intervieweeGroup = document.getElementById("intervieweeGroup");
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
  // Reset
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

  // Separator + Other option
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

  // Store contacts on the select element for access in handler
  intervieweeSelect._contacts = contacts;
}

intervieweeSelect.addEventListener("change", () => {
  const val = intervieweeSelect.value;
  if (val === "other" || val === "") {
    clearAutofill();
    return;
  }
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
  // Remove autofill indicator on manual edit
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
  // Already YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) return str;
  // MM/DD/YYYY or M/D/YYYY
  const m = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
  // Try browser Date parsing as last resort
  const d = new Date(str);
  if (!isNaN(d)) return d.toISOString().slice(0, 10);
  return "";
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

  // Validation
  if (!file && !pasteText) return showStatus("Please upload a .txt file or paste transcript text.", "error");
  if (!role)     return showStatus("Interviewee Role is required.", "error");
  if (!setting)  return showStatus("Setting is required.", "error");
  if (!location) return showStatus("Location is required.", "error");

  setLoading(true);
  hideStatus();
  cliPanel.hidden = true;

  if (API_ENDPOINT) {
    // ── Live API mode ────────────────────────────────────────────────────────
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

    try {
      const res = await fetch(API_ENDPOINT, { method: "POST", body: fd });
      if (!res.ok) {
        const msg = await res.text().catch(() => res.statusText);
        throw new Error(msg || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const filename = extractFilename(res) || `${num || "IV"}_Cleaned.docx`;
      downloadBlob(blob, filename);
      showStatus(`✓ Done — ${filename} downloaded.`, "success");
    } catch (err) {
      showStatus(`Error: ${err.message}`, "error");
    }

  } else {
    // ── CLI fallback mode ────────────────────────────────────────────────────
    const src       = file ? file.name : "pasted_transcript.txt";
    const dateFlag  = date ? `  --date "${date}"` : "";
    const numFlag   = num  ? `  --interview-num "${num}"` : "";
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
  }

  setLoading(false);
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function val(id) { return document.getElementById(id).value.trim(); }
function escHtml(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function setLoading(on) {
  submitBtn.disabled = on;
  btnText.hidden     = on;
  btnSpinner.hidden  = !on;
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

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function extractFilename(res) {
  const cd = res.headers.get("Content-Disposition") || "";
  const m  = cd.match(/filename="?([^";\n]+)"?/);
  return m ? m[1] : null;
}

function copyCmd() {
  navigator.clipboard.writeText(cliBlock.textContent)
    .then(() => {
      const btn = document.getElementById("copyBtn");
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = "Copy"; }, 1800);
    });
}
