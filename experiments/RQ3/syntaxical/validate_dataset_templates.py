from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from experiments._bootstrap import configure_source_paths
configure_source_paths()

from cnlp_compiler.parser import ParserLike
from experiments.RQ3.syntaxical.linting_agent_based_on_llms.agent_linting import (
    syntax_issue_linting_agent,
)
from experiments.RQ3.syntaxical.linting_agent_based_on_llms.llm_client import (
    LLM_MODEL,
    LLM_REASONING_EFFORT,
)
from experiments.RQ3.syntaxical.task.benchmark_case import diet_advisor, travel_assistant


RESULTS = (
    WORKSPACE_ROOT / "experiment_results" / "RQ3" / "reruns"
    / "template_validation_result" / "single_run" / "syntax"
)
TEMPLATES = (
    ("diet_advisor", diet_advisor),
    ("travel_assistant", travel_assistant),
)


def validate_with_parser() -> list[dict[str, Any]]:
    parser = ParserLike()
    results: list[dict[str, Any]] = []
    for template_name, cnlp in TEMPLATES:
        parse_result = parser.syntax_analysis(cnl_p=cnlp)
        errors = [
            {
                "error_type": error.error_type,
                "start_line": error.start_line,
                "end_line": error.end_line,
                "error_message": error.message,
            }
            for error in parse_result.errors
        ]
        results.append(
            {
                "template_name": template_name,
                "parser_errors": errors,
                "passed": not errors,
            }
        )
    failures = [result for result in results if not result["passed"]]
    if failures:
        raise RuntimeError(
            "Syntax template Parser validation failed: "
            + json.dumps(failures, ensure_ascii=False)
        )
    return results


def _parse_llm_errors(content: str) -> list[Any]:
    normalized = content.strip()
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
    results: list[dict[str, Any]] = []
    for index, (template_name, cnlp) in enumerate(TEMPLATES, start=1):
        print(
            f"LLM Syntax template validation [{index}/{len(TEMPLATES)}]: "
            f"{template_name}",
            flush=True,
        )
        raw_result = syntax_issue_linting_agent(
            cnlp,
            clean_validation=True,
        )
        try:
            errors = _parse_llm_errors(raw_result)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Invalid LLM response for {template_name}: {raw_result!r}"
            ) from exc
        results.append(
            {
                "template_name": template_name,
                "model": LLM_MODEL,
                "reasoning_effort": LLM_REASONING_EFFORT,
                "llm_errors": errors,
                "raw_result": raw_result,
                "passed": not errors,
            }
        )
        print(f"LLM result: {len(errors)} error(s)", flush=True)
    failures = [result for result in results if not result["passed"]]
    if failures:
        raise RuntimeError(
            "Syntax template LLM validation failed: "
            + json.dumps(failures, ensure_ascii=False)
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the two clean RQ3 Syntax templates.",
    )
    parser.add_argument(
        "--method",
        choices=("parser", "llm", "both"),
        default="both",
    )
    arguments = parser.parse_args()
    payload: dict[str, Any] = {
        "created_at": datetime.now().astimezone().isoformat(),
        "template_count": len(TEMPLATES),
    }
    if arguments.method in {"parser", "both"}:
        payload["parser"] = validate_with_parser()
    if arguments.method in {"llm", "both"}:
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
