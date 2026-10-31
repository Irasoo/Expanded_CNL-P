"""Locate repository source packages for directly runnable experiments."""
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def configure_source_paths() -> Path:
    for directory in (REPOSITORY_ROOT, REPOSITORY_ROOT / "experiments", REPOSITORY_ROOT / "src"):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    return REPOSITORY_ROOT
