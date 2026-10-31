from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from experiments._bootstrap import configure_source_paths
configure_source_paths()

from experiments.RQ3.experiment_runtime import (
    append_jsonl,
    local_timestamp,
    standalone_mode_result_directory,
    write_json,
)
from experiments.RQ3.semantic.tools import (
    CNLPDataloader,
    check_cnlp_by_linting,
    check_cnlp_by_llm,
)


TASKS = HERE / "tasks"
REVIEW_COLUMNS = (
    "Correct Location Identified (CLI)",
    "Correct but Erroneous Explanation (CEE)",
    "Explanation with Redundant Misjudgment (ERM)",
)


def _write_csv_snapshot(
    rows: list[dict[str, object]],
    destination: Path,
) -> None:
    data_frame = pd.DataFrame(rows)
    for column in REVIEW_COLUMNS:
        data_frame[column] = ""
    data_frame.to_csv(destination, index=False, encoding="utf-8")


def run_experiment(
    result_dir: Path | None = None,
    *,
    max_api_retries: int = 10,
    api_retry_delay_seconds: int = 15,
) -> tuple[Path, Path]:
    output_directory = result_dir or standalone_mode_result_directory(
        "semantic"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    llm_output_path = output_directory / "llm_results.csv"
    linting_output_path = output_directory / "linting_results.csv"
    progress_path = output_directory / "progress.jsonl"
    attempt_log_path = output_directory / "api_attempts.jsonl"
    status_path = output_directory / "status.json"

    task_paths = sorted(TASKS.glob("task*.json"))
    total_instances = sum(
        CNLPDataloader(str(TASKS), path.name).get_total_instances()
        for path in task_paths
    )
    write_json(
        status_path,
        {
            "mode": "semantic",
            "status": "running",
            "started_at": local_timestamp(),
            "task_count": len(task_paths),
            "instance_count": total_instances,
            "max_api_retries": max_api_retries,
            "maximum_api_attempts": max_api_retries + 1,
            "api_retry_delay_seconds": api_retry_delay_seconds,
        },
    )

    llm_results: list[dict[str, object]] = []
    linting_results: list[dict[str, object]] = []
    completed_instances = 0
    failed_llm_instances = 0
    failed_linting_instances = 0

    for task_path in task_paths:
        dataloader = CNLPDataloader(
            tasks_dir=str(TASKS),
            task_filename=task_path.name,
        )
        print(task_path.name, flush=True)
        for instance in dataloader.get_instance_iterator():
            instance_id = instance["id"]
            print(
                f"semantic instance {instance_id} "
                f"({completed_instances + 1}/{total_instances})",
                flush=True,
            )
            common = {
                "task_filename": task_path.name,
                "instance_id": instance_id,
                "agent_name": instance["agent_name"],
                "global_variable": instance["global_variable"],
                "api_info": instance["api_info"],
                "type_info": instance["schema"],
                "reference_version": instance["reference_version"],
                "cnlp_code": instance["cnlp"],
            }

            try:
                linting_errors = check_cnlp_by_linting(
                    cnlp=instance["cnlp"],
                    global_variable=instance["global_variable"],
                    api_info=instance["api_info"],
                    type_info=instance["schema"],
                )
                linting_status = "succeeded"
                linting_error = None
            except Exception as exc:
                linting_errors = None
                linting_status = "failed"
                linting_error = f"{type(exc).__name__}: {exc}"
                failed_linting_instances += 1

            try:
                llm_errors = check_cnlp_by_llm(
                    global_variable=instance["global_variable"],
                    api_info=instance["api_info"],
                    type_info=instance["schema"],
                    cnlp=instance["cnlp"],
                    clean_validation=False,
                    max_retries=max_api_retries,
                    retry_delay_seconds=api_retry_delay_seconds,
                    attempt_log_path=attempt_log_path,
                    attempt_context={
                        "mode": "semantic",
                        "task_filename": task_path.name,
                        "instance_id": instance_id,
                        "agent_name": instance["agent_name"],
                    },
                )
                llm_status = "succeeded"
                llm_error = None
            except Exception as exc:
                llm_errors = None
                llm_status = "failed"
                llm_error = f"{type(exc).__name__}: {exc}"
                failed_llm_instances += 1

            llm_results.append(
                {
                    **common,
                    "model": "gpt-5.6-sol",
                    "reasoning_effort": "high",
                    "status": llm_status,
                    "llm_errors": llm_errors,
                    "api_error": llm_error,
                }
            )
            linting_results.append(
                {
                    **common,
                    "status": linting_status,
                    "linting_errors": linting_errors,
                    "linting_error": linting_error,
                }
            )
            completed_instances += 1
            append_jsonl(
                progress_path,
                {
                    "recorded_at": local_timestamp(),
                    "mode": "semantic",
                    "task_filename": task_path.name,
                    "instance_id": instance_id,
                    "agent_name": instance["agent_name"],
                    "llm_status": llm_status,
                    "llm_api_error": llm_error,
                    "linting_status": linting_status,
                    "linting_error": linting_error,
                    "completed_instances": completed_instances,
                    "total_instances": total_instances,
                },
            )
            _write_csv_snapshot(llm_results, llm_output_path)
            _write_csv_snapshot(linting_results, linting_output_path)

    final_status = (
        "completed"
        if not failed_llm_instances and not failed_linting_instances
        else "completed_with_errors"
    )
    write_json(
        status_path,
        {
            "mode": "semantic",
            "status": final_status,
            "finished_at": local_timestamp(),
            "task_count": len(task_paths),
            "instance_count": total_instances,
            "completed_instances": completed_instances,
            "failed_llm_instances": failed_llm_instances,
            "failed_linting_instances": failed_linting_instances,
            "max_api_retries": max_api_retries,
            "maximum_api_attempts": max_api_retries + 1,
            "api_retry_delay_seconds": api_retry_delay_seconds,
            "llm_results": str(llm_output_path.resolve()),
            "linting_results": str(linting_output_path.resolve()),
        },
    )
    print(f"The result has been saved to {llm_output_path.resolve()}")
    print(f"The result has been saved to {linting_output_path.resolve()}")
    return llm_output_path, linting_output_path


if __name__ == "__main__":
    run_experiment()
