from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, Callable, TypeVar


T = TypeVar("T")


def local_timestamp() -> str:
    return datetime.now().astimezone().isoformat()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def call_with_retry(
    operation: Callable[[], T],
    *,
    max_retries: int,
    retry_delay_seconds: int,
    attempt_log_path: Path | None = None,
    context: dict[str, Any] | None = None,
) -> T:
    if max_retries < 0:
        raise ValueError("max_retries must be greater than or equal to zero.")
    if retry_delay_seconds < 0:
        raise ValueError(
            "retry_delay_seconds must be greater than or equal to zero."
        )

    attempt_context = dict(context or {})
    total_attempts = max_retries + 1
    for attempt_number in range(1, total_attempts + 1):
        started_at = local_timestamp()
        started_clock = monotonic()
        try:
            result = operation()
        except Exception as exc:
            record = {
                **attempt_context,
                "attempt_number": attempt_number,
                "max_attempts": total_attempts,
                "started_at": started_at,
                "finished_at": local_timestamp(),
                "duration_seconds": round(monotonic() - started_clock, 6),
                "status": "failed",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "will_retry": attempt_number < total_attempts,
            }
            if attempt_log_path is not None:
                append_jsonl(attempt_log_path, record)
            if attempt_number >= total_attempts:
                raise
            print(
                f"API attempt {attempt_number}/{total_attempts} failed: "
                f"{type(exc).__name__}: {exc}. Retrying in "
                f"{retry_delay_seconds} seconds.",
                flush=True,
            )
            time.sleep(retry_delay_seconds)
            continue

        if attempt_log_path is not None:
            append_jsonl(
                attempt_log_path,
                {
                    **attempt_context,
                    "attempt_number": attempt_number,
                    "max_attempts": total_attempts,
                    "started_at": started_at,
                    "finished_at": local_timestamp(),
                    "duration_seconds": round(monotonic() - started_clock, 6),
                    "status": "succeeded",
                    "error_type": None,
                    "error_message": None,
                    "will_retry": False,
                },
            )
        return result

    raise AssertionError("The retry loop ended without returning or raising.")


def standalone_mode_result_directory(mode: str) -> Path:
    rq3_root = (
        Path(__file__).resolve().parents[2]
        / "experiment_results" / "RQ3" / "reruns"
    )
    batch_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    batch_directory = rq3_root / "linting_result" / batch_name
    suffix = 2
    while batch_directory.exists():
        batch_directory = (
            rq3_root / "linting_result" / f"{batch_name}_{suffix:02d}"
        )
        suffix += 1
    run_directory = batch_directory / "run1"
    for child_mode in ("syntax", "semantic"):
        (run_directory / child_mode).mkdir(parents=True, exist_ok=True)
    return run_directory / mode


__all__ = [
    "append_jsonl",
    "call_with_retry",
    "local_timestamp",
    "standalone_mode_result_directory",
    "write_json",
]
