"""Run-directory resolution, README generation, manifests, and registry updates."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

from utils.configuration import (
    discover_instance_files,
    infer_model_provider,
    load_instances,
    load_model_registry,
    prompt_path,
    selection_items,
)
from utils.constants import DATA_ROOT, PROJECT_ROOT, README_LANGUAGE_ORDER
from utils.files import read_csv, result_files, run_readme_path, write_csv
from utils.scoring import format_accuracy
from utils.types import ModelConfig, PipelineConfig, REGISTRY_FIELDS, RunSelection


RUN_ID_PATTERN = re.compile(r"^run_(?P<date>\d{8})_(?P<sequence>\d{3})$")


def generate_run_id(result_base: Path, now: datetime | None = None) -> str:
    now = now or datetime.now()
    date = now.strftime("%Y%m%d")
    max_sequence = 0
    if result_base.is_dir():
        for path in result_base.iterdir():
            match = RUN_ID_PATTERN.fullmatch(path.name)
            if match and match.group("date") == date:
                max_sequence = max(max_sequence, int(match.group("sequence")))
        registry_path = result_base / "run_registry.csv"
        if registry_path.is_file():
            _, registry_rows = read_csv(registry_path)
            for row in registry_rows:
                match = RUN_ID_PATTERN.fullmatch(row.get("run_id", "").strip())
                if match and match.group("date") == date:
                    max_sequence = max(max_sequence, int(match.group("sequence")))
    return f"run_{date}_{max_sequence + 1:03d}"


def resolve_run_root(config: PipelineConfig) -> Path:
    configured_path = str(config.run_path).strip()
    if configured_path:
        run_root = Path(configured_path)
        if not run_root.is_absolute():
            run_root = PROJECT_ROOT / run_root
        run_root = run_root.resolve()
        if not run_root.exists():
            raise FileNotFoundError(
                f"Configured RUN_PATH does not exist: {configured_path!r} (resolved to {run_root})"
            )
        if not run_root.is_dir():
            raise NotADirectoryError(
                f"Configured RUN_PATH must be a result directory: {configured_path!r} (resolved to {run_root})"
            )
        if not result_files(run_root):
            raise ValueError(
                f"Configured RUN_PATH contains no result CSV files "
                f"(expected task*/<model>/<language>.csv): {run_root}"
            )
        return run_root

    result_base = config.result_base.resolve()
    if config.run_id:
        return result_base / config.run_id
    candidates = sorted(
        (path for path in result_base.glob("run_*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No run directory found in {result_base}")
    return candidates[0]


def _readme_language(language: str) -> str:
    return {
        "original": "Original",
        "cnlp-direct": "Direct",
        "cnlp-variant-1": "Variant-1",
        "cnlp-variant-2": "Variant-2",
        "cnlp-gold": "Gold",
    }.get(language, language)


def _readme_score(correct: int, total: int) -> str:
    return format_accuracy(correct, total)[0] if total else "—"


def _readme_models(model_keys: Iterable[str]) -> list[ModelConfig]:
    registry = load_model_registry()
    return sorted(
        (registry.get(key, ModelConfig(key, key)) for key in set(model_keys)),
        key=lambda model: (-model.intelligence, model.key),
    )


def _readme_link_target(path: Path, directory: Path) -> str:
    try:
        return Path(os.path.relpath(path, directory)).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_run_readme(
    run_root: Path,
    *,
    selection: RunSelection | None = None,
    status: str | None = None,
) -> Path:
    if selection is not None:
        task_ids = list(selection.task_ids)
        languages = [language for language in README_LANGUAGE_ORDER if language in selection.languages]
        models = sorted(selection.models, key=lambda model: (-model.intelligence, model.key))
        instance_counts = dict(selection.instance_counts)
        available_prompt_pairs = set(selection.prompt_paths)
    else:
        paths = result_files(run_root)
        task_ids = sorted({path.parts[-3].removeprefix("task") for path in paths}, key=int)
        rows_by_path = {path: read_csv(path)[1] for path in paths}
        languages = [language for language in README_LANGUAGE_ORDER if any(path.stem == language for path in paths)]
        models = _readme_models(path.parent.name for path in paths)
        available_prompt_pairs = {
            (path.parts[-3].removeprefix("task"), path.stem)
            for path in paths
        }
        instance_counts = {
            task_id: max(
                (len(rows) for path, rows in rows_by_path.items() if path.parts[-3] == f"task{task_id}"),
                default=0,
            )
            for task_id in task_ids
        }
    created = (
        datetime.fromtimestamp(run_root.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        if run_root.exists() else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    lines = [
        f"# `{run_root.name}`", "",
        f"> **Created** · {created}  ",
        f"> **Scope** · {len(task_ids)} task(s) · {sum(instance_counts.values())} instances · "
        f"{len(languages)} prompt variants · {len(models)} models",
        "", "## At a glance", "", "| Task | Instance file |", "|---|---|",
    ]
    instance_files = discover_instance_files()
    for task_id in task_ids:
        instance_path = instance_files[task_id]
        relative = _readme_link_target(instance_path, run_root)
        instance_label = _data_path_label(instance_path)
        lines.append(
            f"| **{task_id}** · {instance_counts[task_id]} instances | "
            f"[{instance_label}](<{relative}>) |"
        )
    lines.extend(["", "### Prompt variants", "", "| Language | Prompt file(s) |", "|---|---|"])
    for language in languages:
        links = "<br>".join(
            f"[task{task_id}](<{_readme_link_target(prompt_path(task_id, language), run_root)}>)"
            for task_id in task_ids
            if (task_id, language) in available_prompt_pairs
        )
        lines.append(f"| {_readme_language(language)} | {links} |")
    lines.extend(["", "### Models", "", "| Rank | Model | Intelligence |", "|---:|---|---:|"])
    for rank, model in enumerate(models, start=1):
        lines.append(f"| {rank} | {model.key} | **{model.intelligence}** |")

    paths = result_files(run_root)
    if paths:
        data: dict[tuple[str, str, str], tuple[int, int]] = {}
        for path in paths:
            _, rows = read_csv(path)
            if not rows:
                continue
            first = rows[0]
            scored = [row for row in rows if row.get("score", "").strip() in {"0", "1"}]
            data[(first["task_id"], first["model"], first["language"])] = (
                sum(row.get("score", "").strip() == "1" for row in scored), len(scored),
            )
        lines.extend(["", "---", "", "## Results"])
        for task_id in task_ids:
            lines.extend([
                "", f"### Task {task_id}", "",
                "| Intelligence | Model | " + " | ".join(_readme_language(value) for value in languages) + " |",
                "|---:|---|" + "---:|" * len(languages),
            ])
            for model in models:
                cells = [
                    _readme_score(*data[(task_id, model.key, language)])
                    if (task_id, model.key, language) in data else "—"
                    for language in languages
                ]
                lines.append(f"| {model.intelligence} | {model.key} | " + " | ".join(cells) + " |")
        lines.extend([
            "", "---", "", "## Overall model average", "",
            "| Rank | Model | Intelligence | Average accuracy |", "|---:|---|---:|---:|",
        ])
        for rank, model in enumerate(models, start=1):
            correct = total = 0
            for task_id in task_ids:
                for language in languages:
                    value = data.get((task_id, model.key, language))
                    if value:
                        correct += value[0]
                        total += value[1]
            lines.append(f"| {rank} | {model.key} | {model.intelligence} | {_readme_score(correct, total)} |")
    elif status:
        lines.extend(["", "---", "", f"_Status: {status}. Results will be added after scoring._"])
    run_root.mkdir(parents=True, exist_ok=True)
    run_readme_path(run_root).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_readme_path(run_root)


def _manifest_path(run_root: Path) -> Path:
    return run_root / "manifest.yaml"


def write_manifest(run_root: Path, manifest: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    _manifest_path(run_root).write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def read_manifest(run_root: Path) -> dict[str, Any]:
    path = _manifest_path(run_root)
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid manifest: {path}")
    return payload


def manifest_model_configs(run_root: Path) -> dict[str, ModelConfig]:
    raw_models = read_manifest(run_root).get("models", [])
    if not isinstance(raw_models, list):
        raise ValueError("Manifest models must be a list")
    result: dict[str, ModelConfig] = {}
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        model_id = str(item.get("model_id", ""))
        if key and model_id:
            raw_reasoning = item.get("reasoning_effort")
            reasoning = raw_reasoning.strip() if isinstance(raw_reasoning, str) else None
            configured_provider = str(item.get("provider") or "").strip().upper()
            provider = configured_provider or infer_model_provider(key, model_id)
            extra_body = item.get("extra_body")
            api_style = str(
                item.get("api_style") or "chat_completions"
            ).strip().casefold()
            result[key] = ModelConfig(
                key,
                model_id,
                reasoning,
                provider=provider,
                extra_body=extra_body if isinstance(extra_body, dict) else None,
                api_style=api_style,
            )
    return result


def _data_path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(DATA_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _file_metadata(path: Path) -> dict[str, str]:
    return {
        "path": _data_path_label(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def build_manifest(config: PipelineConfig, selection: RunSelection, run_id: str) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    instance_files = discover_instance_files()
    for task_id in selection.task_ids:
        instance_path = instance_files[task_id]
        for language in selection.languages:
            prompt = selection.prompt_paths.get((task_id, language))
            if prompt is None:
                continue
            inputs.append({
                "task_id": task_id,
                "language": language,
                "instance": {
                    **_file_metadata(instance_path),
                    "available_count": len(load_instances(task_id)),
                    "selected_count": selection.instance_counts[task_id],
                },
                "prompt": _file_metadata(prompt),
            })
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "running",
        "requested": {
            "task_ids": list(selection_items(config.task_ids)),
            "languages": list(selection_items(config.languages)),
            "models": list(selection_items(config.models)),
            "instance_count": str(config.instance_count),
            "seed": None,
        },
        "resolved": {
            "task_ids": list(selection.task_ids),
            "languages": list(selection.languages),
            "skipped": list(selection.skipped),
        },
        "models": [
            {
                "key": model.key,
                "model_id": model.model_id,
                "reasoning_effort": model.reasoning_effort,
                "provider": model.provider,
                "extra_body": model.extra_body,
                "api_style": model.api_style,
            }
            for model in selection.models
        ],
        "inputs": inputs,
        "model_status": {model.key: "running" for model in selection.models},
    }


def update_manifest_status(run_root: Path, status: str, model_status: dict[str, str]) -> None:
    manifest = read_manifest(run_root)
    manifest["status"] = status
    manifest["completed_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["model_status"] = model_status
    write_manifest(run_root, manifest)


def upsert_run_registry(run_root: Path, selection: RunSelection, status: str) -> None:
    registry_path = run_root.parent / "run_registry.csv"
    rows: list[dict[str, str]] = []
    if registry_path.is_file():
        fields, rows = read_csv(registry_path)
        if fields != REGISTRY_FIELDS:
            raise ValueError(f"Unexpected run registry header: {registry_path}")
    row = {
        "run_id": run_root.name,
        "date": datetime.now().date().isoformat(),
        "task_group": ",".join(selection.task_ids),
        "prompt_group": ",".join(selection.languages),
        "model": ",".join(model.key for model in selection.models),
        "reasoning": ",".join(
            f"{model.key}={model.reasoning_effort or 'default'}" for model in selection.models
        ),
        "seed": "",
        "status": status,
    }
    for index, existing in enumerate(rows):
        if existing.get("run_id") == run_root.name:
            rows[index] = row
            break
    else:
        rows.append(row)
    write_csv(registry_path, REGISTRY_FIELDS, rows)
