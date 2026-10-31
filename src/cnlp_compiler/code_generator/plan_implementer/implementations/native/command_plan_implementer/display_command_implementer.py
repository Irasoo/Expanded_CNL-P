from __future__ import annotations

from ......schema import (
    DisplayCommandAnalysisPlan,
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
        DISPLAY_COMMAND_LLM_BASED_IMPLEMENTATION_PROMPT,
        DISPLAY_COMMAND_TRADITIONAL_IMPLEMENTATION_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_shared import (
        DISPLAY_COMMAND_LLM_BASED_IMPLEMENTATION_PROMPT,
        DISPLAY_COMMAND_TRADITIONAL_IMPLEMENTATION_PROMPT,
    )


class DisplayCommandPlanImplementer:

    def __init__(self, llm_client: LLMclient | None = None) -> None:
        self._llm_client = llm_client

    def implement(
        self,
        *,
        command_plan: DisplayCommandAnalysisPlan,
        static_attributes: StaticAttributes | None = None,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
        model_config: ModelConfig,
    ) -> FunctionImplementation:
        self._validate_plan(command_plan)
        related_variables = select_related_variables(
            command_plan["required_variables"],
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
            DISPLAY_COMMAND_LLM_BASED_IMPLEMENTATION_PROMPT
            if command_plan["display_content_generation"]["llm_based"]
            else DISPLAY_COMMAND_TRADITIONAL_IMPLEMENTATION_PROMPT
        )
        prompt = (
            prompt_template.replace(
                "STATIC_ATTRIBUTES_JSON",
                json_text(static_attributes or create_empty_static_attributes()),
            )
            .replace(
                "DISPLAY_COMMAND_JSON",
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
                    "display",
                    "state.record_display_command_history",
                }
                | (
                    {"llm_client.complete"}
                    if command_plan["display_content_generation"]["llm_based"]
                    else set()
                ),
                forbidden_calls={
                    "input",
                    "llm_client.complete_call_api",
                    "state.revise_variable_value",
                }
                | (
                    set()
                    if command_plan["display_content_generation"]["llm_based"]
                    else {"llm_client.complete"}
                ),
                allowed_written_variables=set(),
            ),
        }

    def _get_llm_client(self, model_config: ModelConfig) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_model_client(model_config)
        return self._llm_client

    @staticmethod
    def _command_prompt_data(
        command_plan: DisplayCommandAnalysisPlan,
    ) -> dict[str, object]:
        return {
            "command_name": command_plan["command_name"],
            "description": command_plan["description"],
            "required_variables": command_plan["required_variables"],
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
        command_plan: DisplayCommandAnalysisPlan,
    ) -> None:
        if command_plan["written_variable"] is not None:
            raise ValueError("Display Command must not write variables.")
        if command_plan["write_operation"] is not None:
            raise ValueError("Display Command must not define a write operation.")
