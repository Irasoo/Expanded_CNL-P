"""Batch implementation planning for CNL-P judgement conditions."""

from __future__ import annotations

import json
from typing import Any

from ....schema import (
    ConditionNode,
    PredicateAnalysisPlan,
    VariableNode,
)
from ....utils import (
    LLMclient,
    PromptSection,
    create_llm_client,
    create_prompt_section,
)
from ...plan_implementer.type_converter import TypeConverter
from ..analysis_support import parse_json_object_response, select_variables


try:
    from ....prompts.code_generator_implementation_planner_predicate_analyzer import (
        PREDICATE_ANALYSIS_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_implementation_planner_predicate_analyzer import (
        PREDICATE_ANALYSIS_PROMPT,
    )


class PredicateAnalyzer:

    def __init__(self, llm_client: LLMclient | None = None):
        self._llm_client = llm_client

    def analyze_all(
        self,
        *,
        conditions: list[ConditionNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
    ) -> list[PredicateAnalysisPlan]:
        """Analyze every supplied judgement condition in one model request."""
        if not conditions:
            return []

        response = self._get_llm_client().complete(
            self._build_prompt(
                conditions=conditions,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(python_schema_dependency_table or {}),
            )
        )
        decisions = self._parse_analyses(
            response=response,
            expected_condition_paths=[
                condition["condition_path"] for condition in conditions
            ],
        )

        return [
            {
                "predicate_name": condition["predicate_name"],
                "predicate_index": condition["predicate_index"],
                "owner_name": condition["owner_name"],
                "condition_kind": condition["condition_kind"],
                "condition_path": condition["condition_path"],
                "description": condition["description"],
                "required_variables": condition["required_variables"],
                "llm_based_processing": decision["llm_based_processing"],
            }
            for condition, decision in zip(
                conditions,
                decisions,
                strict=True,
            )
        ]

    def analyze(
        self,
        *,
        conditions: list[ConditionNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
    ) -> list[PredicateAnalysisPlan]:
        """Compatibility wrapper for an isolated condition collection."""
        return self.analyze_all(
            conditions=conditions,
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=python_schema_dependency_table,
        )

    def _build_prompt(
        self,
        *,
        conditions: list[ConditionNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
    ) -> list[PromptSection]:
        related_variables = select_variables(
            [
                variable_name
                for condition in conditions
                for variable_name in condition["required_variables"]
            ],
            variables,
        )
        related_python_schema_code = (
            TypeConverter.render_related_variable_type_code(
                variables=related_variables,
                schema_code_table=python_schema_code_table,
                schema_dependency_table=(python_schema_dependency_table or {}),
            )
            if python_schema_code_table is not None
            else ""
        )
        content = (
            PREDICATE_ANALYSIS_PROMPT.replace(
                "{{PREDICATES_JSON}}",
                json.dumps(
                    [
                        self._condition_prompt_data(condition)
                        for condition in conditions
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{RELATED_VARIABLES_JSON}}",
                json.dumps(
                    self._variable_prompt_data(related_variables),
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            .replace(
                "{{RELATED_PYTHON_SCHEMA_CODE}}",
                related_python_schema_code.strip() or "None",
            )
        )
        return [create_prompt_section("user", content)]

    @staticmethod
    def _condition_prompt_data(
        condition: ConditionNode,
    ) -> dict[str, object]:
        return {
            "condition_path": condition["condition_path"],
            "condition_kind": condition["condition_kind"],
            "description": condition["description"],
            "required_variables": condition["required_variables"],
        }

    @staticmethod
    def _variable_prompt_data(
        variables: list[VariableNode],
    ) -> list[dict[str, object]]:
        return [
            {
                "variable_name": variable["variable_name"],
                "description": variable["description"],
            }
            for variable in variables
        ]

    @staticmethod
    def _parse_analyses(
        *,
        response: str,
        expected_condition_paths: list[list[str]],
    ) -> list[dict[str, Any]]:
        result = parse_json_object_response(response)
        if set(result) != {"predicate_analyses"}:
            raise ValueError(
                "The judgement-condition analysis must contain exactly "
                "'predicate_analyses'."
            )
        analyses = result["predicate_analyses"]
        if not isinstance(analyses, list):
            raise ValueError("'predicate_analyses' must be a JSON array.")
        if len(analyses) != len(expected_condition_paths):
            raise ValueError(
                "The judgement-condition analysis count does not match "
                "the input condition count."
            )

        parsed: list[dict[str, Any]] = []
        for expected_path, analysis in zip(
            expected_condition_paths,
            analyses,
            strict=True,
        ):
            if not isinstance(analysis, dict) or set(analysis) != {
                "condition_path",
                "llm_based_processing",
            }:
                raise ValueError(
                    "Each judgement-condition analysis must contain "
                    "exactly 'condition_path' and "
                    "'llm_based_processing'."
                )
            if analysis["condition_path"] != expected_path:
                raise ValueError(
                    "Judgement-condition analyses must preserve input "
                    f"order and paths: expected {expected_path!r}, "
                    f"received {analysis['condition_path']!r}."
                )
            if type(analysis["llm_based_processing"]) is not bool:
                raise ValueError("'llm_based_processing' must be a boolean.")
            parsed.append(analysis)
        return parsed

    def _get_llm_client(self) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_llm_client()
        return self._llm_client
