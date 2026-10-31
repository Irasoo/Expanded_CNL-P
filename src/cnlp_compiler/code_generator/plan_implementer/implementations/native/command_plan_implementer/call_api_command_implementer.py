from __future__ import annotations

from typing import cast

from .....reference_code_catalog import (
    ReferenceCodeCatalog,
    RegisteredCode,
)
from ......schema import (
    CallAPICommandAnalysisPlan,
    ModelConfig,
    StaticAttributes,
    VariableNode,
    create_empty_static_attributes,
)
from ......utils import (
    LLMclient,
    WebSearchClient,
    create_prompt_section,
)
from ....type_converter import TypeConverter
from ..schema import FunctionImplementation
from .command_generation import (
    CALL_API_COMMAND_RUNTIME_CONTRACT,
    COMMAND_LLM_COMPLETE_CONTRACT,
    COMMAND_VARIABLE_READ_CONTRACT,
    COMMAND_VARIABLE_WRITE_CONTRACT,
    compose_runtime_contract,
    create_model_client,
    json_text,
    request_function_code,
    select_related_variables,
    validate_function_code_response,
)


try:
    from ......prompts.code_generator_plan_implementer_shared import (
        CALL_API_COMMAND_IMPLEMENTATION_PROMPT,
        CALL_API_WEB_IMPLEMENTATION_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_plan_implementer_shared import (
        CALL_API_COMMAND_IMPLEMENTATION_PROMPT,
        CALL_API_WEB_IMPLEMENTATION_PROMPT,
    )


class CallAPICommandPlanImplementer:

    def __init__(self, llm_client: LLMclient | None = None) -> None:
        self._llm_client = llm_client

    def implement(
        self,
        *,
        command_plan: CallAPICommandAnalysisPlan,
        static_attributes: StaticAttributes | None = None,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
        model_config: ModelConfig,
        reference_code_catalog: ReferenceCodeCatalog,
    ) -> FunctionImplementation:
        related_variable_names = list(command_plan["required_variables"])
        if command_plan["written_variable"] is not None:
            related_variable_names.append(command_plan["written_variable"])
        related_variables = select_related_variables(
            related_variable_names,
            variables,
        )
        related_python_schema_code = TypeConverter.render_related_variable_type_code(
            variables=related_variables,
            schema_code_table=python_schema_code_table,
            schema_dependency_table=python_schema_dependency_table,
        )
        if self._requires_web_implementation(command_plan):
            return self._implement_from_web(
                command_plan=command_plan,
                static_attributes=(
                    static_attributes or create_empty_static_attributes()
                ),
                related_variables=related_variables,
                related_python_schema_code=related_python_schema_code,
                model_config=model_config,
            )

        return self._implement_from_reference(
            command_plan=command_plan,
            static_attributes=(static_attributes or create_empty_static_attributes()),
            related_variables=related_variables,
            related_python_schema_code=related_python_schema_code,
            model_config=model_config,
            reference_code_catalog=reference_code_catalog,
        )

    def _implement_from_reference(
        self,
        *,
        command_plan: CallAPICommandAnalysisPlan,
        static_attributes: StaticAttributes,
        related_variables: list[VariableNode],
        related_python_schema_code: str,
        model_config: ModelConfig,
        reference_code_catalog: ReferenceCodeCatalog,
    ) -> FunctionImplementation:
        reference_code = reference_code_catalog.get(
            command_plan["reference_function_name"]
        )
        self._validate_reference_identity(
            command_plan=command_plan,
            reference_code=reference_code,
        )
        function_name = command_plan["command_name"]
        prompt = (
            CALL_API_COMMAND_IMPLEMENTATION_PROMPT.replace(
                "STATIC_ATTRIBUTES_JSON",
                json_text(static_attributes),
            )
            .replace("COMMAND_NAME", function_name)
            .replace(
                "COMMAND_PLAN_JSON",
                json_text(self._command_prompt_data(command_plan)),
            )
            .replace(
                "VARIABLES_JSON",
                json_text(self._variable_prompt_data(related_variables)),
            )
            .replace(
                "RELATED_PYTHON_SCHEMA_CODE",
                related_python_schema_code.strip()
                or "当前 Command 的相关变量未使用声明类型。",
            )
            .replace(
                "REFERENCE_METADATA_JSON",
                json_text(self._reference_metadata(reference_code)),
            )
            .replace(
                "REFERENCE_SOURCE_CODE",
                reference_code.code.strip(),
            )
        )

        required_calls = {
            "state.record_call_api_command_history",
        }
        if command_plan["response"] is not None:
            required_calls.add("state.revise_variable_value")

        forbidden_calls = {"display", "input"}
        if command_plan["response"] is None:
            forbidden_calls.add("state.revise_variable_value")

        return {
            "function_name": function_name,
            "function_code": request_function_code(
                prompt=prompt,
                function_name=function_name,
                llm_client=self._get_llm_client(model_config),
                required_calls=required_calls,
                forbidden_calls=forbidden_calls,
                allowed_written_variables=(
                    {command_plan["written_variable"]}
                    if command_plan["written_variable"] is not None
                    else set()
                ),
            ),
        }

    def _implement_from_web(
        self,
        *,
        command_plan: CallAPICommandAnalysisPlan,
        static_attributes: StaticAttributes,
        related_variables: list[VariableNode],
        related_python_schema_code: str,
        model_config: ModelConfig,
    ) -> FunctionImplementation:
        # TODO(Call API Web Implementation): This route is outside the current
        # paper scope. Keep the existing fallback operational, but do not
        # extend or optimize its prompt and generation workflow for now.
        function_name = command_plan["command_name"]
        prompt = (
            CALL_API_WEB_IMPLEMENTATION_PROMPT.replace(
                "STATIC_ATTRIBUTES_JSON",
                json_text(static_attributes),
            )
            .replace("COMMAND_NAME", function_name)
            .replace(
                "FALLBACK_REASON_JSON",
                json_text(
                    {
                        "reason": (
                            "No reference function was selected during " "planning."
                        )
                    }
                ),
            )
            .replace(
                "COMMAND_PLAN_JSON",
                json_text(command_plan),
            )
            .replace(
                "VARIABLES_JSON",
                json_text(related_variables),
            )
            .replace(
                "RELATED_PYTHON_SCHEMA_CODE",
                related_python_schema_code.strip()
                or "当前 Command 的相关变量未使用声明类型。",
            )
            .replace(
                "RUNTIME_CONTRACT",
                compose_runtime_contract(
                    (
                        COMMAND_VARIABLE_READ_CONTRACT
                        if command_plan["required_variables"]
                        or self._writes_nested_response(command_plan)
                        else ""
                    ),
                    (
                        COMMAND_VARIABLE_WRITE_CONTRACT
                        if command_plan["response"] is not None
                        else ""
                    ),
                    COMMAND_LLM_COMPLETE_CONTRACT,
                    CALL_API_COMMAND_RUNTIME_CONTRACT,
                ),
            )
        )

        required_calls = {
            "state.record_call_api_command_history",
        }
        if command_plan["response"] is not None:
            required_calls.add("state.revise_variable_value")

        forbidden_calls = {"display", "input"}
        if command_plan["response"] is None:
            forbidden_calls.add("state.revise_variable_value")

        web_result = self._get_web_search_client(model_config).search_web(
            [create_prompt_section("user", prompt)],
            search_context_size="high",
            force_search=True,
        )
        return {
            "function_name": function_name,
            "function_code": validate_function_code_response(
                response=web_result["answer"],
                function_name=function_name,
                required_calls=required_calls,
                forbidden_calls=forbidden_calls,
                allowed_written_variables=(
                    {command_plan["written_variable"]}
                    if command_plan["written_variable"] is not None
                    else set()
                ),
            ),
        }

    def _get_llm_client(self, model_config: ModelConfig) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_model_client(model_config)
        return self._llm_client

    def _get_web_search_client(
        self,
        model_config: ModelConfig,
    ) -> WebSearchClient:
        client = self._get_llm_client(model_config)
        if not callable(getattr(client, "search_web", None)):
            raise TypeError("The compiler model client does not provide search_web().")
        return cast(WebSearchClient, client)

    @staticmethod
    def _requires_web_implementation(
        command_plan: CallAPICommandAnalysisPlan,
    ) -> bool:
        return not command_plan["reference_function_name"]

    @staticmethod
    def _writes_nested_response(
        command_plan: CallAPICommandAnalysisPlan,
    ) -> bool:
        response = command_plan["response"]
        return response is not None and "." in response["variable_name"]

    @staticmethod
    def _reference_metadata(
        reference_code: RegisteredCode,
    ) -> dict[str, object]:
        return {
            # The Catalog key and real Python function name are identical.
            "function_name": reference_code.function_name,
            # Describes the registered function's intended capability.
            "description": reference_code.description,
            # Preserves signature order, type, requirement, and meaning.
            "parameters": [
                parameter.to_dict() for parameter in reference_code.parameters
            ],
            # Describes whether and what the reference function returns.
            "return_spec": reference_code.returns.to_dict(),
        }

    @staticmethod
    def _command_prompt_data(
        command_plan: CallAPICommandAnalysisPlan,
    ) -> dict[str, object]:
        """Remove CNL-P Type IR that is rendered separately as Python code."""
        response = command_plan["response"]
        return {
            "command_name": command_plan["command_name"],
            "command_index": command_plan["command_index"],
            "command_type": command_plan["command_type"],
            "api_name": command_plan["api_name"],
            "description": command_plan["description"],
            "arguments": [
                {
                    "parameter_name": argument["parameter_name"],
                    "argument_name": argument["argument_name"],
                    "argument_description": argument["argument_description"],
                }
                for argument in command_plan["arguments"]
            ],
            "response": (
                None
                if response is None
                else {
                    "variable_name": response["variable_name"],
                    "variable_description": response["variable_description"],
                }
            ),
            "reference_function_name": command_plan["reference_function_name"],
            "required_variables": command_plan["required_variables"],
            "written_variable": command_plan["written_variable"],
            "write_operation": command_plan["write_operation"],
        }

    @staticmethod
    def _variable_prompt_data(
        variables: list[VariableNode],
    ) -> list[dict[str, object]]:
        """Keep variable semantics while omitting duplicated Type IR."""
        return [
            {
                "variable_name": variable["variable_name"],
                "description": variable["description"],
            }
            for variable in variables
        ]

    @staticmethod
    def _validate_reference_identity(
        *,
        command_plan: CallAPICommandAnalysisPlan,
        reference_code: RegisteredCode,
    ) -> None:
        if reference_code.function_name != command_plan["reference_function_name"]:
            raise ValueError(
                "Catalog returned a reference function different from the "
                "one selected by the Plan."
            )
