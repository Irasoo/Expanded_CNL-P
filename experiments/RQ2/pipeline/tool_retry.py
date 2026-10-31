"""Independent utility for retrying unresolved rows."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path

from utils import (
    CONCURRENT_REQUESTS_PER_KEY,
    MAX_ASYNC_CONCURRENCY,
    MAX_ATTEMPTS,
    RATE_LIMITED_PROVIDERS,
    RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
    RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
    RETRY_DELAY_SECONDS,
    PipelineConfig,
    _read_csv,
    load_model_registry,
    load_settings,
    resolve_run_root,
    result_files,
    write_csv,
)


async def _retry(
    run_root: Path,
    *,
    max_concurrency: int = MAX_ASYNC_CONCURRENCY,
    concurrent_requests_per_key: int = CONCURRENT_REQUESTS_PER_KEY,
    rate_limited_providers: tuple[str, ...] = RATE_LIMITED_PROVIDERS,
    rate_limited_provider_max_concurrency: int = RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
    rate_limited_provider_requests_per_minute: int = RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
) -> tuple[int, int]:
    if (
        rate_limited_provider_max_concurrency < 1
        or rate_limited_provider_requests_per_minute < 1
    ):
        raise ValueError("Provider concurrency and requests per minute must be positive")
    limited_providers = {provider.strip().upper() for provider in rate_limited_providers}
    review_path = run_root / "manual_review.csv"
    if not review_path.is_file():
        print("No manual_review.csv; nothing to retry")
        return 0, 0
    review_fields, reviews = _read_csv(review_path)
    pending = [row for row in reviews if row.get("manual_score", "").strip() == "2"]
    if not pending:
        print("No unresolved rows to retry")
        return 0, 0

    configs = load_model_registry()
    file_data = {path.relative_to(run_root).as_posix(): (path, *_read_csv(path)) for path in result_files(run_root)}
    settings = load_settings()
    from llm.client import ChatCompletionClient

    providers = {
        model.provider
        for row in pending
        if (model := configs.get(row.get("model", ""))) is not None
    }
    clients: dict[str, ChatCompletionClient] = {}
    provider_limits: dict[str, int] = {}
    for provider in providers:
        endpoint = settings.endpoint_for(provider)
        provider_limit = max(
            1, len(endpoint.api_keys) * concurrent_requests_per_key
        )
        if provider in limited_providers:
            provider_limit = min(
                provider_limit,
                rate_limited_provider_max_concurrency,
            )
        provider_limits[provider] = provider_limit
        clients[provider] = ChatCompletionClient(
            endpoint.base_url,
            endpoint.api_keys,
            max_connections=min(max_concurrency, provider_limit),
            default_headers=(
                {"X-DashScope-Wait-Timeout": "30"}
                if provider == "DASHSCOPE"
                else None
            ),
        )
    concurrency = min(max_concurrency, max(1, sum(provider_limits.values())))
    semaphore = asyncio.Semaphore(concurrency)
    provider_semaphores = {
        provider: asyncio.Semaphore(limit)
        for provider, limit in provider_limits.items()
    }
    paced_providers = limited_providers & providers
    provider_rate_locks = {
        provider: asyncio.Lock() for provider in paced_providers
    }
    provider_next_start = {provider: 0.0 for provider in paced_providers}
    provider_start_interval = (
        60.0 / rate_limited_provider_requests_per_minute
    )
    persistence_lock = asyncio.Lock()
    print(f"Retrying {len(pending)} unresolved rows (concurrency={concurrency})")

    async def wait_for_provider_start(provider: str) -> None:
        if provider not in paced_providers:
            return
        async with provider_rate_locks[provider]:
            loop = asyncio.get_running_loop()
            delay = provider_next_start[provider] - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            provider_next_start[provider] = loop.time() + provider_start_interval

    async def retry_one(review: dict[str, str]) -> tuple[str, str, bool, str]:
        source = review.get("source_csv", "").strip()
        instance_id = review.get("instance_id", "").strip()
        data = file_data.get(source)
        if data is None:
            return source, instance_id, False, f"missing source CSV {source}"
        _, _, rows = data
        row = next((candidate for candidate in rows if candidate.get("instance_id", "").strip() == instance_id), None)
        if row is None:
            return source, instance_id, False, "missing instance row"
        model = configs.get(row.get("model", ""))
        if model is None:
            return source, instance_id, False, f"model not found in llm/models.yaml: {row.get('model', '')}"
        try:
            messages = json.loads(row.get("model_input", ""))
        except json.JSONDecodeError:
            return source, instance_id, False, "invalid model_input JSON"
        try:
            await wait_for_provider_start(model.provider)
            async with provider_semaphores[model.provider]:
                async with semaphore:
                    print(f"  [REQUEST] source={source} instance={instance_id}")
                    request_options = (
                        {"extra_body": model.extra_body} if model.extra_body else {}
                    )
                    if model.api_style != "chat_completions":
                        request_options["api_style"] = model.api_style
                    if model.provider == "DASHSCOPE":
                        request_options["timeout"] = 150.0
                    output = await clients[model.provider].complete_async(
                        model=model.model_id,
                        messages=messages,
                        max_attempts=MAX_ATTEMPTS,
                        retry_delay=RETRY_DELAY_SECONDS,
                        max_tokens=None,
                        temperature=0,
                        reasoning_effort=model.reasoning_effort,
                        **request_options,
                    )
        except Exception as error:
            return source, instance_id, False, str(error)
        row["model_output"] = output
        row["extracted_answer"] = ""
        row["score"] = ""
        review["model_output"] = output
        review["manual_score"] = ""
        # Both files use atomic replacement. Keep this section serialized so
        # concurrent completions for the same CSV cannot overwrite each other.
        # Persist the result CSV first: if interrupted between the two writes,
        # retrying the still-pending review is safe and does not lose output.
        async with persistence_lock:
            path, fields, rows = data
            write_csv(path, fields, rows)
            write_csv(review_path, review_fields, reviews)
        return source, instance_id, True, output

    success_count = failure_count = 0
    tasks = [asyncio.create_task(retry_one(row)) for row in pending]
    try:
        for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
            source, instance_id, success, detail = await task
            if success:
                success_count += 1
                print(
                    f"  [OK/SAVED] {completed}/{len(tasks)} "
                    f"source={source} instance={instance_id}"
                )
            else:
                failure_count += 1
                reason = detail.replace("\n", " ")[:160]
                print(
                    f"  [ERROR] {completed}/{len(tasks)} source={source} "
                    f"instance={instance_id}: {reason}"
                )
    finally:
        for client in clients.values():
            await client.aclose()
    return success_count, failure_count


def run(config: PipelineConfig, *, run_root: Path | None = None) -> int:
    run_root = run_root or resolve_run_root(config)
    success, failure = asyncio.run(
        _retry(
            run_root,
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
    print(f"Retry complete: success={success}, failed={failure}")
    return success


if __name__ == "__main__":
    from main import build_config

    run(build_config())
