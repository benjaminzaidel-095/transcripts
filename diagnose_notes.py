#!/usr/bin/env python3
"""
Diagnostic script — run this to see exactly what Claude returns for notes
and how the parser handles it.

Usage:
    python diagnose_notes.py                    # uses built-in mini transcript
    python diagnose_notes.py transcript.txt     # uses a real cleaned transcript
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config
import anthropic

SECTION_HEADERS = [
    "Key Themes",
    "Notable Quotes",
    "IVD Platform & Competitive Landscape",
    "Workflow & Utilization Patterns",
    "Reimbursement & Coding",
    "Forward-Looking Signals",
]

MINI_TRANSCRIPT = """\
DeciBio Moderator: Can you describe the sequencing platforms your lab currently uses?

Stakeholder: We primarily rely on the Illumina NextSeq 550. We have been on it for about three years. It works well for our oncology panel, which covers roughly 500 genes.

DeciBio Moderator: How does your lab approach reimbursement for NGS panels?

Stakeholder: It is genuinely challenging. We use CPT 81455 for most of our solid tumor work. Payers have been pushing back on broader panels, so we have had to narrow the menu. The economics just do not pencil out otherwise.

DeciBio Moderator: Are you evaluating any alternative platforms?

Stakeholder: We have looked at the Ion Torrent system but nothing serious yet. Illumina has been our primary vendor for eight years and we are not switching unless something dramatic changes.
"""


def main():
    if len(sys.argv) > 1:
        transcript = Path(sys.argv[1]).read_text(encoding="utf-8")
        print(f"Using transcript: {sys.argv[1]}")
    else:
        transcript = MINI_TRANSCRIPT
        print("Using built-in mini transcript")

    prompt_path = Path(__file__).parent / "prompts" / "notes_prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8").replace("{cleaned_transcript}", transcript)

    print(f"\nModel: {config.NOTES_MODEL}")
    print("Calling Claude...\n")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.NOTES_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    # ── Show raw output ───────────────────────────────────────────────────────
    print("=" * 60)
    print("RAW CLAUDE OUTPUT (first 60 lines):")
    print("=" * 60)
    lines = raw.splitlines()
    for i, line in enumerate(lines[:60]):
        print(f"{i+1:3d}  {repr(line)}")
    if len(lines) > 60:
        print(f"     ... ({len(lines) - 60} more lines)")

    # ── Show which lines match (or fail to match) section headers ─────────────
    print("\n" + "=" * 60)
    print("HEADER DETECTION TRACE (every line checked):")
    print("=" * 60)
    for i, line in enumerate(lines[:80]):
        stripped = line.strip()
        if not stripped:
            continue
        clean = re.sub(r'^\d+[\.\)]\s*', '', stripped)
        clean = re.sub(r'^[#*_]+\s*', '', clean)
        clean = re.sub(r'\s*[#*_]+$', '', clean).strip()
        clean = re.sub(r'^\d+[\.\)]\s*', '', clean)  # second pass

        matched = None
        for h in SECTION_HEADERS:
            if clean.lower() == h.lower() or clean.lower().startswith(h.lower() + ':'):
                matched = h
                break

        if matched:
            print(f"  LINE {i+1:3d} HEADER MATCH: {repr(stripped)} → '{matched}'")
        elif any(h.lower() in stripped.lower() for h in SECTION_HEADERS):
            print(f"  LINE {i+1:3d} NEAR-MISS:    {repr(stripped)}")
            print(f"            clean={repr(clean)}")

    # ── Run the actual parser and show result ────────────────────────────────
    print("\n" + "=" * 60)
    print("PARSER RESULT:")
    print("=" * 60)
    from pipeline.notes import _parse_notes
    result = _parse_notes(raw)
    total = 0
    for section, items in result.items():
        print(f"\n  [{section}] — {len(items)} item(s)")
        for item in items[:5]:
            print(f"    {repr(item[:100])}")
        total += len(items)
    print(f"\nTOTAL ITEMS PARSED: {total}")

    if total == 0:
        print("\n*** DIAGNOSIS: Parser returned 0 items ***")
        print("Likely causes:")
        print("  1. Section headers in Claude output don't match after normalisation")
        print("  2. Claude output is empty")
        print("  3. All content lines before any recognised header (skipped)")


if __name__ == "__main__":
    main()
