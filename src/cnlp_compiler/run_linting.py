from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from experiments._bootstrap import configure_source_paths
configure_source_paths()

from experiments.RQ3.experiment_runtime import local_timestamp, write_json


# Right-click Run configuration. Enable either dataset or both datasets.
RUN_SYNTAX = False
RUN_SEMANTIC = True

# Number of independent runs created inside this launch's timestamp directory.
REPEAT_COUNT = 3

# One initial API request plus at most 10 retries, 15 seconds apart.
API_RETRY_DELAY_SECONDS = 15
API_MAX_RETRIES = 10

RESULT_ROOT = (
    WORKSPACE_ROOT / "experiment_results" / "RQ3" / "reruns" / "linting_result"
)


def _create_batch_directory() -> Path:
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_directory = RESULT_ROOT / timestamp
    collision_index = 2
    while batch_directory.exists():
        batch_directory = RESULT_ROOT / f"{timestamp}_{collision_index:02d}"
        collision_index += 1
    batch_directory.mkdir(parents=True)
    return batch_directory


def run_semantic(result_directory: Path) -> tuple[Path, Path]:
    from experiments.RQ3.semantic.main import run_experiment

    return run_experiment(
        result_dir=result_directory,
        max_api_retries=API_MAX_RETRIES,
        api_retry_delay_seconds=API_RETRY_DELAY_SECONDS,
    )


def run_syntax(result_directory: Path) -> tuple[Path, Path]:
    from experiments.RQ3.syntaxical.main import run_experiment

    return run_experiment(
        result_dir=result_directory,
        max_api_retries=API_MAX_RETRIES,
        api_retry_delay_seconds=API_RETRY_DELAY_SECONDS,
    )


def _not_selected(mode_directory: Path, mode: str) -> None:
    write_json(
        mode_directory / "status.json",
        {
            "mode": mode,
            "status": "not_selected",
            "recorded_at": local_timestamp(),
        },
    )


def _failed_mode(mode_directory: Path, mode: str, exc: Exception) -> None:
    write_json(
        mode_directory / "status.json",
        {
            "mode": mode,
            "status": "failed",
            "finished_at": local_timestamp(),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )


def _mode_status(mode_directory: Path) -> str:
    status_path = mode_directory / "status.json"
    if not status_path.exists():
        return "completed"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    return str(payload.get("status", "completed"))


def _validate_configuration() -> None:
    if not RUN_SYNTAX and not RUN_SEMANTIC:
        raise ValueError("At least one of RUN_SYNTAX or RUN_SEMANTIC must be True.")
    if REPEAT_COUNT < 1:
        raise ValueError("REPEAT_COUNT must be at least 1.")
    if API_RETRY_DELAY_SECONDS < 0:
        raise ValueError("API_RETRY_DELAY_SECONDS cannot be negative.")
    if API_MAX_RETRIES < 0:
        raise ValueError("API_MAX_RETRIES cannot be negative.")


def main() -> Path:
    _validate_configuration()
    batch_directory = _create_batch_directory()
    batch_started_at = local_timestamp()
    batch_metadata_path = batch_directory / "batch_metadata.json"
    batch_runs: list[dict[str, object]] = []
    write_json(
        batch_metadata_path,
        {
            "status": "running",
            "started_at": batch_started_at,
            "batch_directory": str(batch_directory.resolve()),
            "run_syntax": RUN_SYNTAX,
            "run_semantic": RUN_SEMANTIC,
            "repeat_count": REPEAT_COUNT,
            "api_retry_delay_seconds": API_RETRY_DELAY_SECONDS,
            "api_max_retries": API_MAX_RETRIES,
            "maximum_api_attempts": API_MAX_RETRIES + 1,
            "runs": batch_runs,
        },
    )
    print(f"RQ3 linting result batch: {batch_directory.resolve()}", flush=True)

    for run_index in range(1, REPEAT_COUNT + 1):
        run_directory = batch_directory / f"run{run_index}"
        syntax_directory = run_directory / "syntax"
        semantic_directory = run_directory / "semantic"
        syntax_directory.mkdir(parents=True)
        semantic_directory.mkdir(parents=True)
        run_metadata_path = run_directory / "run_metadata.json"
        run_started_at = local_timestamp()
        run_record: dict[str, object] = {
            "run_index": run_index,
            "status": "running",
            "started_at": run_started_at,
            "syntax_status": "pending" if RUN_SYNTAX else "not_selected",
            "semantic_status": "pending" if RUN_SEMANTIC else "not_selected",
        }
        batch_runs.append(run_record)
        write_json(run_metadata_path, run_record)
        write_json(
            batch_metadata_path,
            {
                "status": "running",
                "started_at": batch_started_at,
                "batch_directory": str(batch_directory.resolve()),
                "run_syntax": RUN_SYNTAX,
                "run_semantic": RUN_SEMANTIC,
                "repeat_count": REPEAT_COUNT,
                "api_retry_delay_seconds": API_RETRY_DELAY_SECONDS,
                "api_max_retries": API_MAX_RETRIES,
                "maximum_api_attempts": API_MAX_RETRIES + 1,
                "runs": batch_runs,
            },
        )
        print(f"Starting run{run_index}/{REPEAT_COUNT}", flush=True)

        if RUN_SYNTAX:
            try:
                run_syntax(syntax_directory)
                run_record["syntax_status"] = _mode_status(syntax_directory)
            except Exception as exc:
                run_record["syntax_status"] = "failed"
                run_record["syntax_error"] = f"{type(exc).__name__}: {exc}"
                _failed_mode(syntax_directory, "syntax", exc)
        else:
            _not_selected(syntax_directory, "syntax")

        if RUN_SEMANTIC:
            try:
                run_semantic(semantic_directory)
                run_record["semantic_status"] = _mode_status(semantic_directory)
            except Exception as exc:
                run_record["semantic_status"] = "failed"
                run_record["semantic_error"] = f"{type(exc).__name__}: {exc}"
                _failed_mode(semantic_directory, "semantic", exc)
        else:
            _not_selected(semantic_directory, "semantic")

        mode_statuses = (
            run_record["syntax_status"],
            run_record["semantic_status"],
        )
        run_record["status"] = (
            "completed"
            if all(
                status in {"completed", "not_selected"}
                for status in mode_statuses
            )
            else "completed_with_errors"
        )
        run_record["finished_at"] = local_timestamp()
        write_json(run_metadata_path, run_record)
        print(f"Finished run{run_index}: {run_record['status']}", flush=True)

    batch_status = (
        "completed"
        if all(run["status"] == "completed" for run in batch_runs)
        else "completed_with_errors"
    )
    write_json(
        batch_metadata_path,
        {
            "status": batch_status,
            "started_at": batch_started_at,
            "finished_at": local_timestamp(),
            "batch_directory": str(batch_directory.resolve()),
            "run_syntax": RUN_SYNTAX,
            "run_semantic": RUN_SEMANTIC,
            "repeat_count": REPEAT_COUNT,
            "api_retry_delay_seconds": API_RETRY_DELAY_SECONDS,
            "api_max_retries": API_MAX_RETRIES,
            "maximum_api_attempts": API_MAX_RETRIES + 1,
            "runs": batch_runs,
        },
    )
    print(f"RQ3 batch finished: {batch_status}", flush=True)
    return batch_directory


if __name__ == "__main__":
    main()
