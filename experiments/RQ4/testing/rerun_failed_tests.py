from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RQ4_DIRECTORY = Path(__file__).resolve().parents[1]

from .execution_runner import (
    TestingResult,
    _aggregate_runtime_token_usage,
    _copy_attempt_outputs_to_run,
    _load_compilation_results,
    _load_input_groups,
    _positive_integer,
    _read_json,
    _run_one_execution_attempt,
    _validate_directory_name,
    _write_json,
    load_rq4_runtime_environment,
)


_INVALID_RERUN_ENVIRONMENT_REASON = "environment_setup_failure"
_INVALID_RERUN_ENVIRONMENT_DETAIL = (
    "This rerun was executed before rerun_failed_tests initialized the "
    "shared RQ4 runtime environment. It cannot be used to assess the "
    "generated Agent's original failure."
)
_INCOMPLETE_ATTEMPT_REASON = "missing_or_invalid_execution_log"


def _testing_directory(
    *,
    generation_id: str,
    testing_id: str,
    rq4_directory: Path = RQ4_DIRECTORY,
) -> Path:
    generation_id = _validate_directory_name(
        generation_id,
        "generation_id",
    )
    testing_id = _validate_directory_name(
        testing_id,
        "testing_id",
    )
    directory = (
        rq4_directory
        / "results"
        / generation_id
        / testing_id
    ).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(
            f"Testing batch not found: {directory}"
        )
    return directory


def _failed_run_logs(testing_directory: Path) -> list[Path]:
    """Find failed logical runs, excluding their retained Attempt logs."""
    failed_logs: list[Path] = []
    for path in testing_directory.glob(
        "*/*/*/run_*/execution_log.json"
    ):
        record = _read_json(path)
        if record.get("status") != "completed":
            failed_logs.append(path)
    return sorted(failed_logs)


def _compilation_result_map(
    generation_id: str,
    rq4_directory: Path = RQ4_DIRECTORY,
) -> dict[tuple[str, str, int], dict[str, Any]]:
    _, compilation_results = _load_compilation_results(
        rq4_directory=rq4_directory,
        generation_id=generation_id,
    )
    return {
        (
            result["case_name"],
            result["compilation_method"],
            result["trial_index"],
        ): result
        for result in compilation_results
        if result["status"] == "success"
    }


def _input_group_for_rerun(
    *,
    case_name: str,
    input_group_name: str,
    run_directory: Path,
    rq4_directory: Path = RQ4_DIRECTORY,
) -> tuple[Path, dict[str, Any]]:
    input_path, input_groups = _load_input_groups(
        case_directory=rq4_directory / "cases" / case_name,
        expected_case_name=case_name,
    )
    groups_by_name = {
        group["name"]: group
        for group in input_groups
    }
    if input_group_name not in groups_by_name:
        raise ValueError(
            f"Input group {input_group_name!r} no longer exists for "
            f"case {case_name!r}."
        )

    # Reuse the exact original input strings from this failed run. The current
    # case YAML supplies only the timeout and group identity, so later edits to
    # the YAML cannot silently change the experiment being rerun.
    inputs_record = _read_json(run_directory / "inputs.json")
    original_inputs = inputs_record.get("original_inputs")
    if not (
        isinstance(original_inputs, list)
        and all(isinstance(value, str) for value in original_inputs)
    ):
        raise ValueError(
            f"Original inputs are unavailable: {run_directory / 'inputs.json'}"
        )

    input_group = dict(groups_by_name[input_group_name])
    input_group["inputs"] = list(original_inputs)
    return input_path, input_group


def _attempt_directories(run_directory: Path) -> list[Path]:
    attempts_directory = run_directory / "attempts"
    if not attempts_directory.is_dir():
        raise ValueError(
            "This result predates Attempt preservation and cannot be rerun "
            f"in place safely: {run_directory}"
        )
    attempt_directories = sorted(
        path
        for path in attempts_directory.glob("attempt_*")
        if path.is_dir()
    )
    if not attempt_directories:
        raise ValueError(
            f"No preserved execution Attempt exists: {run_directory}"
        )
    return attempt_directories


def _next_attempt_directory(run_directory: Path) -> Path:
    attempt_directories = _attempt_directories(run_directory)
    indexes: list[int] = []
    for directory in attempt_directories:
        suffix = directory.name.removeprefix("attempt_")
        if not suffix.isdigit():
            raise ValueError(
                f"Invalid Attempt directory name: {directory}"
            )
        indexes.append(int(suffix))
    return (
        run_directory
        / "attempts"
        / f"attempt_{max(indexes) + 1:03d}"
    )


