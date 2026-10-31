"""Submit this project's Qwen workload as one asynchronous Batch API job.

Unlike Batch Chat, the file-based Batch API uploads all requests in one JSONL
file and creates one asynchronous job. Run from the experiments/RQ2 directory:

    python -m llm.qwen_batch

Add ``--no-wait`` to return immediately after submission. Resume and import a
previously submitted job with:

    python -m llm.qwen_batch --resume ../../experiment_results/RQ2/results/run_results/run_YYYYMMDD_NNN
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from llm.client import ChatCompletionClient
from utils import (
    OUTPUT_ENCODING,
    RESULT_FIELDS,
    PipelineConfig,
    RunSelection,
    _read_csv,
    ensure_result_file,
    generate_run_id,
    load_instances,
    load_model_registry,
    load_settings,
    read_prompt,
    resolve_selection,
    result_csv_path,
    upsert_run_registry,
    write_csv,
    write_run_readme,
)


QWEN_API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
BATCH_ENDPOINT = "/v1/chat/completions"
DEFAULT_COMPLETION_WINDOW = "24h"
DEFAULT_POLL_INTERVAL_SECONDS = 60.0
MAX_REQUESTS_PER_FILE = 50_000
MAX_FILE_BYTES = 500 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
TERMINAL_STATUSES = {"completed", "failed", "expired", "cancelled"}

INPUT_FILENAME = "qwen_batch_input.jsonl"
JOBS_FILENAME = "qwen_batch_jobs.jsonl"
STATE_FILENAME = "qwen_batch_state.json"
OUTPUT_FILENAME = "qwen_batch_output.jsonl"
ERROR_FILENAME = "qwen_batch_errors.jsonl"


def _log(stage: str, message: str) -> None:
    """Print one immediately visible, timestamped progress event."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{stage:<9}] {message}", flush=True)


def _openai_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError(
            "The openai package is required; run: pip install -U openai"
        ) from error
    return OpenAI(api_key=api_key, base_url=QWEN_API_BASE_URL)


def _validate_qwen_selection(selection: RunSelection) -> Any:
    """A Batch input file must contain exactly one supported Qwen model."""
    if len(selection.models) != 1:
        names = ", ".join(model.key for model in selection.models)
        raise ValueError(
            "Qwen file Batch mode requires exactly one model because every "
            f"request in one input file must use the same model; selected: {names}"
        )
    model = selection.models[0]
    if (
        model.provider != "DASHSCOPE"
        or not model.model_id.casefold().startswith("qwen")
        or model.api_style != "chat_completions"
    ):
        raise ValueError(
            "Qwen file Batch mode only accepts one DashScope qwen* Chat model; "
            f"selected {model.key!r} ({model.model_id!r}, {model.provider!r})"
        )
    return model


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: each line must be an object")
        rows.append(value)
    return rows


def _write_state(run_root: Path, state: Mapping[str, Any]) -> None:
    path = run_root / STATE_FILENAME
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _read_state(run_root: Path) -> dict[str, Any]:
    path = run_root / STATE_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"Batch state not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Invalid Batch state: {path}")
    return value


def _request_body(model: Any, messages: list[dict[str, str]]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model.model_id,
        "messages": messages,
        "temperature": 0,
        "stream": False,
    }
    if model.reasoning_effort:
        body["reasoning_effort"] = model.reasoning_effort
    if model.extra_body:
        # enable_thinking must remain at body top level in Batch JSONL.
        body.update(model.extra_body)
    return body


