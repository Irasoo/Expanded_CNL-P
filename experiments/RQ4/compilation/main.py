from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from typing_extensions import NotRequired, TypedDict

from ..shared.layout import specification_filename

from .trial_runner import (
    CompilationTrialInterrupted,
    run_trial_in_subprocess as _run_trial_in_subprocess,
)


__all__ = ["compile_agents"]


CompilationMethodName = Literal["native", "langgraph", "codex"]
CompilationStatus = Literal["success", "failed"]
AVAILABLE_METHODS: tuple[CompilationMethodName, ...] = (
    "native",
    "langgraph",
    "codex",
)
CASES_DIRECTORY_NAME = "cases"
GENERATED_DIRECTORY_NAME = "generated"
MANIFEST_FILE_NAME = "compilation_manifest.json"


# Token accounting in the logical Trial's compilation_log.json:
#
# 1. cached_input_tokens is already part of input_tokens. It describes how
#    much of the input was served from cache and must not be added to the input
#    count a second time.
# 2. reasoning_tokens is already part of output_tokens. It describes the
#    reasoning portion of the generated output and must not be added again.
# 3. Therefore total_tokens is normally input_tokens + output_tokens. It is
#    not the sum of input_tokens, cached_input_tokens, output_tokens, and
#    reasoning_tokens. For example, 82,000 input + 18,000 output = 100,000
#    total even when 12,000 input tokens were cached and 6,000 output tokens
#    were reasoning tokens.
# 4. For Native and LangGraph, token_usage.calls contains one record for every
#    compiler-time LLM API call and request_count equals len(calls).
# 5. Codex CLI exposes only one aggregate usage object for its complete
#    tool-using turn, not reliable per-request usage. Its normalized report
#    therefore has the same token_usage.total structure, while request counts
#    and calls are null. The exact Codex fields remain under raw_usage.
# 6. compilation_token_usage is the only field used as the resource burden of
#    one successfully compiled Agent. It contains only the successful Attempt.
# 7. retry_overhead_token_usage contains discarded whole-compilation Attempts
#    caused by retryable infrastructure/Codex failures. It is retained for
#    operational auditing and is excluded from the compiler-burden metric.
# 8. observed_total_token_usage sums usage values actually returned across all
#    Attempts. A failed request may return no usage, so this is an audit field,
#    not a guaranteed provider-billing total and not the compiler burden.


class CompilationMethodPlan(TypedDict):
    """How many independent Trials to run for one compilation method."""

    # Registry name of the method implemented in compilation/*.py.
    method: CompilationMethodName
    # Total independent compilations of this case with this method.
    count: int
    # Maximum wall-clock time for each child process; default is 3600 seconds.
    timeout_seconds: NotRequired[float]
    # Method-specific settings; Codex accepts model and reasoning_effort.
    options: NotRequired[dict[str, Any]]


class CaseCompilationPlan(TypedDict):
    """Compilation methods selected for one RQ4 case source directory."""

    # Directory name directly below RQ4/cases, for example
    # github_project_navigator.
    case_name: str
    # Independent method/count definitions for this case.
    methods: list[CompilationMethodPlan]


class CompilationRetryPolicy(TypedDict):
    """RQ4-level retry settings for one logical compilation Trial."""

    # Total Attempts including the first execution. A value of 1 disables
    # whole-compilation retry while preserving the Attempt directory layout.
    max_attempts: int
    # Delay between two whole-compilation Attempts.
    retry_delay_seconds: float


class CompilationResult(TypedDict):
    """One Trial record kept in the batch manifest and used by testing."""

    # RQ4 case that produced this Agent.
    case_name: str
    # Compilation implementation used for this Trial.
    compilation_method: CompilationMethodName
    # Position of this independent compilation in its configured repetitions.
    trial_index: int
    trial_count: int
    # Broad final result after all permitted Attempts for this logical Trial.
    status: CompilationStatus
    # Directory containing both agent/ and compilation_log.json.
    trial_directory: Path
    # Generated Agent directory. Testing should use it only on success.
    agent_directory: Path
    # Exact compilation record for later inspection.
    compilation_log_path: Path


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _validate_case_directory(
    rq4_directory: Path,
    case_name: str,
) -> Path:
    if (
        not isinstance(case_name, str)
        or not case_name.strip()
        or Path(case_name).name != case_name
    ):
        raise ValueError("case_name must be one direct RQ4/cases directory name.")

    case_directory = (
        rq4_directory / CASES_DIRECTORY_NAME / case_name
    ).resolve()
    if not case_directory.is_dir():
        raise FileNotFoundError(f"RQ4 case not found: {case_directory}")

    for file_name in (
        specification_filename(case_directory),
        "branch_input_groups.yaml",
        "reference_code.py",
        "reference_code_for_codex.py",
    ):
        source_path = case_directory / file_name
        if not source_path.is_file():
            raise FileNotFoundError(
                f"RQ4 case source file not found: {source_path}"
            )
    return case_directory


