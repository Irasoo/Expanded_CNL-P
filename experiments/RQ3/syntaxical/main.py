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

from cnlp_compiler.parser import ParserLike
from experiments.RQ3.experiment_runtime import (
    append_jsonl,
    local_timestamp,
    standalone_mode_result_directory,
    write_json,
)
from experiments.RQ3.syntaxical.linting_agent_based_on_llms.agent_linting import (
    syntax_issue_linting_agent,
)
from experiments.RQ3.syntaxical.task.task01_content_with_wrong_position import (
    task01_json_format,
)
from experiments.RQ3.syntaxical.task.task02_identifier_issue import task02_json_format
from experiments.RQ3.syntaxical.task.task03_structural_issue import task03_json_format
from experiments.RQ3.syntaxical.task.task04_sentence_pattern_issue import task04_json_format
from experiments.RQ3.syntaxical.task.task05_reference_issue import task05_json_format
from experiments.RQ3.syntaxical.task.task06_required_field_issue import task06_json_format


TASKS = (
    ("task01_content_with_wrong_position", task01_json_format),
    ("task02_identifier_issue", task02_json_format),
    ("task03_structural_issue", task03_json_format),
    ("task04_sentence_pattern_issue", task04_json_format),
    ("task05_reference_issue", task05_json_format),
    ("task06_required_field_issue", task06_json_format),
)
REVIEW_COLUMNS = ("position", "content", "reason")


def _parser_errors(result: object) -> list[dict[str, object]]:
    return [
        {
            "error_type": error.error_type,
            "start_line": error.start_line,
            "end_line": error.end_line,
            "error_content": error.value,
            "error_message": error.message,
            "is_fatal": error.is_fatal,
        }
        for error in result.errors
    ]


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
    output_directory = result_dir or standalone_mode_result_directory("syntax")
    output_directory.mkdir(parents=True, exist_ok=True)
    llm_output_path = output_directory / "llm_results.csv"
    parser_output_path = output_directory / "linting_results.csv"
    progress_path = output_directory / "progress.jsonl"
    attempt_log_path = output_directory / "api_attempts.jsonl"
    status_path = output_directory / "status.json"

    total_instances = sum(len(task["instances"]) for _, task in TASKS)
    write_json(
        status_path,
        {
            "mode": "syntax",
            "status": "running",
            "started_at": local_timestamp(),
            "task_count": len(TASKS),
            "instance_count": total_instances,
            "max_api_retries": max_api_retries,
            "maximum_api_attempts": max_api_retries + 1,
            "api_retry_delay_seconds": api_retry_delay_seconds,
            "parser": "cnlp_compiler.parser.ParserLike",
        },
    )

    parser = ParserLike()
    llm_results: list[dict[str, object]] = []
    parser_results: list[dict[str, object]] = []
    completed_instances = 0
    failed_llm_instances = 0
    failed_parser_instances = 0

    for task_name, task in TASKS:
        task_description = task["task_description"]
        for instance in task["instances"]:
            instance_id = instance["id"]
            print(
                f"syntax instance {instance_id} "
                f"({completed_instances + 1}/{total_instances})",
                flush=True,
            )
            common = {
                "task_name": task_name,
                "task_description": task_description,
                "instance_id": instance_id,
                "cnl_p": instance["cnl_p"],
                "sample_answer": instance["sample_answer"],
            }

            try:
                parser_errors = _parser_errors(
                    parser.syntax_analysis(instance["cnl_p"])
                )
                parser_status = "succeeded"
                parser_error = None
            except Exception as exc:
                parser_errors = None
                parser_status = "failed"
                parser_error = f"{type(exc).__name__}: {exc}"
                failed_parser_instances += 1

            try:
                llm_result = syntax_issue_linting_agent(
                    instance["cnl_p"],
                    clean_validation=False,
                    max_retries=max_api_retries,
                    retry_delay_seconds=api_retry_delay_seconds,
                    attempt_log_path=attempt_log_path,
                    attempt_context={
                        "mode": "syntax",
                        "task_name": task_name,
                        "instance_id": instance_id,
                    },
                )
                llm_status = "succeeded"
                llm_error = None
            except Exception as exc:
                llm_result = None
                llm_status = "failed"
                llm_error = f"{type(exc).__name__}: {exc}"
                failed_llm_instances += 1

            llm_results.append(
                {
                    **common,
                    "model": "gpt-5.6-sol",
                    "reasoning_effort": "high",
                    "status": llm_status,
                    "result": llm_result,
                    "api_error": llm_error,
                }
            )
            parser_results.append(
                {
                    **common,
                    "status": parser_status,
                    "result": parser_errors,
                    "parser_error": parser_error,
                }
            )
            completed_instances += 1
            append_jsonl(
                progress_path,
                {
                    "recorded_at": local_timestamp(),
                    "mode": "syntax",
                    "task_name": task_name,
                    "instance_id": instance_id,
                    "llm_status": llm_status,
                    "llm_api_error": llm_error,
                    "parser_status": parser_status,
                    "parser_error": parser_error,
                    "completed_instances": completed_instances,
                    "total_instances": total_instances,
                },
            )
            _write_csv_snapshot(llm_results, llm_output_path)
            _write_csv_snapshot(parser_results, parser_output_path)

    final_status = (
        "completed"
        if not failed_llm_instances and not failed_parser_instances
        else "completed_with_errors"
    )
    write_json(
        status_path,
        {
            "mode": "syntax",
            "status": final_status,
            "finished_at": local_timestamp(),
            "task_count": len(TASKS),
            "instance_count": total_instances,
            "completed_instances": completed_instances,
            "failed_llm_instances": failed_llm_instances,
            "failed_parser_instances": failed_parser_instances,
            "max_api_retries": max_api_retries,
            "maximum_api_attempts": max_api_retries + 1,
            "api_retry_delay_seconds": api_retry_delay_seconds,
            "parser": "cnlp_compiler.parser.ParserLike",
            "llm_results": str(llm_output_path.resolve()),
            "linting_results": str(parser_output_path.resolve()),
        },
    )
    print(f"The result has been saved to {llm_output_path.resolve()}")
    print(f"The result has been saved to {parser_output_path.resolve()}")
    return llm_output_path, parser_output_path


if __name__ == "__main__":
    run_experiment()