def _prepare_project_batch(
    config: PipelineConfig,
) -> tuple[Path, RunSelection, dict[str, Any]]:
    _log("PRECHECK", "Loading project tasks, prompts, instances, and model registry")
    selection = resolve_selection(config, load_model_registry())
    model = _validate_qwen_selection(selection)
    _log(
        "PRECHECK",
        f"Model accepted: key={model.key}, API model={model.model_id}, "
        f"provider={model.provider}",
    )
    _log(
        "PRECHECK",
        f"Scope: tasks={len(selection.task_ids)}, "
        f"prompt variants={len(selection.languages)}, "
        f"instance limit={selection.instance_limit or 'all'}",
    )
    result_base = config.result_base.resolve()
    run_id = config.run_id or generate_run_id(result_base)
    run_root = result_base / run_id
    if run_root.exists():
        raise FileExistsError(
            f"Run directory already exists: {run_root}. Use --resume for an "
            "already submitted Batch job, or clear run.run_id for a new run."
        )

    run_root.mkdir(parents=True)
    _log("PREPARE", f"Created run directory: {run_root}")
    write_run_readme(run_root, selection=selection, status="preparing batch")
    upsert_run_registry(run_root, selection, "running")

    requests: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    for task_id in selection.task_ids:
        instances = load_instances(task_id)
        if selection.instance_limit is not None:
            instances = instances[: selection.instance_limit]
        for language in selection.languages:
            if (task_id, language) not in selection.prompt_paths:
                continue
            system_prompt = read_prompt(task_id, language)
            path = result_csv_path(run_root, task_id, model.key, language)
            ensure_result_file(path)
            before_count = len(requests)
            for instance_id, instance in enumerate(instances, start=1):
                custom_id = f"task{task_id}-{language}-{instance_id}"
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": instance.content},
                ]
                request = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": BATCH_ENDPOINT,
                    "body": _request_body(model, messages),
                }
                encoded_line = (
                    json.dumps(request, ensure_ascii=False) + "\n"
                ).encode("utf-8")
                if len(encoded_line) > MAX_LINE_BYTES:
                    raise ValueError(
                        f"Batch request {custom_id!r} exceeds the 1 MB line limit"
                    )
                requests.append(request)
                jobs.append(
                    {
                        "custom_id": custom_id,
                        "result_path": path.relative_to(run_root).as_posix(),
                        "row": {
                            "task_id": task_id,
                            "instance_id": str(instance_id),
                            "model": model.key,
                            "language": language,
                            "instance_content": instance.content,
                            "model_input": json.dumps(messages, ensure_ascii=False),
                            "standard_output": instance.standard_output,
                            "model_output": "",
                            "extracted_answer": "",
                            "score": "",
                        },
                    }
                )
            _log(
                "PACK",
                f"task={task_id}, prompt={language}: "
                f"added={len(requests) - before_count}, total={len(requests)}",
            )

    if not requests:
        raise ValueError("No requests remain for the Batch job")
    if len(requests) > MAX_REQUESTS_PER_FILE:
        raise ValueError(
            f"Batch contains {len(requests)} requests; maximum is "
            f"{MAX_REQUESTS_PER_FILE}"
        )
    input_path = run_root / INPUT_FILENAME
    jobs_path = run_root / JOBS_FILENAME
    _write_jsonl(input_path, requests)
    _write_jsonl(jobs_path, jobs)
    if input_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Batch input file exceeds the 500 MB limit")

    state: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "status": "prepared",
        "model_key": model.key,
        "model_id": model.model_id,
        "request_count": len(requests),
        "input_file": INPUT_FILENAME,
        "jobs_file": JOBS_FILENAME,
        "completion_window": DEFAULT_COMPLETION_WINDOW,
    }
    _write_state(run_root, state)
    _log(
        "READY",
        f"One JSONL is ready: requests={len(requests)}, "
        f"size={input_path.stat().st_size / 1024:.1f} KiB",
    )
    _log("READY", f"Input: {input_path}")
    _log("READY", f"Recovery state: {run_root / STATE_FILENAME}")
    return run_root, selection, state


