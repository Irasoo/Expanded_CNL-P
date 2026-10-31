"""Dataclasses and protocols used across execution, scoring, and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

from utils.constants import RESULT_BASE_DEFAULT


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_keys: tuple[str, ...]
    provider_endpoints: dict[str, "ProviderEndpoint"] = field(default_factory=dict)

    def endpoint_for(self, provider: str | None) -> "ProviderEndpoint":
        """Resolve a provider endpoint while preserving the legacy default pair."""
        normalized = (provider or "default").strip().upper()
        if normalized == "DEFAULT":
            return ProviderEndpoint(self.base_url, self.api_keys)
        endpoint = self.provider_endpoints.get(normalized)
        if endpoint is None:
            raise ValueError(
                f"Missing credentials for provider {normalized!r}; set "
                f"{normalized}_BASE_URL and {normalized}_API_KEY in .env"
            )
        return endpoint


@dataclass(frozen=True)
class ProviderEndpoint:
    base_url: str
    api_keys: tuple[str, ...]


@dataclass(frozen=True)
class ModelConfig:
    key: str
    model_id: str
    reasoning_effort: str | None = None
    intelligence: int = 0
    provider: str = "DEFAULT"
    extra_body: dict[str, Any] | None = None
    api_style: str = "chat_completions"


@dataclass(frozen=True)
class TaskInstance:
    content: str
    standard_output: str


@dataclass(frozen=True)
class PipelineConfig:
    task_ids: str | Sequence[str]
    languages: str | Sequence[str]
    models: str | Sequence[str]
    instance_count: str | int = "00"
    run_id: str = ""
    result_base: Path = RESULT_BASE_DEFAULT
    run_path: str | Path = ""
    max_concurrency: int = 80
    concurrent_requests_per_key: int = 16
    rate_limited_providers: tuple[str, ...] = ()
    rate_limited_provider_max_concurrency: int = 2
    rate_limited_provider_requests_per_minute: int = 12


@dataclass(frozen=True)
class RunSelection:
    task_ids: tuple[str, ...]
    languages: tuple[str, ...]
    models: tuple[ModelConfig, ...]
    prompt_paths: dict[tuple[str, str], Path]
    instance_limit: int | None
    instance_counts: dict[str, int]
    skipped: tuple[str, ...] = ()


@dataclass(frozen=True)
class AccuracyRecord:
    task_id: str
    model: str
    accuracy_percent: str
    language: str
    record_type: str
    source_csv: str
    run_timestamp: str
    total_rows: int
    correct_count: int
    incorrect_count: int
    unresolved_count: int
    accuracy: str


class AsyncCompletionClient(Protocol):
    async def complete_async(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        max_attempts: int,
        retry_delay: float,
        max_tokens: int | None,
        temperature: float,
        timeout: float = 120.0,
        reasoning_effort: str | None = None,
        extra_body: dict[str, Any] | None = None,
        api_style: str = "chat_completions",
    ) -> str: ...


RESULT_FIELDS = [
    "task_id", "instance_id", "model", "language", "instance_content",
    "model_input", "standard_output", "model_output", "extracted_answer", "score",
]
SUMMARY_FIELDS = list(AccuracyRecord.__dataclass_fields__)
MANUAL_FIELDS = [
    "task_id", "model", "language", "source_csv", "csv_row", "instance_id",
    "standard_output", "instance_content", "model_output", "extracted_answer",
    "manual_score",
]
REGISTRY_FIELDS = [
    "run_id", "date", "task_group", "prompt_group", "model", "reasoning",
    "seed", "status",
]
