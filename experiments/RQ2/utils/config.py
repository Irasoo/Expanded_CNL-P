"""Load the unified run and analysis configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from utils.constants import (
    ANALYSIS_RESULTS_BASE_DEFAULT,
    CONCURRENT_REQUESTS_PER_KEY,
    INSTANCE_ROOT,
    MAX_ASYNC_CONCURRENCY,
    PROJECT_ROOT,
    RATE_LIMITED_PROVIDERS,
    RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
    RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
    RUN_RESULTS_BASE_DEFAULT,
)
from utils.types import PipelineConfig


CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass(frozen=True)
class AnalysisConfig:
    source_runs: tuple[str, ...]
    include_models: tuple[str, ...] = ()
    exclude_models: tuple[str, ...] = ()
    analysis_id: str = ""
    run_results_base: Path = RUN_RESULTS_BASE_DEFAULT
    analysis_results_base: Path = ANALYSIS_RESULTS_BASE_DEFAULT


@dataclass(frozen=True)
class AppConfig:
    pipeline: PipelineConfig
    analysis: AnalysisConfig


def _mapping(value: object, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a YAML mapping")
    return value


def _items(value: object, label: str) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.replace("，", ",").split(",") if part.strip())
    if isinstance(value, Sequence):
        return tuple(str(item).strip() for item in value if str(item).strip())
    raise ValueError(f"{label} must be a string or YAML list")


def _path(value: object, default: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        return default
    path = Path(text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_instance_roots(path: Path | None = None) -> dict[str, Path]:
    """Read dataset directories from paths.instances in the RQ2 config.

    Relative paths are resolved against PROJECT_ROOT (the RQ2 code directory).
    """
    config_path = path or CONFIG_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw = _mapping(raw, "config")
    paths = _mapping(raw.get("paths"), "paths")
    configured = _mapping(paths.get("instances"), "paths.instances")
    datasets = ("natural_instructions", "kor_bench")
    unknown = set(configured).difference(datasets)
    if unknown:
        raise ValueError(f"Unknown dataset path keys: {sorted(unknown)}")
    return {
        dataset: _path(configured.get(dataset), INSTANCE_ROOT / dataset).resolve()
        for dataset in datasets
    }


def _providers(value: object, label: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.upper() for item in _items(value, label)))


def _positive_int(value: object, default: int, label: str) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a positive integer") from error
    if parsed < 1:
        raise ValueError(f"{label} must be a positive integer")
    return parsed


def load_app_config(path: Path | None = None) -> AppConfig:
    config_path = path or CONFIG_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("config.yaml must contain a top-level mapping")

    paths = _mapping(raw.get("paths"), "paths")
    run_values = _mapping(raw.get("run"), "run")
    analysis_values = _mapping(raw.get("analysis"), "analysis")
    analysis_models = _mapping(analysis_values.get("models"), "analysis.models")

    run_results_base = _path(paths.get("run_results"), RUN_RESULTS_BASE_DEFAULT)
    analysis_results_base = _path(paths.get("analysis_results"), ANALYSIS_RESULTS_BASE_DEFAULT)
    pipeline = PipelineConfig(
        task_ids=_items(run_values.get("task_ids"), "run.task_ids"),
        languages=_items(run_values.get("languages"), "run.languages"),
        models=_items(run_values.get("models"), "run.models"),
        instance_count=str(run_values.get("instance_count", "00")),
        run_id=str(run_values.get("run_id", "") or "").strip(),
        result_base=run_results_base,
        run_path=str(run_values.get("run_path", "") or "").strip(),
        max_concurrency=_positive_int(
            run_values.get("max_concurrency"),
            MAX_ASYNC_CONCURRENCY,
            "run.max_concurrency",
        ),
        concurrent_requests_per_key=_positive_int(
            run_values.get("concurrent_requests_per_key"),
            CONCURRENT_REQUESTS_PER_KEY,
            "run.concurrent_requests_per_key",
        ),
        rate_limited_providers=_providers(
            run_values.get("rate_limited_providers", RATE_LIMITED_PROVIDERS),
            "run.rate_limited_providers",
        ),
        rate_limited_provider_max_concurrency=_positive_int(
            run_values.get("rate_limited_provider_max_concurrency"),
            RATE_LIMITED_PROVIDER_MAX_CONCURRENCY,
            "run.rate_limited_provider_max_concurrency",
        ),
        rate_limited_provider_requests_per_minute=_positive_int(
            run_values.get("rate_limited_provider_requests_per_minute"),
            RATE_LIMITED_PROVIDER_REQUESTS_PER_MINUTE,
            "run.rate_limited_provider_requests_per_minute",
        ),
    )
    analysis = AnalysisConfig(
        source_runs=_items(analysis_values.get("source_runs"), "analysis.source_runs"),
        include_models=_items(analysis_models.get("include"), "analysis.models.include"),
        exclude_models=_items(analysis_models.get("exclude"), "analysis.models.exclude"),
        analysis_id=str(analysis_values.get("analysis_id", "") or "").strip(),
        run_results_base=run_results_base,
        analysis_results_base=analysis_results_base,
    )
    return AppConfig(pipeline, analysis)


# Compatibility exports for code that previously imported constants here.
_APP_CONFIG = load_app_config()
TASK_IDS = _APP_CONFIG.pipeline.task_ids
LANGUAGES = _APP_CONFIG.pipeline.languages
MODELS = _APP_CONFIG.pipeline.models
INSTANCE_COUNT = _APP_CONFIG.pipeline.instance_count
RUN_ID = _APP_CONFIG.pipeline.run_id
RESULT_BASE = _APP_CONFIG.pipeline.result_base
RUN_PATH = _APP_CONFIG.pipeline.run_path
