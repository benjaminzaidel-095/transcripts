/**
 * IVD Transcript Tool — frontend logic
 *
 * API_ENDPOINT: Render backend URL. Set after deploying server.py to Render.
 * While empty, the form builds and shows the equivalent CLI command instead.
 */
const API_ENDPOINT = "https://transcripts-f993.onrender.com/process";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const form        = document.getElementById("transcriptForm");
const fileInput   = document.getElementById("transcriptFile");
const fileDrop    = document.getElementById("fileDrop");
const fileLabel   = document.getElementById("fileDropLabel");
const submitBtn   = document.getElementById("submitBtn");
const btnText     = submitBtn.querySelector(".btn-text");
const btnSpinner  = submitBtn.querySelector(".btn-spinner");
const statusBox   = document.getElementById("statusBox");
const cliPanel    = document.getElementById("cliPanel");
const cliBlock    = document.getElementById("cliBlock");

// ── File drop UX ─────────────────────────────────────────────────────────────
fileDrop.addEventListener("dragover", e => { e.preventDefault(); fileDrop.classList.add("drag-over"); });
fileDrop.addEventListener("dragleave",  () => fileDrop.classList.remove("drag-over"));
fileDrop.addEventListener("drop", e => {
  e.preventDefault();
  fileDrop.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  if (!file.name.endsWith(".txt")) {
    showStatus("Please upload a .txt file (Granola export).", "error");
    return;
  }
  fileDrop.classList.add("has-file");
  fileLabel.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M5 10l4 4 6-7" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span>${escHtml(file.name)}</span>`;
  hideStatus();
}

// ── Form submit ───────────────────────────────────────────────────────────────
form.addEventListener("submit", async e => {
  e.preventDefault();

  const file     = fileInput.files[0];
  const role     = val("role");
  const setting  = val("setting");
  const location = val("location");
  const date     = val("interviewDate");
  const num      = val("interviewNum");

  // Validation
  if (!file)     return showStatus("Please select a transcript file.", "error");
  if (!role)     return showStatus("Interviewee Role is required.", "error");
  if (!setting)  return showStatus("Setting is required.", "error");
  if (!location) return showStatus("Location is required.", "error");

  setLoading(true);
  hideStatus();
  cliPanel.hidden = true;

  if (API_ENDPOINT) {
    // ── Live API mode ─────────────────────────────────────────────────────
    const fd = new FormData();
    fd.append("transcript", file);
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
    // ── CLI fallback mode ─────────────────────────────────────────────────
    const dateFlag  = date ? `  --date "${date}"` : "";
    const numFlag   = num  ? `  --interview-num "${num}"` : "";
    const cmd = [
      `python ivd_clean.py \\`,
      `  --transcript "${file.name}" \\`,
      `  --role "${role}" \\`,
      `  --setting "${setting}" \\`,
      `  --location "${location}"` + (dateFlag || numFlag ? " \\" : ""),
      dateFlag  ? (numFlag ? dateFlag + " \\" : dateFlag) : null,
      numFlag   ? numFlag : null,
    ].filter(l => l !== null).join("\n");

    cliBlock.textContent = cmd;
    cliPanel.hidden = false;
    showStatus(
      "API not configured yet — copy the command below to run locally.",
      "info"
    );
  }

  setLoading(false);
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function val(id) { return document.getElementById(id).value.trim(); }
function escHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

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
  statusBox.hidden = true;
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
