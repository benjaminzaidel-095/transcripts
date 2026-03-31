import os
from dotenv import load_dotenv

load_dotenv()

# Model routing — swap CLEANING_MODEL between "claude" and "perplexity"
CLEANING_MODEL = "claude"   # TBD: "claude" | "perplexity"
NOTES_MODEL    = "claude-sonnet-4-6"     # used for notes generation
HAIKU_MODEL    = "claude-haiku-4-5-20251001"  # fast/cheap model for transcript cleaning

# Project metadata
PROJECT_NAME = "IVD Sequencing Landscape"

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")  # placeholder

# Output
DEFAULT_OUTPUT_DIR = "./output"
