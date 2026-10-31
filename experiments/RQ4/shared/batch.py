"""Freeze selected inputs and persist the identities of new experiment batches."""
from datetime import datetime
from pathlib import Path
import hashlib
import json
import shutil

from .layout import CASE_NAMES, METHODS, PROJECT_DIRECTORY, SPECIFICATION_FILES, directory_name


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan(representations, cases, generation_counts, parallel_executions, repeat_count):
    if not representations or len(set(representations)) != len(representations):
        raise ValueError("Select one or more distinct representations.")
    if not cases or len(set(cases)) != len(cases) or set(cases) - set(CASE_NAMES):
        raise ValueError("Select distinct cases from the four published cases.")
    if type(repeat_count) is not int or repeat_count < 1:
        raise ValueError("repeat_count must be a positive integer.")
    for representation in representations:
        if representation not in METHODS:
            raise ValueError(f"Unknown representation: {representation}")
        selected = generation_counts[representation]
        if not selected or set(selected) - set(METHODS[representation]):
            raise ValueError(f"Unsupported methods for {representation}: {selected}")
        if any(type(count) is not int or count < 1 for count in selected.values()):
            raise ValueError("Generation counts must be positive integers.")
        parallel = parallel_executions[representation]
        if type(parallel) is not int or parallel < 1:
            raise ValueError("Runtime concurrency must be a positive integer.")


def create_batch(*, representations, cases, generation_counts, parallel_executions, repeat_count):
    validate_plan(representations, cases, generation_counts, parallel_executions, repeat_count)
    sources = []
    for representation in representations:
        for case in cases:
            files = [SPECIFICATION_FILES[representation], "reference_code.py",
                     "reference_code_for_codex.py", "branch_input_groups.yaml"]
            for name in files:
                sources.append((PROJECT_DIRECTORY / "cases" / case / name,
                                Path(representation) / "cases" / case / name))
            sources.append((PROJECT_DIRECTORY / "prompts" / f"codex_{representation}.md",
                            Path(representation) / "cases" / case / "generation_prompt.md"))
    for source, _ in sources:
        if not source.is_file():
            raise FileNotFoundError(source)

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    root = PROJECT_DIRECTORY / "batches" / batch_id
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "batch_id": batch_id, "case_names": list(cases),
        "repeat_count": repeat_count,
        "representations": {name: {"generation_counts": dict(generation_counts[name]),
                                    "max_parallel_executions": parallel_executions[name],
                                    "generation_id": None, "testing_ids": []}
                            for name in representations},
        "frozen_inputs": {},
    }
    for source, relative in sources:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest["frozen_inputs"][relative.as_posix()] = file_hash(destination)
    write_json(root / "batch_manifest.json", manifest)
    return root, manifest


def load_batch(batch_id):
    root = PROJECT_DIRECTORY / "batches" / directory_name(batch_id)
    manifest = read_json(root / "batch_manifest.json")
    for relative, expected in manifest["frozen_inputs"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Frozen input path escapes the batch directory.")
        if not path.is_file() or file_hash(path) != expected:
            raise ValueError(f"Frozen experimental input changed: {path}")
    return root, manifest


def compilation_plan(root, representation, cases, generation_counts, timeout_seconds):
    if representation not in METHODS or set(generation_counts) - set(METHODS[representation]):
        raise ValueError(f"Unsupported generation methods for {representation}")
    return [{"case_name": case, "methods": [
        {"method": method, "count": count, "timeout_seconds": timeout_seconds,
         **({"options": {"reasoning_effort": "high",
                         "specification_file": SPECIFICATION_FILES[representation],
                         "prompt_file": "generation_prompt.md"}} if method == "codex" else {})}
        for method, count in generation_counts.items()
    ]} for case in cases]
