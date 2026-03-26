"""Step 2: LLM transcript cleaning call (swappable via config.CLEANING_MODEL)."""

from pathlib import Path
import config


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "cleaning_prompt.txt"


def clean_transcript(raw_transcript: str) -> str:
    """
    Call the configured cleaning model and return the cleaned transcript text.
    CLEANING_MODEL is set in config.py and can be swapped without code changes.
    """
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.replace("{raw_transcript}", raw_transcript)

    model = config.CLEANING_MODEL.lower()

    if model == "claude":
        return _clean_with_claude(prompt)
    elif model == "perplexity":
        return _clean_with_perplexity(prompt)
    else:
        raise ValueError(
            f"Unknown CLEANING_MODEL '{config.CLEANING_MODEL}'. "
            "Set to 'claude' or 'perplexity' in config.py."
        )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _clean_with_claude(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    with client.messages.stream(
        model=config.HAIKU_MODEL,  # faster + cheaper for mechanical cleaning step
        max_tokens=32768,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_text().strip()


def _clean_with_perplexity(prompt: str) -> str:
    """Perplexity API stub — implement once model decision is made."""
    # Perplexity uses an OpenAI-compatible API
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package required for Perplexity integration. "
            "Run: pip install openai"
        )

    client = OpenAI(
        api_key=config.PERPLEXITY_API_KEY,
        base_url="https://api.perplexity.ai",
    )
    response = client.chat.completions.create(
        model="llama-3.1-sonar-large-128k-online",  # update as needed
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
