"""Step 1: execute every selected task/model/prompt combination."""

from __future__ import annotations

import asyncio
import csv
import json
import time
from typing import Any
from collections import deque
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from utils import (
    CONCURRENT_REQUESTS_PER_KEY,
    INSTANCE_ROOT,
    MAX_ASYNC_CONCURRENCY,
    MAX_ATTEMPTS,
    MAX_CONSECUTIVE_MODEL_FAILURES,
    OUTPUT_ENCODING,
    RATE_LIMITED_PROVIDERS,
    RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
    RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
    RETRY_DELAY_SECONDS,
    AsyncCompletionClient,
    PipelineConfig,
    RunSelection,
    Settings,
    TaskInstance,
    ensure_result_file,
    generate_run_id,
    load_instances,
    load_model_registry,
    load_settings,
    print_run_info,
    read_prompt,
    resolve_selection,
    result_csv_path,
    upsert_run_registry,
    write_csv,
    write_run_readme,
    RESULT_FIELDS,
    _read_csv,
)


@dataclass(frozen=True)
class RunOutcome:
    scheduled: int
    errors: int
    model_errors: dict[str, int]


@dataclass(frozen=True)
class RequestJob:
    path: Path
    task_id: str
    language: str
    model_key: str
    model_id: str
    provider: str
    reasoning_effort: str | None
    extra_body: dict[str, Any] | None
    api_style: str
    instance_id: int
    instance: TaskInstance
    system_prompt: str