def _is_environment_setup_failure(record: dict[str, Any]) -> bool:
    exception = record.get("runtime_exception")
    if not isinstance(exception, dict):
        return False
    message = exception.get("message")
    if not isinstance(message, str):
        return False
    return (
        "Missing OPENAI_API_KEY" in message
        or "Missing runtime configuration:" in message
        or "Missing runtime model configuration:" in message
    )


def _mark_invalid_environment_rerun_attempts(
    run_directory: Path,
) -> int:
    """Label rerun attempts with missing runtime configuration."""
    marked_attempt_names: set[str] = set()
    marked_at = datetime.now(timezone.utc).isoformat()

    for attempt_directory in _attempt_directories(run_directory):
        suffix = attempt_directory.name.removeprefix("attempt_")
        if not suffix.isdigit() or int(suffix) <= 1:
            continue
        attempt_log_path = attempt_directory / "execution_log.json"
        record = _read_json(attempt_log_path)
        if not _is_environment_setup_failure(record):
            continue
        if record.get("rerun_invalid_reason") == _INVALID_RERUN_ENVIRONMENT_REASON:
            continue

        record["rerun_validity"] = "invalid"
        record["rerun_invalid_reason"] = _INVALID_RERUN_ENVIRONMENT_REASON
        record["rerun_invalid_detail"] = _INVALID_RERUN_ENVIRONMENT_DETAIL
        record["rerun_invalid_marked_at"] = marked_at
        _write_json(attempt_log_path, record)
        marked_attempt_names.add(attempt_directory.name)

    if not marked_attempt_names:
        return 0

    execution_log_path = run_directory / "execution_log.json"
    run_record = _read_json(execution_log_path)
    attempts = run_record.get("attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            directory = attempt.get("directory")
            if not isinstance(directory, str):
                continue
            attempt_name = directory.replace("\\", "/").rsplit("/", 1)[-1]
            if attempt_name not in marked_attempt_names:
                continue
            attempt["rerun_validity"] = "invalid"
            attempt["rerun_invalid_reason"] = _INVALID_RERUN_ENVIRONMENT_REASON
            attempt["rerun_invalid_detail"] = _INVALID_RERUN_ENVIRONMENT_DETAIL
            attempt["rerun_invalid_marked_at"] = marked_at
        _write_json(execution_log_path, run_record)
    return len(marked_attempt_names)


def _finalize_rerun(
    *,
    run_directory: Path,
    previous_record: dict[str, Any],
    expected_attempt_directory: Path | None = None,
) -> TestingResult:
    attempt_directories = _attempt_directories(run_directory)
    attempt_records: list[tuple[Path, dict[str, Any]]] = []
    incomplete_attempt_directories: list[Path] = []
    for attempt_directory in attempt_directories:
        record = _read_json(
            attempt_directory / "execution_log.json"
        )
        if not record:
            incomplete_attempt_directories.append(attempt_directory)
            continue
        attempt_records.append((attempt_directory, record))

    if (
        expected_attempt_directory is not None
        and expected_attempt_directory in incomplete_attempt_directories
    ):
        raise ValueError(
            "The current rerun did not produce a valid execution log: "
            f"{expected_attempt_directory / 'execution_log.json'}"
        )
    if not attempt_records:
        raise ValueError(
            f"No valid execution Attempt exists: {run_directory}"
        )

    final_attempt_directory, final_record = attempt_records[-1]
    _copy_attempt_outputs_to_run(
        attempt_directory=final_attempt_directory,
        run_directory=run_directory,
        final_record=final_record,
    )

    timeout_usages = [
        record["runtime_token_usage"]
        for _, record in attempt_records
        if record.get("status") == "timeout"
        and isinstance(record.get("runtime_token_usage"), dict)
    ]
    failed_usages = [
        record["runtime_token_usage"]
        for _, record in attempt_records
        if record.get("status") == "failed"
        and isinstance(record.get("runtime_token_usage"), dict)
    ]
    all_usages = [
        (
            record["runtime_token_usage"]
            if isinstance(record.get("runtime_token_usage"), dict)
            else {}
        )
        for _, record in attempt_records
    ] + [{} for _ in incomplete_attempt_directories]
    successful_usage = (
        final_record.get("runtime_token_usage")
        if final_record.get("status") == "completed"
        else None
    )

    final_record["result_directory"] = str(run_directory)
    final_record["selected_attempt"] = final_attempt_directory.relative_to(run_directory).as_posix()
    final_record["attempt_count"] = len(attempt_directories)
    final_record["valid_attempt_count"] = len(attempt_records)
    final_record["incomplete_attempt_count"] = len(
        incomplete_attempt_directories
    )
    final_record["timeout_max_retries"] = previous_record.get(
        "timeout_max_retries",
        0,
    )
    final_record["timeout_retry_delay_seconds"] = previous_record.get(
        "timeout_retry_delay_seconds",
        0,
    )
    final_record["runtime_token_usage"] = successful_usage
    final_record["successful_runtime_token_usage"] = successful_usage
    final_record["retry_overhead_runtime_token_usage"] = (
        _aggregate_runtime_token_usage(timeout_usages)
    )
    final_record["failed_runtime_token_usage"] = (
        _aggregate_runtime_token_usage(failed_usages)
    )
    final_record["observed_total_runtime_token_usage"] = (
        _aggregate_runtime_token_usage(all_usages)
    )
    runtime_usage_path = run_directory / "runtime_token_usage.json"
    final_record["runtime_token_usage_file"] = str(runtime_usage_path)
    final_record["observed_attempt_duration_seconds"] = round(
        sum(
            float(record.get("duration_seconds") or 0)
            for _, record in attempt_records
        ),
        6,
    )
    final_record["manual_rerun_count"] = int(
        previous_record.get("manual_rerun_count", 0)
    ) + 1
    final_record["last_manual_rerun_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    records_by_directory = dict(attempt_records)
    final_record["attempts"] = []
    for attempt_directory in attempt_directories:
        attempt_index = int(
            attempt_directory.name.removeprefix("attempt_")
        )
        record = records_by_directory.get(attempt_directory)
        if record is None:
            final_record["attempts"].append(
                {
                    "attempt_index": attempt_index,
                    "status": "incomplete",
                    "duration_seconds": None,
                    "directory": str(
                        attempt_directory.relative_to(run_directory)
                    ),
                    "execution_log": None,
                    "runtime_token_usage": None,
                    "runtime_exception": None,
                    "rerun_validity": "invalid",
                    "rerun_invalid_reason": _INCOMPLETE_ATTEMPT_REASON,
                }
            )
            continue
        final_record["attempts"].append(
            {
                "attempt_index": attempt_index,
                "status": record.get("status"),
                "duration_seconds": record.get("duration_seconds"),
                "directory": str(
                    attempt_directory.relative_to(run_directory)
                ),
                "execution_log": str(
                    (
                        attempt_directory / "execution_log.json"
                    ).relative_to(run_directory)
                ),
                "runtime_token_usage": record.get("runtime_token_usage"),
                "runtime_exception": record.get("runtime_exception"),
                **{
                    field_name: record[field_name]
                    for field_name in (
                        "rerun_validity",
                        "rerun_invalid_reason",
                        "rerun_invalid_detail",
                        "rerun_invalid_marked_at",
                    )
                    if field_name in record
                },
            }
        )

    if successful_usage is not None:
        _write_json(runtime_usage_path, successful_usage)
    else:
        runtime_usage_path.unlink(missing_ok=True)
    execution_log_path = run_directory / "execution_log.json"
    _write_json(execution_log_path, final_record)

    return {
        "generation_id": final_record["generation_id"],
        "testing_id": final_record["testing_id"],
        "case_name": final_record["case_name"],
        "compilation_method": final_record["compilation_method"],
        "compilation_trial_name": Path(
            final_record["compilation_trial_directory"]
        ).name,
        "input_group_name": final_record["input_group_name"],
        "run_index": final_record["run_index"],
        "run_count": final_record["run_count"],
        "status": final_record["status"],
        "result_directory": run_directory,
        "execution_log_path": execution_log_path,
    }


def rerun_failed_tests(
    generation_id: str,
    testing_id: str,
    *,
    rq4_directory: Path = RQ4_DIRECTORY,
    max_parallel_executions: int = 1,
) -> list[TestingResult]:
    """Rerun every currently failed execution in one existing test batch.

    The two identifiers are the only selection parameters. Completed runs are
    never executed again. Each rerun becomes a new preserved Attempt under the
    original run directory, and its stable execution_log.json is updated to
    the latest outcome for ordinary statistics and review.
    """
    max_parallel_executions = _positive_integer(
        max_parallel_executions,
        "max_parallel_executions",
    )
    load_rq4_runtime_environment(rq4_directory)
    testing_directory = _testing_directory(
        generation_id=generation_id,
        testing_id=testing_id,
        rq4_directory=rq4_directory,
    )
    failed_logs = _failed_run_logs(testing_directory)
    if not failed_logs:
        print(
            "[Testing rerun] No failed executions were found in "
            f"{generation_id}/{testing_id}.",
            flush=True,
        )
        return []

    invalidated_attempt_count = sum(
        _mark_invalid_environment_rerun_attempts(path.parent)
        for path in failed_logs
    )
    if invalidated_attempt_count:
        print(
            "[Testing rerun] Marked "
            f"{invalidated_attempt_count} previous rerun attempt(s) as invalid "
            "because their RQ4 runtime environment was not initialized.",
            flush=True,
        )

    compilation_results = _compilation_result_map(generation_id, rq4_directory)
    print(
        f"[Testing rerun] {generation_id}/{testing_id}: found "
        f"{len(failed_logs)} failed execution(s).",
        flush=True,
    )

    prepared_tasks: list[dict[str, Any]] = []
    for execution_number, execution_log_path in enumerate(
        failed_logs,
        start=1,
    ):
        previous_record = _read_json(execution_log_path)
        run_directory = execution_log_path.parent
        identity = (
            previous_record.get("case_name"),
            previous_record.get("compilation_method"),
            previous_record.get("compilation_trial_index"),
        )
        compilation_result = compilation_results.get(identity)
        if compilation_result is None:
            raise ValueError(
                "Cannot match the failed execution to a successful "
                f"compilation Trial: {execution_log_path}"
            )

        input_path, input_group = _input_group_for_rerun(
            case_name=previous_record["case_name"],
            input_group_name=previous_record["input_group_name"],
            run_directory=run_directory,
            rq4_directory=rq4_directory,
        )
        attempt_directory = _next_attempt_directory(run_directory)
        prefix = (
            f"[Testing rerun][{previous_record['case_name']}]"
            f"[{compilation_result['trial_directory'].name}]"
            f"[{previous_record['input_group_name']}]"
            f"[Run {previous_record['run_index']} in "
            f"{previous_record['run_count']}; task {execution_number} in "
            f"{len(failed_logs)}]"
        )
        prepared_tasks.append(
            {
                "execution_number": execution_number,
                "prefix": prefix,
                "run_directory": run_directory,
                "previous_record": previous_record,
                "compilation_result": compilation_result,
                "input_path": input_path,
                "input_group": input_group,
                "attempt_directory": attempt_directory,
            }
        )

    def run_prepared_task(task: dict[str, Any]) -> tuple[int, TestingResult]:
        prefix = task["prefix"]
        previous_record = task["previous_record"]
        print(f"{prefix}: started", flush=True)
        _run_one_execution_attempt(
            generation_id=generation_id,
            testing_id=testing_id,
            compilation_result=task["compilation_result"],
            input_path=task["input_path"],
            input_group=task["input_group"],
            run_index=previous_record["run_index"],
            run_count=previous_record["run_count"],
            run_directory=task["attempt_directory"],
        )
        result = _finalize_rerun(
            run_directory=task["run_directory"],
            previous_record=previous_record,
            expected_attempt_directory=task["attempt_directory"],
        )
        print(
            f"{prefix}: {result['status']}\n"
            f"  Result: {result['result_directory']}",
            flush=True,
        )
        return task["execution_number"], result

    results_by_number: dict[int, TestingResult] = {}
    with ThreadPoolExecutor(max_workers=max_parallel_executions) as executor:
        futures = {
            executor.submit(run_prepared_task, task): task
            for task in prepared_tasks
        }
        for future in as_completed(futures):
            task = futures[future]
            try:
                execution_number, result = future.result()
            except Exception as exc:
                execution_number = task["execution_number"]
                previous_record = task["previous_record"]
                print(
                    f"{task['prefix']}: rerun orchestration failed: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                result = {
                    "generation_id": generation_id,
                    "testing_id": testing_id,
                    "case_name": previous_record["case_name"],
                    "compilation_method": previous_record[
                        "compilation_method"
                    ],
                    "compilation_trial_name": task[
                        "compilation_result"
                    ]["trial_directory"].name,
                    "input_group_name": previous_record[
                        "input_group_name"
                    ],
                    "run_index": previous_record["run_index"],
                    "run_count": previous_record["run_count"],
                    "status": "failed",
                    "result_directory": task["run_directory"],
                    "execution_log_path": (
                        task["run_directory"] / "execution_log.json"
                    ),
                }
            results_by_number[execution_number] = result

    results = [
        results_by_number[number]
        for number in range(1, len(prepared_tasks) + 1)
    ]

    completed_count = sum(
        result["status"] == "completed"
        for result in results
    )
    print(
        f"[Testing rerun] Finished: {completed_count} completed, "
        f"{len(results) - completed_count} still failed.",
        flush=True,
    )
    return results
