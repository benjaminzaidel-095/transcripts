#!/usr/bin/env python3
"""
ivd_clean.py — IVD Transcript Cleaning & Notes Tool
Usage: python ivd_clean.py --transcript <file> --role <role> --setting <setting> --location <location>
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import config
from pipeline.parser import parse_transcript, turns_to_text
from pipeline.cleaner import clean_transcript
from pipeline.notes import generate_notes
from pipeline.docx_builder import build_docx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def next_interview_num(output_dir: Path) -> str:
    """Auto-increment interview number from existing IV*.docx files."""
    existing = list(output_dir.glob("IV*_Cleaned.docx"))
    nums = []
    for f in existing:
        m = re.match(r"IV(\d+)_Cleaned\.docx", f.name)
        if m:
            nums.append(int(m.group(1)))
    return f"IV{max(nums) + 1}" if nums else "IV1"


def parse_date(raw: str) -> str:
    """Accept YYYY-MM-DD or MM/DD/YYYY, return 'Month D, YYYY'."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            from datetime import datetime
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%B %-d, %Y") if sys.platform != "win32" else dt.strftime("%B %#d, %Y")
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid date '{raw}'. Use YYYY-MM-DD or MM/DD/YYYY."
    )


def today_formatted() -> str:
    d = date.today()
    if sys.platform == "win32":
        return d.strftime("%B %#d, %Y")
    return d.strftime("%B %-d, %Y")


# ---------------------------------------------------------------------------
# Single-transcript processing
# ---------------------------------------------------------------------------

def process_one(
    transcript_path: Path,
    role: str,
    setting: str,
    location: str,
    interview_date: str,
    interview_num: str,
    output_dir: Path,
) -> Path:
    print(f"[1/4] Parsing {transcript_path.name} …")
    raw_text = transcript_path.read_text(encoding="utf-8")
    turns = parse_transcript(raw_text)
    if not turns:
        sys.exit(f"ERROR: No turns found in {transcript_path}. Check transcript format.")
    raw_mapped = turns_to_text(turns)

    print("[2/4] Cleaning transcript …")
    cleaned = clean_transcript(raw_mapped)

    print("[3/4] Generating structured notes …")
    notes = generate_notes(cleaned)

    print("[4/4] Building .docx …")
    payload = {
        "header": {
            "date": interview_date,
            "role": role,
            "setting": setting,
            "location": location,
        },
        "transcript": [{"speaker": t["speaker"], "text": t["text"]} for t in
                        _parse_cleaned_turns(cleaned)],
        "notes": notes,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{interview_num}_Cleaned.docx"

    build_docx(payload, out_path)
    print(f"Written: {out_path}")

    # Validate
    validate_script = Path(__file__).parent / "scripts" / "validate.py"
    if validate_script.exists():
        val = subprocess.run(
            [sys.executable, "-X", "utf8", str(validate_script), str(out_path)],
            capture_output=True, text=True, encoding="utf-8"
        )
        if val.returncode != 0:
            print(f"WARNING: Validation issues:\n{val.stdout}\n{val.stderr}")
        else:
            print("Validation passed.")

    return out_path


def _parse_cleaned_turns(cleaned_text: str) -> list[dict]:
    """
    Parse cleaned LLM output (which uses 'Speaker: text' format)
    back into {speaker, text} turns for the docx builder.
    """
    turns = []
    current_speaker = None
    current_lines = []

    def flush():
        if current_speaker and current_lines:
            turns.append({"speaker": current_speaker, "text": " ".join(current_lines).strip()})

    for line in cleaned_text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            current_speaker = None
            current_lines = []
            continue

        # Match "Speaker: text" — speaker is up to first colon
        m = re.match(r"^(DeciBio Moderator|Stakeholder):\s*(.*)", stripped)
        if m:
            flush()
            current_speaker = m.group(1)
            current_lines = [m.group(2)] if m.group(2) else []
        else:
            if current_speaker:
                current_lines.append(stripped)

    flush()
    return turns


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_batch(
    transcript_dir: Path,
    role_file: Path,
    output_dir: Path,
    start_num: int,
) -> None:
    import csv

    if not role_file.exists():
        sys.exit(f"ERROR: Demographics file not found: {role_file}")

    with open(role_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows):
        txt_path = transcript_dir / row["filename"]
        if not txt_path.exists():
            print(f"SKIP: {txt_path} not found.")
            continue

        interview_num = f"IV{start_num + i}"
        raw_date = row.get("date", "").strip()
        interview_date = parse_date(raw_date) if raw_date else today_formatted()

        print(f"\n=== {interview_num}: {row['filename']} ===")
        out = process_one(
            txt_path,
            role=row["role"],
            setting=row["setting"],
            location=row["location"],
            interview_date=interview_date,
            interview_num=interview_num,
            output_dir=output_dir,
        )
        print(f"Output: {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="IVD Transcript Cleaning & Notes Tool"
    )

    parser.add_argument("--transcript", required=True,
                        help="Path to raw .txt transcript file, or directory for batch mode")
    parser.add_argument("--role", help="Interviewee role (e.g. 'Lab Director')")
    parser.add_argument("--setting", help="Setting (e.g. 'Core Lab, AMC')")
    parser.add_argument("--location", help="Geography (e.g. 'US')")
    parser.add_argument("--date", default=None,
                        help="Interview date (YYYY-MM-DD or MM/DD/YYYY). Defaults to today.")
    parser.add_argument("--output", default=config.DEFAULT_OUTPUT_DIR,
                        help=f"Output directory (default: {config.DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--interview-num", default=None,
                        help="Interview number label, e.g. 'IV3'. Auto-increments if omitted.")
    # Batch-mode options
    parser.add_argument("--role-file", default=None,
                        help="CSV demographics file for batch mode")
    parser.add_argument("--start-num", type=int, default=1,
                        help="Starting interview number for batch mode (default: 1)")

    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    output_dir = Path(args.output)

    # ---- Batch mode ----
    if transcript_path.is_dir():
        if not args.role_file:
            parser.error("--role-file is required when --transcript is a directory.")
        process_batch(
            transcript_dir=transcript_path,
            role_file=Path(args.role_file),
            output_dir=output_dir,
            start_num=args.start_num,
        )
        return

    # ---- Single mode ----
    if not transcript_path.exists():
        sys.exit(f"ERROR: Transcript file not found: {transcript_path}")

    for flag, name in [("--role", args.role), ("--setting", args.setting), ("--location", args.location)]:
        if not name:
            parser.error(f"{flag} is required for single-file mode.")

    interview_date = parse_date(args.date) if args.date else today_formatted()

    if args.interview_num:
        interview_num = args.interview_num
    else:
        interview_num = next_interview_num(output_dir)

    out = process_one(
        transcript_path=transcript_path,
        role=args.role,
        setting=args.setting,
        location=args.location,
        interview_date=interview_date,
        interview_num=interview_num,
        output_dir=output_dir,
    )
    print(f"\nDone: {out}")


if __name__ == "__main__":
    main()
