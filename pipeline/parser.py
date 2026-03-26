"""Step 1: Parse raw Granola .txt transcript and map speakers."""

import re


def parse_transcript(raw_text: str) -> list[dict]:
    """
    Parse a raw Granola transcript into a list of {speaker, text} turns.

    Input format:
        [HH:MM:SS] You: Hello there...
        [HH:MM:SS] System: Thanks for having me...

    Speaker mapping:
        You     -> DeciBio Moderator
        System  -> Stakeholder
        (anything else) -> kept as-is
    """
    SPEAKER_MAP = {
        "you": "DeciBio Moderator",
        "system": "Stakeholder",
    }

    # Match lines like: [00:01:23] Speaker: text
    line_re = re.compile(
        r"^\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s+([^:]+?):\s+(.*)",
        re.IGNORECASE,
    )

    turns = []
    current_speaker = None
    current_lines = []

    def flush():
        if current_speaker is not None and current_lines:
            turns.append({
                "speaker": current_speaker,
                "text": " ".join(current_lines).strip(),
            })

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = line_re.match(line)
        if m:
            flush()
            raw_speaker = m.group(1).strip()
            text = m.group(2).strip()
            mapped = SPEAKER_MAP.get(raw_speaker.lower(), raw_speaker)
            current_speaker = mapped
            current_lines = [text] if text else []
        else:
            # Continuation of previous turn
            if current_speaker is not None:
                current_lines.append(line)

    flush()
    return turns


def turns_to_text(turns: list[dict]) -> str:
    """Render parsed turns back to a plain-text block for LLM input."""
    lines = []
    for t in turns:
        lines.append(f"{t['speaker']}: {t['text']}")
    return "\n\n".join(lines)
