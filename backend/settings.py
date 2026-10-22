"""Shared configuration; relative data paths are rooted at the backend directory."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    for candidate in (BACKEND_DIR / ".env", Path.cwd() / ".env"):
        if not os.path.exists(candidate):
            continue
        with open(candidate, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        break


_load_dotenv()
_data_path = Path(os.environ.get("DATA_DIR", "data").strip() or "data").expanduser()
DATA_DIR = str((_data_path if _data_path.is_absolute() else BACKEND_DIR / _data_path).resolve())
