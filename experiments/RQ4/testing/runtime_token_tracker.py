from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Iterator


TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
)


def _empty_usage() -> dict[str, int]:
    return {field_name: 0 for field_name in TOKEN_FIELDS}


def _read_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _read_token_count(source: Any, field_name: str) -> int:
    value = _read_value(source, field_name)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _normalize_responses_usage(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    input_details = _read_value(usage, "input_tokens_details")
    output_details = _read_value(usage, "output_tokens_details")
    return {
        "input_tokens": _read_token_count(usage, "input_tokens"),
        "cached_input_tokens": _read_token_count(
            input_details,
            "cached_tokens",
        ),
        "output_tokens": _read_token_count(usage, "output_tokens"),
        "reasoning_tokens": _read_token_count(
            output_details,
            "reasoning_tokens",
        ),
        "total_tokens": _read_token_count(usage, "total_tokens"),
    }


def _normalize_chat_completion_usage(
    usage: Any,
) -> dict[str, int] | None:
    if usage is None:
        return None
    prompt_details = _read_value(usage, "prompt_tokens_details")
    completion_details = _read_value(
        usage,
        "completion_tokens_details",
    )
    return {
        "input_tokens": _read_token_count(usage, "prompt_tokens"),
        "cached_input_tokens": _read_token_count(
            prompt_details,
            "cached_tokens",
        ),
        "output_tokens": _read_token_count(usage, "completion_tokens"),
        "reasoning_tokens": _read_token_count(
            completion_details,
            "reasoning_tokens",
        ),
        "total_tokens": _read_token_count(usage, "total_tokens"),
    }


class RuntimeTokenUsageTracker:
    """Collect provider-reported usage for exactly one Agent process."""

    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path.resolve()
        self._calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._openai_sdk_available: bool | None = None
        self._patched_interfaces: list[str] = []
        self._persistence_error: str | None = None
        self._initialization_error: str | None = None
        with self._lock:
            self._persist_locked()

    def set_instrumentation(
        self,
        *,
        openai_sdk_available: bool,
        patched_interfaces: list[str],
        initialization_error: str | None = None,
    ) -> None:
        with self._lock:
            self._openai_sdk_available = openai_sdk_available
            self._patched_interfaces = list(patched_interfaces)
            self._initialization_error = initialization_error
            self._persist_locked()

    def record_success(
        self,
        *,
        request_type: str,
        model: str,
        usage: dict[str, int] | None,
    ) -> None:
        self._record(
            request_type=request_type,
            model=model,
            status="succeeded",
            usage=usage,
        )

    def record_failure(
        self,
        *,
        request_type: str,
        model: str,
    ) -> None:
        self._record(
            request_type=request_type,
            model=model,
            status="failed",
            usage=None,
        )

    def _record(
        self,
        *,
        request_type: str,
        model: str,
        status: str,
        usage: dict[str, int] | None,
    ) -> None:
        with self._lock:
            self._calls.append(
                {
                    "request_index": len(self._calls) + 1,
                    "request_type": request_type,
                    "model": model,
                    "status": status,
                    "usage": dict(usage) if usage is not None else None,
                }
            )
            # Persist after every completed request. A later Agent exception or
            # process timeout therefore does not erase already returned usage.
            self._persist_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> dict[str, Any]:
        total = _empty_usage()
        successful_request_count = 0
        failed_request_count = 0
        requests_without_usage_count = 0
        calls: list[dict[str, Any]] = []

        for call in self._calls:
            usage = call["usage"]
            calls.append(
                {
                    **call,
                    "usage": dict(usage) if usage is not None else None,
                }
            )
            if call["status"] == "failed":
                failed_request_count += 1
                continue

            successful_request_count += 1
            if usage is None:
                requests_without_usage_count += 1
                continue
            for field_name in TOKEN_FIELDS:
                total[field_name] += usage[field_name]

        return {
            "instrumentation": {
                "openai_sdk_available": self._openai_sdk_available,
                "patched_interfaces": list(self._patched_interfaces),
                "persistence_error": self._persistence_error,
                "initialization_error": self._initialization_error,
            },
            "request_count": len(calls),
            "successful_request_count": successful_request_count,
            "failed_request_count": failed_request_count,
            "requests_without_usage_count": requests_without_usage_count,
            "total": total if self._openai_sdk_available is not False else None,
            "calls": calls,
        }

    def _persist_locked(self) -> None:
        report = self._snapshot_locked()
        temporary_path = self.report_path.with_name(
            f"{self.report_path.name}.tmp"
        )
        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary_path, self.report_path)
            self._persistence_error = None
        except OSError as exc:
            # Measurement must never change the Agent's business behaviour.
            # The in-memory snapshot is still copied into the child report on
            # normal exit, while this fact remains visible to the parent.
            self._persistence_error = f"{type(exc).__name__}: {exc}"


