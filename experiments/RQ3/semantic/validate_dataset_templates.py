from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from experiments._bootstrap import configure_source_paths
configure_source_paths()

from cnlp_compiler.parser import ParserLike
from cnlp_compiler.semantic_analysis import SemanticAnalyzer

from experiments.RQ3.semantic.tools import check_cnlp_by_llm


HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
TEMPLATES = HERE / "dataset_template"
RESULTS = (
    WORKSPACE_ROOT / "experiment_results" / "RQ3" / "reruns"
    / "template_validation_result" / "single_run" / "semantic"
)

# Exactly nine clean templates: three original templates, three counterparts
# containing one Expected and one Defect Example, and three behavior-preserving
# two-Worker counterparts used for Worker-call contract tasks.
TEMPLATE_SPECS = (
    ("daily_news_helper", "daily_news_helper.py", "spl_lifehub"),
    (
        "daily_news_helper",
        "daily_news_helper.py",
        "spl_lifehub_with_examples",
    ),
    (
        "daily_news_helper",
        "daily_news_helper.py",
        "spl_lifehub_with_multiple_workers",
    ),
    ("travel_assistant", "travel_assistant.py", "spl_travel_assistant"),
    (
        "travel_assistant",
        "travel_assistant.py",
        "spl_travel_assistant_with_examples",
    ),
    (
        "travel_assistant",
        "travel_assistant.py",
        "spl_travel_assistant_with_multiple_workers",
    ),
    ("fitness_health_advisor", "fitness_health_advisor.py", "spl_original"),
    (
        "fitness_health_advisor",
        "fitness_health_advisor.py",
        "spl_original_with_examples",
    ),
    (
        "fitness_health_advisor",
        "fitness_health_advisor.py",
        "spl_original_with_multiple_workers",
    ),
)

TEMPLATE_COUNT = len(TEMPLATE_SPECS)


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import template module {path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cases() -> list[dict[str, Any]]:
    context_path = (
        TASKS / "task001_persona_referenced_global_variable_does_not_exist.json"
    )
    context_data = json.loads(context_path.read_text(encoding="utf-8"))
    contexts = {
        instance["agent_name"]: instance
        for instance in context_data["instance"]
    }
    modules: dict[str, Any] = {}
    cases: list[dict[str, Any]] = []
    for agent_name, filename, variable_name in TEMPLATE_SPECS:
        if filename not in modules:
            modules[filename] = _load_module(TEMPLATES / filename)
        context = contexts[agent_name]
        cases.append(
            {
                "agent_name": agent_name,
                "template_name": variable_name,
                "cnlp": getattr(modules[filename], variable_name),
                "global_variable": context["global_variable"],
                "api_info": context["api_info"],
                "schema": context["schema"],
            }
        )
    if len(cases) != TEMPLATE_COUNT:
        raise AssertionError(
            f"Expected {TEMPLATE_COUNT} templates, found {len(cases)}."
        )
    return cases


def validate_with_static_analysis() -> list[dict[str, Any]]:
    """Validate all clean templates with TOSEM Parser and SemanticAnalyzer."""

    parser = ParserLike()
    analyzer = SemanticAnalyzer()
    results: list[dict[str, Any]] = []
    for case in _load_cases():
        parse_result = parser.syntax_analysis(cnl_p=case["cnlp"])
        parser_errors = [error.message for error in parse_result.errors]
        semantic_errors: list[dict[str, str]] = []
        if not parser_errors:
            report = analyzer.analyze(
                parse_result.value,
                global_variables=case["global_variable"],
                apis=case["api_info"],
                schema=case["schema"],
            )
            semantic_errors = [
                {
                    "error_code": diagnostic.code,
                    "error_path": diagnostic.path,
                    "error_reason": diagnostic.message,
                }
                for diagnostic in report.diagnostics
            ]
        results.append(
            {
                "agent_name": case["agent_name"],
                "template_name": case["template_name"],
                "parser_errors": parser_errors,
                "semantic_errors": semantic_errors,
                "passed": not parser_errors and not semantic_errors,
            }
        )
    failures = [result for result in results if not result["passed"]]
    if failures:
        raise RuntimeError(
            "Template static validation failed: "
            + json.dumps(failures, ensure_ascii=False)
        )
    return results


def _parse_llm_errors(content: str) -> list[Any]:
    normalized = content.strip()
    if not normalized:
        raise ValueError("LLM validation returned empty message content.")
    if normalized.startswith("```"):
        lines = normalized.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
    parsed = json.loads(normalized)
    if not isinstance(parsed, list):
        raise ValueError("LLM validation result must be a JSON list.")
    return parsed


def validate_with_llm() -> list[dict[str, Any]]:
    """Require GPT-5.6 Sol/high to return [] for every clean template."""

    results: list[dict[str, Any]] = []
    cases = _load_cases()
    for index, case in enumerate(cases, start=1):
        label = f"{case['agent_name']}/{case['template_name']}"
        print(f"LLM template validation [{index}/{len(cases)}]: {label}", flush=True)
        raw_result = check_cnlp_by_llm(
            global_variable=case["global_variable"],
            api_info=case["api_info"],
            type_info=case["schema"],
            cnlp=case["cnlp"],
            clean_validation=True,
        )
        try:
            llm_errors = _parse_llm_errors(raw_result)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Invalid LLM validation response for "
                f"{label}: {exc}; raw_result={raw_result!r}"
            ) from exc
        results.append(
            {
                "agent_name": case["agent_name"],
                "template_name": case["template_name"],
                "model": "gpt-5.6-sol",
                "reasoning_effort": "high",
                "llm_errors": llm_errors,
                "raw_result": raw_result,
                "passed": not llm_errors,
            }
        )
        print(
            f"LLM template validation result: {len(llm_errors)} error(s)",
            flush=True,
        )
    failures = [result for result in results if not result["passed"]]
    if failures:
        raise RuntimeError(
            "Template LLM validation failed: "
            + json.dumps(failures, ensure_ascii=False)
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate all clean RQ3 semantic dataset templates."
    )
    parser.add_argument(
        "--method",
        choices=("static", "llm", "both"),
        default="both",
    )
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "created_at": datetime.now().astimezone().isoformat(),
        "template_count": TEMPLATE_COUNT,
    }
    if args.method in {"static", "both"}:
        payload["static_analysis"] = validate_with_static_analysis()
    if args.method in {"llm", "both"}:
        payload["llm"] = validate_with_llm()

    RESULTS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = RESULTS / f"dataset_template_validation_{timestamp}.json"
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(destination.resolve())


if __name__ == "__main__":
    main()
