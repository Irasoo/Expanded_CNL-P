from __future__ import annotations

from ......schema import (
    InputCommandAnalysisPlan,
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
        INPUT_COMMAND_IMPLEMENTATION_BASE_PROMPT,
        INPUT_COMMAND_INTERACTION_CONTRACT,
        INPUT_COMMAND_LLM_COMPLETE_CONTRACT,
        INPUT_COMMAND_RAW_DIRECT_PROMPT,
        INPUT_COMMAND_RAW_LLM_BASED_PROMPT,
        INPUT_COMMAND_RAW_TRADITIONAL_PROMPT,
        INPUT_COMMAND_REQUEST_DYNAMIC_LLM_BASED_PROMPT,
        INPUT_COMMAND_REQUEST_DYNAMIC_TRADITIONAL_PROMPT,
        INPUT_COMMAND_REQUEST_STATIC_PROMPT,
        INPUT_COMMAND_RUNTIME_BASE_CONTRACT,
        INPUT_COMMAND_VARIABLE_READ_CONTRACT,
        INPUT_COMMAND_VARIABLE_WRITE_CONTRACT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_shared import (
        INPUT_COMMAND_IMPLEMENTATION_BASE_PROMPT,
        INPUT_COMMAND_INTERACTION_CONTRACT,
        INPUT_COMMAND_LLM_COMPLETE_CONTRACT,
        INPUT_COMMAND_RAW_DIRECT_PROMPT,
        INPUT_COMMAND_RAW_LLM_BASED_PROMPT,
        INPUT_COMMAND_RAW_TRADITIONAL_PROMPT,
        INPUT_COMMAND_REQUEST_DYNAMIC_LLM_BASED_PROMPT,
        INPUT_COMMAND_REQUEST_DYNAMIC_TRADITIONAL_PROMPT,
        INPUT_COMMAND_REQUEST_STATIC_PROMPT,
        INPUT_COMMAND_RUNTIME_BASE_CONTRACT,
        INPUT_COMMAND_VARIABLE_READ_CONTRACT,
        INPUT_COMMAND_VARIABLE_WRITE_CONTRACT,
    )


class InputCommandPlanImplementer:

    def __init__(self, llm_client: LLMclient | None = None) -> None:
        self._llm_client = llm_client

    def implement(
        self,
        *,
        command_plan: InputCommandAnalysisPlan,
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
        prompt = (
            INPUT_COMMAND_IMPLEMENTATION_BASE_PROMPT.replace(
                "STATIC_ATTRIBUTES_JSON",
                json_text(static_attributes or create_empty_static_attributes()),
            )
            .replace(
                "INPUT_COMMAND_JSON",
                json_text(self._command_prompt_data(command_plan)),
            )
            .replace(
                "RELATED_VARIABLES_JSON",
                json_text(self._variable_prompt_data(related_variables)),
            )
            .replace(
                "RELATED_PYTHON_SCHEMA_CODE",
                related_python_schema_code.strip() or "None",
            )
            .replace(
                "RUNTIME_CONTRACT",
                self._runtime_contract(command_plan),
            )
            .replace(
                "REQUEST_GENERATION_IMPLEMENTATION",
                self._request_generation_prompt(command_plan),
            )
            .replace(
                "RAW_INPUT_PROCESSING_IMPLEMENTATION",
                self._raw_input_processing_prompt(command_plan),
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
                    "input",
                    "state.record_input_command_history",
                    "state.revise_variable_value",
                }
                | (
                    {"llm_client.complete"}
                    if self._uses_runtime_llm(command_plan)
                    else set()
                ),
                forbidden_calls=(
                    set()
                    if self._uses_runtime_llm(command_plan)
                    else {"llm_client.complete"}
                )
                | {"llm_client.complete_call_api"},
                minimum_call_counts={
                    "llm_client.complete": (
                        int(command_plan["request_generation"]["llm_based"])
                        + int(command_plan["raw_input_processing"]["llm_based"])
                    )
                },
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
    def _validate_plan(
        command_plan: InputCommandAnalysisPlan,
    ) -> None:
        if not command_plan["written_variable"]:
            raise ValueError("Input Command must write exactly one variable.")
        if command_plan["write_operation"] is None:
            raise ValueError("Input Command requires SET or APPEND.")

    @staticmethod
    def _uses_runtime_llm(
        command_plan: InputCommandAnalysisPlan,
    ) -> bool:
        return (
            command_plan["request_generation"]["llm_based"]
            or command_plan["raw_input_processing"]["llm_based"]
        )

    @classmethod
    def _runtime_contract(
        cls,
        command_plan: InputCommandAnalysisPlan,
    ) -> str:
        runtime_parts = [
            INPUT_COMMAND_RUNTIME_BASE_CONTRACT,
            INPUT_COMMAND_INTERACTION_CONTRACT,
            INPUT_COMMAND_VARIABLE_WRITE_CONTRACT,
        ]
        if command_plan["request_generation"]["dynamic"]:
            runtime_parts.append(INPUT_COMMAND_VARIABLE_READ_CONTRACT)
        if cls._uses_runtime_llm(command_plan):
            runtime_parts.append(INPUT_COMMAND_LLM_COMPLETE_CONTRACT)
        return "\n\n".join(runtime_parts)

    @staticmethod
    def _request_generation_prompt(
        command_plan: InputCommandAnalysisPlan,
    ) -> str:
        request_plan = command_plan["request_generation"]
        if not request_plan["dynamic"]:
            return INPUT_COMMAND_REQUEST_STATIC_PROMPT
        if request_plan["llm_based"]:
            return INPUT_COMMAND_REQUEST_DYNAMIC_LLM_BASED_PROMPT
        return INPUT_COMMAND_REQUEST_DYNAMIC_TRADITIONAL_PROMPT

    @staticmethod
    def _raw_input_processing_prompt(
        command_plan: InputCommandAnalysisPlan,
    ) -> str:
        processing_plan = command_plan["raw_input_processing"]
        if not processing_plan["needed"]:
            return INPUT_COMMAND_RAW_DIRECT_PROMPT
        if processing_plan["llm_based"]:
            return INPUT_COMMAND_RAW_LLM_BASED_PROMPT
        return INPUT_COMMAND_RAW_TRADITIONAL_PROMPT

    @staticmethod
    def _command_prompt_data(
        command_plan: InputCommandAnalysisPlan,
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
