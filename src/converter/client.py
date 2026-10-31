from __future__ import annotations
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from typing import Any
import asyncio
import httpx
from dotenv import load_dotenv
import threading
import json
import os
import random
import re
import time

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 15.0
DEFAULT_TIMEOUT_SECONDS = 120.0
_HTTP_STATUS_PATTERN = re.compile(r"\bHTTP\s+(\d{3})\b", re.IGNORECASE)

# ── module-level helpers ──────────────────────────────────────────────

def _build_chat_completions_url(base_url: str) -> str:
    """Build the standard base URL for the /v1/chat/completions endpoint."""
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("BASE_URL cannot be empty.")

    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("BASE_URL must be an absolute http(s) URL.")

    path = parts.path.rstrip("/")
    if path.endswith("/v1/chat/completions") or path.endswith("/chat/completions"):
        endpoint_path = path
    elif path.endswith("/v1"):
        endpoint_path = f"{path}/chat/completions"
    else:
        endpoint_path = f"{path}/v1/chat/completions"

    return urlunsplit((parts.scheme, parts.netloc, endpoint_path, parts.query, ""))


def _build_responses_url(base_url: str) -> str:
    """Build a base URL into an OpenAI-compatible /responses endpoint."""
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("BASE_URL cannot be empty.")

    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("BASE_URL must be an absolute http(s) URL.")

    path = parts.path.rstrip("/")
    endpoint_path = path if path.endswith("/responses") else f"{path}/responses"
    return urlunsplit((parts.scheme, parts.netloc, endpoint_path, parts.query, ""))


def _default_transport(request: Request, timeout: float) -> bytes:
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        detail = f"HTTP {error.code}"
        if body:
            detail = f"{detail}: {body}"
        raise RuntimeError(detail) from error


def _is_retryable_error(error: Exception) -> bool:
    """Retry only transient failures: HTTP 429/5xx and network-like errors."""
    match = _HTTP_STATUS_PATTERN.search(str(error))
    if match:
        status = int(match.group(1))
        return status == 429 or status >= 500
    return not isinstance(error, (TypeError, ValueError, KeyError))


def _retry_delay(base_delay: float, attempt: int) -> float:
    """Randomized exponential backoff, capped to avoid unbounded sleeps."""
    exponential = min(60.0, base_delay * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, max(0.25, exponential * 0.25))
    return min(60.0, exponential + jitter)


# ── main client ───────────────────────────────────────────────────────

