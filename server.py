"""
IVD Transcript Tool — FastAPI backend
Deploy to Render (free tier) or run locally with: uvicorn server:app --reload
"""

import asyncio
import base64
import json
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from sys import platform

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import config
from pipeline.parser import parse_transcript, turns_to_text
from pipeline.cleaner import clean_transcript
from pipeline.notes import generate_notes
from pipeline.docx_builder import build_transcript_docx, build_notes_docx

app = FastAPI(title="IVD Transcript Tool", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/")
def health():
    """Wake-up ping — frontend calls this on page load to warm Render."""
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
        raise HTTPException(status_code=400, detail="Transcript must be UTF-8 encoded text.")

    # Capture form values for use inside the async closure
    _role, _setting, _location, _date, _num = role, setting, location, date, interview_num

    queue: asyncio.Queue = asyncio.Queue()

    async def run_pipeline():
        try:
            # ── Step 1: Parse ─────────────────────────────────────────────────
            await queue.put({"event": "stage", "stage": "parsing"})
            turns = parse_transcript(raw_text)
            preprocessed = turns_to_text(turns) if turns else raw_text

            # ── Step 2: Clean ─────────────────────────────────────────────────
            await queue.put({"event": "stage", "stage": "cleaning"})
            try:
                cleaned = await asyncio.to_thread(clean_transcript, preprocessed)
            except Exception as e:
                raise RuntimeError(f"Cleaning failed: {e}")

            # ── Step 3: Notes ─────────────────────────────────────────────────
            await queue.put({"event": "stage", "stage": "notes"})
            try:
                notes = await asyncio.to_thread(generate_notes, cleaned)
            except Exception as e:
                raise RuntimeError(f"Notes generation failed: {e}")

            # ── Step 4: Build ─────────────────────────────────────────────────
            await queue.put({"event": "stage", "stage": "building"})

            interview_date = _format_date(_date) if _date else _today()
            num = _num.strip() if _num.strip() else "IV"

            _parts = [p.strip() for p in _setting.split(",") if p.strip()]
            _inst = _parts[-1] if _parts else ""
            stakeholder_label = f"{_inst} Stakeholder" if _inst else "Stakeholder"

            payload = {
                "header": {
                    "date": interview_date,
                    "role": _role,
                    "setting": _setting,
                    "location": _location,
                },
                "transcript": _parse_cleaned_turns(cleaned, stakeholder_label),
                "notes": notes,
            }

            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp1:
                transcript_path = Path(tmp1.name)
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp2:
                notes_path = Path(tmp2.name)

            try:
                await asyncio.gather(
                    asyncio.to_thread(build_transcript_docx, payload, transcript_path),
                    asyncio.to_thread(build_notes_docx, payload, notes_path),
                )
                transcript_bytes = transcript_path.read_bytes()
                notes_bytes = notes_path.read_bytes()
            finally:
                transcript_path.unlink(missing_ok=True)
                notes_path.unlink(missing_ok=True)

            # ── Done ──────────────────────────────────────────────────────────
            await queue.put({
                "event": "done",
                "transcript_filename": f"{num}_Cleaned.docx",
                "transcript_b64": base64.b64encode(transcript_bytes).decode("ascii"),
                "notes_filename": f"{num}_Notes.docx",
                "notes_b64": base64.b64encode(notes_bytes).decode("ascii"),
            })

        except Exception as e:
            await queue.put({"event": "error", "detail": str(e)})
        finally:
            await queue.put(None)  # sentinel — signals end of stream

    asyncio.create_task(run_pipeline())

    async def event_stream():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_cleaned_turns(cleaned_text: str, stakeholder_label: str = "Stakeholder") -> list[dict]:
    turns, current_speaker, current_lines = [], None, []

    _SPEAKER_RE = re.compile(
        r"^(DeciBio Moderator|Stakeholder|You|System):\s*(.*)",
        re.IGNORECASE,
    )

    def flush():
        if current_speaker and current_lines:
            turns.append({"speaker": current_speaker, "text": " ".join(current_lines).strip()})

    for line in cleaned_text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush(); current_speaker = None; current_lines = []; continue
        m = _SPEAKER_RE.match(stripped)
        if m:
            flush()
            raw = m.group(1).lower()
            if raw in ("you", "decibio moderator"):
                current_speaker = "DeciBio Moderator"
            else:
                current_speaker = stakeholder_label
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
    return raw


def _today() -> str:
    d = date.today()
    return d.strftime("%B %#d, %Y") if platform == "win32" else d.strftime("%B %-d, %Y")
