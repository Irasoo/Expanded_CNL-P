from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from experiments._bootstrap import configure_source_paths
configure_source_paths()

from cnlp_compiler.parser import ParserLike
from cnlp_compiler.semantic_analysis import SemanticAnalyzer
from experiments.RQ3.experiment_runtime import append_jsonl, local_timestamp, write_json
from experiments.RQ3.syntaxical.task.benchmark_case import diet_advisor, travel_assistant


# Right-click Run configuration. Enable either dataset or both datasets.
RUN_SYNTAX = True
RUN_SEMANTIC = True

# Each launch validates every selected clean template three independent times.
REPEAT_COUNT = 3

# Each run performs both the deterministic check and the LLM check.
RUN_DETERMINISTIC_VALIDATION = True
RUN_LLM_VALIDATION = True

# One initial API request plus at most 10 retries, 15 seconds apart.
API_RETRY_DELAY_SECONDS = 15
API_MAX_RETRIES = 10

RESULT_ROOT = (
    WORKSPACE_ROOT / "experiment_results" / "RQ3" / "reruns"
    / "template_validation_result"
)
LLM_MODEL = "gpt-5.6-sol"
LLM_REASONING_EFFORT = "high"

SYNTAX_TEMPLATES = (
    ("diet_advisor", diet_advisor),
    ("travel_assistant", travel_assistant),
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


def _parse_llm_errors(content: str) -> list[Any]:
    normalized = content.strip()
    if not normalized:
        raise ValueError("LLM validation returned empty message content.")
    if normalized.startswith("```"):
        lines = normalized.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
    parsed = json.loads(normalized)
    if not isinstance(parsed, list):
        raise ValueError("LLM validation result must be a JSON list.")
    return parsed


def _write_result_snapshot(
    path: Path,
    *,
    method: str,
    rows: list[dict[str, Any]],
) -> None:
    write_json(
        path,
        {
            "updated_at": local_timestamp(),
            "method": method,
            "result_count": len(rows),
            "passed_count": sum(bool(row.get("passed")) for row in rows),
            "results": rows,
        },
    )


def _write_mode_status(
    directory: Path,
    *,
    mode: str,
    status: str,
    deterministic_results: list[dict[str, Any]],
    llm_results: list[dict[str, Any]],
) -> None:
    all_results = deterministic_results + llm_results
    write_json(
        directory / "status.json",
        {
            "mode": mode,
            "status": status,
            "recorded_at": local_timestamp(),
            "deterministic_validation_enabled": (
                RUN_DETERMINISTIC_VALIDATION
            ),
            "llm_validation_enabled": RUN_LLM_VALIDATION,
            "result_count": len(all_results),
            "passed_count": sum(
                bool(result.get("passed")) for result in all_results
            ),
            "failed_count": sum(
                not bool(result.get("passed")) for result in all_results
            ),
        },
    )


def _validation_status(results: list[dict[str, Any]]) -> str:
    return (
        "completed"
        if all(bool(result.get("passed")) for result in results)
        else "completed_with_errors"
    )


def _validate_syntax(
    output_directory: Path,
    *,
    run_index: int,
) -> str:
    output_directory.mkdir(parents=True, exist_ok=True)
    deterministic_path = output_directory / "parser_results.json"
    llm_path = output_directory / "llm_results.json"
    progress_path = output_directory / "progress.jsonl"
    attempt_log_path = output_directory / "api_attempts.jsonl"
    deterministic_results: list[dict[str, Any]] = []
    llm_results: list[dict[str, Any]] = []

    if RUN_DETERMINISTIC_VALIDATION:
        parser = ParserLike()
        for template_index, (template_name, cnlp) in enumerate(
            SYNTAX_TEMPLATES,
            start=1,
        ):
            try:
                parse_result = parser.syntax_analysis(cnl_p=cnlp)
                parser_errors = [
                    {
                        "error_type": error.error_type,
                        "start_line": error.start_line,
                        "end_line": error.end_line,
                        "error_content": error.value,
                        "error_message": error.message,
                        "is_fatal": error.is_fatal,
                    }
                    for error in parse_result.errors
                ]
                row = {
                    "template_name": template_name,
                    "status": "succeeded",
                    "parser_errors": parser_errors,
                    "execution_error": None,
                    "passed": not parser_errors,
                }
            except Exception as exc:
                row = {
                    "template_name": template_name,
                    "status": "failed",
                    "parser_errors": None,
                    "execution_error": f"{type(exc).__name__}: {exc}",
                    "passed": False,
                }
            deterministic_results.append(row)
            _write_result_snapshot(
                deterministic_path,
                method="parser",
                rows=deterministic_results,
            )
            append_jsonl(
                progress_path,
                {
                    "recorded_at": local_timestamp(),
                    "run_index": run_index,
                    "mode": "syntax",
                    "method": "parser",
                    "template_index": template_index,
                    "template_count": len(SYNTAX_TEMPLATES),
                    "template_name": template_name,
                    "status": row["status"],
                    "passed": row["passed"],
                },
            )

    if RUN_LLM_VALIDATION:
        from experiments.RQ3.syntaxical.linting_agent_based_on_llms.agent_linting import (
            syntax_issue_linting_agent,
        )

        for template_index, (template_name, cnlp) in enumerate(
            SYNTAX_TEMPLATES,
            start=1,
        ):
            print(
                f"run{run_index} Syntax LLM "
                f"[{template_index}/{len(SYNTAX_TEMPLATES)}]: "
                f"{template_name}",
                flush=True,
            )
            try:
                raw_result = syntax_issue_linting_agent(
                    cnlp,
                    clean_validation=True,
                    max_retries=API_MAX_RETRIES,
                    retry_delay_seconds=API_RETRY_DELAY_SECONDS,
                    attempt_log_path=attempt_log_path,
                    attempt_context={
                        "run_index": run_index,
                        "mode": "syntax",
                        "template_name": template_name,
                    },
                )
                llm_errors = _parse_llm_errors(raw_result)
                row = {
                    "template_name": template_name,
                    "model": LLM_MODEL,
                    "reasoning_effort": LLM_REASONING_EFFORT,
                    "status": "succeeded",
                    "llm_errors": llm_errors,
                    "raw_result": raw_result,
                    "api_error": None,
                    "passed": not llm_errors,
                }
            except Exception as exc:
                row = {
                    "template_name": template_name,
                    "model": LLM_MODEL,
                    "reasoning_effort": LLM_REASONING_EFFORT,
                    "status": "failed",
                    "llm_errors": None,
                    "raw_result": None,
                    "api_error": f"{type(exc).__name__}: {exc}",
                    "passed": False,
                }
            llm_results.append(row)
            _write_result_snapshot(
                llm_path,
                method="llm",
                rows=llm_results,
            )
            append_jsonl(
                progress_path,
                {
                    "recorded_at": local_timestamp(),
                    "run_index": run_index,
                    "mode": "syntax",
                    "method": "llm",
                    "template_index": template_index,
                    "template_count": len(SYNTAX_TEMPLATES),
                    "template_name": template_name,
                    "status": row["status"],
                    "passed": row["passed"],
                    "api_error": row["api_error"],
                },
            )

    all_results = deterministic_results + llm_results
    status = _validation_status(all_results)
    _write_mode_status(
        output_directory,
        mode="syntax",
        status=status,
        deterministic_results=deterministic_results,
        llm_results=llm_results,
    )
    return status


def _validate_semantic(
    output_directory: Path,
    *,
    run_index: int,
) -> str:
    from experiments.RQ3.semantic.validate_dataset_templates import _load_cases

    cases = _load_cases()
    output_directory.mkdir(parents=True, exist_ok=True)
    deterministic_path = output_directory / "static_analysis_results.json"
    llm_path = output_directory / "llm_results.json"
    progress_path = output_directory / "progress.jsonl"
    attempt_log_path = output_directory / "api_attempts.jsonl"
    deterministic_results: list[dict[str, Any]] = []
    llm_results: list[dict[str, Any]] = []

    if RUN_DETERMINISTIC_VALIDATION:
        parser = ParserLike()
        analyzer = SemanticAnalyzer()
        for template_index, case in enumerate(cases, start=1):
            label = f"{case['agent_name']}/{case['template_name']}"
            try:
                parse_result = parser.syntax_analysis(cnl_p=case["cnlp"])
                parser_errors = [
                    {
                        "error_type": error.error_type,
                        "start_line": error.start_line,
                        "end_line": error.end_line,
                        "error_content": error.value,
                        "error_message": error.message,
                        "is_fatal": error.is_fatal,
                    }
                    for error in parse_result.errors
                ]
                semantic_errors: list[dict[str, Any]] = []
                if not parser_errors:
                    report = analyzer.analyze(
                        parse_result.value,
                        global_variables=case["global_variable"],
                        apis=case["api_info"],
                        schema=case["schema"],
                    )
                    semantic_errors = [
                        {
                            "error_code": diagnostic.code,
                            "error_path": diagnostic.path,
                            "error_reason": diagnostic.message,
                        }
                        for diagnostic in report.diagnostics
                    ]
                row = {
                    "agent_name": case["agent_name"],
                    "template_name": case["template_name"],
                    "status": "succeeded",
                    "parser_errors": parser_errors,
                    "semantic_errors": semantic_errors,
                    "execution_error": None,
                    "passed": not parser_errors and not semantic_errors,
                }
            except Exception as exc:
                row = {
                    "agent_name": case["agent_name"],
                    "template_name": case["template_name"],
                    "status": "failed",
                    "parser_errors": None,
                    "semantic_errors": None,
                    "execution_error": f"{type(exc).__name__}: {exc}",
                    "passed": False,
                }
            deterministic_results.append(row)
            _write_result_snapshot(
                deterministic_path,
                method="parser_and_semantic_analysis",
                rows=deterministic_results,
            )
            append_jsonl(
                progress_path,
                {
                    "recorded_at": local_timestamp(),
                    "run_index": run_index,
                    "mode": "semantic",
                    "method": "parser_and_semantic_analysis",
                    "template_index": template_index,
                    "template_count": len(cases),
                    "template_name": label,
                    "status": row["status"],
                    "passed": row["passed"],
                },
            )

    if RUN_LLM_VALIDATION:
        from experiments.RQ3.semantic.tools import check_cnlp_by_llm

        for template_index, case in enumerate(cases, start=1):
            label = f"{case['agent_name']}/{case['template_name']}"
            print(
                f"run{run_index} Semantic LLM "
                f"[{template_index}/{len(cases)}]: {label}",
                flush=True,
            )
            try:
                raw_result = check_cnlp_by_llm(
                    global_variable=case["global_variable"],
                    api_info=case["api_info"],
                    type_info=case["schema"],
                    cnlp=case["cnlp"],
                    clean_validation=True,
                    max_retries=API_MAX_RETRIES,
                    retry_delay_seconds=API_RETRY_DELAY_SECONDS,
                    attempt_log_path=attempt_log_path,
                    attempt_context={
                        "run_index": run_index,
                        "mode": "semantic",
                        "agent_name": case["agent_name"],
                        "template_name": case["template_name"],
                    },
                )
                llm_errors = _parse_llm_errors(raw_result)
                row = {
                    "agent_name": case["agent_name"],
                    "template_name": case["template_name"],
                    "model": LLM_MODEL,
                    "reasoning_effort": LLM_REASONING_EFFORT,
                    "status": "succeeded",
                    "llm_errors": llm_errors,
                    "raw_result": raw_result,
                    "api_error": None,
                    "passed": not llm_errors,
                }
            except Exception as exc:
                row = {
                    "agent_name": case["agent_name"],
                    "template_name": case["template_name"],
                    "model": LLM_MODEL,
                    "reasoning_effort": LLM_REASONING_EFFORT,
                    "status": "failed",
                    "llm_errors": None,
                    "raw_result": None,
                    "api_error": f"{type(exc).__name__}: {exc}",
                    "passed": False,
                }
            llm_results.append(row)
            _write_result_snapshot(
                llm_path,
                method="llm",
                rows=llm_results,
            )
            append_jsonl(
                progress_path,
                {
                    "recorded_at": local_timestamp(),
                    "run_index": run_index,
                    "mode": "semantic",
                    "method": "llm",
                    "template_index": template_index,
                    "template_count": len(cases),
                    "template_name": label,
                    "status": row["status"],
                    "passed": row["passed"],
                    "api_error": row["api_error"],
                },
            )

    all_results = deterministic_results + llm_results
    status = _validation_status(all_results)
    _write_mode_status(
        output_directory,
        mode="semantic",
        status=status,
        deterministic_results=deterministic_results,
        llm_results=llm_results,
    )
    return status


def _not_selected(directory: Path, mode: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    write_json(
        directory / "status.json",
        {
            "mode": mode,
            "status": "not_selected",
            "recorded_at": local_timestamp(),
        },
    )
    return "not_selected"


def _validate_configuration() -> None:
    if not RUN_SYNTAX and not RUN_SEMANTIC:
        raise ValueError("At least one validation dataset must be enabled.")
    if not RUN_DETERMINISTIC_VALIDATION and not RUN_LLM_VALIDATION:
        raise ValueError("At least one validation method must be enabled.")
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
    run_records: list[dict[str, Any]] = []

    print(
        f"Original template validation batch: {batch_directory.resolve()}",
        flush=True,
    )
    for run_index in range(1, REPEAT_COUNT + 1):
        run_directory = batch_directory / f"run{run_index}"
        syntax_directory = run_directory / "syntax"
        semantic_directory = run_directory / "semantic"
        syntax_directory.mkdir(parents=True)
        semantic_directory.mkdir(parents=True)
        run_record: dict[str, Any] = {
            "run_index": run_index,
            "status": "running",
            "started_at": local_timestamp(),
        }
        run_records.append(run_record)
        print(f"Starting validation run{run_index}/{REPEAT_COUNT}", flush=True)

        try:
            run_record["syntax_status"] = (
                _validate_syntax(syntax_directory, run_index=run_index)
                if RUN_SYNTAX
                else _not_selected(syntax_directory, "syntax")
            )
        except Exception as exc:
            run_record["syntax_status"] = "failed"
            run_record["syntax_error"] = f"{type(exc).__name__}: {exc}"
            write_json(
                syntax_directory / "status.json",
                {
                    "mode": "syntax",
                    "status": "failed",
                    "recorded_at": local_timestamp(),
                    "error": run_record["syntax_error"],
                },
            )

        try:
            run_record["semantic_status"] = (
                _validate_semantic(semantic_directory, run_index=run_index)
                if RUN_SEMANTIC
                else _not_selected(semantic_directory, "semantic")
            )
        except Exception as exc:
            run_record["semantic_status"] = "failed"
            run_record["semantic_error"] = f"{type(exc).__name__}: {exc}"
            write_json(
                semantic_directory / "status.json",
                {
                    "mode": "semantic",
                    "status": "failed",
                    "recorded_at": local_timestamp(),
                    "error": run_record["semantic_error"],
                },
            )

        statuses = (
            run_record["syntax_status"],
            run_record["semantic_status"],
        )
        run_record["status"] = (
            "completed"
            if all(
                status in {"completed", "not_selected"}
                for status in statuses
            )
            else "completed_with_errors"
        )
        run_record["finished_at"] = local_timestamp()
        write_json(run_directory / "run_metadata.json", run_record)
        write_json(
            batch_metadata_path,
            {
                "status": "running",
                "started_at": batch_started_at,
                "run_syntax": RUN_SYNTAX,
                "run_semantic": RUN_SEMANTIC,
                "repeat_count": REPEAT_COUNT,
                "run_deterministic_validation": (
                    RUN_DETERMINISTIC_VALIDATION
                ),
                "run_llm_validation": RUN_LLM_VALIDATION,
                "model": LLM_MODEL,
                "reasoning_effort": LLM_REASONING_EFFORT,
                "api_retry_delay_seconds": API_RETRY_DELAY_SECONDS,
                "api_max_retries": API_MAX_RETRIES,
                "maximum_api_attempts": API_MAX_RETRIES + 1,
                "runs": run_records,
            },
        )
        print(
            f"Finished validation run{run_index}: {run_record['status']}",
            flush=True,
        )

    batch_status = (
        "completed"
        if all(run["status"] == "completed" for run in run_records)
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
            "run_deterministic_validation": RUN_DETERMINISTIC_VALIDATION,
            "run_llm_validation": RUN_LLM_VALIDATION,
            "model": LLM_MODEL,
            "reasoning_effort": LLM_REASONING_EFFORT,
            "api_retry_delay_seconds": API_RETRY_DELAY_SECONDS,
            "api_max_retries": API_MAX_RETRIES,
            "maximum_api_attempts": API_MAX_RETRIES + 1,
            "runs": run_records,
        },
    )
    print(f"Template validation finished: {batch_status}", flush=True)
    return batch_directory


if __name__ == "__main__":
    main()
