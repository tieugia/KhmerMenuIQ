import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CHAT_MODEL = os.environ.get("CHAT_MODEL", "google/gemini-2.5-flash")
KHR_PER_USD = float(os.environ.get("KHR_PER_USD", "4100"))

# Extra origin allowed to call the API (the deployed frontend's URL). Local dev origins are
# always allowed regardless of this setting.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "")

MENUS_FILE = BACKEND_DIR / "data" / "menus.json"
