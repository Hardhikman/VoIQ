"""VoIQ Configuration - Environment and settings management."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "voiq.db"))

# LLM Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# Quiz Settings
DEFAULT_TIMER_SECONDS = 10
TIMER_OPTIONS = [5, 10, 20]

# Fuzzy matching threshold for dictation
FUZZY_THRESHOLD = 0.75

# UI Theme
THEME_PRIMARY_COLOR = "#6366f1"  # Indigo
THEME_SECONDARY_COLOR = "#8b5cf6"  # Purple
