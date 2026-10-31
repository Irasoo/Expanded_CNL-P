from __future__ import annotations

from ......schema import (
    GeneralCommandAnalysisPlan,
    ModelConfig,
    StaticAttributes,
    VariableNode,
    create_empty_static_attributes,
)
from ......utils import LLMclient
from ....type_converter import TypeConverter
from ..schema import FunctionImplementation
from .command_generation import (
    create_model_client,
    json_text,
    request_function_code,
    select_related_variables,
)


try:
    from ......prompts.code_generator_plan_implementer_shared import (
        GENERAL_COMMAND_LLM_BASED_IMPLEMENTATION_PROMPT,
        GENERAL_COMMAND_TRADITIONAL_IMPLEMENTATION_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_shared import (
        GENERAL_COMMAND_LLM_BASED_IMPLEMENTATION_PROMPT,
        GENERAL_COMMAND_TRADITIONAL_IMPLEMENTATION_PROMPT,
    )


class GeneralCommandPlanImplementer:

    def __init__(self, llm_client: LLMclient | None = None) -> None:
        self._llm_client = llm_client

    def implement(
        self,
        *,
        command_plan: GeneralCommandAnalysisPlan,
        static_attributes: StaticAttributes | None = None,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
        model_config: ModelConfig,
    ) -> FunctionImplementation:
        self._validate_plan(command_plan)
        related_variables = select_related_variables(
            (command_plan["required_variables"] + [command_plan["written_variable"]]),
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
        function_name = command_plan["command_name"]
        prompt_template = (
            GENERAL_COMMAND_LLM_BASED_IMPLEMENTATION_PROMPT
            if command_plan["llm_based_processing"]
            else GENERAL_COMMAND_TRADITIONAL_IMPLEMENTATION_PROMPT
        )
        prompt = (
            prompt_template.replace(
                "STATIC_ATTRIBUTES_JSON",
                json_text(static_attributes or create_empty_static_attributes()),
            )
            .replace(
                "GENERAL_COMMAND_JSON",
                json_text(self._command_prompt_data(command_plan)),
            )
            .replace(
                "RELATED_VARIABLES_JSON",
                json_text(self._variable_prompt_data(related_variables)),
            )
            .replace(
                "RELATED_PYTHON_SCHEMA_CODE",
                related_python_schema_code.strip()
                or "The variables related to this Command use no declared types.",
            )
            .replace("COMMAND_NAME", function_name)
        )

        return {
            "function_name": function_name,
            "function_code": request_function_code(
                prompt=prompt,
                function_name=function_name,
                llm_client=self._get_llm_client(model_config),
                required_calls={
                    "state.revise_variable_value",
                    "state.record_general_command_history",
                }
                | (
                    {
                        "llm_client.complete",
                    }
                    if command_plan["llm_based_processing"]
                    else set()
                ),
                forbidden_calls={
                    "display",
                    "input",
                    "llm_client.complete_call_api",
                }
                | (
                    set()
                    if command_plan["llm_based_processing"]
                    else {
                        "llm_client.complete",
                    }
                ),
                allowed_written_variables={
                    command_plan["written_variable"]
                },
            ),
        }

    def _get_llm_client(self, model_config: ModelConfig) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_model_client(model_config)
        return self._llm_client

    @staticmethod
    def _command_prompt_data(
        command_plan: GeneralCommandAnalysisPlan,
    ) -> dict[str, object]:
        return {
            "command_name": command_plan["command_name"],
            "description": command_plan["description"],
            "required_variables": command_plan["required_variables"],
            "written_variable": command_plan["written_variable"],
            "write_operation": command_plan["write_operation"],
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
    def _validate_plan(
        command_plan: GeneralCommandAnalysisPlan,
    ) -> None:
        if not command_plan["written_variable"]:
            raise ValueError("General Command must write exactly one variable.")
        if command_plan["write_operation"] is None:
            raise ValueError("General Command requires SET or APPEND.")
