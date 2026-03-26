# IVD Transcript Tool — Codebase Overview

A tool that takes raw Granola interview transcripts (.txt), cleans them with Claude, generates structured analyst notes, and outputs a formatted .docx using a locked DeciBio template. Deployed as a GitHub Pages frontend + Render FastAPI backend.

---

## Architecture

```
Browser (GitHub Pages)
    └─ docs/index.html + app.js + style.css + logo.png
           │  POST multipart/form-data
           ▼
Render (FastAPI)
    └─ server.py
           │
           ▼
    pipeline/
        parser.py       Step 1 — parse raw .txt → turns
        cleaner.py      Step 2 — LLM transcript clean
        notes.py        Step 3 — LLM structured notes
        docx_builder.py Step 4 — assemble .docx from template
           │
           ▼
    template/IV_template.docx  ← locked DeciBio branded template
```

---

## Deployment

| Layer    | Service             | URL                                              |
|----------|---------------------|--------------------------------------------------|
| Frontend | GitHub Pages        | https://benjaminzaidel-095.github.io/transcripts/ |
| Backend  | Render (free tier)  | https://transcripts-f993.onrender.com            |

`API_ENDPOINT` in `docs/app.js` line 7 must match the Render URL.
`ANTHROPIC_API_KEY` is set as an environment variable in the Render dashboard (never committed).

---

## Key Files

### `config.py`
Central config. Reads `.env` via `python-dotenv`.
- `CLEANING_MODEL` — `"claude"` or `"perplexity"` (swappable without code changes)
- `NOTES_MODEL` — always `"claude-sonnet-4-6"`
- `ANTHROPIC_API_KEY` / `PERPLEXITY_API_KEY` — from env

### `server.py`
FastAPI app. Single endpoint: `POST /process`
- Accepts: `transcript` (file), `role`, `setting`, `location`, `date`, `interview_num` (form fields)
- Runs the 4-step pipeline, writes temp .docx, returns it as a file download
- Cleans up temp file after response via `BackgroundTask`
- CORS open to `*` (tighten to GH Pages URL once stable)

### `ivd_clean.py`
CLI entrypoint (local use / batch processing).
```
python ivd_clean.py --transcript <file.txt> --role "Lab Director" --setting "Core Lab, AMC" --location "US"
```
Batch mode: pass a directory + `--role-file demographics.csv`

---

## Pipeline (`pipeline/`)

### `parser.py`
Parses Granola `.txt` format: `[HH:MM:SS] Speaker: text`
Speaker mapping: `You` → `DeciBio Moderator`, `System` → `Stakeholder`
Returns `list[{speaker, text}]`

### `cleaner.py`
Calls Claude (or Perplexity stub) with `prompts/cleaning_prompt.txt`.
Removes filler words, fixes grammar, strips PII — preserves all substance and Q&A structure.
Returns cleaned transcript as plain text (same `Speaker: text` format).

### `notes.py`
Calls Claude with `prompts/notes_prompt.txt`.
Returns `dict[section_name → list[str]]`. Each item is either:
- An analytical bullet (plain string)
- A supporting quote (string starting with `"` — rendered italic/indented in docx)

**6 fixed sections:**
1. Key Themes
2. Notable Quotes
3. IVD Platform & Competitive Landscape
4. Workflow & Utilization Patterns
5. Reimbursement & Coding
6. Forward-Looking Signals

### `docx_builder.py`
Builds the output `.docx` by:
1. Extracting `sectPr` (page layout, header/footer, logo refs) from `template/IV_template.docx`
2. Generating all body paragraphs as raw OOXML
3. Cloning the template zip, overwriting `word/document.xml`, rezipping

**Document structure:**
- Header block: Interview Subject / Date / Interviewee Demographics
- Horizontal rule (from template)
- Full cleaned transcript (speaker bold, text normal)
- Page break
- `INTERVIEW NOTES` title
- 6 sections: each with heading, bullets, and indented italic quotes

**Paragraph styles** (all Arial, hardcoded OOXML — no Word styles dependency):
- `_header_para()` — bold label + plain value, 1.5× line spacing
- `_transcript_para()` — bold speaker + plain text
- `_section_heading()` — bold, spacing before/after
- `_bullet_para()` — numId=6 (from template's numbering.xml), indented
- `_quote_para()` — italic, 10pt, gray (#595959), extra indent
- `_HRULE` — VML horizontal rule (verbatim from template)

---

## Prompts (`prompts/`)

### `cleaning_prompt.txt`
Instructs Claude to clean the transcript while preserving all substance. Placeholder: `{raw_transcript}`

### `notes_prompt.txt`
Instructs Claude to produce the 6-section notes with bullets + supporting quotes in a specific format. Placeholder: `{cleaned_transcript}`. Quotes must start with `"` and end with `— Stakeholder`.

---

## Frontend (`docs/`)

- `index.html` — form: file upload (drag+drop), role, setting, location, date, interview number
- `app.js` — submits FormData to `API_ENDPOINT`; on success downloads the returned .docx blob. Falls back to CLI command display if `API_ENDPOINT` is empty.
- `style.css` — DeciBio-branded card UI
- `logo.png` — DeciBio logo (also embedded in the .docx template)

GitHub Pages serves from the `/docs` folder on `main` branch.

---

## Template (`template/IV_template.docx`)

The branded base file. **Never modify its contents directly** — the docx_builder clones it and replaces only `word/document.xml`. The template carries:
- DeciBio logo in the header
- Page layout / margins (`sectPr`)
- Numbering definitions (`numbering.xml`) — bullet list uses `numId=6`
- Font embedding / theme

---

## Environment / Secrets

| Variable             | Where set                  | Used by              |
|----------------------|----------------------------|----------------------|
| `ANTHROPIC_API_KEY`  | `.env` (local) / Render dashboard | `config.py` |
| `PERPLEXITY_API_KEY` | `.env` (local, optional)   | `config.py` (stub)   |

`.env` is gitignored. Never commit it. `.env.example` is the safe reference.

---

## Known Pending Work / Notes for Next Agent

- **Quote rendering in notes:** The notes prompt already instructs Claude to emit supporting quotes per bullet. `notes.py` parses them and `docx_builder.py` renders them as italic/indented `_quote_para()`. Verify this round-trip is working end-to-end on a real transcript.
- **`numId=6`** in `_bullet_para()` is hardcoded from the current template's `numbering.xml`. If the template is ever replaced, verify this ID still maps to the correct list style.
- **Perplexity integration** (`pipeline/cleaner.py`) is a stub — not implemented.
- **CORS** in `server.py` is `allow_origins=["*"]` — restrict to the GitHub Pages URL once stable.
- **Render free tier** spins down after 15 min of inactivity; first request after sleep takes ~30s.
- **Design changes** are expected from the user before the next active build session.
