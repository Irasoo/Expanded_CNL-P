"""Step 3: apply manual decisions and write task/run summaries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from utils import (
    AccuracyRecord,
    PipelineConfig,
    README_LANGUAGE_ORDER,
    SUMMARY_FIELDS,
    _read_csv,
    format_accuracy,
    global_summary_path,
    load_model_registry,
    resolve_run_root,
    result_files,
    task_summary_path,
    write_csv,
    write_run_readme,
)
from .step2_judge import score_semantic_row


def _apply_manual_review(run_root: Path) -> int:
    review_path = run_root / "manual_review.csv"
    if not review_path.is_file():
        return 0
    _, reviews = _read_csv(review_path)
    overrides: dict[str, dict[str, str]] = defaultdict(dict)
    for row in reviews:
        score = row.get("manual_score", "").strip()
        if score in {"0", "1"}:
            overrides[row.get("source_csv", "").strip()][row.get("instance_id", "").strip()] = score
    applied = 0
    for path in result_files(run_root):
        relative = path.relative_to(run_root).as_posix()
        file_overrides = overrides.get(relative, {})
        if not file_overrides:
            continue
        fields, rows = _read_csv(path)
        changed = False
        for row in rows:
            score = file_overrides.get(row.get("instance_id", "").strip())
            if score is None:
                continue
            if row.get("score", "") != score:
                row["score"] = score
                applied += 1
                changed = True
            if not row.get("extracted_answer", ""):
                row["extracted_answer"] = score_semantic_row(
                    row["task_id"],
                    row["standard_output"],
                    row.get("model_output", ""),
                    row.get("instance_content", ""),
                ).extracted_answer
                changed = True
        if changed:
            write_csv(path, fields, rows)
    return applied


def _record(path: Path, run_root: Path, rows: list[dict[str, str]]) -> AccuracyRecord:
    first = rows[0]
    all_scores = [row.get("score", "").strip() for row in rows]
    scores = [score for score in all_scores if score in {"0", "1"}]
    correct = scores.count("1")
    incorrect = scores.count("0")
    unresolved = all_scores.count("2")
    accuracy, percent = format_accuracy(correct, len(scores))
    return AccuracyRecord(
        task_id=first["task_id"],
        model=first["model"],
        accuracy_percent=percent,
        language=first["language"],
        record_type="file",
        source_csv=path.relative_to(run_root).as_posix(),
        run_timestamp=run_root.name,
        total_rows=len(scores),
        correct_count=correct,
        incorrect_count=incorrect,
        unresolved_count=unresolved,
        accuracy=accuracy,
    )


def _aggregate(items: list[AccuracyRecord], *, task_id: str, model: str, language: str, record_type: str, source_csv: str, run_id: str) -> AccuracyRecord:
    total = sum(item.total_rows for item in items)
    correct = sum(item.correct_count for item in items)
    incorrect = sum(item.incorrect_count for item in items)
    unresolved = sum(item.unresolved_count for item in items)
    accuracy, percent = format_accuracy(correct, total)
    return AccuracyRecord(task_id, model, percent, language, record_type, source_csv, run_id, total, correct, incorrect, unresolved, accuracy)


def _summary_sort_key(record: AccuracyRecord, intelligence: dict[str, int]) -> tuple[int, int, str, int, str]:
    language_rank = {language: index for index, language in enumerate(README_LANGUAGE_ORDER)}
    try:
        task_rank = int(record.task_id)
    except ValueError:
        task_rank = 10**9
    return (
        task_rank,
        -intelligence.get(record.model, 0),
        record.model,
        language_rank.get(record.language, len(language_rank)),
        record.language,
    )


def run(
    config: PipelineConfig,
    *,
    run_root: Path | None = None,
    apply_manual_reviews: bool = True,
) -> tuple[Path, list[AccuracyRecord]]:
    run_root = run_root or resolve_run_root(config)
    applied = _apply_manual_review(run_root) if apply_manual_reviews else 0
    if applied:
        print(f"Applied {applied} manual review decisions")
    records: list[AccuracyRecord] = []
    per_task: dict[str, list[AccuracyRecord]] = defaultdict(list)
    for path in result_files(run_root):
        _, rows = _read_csv(path)
        if not rows:
            continue
        record = _record(path, run_root, rows)
        records.append(record)
        per_task[record.task_id].append(record)
    intelligence = {
        model.key: model.intelligence
        for model in load_model_registry().values()
    }
    for task_id, items in per_task.items():
        ordered_items = sorted(items, key=lambda item: _summary_sort_key(item, intelligence))
        write_csv(task_summary_path(run_root, task_id), SUMMARY_FIELDS, (asdict(item) for item in ordered_items))

    summaries = sorted(records, key=lambda item: _summary_sort_key(item, intelligence))
    by_model: dict[str, list[AccuracyRecord]] = defaultdict(list)
    for record in records:
        by_model[record.model].append(record)
    overall = [
        _aggregate(
            items,
            task_id="all",
            model=model,
            language="all",
            record_type="model_aggregate",
            source_csv=f"all/{model}",
            run_id=run_root.name,
        )
        for model, items in by_model.items()
    ]
    summaries.extend(sorted(overall, key=lambda item: _summary_sort_key(item, intelligence)))
    output = global_summary_path(run_root)
    write_csv(output, SUMMARY_FIELDS, (asdict(item) for item in summaries))
    write_run_readme(run_root)
    print(f"Step 3 complete: task summaries={len(per_task)}, total summary={output}")
    return output, summaries


if __name__ == "__main__":
    from main import build_config

    run(build_config())
