"""Credential, model-registry, task-input, and run-selection loading."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Sequence

import yaml

from utils.constants import (
    DATA_ROOT,
    INSTANCE_ROOT,
    LANGUAGE_ORDER,
    PROJECT_ROOT,
    REPOSITORY_ROOT,
    PROMPT_ROOT,
)
from utils.types import (
    ModelConfig,
    PipelineConfig,
    ProviderEndpoint,
    RunSelection,
    Settings,
    TaskInstance,
)


INSTANCE_FILE_PATTERN = re.compile(r"^task(?P<task_id>\d+)_+instances\.json$", re.I)


def _split_env_values(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"[,，\s]+", value) if part.strip())


def infer_model_provider(key: str, model_id: str) -> str:
    """Infer known direct providers; unrecognized models keep the legacy gateway."""
    value = f"{key} {model_id}".casefold()
    prefixes = {
        "deepseek": "DEEPSEEK",
        "kimi-": "KIMI",
        "mimo-": "MIMO",
        "qwen": "DASHSCOPE",
    }
    for prefix, provider in prefixes.items():
        if any(part.startswith(prefix) for part in value.split()):
            return provider
    return "DEFAULT"


PROVIDER_SPEC_PATTERN = re.compile(
    r"^(?P<provider>[A-Za-z0-9_]+)(?:\((?P<model_id>[^()]+)\)|（(?P<cn_model_id>[^（）]+)）)?$"
)


def parse_provider_spec(value: object, model_key: str) -> tuple[str, str | None]:
    """Parse PROVIDER or PROVIDER(provider-specific-model-id)."""
    text = str(value or "").strip()
    if not text:
        return "", None
    match = PROVIDER_SPEC_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(
            f"Model {model_key!r} provider must use PROVIDER or "
            "PROVIDER(model_id), for example ARK(provider-model-id)"
        )
    provider = match.group("provider").upper()
    model_id = (match.group("model_id") or match.group("cn_model_id") or "").strip()
    return provider, model_id or None


def _default_extra_body(provider: str) -> dict[str, object] | None:
    if provider == "DEEPSEEK":
        return {"thinking": {"type": "enabled"}}
    return None


def load_settings(env_path: Path | None = None) -> Settings:
    env_path = env_path or (REPOSITORY_ROOT / ".env")
    if not env_path.is_file():
        raise FileNotFoundError(f"Missing .env file: {env_path}")
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    base_url = values.get("BASE_URL", "")
    api_keys = _split_env_values(values.get("OPENAI_API_KEY", ""))
    if not base_url:
        raise ValueError("BASE_URL is required in .env")
    if not api_keys:
        raise ValueError("OPENAI_API_KEY is required in .env")
    provider_endpoints: dict[str, ProviderEndpoint] = {}
    suffix = "_BASE_URL"
    for name, provider_base_url in values.items():
        if not name.endswith(suffix):
            continue
        provider = name.removesuffix(suffix).strip().upper()
        if not provider or not provider_base_url:
            continue
        provider_api_keys = _split_env_values(values.get(f"{provider}_API_KEY", ""))
        if provider_api_keys:
            provider_endpoints[provider] = ProviderEndpoint(
                provider_base_url, provider_api_keys
            )
    return Settings(base_url, api_keys, provider_endpoints)


def load_model_registry(path: Path | None = None) -> dict[str, ModelConfig]:
    path = path or (PROJECT_ROOT / "llm" / "models.yaml")
    if not path.is_file():
        raise FileNotFoundError(f"Model registry not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models = raw.get("models")
    if not isinstance(models, dict):
        raise ValueError("llm/models.yaml must contain a top-level 'models' mapping")
    registry: dict[str, ModelConfig] = {}
    for key, item in models.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise ValueError("Each model entry must be a mapping")
        # A blank model_id means the registry key is also the API model ID.
        model_id = str(item.get("model_id") or "").strip() or key
        reasoning = item.get("reasoning_effort")
        reasoning_text = str(reasoning).strip() if reasoning is not None else ""
        configured_provider, provider_model_id = parse_provider_spec(
            item.get("provider"), key
        )
        if provider_model_id:
            model_id = provider_model_id
        provider = configured_provider or infer_model_provider(key, model_id)
        extra_body = (
            item.get("extra_body")
            if "extra_body" in item
            else _default_extra_body(provider)
        )
        if extra_body is not None and not isinstance(extra_body, dict):
            raise ValueError(f"Model {key!r} extra_body must be a mapping")
        api_style = str(item.get("api_style") or "chat_completions").strip().casefold()
        if api_style not in {"chat_completions", "responses"}:
            raise ValueError(
                f"Model {key!r} api_style must be 'chat_completions' or 'responses'"
            )
        try:
            intelligence = int(item.get("intelligence", 0))
        except (TypeError, ValueError):
            intelligence = 0
        registry[key] = ModelConfig(
            key,
            model_id,
            reasoning_text or None,
            intelligence,
            provider,
            extra_body,
            api_style,
        )
    return registry


def discover_instance_files() -> dict[str, Path]:
    from utils.config import load_instance_roots

    found: dict[str, Path] = {}
    for dataset, directory in load_instance_roots().items():
        if not directory.is_dir():
            raise FileNotFoundError(f"Dataset instance directory does not exist: {dataset}: {directory}")
        for path in sorted(directory.rglob("task*_instances.json")):
            match = INSTANCE_FILE_PATTERN.fullmatch(path.name)
            if not match:
                continue
            task_id = match.group("task_id")
            if task_id in found:
                raise ValueError(f"Duplicate instance files for task {task_id}: {found[task_id]} and {path}")
            found[task_id] = path
    return found


def load_instances(task_id: str) -> list[TaskInstance]:
    path = discover_instance_files().get(task_id)
    if path is None:
        raise FileNotFoundError(f"No instance file found for task {task_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Instance file must contain a list: {path}")
    result: list[TaskInstance] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid instance in {path}")
        output = item.get("output", [])
        standard = ",".join(str(value) for value in output) if isinstance(output, list) else str(output)
        result.append(TaskInstance(str(item.get("input", "")), standard))
    return result


def prompt_path(task_id: str, language: str) -> Path:
    return PROMPT_ROOT / f"task{task_id}" / f"{language}.txt"


def read_prompt(task_id: str, language: str) -> str:
    path = prompt_path(task_id, language)
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def selection_items(value: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item for item in re.split(r"[,，\s]+", value.strip()) if item)
    return tuple(str(item).strip() for item in value if str(item).strip())


def _normalize_task_id(value: str) -> str | None:
    task_id = str(value).strip().removeprefix("task")
    if not task_id.isdigit() or not 190 <= int(task_id) <= 1819:
        return None
    return task_id


def _parse_instance_count(value: str | int) -> int | None:
    text = str(value).strip()
    if text == "00":
        return None
    if not text.isdigit() or int(text) < 1:
        raise ValueError("INSTANCE_COUNT must be '00' or a positive integer")
    return int(text)


def _confirm_skips(messages: list[str], confirm: Callable[[str], bool] | None) -> None:
    if not messages:
        return
    print("The following selected inputs are unavailable:")
    for message in messages:
        print(f"  - {message}")
    question = "Continue and skip these inputs? [y/N]: "
    proceed = confirm(question) if confirm else input(question).strip().casefold() in {"y", "yes"}
    if not proceed:
        raise RuntimeError("Run cancelled because selected inputs are unavailable")


def resolve_selection(
    config: PipelineConfig,
    registry: dict[str, ModelConfig],
    *,
    confirm: Callable[[str], bool] | None = None,
) -> RunSelection:
    instance_limit = _parse_instance_count(config.instance_count)
    skipped: list[str] = []
    models: list[ModelConfig] = []
    for model_key in selection_items(config.models):
        model = registry.get(model_key)
        if not model:
            skipped.append(f"model {model_key!r} is not defined in llm/models.yaml")
        elif model not in models:
            models.append(model)

    instance_files = discover_instance_files()
    tasks: list[str] = []
    for raw_task_id in selection_items(config.task_ids):
        task_id = _normalize_task_id(raw_task_id)
        if task_id is None:
            skipped.append(f"task {raw_task_id!r} is outside the allowed 190-1819 range")
        elif task_id not in instance_files:
            skipped.append(f"task {task_id} has no instance file")
        elif task_id not in tasks:
            tasks.append(task_id)

    languages: list[str] = []
    for language in selection_items(config.languages):
        if language not in LANGUAGE_ORDER:
            skipped.append(f"language {language!r} is unsupported")
        elif language not in languages:
            languages.append(language)

    prompt_paths: dict[tuple[str, str], Path] = {}
    for task_id in tasks:
        for language in languages:
            path = prompt_path(task_id, language)
            if path.is_file():
                prompt_paths[(task_id, language)] = path
            elif not language.startswith(("risen-", "rodes-")):
                skipped.append(f"task {task_id} / {language} is missing prompt {path.relative_to(DATA_ROOT)}")

    _confirm_skips(skipped, confirm)
    executable_tasks = tuple(task for task in tasks if any((task, language) in prompt_paths for language in languages))
    executable_languages = tuple(language for language in languages if any((task, language) in prompt_paths for task in tasks))
    if not models:
        raise ValueError("No valid model remains after validation")
    if not executable_tasks or not executable_languages:
        raise ValueError("No executable task/prompt combination remains after validation")
    instance_counts = {
        task_id: min(len(load_instances(task_id)), instance_limit) if instance_limit is not None else len(load_instances(task_id))
        for task_id in executable_tasks
    }
    return RunSelection(
        executable_tasks, executable_languages, tuple(models), prompt_paths,
        instance_limit, instance_counts, tuple(skipped),
    )


def print_run_info(selection: RunSelection, result_base: Path) -> None:
    combinations = len(selection.models) * len(selection.prompt_paths)
    print("=" * 55)
    print(f"  Tasks       {', '.join(selection.task_ids)}")
    print(f"  Languages   {', '.join(selection.languages)}")
    print(f"  Models      {', '.join(model.key for model in selection.models)}")
    requested = "all" if selection.instance_limit is None else str(selection.instance_limit)
    actual = ", ".join(f"task{task_id}={count}" for task_id, count in selection.instance_counts.items())
    print(f"  Instances   {requested} per task ({actual})")
    print(f"  Combinations {combinations}")
    print(f"  Result base {result_base.resolve()}")
    print("=" * 55)


_selection_items = selection_items
