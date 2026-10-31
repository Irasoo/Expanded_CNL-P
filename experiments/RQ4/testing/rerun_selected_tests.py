from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


RQ4_DIRECTORY = Path(__file__).resolve().parents[1]

from .execution_runner import (
    TestingResult,
    _positive_integer,
    _run_one_execution_attempt,
    load_rq4_runtime_environment,
)
from .rerun_failed_tests import (
    _compilation_result_map,
    _finalize_rerun,
    _input_group_for_rerun,
    _mark_invalid_environment_rerun_attempts,
    _next_attempt_directory,
    _read_json,
    _testing_directory,
)


def _resolve_run_directory(
    *,
    testing_directory: Path,
    raw_directory: str,
) -> Path:
    if not isinstance(raw_directory, str) or not raw_directory.strip():
        raise ValueError("Every RUN_DIRECTORIES entry must be a non-empty string.")

    requested_path = Path(raw_directory)
    if requested_path.is_absolute():
        raise ValueError(
            "RUN_DIRECTORIES entries must be relative to the selected testing batch."
        )
    run_directory = (testing_directory / requested_path).resolve()
    try:
        relative_path = run_directory.relative_to(testing_directory)
    except ValueError as exc:
        raise ValueError(
            "RUN_DIRECTORIES entry escapes the selected testing batch: "
            f"{raw_directory!r}"
        ) from exc

    if len(relative_path.parts) != 4 or not relative_path.name.startswith("run_"):
        raise ValueError(
            "RUN_DIRECTORIES entries must use the exact form "
            "<case>/<method_trial>/<input_group>/run_00x: "
            f"{raw_directory!r}"
        )
    execution_log_path = run_directory / "execution_log.json"
    if not execution_log_path.is_file():
        raise FileNotFoundError(
            f"Execution log not found for selected run: {execution_log_path}"
        )
    return run_directory


def rerun_selected_tests(
    *,
    generation_id: str,
    testing_id: str,
    run_directories: list[str],
    rq4_directory: Path = RQ4_DIRECTORY,
    max_parallel_executions: int = 1,
) -> list[TestingResult]:
    """Append one new Attempt to each explicitly selected logical Run.

    The function reuses the original generated Agent, original inputs, and
    existing run index. It never overwrites prior Attempt directories.
    """
    if not run_directories:
        raise ValueError("run_directories must contain at least one selected Run.")
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
    selected_runs = [
        _resolve_run_directory(
            testing_directory=testing_directory,
            raw_directory=raw_directory,
        )
        for raw_directory in run_directories
    ]
    if len(set(selected_runs)) != len(selected_runs):
        raise ValueError("run_directories must not contain duplicate paths.")

    compilation_results = _compilation_result_map(generation_id, rq4_directory)
    prepared_tasks: list[dict[str, Any]] = []
    for execution_number, run_directory in enumerate(selected_runs, start=1):
        execution_log_path = run_directory / "execution_log.json"
        previous_record = _read_json(execution_log_path)
        identity = (
            previous_record.get("case_name"),
            previous_record.get("compilation_method"),
            previous_record.get("compilation_trial_index"),
        )
        compilation_result = compilation_results.get(identity)
        if compilation_result is None:
            raise ValueError(
                "Cannot match the selected execution to a successful compilation "
                f"Trial: {execution_log_path}"
            )

        _mark_invalid_environment_rerun_attempts(run_directory)
        input_path, input_group = _input_group_for_rerun(
            case_name=previous_record["case_name"],
            input_group_name=previous_record["input_group_name"],
            run_directory=run_directory,
            rq4_directory=rq4_directory,
        )
        attempt_directory = _next_attempt_directory(run_directory)
        prefix = (
            f"[Testing selected rerun][{previous_record['case_name']}]"
            f"[{compilation_result['trial_directory'].name}]"
            f"[{previous_record['input_group_name']}]"
            f"[Run {previous_record['run_index']} in "
            f"{previous_record['run_count']}; task {execution_number} in "
            f"{len(selected_runs)}]"
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

    completed_count = sum(result["status"] == "completed" for result in results)
    print(
        f"[Testing selected rerun] Finished: {completed_count} completed, "
        f"{len(results) - completed_count} still failed.",
        flush=True,
    )
    return results
