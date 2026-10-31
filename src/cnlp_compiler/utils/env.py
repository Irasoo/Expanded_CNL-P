import os
from pathlib import Path

from dotenv import load_dotenv


def _find_env_path() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate

    cwd_candidate = Path.cwd() / ".env"
    if cwd_candidate.exists():
        return cwd_candidate

    return None


def get_env_value(key: str):
    env_path = _find_env_path()
    if env_path is not None:
        load_dotenv(dotenv_path=env_path, override=True)
    return os.getenv(key)
