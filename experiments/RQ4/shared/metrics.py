"""Explicit final-attempt accounting and human-reviewed effectiveness metrics."""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import hashlib
import math
import statistics

from .batch import read_json, write_json

TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")


def token_counts(usage):
    """Missing usage is unknown, not proof that the execution cost zero tokens."""
    if not isinstance(usage, dict) or not isinstance(usage.get("total"), dict):
        return None
    total = usage["total"]
    if any(type(total.get(name)) not in (int, float) or total[name] < 0
           or not math.isfinite(total[name]) for name in TOKEN_FIELDS):
        return None
    if total["cached_input_tokens"] > total["input_tokens"] or total["reasoning_tokens"] > total["output_tokens"]:
        raise ValueError("Cached input and reasoning tokens must be subsets of input/output.")
    return {name: int(total[name]) for name in TOKEN_FIELDS}


def selected_execution(run_directory):
    root_record = read_json(run_directory / "execution_log.json")
    selected = root_record.get("selected_attempt")
    if selected:
        path = (run_directory / selected / "execution_log.json").resolve()
        if not path.is_relative_to((run_directory / "attempts").resolve()):
            raise ValueError("Selected attempt escapes its Run directory.")
        candidates = [path]
    else:
        candidates = sorted((run_directory / "attempts").glob("attempt_*/execution_log.json"), reverse=True)
    for path in candidates:
        record = read_json(path)
        if record.get("status") in {"completed", "failed", "timeout"} and record.get("rerun_validity") != "invalid":
            return path, record
    raise ValueError(f"No final valid execution log is available: {run_directory}")


def execution_fingerprint(path):
    """A rerun or changed output invalidates an earlier human review."""
    digest = hashlib.sha256(path.read_bytes())
    for filename in ("stdout.txt", "stderr.txt"):
        output = path.parent / filename
        digest.update(filename.encode("utf-8"))
        digest.update(output.read_bytes() if output.is_file() else b"<missing>")
    return digest.hexdigest()


def read_reviews(path):
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    indexed = {}
    for row in rows:
        key = row["run_directory"]
        if key in indexed:
            raise ValueError(f"Duplicate review: {key}")
        if row.get("judgment", "") not in {"", "Success", "Failure"}:
            raise ValueError(f"Review judgment must be Success, Failure, or blank: {key}")
        indexed[key] = row
    return indexed


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def summarize_runs(runs):
    successes = [run for run in runs if run["judgment"] == "Success"]
    failures = [run for run in runs if run["judgment"] == "Failure"]
    pending = [run for run in runs if not run["judgment"]]
    measured = [run for run in runs if run["tokens"] is not None]

    def average(selected, denominator):
        if not denominator:
            return None
        return {name: sum(run["tokens"][name] for run in selected) / denominator for name in TOKEN_FIELDS}

    known_successes = [run for run in successes if run["tokens"] is not None]
    groups = defaultdict(list)
    for run in runs:
        groups[(run["trial"], run["scenario"])].append(run)
    recurrence = defaultdict(Counter)
    for (trial, scenario), group in groups.items():
        failed = sum(run["judgment"] == "Failure" for run in group)
        if failed:
            recurrence[trial][f"{failed}/{len(group)}"] += 1
    return {
        "execution_count": len(runs), "success_count": len(successes),
        "failure_count": len(failures), "pending_review_count": len(pending),
        "success_rate_percent": (100 * len(successes) / len(runs)) if runs and not pending else None,
        "failure_recurrence": {trial: dict(counts) for trial, counts in recurrence.items()},
        "process_status_counts": dict(Counter(run["status"] for run in runs)),
        "runtime_recorded_execution_count": len(measured),
        "runtime_missing_usage_count": len(runs) - len(measured),
        "successful_executions_missing_usage_count": len(successes) - len(known_successes),
        "average_tokens_per_success": (
            average(known_successes, len(successes))
            if not pending and len(known_successes) == len(successes) else None),
        "amortized_recorded_tokens_per_success": (
            average(measured, len(successes)) if not pending else None),
    }


