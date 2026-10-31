"""Analyze experiment runs and archived model outputs."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import re
import shutil
from statistics import fmean
import sys
from typing import Iterable
import unicodedata

# Support both ``python -m analysis.tool_analysis`` and direct absolute-path
# execution (the form used by the project run configuration).
if __package__ in {None, ""}:
    project_directory = Path(__file__).resolve().parents[1]
    if str(project_directory) not in sys.path:
        sys.path.insert(0, str(project_directory))

import yaml

from utils.config import AnalysisConfig, load_app_config
from utils import (
    AccuracyRecord,
    _read_csv,
    format_accuracy,
    load_model_registry,
    result_files,
    write_csv,
)

from utils.constants import DATA_ROOT as PROJECT_ROOT


CONDITION_ORDER = (
    "original",
    "cnlp-direct",
    "cnlp-gold",
    "cnlp-variant-1",
    "cnlp-variant-2",
)
BEST_CNLP_CONDITIONS = (
    "cnlp-gold",
    "cnlp-variant-1",
    "cnlp-variant-2",
)
TASK_FIELDS = [
    "task_id", "condition", "accuracy_percent", "accuracy", "total_rows",
    "correct_count", "incorrect_count", "unresolved_count", "model_count", "models",
]
PROFILE_FIELDS = [
    "task_id", *CONDITION_ORDER, "best_condition", "best_accuracy_percent",
    "condition_range_pp",
]
CONVERTER_FIELDS = [
    "task_id", "converter_human_score", "direct_accuracy_percent",
    "gold_accuracy_percent", "gold_minus_direct_pp", "variant",
    "variant_accuracy_percent", "variant_minus_direct_pp",
]
BEST_CNLP_FIELDS = [
    "task_id", "converter_human_score", "direct_minus_original_pp",
    "best_condition", "best_accuracy_percent",
    "best_minus_direct_pp", "best_minus_original_pp",
]
DELTA_FIELDS = [
    "task_id", "baseline", "target", "baseline_accuracy_percent",
    "target_accuracy_percent", "delta_pp", "direction",
]
DELTA_SUMMARY_FIELDS = [
    "baseline", "target", "applicable_task_count", "mean_delta_pp",
    "positive_task_count", "tie_task_count", "negative_task_count",
]
OVERALL_FIELDS = [
    "condition", "applicable_task_count", "pooled_accuracy_percent",
    "macro_task_accuracy_percent", "total_rows", "correct_count",
    "incorrect_count", "unresolved_count",
]
SOURCE_FIELDS = [
    "task_id", "model", "condition", "source_run", "source_csv",
    "accuracy_percent", "total_rows", "correct_count", "incorrect_count",
    "unresolved_count",
]
COMPARISONS = (
    ("original", "cnlp-direct"),
    ("original", "cnlp-gold"),
    ("original", "cnlp-variant-1"),
    ("original", "cnlp-variant-2"),
    ("cnlp-direct", "cnlp-gold"),
    ("cnlp-direct", "cnlp-variant-1"),
    ("cnlp-direct", "cnlp-variant-2"),
)
RUN_PATTERN = re.compile(r"^run_(?P<date>\d{8})_(?P<sequence>\d{3})$")
ANALYSIS_PATTERN = re.compile(r"^analysis-(?P<sequence>\d{3})-(?P<number>\d{2})$")
FINAL_ANALYSIS_PATTERN = re.compile(r"^analysis-final-(?P<number>\d{2})$")
FINAL_RESULT_ROOT = PROJECT_ROOT / "results" / "final_result"
FINAL_RESULT_SOURCE_IDS = PROJECT_ROOT / "results" / "final_result_source_ids.csv"
ANALYSIS_RESULTS_ROOT = PROJECT_ROOT / "results" / "analysis_results"
FRAMEWORKS = {"risen": "RISEN", "rodes": "RODES"}
FRAMEWORK_ANALYSIS_PATTERN = re.compile(
    r"^analysis-risen-rodes-(?P<number>\d{2})$"
)
VERSION_SPECS = (
    ("all", "analysis_report.md", "All models"),
)


def _percent(value: float) -> str:
    percent = f"{value * 100:.3f}".rstrip("0").rstrip(".")
    return f"{percent}%"


def _delta(value: float) -> str:
    return f"{value * 100:+.2f}"


def _markdown_pp(value: object) -> str:
    return f"{value} pp" if value not in {None, ""} else "—"


def _direction(value: float) -> str:
    if value > 1e-12:
        return "improved"
    if value < -1e-12:
        return "worsened"
    return "tied"


def _task_rows(records: list[AccuracyRecord]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[AccuracyRecord]] = defaultdict(list)
    for record in records:
        if record.language in CONDITION_ORDER:
            grouped[(record.task_id, record.language)].append(record)
    rows: list[dict[str, object]] = []
    for (task_id, condition), items in grouped.items():
        total = sum(item.total_rows for item in items)
        correct = sum(item.correct_count for item in items)
        incorrect = sum(item.incorrect_count for item in items)
        unresolved = sum(item.unresolved_count for item in items)
        accuracy = correct / total if total else 0.0
        models = sorted((item.model for item in items), key=str.casefold)
        rows.append({
            "task_id": task_id,
            "condition": condition,
            "accuracy_percent": _percent(accuracy),
            "accuracy": f"{accuracy:.3f}".rstrip("0").rstrip("."),
            "total_rows": total,
            "correct_count": correct,
            "incorrect_count": incorrect,
            "unresolved_count": unresolved,
            "model_count": len(models),
            "models": ",".join(models),
        })
    rank = {condition: index for index, condition in enumerate(CONDITION_ORDER)}
    return sorted(rows, key=lambda row: (int(str(row["task_id"])), rank[str(row["condition"])]))


def _values(task_rows: list[dict[str, object]]) -> dict[tuple[str, str], float]:
    return {
        (str(row["task_id"]), str(row["condition"])): float(row["accuracy"])
        for row in task_rows
    }


def _profile_rows(task_ids: tuple[str, ...], values: dict[tuple[str, str], float]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task_id in task_ids:
        available = {
            condition: values[(task_id, condition)]
            for condition in CONDITION_ORDER
            if (task_id, condition) in values
        }
        if not available:
            continue
        best = max(available.values())
        worst = min(available.values())
        row: dict[str, object] = {
            "task_id": task_id,
            "best_condition": ",".join(
                condition for condition in CONDITION_ORDER
                if condition in available and abs(available[condition] - best) < 1e-12
            ),
            "best_accuracy_percent": _percent(best),
            "condition_range_pp": f"{(best - worst) * 100:.2f}",
        }
        for condition in CONDITION_ORDER:
            row[condition] = _percent(available[condition]) if condition in available else ""
        rows.append(row)
    return rows


def _converter_rows(
    task_ids: tuple[str, ...],
    values: dict[tuple[str, str], float],
    converter_scores: dict[str, float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task_id in task_ids:
        direct = values.get((task_id, "cnlp-direct"))
        gold = values.get((task_id, "cnlp-gold"))
        if direct is None or gold is None:
            continue
        variants = [
            condition for condition in ("cnlp-variant-1", "cnlp-variant-2")
            if (task_id, condition) in values
        ]
        for variant in variants or [""]:
            variant_value = values.get((task_id, variant)) if variant else None
            rows.append({
                "task_id": task_id,
                "converter_human_score": (
                    f"{converter_scores[task_id]:.3f}" if task_id in converter_scores else ""
                ),
                "direct_accuracy_percent": _percent(direct),
                "gold_accuracy_percent": _percent(gold),
                "gold_minus_direct_pp": _delta(gold - direct),
                "variant": variant,
                "variant_accuracy_percent": _percent(variant_value) if variant_value is not None else "",
                "variant_minus_direct_pp": _delta(variant_value - direct) if variant_value is not None else "",
            })
    return rows


def _best_cnlp_rows(
    task_ids: tuple[str, ...],
    values: dict[tuple[str, str], float],
    converter_scores: dict[str, float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task_id in task_ids:
        original = values.get((task_id, "original"))
        direct = values.get((task_id, "cnlp-direct"))
        candidates = {
            condition: values[(task_id, condition)]
            for condition in BEST_CNLP_CONDITIONS
            if (task_id, condition) in values
        }
        best = max(candidates.values()) if candidates else None
        # A task has exactly one comprehensive best CNL-P condition.  Ties are
        # resolved deterministically by the declared condition order so the
        # report never presents multiple "best" versions for one task.
        best_condition = (
            next(
                condition
                for condition in BEST_CNLP_CONDITIONS
                if condition in candidates
                and abs(candidates[condition] - best) < 1e-12
            )
            if best is not None
            else ""
        )
        rows.append({
            "task_id": task_id,
            "converter_human_score": (
                f"{converter_scores[task_id]:.3f}" if task_id in converter_scores else ""
            ),
            "direct_minus_original_pp": (
                _delta(direct - original) if direct is not None and original is not None else ""
            ),
            "best_condition": best_condition,
            "best_accuracy_percent": _percent(best) if best is not None else "",
            "best_minus_direct_pp": (
                _delta(best - direct) if best is not None and direct is not None else ""
            ),
            "best_minus_original_pp": (
                _delta(best - original) if best is not None and original is not None else ""
            ),
        })
    return rows


def _delta_rows(task_ids: tuple[str, ...], values: dict[tuple[str, str], float]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task_id in task_ids:
        for baseline, target in COMPARISONS:
            baseline_value = values.get((task_id, baseline))
            target_value = values.get((task_id, target))
            if baseline_value is None or target_value is None:
                continue
            delta = target_value - baseline_value
            rows.append({
                "task_id": task_id,
                "baseline": baseline,
                "target": target,
                "baseline_accuracy_percent": _percent(baseline_value),
                "target_accuracy_percent": _percent(target_value),
                "delta_pp": _delta(delta),
                "direction": _direction(delta),
            })
    return rows


def _delta_summary_rows(delta_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in delta_rows:
        grouped[(str(row["baseline"]), str(row["target"]))].append(float(row["delta_pp"]))
    rows: list[dict[str, object]] = []
    for baseline, target in COMPARISONS:
        deltas = grouped.get((baseline, target), [])
        if not deltas:
            continue
        rows.append({
            "baseline": baseline,
            "target": target,
            "applicable_task_count": len(deltas),
            "mean_delta_pp": f"{fmean(deltas):+.2f}",
            "positive_task_count": sum(value > 0 for value in deltas),
            "tie_task_count": sum(value == 0 for value in deltas),
            "negative_task_count": sum(value < 0 for value in deltas),
        })
    return rows


def _overall_rows(task_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in task_rows:
        grouped[str(row["condition"])].append(row)
    rows: list[dict[str, object]] = []
    for condition in CONDITION_ORDER:
        items = grouped.get(condition, [])
        if not items:
            continue
        total = sum(int(item["total_rows"]) for item in items)
        correct = sum(int(item["correct_count"]) for item in items)
        incorrect = sum(int(item["incorrect_count"]) for item in items)
        unresolved = sum(int(item["unresolved_count"]) for item in items)
        pooled = correct / total if total else 0.0
        macro = fmean(float(item["accuracy"]) for item in items)
        rows.append({
            "condition": condition,
            "applicable_task_count": len(items),
            "pooled_accuracy_percent": _percent(pooled),
            "macro_task_accuracy_percent": _percent(macro),
            "total_rows": total,
            "correct_count": correct,
            "incorrect_count": incorrect,
            "unresolved_count": unresolved,
        })
    return rows


def _source_rows(records: list[AccuracyRecord]) -> list[dict[str, object]]:
    return [
        {
            "task_id": record.task_id,
            "model": record.model,
            "condition": record.language,
            "source_run": record.run_timestamp,
            "source_csv": record.source_csv,
            "accuracy_percent": record.accuracy_percent,
            "total_rows": record.total_rows,
            "correct_count": record.correct_count,
            "incorrect_count": record.incorrect_count,
            "unresolved_count": record.unresolved_count,
        }
        for record in records
    ]


def _markdown(
    *,
    analysis_id: str,
    label: str,
    anchor_run: str,
    source_runs: tuple[str, ...],
    task_ids: tuple[str, ...],
    models: tuple[str, ...],
    profile_rows: list[dict[str, object]],
    converter_rows: list[dict[str, object]],
    best_cnlp_rows: list[dict[str, object]],
    delta_rows: list[dict[str, object]],
) -> str:
    lines = [
        f"# Condition Analysis Report: {label}",
        "",
        f"> Analysis ID: `{analysis_id}`  ",
        f"> Anchor run: `{anchor_run}`  ",
        "> Task scope: " + ", ".join(f"`task{task_id}`" for task_id in task_ids) + "  ",
        "> Data sources (newest to oldest): " + ", ".join(f"`{run}`" for run in reversed(source_runs)),
        "",
        f"**Included models ({len(models)}):** " + (", ".join(models) if models else "None"),
        "",
        "## Accuracy of each task across conditions",
        "",
        "| Task | Original | Direct | Gold | Variant-1 | Variant-2 | Best condition | Range across conditions (pp) |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in profile_rows:
        lines.append(
            f"| task{row['task_id']} | {row['original'] or '—'} | {row['cnlp-direct'] or '—'} | "
            f"{row['cnlp-gold'] or '—'} | {row['cnlp-variant-1'] or '—'} | "
            f"{row['cnlp-variant-2'] or '—'} | {row['best_condition']} "
            f"({row['best_accuracy_percent']}) | {row['condition_range_pp']} |"
        )

    by_task: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in converter_rows:
        by_task[str(row["task_id"])].append(row)
    lines.extend([
        "", "## Converter human score vs. Direct, Gold, Variant", "",
        "| Task | Converter human score | Direct | Gold | Gold−Direct | Variant | Variant−Direct |",
        "|---|---:|---:|---:|---:|---|---:|",
    ])
    for task_id in task_ids:
        items = by_task.get(task_id, [])
        if not items:
            continue
        first = items[0]
        variant_values = "<br>".join(
            f"{row['variant']}: {row['variant_accuracy_percent']}" for row in items if row["variant"]
        ) or "—"
        variant_deltas = "<br>".join(
            f"{row['variant']}: {row['variant_minus_direct_pp']} pp" for row in items if row["variant"]
        ) or "—"
        lines.append(
            f"| task{task_id} | {first['converter_human_score'] or '—'} | "
            f"{first['direct_accuracy_percent']} | {first['gold_accuracy_percent']} | "
            f"{first['gold_minus_direct_pp']} pp | {variant_values} | {variant_deltas} |"
        )

    delta_lookup = {
        (str(row["task_id"]), str(row["baseline"]), str(row["target"])): str(row["delta_pp"])
        for row in delta_rows
    }
    lines.extend([
        "", "## Baseline: original", "",
        "| Task | Direct−Original | Gold−Original | Variant-1−Original | Variant-2−Original |",
        "|---|---:|---:|---:|---:|",
    ])
    for task_id in task_ids:
        lines.append(
            f"| task{task_id} | {_markdown_pp(delta_lookup.get((task_id, 'original', 'cnlp-direct')))} | "
            f"{_markdown_pp(delta_lookup.get((task_id, 'original', 'cnlp-gold')))} | "
            f"{_markdown_pp(delta_lookup.get((task_id, 'original', 'cnlp-variant-1')))} | "
            f"{_markdown_pp(delta_lookup.get((task_id, 'original', 'cnlp-variant-2')))} |"
        )
    best_by_task = {str(row["task_id"]): row for row in best_cnlp_rows}
    lines.extend([
        "", "## Baseline: cnlp-direct", "",
        "| Task | Gold−Direct | Variant-1−Direct | Variant-2−Direct | Best non-Direct performance vs. Direct |",
        "|---|---:|---:|---:|---|",
    ])
    for task_id in task_ids:
        best_row = best_by_task.get(task_id, {})
        best_condition = str(best_row.get("best_condition", ""))
        best_delta = str(best_row.get("best_minus_direct_pp", ""))
        best_display = f"{best_condition} ({best_delta} pp)" if best_condition and best_delta else "—"
        lines.append(
            f"| task{task_id} | {_markdown_pp(delta_lookup.get((task_id, 'cnlp-direct', 'cnlp-gold')))} | "
            f"{_markdown_pp(delta_lookup.get((task_id, 'cnlp-direct', 'cnlp-variant-1')))} | "
            f"{_markdown_pp(delta_lookup.get((task_id, 'cnlp-direct', 'cnlp-variant-2')))} | "
            f"{best_display} |"
        )
    lines.extend([
        "", "## Best non-Direct CNL-P variant per task", "",
        "| Task | Converter human score | Direct−Original | Best CNL-P variant (excluding Direct) | Best variant − Direct | Best variant − Original |",
        "|---|---:|---:|---|---:|---:|",
    ])
    for row in best_cnlp_rows:
        best_condition = str(row["best_condition"] or "—")
        best_accuracy = str(row["best_accuracy_percent"] or "")
        if best_accuracy:
            best_condition = f"{best_condition} ({best_accuracy})"
        lines.append(
            f"| task{row['task_id']} | {row['converter_human_score'] or '—'} | "
            f"{_markdown_pp(row['direct_minus_original_pp'])} | {best_condition} | "
            f"{_markdown_pp(row['best_minus_direct_pp'])} | "
            f"{_markdown_pp(row['best_minus_original_pp'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _task_detail_markdown(
    *,
    analysis_id: str,
    task_id: str,
    records: list[AccuracyRecord],
    values: dict[tuple[str, str], float],
    converter_score: float | None,
    best_cnlp_row: dict[str, object] | None,
) -> str:
    """Build one detailed, model-level report for a single task."""
    task_records = [record for record in records if record.task_id == task_id]
    by_model: dict[str, dict[str, AccuracyRecord]] = defaultdict(dict)
    for record in task_records:
        by_model[record.model][record.language] = record

    def task_accuracy(condition: str) -> str:
        value = values.get((task_id, condition))
        return _percent(value) if value is not None else "—"

    best_condition = (
        str(best_cnlp_row.get("best_condition", ""))
        if best_cnlp_row
        else ""
    )
    best_delta = (
        str(best_cnlp_row.get("best_minus_direct_pp", ""))
        if best_cnlp_row
        else ""
    )
    best_vs_direct = (
        f"{best_condition} ({best_delta} pp)"
        if best_condition and best_delta
        else "—"
    )
    unresolved = sum(record.unresolved_count for record in task_records)
    lines = [
        f"# task{task_id} Detailed Analysis Report",
        "",
        f"> Analysis ID: `{analysis_id}`  ",
        f"> Data source: `final_result`  ",
        f"> Included models: {len(by_model)}  ",
        f"> Unresolved scoring records: {unresolved}",
        "",
        "## Task summary",
        "",
        "| Task | Converter human score | Original | Direct | Gold | Variant-1 | Variant-2 | Best−Direct |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
        f"| task{task_id} | "
        f"{f'{converter_score:.3f}' if converter_score is not None else '—'} | "
        f"{task_accuracy('original')} | {task_accuracy('cnlp-direct')} | "
        f"{task_accuracy('cnlp-gold')} | {task_accuracy('cnlp-variant-1')} | "
        f"{task_accuracy('cnlp-variant-2')} | {best_vs_direct} |",
        "",
        "Corrected best: the highest-performing non-Direct CNL-P variant for this task after aggregating across all included models. Ties are resolved by the fixed order Gold, Variant-1, Variant-2 to select a single variant.",
        "",
        "## Model overview",
        "",
        "| Model | Original | Direct | Gold | Variant-1 | Variant-2 | Corrected best | Best−Direct | Best−Original |",
        "|---|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for model in sorted(by_model, key=str.casefold):
        conditions = by_model[model]
        # The corrected best condition is selected once at task level from
        # the aggregate across all models.  Every model row compares that same
        # condition with its own Direct and Original results.
        selected_best_record = conditions.get(best_condition)
        model_best_value = (
            float(selected_best_record.accuracy)
            if selected_best_record is not None
            else None
        )
        direct_record = conditions.get("cnlp-direct")
        original_record = conditions.get("original")
        model_delta = (
            _delta(model_best_value - float(direct_record.accuracy))
            if model_best_value is not None and direct_record is not None
            else ""
        )
        model_original_delta = (
            _delta(model_best_value - float(original_record.accuracy))
            if model_best_value is not None and original_record is not None
            else ""
        )

        def model_accuracy(condition: str) -> str:
            record = conditions.get(condition)
            return record.accuracy_percent if record is not None else "—"

        best_display = (
            f"{best_condition} ({_percent(model_best_value)})"
            if model_best_value is not None
            else "—"
        )
        lines.append(
            f"| {model} | {model_accuracy('original')} | "
            f"{model_accuracy('cnlp-direct')} | {model_accuracy('cnlp-gold')} | "
            f"{model_accuracy('cnlp-variant-1')} | "
            f"{model_accuracy('cnlp-variant-2')} | {best_display} | "
            f"{_markdown_pp(model_delta)} | "
            f"{_markdown_pp(model_original_delta)} |"
        )

    original = values.get((task_id, "original"))
    direct = values.get((task_id, "cnlp-direct"))
    lines.extend([
        "",
        "## Summary differences",
        "",
        "| Comparison | Difference (pp) |",
        "|---|---:|",
    ])
    for condition in ("cnlp-direct", "cnlp-gold", "cnlp-variant-1", "cnlp-variant-2"):
        value = values.get((task_id, condition))
        delta = _delta(value - original) if value is not None and original is not None else ""
        lines.append(f"| {condition} − original | {_markdown_pp(delta)} |")
    for condition in ("cnlp-gold", "cnlp-variant-1", "cnlp-variant-2"):
        value = values.get((task_id, condition))
        delta = _delta(value - direct) if value is not None and direct is not None else ""
        lines.append(f"| {condition} − cnlp-direct | {_markdown_pp(delta)} |")

    lines.extend([
        "",
        "## Data source and scoring integrity",
        "",
        "| Model | Condition | Source ID | Valid rows | Correct | Incorrect | Unresolved |",
        "|---|---|---|---:|---:|---:|---:|",
    ])
    for record in sorted(
        task_records,
        key=lambda item: (
            item.model.casefold(), CONDITION_ORDER.index(item.language)
        ),
    ):
        lines.append(
            f"| {record.model} | {record.language} | {record.run_timestamp} | "
            f"{record.total_rows} | {record.correct_count} | "
            f"{record.incorrect_count} | {record.unresolved_count} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_analysis_version(
    analysis_root: Path,
    *,
    version: str,
    report_name: str,
    label: str,
    analysis_id: str,
    anchor_run: str,
    source_runs: tuple[str, ...],
    task_ids: tuple[str, ...],
    models: Iterable[str],
    records: Iterable[AccuracyRecord],
    converter_scores: dict[str, float],
) -> Path:
    model_tuple = tuple(sorted(set(models), key=str.casefold))
    model_set = set(model_tuple)
    selected_records = sorted(
        (record for record in records if record.model in model_set),
        key=lambda record: (
            int(record.task_id), record.model.casefold(),
            CONDITION_ORDER.index(record.language),
        ),
    )
    version_dir = analysis_root if version == "all" else analysis_root / version
    task_rows = _task_rows(selected_records)
    values = _values(task_rows)
    profile_rows = _profile_rows(task_ids, values)
    converter_rows = _converter_rows(task_ids, values, converter_scores)
    best_cnlp_rows = _best_cnlp_rows(task_ids, values, converter_scores)
    delta_rows = _delta_rows(task_ids, values)
    delta_summary_rows = _delta_summary_rows(delta_rows)
    overall_rows = _overall_rows(task_rows)

    write_csv(version_dir / "source_selection.csv", SOURCE_FIELDS, _source_rows(selected_records))
    write_csv(version_dir / "task_condition_accuracy.csv", TASK_FIELDS, task_rows)
    write_csv(version_dir / "task_condition_summary.csv", PROFILE_FIELDS, profile_rows)
    write_csv(version_dir / "human_score_condition_comparison.csv", CONVERTER_FIELDS, converter_rows)
    write_csv(version_dir / "best_condition_by_task.csv", BEST_CNLP_FIELDS, best_cnlp_rows)
    write_csv(version_dir / "overall_condition_accuracy.csv", OVERALL_FIELDS, overall_rows)
    write_csv(version_dir / "task_condition_deltas.csv", DELTA_FIELDS, delta_rows)
    write_csv(version_dir / "condition_delta_summary.csv", DELTA_SUMMARY_FIELDS, delta_summary_rows)

    report_path = analysis_root / report_name
    report_path.write_text(
        _markdown(
            analysis_id=analysis_id,
            label=label,
            anchor_run=anchor_run,
            source_runs=source_runs,
            task_ids=task_ids,
            models=model_tuple,
            profile_rows=profile_rows,
            converter_rows=converter_rows,
            best_cnlp_rows=best_cnlp_rows,
            delta_rows=delta_rows,
        ),
        encoding="utf-8",
    )
    return report_path


def _run_key(path: Path) -> tuple[int, int]:
    match = RUN_PATTERN.fullmatch(path.name)
    if match is None:
        raise ValueError(f"Source run directory must use run_YYYYMMDD_NNN: {path}")
    return int(match.group("date")), int(match.group("sequence"))


def _is_final_result_source(path: Path) -> bool:
    return path.resolve() == FINAL_RESULT_ROOT.resolve()


def _source_sort_key(path: Path) -> tuple[int, int, int]:
    """Sort ordinary runs chronologically and consolidated final_result last."""
    if _is_final_result_source(path):
        return (1, 0, 0)
    date, sequence = _run_key(path)
    return (0, date, sequence)


def _normalize_model_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        "-" if unicodedata.category(character) == "Pd" else character
        for character in normalized
    ).casefold()


def _is_gpt(model: str) -> bool:
    return _normalize_model_name(model).startswith("gpt-")


def _is_gpt_4o(model: str) -> bool:
    return _normalize_model_name(model) == "gpt-4o"


def _resolve_source_run(value: str, run_results_base: Path) -> Path:
    configured = Path(value)
    candidates = [configured] if configured.is_absolute() else [
        run_results_base / configured,
        PROJECT_ROOT / configured,
        PROJECT_ROOT / "results" / configured,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_dir():
            if not _is_final_result_source(resolved):
                _run_key(resolved)
            if not result_files(resolved):
                raise ValueError(f"Source run contains no result CSV files: {resolved}")
            return resolved
    raise FileNotFoundError(f"Analysis source run not found: {value!r}")


def resolve_source_runs(config: AnalysisConfig) -> tuple[Path, ...]:
    if not config.source_runs:
        raise ValueError("analysis.source_runs must select at least one run")
    unique: dict[Path, Path] = {}
    for value in config.source_runs:
        path = _resolve_source_run(value, config.run_results_base)
        unique[path] = path
    return tuple(sorted(unique.values(), key=_source_sort_key))


def _anchor_task_ids(anchor_run: Path) -> tuple[str, ...]:
    task_ids = {
        path.parts[-3].removeprefix("task")
        for path in result_files(anchor_run)
        if path.parts[-3].startswith("task")
    }
    if not task_ids:
        raise ValueError(f"Anchor run contains no task result files: {anchor_run}")
    return tuple(sorted(task_ids, key=int))


def _read_accuracy_record(
    path: Path,
    run_root: Path,
    allowed_conditions: Iterable[str],
) -> AccuracyRecord | None:
    """Read one result CSV and calculate accuracy for an allowed condition."""
    _, rows = _read_csv(path)
    if not rows:
        return None
    first = rows[0]
    condition = first.get("language", "").strip()
    if condition not in allowed_conditions:
        return None
    all_scores = [row.get("score", "").strip() for row in rows]
    scores = [score for score in all_scores if score in {"0", "1"}]
    correct = scores.count("1")
    incorrect = scores.count("0")
    total = len(scores)
    accuracy, accuracy_percent = format_accuracy(correct, total)
    return AccuracyRecord(
        task_id=first.get("task_id", "").strip(),
        model=first.get("model", "").strip(),
        accuracy_percent=accuracy_percent,
        language=condition,
        record_type="file",
        source_csv=path.relative_to(run_root).as_posix(),
        run_timestamp=run_root.name,
        total_rows=total,
        correct_count=correct,
        incorrect_count=incorrect,
        unresolved_count=all_scores.count("2"),
        accuracy=accuracy,
    )


def _record(path: Path, run_root: Path) -> AccuracyRecord | None:
    return _read_accuracy_record(path, run_root, CONDITION_ORDER)


def _final_result_source_ids() -> dict[tuple[str, str, str], str]:
    """Read optional source-ID annotations without opening historical runs."""
    if not FINAL_RESULT_SOURCE_IDS.is_file():
        return {}
    _, rows = _read_csv(FINAL_RESULT_SOURCE_IDS)
    condition_columns = {
        "original": "original_source_id",
        "cnlp-direct": "direct_source_id",
        "cnlp-gold": "gold_source_id",
        "cnlp-variant-1": "variant_1_source_id",
        "cnlp-variant-2": "variant_2_source_id",
    }
    return {
        (
            row.get("task_id", "").strip().removeprefix("task"),
            _normalize_model_name(row.get("model", "").strip()),
            condition,
        ): row.get(column, "").strip()
        for row in rows
        for condition, column in condition_columns.items()
        if row.get(column, "").strip()
    }


def merge_latest_records(
    source_runs: tuple[Path, ...],
    task_ids: tuple[str, ...],
) -> list[AccuracyRecord]:
    task_set = set(task_ids)
    merged: dict[tuple[str, str, str], AccuracyRecord] = {}
    for run_root in source_runs:
        source_ids = (
            _final_result_source_ids()
            if _is_final_result_source(run_root)
            else {}
        )
        for path in result_files(run_root):
            record = _record(path, run_root)
            if record is None or record.task_id not in task_set or not record.model:
                continue
            if _is_final_result_source(run_root):
                source_id = source_ids.get(
                    (
                        record.task_id,
                        _normalize_model_name(record.model),
                        record.language,
                    )
                )
                record = replace(
                    record,
                    run_timestamp=source_id or "final_result",
                )
            merged[(record.task_id, record.model, record.language)] = record
    return sorted(
        merged.values(),
        key=lambda record: (
            int(record.task_id), record.model.casefold(),
            CONDITION_ORDER.index(record.language),
        ),
    )


def _candidate_models(records: list[AccuracyRecord], config: AnalysisConfig) -> set[str]:
    available = {record.model for record in records}
    included = set(config.include_models) if config.include_models else available
    candidates = (available & included) - set(config.exclude_models)
    if not candidates:
        raise ValueError("No model remains after analysis.models include/exclude filtering")
    return candidates


def _version_models(candidates: set[str]) -> dict[str, set[str]]:
    return {"all": set(candidates)}


def _converter_human_scores(converter: str = "CNL-P") -> dict[str, float]:
    path = PROJECT_ROOT / "evaluation" / "raw" / "annotation_scores.csv"
    if not path.is_file():
        return {}
    _, rows = _read_csv(path)
    grouped: dict[str, list[float]] = {}
    for row in rows:
        if row.get("converter", "").strip().casefold() != converter.casefold():
            continue
        task_id = row.get("task_id", "").strip()
        try:
            grouped.setdefault(task_id, []).append(
                float(row.get("mean_score", ""))
            )
        except ValueError:
            continue
    return {
        task_id: sum(values) / len(values)
        for task_id, values in grouped.items()
        if values
    }


def _analysis_id(config: AnalysisConfig, anchor_run: Path) -> str:
    if _is_final_result_source(anchor_run):
        prefix = "analysis-final-"
        if config.analysis_id:
            if FINAL_ANALYSIS_PATTERN.fullmatch(config.analysis_id) is None:
                raise ValueError(
                    "analysis.analysis_id must use analysis-final-NN when "
                    "the anchor source is final_result"
                )
            return config.analysis_id
        highest = 0
        if config.analysis_results_base.is_dir():
            for path in config.analysis_results_base.iterdir():
                match = FINAL_ANALYSIS_PATTERN.fullmatch(path.name)
                if path.is_dir() and match:
                    highest = max(highest, int(match.group("number")))
        if highest >= 99:
            raise ValueError("No analysis number remains for final_result")
        return f"{prefix}{highest + 1:02d}"

    sequence = _run_key(anchor_run)[1]
    prefix = f"analysis-{sequence:03d}-"
    if config.analysis_id:
        match = ANALYSIS_PATTERN.fullmatch(config.analysis_id)
        if match is None:
            raise ValueError("analysis.analysis_id must use analysis-NNN-NN")
        if int(match.group("sequence")) != sequence:
            raise ValueError(
                f"analysis.analysis_id must start with analysis-{sequence:03d}- for anchor {anchor_run.name}"
            )
        return config.analysis_id
    highest = 0
    if config.analysis_results_base.is_dir():
        for path in config.analysis_results_base.iterdir():
            match = ANALYSIS_PATTERN.fullmatch(path.name)
            if path.is_dir() and match and path.name.startswith(prefix):
                highest = max(highest, int(match.group("number")))
    if highest >= 99:
        raise ValueError(f"No analysis number remains for {anchor_run.name}")
    return f"{prefix}{highest + 1:02d}"


def _write_snapshot(
    output: Path,
    config: AnalysisConfig,
    source_runs: tuple[Path, ...],
    anchor_run: Path,
    task_ids: tuple[str, ...],
    analysis_id: str,
) -> None:
    payload = {
        "paths": {
            "run_results": str(config.run_results_base),
            "analysis_results": str(config.analysis_results_base),
        },
        "analysis": {
            "analysis_id": analysis_id,
            "anchor_run": anchor_run.name,
            "task_scope": [f"task{task_id}" for task_id in task_ids],
            "source_runs_oldest_to_newest": [path.name for path in source_runs],
            "merge_rule": (
                "preconsolidated_final_result"
                if _is_final_result_source(anchor_run)
                else "latest_run_wins_per_task_model_condition"
            ),
            "models": {
                "include": list(config.include_models),
                "exclude": list(config.exclude_models),
            },
            "fixed_versions": [spec[0] for spec in VERSION_SPECS],
        },
    }
    (output / "analysis_config.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def run(config: AnalysisConfig | None = None) -> Path:
    config = config or load_app_config().analysis
    source_runs = resolve_source_runs(config)
    anchor_run = source_runs[-1]
    task_ids = _anchor_task_ids(anchor_run)
    records = merge_latest_records(source_runs, task_ids)
    candidates = _candidate_models(records, config)
    versions = _version_models(candidates)
    analysis_id = _analysis_id(config, anchor_run)

    base = config.analysis_results_base.resolve()
    output = base / analysis_id
    temporary = base / f".{analysis_id}.tmp"
    base.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        _write_snapshot(temporary, config, source_runs, anchor_run, task_ids, analysis_id)
        scores = _converter_human_scores()
        source_names = tuple(path.name for path in source_runs)
        for version, report_name, label in VERSION_SPECS:
            write_analysis_version(
                temporary,
                version=version,
                report_name=report_name,
                label=label,
                analysis_id=analysis_id,
                anchor_run=anchor_run.name,
                source_runs=source_names,
                task_ids=task_ids,
                models=versions[version],
                records=records,
                converter_scores=scores,
            )
        if output.exists():
            shutil.rmtree(output)
        temporary.replace(output)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print(
        f"Analysis complete: {output} "
        f"(anchor={anchor_run.name}, tasks={','.join(task_ids)})"
    )
    return output


def _framework_conditions(framework: str) -> tuple[str, ...]:
    return (
        f"{framework}-direct",
        f"{framework}-gold",
        f"{framework}-variant-1",
        f"{framework}-variant-2",
    )


def _framework_record(
    path: Path,
    root: Path,
    allowed: set[str],
) -> AccuracyRecord | None:
    return _read_accuracy_record(path, root, allowed)


def _load_original_records(
    source_root: Path,
    task_ids: set[str],
) -> list[AccuracyRecord]:
    records: list[AccuracyRecord] = []
    for path in result_files(source_root):
        record = _framework_record(path, source_root, {"original"})
        if record is None or record.task_id not in task_ids or not record.model:
            continue
        records.append(record)
    return records


def _load_framework_records(
    source_root: Path,
    framework: str,
) -> list[AccuracyRecord]:
    allowed = set(_framework_conditions(framework))
    merged: dict[tuple[str, str, str], AccuracyRecord] = {}
    for path in result_files(source_root):
        record = _framework_record(path, source_root, allowed)
        if record is None or not record.task_id or not record.model:
            continue
        merged[(record.task_id, record.model, record.language)] = record
    return list(merged.values())


def _result_task_ids(source_root: Path) -> tuple[str, ...]:
    task_ids = {
        path.parts[-3].removeprefix("task")
        for path in result_files(source_root)
        if path.parts[-3].startswith("task")
    }
    return tuple(sorted(task_ids, key=int))


def _canonical_framework_records(
    originals: list[AccuracyRecord],
    framework_records: list[AccuracyRecord],
    framework: str,
) -> list[AccuracyRecord]:
    records = list(originals)
    records.extend(
        replace(
            record,
            language=record.language.replace(f"{framework}-", "cnlp-", 1),
        )
        for record in framework_records
    )
    return records


def _align_to_original_baseline(
    originals: list[AccuracyRecord],
    framework_records: list[AccuracyRecord],
    framework: str,
    *,
    source_name: str = "final_result",
) -> tuple[list[AccuracyRecord], list[dict[str, str]]]:
    original_keys = {(record.task_id, record.model) for record in originals}
    framework_keys = {
        (record.task_id, record.model) for record in framework_records
    }
    missing = sorted(
        framework_keys - original_keys,
        key=lambda item: (int(item[0]), item[1]),
    )
    if not framework_records:
        raise ValueError(f"No {framework.upper()} result records were found")
    exclusions = [
        {
            "task_id": task_id,
            "model": model,
            "framework": framework,
            "reason": f"original baseline missing from {source_name}",
        }
        for task_id, model in missing
    ]
    aligned = [
        record
        for record in framework_records
        if (record.task_id, record.model) in original_keys
    ]
    return aligned, exclusions


def _rewrite_framework_labels(
    root: Path,
    framework: str,
    label: str,
) -> None:
    """Translate the canonical CNL-P report labels back to the framework."""
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8-sig")
        text = text.replace("cnlp-", f"{framework}-")
        text = text.replace("CNL-P", label)
        if path.suffix == ".md":
            text = text.replace(
                "> Data source: `final_result`  ",
                "> Original NL data source: `final_result`  ",
            )
        path.write_text(text, encoding="utf-8")


def _next_framework_analysis_id(output_base: Path) -> str:
    highest = 0
    if output_base.is_dir():
        for path in output_base.iterdir():
            match = FRAMEWORK_ANALYSIS_PATTERN.fullmatch(path.name)
            if path.is_dir() and match:
                highest = max(highest, int(match.group("number")))
    if highest >= 99:
        raise ValueError("No analysis-risen-rodes-NN number remains")
    return f"analysis-risen-rodes-{highest + 1:02d}"


def _write_framework_snapshot(
    output: Path,
    analysis_id: str,
    source_root: Path,
    task_ids: tuple[str, ...],
    methods: tuple[str, ...] = tuple(FRAMEWORKS),
) -> None:
    payload = {
        "analysis": {
            "analysis_id": analysis_id,
            "methods": list(methods),
            "task_scope": [f"task{task_id}" for task_id in task_ids],
            "data_source": str(source_root),
            "original_nl_source": str(source_root),
            "framework_result_source": str(source_root),
            "merge_rule": (
                "preconsolidated_final_result"
                if source_root.name == "final_result"
                else "preconsolidated_framework_result"
            ),
            "statistics_and_report_layout": "analysis.tool_analysis",
        }
    }
    (output / "analysis_config.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_framework_analysis(
    output: Path,
    *,
    source_root: Path,
    framework: str,
    analysis_id: str,
    task_ids: tuple[str, ...],
    originals: list[AccuracyRecord],
    report_name: str,
) -> None:
    label = FRAMEWORKS[framework]
    framework_records = _load_framework_records(source_root, framework)
    framework_records, exclusions = _align_to_original_baseline(
        originals,
        framework_records,
        framework,
        source_name=source_root.name,
    )
    records = _canonical_framework_records(
        originals,
        framework_records,
        framework,
    )
    write_analysis_version(
        output,
        version="all",
        report_name=report_name,
        label="All models",
        analysis_id=analysis_id,
        anchor_run=source_root.name,
        source_runs=(source_root.name,),
        task_ids=task_ids,
        models={record.model for record in framework_records},
        records=records,
        converter_scores=_converter_human_scores(label),
    )
    _rewrite_framework_labels(output, framework, label)
    write_csv(
        output / "baseline_exclusions.csv",
        ["task_id", "model", "framework", "reason"],
        exclusions,
    )


def run_framework(
    framework: str,
    source_root: Path,
    output: Path,
    *,
    analysis_id: str = "",
) -> Path:
    """Analyze one RISEN/RODES result tree with the shared report pipeline."""
    if framework not in FRAMEWORKS:
        raise ValueError(f"Unknown framework: {framework}")
    resolved_source = source_root.resolve()
    if not resolved_source.is_dir():
        raise FileNotFoundError(f"result directory not found: {resolved_source}")
    task_ids = _result_task_ids(resolved_source)
    if not task_ids:
        raise ValueError(f"{resolved_source} contains no task result files")
    originals = _load_original_records(resolved_source, set(task_ids))
    selected_id = analysis_id or f"analysis-{framework}"
    resolved_output = output.resolve()
    temporary = resolved_output.parent / f".{resolved_output.name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        _write_framework_snapshot(
            temporary,
            selected_id,
            resolved_source,
            task_ids,
            methods=(framework,),
        )
        _write_framework_analysis(
            temporary,
            source_root=resolved_source,
            framework=framework,
            analysis_id=selected_id,
            task_ids=task_ids,
            originals=originals,
            report_name="analysis_report.md",
        )
        if resolved_output.exists():
            shutil.rmtree(resolved_output)
        temporary.replace(resolved_output)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print(f"{FRAMEWORKS[framework]} analysis complete: {resolved_output}")
    return resolved_output


def run_risen_rodes(
    source_root: Path = FINAL_RESULT_ROOT,
    *,
    output_base: Path = ANALYSIS_RESULTS_ROOT,
    analysis_id: str = "",
) -> Path:
    """Analyze RISEN and RODES together under one versioned directory."""
    resolved_source = source_root.resolve()
    if not resolved_source.is_dir():
        raise FileNotFoundError(
            f"final_result directory not found: {resolved_source}"
        )
    task_ids = _result_task_ids(resolved_source)
    if not task_ids:
        raise ValueError("final_result contains no task result files")
    originals = _load_original_records(resolved_source, set(task_ids))
    selected_id = analysis_id or _next_framework_analysis_id(output_base)
    if FRAMEWORK_ANALYSIS_PATTERN.fullmatch(selected_id) is None:
        raise ValueError("analysis_id must use analysis-risen-rodes-NN")

    base = output_base.resolve()
    output = base / selected_id
    temporary = base / f".{selected_id}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        _write_framework_snapshot(
            temporary,
            selected_id,
            resolved_source,
            task_ids,
        )
        for framework in FRAMEWORKS:
            _write_framework_analysis(
                temporary / framework,
                source_root=resolved_source,
                framework=framework,
                analysis_id=selected_id,
                task_ids=task_ids,
                originals=originals,
                report_name="analysis_report.md",
            )
        if output.exists():
            shutil.rmtree(output)
        temporary.replace(output)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print(f"RISEN/RODES analysis complete: {output}")
    return output


PUBLIC_RAW_RESULTS_ROOT = PROJECT_ROOT / "results" / "raw_results"
PUBLIC_FRAMEWORK_PROMPTS = {
    "cnlp": {
        "direct": "cnlp-direct",
        "gold": "cnlp-gold",
        "variant_1": "cnlp-variant-1",
        "variant_2": "cnlp-variant-2",
    },
    "risen": {
        "direct": "risen-direct",
        "gold": "risen-gold",
        "variant_1": "risen-variant-1",
        "variant_2": "risen-variant-2",
    },
    "rodes": {
        "direct": "rodes-direct",
        "gold": "rodes-gold",
        "variant_1": "rodes-variant-1",
        "variant_2": "rodes-variant-2",
    },
}
PUBLIC_TASK_SUMMARY_FIELDS = [
    "task_id",
    "converter_human_score",
    "original_accuracy_percent",
    "direct_accuracy_percent",
    "gold_accuracy_percent",
    "variant_1_accuracy_percent",
    "variant_2_accuracy_percent",
]
PUBLIC_MODEL_OVERVIEW_FIELDS = [
    "task_id",
    "model",
    "original_accuracy_percent",
    "direct_accuracy_percent",
    "gold_accuracy_percent",
    "variant_1_accuracy_percent",
    "variant_2_accuracy_percent",
    "best_revised_prompt",
    "best_revised_accuracy_percent",
    "best_minus_direct_pp",
    "best_minus_original_pp",
]
PUBLIC_PROMPT_DIFFERENCE_FIELDS = [
    "task_id",
    "baseline",
    "target",
    "baseline_accuracy_percent",
    "target_accuracy_percent",
    "delta_pp",
    "direction",
]
PUBLIC_CROSS_MODEL_FIELDS = [
    "task_id", "model", "model_intelligence",
    "original_correct_count", "original_total_rows", "original_accuracy",
    "cnlp_best_prompt", "cnlp_best_correct_count", "cnlp_best_total_rows",
    "cnlp_best_accuracy", "cnlp_delta_vs_original_pp",
    "risen_best_prompt", "risen_best_correct_count", "risen_best_total_rows",
    "risen_best_accuracy", "risen_delta_vs_original_pp",
    "rodes_best_prompt", "rodes_best_correct_count", "rodes_best_total_rows",
    "rodes_best_accuracy", "rodes_delta_vs_original_pp",
    "best_framework", "best_framework_accuracy",
]
PUBLIC_CROSS_TASK_FIELDS = [
    "task_id", "original_correct_count", "original_total_rows",
    "original_accuracy",
    "cnlp_best_prompt", "cnlp_best_correct_count", "cnlp_best_total_rows",
    "cnlp_best_accuracy", "cnlp_delta_vs_original_pp",
    "risen_best_prompt", "risen_best_correct_count", "risen_best_total_rows",
    "risen_best_accuracy", "risen_delta_vs_original_pp",
    "rodes_best_prompt", "rodes_best_correct_count", "rodes_best_total_rows",
    "rodes_best_accuracy", "rodes_delta_vs_original_pp",
    "best_framework", "best_framework_accuracy",
]


def _public_accuracy(record: AccuracyRecord) -> float:
    return record.correct_count / record.total_rows if record.total_rows else 0.0


def _public_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _load_public_records(root: Path, allowed: set[str]) -> list[AccuracyRecord]:
    records: list[AccuracyRecord] = []
    for path in result_files(root):
        record = _read_accuracy_record(path, root, allowed)
        if record is not None and record.task_id and record.model:
            records.append(record)
    return sorted(
        records,
        key=lambda item: (int(item.task_id), item.model.casefold(), item.language),
    )


def _public_framework_records(
    framework: str,
    originals: list[AccuracyRecord],
) -> list[AccuracyRecord]:
    prompts = PUBLIC_FRAMEWORK_PROMPTS[framework]
    if framework == "cnlp":
        framework_records = _load_public_records(
            PUBLIC_RAW_RESULTS_ROOT / framework,
            set(prompts.values()),
        )
    else:
        framework_records = _load_public_records(
            PUBLIC_RAW_RESULTS_ROOT / framework,
            set(prompts.values()),
        )
    framework_keys = {
        (record.task_id, record.model) for record in framework_records
    }
    original_by_key = {
        (record.task_id, record.model): record for record in originals
    }
    missing = sorted(
        framework_keys - set(original_by_key),
        key=lambda item: (int(item[0]), item[1].casefold()),
    )
    if missing:
        formatted = ", ".join(f"task{task}/{model}" for task, model in missing)
        raise ValueError(f"{framework} is missing Original baselines: {formatted}")
    aligned_originals = [original_by_key[key] for key in sorted(
        framework_keys,
        key=lambda item: (int(item[0]), item[1].casefold()),
    )]
    return aligned_originals + framework_records


def _public_task_values(
    records: list[AccuracyRecord],
) -> tuple[list[dict[str, object]], dict[tuple[str, str], float]]:
    grouped: dict[tuple[str, str], list[AccuracyRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.task_id, record.language)].append(record)
    task_rows: list[dict[str, object]] = []
    for (task_id, condition), items in grouped.items():
        total = sum(item.total_rows for item in items)
        correct = sum(item.correct_count for item in items)
        incorrect = sum(item.incorrect_count for item in items)
        unresolved = sum(item.unresolved_count for item in items)
        accuracy = correct / total if total else 0.0
        task_rows.append({
            "task_id": task_id,
            "condition": condition,
            "accuracy_percent": _percent(accuracy),
            "accuracy": f"{accuracy:.3f}".rstrip("0").rstrip("."),
            "total_rows": total,
            "correct_count": correct,
            "incorrect_count": incorrect,
            "unresolved_count": unresolved,
            "model_count": len(items),
            "models": ",".join(sorted(
                (item.model for item in items), key=str.casefold
            )),
        })
    task_rows.sort(key=lambda row: (
        int(str(row["task_id"])), str(row["condition"])
    ))
    return task_rows, _values(task_rows)


def _public_best_prompt_by_task(
    task_ids: tuple[str, ...],
    values: dict[tuple[str, str], float],
    prompts: dict[str, str],
) -> dict[str, str]:
    order = (prompts["gold"], prompts["variant_1"], prompts["variant_2"])
    selected: dict[str, str] = {}
    for task_id in task_ids:
        candidates = {
            prompt: values[(task_id, prompt)]
            for prompt in order
            if (task_id, prompt) in values
        }
        if not candidates:
            continue
        best = max(candidates.values())
        selected[task_id] = next(
            prompt for prompt in order
            if prompt in candidates and abs(candidates[prompt] - best) < 1e-12
        )
    return selected


def _public_framework_tables(
    framework: str,
    records: list[AccuracyRecord],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    prompts = PUBLIC_FRAMEWORK_PROMPTS[framework]
    task_ids = tuple(sorted({record.task_id for record in records}, key=int))
    task_rows, values = _public_task_values(records)
    task_lookup = {
        (str(row["task_id"]), str(row["condition"])): row
        for row in task_rows
    }
    converter = "CNL-P" if framework == "cnlp" else FRAMEWORKS[framework]
    converter_scores = _converter_human_scores(converter)
    task_summary: list[dict[str, object]] = []
    for task_id in task_ids:
        def task_percent(condition: str) -> str:
            row = task_lookup.get((task_id, condition))
            return str(row["accuracy_percent"]) if row else ""

        task_summary.append({
            "task_id": task_id,
            "converter_human_score": (
                f"{converter_scores[task_id]:.3f}"
                if task_id in converter_scores else ""
            ),
            "original_accuracy_percent": task_percent("original"),
            "direct_accuracy_percent": task_percent(prompts["direct"]),
            "gold_accuracy_percent": task_percent(prompts["gold"]),
            "variant_1_accuracy_percent": task_percent(prompts["variant_1"]),
            "variant_2_accuracy_percent": task_percent(prompts["variant_2"]),
        })

    best_by_task = _public_best_prompt_by_task(task_ids, values, prompts)
    by_task_model: dict[tuple[str, str], dict[str, AccuracyRecord]] = defaultdict(dict)
    for record in records:
        by_task_model[(record.task_id, record.model)][record.language] = record
    model_overview: list[dict[str, object]] = []
    for (task_id, model), conditions in sorted(
        by_task_model.items(),
        key=lambda item: (int(item[0][0]), item[0][1].casefold()),
    ):
        if prompts["direct"] not in conditions:
            continue
        best_prompt = best_by_task.get(task_id, "")
        best_record = conditions.get(best_prompt)
        direct_record = conditions.get(prompts["direct"])
        original_record = conditions.get("original")

        def model_percent(condition: str) -> str:
            record = conditions.get(condition)
            return record.accuracy_percent if record else ""

        best_value = float(best_record.accuracy) if best_record else None
        direct_value = float(direct_record.accuracy) if direct_record else None
        original_value = float(original_record.accuracy) if original_record else None
        model_overview.append({
            "task_id": task_id,
            "model": model,
            "original_accuracy_percent": model_percent("original"),
            "direct_accuracy_percent": model_percent(prompts["direct"]),
            "gold_accuracy_percent": model_percent(prompts["gold"]),
            "variant_1_accuracy_percent": model_percent(prompts["variant_1"]),
            "variant_2_accuracy_percent": model_percent(prompts["variant_2"]),
            "best_revised_prompt": best_prompt,
            "best_revised_accuracy_percent": (
                _percent(best_value) if best_value is not None else ""
            ),
            "best_minus_direct_pp": (
                _delta(best_value - direct_value)
                if best_value is not None and direct_value is not None else ""
            ),
            "best_minus_original_pp": (
                _delta(best_value - original_value)
                if best_value is not None and original_value is not None else ""
            ),
        })

    comparisons = (
        ("original", prompts["direct"]),
        ("original", prompts["gold"]),
        ("original", prompts["variant_1"]),
        ("original", prompts["variant_2"]),
        (prompts["direct"], prompts["gold"]),
        (prompts["direct"], prompts["variant_1"]),
        (prompts["direct"], prompts["variant_2"]),
    )
    differences: list[dict[str, object]] = []
    for task_id in task_ids:
        for baseline, target in comparisons:
            baseline_value = values.get((task_id, baseline))
            target_value = values.get((task_id, target))
            if baseline_value is None or target_value is None:
                continue
            delta = target_value - baseline_value
            differences.append({
                "task_id": task_id,
                "baseline": baseline,
                "target": target,
                "baseline_accuracy_percent": _percent(baseline_value),
                "target_accuracy_percent": _percent(target_value),
                "delta_pp": _delta(delta),
                "direction": _direction(delta),
            })
    return task_summary, model_overview, differences


def _public_best_record(
    conditions: dict[str, AccuracyRecord],
    prompts: dict[str, str],
) -> tuple[str, AccuracyRecord] | None:
    order = (prompts["gold"], prompts["variant_1"], prompts["variant_2"])
    available = [(prompt, conditions[prompt]) for prompt in order if prompt in conditions]
    if not available:
        return None
    best_accuracy = max(_public_accuracy(record) for _, record in available)
    return next(
        (prompt, record) for prompt, record in available
        if abs(_public_accuracy(record) - best_accuracy) < 1e-12
    )


def _public_cross_framework_tables(
    records_by_framework: dict[str, list[AccuracyRecord]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    original_by_key = {
        (record.task_id, record.model): record
        for record in records_by_framework["cnlp"]
        if record.language == "original"
    }
    conditions_by_framework: dict[
        str, dict[tuple[str, str], dict[str, AccuracyRecord]]
    ] = {}
    for framework, records in records_by_framework.items():
        grouped: dict[tuple[str, str], dict[str, AccuracyRecord]] = defaultdict(dict)
        for record in records:
            if record.language != "original":
                grouped[(record.task_id, record.model)][record.language] = record
        conditions_by_framework[framework] = grouped
    common_keys = set(original_by_key)
    for grouped in conditions_by_framework.values():
        common_keys &= set(grouped)
    intelligence = {
        model.key: model.intelligence for model in load_model_registry().values()
    }
    labels = {"cnlp": "CNL-P", "risen": "RISEN", "rodes": "RODES"}
    model_rows: list[dict[str, object]] = []
    for task_id, model in sorted(
        common_keys,
        key=lambda item: (int(item[0]), item[1].casefold()),
    ):
        original = original_by_key[(task_id, model)]
        original_accuracy = _public_accuracy(original)
        row: dict[str, object] = {
            "task_id": task_id,
            "model": model,
            "model_intelligence": intelligence.get(model, ""),
            "original_correct_count": original.correct_count,
            "original_total_rows": original.total_rows,
            "original_accuracy": _public_number(original_accuracy),
        }
        framework_accuracies: dict[str, float] = {}
        for framework in ("cnlp", "risen", "rodes"):
            best = _public_best_record(
                conditions_by_framework[framework][(task_id, model)],
                PUBLIC_FRAMEWORK_PROMPTS[framework],
            )
            if best is None:
                continue
            prompt, record = best
            accuracy = _public_accuracy(record)
            framework_accuracies[framework] = accuracy
            row.update({
                f"{framework}_best_prompt": prompt,
                f"{framework}_best_correct_count": record.correct_count,
                f"{framework}_best_total_rows": record.total_rows,
                f"{framework}_best_accuracy": _public_number(accuracy),
                f"{framework}_delta_vs_original_pp": (
                    f"{(accuracy - original_accuracy) * 100:.3f}".rstrip("0").rstrip(".")
                ),
            })
        best_accuracy = max(framework_accuracies.values())
        row["best_framework"] = ";".join(
            labels[framework] for framework in ("cnlp", "risen", "rodes")
            if abs(framework_accuracies[framework] - best_accuracy) < 1e-12
        )
        row["best_framework_accuracy"] = _public_number(best_accuracy)
        model_rows.append(row)

    task_rows: list[dict[str, object]] = []
    task_ids = sorted({task_id for task_id, _ in common_keys}, key=int)
    for task_id in task_ids:
        original_items = [
            record for (record_task, _), record in original_by_key.items()
            if record_task == task_id
        ]
        original_correct = sum(record.correct_count for record in original_items)
        original_total = sum(record.total_rows for record in original_items)
        original_accuracy = original_correct / original_total if original_total else 0.0
        row = {
            "task_id": task_id,
            "original_correct_count": original_correct,
            "original_total_rows": original_total,
            "original_accuracy": _public_number(original_accuracy),
        }
        framework_accuracies: dict[str, float] = {}
        for framework in ("cnlp", "risen", "rodes"):
            prompts = PUBLIC_FRAMEWORK_PROMPTS[framework]
            candidate_rows: list[tuple[str, int, int, float]] = []
            for prompt in (prompts["gold"], prompts["variant_1"], prompts["variant_2"]):
                items = [
                    record
                    for (record_task, _), conditions in conditions_by_framework[framework].items()
                    if record_task == task_id and prompt in conditions
                    for record in (conditions[prompt],)
                ]
                if not items:
                    continue
                correct = sum(record.correct_count for record in items)
                total = sum(record.total_rows for record in items)
                candidate_rows.append((prompt, correct, total, correct / total if total else 0.0))
            best_accuracy = max(item[3] for item in candidate_rows)
            prompt, correct, total, accuracy = next(
                item for item in candidate_rows
                if abs(item[3] - best_accuracy) < 1e-12
            )
            framework_accuracies[framework] = accuracy
            row.update({
                f"{framework}_best_prompt": prompt,
                f"{framework}_best_correct_count": correct,
                f"{framework}_best_total_rows": total,
                f"{framework}_best_accuracy": _public_number(accuracy),
                f"{framework}_delta_vs_original_pp": (
                    f"{(accuracy - original_accuracy) * 100:.3f}".rstrip("0").rstrip(".")
                ),
            })
        best_accuracy = max(framework_accuracies.values())
        row["best_framework"] = ";".join(
            labels[framework] for framework in ("cnlp", "risen", "rodes")
            if abs(framework_accuracies[framework] - best_accuracy) < 1e-12
        )
        row["best_framework_accuracy"] = _public_number(best_accuracy)
        task_rows.append(row)
    return model_rows, task_rows


def run_public_results(
    output_root: Path = ANALYSIS_RESULTS_ROOT,
) -> Path:
    """Generate the three public tables per framework and cross-framework tables."""
    cnlp_root = PUBLIC_RAW_RESULTS_ROOT / "cnlp"
    originals = _load_public_records(cnlp_root, {"original"})
    records_by_framework = {
        framework: _public_framework_records(framework, originals)
        for framework in ("cnlp", "risen", "rodes")
    }
    resolved_output = output_root.resolve()
    temporary = resolved_output / ".public-results.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        for framework, records in records_by_framework.items():
            framework_root = temporary / framework
            task_summary, model_overview, differences = _public_framework_tables(
                framework, records
            )
            write_csv(
                framework_root / "task_summary.csv",
                PUBLIC_TASK_SUMMARY_FIELDS,
                task_summary,
            )
            write_csv(
                framework_root / "model_overview.csv",
                PUBLIC_MODEL_OVERVIEW_FIELDS,
                model_overview,
            )
            write_csv(
                framework_root / "prompt_differences.csv",
                PUBLIC_PROMPT_DIFFERENCE_FIELDS,
                differences,
            )
        cross_model, cross_task = _public_cross_framework_tables(records_by_framework)
        write_csv(
            temporary / "model_summary.csv",
            PUBLIC_CROSS_MODEL_FIELDS,
            cross_model,
        )
        write_csv(
            temporary / "task_summary.csv",
            PUBLIC_CROSS_TASK_FIELDS,
            cross_task,
        )

        resolved_output.mkdir(parents=True, exist_ok=True)
        for framework in ("cnlp", "risen", "rodes"):
            target = resolved_output / framework
            if target.exists():
                shutil.rmtree(target)
            (temporary / framework).replace(target)
        for path in resolved_output.iterdir():
            if path.is_file():
                path.unlink()
        for path in tuple(temporary.iterdir()):
            path.replace(resolved_output / path.name)
        temporary.rmdir()
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print(f"Public analysis results complete: {resolved_output}")
    return resolved_output


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("cnlp", "risen", "rodes", "risen-rodes", "public"),
        default="public",
        help="analysis workflow to run (default: public three-table output)",
    )
    parser.add_argument("--source-root", type=Path, default=FINAL_RESULT_ROOT)
    parser.add_argument("--output-base", type=Path, default=ANALYSIS_RESULTS_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        help="exact output directory for single-framework mode",
    )
    parser.add_argument("--analysis-id", default="")
    return parser.parse_args()


def main() -> Path:
    args = _arguments()
    if args.mode == "public":
        return run_public_results(args.output_base)
    if args.mode == "cnlp":
        return run()
    if args.mode == "risen-rodes":
        return run_risen_rodes(
            args.source_root,
            output_base=args.output_base,
            analysis_id=args.analysis_id,
        )
    output = args.output or (args.output_base / args.mode)
    return run_framework(
        args.mode,
        args.source_root,
        output,
        analysis_id=args.analysis_id,
    )


if __name__ == "__main__":
    main()
