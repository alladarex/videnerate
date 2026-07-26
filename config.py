import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# App root
APP_DIR = Path(__file__).resolve().parent

# Project directory (where user projects live)
PROJECTS_DIR = Path(os.getenv("VIDENERATE_PROJECTS_DIR") or APP_DIR / "projects").resolve()


# Ensure directories exist
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY")