class ChatCompletionClient:
    """Call an OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str | Sequence[str],
        *,
        max_connections: int = 20,
        transport: Callable[[Request, float], bytes] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        if isinstance(api_key, str):
            api_keys = (api_key.strip(),)
        else:
            api_keys = tuple(key.strip() for key in api_key if key.strip())
        if not api_keys:
            raise ValueError("api_key cannot be empty.")
        if max_connections < 1:
            raise ValueError("max_connections must be at least 1.")
        self.endpoint = _build_chat_completions_url(base_url)
        self.responses_endpoint = _build_responses_url(base_url)
        self._api_keys = api_keys
        self._transport = transport or _default_transport
        self._uses_default_transport = transport is None
        self._sleep = sleep
        self._key_counter = 0
        self._key_counter_lock = threading.Lock()
        self._async_client: httpx.AsyncClient | None = None
        self._max_connections = max_connections
        self._default_headers = dict(default_headers or {})

    @property
    def api_key_count(self) -> int:
        return len(self._api_keys)

    def _reserve_starting_key(self) -> int:
        with self._key_counter_lock:
            index = self._key_counter % len(self._api_keys)
            self._key_counter += 1
        return index

    def _make_request(
        self, payload: bytes, api_key: str, endpoint: str | None = None
    ) -> Request:
        return Request(
            endpoint or self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self._default_headers,
            },
        )

    def _get_async_client(self) -> httpx.AsyncClient:
        """Return one shared client so async requests reuse HTTP connections."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=self._max_connections,
                    max_keepalive_connections=self._max_connections,
                ),
                timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS),
            )
        return self._async_client

    async def aclose(self) -> None:
        """Close pooled async connections, if the async client was used."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    async def __aenter__(self) -> "ChatCompletionClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    @staticmethod
    def _parse_response(
        raw_response: bytes, api_style: str = "chat_completions"
    ) -> str:
        response: Any = json.loads(raw_response.decode("utf-8"))
        if api_style == "responses":
            output_text = response.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                return output_text

            parts: list[str] = []
            for item in response.get("output", []):
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []):
                    if not isinstance(content, dict):
                        continue
                    text = content.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            joined = "".join(parts)
            if joined.strip():
                return joined
            raise ValueError("Responses API response contains no output text.")

        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

        # Some OpenAI-compatible providers return structured content parts.
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            joined = "".join(parts)
            if joined.strip():
                return joined

        # Reasoning models/proxies may place the only generated text here while
        # leaving message.content empty.
        for field_name in ("reasoning_content", "reasoning", "text"):
            fallback = message.get(field_name)
            if isinstance(fallback, str) and fallback.strip():
                return fallback

        finish_reason = choice.get("finish_reason", "unknown")
        raise ValueError(
            "Response contains no non-empty text in content or reasoning fields "
            f"(finish_reason={finish_reason!r})."
        )

    @staticmethod
    def _make_payload(
        model: str,
        messages: Sequence[dict[str, str]],
        max_tokens: int | None,
        temperature: float,
        reasoning_effort: str | None = None,
        extra_body: dict[str, Any] | None = None,
        api_style: str = "chat_completions",
    ) -> bytes:
        if api_style == "responses":
            payload: dict[str, Any] = {
                "model": model,
                "input": list(messages),
            }
            if max_tokens is not None:
                payload["max_output_tokens"] = max_tokens
            if reasoning_effort:
                payload["reasoning"] = {"effort": reasoning_effort}
        elif api_style == "chat_completions":
            payload = {
                "model": model,
                "messages": list(messages),
                "temperature": temperature,
                "stream": False,
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
        else:
            raise ValueError(f"Unsupported api_style: {api_style!r}")
        if extra_body:
            payload.update(extra_body)
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def complete(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_tokens: int | None = 4000,
        temperature: float = 0,
        reasoning_effort: str | None = None,
        extra_body: dict[str, Any] | None = None,
        api_style: str = "chat_completions",
    ) -> str:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if not model.strip():
            raise ValueError("model cannot be empty.")

        payload = self._make_payload(
            model,
            messages,
            max_tokens,
            temperature,
            reasoning_effort,
            extra_body,
            api_style,
        )
        endpoint = self.responses_endpoint if api_style == "responses" else self.endpoint
        starting_key = self._reserve_starting_key()

        last_error: Exception | None = None
        attempts_used = 0
        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            api_key = self._api_keys[(starting_key + attempt - 1) % len(self._api_keys)]
            request = self._make_request(payload, api_key, endpoint)
            try:
                raw_response = self._transport(request, timeout)
                return self._parse_response(raw_response, api_style)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as error:
                last_error = error
                if attempt >= max_attempts or not _is_retryable_error(error):
                    break
                self._sleep(_retry_delay(retry_delay, attempt))

        assert last_error is not None
        raise RuntimeError(
            f"LLM request failed after {attempts_used} attempts: {last_error}"
        )

    async def complete_async(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_tokens: int | None = 4000,
        temperature: float = 0,
        on_retry: Callable[[int, int, str], None] | None = None,
        reasoning_effort: str | None = None,
        extra_body: dict[str, Any] | None = None,
        api_style: str = "chat_completions",
    ) -> str:
        """Async version of :meth:`complete`, with an optional retry callback."""
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if not model.strip():
            raise ValueError("model cannot be empty.")

        payload = self._make_payload(
            model,
            messages,
            max_tokens,
            temperature,
            reasoning_effort,
            extra_body,
            api_style,
        )
        endpoint = self.responses_endpoint if api_style == "responses" else self.endpoint
        starting_key = self._reserve_starting_key()
        last_error: Exception | None = None
        attempts_used = 0

        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            api_key = self._api_keys[(starting_key + attempt - 1) % len(self._api_keys)]
            try:
                if self._uses_default_transport:
                    response = await self._get_async_client().post(
                        endpoint,
                        content=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            **self._default_headers,
                        },
                        timeout=timeout,
                    )
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as error:
                        detail = f"HTTP {response.status_code}"
                        if response.text:
                            detail = f"{detail}: {response.text}"
                        raise RuntimeError(detail) from error
                    raw_response = response.content
                else:
                    request = self._make_request(payload, api_key, endpoint)
                    raw_response = await asyncio.to_thread(
                        self._transport, request, timeout
                    )
                return self._parse_response(raw_response, api_style)
            except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
                raise
            except Exception as error:
                last_error = error
                if attempt >= max_attempts or not _is_retryable_error(error):
                    break
                if on_retry:
                    on_retry(attempt, max_attempts, str(error))
                await asyncio.sleep(_retry_delay(retry_delay, attempt))

        assert last_error is not None
        raise RuntimeError(
            f"LLM request failed after {attempts_used} attempts: {last_error}"
        )


def call_llm(
    *,
    base_url: str,
    api_key: str | Sequence[str],
    model: str,
    messages: Sequence[dict[str, str]],
    reasoning_effort: str | None = None,
    extra_body: dict[str, Any] | None = None,
    api_style: str = "chat_completions",
    **kwargs: Any,
) -> str:
    """Compatibility helper for one synchronous OpenAI-compatible request."""
    return ChatCompletionClient(base_url, api_key).complete(
        model=model,
        messages=messages,
        reasoning_effort=reasoning_effort,
        extra_body=extra_body,
        api_style=api_style,
        **kwargs,
    )


# ── conversion helpers ─────────────────────────────────────────────────

_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def output_path(project_dir: Path, task_id: str, suffix: str) -> Path:
    """Build an output path without allowing a task ID to escape the directory."""
    normalized_task_id = task_id.strip()
    if not _TASK_ID_PATTERN.fullmatch(normalized_task_id):
        raise ValueError(
            "Task ID may contain only letters, numbers, underscores, and hyphens."
        )
    return project_dir / f"{normalized_task_id}_{suffix}.txt"


def complete_conversion(
    *,
    messages: Sequence[dict[str, str]],
    output_file: Path,
    model: str,
) -> None:
    """Run one conversion request and write the non-empty response to disk."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    base_url = os.getenv("BASE_URL", "").strip()
    if not base_url:
        raise ValueError("BASE_URL cannot be empty.")

    api_keys = tuple(
        key.strip() for key in os.getenv("OPENAI_API_KEY", "").split(",") if key.strip()
    )
    if not api_keys:
        raise ValueError("OPENAI_API_KEY cannot be empty.")

    normalized_model = model.strip()
    if not normalized_model:
        raise ValueError("Model cannot be empty.")

    content = call_llm(
        base_url=base_url,
        api_key=api_keys,
        model=normalized_model,
        messages=messages,
    )
    if not content.strip():
        raise ValueError("The model returned an empty response.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    print(f"Result saved to: {output_file}")
