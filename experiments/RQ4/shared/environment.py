"""Shared environment initialization for generation, testing and reruns."""
from dotenv import load_dotenv

from .. import REPOSITORY_ROOT


def load_runtime_environment() -> None:
    """Load repository-root configuration without replacing process settings."""
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