def _model_name(kwargs: dict[str, Any], response: Any = None) -> str:
    value = kwargs.get("model")
    if not isinstance(value, str) or not value:
        value = _read_value(response, "model")
    return value if isinstance(value, str) else ""


@contextmanager
def track_openai_sdk_usage(
    tracker: RuntimeTokenUsageTracker,
) -> Iterator[None]:
    """Temporarily observe OpenAI SDK calls made by one Agent process."""
    try:
        from openai.resources.chat.completions.completions import (
            AsyncCompletions,
            Completions,
        )
        from openai.resources.responses.responses import (
            AsyncResponses,
            Responses,
        )
    except ImportError as exc:
        tracker.set_instrumentation(
            openai_sdk_available=False,
            patched_interfaces=[],
            initialization_error=f"{type(exc).__name__}: {exc}",
        )
        raise RuntimeError(
            "RQ4 runtime environment is incompatible: OpenAI Responses/Chat "
            "token instrumentation could not initialize. Install the project "
            "runtime requirements in this Python interpreter before testing. "
            "The Agent was not started; missing usage must not count as zero."
        ) from exc

    patches: list[tuple[type, Any]] = []
    interfaces: list[str] = []

    def patch_sync(
        owner: type,
        *,
        request_type: str,
        normalizer: Any,
    ) -> None:
        original = owner.create

        @wraps(original)
        def wrapped(resource: Any, *args: Any, **kwargs: Any) -> Any:
            model = _model_name(kwargs)
            try:
                response = original(resource, *args, **kwargs)
            except Exception:
                tracker.record_failure(
                    request_type=request_type,
                    model=model,
                )
                raise
            tracker.record_success(
                request_type=request_type,
                model=_model_name(kwargs, response),
                usage=normalizer(_read_value(response, "usage")),
            )
            return response

        patches.append((owner, original))
        owner.create = wrapped
        interfaces.append(f"{owner.__name__}.create")

    def patch_async(
        owner: type,
        *,
        request_type: str,
        normalizer: Any,
    ) -> None:
        original = owner.create

        @wraps(original)
        async def wrapped(resource: Any, *args: Any, **kwargs: Any) -> Any:
            model = _model_name(kwargs)
            try:
                response = await original(resource, *args, **kwargs)
            except Exception:
                tracker.record_failure(
                    request_type=request_type,
                    model=model,
                )
                raise
            tracker.record_success(
                request_type=request_type,
                model=_model_name(kwargs, response),
                usage=normalizer(_read_value(response, "usage")),
            )
            return response

        patches.append((owner, original))
        owner.create = wrapped
        interfaces.append(f"{owner.__name__}.create")

    patch_sync(
        Responses,
        request_type="responses",
        normalizer=_normalize_responses_usage,
    )
    patch_sync(
        Completions,
        request_type="chat_completion",
        normalizer=_normalize_chat_completion_usage,
    )
    patch_async(
        AsyncResponses,
        request_type="responses",
        normalizer=_normalize_responses_usage,
    )
    patch_async(
        AsyncCompletions,
        request_type="chat_completion",
        normalizer=_normalize_chat_completion_usage,
    )
    tracker.set_instrumentation(
        openai_sdk_available=True,
        patched_interfaces=interfaces,
    )

    try:
        yield
    finally:
        for owner, original in reversed(patches):
            owner.create = original
