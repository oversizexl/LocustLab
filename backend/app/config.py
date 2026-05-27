import os
from pathlib import Path

STORAGE_DIR = Path(
    os.getenv("STORAGE_DIR", Path(__file__).parent.parent.parent / "storage")
).resolve()
SCRIPTS_DIR = STORAGE_DIR / "scripts"
REPORTS_DIR = STORAGE_DIR / "reports"
LOGS_DIR = STORAGE_DIR / "logs"

for directory in (SCRIPTS_DIR, REPORTS_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "locust-pressure-platform-secret")
DB_URL = os.getenv(
    "DB_URL", f"sqlite+aiosqlite:///{STORAGE_DIR / 'locust_platform.db'}"
)