def generation_summary(generation_directory):
    groups = defaultdict(list)
    for path in sorted(generation_directory.glob("*/*/compilation_log.json")):
        root_record = read_json(path)
        attempts = sorted((path.parent / "attempts").glob("attempt_*/compilation_log.json"))
        record = read_json(attempts[-1]) if attempts else root_record
        tokens = token_counts(record.get("token_usage") or record.get("compilation_token_usage"))
        groups[(root_record["case_name"], root_record["compilation_method"])].append(tokens)
    results = {}
    for (case, method), values in groups.items():
        totals = [value["total_tokens"] for value in values if value is not None]
        complete = len(totals) == len(values)
        mean = statistics.mean(totals) if totals and complete else None
        results[f"{case}/{method}"] = {
            "generation_trial_count": len(values), "missing_usage_count": len(values) - len(totals),
            "average_tokens": mean,
            "sample_cv_percent": (100 * statistics.stdev(totals) / mean)
            if complete and len(totals) > 1 and mean else None,
        }
    return results


def process_testing_batch(experiment_directory, generation_id, testing_id):
    testing_directory = experiment_directory / "results" / generation_id / testing_id
    if not testing_directory.is_dir():
        raise FileNotFoundError(testing_directory)
    output = experiment_directory / "analysis" / generation_id / testing_id
    review_path = output / "reviews.csv"
    old_reviews = read_reviews(review_path)
    review_rows, runs = [], []
    root_logs = sorted(testing_directory.glob("*/*/*/run_*/execution_log.json"))
    manifest_path = testing_directory / "testing_manifest.json"
    if manifest_path.is_file():
        expected = set(read_json(manifest_path)["executions"])
        observed = {path.parent.relative_to(testing_directory).as_posix() for path in root_logs}
        if observed != expected:
            raise ValueError(f"Execution set is incomplete or unexpected: missing={sorted(expected - observed)}, extra={sorted(observed - expected)}")
    for root_log in root_logs:
        run_directory = root_log.parent
        path, record = selected_execution(run_directory)
        relative = run_directory.relative_to(testing_directory).as_posix()
        fingerprint = execution_fingerprint(path)
        old = old_reviews.get(relative, {})
        judgment = old.get("judgment", "") if old.get("execution_fingerprint") == fingerprint else ""
        if judgment == "Success" and record["status"] != "completed":
            raise ValueError(f"A non-completed execution cannot be reviewed as Success: {run_directory}")
        # Process errors are execution failures even without business output.
        if not judgment and record["status"] != "completed":
            judgment = "Failure"
        row = {"run_directory": relative, "selected_attempt": path.parent.relative_to(run_directory).as_posix(),
               "process_status": record["status"], "execution_fingerprint": fingerprint,
               "judgment": judgment, "notes": old.get("notes", "")}
        review_rows.append(row)
        runs.append({"case": relative.split("/")[0], "method": record["compilation_method"],
                     "trial": relative.split("/")[1], "scenario": relative.split("/")[2],
                     "judgment": judgment, "status": record["status"],
                     "tokens": token_counts(record.get("runtime_token_usage"))})
    if not runs:
        raise ValueError(f"No Run execution logs found: {testing_directory}")
    output.mkdir(parents=True, exist_ok=True)
    if review_path.exists():
        previous = review_path.with_name("reviews.previous.csv")
        previous.write_bytes(review_path.read_bytes())
    write_csv(review_path, review_rows,
              ["run_directory", "selected_attempt", "process_status", "execution_fingerprint", "judgment", "notes"])
    grouped = defaultdict(list)
    for run in runs:
        grouped[(run["case"], run["method"])].append(run)
    summary = {"generation_id": generation_id, "testing_id": testing_id,
               "accounting": "One final valid attempt per Run; discarded retries excluded. Cached input is part of input; reasoning is part of output.",
               "generation": generation_summary(experiment_directory / "generated" / generation_id),
               "testing": {f"{case}/{method}": summarize_runs(values) for (case, method), values in grouped.items()}}
    write_json(output / "summary.json", summary)
    rows = []
    for key, values in summary["testing"].items():
        row = {"case_method": key, **{field: values[field] for field in (
            "execution_count", "success_count", "failure_count", "pending_review_count", "success_rate_percent", "runtime_missing_usage_count")}}
        for metric in ("average_tokens_per_success", "amortized_recorded_tokens_per_success"):
            row.update({f"{metric}_{name}": (values[metric][name] if values[metric] else "")
                        for name in TOKEN_FIELDS})
        rows.append(row)
    write_csv(output / "summary.csv", rows, list(rows[0]))
    return output, summary
