"""Batch implementation planning for General Commands."""

from __future__ import annotations

import json
from typing import Any

from ....schema import (
    CommandNode,
    GeneralCommandAnalysisPlan,
    VariableNode,
)
from ....utils import (
    LLMclient,
    PromptSection,
    create_llm_client,
    create_prompt_section,
)
from ...plan_implementer.type_converter import TypeConverter
from ..analysis_support import (
    parse_json_object_response,
    select_variables,
)


try:
    from ....prompts.code_generator_implementation_planner_command_analyzer import (
        GENERAL_COMMAND_ANALYSIS_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_implementation_planner_command_analyzer import (
        GENERAL_COMMAND_ANALYSIS_PROMPT,
    )


class GeneralCommandAnalyzer:

    def __init__(self, llm_client: LLMclient | None = None):
        self._llm_client = llm_client

    def analyze_all(
        self,
        *,
        commands: list[CommandNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
    ) -> list[GeneralCommandAnalysisPlan]:
        """Analyze every supplied General Command in one model request."""
        if not commands:
            return []

        response = self._get_llm_client().complete(
            self._build_prompt(
                commands=commands,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(python_schema_dependency_table or {}),
            )
        )
        decisions = self._parse_analyses(
            response=response,
            expected_command_names=[command["command_name"] for command in commands],
        )

        return [
            {
                "command_name": command["command_name"],
                "command_index": command["command_index"],
                "command_type": "general_command",
                "description": command["description"],
                "required_variables": command["required_variables"],
                "llm_based_processing": decision["llm_based_processing"],
                "written_variable": command["written_variable"],
                "write_operation": command["write_operation"],
            }
            for command, decision in zip(commands, decisions, strict=True)
        ]

    def analyze(
        self,
        *,
        command: CommandNode,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
    ) -> GeneralCommandAnalysisPlan:
        """Compatibility wrapper for isolated single-Command analysis."""
        return self.analyze_all(
            commands=[command],
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=(python_schema_dependency_table),
        )[0]

    def _build_prompt(
        self,
        *,
        commands: list[CommandNode],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
    ) -> list[PromptSection]:
        related_variable_names = [
            variable_name
            for command in commands
            for variable_name in (
                list(command["required_variables"])
                + (
                    [command["written_variable"]]
                    if command["written_variable"] is not None
                    else []
                )
            )
        ]
        related_variables = select_variables(
            related_variable_names,
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
            GENERAL_COMMAND_ANALYSIS_PROMPT.replace(
                "{{GENERAL_COMMANDS_JSON}}",
                json.dumps(
                    [self._command_prompt_data(command) for command in commands],
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
    def _command_prompt_data(command: CommandNode) -> dict[str, object]:
        return {
            "command_name": command["command_name"],
            "description": command["description"],
            "required_variables": command["required_variables"],
            "written_variable": command["written_variable"],
            "write_operation": command["write_operation"],
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
        expected_command_names: list[str],
    ) -> list[dict[str, Any]]:
        result = parse_json_object_response(response)
        if set(result) != {"general_command_analyses"}:
            raise ValueError(
                "The General Command analysis must contain exactly "
                "'general_command_analyses'."
            )
        analyses = result["general_command_analyses"]
        if not isinstance(analyses, list):
            raise ValueError("'general_command_analyses' must be a JSON array.")
        if len(analyses) != len(expected_command_names):
            raise ValueError(
                "The General Command analysis count does not match the "
                "input Command count."
            )

        parsed: list[dict[str, Any]] = []
        for expected_name, analysis in zip(
            expected_command_names,
            analyses,
            strict=True,
        ):
            if not isinstance(analysis, dict) or set(analysis) != {
                "command_name",
                "llm_based_processing",
            }:
                raise ValueError(
                    "Each General Command analysis must contain exactly "
                    "'command_name' and 'llm_based_processing'."
                )
            if analysis["command_name"] != expected_name:
                raise ValueError(
                    "General Command analyses must preserve input order and "
                    f"names: expected {expected_name!r}, received "
                    f"{analysis['command_name']!r}."
                )
            if type(analysis["llm_based_processing"]) is not bool:
                raise ValueError("'llm_based_processing' must be a boolean.")
            parsed.append(analysis)
        return parsed

    def _get_llm_client(self) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_llm_client()
        return self._llm_client
