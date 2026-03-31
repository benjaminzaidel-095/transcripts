"""Step 3: LLM structured notes call (always Claude)."""

import re
from pathlib import Path
import config


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "notes_prompt.txt"

SECTION_HEADERS = [
    "Key Themes",
    "Notable Quotes",
    "IVD Platform & Competitive Landscape",
    "Workflow & Utilization Patterns",
    "Reimbursement & Coding",
    "Forward-Looking Signals",
]


def generate_notes(cleaned_transcript: str) -> dict[str, list[str]]:
    """
    Call Claude to generate structured notes.
    Returns dict: section name -> list of strings where each string is either
    - a bullet (analytical point) — plain text
    - a quote — starts with '"' (will be rendered italic/indented in docx)
    """
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.replace("{cleaned_transcript}", cleaned_transcript)

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.NOTES_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_notes = message.content[0].text.strip()
    return _parse_notes(raw_notes)


def _parse_notes(raw: str) -> dict[str, list[str]]:
    """
    Parse LLM notes output into {section: [items]}.

    Items are either:
    - bullet text (plain string, no leading •)
    - quote string (starts with '"' — indented italic in docx)
    """
    sections: dict[str, list[str]] = {h: [] for h in SECTION_HEADERS}
    current_section: str | None = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Normalise the line so all Claude formatting variants resolve to bare text.
        # Order matters: strip numbers → strip markdown → strip numbers again.
        # This handles: "1. Key Themes", "**Key Themes**", "**1. Key Themes**",
        # "1. **Key Themes**", "## 1. Key Themes", etc.
        clean = re.sub(r'^\d+[\.\)]\s*', '', stripped)   # "1. Key Themes" → "Key Themes"
        clean = re.sub(r'^[#*_]+\s*', '', clean)          # "**Key Themes**" → "Key Themes**"
        clean = re.sub(r'\s*[#*_]+$', '', clean).strip()  # "Key Themes**"  → "Key Themes"
        clean = re.sub(r'^\d+[\.\)]\s*', '', clean)       # "1. Key Themes" → "Key Themes" (second pass after ** strip)

        # Section header check — must run BEFORE any bullet guard because Claude
        # often emits "**Key Themes**" which starts with "*" and would otherwise
        # be misidentified as a bullet, leaving current_section unset forever.
        matched = None
        for header in SECTION_HEADERS:
            if (clean.lower() == header.lower()
                    or clean.lower().startswith(header.lower() + ':')):
                matched = header
                break

        if matched:
            current_section = matched
            continue

        if current_section is None:
            continue

        # Quote line: starts with " or " (supporting quote)
        if stripped.startswith('"') or stripped.startswith('\u201c'):
            sections[current_section].append(stripped)

        # Bullet line: starts with •, -, *
        elif stripped.startswith(("•", "-", "*")):
            text = stripped[1:].strip()
            if text:
                sections[current_section].append(text)
        elif stripped[0].isdigit() and len(stripped) > 2 and stripped[1] in ".):":
            text = stripped[2:].strip()
            if text:
                sections[current_section].append(text)
        else:
            if stripped:
                sections[current_section].append(stripped)

    return sections
