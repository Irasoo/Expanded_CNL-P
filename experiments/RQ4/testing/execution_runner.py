from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from typing_extensions import TypedDict

from ..compilation.main import (
    CASES_DIRECTORY_NAME,
    GENERATED_DIRECTORY_NAME,
    MANIFEST_FILE_NAME,
    CompilationResult,
)


TestingStatus = Literal["completed", "failed", "timeout"]
InputConsumptionStatus = Literal[
    "matched",
    "requested_more_than_provided",
    "ended_with_unused_inputs",
    "unavailable",
]
INPUT_FILE_NAME = "branch_input_groups.yaml"
SAFE_DIRECTORY_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class TestingResult(TypedDict):
    """Location and identity of one completed Agent process execution."""

    # The generated compilation batch selected by test_agents().
    generation_id: str
    # Timestamp of this one testing invocation under results/<generation_id>/.
    testing_id: str
    case_name: str
    compilation_method: str
    compilation_trial_name: str
    input_group_name: str
    run_index: int
    run_count: int
    status: TestingStatus
    result_directory: Path
    execution_log_path: Path


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        # Compiler-written JSON is UTF-8, while manually inspected or copied
        # batch manifests can carry a UTF-8 BOM on Windows. Both are valid
        # inputs for the testing reader.
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_directory_name(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not SAFE_DIRECTORY_NAME.fullmatch(value):
        raise ValueError(
            f"{field_name} must contain only letters, numbers, '_' or '-'."
        )
    return value


def _positive_integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _positive_number(value: Any, field_name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be a positive number.")
    return float(value)


def _non_negative_integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


def _non_negative_number(value: Any, field_name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative number.")
    return float(value)


def _relative_batch_path(
    *,
    generation_directory: Path,
    raw_path: Any,
    field_name: str,
) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(f"Manifest {field_name} must be a non-empty path.")
    relative_path = Path(raw_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(
            f"Manifest {field_name} must stay inside its generation batch."
        )
    resolved_path = (generation_directory / relative_path).resolve()
    try:
        resolved_path.relative_to(generation_directory)
    except ValueError as exc:
        raise ValueError(
            f"Manifest {field_name} escapes its generation batch."
        ) from exc
    return resolved_path


def _load_compilation_results(
    *,
    rq4_directory: Path,
    generation_id: str,
) -> tuple[Path, list[CompilationResult]]:
    """Reconstruct Trial records from one generated batch's manifest."""
    generation_id = _validate_directory_name(generation_id, "generation_id")
    generation_directory = (
        rq4_directory / GENERATED_DIRECTORY_NAME / generation_id
    ).resolve()
    manifest_path = generation_directory / MANIFEST_FILE_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Compilation manifest not found: {manifest_path}"
        )

    document = _read_json(manifest_path)
    if document.get("generation_id") != generation_id:
        raise ValueError(
            f"generation_id in {manifest_path} does not match {generation_id!r}."
        )
    if document.get("is_example") is True:
        raise ValueError(
            "The selected generation_id is a documentation example, not a "
            "testable compilation batch."
        )
    raw_trials = document.get("trials")
    if not isinstance(raw_trials, list):
        raise ValueError(f"trials in {manifest_path} must be a list.")

    results: list[CompilationResult] = []
    for raw_trial in raw_trials:
        if not isinstance(raw_trial, dict):
            raise ValueError(f"Each trial in {manifest_path} must be a map.")
        case_name = _validate_directory_name(
            raw_trial.get("case_name"),
            "manifest case_name",
        )
        # Testing treats the compilation method as provenance metadata. Any
        # safe method name recorded by this batch is accepted; how that Agent
        # was generated must not select a method-specific execution path.
        method = _validate_directory_name(
            raw_trial.get("compilation_method"),
            "manifest compilation_method",
        )
        trial_index = _positive_integer(
            raw_trial.get("trial_index"),
            "manifest trial_index",
        )
        trial_count = _positive_integer(
            raw_trial.get("trial_count"),
            "manifest trial_count",
        )
        status = raw_trial.get("status")
        if status not in {"success", "failed"}:
            raise ValueError(
                f"Manifest contains invalid trial status: {status!r}."
            )

        trial_directory = _relative_batch_path(
            generation_directory=generation_directory,
            raw_path=raw_trial.get("trial_directory"),
            field_name="trial_directory",
        )
        agent_directory = _relative_batch_path(
            generation_directory=generation_directory,
            raw_path=raw_trial.get("agent_directory"),
            field_name="agent_directory",
        )
        compilation_log_path = _relative_batch_path(
            generation_directory=generation_directory,
            raw_path=raw_trial.get("compilation_log_path"),
            field_name="compilation_log_path",
        )
        results.append(
            {
                "case_name": case_name,
                "compilation_method": method,
                "trial_index": trial_index,
                "trial_count": trial_count,
                "status": status,
                "trial_directory": trial_directory,
                "agent_directory": agent_directory,
                "compilation_log_path": compilation_log_path,
            }
        )
    return generation_directory, results


def _validate_requested_names(
    *,
    requested_names: list[str] | None,
    available_names: set[str],
    field_name: str,
) -> set[str] | None:
    """None means all; a list selects only explicitly named values."""
    if requested_names is None:
        return None
    if not isinstance(requested_names, list) or not requested_names:
        raise ValueError(f"{field_name} must be None or a non-empty list.")
    if not all(isinstance(name, str) and name for name in requested_names):
        raise ValueError(f"{field_name} must contain non-empty strings.")
    selected_names = set(requested_names)
    unknown_names = selected_names - available_names
    if unknown_names:
        raise ValueError(
            f"Unknown {field_name}: {', '.join(sorted(unknown_names))}."
        )
    return selected_names


def _load_input_groups(
    *,
    case_directory: Path,
    expected_case_name: str,
) -> tuple[Path, list[dict[str, Any]]]:
    input_path = case_directory / INPUT_FILE_NAME
    if not input_path.is_file():
        raise FileNotFoundError(f"Testing input file not found: {input_path}")

    document = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"Testing input file must contain a map: {input_path}")
    if document.get("case_name") != expected_case_name:
        raise ValueError(
            f"case_name in {input_path} does not match {expected_case_name!r}."
        )

    raw_groups = document.get("input_groups")
    if not isinstance(raw_groups, dict) or not raw_groups:
        raise ValueError(f"input_groups must be a non-empty map: {input_path}")

    groups: list[dict[str, Any]] = []
    for raw_name, raw_group in raw_groups.items():
        name = _validate_directory_name(raw_name, "input group name")
        if not isinstance(raw_group, dict):
            raise ValueError(f"Input group {name!r} must contain a map.")

        raw_inputs = raw_group.get("inputs")
        if not isinstance(raw_inputs, list) or not all(
            isinstance(item, str) for item in raw_inputs
        ):
            raise ValueError(
                f"Input group {name!r} inputs must be a list of strings."
            )

        groups.append(
            {
                "name": name,
                # Case-local repeat is used only when test_agents() does not
                # receive a global repeat_count override.
                "repeat": _positive_integer(
                    raw_group.get("repeat", 1),
                    f"{name}.repeat",
                ),
                "timeout_seconds": _positive_number(
                    raw_group.get("timeout_seconds", 300),
                    f"{name}.timeout_seconds",
                ),
                "inputs": list(raw_inputs),
            }
        )

    return input_path, groups


def _create_testing_directory(
    *,
    rq4_directory: Path,
    generation_id: str,
) -> tuple[str, Path]:
    """Create a new test session, preserving previous runs of the same batch."""
    generation_results_directory = (
        rq4_directory / "results" / generation_id
    )
    generation_results_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    testing_id = timestamp
    testing_directory = generation_results_directory / testing_id
    suffix = 2
    while testing_directory.exists():
        testing_id = f"{timestamp}_{suffix:02d}"
        testing_directory = generation_results_directory / testing_id
        suffix += 1
    testing_directory.mkdir()
    return testing_id, testing_directory


def _resolve_inputs(
    inputs: list[str],
    artifact_directory: Path,
) -> list[str]:
    return [
        value.replace("${ARTIFACT_DIR}", str(artifact_directory))
        for value in inputs
    ]


def _capture_complete_html(
    *,
    stdout: str,
    artifact_directory: Path,
) -> list[dict[str, Any]]:
    """Preserve complete HTML documents observed in terminal output.

    This is transport-level collection, not a correctness judgment. It keeps
    the testing framework independent of the compilation method while making
    an HTML result directly available for later human or browser inspection.
    """
    lowered = stdout.lower()
    document_end = lowered.rfind("</html>")
    if document_end < 0:
        return []

    document_end += len("</html>")
    document_start = lowered.rfind(
        "<!doctype html",
        0,
        document_end,
    )
    if document_start < 0:
        document_start = lowered.rfind(
            "<html",
            0,
            document_end,
        )
    if document_start < 0:
        return []

    html_document = stdout[document_start:document_end].strip()
    artifact_path = artifact_directory / "generated_artifact.html"
    artifact_path.write_text(html_document, encoding="utf-8")
    return [
        {
            "kind": "html",
            "path": str(artifact_path),
            "sha256": _sha256(artifact_path),
            "size_bytes": artifact_path.stat().st_size,
        }
    ]


def _build_execution_record(
    *,
    generation_id: str,
    testing_id: str,
    compilation_result: CompilationResult,
    input_path: Path,
    input_group: dict[str, Any],
    run_index: int,
    run_count: int,
    run_directory: Path,
    resolved_inputs: list[str],
) -> dict[str, Any]:
    return {
        "status": "running",
        "generation_id": generation_id,
        "testing_id": testing_id,
        "case_name": compilation_result["case_name"],
        "compilation_method": compilation_result["compilation_method"],
        "compilation_trial_index": compilation_result["trial_index"],
        "compilation_trial_count": compilation_result["trial_count"],
        "compilation_trial_directory": str(
            compilation_result["trial_directory"]
        ),
        "agent_directory": str(compilation_result["agent_directory"]),
        "compilation_log_path": str(
            compilation_result["compilation_log_path"]
        ),
        "input_file": {
            "path": str(input_path),
            "sha256": _sha256(input_path),
        },
        "input_group_name": input_group["name"],
        "run_index": run_index,
        "run_count": run_count,
        "result_directory": str(run_directory),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "duration_seconds": None,
        "exit_code": None,
        "termination_reason": None,
        "input_count": len(resolved_inputs),
        "consumed_input_count": None,
        "unused_input_count": None,
        "ended_before_all_inputs_consumed": None,
        "input_exhausted": None,
        "input_consumption_status": "unavailable",
        # Provider-reported OpenAI SDK usage observed during this one process.
        # It is separate from compilation_log.json's compilation-time usage.
        "runtime_token_usage": None,
        "runtime_token_usage_file": str(
            run_directory / "runtime_token_usage.json"
        ),
        # Files observed in normal Agent output and copied into artifacts/.
        # Their presence is recorded without judging business correctness.
        "captured_artifacts": [],
        "execution_contract": {
            "version": "rq4-python-main-v1",
            "entrypoint_path": "main.py",
            "entrypoint_callable": "main",
            "input_transport": [
                "builtins.input",
                "sys.stdin.readline",
            ],
            "output_transport": "stdout",
        },
        "runtime_exception": None,
    }


def _derive_input_consumption_status(
    record: dict[str, Any],
) -> InputConsumptionStatus:
    """Summarize only observed input counts, never business correctness."""
    input_count = record.get("input_count")
    consumed_count = record.get("consumed_input_count")
    unused_count = record.get("unused_input_count")
    input_exhausted = record.get("input_exhausted")

    if input_exhausted is True:
        return "requested_more_than_provided"
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (input_count, consumed_count, unused_count)
    ):
        return "unavailable"
    if unused_count > 0:
        return "ended_with_unused_inputs"
    if consumed_count == input_count and unused_count == 0:
        return "matched"
    return "unavailable"


def _run_one_execution_attempt(
    *,
    generation_id: str,
    testing_id: str,
    compilation_result: CompilationResult,
    input_path: Path,
    input_group: dict[str, Any],
    run_index: int,
    run_count: int,
    run_directory: Path,
) -> TestingResult:
    run_directory.mkdir(parents=True)
    artifact_directory = run_directory / "artifacts"
    artifact_directory.mkdir()

    original_inputs = input_group["inputs"]
    resolved_inputs = _resolve_inputs(original_inputs, artifact_directory)
    _write_json(
        run_directory / "inputs.json",
        {
            "original_inputs": original_inputs,
            "resolved_inputs": resolved_inputs,
        },
    )

    execution_log_path = run_directory / "execution_log.json"
    child_report_path = run_directory / "_agent_process_report.json"
    child_request_path = run_directory / "_agent_process_request.json"
    runtime_token_usage_path = run_directory / "runtime_token_usage.json"
    record = _build_execution_record(
        generation_id=generation_id,
        testing_id=testing_id,
        compilation_result=compilation_result,
        input_path=input_path,
        input_group=input_group,
        run_index=run_index,
        run_count=run_count,
        run_directory=run_directory,
        resolved_inputs=resolved_inputs,
    )
    request = {
        "agent_directory": str(compilation_result["agent_directory"]),
        "inputs": resolved_inputs,
        "report_path": str(child_report_path),
        "runtime_token_usage_path": str(runtime_token_usage_path),
    }
    _write_json(child_request_path, request)

    process_environment = os.environ.copy()
    process_environment["PYTHONIOENCODING"] = "utf-8"
    process_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("agent_process.py")),
        str(child_request_path),
    ]
    started_clock = time.monotonic()
    stdout = ""
    stderr = ""

    try:
        completed = subprocess.run(
            command,
            cwd=run_directory,
            env=process_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=input_group["timeout_seconds"],
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        record["exit_code"] = completed.returncode
        record["termination_reason"] = "process_exit"
        record["status"] = (
            "completed" if completed.returncode == 0 else "failed"
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        record["status"] = "timeout"
        record["termination_reason"] = "timeout"
        record["runtime_exception"] = {
            "type": type(exc).__name__,
            "message": (
                "Agent execution exceeded the configured timeout of "
                f"{input_group['timeout_seconds']:g} seconds."
            ),
            "traceback": "",
        }
    except OSError as exc:
        record["status"] = "failed"
        record["termination_reason"] = "process_start_error"
        record["runtime_exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        child_request_path.unlink(missing_ok=True)

    child_report = _read_json(child_report_path)
    child_report_path.unlink(missing_ok=True)
    for field_name in (
        "consumed_input_count",
        "unused_input_count",
        "ended_before_all_inputs_consumed",
        "input_exhausted",
    ):
        if field_name in child_report:
            record[field_name] = child_report[field_name]
    record["input_consumption_status"] = (
        _derive_input_consumption_status(record)
    )
    if child_report.get("runtime_exception") is not None:
        record["runtime_exception"] = child_report["runtime_exception"]
    runtime_token_usage = child_report.get("runtime_token_usage")
    if not isinstance(runtime_token_usage, dict):
        # The tracker writes after each returned request. This fallback keeps
        # partial usage available when a timeout kills the child before its
        # ordinary finally block can create the combined child report.
        runtime_token_usage = _read_json(runtime_token_usage_path)
    if isinstance(runtime_token_usage, dict) and runtime_token_usage:
        record["runtime_token_usage"] = runtime_token_usage

    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["duration_seconds"] = round(
        time.monotonic() - started_clock,
        6,
    )
    record["captured_artifacts"] = _capture_complete_html(
        stdout=stdout,
        artifact_directory=artifact_directory,
    )
    (run_directory / "stdout.txt").write_text(stdout, encoding="utf-8")
    (run_directory / "stderr.txt").write_text(stderr, encoding="utf-8")
    _write_json(execution_log_path, record)

    return {
        "generation_id": generation_id,
        "testing_id": testing_id,
        "case_name": compilation_result["case_name"],
        "compilation_method": compilation_result["compilation_method"],
        "compilation_trial_name": compilation_result[
            "trial_directory"
        ].name,
        "input_group_name": input_group["name"],
        "run_index": run_index,
        "run_count": run_count,
        "status": record["status"],
        "result_directory": run_directory,
        "execution_log_path": execution_log_path,
    }


_RUNTIME_TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)


def _aggregate_runtime_token_usage(
    usages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Aggregate only provider-reported usage from the selected Attempts."""
    valid_usages = [
        usage
        for usage in usages
        if isinstance(usage, dict) and isinstance(usage.get("total"), dict)
        and (usage.get("instrumentation") or {}).get("openai_sdk_available") is not False
    ]
    if not valid_usages:
        return None

    totals = {field_name: 0 for field_name in _RUNTIME_TOKEN_FIELDS}
    for usage in valid_usages:
        for field_name in _RUNTIME_TOKEN_FIELDS:
            value = usage["total"].get(field_name, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                totals[field_name] += value

    count_fields = (
        "request_count",
        "successful_request_count",
        "failed_request_count",
        "requests_without_usage_count",
    )
    counts: dict[str, int | None] = {}
    for field_name in count_fields:
        values = [usage.get(field_name) for usage in valid_usages]
        counts[field_name] = (
            sum(values)
            if all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in values
            )
            else None
        )

    combined_calls: list[dict[str, Any]] = []
    calls_available = True
    for usage in valid_usages:
        calls = usage.get("calls")
        if not isinstance(calls, list):
            calls_available = False
            break
        combined_calls.extend(calls)

    return {
        "source": "rq4_runtime_attempt_aggregate",
        "attempt_usage_count": len(valid_usages),
        "unmeasured_attempt_usage_count": len(usages) - len(valid_usages),
        "measurement_complete": len(valid_usages) == len(usages),
        **counts,
        "total": totals,
        "calls": combined_calls if calls_available else None,
    }


def _copy_attempt_outputs_to_run(
    *,
    attempt_directory: Path,
    run_directory: Path,
    final_record: dict[str, Any],
) -> None:
    """Keep the final Attempt's human-facing files at the stable run path."""
    for file_name in ("inputs.json", "stdout.txt", "stderr.txt"):
        source = attempt_directory / file_name
        if source.is_file():
            target = run_directory / file_name
            # inputs.json is normally identical across every retry. Avoid
            # needlessly reopening an unchanged stable file, which can fail
            # on Windows while another reader still holds it.
            if (
                target.is_file()
                and source.read_bytes() == target.read_bytes()
            ):
                continue
            shutil.copy2(source, target)

    source_artifacts = attempt_directory / "artifacts"
    target_artifacts = run_directory / "artifacts"
    # A standalone failed-run rerun replaces the stable human-facing result,
    # while every earlier result remains preserved under attempts/. Remove
    # only this stable projection before copying the newest Attempt.
    if target_artifacts.is_dir():
        shutil.rmtree(target_artifacts)
    elif target_artifacts.exists():
        target_artifacts.unlink()
    if source_artifacts.is_dir():
        shutil.copytree(source_artifacts, target_artifacts)
    else:
        target_artifacts.mkdir()

    copied_artifacts: list[dict[str, Any]] = []
    for raw_artifact in final_record.get("captured_artifacts", []):
        if not isinstance(raw_artifact, dict):
            continue
        copied_artifact = dict(raw_artifact)
        raw_path = raw_artifact.get("path")
        if isinstance(raw_path, str):
            copied_artifact["path"] = str(
                target_artifacts / Path(raw_path).name
            )
        copied_artifacts.append(copied_artifact)
    final_record["captured_artifacts"] = copied_artifacts


def _run_one_execution(
    *,
    generation_id: str,
    testing_id: str,
    compilation_result: CompilationResult,
    input_path: Path,
    input_group: dict[str, Any],
    run_index: int,
    run_count: int,
    result_directory: Path,
    timeout_max_retries: int = 0,
    timeout_retry_delay_seconds: float = 0,
    progress_prefix: str = "[Testing]",
) -> TestingResult:
    """Run one logical test, retrying only process timeouts.

    Every physical execution is retained below ``attempts/``. The stable
    ``run_XXX/execution_log.json`` describes the final outcome, so callers and
    human reviewers do not need to select the successful Attempt themselves.
    """
    run_directory = result_directory / f"run_{run_index:03d}"
    run_directory.mkdir(parents=True)
    attempts_directory = run_directory / "attempts"
    attempts_directory.mkdir()
    maximum_attempts = timeout_max_retries + 1
    attempt_records: list[tuple[Path, dict[str, Any]]] = []
    final_attempt_result: TestingResult | None = None

    for attempt_index in range(1, maximum_attempts + 1):
        attempt_directory = (
            attempts_directory / f"attempt_{attempt_index:03d}"
        )
        print(
            f"{progress_prefix}: Attempt {attempt_index} in "
            f"{maximum_attempts} started",
            flush=True,
        )
        attempt_result = _run_one_execution_attempt(
            generation_id=generation_id,
            testing_id=testing_id,
            compilation_result=compilation_result,
            input_path=input_path,
            input_group=input_group,
            run_index=run_index,
            run_count=run_count,
            run_directory=attempt_directory,
        )
        attempt_record = _read_json(
            attempt_directory / "execution_log.json"
        )
        attempt_records.append((attempt_directory, attempt_record))
        final_attempt_result = attempt_result

        if attempt_result["status"] != "timeout":
            break
        if attempt_index >= maximum_attempts:
            break

        print(
            f"{progress_prefix}: Attempt {attempt_index} timed out; "
            f"retrying in {timeout_retry_delay_seconds:g}s",
            flush=True,
        )
        if timeout_retry_delay_seconds:
            time.sleep(timeout_retry_delay_seconds)

    if final_attempt_result is None or not attempt_records:
        raise RuntimeError("A logical Agent run produced no execution Attempt.")

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
        record["runtime_token_usage"]
        for _, record in attempt_records
        if isinstance(record.get("runtime_token_usage"), dict)
    ]
    successful_usage = (
        final_record.get("runtime_token_usage")
        if final_record.get("status") == "completed"
        else None
    )

    final_record["result_directory"] = str(run_directory)
    final_record["selected_attempt"] = final_attempt_directory.relative_to(run_directory).as_posix()
    final_record["attempt_count"] = len(attempt_records)
    final_record["timeout_max_retries"] = timeout_max_retries
    final_record["timeout_retry_delay_seconds"] = (
        timeout_retry_delay_seconds
    )
    # The standard runtime field contains only the successful execution. Token
    # use from timed-out Attempts is diagnostic overhead, not Agent burden.
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
    final_record["runtime_token_usage_file"] = str(
        run_directory / "runtime_token_usage.json"
    )
    final_record["observed_attempt_duration_seconds"] = round(
        sum(
            float(record.get("duration_seconds") or 0)
            for _, record in attempt_records
        ),
        6,
    )
    final_record["attempts"] = [
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
        }
        for attempt_index, (attempt_directory, record) in enumerate(
            attempt_records,
            start=1,
        )
    ]

    if successful_usage is not None:
        _write_json(
            run_directory / "runtime_token_usage.json",
            successful_usage,
        )
    _write_json(run_directory / "execution_log.json", final_record)

    return {
        **final_attempt_result,
        "result_directory": run_directory,
        "execution_log_path": run_directory / "execution_log.json",
    }


def load_rq4_runtime_environment(rq4_directory: Path) -> None:
    """Load the environment inherited by every generated Agent subprocess.

    Initial testing and failed-run reruns must share this setup so that the
    generated Agent, inputs, and runtime environment remain identical.
    """
    # Nested Representation roots inherit the same project environment.
    from ..shared.environment import load_runtime_environment
    load_runtime_environment()


def run_agent_tests(
    *,
    rq4_directory: Path,
    generation_id: str,
    case_names: list[str] | None,
    methods: list[str] | None,
    repeat_count: int | None,
    timeout_max_retries: int = 0,
    timeout_retry_delay_seconds: float = 0,
    max_parallel_executions: int = 1,
) -> list[TestingResult]:
    """Run selected successful Agents from one generated compilation batch."""
    if repeat_count is not None:
        _positive_integer(repeat_count, "repeat_count")
    timeout_max_retries = _non_negative_integer(
        timeout_max_retries,
        "timeout_max_retries",
    )
    timeout_retry_delay_seconds = _non_negative_number(
        timeout_retry_delay_seconds,
        "timeout_retry_delay_seconds",
    )
    max_parallel_executions = _positive_integer(
        max_parallel_executions,
        "max_parallel_executions",
    )

    load_rq4_runtime_environment(rq4_directory)
    _, all_compilations = _load_compilation_results(
        rq4_directory=rq4_directory,
        generation_id=generation_id,
    )
    selected_case_names = _validate_requested_names(
        requested_names=case_names,
        available_names={result["case_name"] for result in all_compilations},
        field_name="case_names",
    )
    selected_methods = _validate_requested_names(
        requested_names=methods,
        available_names={
            result["compilation_method"]
            for result in all_compilations
        },
        field_name="methods",
    )

    selected_compilations = [
        result
        for result in all_compilations
        if (
            selected_case_names is None
            or result["case_name"] in selected_case_names
        )
        and (
            selected_methods is None
            or result["compilation_method"] in selected_methods
        )
    ]
    successful_compilations = [
        result
        for result in selected_compilations
        if result["status"] == "success"
    ]
    skipped_count = len(selected_compilations) - len(successful_compilations)
    if skipped_count:
        print(
            f"[Testing] Skipping {skipped_count} failed compilation(s).",
            flush=True,
        )
    if not successful_compilations:
        print(
            f"[Testing] Generation {generation_id}: no successful Agent "
            "matches the selected filters.",
            flush=True,
        )
        return []

    grouped_results: dict[str, list[CompilationResult]] = {}
    for compilation_result in successful_compilations:
        grouped_results.setdefault(
            compilation_result["case_name"],
            [],
        ).append(compilation_result)

    prepared_cases: list[
        tuple[str, list[CompilationResult], Path, list[dict[str, Any]]]
    ] = []
    total_executions = 0
    for case_name, case_compilations in grouped_results.items():
        case_directory = rq4_directory / CASES_DIRECTORY_NAME / case_name
        input_path, input_groups = _load_input_groups(
            case_directory=case_directory,
            expected_case_name=case_name,
        )
        prepared_cases.append(
            (case_name, case_compilations, input_path, input_groups)
        )
        group_execution_count = sum(
            repeat_count if repeat_count is not None else group["repeat"]
            for group in input_groups
        )
        total_executions += len(case_compilations) * group_execution_count

    testing_id, testing_directory = _create_testing_directory(
        rq4_directory=rq4_directory,
        generation_id=generation_id,
    )
    print(
        f"[Testing] Generation {generation_id}, test {testing_id}: started "
        f"({total_executions} execution(s)).",
        flush=True,
    )

    execution_number = 0
    prepared_executions: list[tuple[int, str, dict[str, Any]]] = []
    for case_name, case_compilations, input_path, input_groups in prepared_cases:
        for compilation_result in case_compilations:
            compilation_trial_name = compilation_result[
                "trial_directory"
            ].name
            compilation_result_directory = (
                testing_directory / case_name / compilation_trial_name
            )

            for input_group in input_groups:
                effective_run_count = (
                    repeat_count
                    if repeat_count is not None
                    else input_group["repeat"]
                )
                input_group_directory = (
                    compilation_result_directory / input_group["name"]
                )
                input_group_directory.mkdir(parents=True, exist_ok=True)
                for run_index in range(1, effective_run_count + 1):
                    execution_number += 1
                    prefix = (
                        f"[Testing][{generation_id}][{case_name}]"
                        f"[{compilation_trial_name}]"
                        f"[{input_group['name']}]"
                        f"[Run {run_index} in {effective_run_count}; "
                        f"task {execution_number} in {total_executions}]"
                    )
                    prepared_executions.append(
                        (
                            execution_number,
                            prefix,
                            {
                                "generation_id": generation_id,
                                "testing_id": testing_id,
                                "compilation_result": compilation_result,
                                "input_path": input_path,
                                "input_group": input_group,
                                "run_index": run_index,
                                "run_count": effective_run_count,
                                "result_directory": input_group_directory,
                                "timeout_max_retries": timeout_max_retries,
                                "timeout_retry_delay_seconds": (
                                    timeout_retry_delay_seconds
                                ),
                                "progress_prefix": prefix,
                            },
                        )
                    )

    testing_manifest = {
        "generation_id": generation_id,
        "testing_id": testing_id,
        "status": "running",
        "executions": [
            (arguments["result_directory"] / f"run_{arguments['run_index']:03d}").relative_to(testing_directory).as_posix()
            for _, _, arguments in prepared_executions
        ],
    }
    _write_json(testing_directory / "testing_manifest.json", testing_manifest)

    def run_prepared_execution(
        task_number: int,
        prefix: str,
        execution_arguments: dict[str, Any],
    ) -> tuple[int, TestingResult]:
        print(f"{prefix}: started", flush=True)
        result = _run_one_execution(**execution_arguments)
        print(
            f"{prefix}: {result['status']}\n"
            f"  Result: {result['result_directory']}",
            flush=True,
        )
        return task_number, result

    results_by_number: dict[int, TestingResult] = {}
    with ThreadPoolExecutor(max_workers=max_parallel_executions) as executor:
        futures = [
            executor.submit(run_prepared_execution, *prepared_execution)
            for prepared_execution in prepared_executions
        ]
        for future in as_completed(futures):
            task_number, result = future.result()
            results_by_number[task_number] = result

    testing_results = [
        results_by_number[number]
        for number in range(1, len(prepared_executions) + 1)
    ]

    testing_manifest["status"] = "completed"
    _write_json(testing_directory / "testing_manifest.json", testing_manifest)

    print(
        f"[Testing] Generation {generation_id}, test {testing_id}: completed\n"
        f"  Results: {testing_directory}",
        flush=True,
    )
    return testing_results
