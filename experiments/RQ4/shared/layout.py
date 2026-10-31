"""Locate specifications, generation methods and batch directories."""
from pathlib import Path
import re

PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
SPECIFICATION_FILES = {"cnlp": "agent.cnlp", "nl": "agent.nl.md", "risen": "agent.risen.md"}
METHODS = {"cnlp": ("native", "langgraph", "codex"), "nl": ("codex",), "risen": ("codex",)}
CASE_NAMES = ("ab_test", "creative_concept_refinement", "github_project_navigator", "internal_comms")


def directory_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"Expected a direct directory name: {value!r}")
    return value


def specification_filename(case_directory: Path) -> str:
    present = [name for name in SPECIFICATION_FILES.values() if (case_directory / name).is_file()]
    if len(present) != 1:
        raise ValueError(f"Frozen case must contain exactly one representation: {case_directory}")
    return present[0]


def representation_for_case(case_directory: Path) -> str:
    selected = specification_filename(case_directory)
    return next(name for name, filename in SPECIFICATION_FILES.items() if filename == selected)


def representation_directory(batch_id: str, representation: str) -> Path:
    directory_name(batch_id)
    if representation not in SPECIFICATION_FILES:
        raise ValueError(f"Unknown representation: {representation!r}")
    directory = PROJECT_DIRECTORY / "batches" / batch_id / representation
    if not directory.is_dir():
        raise FileNotFoundError(f"Frozen experiment not found: {directory}")
    return directory
