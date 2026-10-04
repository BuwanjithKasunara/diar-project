"""Environment overrides are read at startup. Defaults target a local demo."""
import os


def positive(name, default):
    value = int(os.getenv(name, default))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


MAX_PDF_BYTES = positive("DIAR_MAX_PDF_BYTES", 5 * 1024 * 1024)
MAX_PDF_PAGES = positive("DIAR_MAX_PDF_PAGES", 30)
MAX_TEXT_CHARS = positive("DIAR_MAX_TEXT_CHARS", 50000)
ACTIVITY_DAYS = positive("DIAR_ACTIVITY_DAYS", 180)
MAX_REPOS = positive("DIAR_MAX_REPOS", 500)
MAX_GITHUB_READMES = positive("DIAR_MAX_GITHUB_READMES", 5)
MAX_GITHUB_README_CHARS = positive("DIAR_MAX_GITHUB_README_CHARS", 20000)
MAX_ACTIONS = positive("DIAR_MAX_ACTIONS", 20)
MAX_STATES = positive("DIAR_MAX_STATES", 50000)
GITHUB_TOKEN = os.getenv("DIAR_GITHUB_TOKEN")
BENCHMARK_VERSION = "3"
PLANNER_VERSION = "2"
LOCAL_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