def _submit(client: Any, run_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("input_file_id"):
        input_path = run_root / str(state["input_file"])
        started = time.monotonic()
        _log(
            "UPLOAD",
            f"Uploading {input_path.name} "
            f"({input_path.stat().st_size / 1024:.1f} KiB); please wait...",
        )
        uploaded = client.files.create(
            file=input_path, purpose="batch"
        )
        state["input_file_id"] = uploaded.id
        state["status"] = "file_uploaded"
        _write_state(run_root, state)
        _log(
            "UPLOAD",
            f"Completed in {time.monotonic() - started:.1f}s: file_id={uploaded.id}",
        )
    else:
        _log("RESUME", f"Reusing uploaded file: {state['input_file_id']}")

    if not state.get("batch_id"):
        started = time.monotonic()
        _log(
            "SUBMIT",
            f"Creating ONE remote Batch job for {state['request_count']} requests...",
        )
        batch = client.batches.create(
            input_file_id=str(state["input_file_id"]),
            endpoint=BATCH_ENDPOINT,
            completion_window=str(state["completion_window"]),
            metadata={
                "ds_name": str(state["run_id"])[:100],
                "ds_description": "TOSEM RQ2 Qwen evaluation"[:200],
            },
        )
        state["batch_id"] = batch.id
        state["status"] = batch.status
        _write_state(run_root, state)
        _log(
            "SUBMIT",
            f"Created in {time.monotonic() - started:.1f}s: "
            f"batch_id={batch.id}, status={batch.status}",
        )
    else:
        _log("RESUME", f"Reusing Batch job: {state['batch_id']}")
    return state


def _wait_for_batch(
    client: Any,
    run_root: Path,
    state: dict[str, Any],
    poll_interval: float,
) -> tuple[Any, dict[str, Any]]:
    if poll_interval < 10:
        raise ValueError("poll_interval must be at least 10 seconds")
    batch_id = str(state.get("batch_id") or "")
    if not batch_id:
        raise ValueError("Batch state contains no batch_id")

    started = time.monotonic()
    poll_number = 0
    while True:
        poll_number += 1
        _log("POLL", f"Query #{poll_number}: batch_id={batch_id}")
        batch = client.batches.retrieve(batch_id)
        state["status"] = batch.status
        counts = getattr(batch, "request_counts", None)
        if counts is not None:
            state["request_counts"] = {
                "total": getattr(counts, "total", 0),
                "completed": getattr(counts, "completed", 0),
                "failed": getattr(counts, "failed", 0),
            }
        _write_state(run_root, state)
        request_counts = state.get("request_counts", {})
        _log(
            "STATUS",
            f"status={batch.status}; total={request_counts.get('total', '?')}, "
            f"completed={request_counts.get('completed', '?')}, "
            f"failed={request_counts.get('failed', '?')}; "
            f"elapsed={time.monotonic() - started:.0f}s",
        )
        if batch.status in TERMINAL_STATUSES:
            return batch, state
        _log("WAIT", f"Next status query in {poll_interval:g}s (Ctrl+C is safe)")
        time.sleep(poll_interval)


def _download_file(client: Any, file_id: str, path: Path) -> None:
    started = time.monotonic()
    _log("DOWNLOAD", f"Downloading file_id={file_id} -> {path.name}")
    content = client.files.content(file_id)
    write_to_file = getattr(content, "write_to_file", None)
    if callable(write_to_file):
        write_to_file(path)
    else:
        raw = getattr(content, "content", content)
        if isinstance(raw, str):
            path.write_text(raw, encoding="utf-8")
        elif isinstance(raw, bytes):
            path.write_bytes(raw)
        else:
            raise TypeError(
                f"Unsupported downloaded file content type: {type(raw)!r}"
            )
    _log(
        "DOWNLOAD",
        f"Saved {path.stat().st_size / 1024:.1f} KiB in "
        f"{time.monotonic() - started:.1f}s: {path}",
    )


def _response_text(result: Mapping[str, Any]) -> str:
    response = result.get("response")
    if not isinstance(response, Mapping):
        raise ValueError("missing response object")
    status_code = response.get("status_code")
    if status_code != 200:
        raise ValueError(f"HTTP {status_code}: {response.get('body')}")
    body = response.get("body")
    if not isinstance(body, Mapping):
        raise ValueError("missing response body")
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return ChatCompletionClient._parse_response(encoded)


def _error_text(result: Mapping[str, Any]) -> str:
    error = result.get("error")
    if isinstance(error, Mapping):
        code = error.get("code", "unknown")
        message = error.get("message", error)
        return f"error: Qwen Batch {code}: {message}"
    return f"error: Qwen Batch request failed: {error or result}"


def _set_registry_status(run_root: Path, status: str) -> None:
    registry_path = run_root.parent / "run_registry.csv"
    if not registry_path.is_file():
        return
    fields, rows = _read_csv(registry_path)
    for row in rows:
        if row.get("run_id") == run_root.name:
            row["status"] = status
    write_csv(registry_path, fields, rows)


def _import_results(
    client: Any,
    run_root: Path,
    batch: Any,
    state: dict[str, Any],
) -> tuple[int, int]:
    _log("IMPORT", "Downloading and parsing Batch result files")
    output_file_id = str(getattr(batch, "output_file_id", "") or "")
    error_file_id = str(getattr(batch, "error_file_id", "") or "")
    output_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    if output_file_id:
        output_path = run_root / OUTPUT_FILENAME
        _download_file(client, output_file_id, output_path)
        output_rows = _read_jsonl(output_path)
        state["output_file_id"] = output_file_id
    if error_file_id:
        error_path = run_root / ERROR_FILENAME
        _download_file(client, error_file_id, error_path)
        error_rows = _read_jsonl(error_path)
        state["error_file_id"] = error_file_id

    successes: dict[str, str] = {}
    failures: dict[str, str] = {}
    for result in output_rows:
        custom_id = str(result.get("custom_id") or "")
        try:
            successes[custom_id] = _response_text(result)
        except Exception as error:
            failures[custom_id] = f"error: invalid Qwen Batch response: {error}"
    for result in error_rows:
        failures[str(result.get("custom_id") or "")] = _error_text(result)
    _log(
        "IMPORT",
        f"Downloaded records: successful={len(successes)}, failed={len(failures)}",
    )

    jobs = _read_jsonl(run_root / str(state["jobs_file"]))
    rows_by_path: dict[Path, list[dict[str, str]]] = defaultdict(list)
    failure_count = 0
    for job in jobs:
        custom_id = str(job["custom_id"])
        row = {key: str(value) for key, value in dict(job["row"]).items()}
        if custom_id in successes:
            row["model_output"] = successes[custom_id]
        else:
            row["model_output"] = failures.get(
                custom_id, "error: Qwen Batch returned no result for this request"
            )
            failure_count += 1
        rows_by_path[run_root / str(job["result_path"])].append(row)

    for path, new_rows in rows_by_path.items():
        fields, existing_rows = _read_csv(path)
        existing_ids = {row.get("instance_id", "") for row in existing_rows}
        existing_rows.extend(
            row for row in new_rows if row["instance_id"] not in existing_ids
        )
        existing_rows.sort(key=lambda row: int(row["instance_id"]))
        write_csv(path, fields or RESULT_FIELDS, existing_rows)
        _log(
            "SAVE",
            f"CSV={path.relative_to(run_root).as_posix()}: "
            f"batch_rows={len(new_rows)}, total_rows={len(existing_rows)}",
        )

    state["status"] = "imported"
    state["imported_successes"] = len(jobs) - failure_count
    state["imported_failures"] = failure_count
    _write_state(run_root, state)
    _log(
        "IMPORT",
        f"Import finished: succeeded={len(jobs) - failure_count}, "
        f"failed={failure_count}",
    )
    return len(jobs) - failure_count, failure_count


def _finish_project(config: PipelineConfig, run_root: Path) -> None:
    from pipeline.step2_judge import run as step2
    from pipeline.step3_score import run as step3

    _log("STEP 2", "Starting answer extraction and judging")
    step2(config, run_root=run_root)
    _log("STEP 2", "Completed")
    _log("STEP 3", "Starting score aggregation and report generation")
    step3(config, run_root=run_root)
    _log("STEP 3", "Completed")


def run_project(
    *,
    resume: Path | None = None,
    wait: bool = True,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> Path:
    from utils.config import load_app_config

    config = load_app_config().pipeline
    _log(
        "START",
        "Mode=Qwen file Batch API; requests are packed into one asynchronous job",
    )
    _log(
        "CONFIG",
        f"tasks={','.join(str(value) for value in config.task_ids)}, "
        f"languages={','.join(str(value) for value in config.languages)}, "
        f"models={','.join(str(value) for value in config.models)}, "
        f"instance_count={config.instance_count}",
    )
    settings = load_settings()
    endpoint = settings.endpoint_for("DASHSCOPE")
    _log(
        "AUTH",
        f"DashScope credentials found: key_count={len(endpoint.api_keys)} "
        "(key values are hidden)",
    )
    client = _openai_client(endpoint.api_keys[0])

    selection: RunSelection | None = None
    if resume is None:
        run_root, selection, state = _prepare_project_batch(config)
    else:
        run_root = resume.resolve()
        _log("RESUME", f"Loading saved run: {run_root}")
        state = _read_state(run_root)
        _log(
            "RESUME",
            f"Saved status={state.get('status')}, "
            f"requests={state.get('request_count')}, "
            f"batch_id={state.get('batch_id', 'not-created')}",
        )

    try:
        state = _submit(client, run_root, state)
        if not wait:
            _log(
                "DETACHED",
                "Batch is running remotely; the local process can now exit safely",
            )
            _log(
                "RESUME",
                f"python -m llm.qwen_batch --resume \"{run_root}\"",
            )
            return run_root
        batch, state = _wait_for_batch(client, run_root, state, poll_interval)
        if batch.status != "completed":
            _set_registry_status(run_root, "failed")
            raise RuntimeError(
                f"Qwen Batch {batch.id} ended with status {batch.status!r}"
            )
        succeeded, failed = _import_results(client, run_root, batch, state)
        _finish_project(config, run_root)
        _set_registry_status(run_root, "partial" if failed else "complete")
        if selection is not None:
            write_run_readme(
                run_root,
                selection=selection,
                status="partial" if failed else "complete",
            )
        _log(
            "COMPLETE",
            f"succeeded={succeeded}, failed={failed}, run={run_root}",
        )
        return run_root
    except BaseException as error:
        _log("ERROR", f"{type(error).__name__}: {error}")
        if state.get("status") not in {"validating", "in_progress", "finalizing"}:
            _set_registry_status(run_root, "failed")
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Submit all configured project requests as one Qwen file Batch job."
        )
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="resume, download, and import a previously submitted run directory",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="return after creating the remote Batch job",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help=f"status polling interval in seconds (default: {DEFAULT_POLL_INTERVAL_SECONDS:g})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run_project(
        resume=args.resume,
        wait=not args.no_wait,
        poll_interval=args.poll_interval,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