def _validate_method_plan(
    raw_plan: CompilationMethodPlan,
) -> tuple[CompilationMethodName, int, float, dict[str, Any]]:
    method = raw_plan.get("method")
    if method not in AVAILABLE_METHODS:
        raise ValueError(
            f"Unknown compilation method {method!r}. "
            f"Available methods: {', '.join(AVAILABLE_METHODS)}."
        )

    count = raw_plan.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("Compilation method count must be a positive integer.")

    timeout_seconds = raw_plan.get("timeout_seconds", 3600)
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive number.")

    options = raw_plan.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("Compilation method options must be a dictionary.")

    return method, count, float(timeout_seconds), dict(options)


def _validate_retry_policy(
    raw_policy: CompilationRetryPolicy | None,
) -> tuple[int, float]:
    policy = raw_policy or {
        "max_attempts": 1,
        "retry_delay_seconds": 0,
    }
    max_attempts = policy.get("max_attempts")
    if (
        not isinstance(max_attempts, int)
        or isinstance(max_attempts, bool)
        or max_attempts < 1
    ):
        raise ValueError("retry_policy.max_attempts must be a positive integer.")

    retry_delay_seconds = policy.get("retry_delay_seconds")
    if (
        not isinstance(retry_delay_seconds, (int, float))
        or isinstance(retry_delay_seconds, bool)
        or retry_delay_seconds < 0
    ):
        raise ValueError(
            "retry_policy.retry_delay_seconds must be a non-negative number."
        )
    return max_attempts, float(retry_delay_seconds)


def _create_generation_directory(
    rq4_directory: Path,
) -> tuple[str, Path]:
    """Create one output batch; its name is the generation timestamp."""
    generated_root = rq4_directory / GENERATED_DIRECTORY_NAME
    generated_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generation_id = timestamp
    suffix = 2
    generation_directory = generated_root / generation_id
    # A suffix is needed only when two batches begin in the same second. It
    # keeps the first, normal directory name as a plain readable timestamp.
    while generation_directory.exists():
        generation_id = f"{timestamp}_{suffix:02d}"
        generation_directory = generated_root / generation_id
        suffix += 1

    generation_directory.mkdir()
    return generation_id, generation_directory


def _build_compilation_result(
    *,
    case_name: str,
    method: CompilationMethodName,
    trial_index: int,
    trial_count: int,
    trial_directory: Path,
) -> CompilationResult:
    log_path = trial_directory / "compilation_log.json"
    log_record = json.loads(log_path.read_text(encoding="utf-8"))
    status = log_record.get("status")
    if status not in {"success", "failed"}:
        raise ValueError(
            f"Compilation log contains an invalid status: {log_path}"
        )

    return {
        "case_name": case_name,
        "compilation_method": method,
        "trial_index": trial_index,
        "trial_count": trial_count,
        "status": status,
        "trial_directory": trial_directory,
        "agent_directory": trial_directory / "agent",
        "compilation_log_path": log_path,
    }


def _manifest_trial_record(
    *,
    result: CompilationResult,
    generation_directory: Path,
) -> dict[str, Any]:
    """Store paths relative to this batch, so a batch can be moved intact."""
    return {
        "case_name": result["case_name"],
        "compilation_method": result["compilation_method"],
        "trial_index": result["trial_index"],
        "trial_count": result["trial_count"],
        "status": result["status"],
        "trial_directory": str(
            result["trial_directory"].relative_to(generation_directory)
        ),
        "agent_directory": str(
            result["agent_directory"].relative_to(generation_directory)
        ),
        "compilation_log_path": str(
            result["compilation_log_path"].relative_to(generation_directory)
        ),
    }


def _write_manifest(
    *,
    manifest_path: Path,
    generation_id: str,
    started_at: str,
    status: str,
    results: list[CompilationResult],
    generation_directory: Path,
    exception: dict[str, str] | None = None,
) -> None:
    """Write an operational index, not an automatic experiment evaluation."""
    _write_json(
        manifest_path,
        {
            "generation_id": generation_id,
            "status": status,
            "started_at": started_at,
            # While a Trial batch is still running this is only a progress
            # snapshot. finished_at is reserved for the final write below.
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": (
                None
                if status == "running"
                else datetime.now(timezone.utc).isoformat()
            ),
            "trials": [
                _manifest_trial_record(
                    result=result,
                    generation_directory=generation_directory,
                )
                for result in results
            ],
            "exception": exception,
        },
    )


