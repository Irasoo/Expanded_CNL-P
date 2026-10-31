from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO


RQ4_DIRECTORY = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = RQ4_DIRECTORY.parent
if str(WORKSPACE_ROOT) not in sys.path:
    # Child processes start in RQ4/. Add only the root required to import the
    # compiler package; each method still receives one explicit case path.
    sys.path.insert(0, str(WORKSPACE_ROOT))

from importlib import import_module

from ..shared.layout import representation_for_case, specification_filename
from ..shared.environment import load_runtime_environment
from . import codex


CompilationFunction = Callable[..., None]
METHOD_COMPILERS: dict[str, CompilationFunction] = {
    "native": lambda **kwargs: import_module(".native", __package__).compile_agent(**kwargs),
    "langgraph": lambda **kwargs: import_module(".langgraph", __package__).compile_agent(**kwargs),
    "codex": codex.compile_agent,
}


class CompilationTrialInterrupted(KeyboardInterrupt):
    """Carry the finalized Trial directory back to the batch manifest."""

    def __init__(self, trial_directory: Path) -> None:
        super().__init__("Compilation Trial was interrupted by the user.")
        self.trial_directory = trial_directory


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_file_records(case_directory: Path) -> dict[str, Any]:
    # Hashes make the Trial traceable without duplicating large source files in
    # every compilation log.
    specification_file = specification_filename(case_directory)
    records = {
        specification_file: {
            "path": str(case_directory / specification_file),
            "sha256": _sha256(case_directory / specification_file),
        },
        "reference_code.py": {
            "path": str(case_directory / "reference_code.py"),
            "sha256": _sha256(case_directory / "reference_code.py"),
        },
    }
    codex_reference_path = case_directory / "reference_code_for_codex.py"
    if codex_reference_path.is_file():
        # Codex sees this undecorated copy instead of the compiler-registration
        # source. Recording its hash makes that separate experimental input
        # auditable without changing Native or LangGraph registration.
        records["reference_code_for_codex.py"] = {
            "path": str(codex_reference_path),
            "sha256": _sha256(codex_reference_path),
        }
    return records


def _create_trial_directory(
    *,
    generation_directory: Path,
    case_name: str,
    method: str,
    trial_index: int,
    trial_count: int,
) -> Path:
    # Case source files are immutable inputs under RQ4/cases/. Every generated
    # file instead belongs to exactly one generated/<generation_id>/ batch.
    case_generation_directory = generation_directory / case_name
    case_generation_directory.mkdir(parents=True, exist_ok=True)
    trial_directory = (
        case_generation_directory / f"{method}_{trial_index}in{trial_count}"
    )
    if trial_directory.exists():
        raise FileExistsError(
            "A Trial directory already exists inside this generation batch: "
            f"{trial_directory}"
        )

    trial_directory.mkdir()
    (trial_directory / "attempts").mkdir()
    return trial_directory


def _trial_directory_path(
    *,
    generation_directory: Path,
    case_name: str,
    method: str,
    trial_index: int,
    trial_count: int,
) -> Path:
    return (
        generation_directory
        / case_name
        / f"{method}_{trial_index}in{trial_count}"
    )


def _prepare_attempt_directory(
    *,
    trial_directory: Path,
    attempt_index: int,
) -> Path:
    attempt_directory = (
        trial_directory / "attempts" / f"attempt_{attempt_index:03d}"
    )
    if attempt_directory.exists():
        raise FileExistsError(
            "A compilation Attempt already exists inside this Trial: "
            f"{attempt_directory}"
        )
    attempt_directory.mkdir()
    (attempt_directory / "agent").mkdir()
    return attempt_directory


def _base_record(request: dict[str, Any]) -> dict[str, Any]:
    case_directory = Path(request["case_directory"])
    return {
        # success/failed is the public result. failure_category and
        # rq4_retryable below separately control whether RQ4 may create another
        # Attempt for this same logical Trial.
        "status": "running",
        "case_name": request["case_name"],
        "representation": representation_for_case(case_directory),
        "compilation_method": request["compilation_method"],
        "trial_index": request["trial_index"],
        "trial_count": request["trial_count"],
        # An RQ4 Attempt is one execution of the same logical Trial. A relay
        # failure may create several Attempts, but the Trial identity and the
        # generated-batch timestamp do not change.
        "attempt_index": request["attempt_index"],
        "maximum_attempts": request["maximum_attempts"],
        "agent_directory": request["agent_directory"],
        "method_options": request["method_options"],
        "source_files": _source_file_records(case_directory),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "duration_seconds": None,
        "token_usage": None,
        "method_details": {},
        "failure_category": None,
        "rq4_retryable": False,
        "exception": None,
    }


