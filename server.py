"""
IVD Transcript Tool — FastAPI backend
Deploy to Render (free tier) or run locally with: uvicorn server:app --reload
"""

import tempfile
from datetime import date, datetime
from pathlib import Path
from sys import platform

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
from pipeline.cleaner import clean_transcript
from pipeline.notes import generate_notes
from pipeline.docx_builder import build_docx

app = FastAPI(title="IVD Transcript Tool", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # lock this down to your GitHub Pages URL once deployed
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/process")
async def process_transcript(
    transcript: UploadFile = File(...),
    role: str = Form(...),
    setting: str = Form(...),
    location: str = Form(...),
    date: str = Form(default=""),
    interview_num: str = Form(default=""),
):
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured on server.")

    raw_bytes = await transcript.read()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Transcript file must be UTF-8 encoded text.")

    # Clean
    try:
        cleaned = clean_transcript(raw_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cleaning step failed: {e}")

    # Notes
    try:
        notes = generate_notes(cleaned)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Notes step failed: {e}")

    # Format date
    interview_date = _format_date(date) if date else _today()

    # Determine interview number
    num = interview_num.strip() if interview_num.strip() else "IV"

    # Build docx into a temp file
    payload = {
        "header": {
            "date": interview_date,
            "role": role,
            "setting": setting,
            "location": location,
        },
        "transcript": _parse_cleaned_turns(cleaned),
        "notes": notes,
    }

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        out_path = Path(tmp.name)

    build_docx(payload, out_path)

    filename = f"{num}_Cleaned.docx"
    return FileResponse(
        path=str(out_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=_cleanup(out_path),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

import re

def _parse_cleaned_turns(cleaned_text: str) -> list[dict]:
    turns, current_speaker, current_lines = [], None, []

    def flush():
        if current_speaker and current_lines:
            turns.append({"speaker": current_speaker, "text": " ".join(current_lines).strip()})

    for line in cleaned_text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush(); current_speaker = None; current_lines = []; continue
        m = re.match(r"^(DeciBio Moderator|Stakeholder):\s*(.*)", stripped)
        if m:
            flush()
            current_speaker = m.group(1)
            current_lines = [m.group(2)] if m.group(2) else []
        elif current_speaker:
            current_lines.append(stripped)
    flush()
    return turns


def _format_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%B %#d, %Y") if platform == "win32" else dt.strftime("%B %-d, %Y")
        except ValueError:
            continue
    return raw  # return as-is if unparseable


def _today() -> str:
    d = date.today()
    return d.strftime("%B %#d, %Y") if platform == "win32" else d.strftime("%B %-d, %Y")


from starlette.background import BackgroundTask

def _cleanup(path: Path) -> BackgroundTask:
    def _del():
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
    return BackgroundTask(_del)