async def _run_async_impl(
    run_root: Path,
    settings: Settings,
    selection: RunSelection,
    client: AsyncCompletionClient | dict[str, AsyncCompletionClient],
    *,
    max_concurrency: int = MAX_ASYNC_CONCURRENCY,
    concurrent_requests_per_key: int = CONCURRENT_REQUESTS_PER_KEY,
    rate_limited_providers: tuple[str, ...] = RATE_LIMITED_PROVIDERS,
    rate_limited_provider_max_concurrency: int = RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
    rate_limited_provider_requests_per_minute: int = RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
) -> RunOutcome:
    if (
        rate_limited_provider_max_concurrency < 1
        or rate_limited_provider_requests_per_minute < 1
    ):
        raise ValueError("Provider concurrency and requests per minute must be positive")
    limited_providers = {provider.strip().upper() for provider in rate_limited_providers}
    if isinstance(client, dict):
        provider_limits = {
            provider: max(
                1,
                len(settings.endpoint_for(provider).api_keys)
                * concurrent_requests_per_key,
            )
            for provider in client
        }
        for provider in limited_providers & provider_limits.keys():
            provider_limits[provider] = min(
                provider_limits[provider],
                rate_limited_provider_max_concurrency,
            )
        concurrency = min(max_concurrency, sum(provider_limits.values()))
    else:
        key_count = len(settings.api_keys)
        concurrency = min(
            max_concurrency,
            max(1, key_count * concurrent_requests_per_key),
        )
        provider_limits = {}
    result_paths: list[Path] = []
    jobs_by_model: dict[str, deque[RequestJob]] = {
        model.key: deque() for model in selection.models
    }
    completed = 0
    errors = 0
    model_errors: dict[str, int] = defaultdict(int)

    def persist_result(job: RequestJob, output: str) -> None:
        """Persist each completed request immediately so interrupted runs resume."""
        messages = [
            {"role": "system", "content": job.system_prompt},
            {"role": "user", "content": job.instance.content},
        ]
        row = {
            "task_id": job.task_id,
            "instance_id": job.instance_id,
            "model": job.model_key,
            "language": job.language,
            "instance_content": job.instance.content,
            "model_input": json.dumps(messages, ensure_ascii=False),
            "standard_output": job.instance.standard_output,
            "model_output": output,
            "extracted_answer": "",
            "score": "",
        }
        with job.path.open("a", encoding=OUTPUT_ENCODING, newline="") as handle:
            csv.DictWriter(handle, fieldnames=RESULT_FIELDS).writerow(row)

    async def request_one(job: RequestJob) -> bool:
        nonlocal completed, errors
        messages = [
            {"role": "system", "content": job.system_prompt},
            {"role": "user", "content": job.instance.content},
        ]
        succeeded = True
        try:
            request_client = client[job.provider] if isinstance(client, dict) else client
            request_options: dict[str, Any] = {}
            if job.extra_body:
                request_options["extra_body"] = job.extra_body
            if job.api_style != "chat_completions":
                request_options["api_style"] = job.api_style
            if job.provider == "DASHSCOPE":
                request_options["timeout"] = 150.0
            output = await request_client.complete_async(
                model=job.model_id,
                messages=messages,
                max_attempts=MAX_ATTEMPTS,
                retry_delay=RETRY_DELAY_SECONDS,
                max_tokens=None,
                temperature=0,
                reasoning_effort=job.reasoning_effort,
                **request_options,
            )
        except Exception as error:  # Persist failures so retry can reproduce the input.
            output = f"error: {error}"
            succeeded = False
            errors += 1
            model_errors[job.model_key] += 1
        persist_result(job, output)
        completed += 1
        state = "OK" if succeeded else "ERROR"
        print(
            f"  [{state}] {completed:4d}/{total_jobs:4d} task={job.task_id} "
            f"model={job.model_key} language={job.language} instance={job.instance_id}"
        )
        return succeeded

    for task_id in selection.task_ids:
        instances = load_instances(task_id)
        if selection.instance_limit is not None:
            instances = instances[:selection.instance_limit]
        for language in selection.languages:
            if (task_id, language) not in selection.prompt_paths:
                continue
            system_prompt = read_prompt(task_id, language)
            for model in selection.models:
                path = result_csv_path(run_root, task_id, model.key, language)
                already_completed = ensure_result_file(path)
                if path not in result_paths:
                    result_paths.append(path)
                for instance_id, instance in enumerate(instances, start=1):
                    if str(instance_id) in already_completed:
                        continue
                    jobs_by_model[model.key].append(RequestJob(
                        path=path,
                        task_id=task_id,
                        language=language,
                        model_key=model.key,
                        model_id=model.model_id,
                        provider=model.provider,
                        reasoning_effort=model.reasoning_effort,
                        extra_body=model.extra_body,
                        api_style=model.api_style,
                        instance_id=instance_id,
                        instance=instance,
                        system_prompt=system_prompt,
                    ))

    total_jobs = sum(len(jobs) for jobs in jobs_by_model.values())
    print(
        f"Starting run {run_root.name}: {total_jobs} requests, concurrency={concurrency}, "
        f"model failure limit={MAX_CONSECUTIVE_MODEL_FAILURES}"
    )
    if provider_limits:
        capacities = ", ".join(
            f"{provider}={limit}" for provider, limit in sorted(provider_limits.items())
        )
        print(f"  Provider concurrency: {capacities}")

    # Fairly fill one global concurrency pool from every model queue. Each
    # model begins with a limited health-probe budget; its first success opens
    # the rest of that queue. A request counts as failed only after all of its
    # own MAX_ATTEMPTS API calls fail.
    model_order = deque(model.key for model in selection.models if jobs_by_model[model.key])
    model_provider = {model.key: model.provider for model in selection.models}
    paced_providers = limited_providers & set(model_provider.values())
    provider_start_interval = 60.0 / rate_limited_provider_requests_per_minute
    if paced_providers:
        print(
            "  Provider pacing: "
            f"providers={','.join(sorted(paced_providers))}, "
            f"max_in_flight_per_provider={rate_limited_provider_max_concurrency}, "
            f"starts_per_minute_per_provider="
            f"{rate_limited_provider_requests_per_minute}"
        )
    failure_streak: dict[str, int] = defaultdict(int)
    model_is_healthy: dict[str, bool] = defaultdict(bool)
    probe_budget: dict[str, int] = {
        model_key: MAX_CONSECUTIVE_MODEL_FAILURES for model_key in model_order
    }
    in_flight: dict[asyncio.Task[bool], tuple[str, str]] = {}
    provider_in_flight: dict[str, int] = defaultdict(int)
    provider_next_dispatch: dict[str, float] = defaultdict(float)

    def next_model() -> str | None:
        """Select one dispatchable model and rotate it to the back."""
        for _ in range(len(model_order)):
            model_key = model_order.popleft()
            model_order.append(model_key)
            if not jobs_by_model[model_key]:
                continue
            if failure_streak[model_key] >= MAX_CONSECUTIVE_MODEL_FAILURES:
                continue
            provider = model_provider[model_key]
            if provider in paced_providers:
                if (
                    provider_in_flight[provider]
                    >= rate_limited_provider_max_concurrency
                ):
                    continue
                if time.monotonic() < provider_next_dispatch[provider]:
                    continue
            if (
                provider_limits
                and provider_in_flight[provider] >= provider_limits[provider]
            ):
                continue
            if model_is_healthy[model_key] or probe_budget[model_key] > 0:
                return model_key
        return None

    def next_rate_delay() -> float | None:
        """Return the shortest provider cooldown that can unlock queued work."""
        now = time.monotonic()
        delays: list[float] = []
        for model_key in model_order:
            if not jobs_by_model[model_key]:
                continue
            if failure_streak[model_key] >= MAX_CONSECUTIVE_MODEL_FAILURES:
                continue
            provider = model_provider[model_key]
            if provider not in paced_providers:
                continue
            if (
                provider_in_flight[provider]
                >= rate_limited_provider_max_concurrency
            ):
                continue
            if (
                provider_limits
                and provider_in_flight[provider] >= provider_limits[provider]
            ):
                continue
            delay = provider_next_dispatch[provider] - now
            if delay > 0:
                delays.append(delay)
        return min(delays) if delays else None

    def apply_result(model_key: str, succeeded: bool) -> None:
        if succeeded:
            failure_streak[model_key] = 0
            model_is_healthy[model_key] = True
            return
        failure_streak[model_key] += 1
        if failure_streak[model_key] == MAX_CONSECUTIVE_MODEL_FAILURES:
            print(
                f"  [PAUSE] model={model_key} after "
                f"{MAX_CONSECUTIVE_MODEL_FAILURES} consecutive failed requests"
            )

    while any(jobs_by_model.values()) or in_flight:
        while len(in_flight) < concurrency:
            model_key = next_model()
            if model_key is None:
                break
            if not model_is_healthy[model_key]:
                probe_budget[model_key] -= 1
            provider = model_provider[model_key]
            task = asyncio.create_task(request_one(jobs_by_model[model_key].popleft()))
            in_flight[task] = (model_key, provider)
            provider_in_flight[provider] += 1
            if provider in paced_providers:
                provider_next_dispatch[provider] = (
                    time.monotonic() + provider_start_interval
                )

        if in_flight:
            rate_delay = next_rate_delay()
            done, _ = await asyncio.wait(
                in_flight,
                timeout=rate_delay,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                continue
            for task in done:
                model_key, provider = in_flight.pop(task)
                provider_in_flight[provider] -= 1
                apply_result(model_key, task.result())
            continue

        rate_delay = next_rate_delay()
        if rate_delay is not None:
            await asyncio.sleep(rate_delay)
            continue

        # Only paused model queues remain. Give each one a concurrent health
        # check; one success reopens that model, while an all-failure round
        # terminates without spinning forever.
        retry_models = [
            model_key for model_key in model_order if jobs_by_model[model_key]
        ]
        if not retry_models:
            break
        print("  [RETRY] probing paused models")
        retry_tasks: dict[asyncio.Task[bool], str] = {}
        retry_provider_counts: dict[str, int] = defaultdict(int)
        for model_key in retry_models[:concurrency]:
            provider = model_provider[model_key]
            if (
                provider_limits
                and retry_provider_counts[provider] >= provider_limits[provider]
            ):
                continue
            if (
                provider in paced_providers
                and retry_provider_counts[provider]
                >= rate_limited_provider_max_concurrency
            ):
                continue
            if provider in paced_providers:
                delay = provider_next_dispatch[provider] - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                provider_next_dispatch[provider] = (
                    time.monotonic() + provider_start_interval
                )
            failure_streak[model_key] = MAX_CONSECUTIVE_MODEL_FAILURES - 1
            probe_budget[model_key] = 0
            task = asyncio.create_task(request_one(jobs_by_model[model_key].popleft()))
            retry_tasks[task] = model_key
            retry_provider_counts[provider] += 1
        retry_results = await asyncio.gather(*retry_tasks)
        any_success = False
        for task, succeeded in zip(retry_tasks, retry_results):
            model_key = retry_tasks[task]
            apply_result(model_key, succeeded)
            any_success = any_success or succeeded
        if not any_success:
            print("  [STOP] Every remaining model failed its retry probe; recording skipped requests")
            break

    # Do not silently lose work when every model remains unavailable.  These
    # rows enter the existing manual-review/retry flow with their exact input.
    for model_key, pending in jobs_by_model.items():
        while pending:
            job = pending.popleft()
            message = (
                "error: skipped after repeated model-level request failures "
                f"(limit={MAX_CONSECUTIVE_MODEL_FAILURES})"
            )
            persist_result(job, message)
            completed += 1
            errors += 1
            model_errors[model_key] += 1
            print(
                f"  [SKIPPED] {completed:4d}/{total_jobs:4d} task={job.task_id} "
                f"model={job.model_key} language={job.language} instance={job.instance_id}"
            )
    for path in result_paths:
        fields, rows = _read_csv(path)
        rows.sort(key=lambda row: int(row["instance_id"]))
        write_csv(path, fields, rows)
    return RunOutcome(total_jobs, errors, dict(model_errors))


async def _run_async(
    run_root: Path,
    settings: Settings,
    selection: RunSelection,
    client: AsyncCompletionClient | None = None,
    *,
    max_concurrency: int = MAX_ASYNC_CONCURRENCY,
    concurrent_requests_per_key: int = CONCURRENT_REQUESTS_PER_KEY,
    rate_limited_providers: tuple[str, ...] = RATE_LIMITED_PROVIDERS,
    rate_limited_provider_max_concurrency: int = RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
    rate_limited_provider_requests_per_minute: int = RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
) -> RunOutcome:
    owns_client = client is None
    if client is None:
        from llm.client import ChatCompletionClient

        client = {}
        for model in selection.models:
            if model.provider in client:
                continue
            endpoint = settings.endpoint_for(model.provider)
            client[model.provider] = ChatCompletionClient(
                endpoint.base_url,
                endpoint.api_keys,
                max_connections=min(
                    max_concurrency,
                    len(endpoint.api_keys) * concurrent_requests_per_key,
                ),
                default_headers=(
                    {"X-DashScope-Wait-Timeout": "30"}
                    if model.provider == "DASHSCOPE"
                    else None
                ),
            )
    try:
        return await _run_async_impl(
            run_root,
            settings,
            selection,
            client,
            max_concurrency=max_concurrency,
            concurrent_requests_per_key=concurrent_requests_per_key,
            rate_limited_providers=rate_limited_providers,
            rate_limited_provider_max_concurrency=rate_limited_provider_max_concurrency,
            rate_limited_provider_requests_per_minute=(
                rate_limited_provider_requests_per_minute
            ),
        )
    finally:
        if owns_client:
            clients = client.values() if isinstance(client, dict) else (client,)
            for provider_client in clients:
                close = getattr(provider_client, "aclose", None)
                if close is not None:
                    await close()


def _final_status(outcome: RunOutcome, selection: RunSelection) -> tuple[str, dict[str, str]]:
    if outcome.scheduled and outcome.errors == outcome.scheduled:
        status = "failed"
    elif outcome.errors or selection.skipped:
        status = "partial"
    else:
        status = "complete"
    model_status = {
        model.key: ("failed" if outcome.model_errors.get(model.key, 0) else "complete")
        for model in selection.models
    }
    return status, model_status


def run(config: PipelineConfig, client: AsyncCompletionClient | None = None) -> Path:
    settings = load_settings()
    selection = resolve_selection(config, load_model_registry())
    print_run_info(selection, config.result_base)
    result_base = config.result_base.resolve()
    run_id = config.run_id or generate_run_id(result_base)
    run_root = result_base / run_id
    if run_root.exists() and not config.run_id:
        raise FileExistsError(f"Generated run directory already exists: {run_root}")

    write_run_readme(run_root, selection=selection, status="running")
    upsert_run_registry(run_root, selection, "running")
    try:
        outcome = asyncio.run(
            _run_async(
                run_root,
                settings,
                selection,
                client,
                max_concurrency=config.max_concurrency,
                concurrent_requests_per_key=config.concurrent_requests_per_key,
                rate_limited_providers=config.rate_limited_providers,
                rate_limited_provider_max_concurrency=(
                    config.rate_limited_provider_max_concurrency
                ),
                rate_limited_provider_requests_per_minute=(
                    config.rate_limited_provider_requests_per_minute
                ),
            )
        )
    except BaseException:
        write_run_readme(run_root, selection=selection, status="failed")
        upsert_run_registry(run_root, selection, "failed")
        raise
    status, model_status = _final_status(outcome, selection)
    write_run_readme(run_root, selection=selection, status=status)
    upsert_run_registry(run_root, selection, status)
    print(f"Step 1 complete: {run_root} ({status})")
    return run_root


if __name__ == "__main__":
    from main import build_config

    run(build_config())