def _execute_trial(request_path: Path) -> int:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    trial_directory = Path(request["trial_directory"]).resolve()
    agent_directory = Path(request["agent_directory"]).resolve()
    case_directory = Path(request["case_directory"]).resolve()
    log_path = trial_directory / "compilation_log.json"
    method_name = request["compilation_method"]
    method_record: dict[str, Any] = {}
    record = _base_record(request)
    started_clock = time.monotonic()

    try:
        load_runtime_environment()
        if method_name != "codex" and representation_for_case(case_directory) != "cnlp":
            raise ValueError("Native and LangGraph generation require the CNL-P representation.")
        compiler_function = METHOD_COMPILERS[method_name]
        compiler_function(
            case_directory=case_directory,
            agent_directory=agent_directory,
            method_record=method_record,
            options=request["method_options"],
        )
    except Exception as exc:
        record["status"] = "failed"
        # Native/LangGraph are retried only when the compiler preserves the
        # explicit transient LLM-request exception. Invalid CNL-P, invalid
        # Plans, invalid generated Python, and other compiler-quality failures
        # remain final results. Per the RQ4 experiment policy, a failed Codex
        # generation is always eligible for a fresh isolated Attempt.
        if method_name == "codex":
            record["failure_category"] = "codex_attempt_failure"
            record["rq4_retryable"] = True
        elif type(exc).__name__ == "RetryableLLMRequestError":
            record["failure_category"] = "transient_llm_infrastructure"
            record["rq4_retryable"] = True
        else:
            record["failure_category"] = "compiler_failure"
            record["rq4_retryable"] = False
        record["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        exit_code = 1
    else:
        record["status"] = "success"
        record["failure_category"] = None
        record["rq4_retryable"] = False
        exit_code = 0
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        record["duration_seconds"] = round(
            time.monotonic() - started_clock,
            6,
        )
        # All methods expose token usage at one stable top-level location.
        record["token_usage"] = method_record.pop("token_usage", None)
        record["method_details"] = method_record
        _write_json(log_path, record)

    return exit_code


def _record_subprocess_result(
    *,
    log_path: Path,
    request: dict[str, Any],
    exit_code: int | None,
    termination_reason: str,
    stdout: str,
    stderr: str,
    parent_exception: dict[str, str] | None,
) -> None:
    record = _read_json(log_path)
    if not record:
        # A timeout/start error can occur before the child writes its own log.
        # The parent still creates the required factual compilation record.
        record = _base_record(request)
        record["status"] = "failed"
        record["failure_category"] = "abnormal_child_exit"
        record["rq4_retryable"] = True
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        record["exception"] = parent_exception or {
            "type": "CompilationProcessError",
            "message": "Compilation child process produced no record.",
            "traceback": "",
        }

    if parent_exception is not None:
        # KeyboardInterrupt is a BaseException, so the child Trial's finally
        # block can leave a partial record whose status is still "running".
        # The parent owns process-level termination and must finalize it.
        record["status"] = "failed"
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        record["exception"] = parent_exception
        exception_type = parent_exception.get("type")
        if exception_type == "KeyboardInterrupt":
            record["failure_category"] = "user_interruption"
            record["rq4_retryable"] = False
        else:
            record["failure_category"] = "compilation_process_failure"
            record["rq4_retryable"] = True
    elif exit_code not in (0, None) and record.get("status") != "failed":
        record["status"] = "failed"
        record["failure_category"] = "abnormal_child_exit"
        record["rq4_retryable"] = True
    record["subprocess"] = {
        "exit_code": exit_code,
        "termination_reason": termination_reason,
        "stdout": stdout,
        "stderr": stderr,
    }
    _write_json(log_path, record)


_TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)


