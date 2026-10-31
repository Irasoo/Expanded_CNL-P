"""CSV persistence and result-path helpers."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterable

from utils.constants import OUTPUT_ENCODING
from utils.types import RESULT_FIELDS


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding=OUTPUT_ENCODING, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    raise ValueError(f"CSV has no header: {path}")
                return list(reader.fieldnames), list(reader)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode CSV: {path}")


def result_csv_path(run_root: Path, task_id: str, model_key: str, language: str) -> Path:
    return run_root / f"task{task_id}" / model_key / f"{language}.csv"


def task_summary_path(run_root: Path, task_id: str) -> Path:
    return run_root / f"task{task_id}" / f"task{task_id}_summary.csv"


def global_summary_path(run_root: Path) -> Path:
    return run_root / "total_summary.csv"


def run_readme_path(run_root: Path) -> Path:
    return run_root / "README.md"


def result_files(run_root: Path) -> list[Path]:
    return sorted(path for path in run_root.glob("task*/*/*.csv") if path.name != "task_summary.csv")


def ensure_result_file(path: Path) -> set[str]:
    if not path.exists():
        write_csv(path, RESULT_FIELDS, [])
        return set()
    fields, rows = read_csv(path)
    if fields != RESULT_FIELDS:
        raise ValueError(f"Unexpected result CSV header: {path}")
    instance_ids = [row.get("instance_id", "").strip() for row in rows]
    if len(instance_ids) != len(set(instance_ids)):
        raise ValueError(f"Duplicate instance_id in {path}")
    return set(instance_ids)


# Kept as a compatibility alias while callers migrate to the public name.
_read_csv = read_csv
