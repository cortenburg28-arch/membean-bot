from pathlib import Path

from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

STORAGE_STATE_PATH = ROOT_DIR / "storage_state.json"
LOGS_DIR = ROOT_DIR / "logs"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
WORTER_PATH = ROOT_DIR / "worter.txt"

AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

_PROVIDER_DEFAULTS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1",
        "model": "allam-2-7b",
    },
    "lmstudio": {
        "url": "http://localhost:1234/v1",
        "model": "qwen3-8b",
    },
}

_defaults = _PROVIDER_DEFAULTS.get(AI_PROVIDER, _PROVIDER_DEFAULTS["groq"])
AI_API_URL = os.getenv("AI_API_URL", _defaults["url"])
AI_MODEL = os.getenv("AI_MODEL", _defaults["model"])
AI_API_KEY = os.getenv("AI_API_KEY", "")

MEMBEAN_HOME_URL = os.getenv("MEMBEAN_HOME_URL", "https://membean.com")
MEMBEAN_DASHBOARD_URL = os.getenv("MEMBEAN_DASHBOARD_URL", "https://membean.com/dashboard").strip()
MEMBEAN_TRAINING_URL = os.getenv("MEMBEAN_TRAINING_URL", "").strip()

AUTO_START_TRAINING = os.getenv("AUTO_START_TRAINING", "true").lower() in {"1", "true", "yes"}
SESSION_DURATION_MINUTES = int(os.getenv("SESSION_DURATION_MINUTES", "10"))

HEADLESS = os.getenv("HEADLESS", "false").lower() in {"1", "true", "yes"}
BROWSER_SLOW_MO = int(os.getenv("BROWSER_SLOW_MO", "0"))

# Allgemeine menschliche Pausen (Tipp 1)
DELAY_MIN = float(os.getenv("DELAY_MIN", "0.8"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "2.5"))

LEARN_PAGE_WAIT = float(os.getenv("LEARN_PAGE_WAIT", "1.0"))

QUIZ_LOAD_WAIT_MIN = float(os.getenv("QUIZ_LOAD_WAIT_MIN", "3.0"))
QUIZ_LOAD_WAIT_MAX = float(os.getenv("QUIZ_LOAD_WAIT_MAX", "6.0"))
QUIZ_AFTER_ANSWER_WAIT = float(os.getenv("QUIZ_AFTER_ANSWER_WAIT", "2.0"))

READ_PAUSE_MIN = float(os.getenv("READ_PAUSE_MIN", "2.0"))
READ_PAUSE_MAX = float(os.getenv("READ_PAUSE_MAX", "5.0"))

# Tipp 3: kurz überlegen vor MCQ/Learn-Quiz
THINK_PAUSE_MIN = float(os.getenv("THINK_PAUSE_MIN", "1.0"))
THINK_PAUSE_MAX = float(os.getenv("THINK_PAUSE_MAX", "3.0"))

# Tipp 9: Pause zwischen Seitenwechseln
PAGE_TRANSITION_MIN = float(os.getenv("PAGE_TRANSITION_MIN", "0.5"))
PAGE_TRANSITION_MAX = float(os.getenv("PAGE_TRANSITION_MAX", "1.5"))

SPELL_PAUSE_BEFORE_MIN = float(os.getenv("SPELL_PAUSE_BEFORE_MIN", "1.0"))
SPELL_PAUSE_BEFORE_MAX = float(os.getenv("SPELL_PAUSE_BEFORE_MAX", "2.5"))
SPELL_PAUSE_AFTER_MIN = float(os.getenv("SPELL_PAUSE_AFTER_MIN", "0.4"))
SPELL_PAUSE_AFTER_MAX = float(os.getenv("SPELL_PAUSE_AFTER_MAX", "0.9"))

# Tipp 2: variable Tippgeschwindigkeit
TYPE_DELAY_MIN_MS = int(os.getenv("TYPE_DELAY_MIN_MS", "90"))
TYPE_DELAY_MAX_MS = int(os.getenv("TYPE_DELAY_MAX_MS", "220"))

# Tipp 4: realistische Survey-Antwort (nur Zwischenfragen, nicht MCQ)
SURVEY_REALISTIC_RATE = float(os.getenv("SURVEY_REALISTIC_RATE", "0.95"))

# Ziel-Genauigkeit MCQ/Learn: 100 = immer KI-Antwort, 87 = ~87 % richtig
QUIZ_TARGET_ACCURACY = float(os.getenv("QUIZ_TARGET_ACCURACY", "100"))

ANSWER_MODE = os.getenv("ANSWER_MODE", "ai")

# KI-Prompt: ultra (~20) | compact (~60, default) | standard (~100)
AI_PROMPT_STYLE = os.getenv("AI_PROMPT_STYLE", "compact").lower()