def _aggregate_token_usage(
    usages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Sum Attempt reports without changing their accounting semantics."""
    valid_usages = [
        usage
        for usage in usages
        if isinstance(usage, dict) and isinstance(usage.get("total"), dict)
    ]
    if not valid_usages:
        return None

    totals = {field_name: 0 for field_name in _TOKEN_FIELDS}
    for usage in valid_usages:
        usage_total = usage["total"]
        for field_name in _TOKEN_FIELDS:
            value = usage_total.get(field_name, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                totals[field_name] += value

    count_fields = (
        "request_count",
        "successful_request_count",
        "failed_request_count",
        "requests_without_usage_count",
    )
    normalized_counts: dict[str, int | None] = {}
    for field_name in count_fields:
        values = [usage.get(field_name) for usage in valid_usages]
        normalized_counts[field_name] = (
            sum(values)
            if all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in values
            )
            else None
        )

    all_calls: list[dict[str, Any]] = []
    calls_available = True
    for usage in valid_usages:
        calls = usage.get("calls")
        if not isinstance(calls, list):
            calls_available = False
            break
        all_calls.extend(calls)

    return {
        "source": "rq4_attempt_aggregate",
        "attempt_usage_count": len(valid_usages),
        **normalized_counts,
        "total": totals,
        "calls": all_calls if calls_available else None,
    }


def _promote_successful_agent(
    *,
    attempt_directory: Path,
    trial_directory: Path,
) -> None:
    source = attempt_directory / "agent"
    destination = trial_directory / "agent"
    if not source.is_dir():
        raise RuntimeError(
            f"Successful Attempt did not produce an Agent directory: {source}"
        )
    if destination.exists():
        raise FileExistsError(
            "The stable Trial Agent directory already exists: "
            f"{destination}"
        )
    shutil.copytree(source, destination)


def _write_trial_summary(
    *,
    trial_directory: Path,
    latest_attempt_directory: Path,
) -> None:
    """Build the stable logical-Trial log consumed by the RQ4 dispatcher.

    Only a successful Attempt becomes ``compilation_token_usage``. Usage from
    discarded infrastructure/Codex retries is kept separately and must not be
    used as the compiler's resource burden in the paper.
    """
    attempt_directories = sorted(
        path
        for path in (trial_directory / "attempts").iterdir()
        if path.is_dir()
    )
    attempt_records: list[tuple[Path, dict[str, Any]]] = []
    for attempt_directory in attempt_directories:
        attempt_record = _read_json(
            attempt_directory / "compilation_log.json"
        )
        if attempt_record:
            attempt_records.append((attempt_directory, attempt_record))

    latest_record = _read_json(
        latest_attempt_directory / "compilation_log.json"
    )
    if not latest_record:
        raise RuntimeError(
            "The latest compilation Attempt did not leave a log: "
            f"{latest_attempt_directory}"
        )

    successful_record = next(
        (
            record
            for _, record in reversed(attempt_records)
            if record.get("status") == "success"
        ),
        None,
    )
    retry_overhead_usages = [
        record["token_usage"]
        for _, record in attempt_records
        if record.get("status") == "failed"
        and record.get("rq4_retryable") is True
        and isinstance(record.get("token_usage"), dict)
    ]
    terminal_failure_usages = [
        record["token_usage"]
        for _, record in attempt_records
        if record.get("status") == "failed"
        and record.get("rq4_retryable") is not True
        and isinstance(record.get("token_usage"), dict)
    ]
    all_usages = [
        record["token_usage"]
        for _, record in attempt_records
        if isinstance(record.get("token_usage"), dict)
    ]

    compilation_usage = (
        successful_record.get("token_usage")
        if successful_record is not None
        else None
    )
    summary = {
        "status": latest_record.get("status", "failed"),
        "case_name": latest_record.get("case_name"),
        "compilation_method": latest_record.get("compilation_method"),
        "trial_index": latest_record.get("trial_index"),
        "trial_count": latest_record.get("trial_count"),
        "attempt_count": len(attempt_records),
        "maximum_attempts": latest_record.get("maximum_attempts"),
        "agent_directory": str(trial_directory / "agent"),
        "method_options": latest_record.get("method_options", {}),
        "source_files": latest_record.get("source_files", {}),
        "started_at": (
            attempt_records[0][1].get("started_at")
            if attempt_records
            else latest_record.get("started_at")
        ),
        "finished_at": latest_record.get("finished_at"),
        "duration_seconds": round(
            sum(
                float(record.get("duration_seconds") or 0)
                for _, record in attempt_records
            ),
            6,
        ),
        # Backward-compatible name: it now deliberately means only the final
        # successful compilation, never the sum of failed retry Attempts.
        "token_usage": compilation_usage,
        "compilation_token_usage": compilation_usage,
        "retry_overhead_token_usage": _aggregate_token_usage(
            retry_overhead_usages
        ),
        "failed_compilation_token_usage": _aggregate_token_usage(
            terminal_failure_usages
        ),
        # This is intentionally named "observed", not "billed": a relay may
        # omit usage for the request that actually disconnected or timed out.
        "observed_total_token_usage": _aggregate_token_usage(all_usages),
        "token_accounting": {
            "paper_compilation_burden_field": "compilation_token_usage",
            "retry_overhead_excluded_from_compilation_burden": True,
            "description": (
                "Only the successful Attempt is the compiler resource burden; "
                "discarded relay/Codex retry Attempts are operational overhead."
            ),
        },
        "method_details": (
            successful_record.get("method_details", {})
            if successful_record is not None
            else latest_record.get("method_details", {})
        ),
        "failure_category": latest_record.get("failure_category"),
        "rq4_retryable": latest_record.get("rq4_retryable", False),
        "exception": latest_record.get("exception"),
        "attempts": [
            {
                "attempt_index": record.get("attempt_index"),
                "status": record.get("status"),
                "failure_category": record.get("failure_category"),
                "rq4_retryable": record.get("rq4_retryable", False),
                "directory": str(
                    attempt_directory.relative_to(trial_directory)
                ),
                "compilation_log": str(
                    (
                        attempt_directory / "compilation_log.json"
                    ).relative_to(trial_directory)
                ),
                "token_usage": record.get("token_usage"),
                "exception": record.get("exception"),
            }
            for attempt_directory, record in attempt_records
        ],
    }
    _write_json(trial_directory / "compilation_log.json", summary)


def _forward_process_stream(
    *,
    stream: TextIO | None,
    captured_parts: list[str],
    terminal: TextIO,
) -> None:
    """Forward one child stream live while retaining the Trial transcript."""
    if stream is None:
        return
    captured_characters: list[str] = []
    try:
        # 子进程的紧凑进度使用回车符在同一行原地更新。readline() 只有遇到
        # 换行才会返回，会让进度在阶段结束前一直不可见；逐字符转发可以立即
        # 保留回车语义。这里只处理本机管道，不会增加任何 LLM 调用。
        for character in iter(lambda: stream.read(1), ""):
            captured_characters.append(character)
            terminal.write(character)
            terminal.flush()
    finally:
        captured_parts.append("".join(captured_characters))
        stream.close()


def _stop_child_process(process: subprocess.Popen[str]) -> None:
    """Stop an interrupted or timed-out compiler child on Windows or POSIX."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_trial_in_subprocess(
    *,
    rq4_directory: Path,
    case_directory: Path,
    generation_directory: Path,
    method: str,
    trial_index: int,
    trial_count: int,
    timeout_seconds: float,
    options: dict[str, Any],
    attempt_index: int = 1,
    maximum_attempts: int = 1,
) -> Path:
    """Run one isolated Attempt and refresh its logical Trial summary."""
    trial_directory = _trial_directory_path(
        generation_directory=generation_directory,
        case_name=case_directory.name,
        method=method,
        trial_index=trial_index,
        trial_count=trial_count,
    )
    if attempt_index == 1:
        trial_directory = _create_trial_directory(
            generation_directory=generation_directory,
            case_name=case_directory.name,
            method=method,
            trial_index=trial_index,
            trial_count=trial_count,
        )
    elif not trial_directory.is_dir():
        raise FileNotFoundError(
            "Cannot add a retry Attempt because its logical Trial does not "
            f"exist: {trial_directory}"
        )
    attempt_directory = _prepare_attempt_directory(
        trial_directory=trial_directory,
        attempt_index=attempt_index,
    )
    request = {
        "case_name": case_directory.name,
        "case_directory": str(case_directory),
        "compilation_method": method,
        "trial_index": trial_index,
        "trial_count": trial_count,
        "attempt_index": attempt_index,
        "maximum_attempts": maximum_attempts,
        "trial_directory": str(attempt_directory),
        "agent_directory": str(attempt_directory / "agent"),
        "method_options": options,
    }
    log_path = attempt_directory / "compilation_log.json"
    process_environment = os.environ.copy()
    process_environment["PYTHONIOENCODING"] = "utf-8"
    process_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    exit_code: int | None = None
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    termination_reason = "process_exit"
    parent_exception: dict[str, str] | None = None
    interrupted = False

    # Keep the child-process request beside its Trial.
    request_path = attempt_directory / "_compilation_request.json"
    _write_json(request_path, request)
    command = [
        sys.executable,
        "-m",
        "RQ4.compilation.trial_runner",
        str(request_path),
    ]
    try:
        process = subprocess.Popen(
            command,
            # Launch the shared runner from its source root, even when outputs
            # belong to a separate representation experiment workspace.
            cwd=WORKSPACE_ROOT,
            env=process_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        # Popen 的默认文本读取会把单独的 ``\r`` 归一化为换行，进而把
        # 单行进度重新变成多行刷屏。保留原始换行符后，父进程才能原样
        # 转发子进程的回车更新。
        if process.stdout is not None:
            process.stdout.reconfigure(newline="")
        if process.stderr is not None:
            process.stderr.reconfigure(newline="")
        # subprocess.run(capture_output=True) previously hid every compiler
        # message until the Trial ended. Dedicated readers now both stream the
        # output to the terminal and retain it for compilation_log.json.
        stdout_thread = threading.Thread(
            target=_forward_process_stream,
            kwargs={
                "stream": process.stdout,
                "captured_parts": stdout_parts,
                "terminal": sys.stdout,
            },
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_forward_process_stream,
            kwargs={
                "stream": process.stderr,
                "captured_parts": stderr_parts,
                "terminal": sys.stderr,
            },
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            termination_reason = "timeout"
            print(
                f"[Compilation][{request['case_name']}]"
                f"[{request['compilation_method']}] Trial timed out after "
                f"{timeout_seconds:g}s; stopping the child process.",
                file=sys.stderr,
                flush=True,
            )
            parent_exception = {
                "type": type(exc).__name__,
                "message": (
                    "Compilation exceeded the configured timeout of "
                    f"{timeout_seconds:g} seconds."
                ),
                "traceback": "",
            }
            _stop_child_process(process)
            exit_code = process.returncode
        except KeyboardInterrupt:
            # Do not leave an expensive compiler child running after the user
            # stops RQ4. Finalize the Trial log first, then re-raise below.
            termination_reason = "keyboard_interrupt"
            parent_exception = {
                "type": "KeyboardInterrupt",
                "message": "Compilation was interrupted by the user.",
                "traceback": "",
            }
            interrupted = True
            print(
                f"[Compilation][{request['case_name']}]"
                f"[{request['compilation_method']}] Interrupt received; "
                "stopping the child process and finalizing its log.",
                file=sys.stderr,
                flush=True,
            )
            _stop_child_process(process)
            exit_code = process.returncode
        finally:
            stdout_thread.join()
            stderr_thread.join()
    except OSError as exc:
        termination_reason = "process_start_error"
        parent_exception = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        request_path.unlink(missing_ok=True)

    _record_subprocess_result(
        log_path=log_path,
        request=request,
        exit_code=exit_code,
        termination_reason=termination_reason,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        parent_exception=parent_exception,
    )
    attempt_record = _read_json(log_path)
    if attempt_record.get("status") == "success":
        _promote_successful_agent(
            attempt_directory=attempt_directory,
            trial_directory=trial_directory,
        )
    _write_trial_summary(
        trial_directory=trial_directory,
        latest_attempt_directory=attempt_directory,
    )
    if interrupted:
        raise CompilationTrialInterrupted(trial_directory)
    return trial_directory


def _child_main() -> int:
    if len(sys.argv) != 2:
        print(
            "trial_runner is an internal helper and expects one request file.",
            file=sys.stderr,
        )
        return 64
    return _execute_trial(Path(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(_child_main())