def compile_agents(
    *,
    rq4_directory: str | Path,
    compilation_plan: list[CaseCompilationPlan],
    retry_policy: CompilationRetryPolicy | None = None,
) -> str:
    """Compile one batch and return its generation timestamp identifier.

    Each Trial has its own compilation_log.json. The batch-level manifest is
    only an index that lets testing locate all completed Trials from this one
    returned generation_id.
    """
    rq4_path = Path(rq4_directory).resolve()
    maximum_attempts, retry_delay_seconds = _validate_retry_policy(
        retry_policy
    )
    generation_id, generation_directory = _create_generation_directory(
        rq4_path
    )
    manifest_path = generation_directory / MANIFEST_FILE_NAME
    started_at = datetime.now(timezone.utc).isoformat()
    results: list[CompilationResult] = []
    manifest_status = "completed"
    manifest_exception: dict[str, str] | None = None

    print(
        f"[Compilation] Generation {generation_id}: started",
        flush=True,
    )
    try:
        for case_plan in compilation_plan:
            case_name = case_plan.get("case_name")
            methods = case_plan.get("methods")
            if not isinstance(methods, list) or not methods:
                raise ValueError(
                    f"Case {case_name!r} must define at least one method."
                )
            case_directory = _validate_case_directory(rq4_path, case_name)

            for raw_method_plan in methods:
                method, count, timeout_seconds, options = (
                    _validate_method_plan(raw_method_plan)
                )
                for trial_index in range(1, count + 1):
                    print(
                        f"[Compilation][{case_name}][{method}] "
                        f"Trial {trial_index} in {count}: started "
                        f"(timeout={timeout_seconds:g}s; "
                        f"max attempts={maximum_attempts})",
                        flush=True,
                    )
                    attempt_index = 1
                    retry_exhausted = False
                    try:
                        while True:
                            print(
                                f"[Compilation][{case_name}][{method}] "
                                f"Trial {trial_index} in {count}, "
                                f"Attempt {attempt_index} in "
                                f"{maximum_attempts}: started",
                                flush=True,
                            )
                            trial_directory = _run_trial_in_subprocess(
                                rq4_directory=rq4_path,
                                case_directory=case_directory,
                                generation_directory=generation_directory,
                                method=method,
                                trial_index=trial_index,
                                trial_count=count,
                                timeout_seconds=timeout_seconds,
                                options=options,
                                attempt_index=attempt_index,
                                maximum_attempts=maximum_attempts,
                            )
                            trial_log = json.loads(
                                (
                                    trial_directory
                                    / "compilation_log.json"
                                ).read_text(encoding="utf-8")
                            )
                            if trial_log.get("status") == "success":
                                break

                            rq4_retryable = (
                                trial_log.get("rq4_retryable") is True
                            )
                            if not rq4_retryable:
                                break
                            if attempt_index >= maximum_attempts:
                                retry_exhausted = True
                                break

                            print(
                                f"[Compilation][{case_name}][{method}] "
                                f"Attempt {attempt_index} failed with a "
                                "retryable infrastructure/Codex error; "
                                f"retrying the same Trial in "
                                f"{retry_delay_seconds:g}s.",
                                flush=True,
                            )
                            if retry_delay_seconds:
                                time.sleep(retry_delay_seconds)
                            attempt_index += 1
                    except CompilationTrialInterrupted as exc:
                        # The child log has already been finalized. Preserve
                        # this interrupted Trial in the batch manifest before
                        # stopping the remaining compilation plan.
                        interrupted_result = _build_compilation_result(
                            case_name=case_name,
                            method=method,
                            trial_index=trial_index,
                            trial_count=count,
                            trial_directory=exc.trial_directory,
                        )
                        results.append(interrupted_result)
                        print(
                            f"[Compilation][{case_name}][{method}] "
                            f"Trial {trial_index} in {count}: interrupted\n"
                            f"  Log:   "
                            f"{interrupted_result['compilation_log_path']}",
                            flush=True,
                        )
                        raise KeyboardInterrupt from exc
                    result = _build_compilation_result(
                        case_name=case_name,
                        method=method,
                        trial_index=trial_index,
                        trial_count=count,
                        trial_directory=trial_directory,
                    )
                    results.append(result)
                    # Persist partial progress too: an interruption never
                    # erases the identities of Trials that have already run.
                    _write_manifest(
                        manifest_path=manifest_path,
                        generation_id=generation_id,
                        started_at=started_at,
                        status="running",
                        results=results,
                        generation_directory=generation_directory,
                    )
                    print(
                        f"[Compilation][{case_name}][{method}] "
                        f"Trial {trial_index} in {count}: {result['status']}\n"
                        f"  Agent: {result['agent_directory']}\n"
                        f"  Log:   {result['compilation_log_path']}",
                        flush=True,
                    )
                    if retry_exhausted:
                        raise RuntimeError(
                            "RQ4 whole-compilation retry limit was exhausted "
                            f"for {case_name}/{method} Trial "
                            f"{trial_index} in {count} after "
                            f"{maximum_attempts} Attempts. See "
                            f"{result['compilation_log_path']}."
                        )
    except BaseException as exc:
        manifest_status = "interrupted"
        manifest_exception = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        raise
    finally:
        _write_manifest(
            manifest_path=manifest_path,
            generation_id=generation_id,
            started_at=started_at,
            status=manifest_status,
            results=results,
            generation_directory=generation_directory,
            exception=manifest_exception,
        )

    print(
        f"[Compilation] Generation {generation_id}: completed\n"
        f"  Manifest: {manifest_path}",
        flush=True,
    )
    return generation_id
