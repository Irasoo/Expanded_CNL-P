from __future__ import annotations

import json
from typing import Any, TypedDict

from ...reference_code_catalog import (
    ReferenceCodeCatalog,
    ReferenceCodeSearchQuery,
)
from ....schema import (
    CNLPDataType,
    CNLPTypeIR,
    CallAPICommandAnalysisPlan,
    CallAPICommandNode,
)
from ....utils import (
    LLMclient,
    PromptSection,
    create_llm_client,
    create_prompt_section,
    extract_single_json_from_text,
)


try:
    from ....prompts.code_generator_implementation_planner_command_analyzer import (
        CALL_API_DESCRIPTION_ANALYSIS_PROMPT,
    )
except ImportError:  # Supports legacy top-level package imports.
    from prompts.code_generator_implementation_planner_command_analyzer import (
        CALL_API_DESCRIPTION_ANALYSIS_PROMPT,
    )


class CallAPIDescriptionResult(TypedDict):
    """One contextual description returned by the batch LLM analysis."""

    analysis_index: int
    command_name: str
    description: str


class CallAPICommandAnalyzer:
    """Summarize Call API Commands and select reference functions."""

    def __init__(
        self,
        llm_client: LLMclient | None = None,
        *,
        reference_code_catalog: ReferenceCodeCatalog | None = None,
    ) -> None:
        self._llm_client = llm_client
        self.reference_code_catalog = (
            reference_code_catalog
            if reference_code_catalog is not None
            else ReferenceCodeCatalog()
        )

    def analyze_all(
        self,
        *,
        cnlp_script: str,
        commands: list[CallAPICommandNode],
        cnlp_types: list[CNLPTypeIR] | None = None,
    ) -> list[CallAPICommandAnalysisPlan]:
        if not commands:
            return []

        print(
            "[Compiler][Planning][Call API] Summarizing descriptions for "
            f"{len(commands)} Command(s): started.",
            flush=True,
        )
        descriptions = self._summarize_descriptions(
            cnlp_script=cnlp_script,
            commands=commands,
        )
        print(
            "[Compiler][Planning][Call API] Description summary completed.",
            flush=True,
        )

        type_contents = {
            type_ir["type_name"]: type_ir["type_content"]
            for type_ir in (cnlp_types or [])
        }
        plans: list[CallAPICommandAnalysisPlan] = []
        for command_index, command in enumerate(commands, start=1):
            command_name = command["command_name"]
            print(
                "[Compiler][Planning][Call API] "
                f"{command_index}/{len(commands)} {command_name} "
                f"(api={command['api_name']}): started.",
                flush=True,
            )
            plans.append(
                self._build_plan(
                    command=command,
                    description=descriptions[command_index - 1],
                    type_contents=type_contents,
                )
            )
            print(
                "[Compiler][Planning][Call API] "
                f"{command_index}/{len(commands)} {command_name}: completed.",
                flush=True,
            )
        return plans

    def build_search_query(
        self,
        *,
        command: CallAPICommandNode,
        description: str,
        type_contents: dict[str, CNLPDataType] | None = None,
    ) -> ReferenceCodeSearchQuery:
        """Build one source-free query using only simplified type families."""
        response = command["response"]
        declared_types = type_contents or {}
        return {
            "requested_api_name": command["api_name"],
            "task_description": description,
            "arguments": [
                {
                    "parameter_name": argument["parameter_name"],
                    "argument_variable_name": argument["argument_name"],
                    "argument_description": argument["argument_description"],
                    "argument_type": self._convert_search_type(
                        argument["argument_type"],
                        type_contents=declared_types,
                    ),
                }
                for argument in command["arguments"]
            ],
            "expected_return": (
                None
                if response is None
                else {
                    "variable_name": response["variable_name"],
                    "return_description": response["variable_description"],
                    "return_type": self._convert_search_type(
                        response["variable_type"],
                        type_contents=declared_types,
                    ),
                }
            ),
        }

    def _build_plan(
        self,
        *,
        command: CallAPICommandNode,
        description: str,
        type_contents: dict[str, CNLPDataType],
    ) -> CallAPICommandAnalysisPlan:
        print(
            "[Compiler][Planning][Call API] "
            f"{command['command_name']}: searching Reference Code Catalog.",
            flush=True,
        )
        reference_document = self.reference_code_catalog.search(
            self.build_search_query(
                command=command,
                description=description,
                type_contents=type_contents,
            )
        )
        if reference_document is None:
            print(
                "[Compiler][Planning][Call API] "
                f"{command['command_name']}: no registered reference "
                "function selected.",
                flush=True,
            )
            reference_function_name = None
        else:
            reference_function_name = reference_document["function_name"]
            print(
                "[Compiler][Planning][Call API] "
                f"{command['command_name']}: matched "
                f"{reference_function_name}.",
                flush=True,
            )

        return {
            "command_name": command["command_name"],
            "command_index": command["command_index"],
            "command_type": "call_api",
            "api_name": command["api_name"],
            "arguments": command["arguments"],
            "response": command["response"],
            "description": description,
            "reference_function_name": reference_function_name,
            "required_variables": command["required_variables"],
            "written_variable": command["written_variable"],
            "write_operation": command["write_operation"],
        }

    def _summarize_descriptions(
        self,
        *,
        cnlp_script: str,
        commands: list[CallAPICommandNode],
    ) -> list[str]:
        response = self._get_llm_client().complete(
            self._build_description_prompt(
                cnlp_script=cnlp_script,
                commands=commands,
            )
        )
        return self._parse_descriptions(
            response=response,
            expected_commands=commands,
        )

    @staticmethod
    def _build_description_prompt(
        *,
        cnlp_script: str,
        commands: list[CallAPICommandNode],
    ) -> list[PromptSection]:
        targets = [
            {
                "analysis_index": index,
                "command_name": command["command_name"],
                "command_index": command["command_index"],
                "api_name": command["api_name"],
            }
            for index, command in enumerate(commands, start=1)
        ]
        content = CALL_API_DESCRIPTION_ANALYSIS_PROMPT.replace(
            "{{CNLP_SCRIPT}}", cnlp_script
        ).replace(
            "{{TARGET_COMMANDS_JSON}}",
            json.dumps(targets, ensure_ascii=False, indent=2),
        )
        return [create_prompt_section("user", content)]

    @classmethod
    def _convert_search_type(
        cls,
        data_type: CNLPDataType,
        *,
        type_contents: dict[str, CNLPDataType],
        resolving: set[str] | None = None,
    ) -> str:
        """Reduce a complete CNL-P type to one matching type family."""
        if isinstance(data_type, list):
            return "dict"
        if not isinstance(data_type, dict):
            raise ValueError(f"Unsupported CNL-P data type: {data_type!r}.")
        if "simple_type" in data_type:
            simple_types = {
                "text": "str",
                "number": "number",
                "boolean": "bool",
            }
            simple_type = data_type["simple_type"]
            try:
                return simple_types[simple_type.lower()]
            except (AttributeError, KeyError) as exc:
                raise ValueError(
                    f"Unsupported CNL-P simple type: {simple_type!r}."
                ) from exc
        if "declared_type_name" in data_type:
            declared_name = data_type["declared_type_name"]
            current_resolving = set(resolving or ())
            if declared_name in current_resolving:
                return "unknown"
            declared_content = type_contents.get(declared_name)
            if declared_content is None:
                return "unknown"
            current_resolving.add(declared_name)
            return cls._convert_search_type(
                declared_content,
                type_contents=type_contents,
                resolving=current_resolving,
            )
        if "enum_elements" in data_type:
            return "str"
        if "type_of_list_element" in data_type:
            return "list"
        raise ValueError(f"Unknown CNL-P data type: {data_type!r}.")

    @classmethod
    def _parse_descriptions(
        cls,
        *,
        response: str,
        expected_commands: list[CallAPICommandNode],
    ) -> list[str]:
        result = cls._parse_json_object(
            response=response,
            response_name="Call API description",
        )
        if set(result) != {"call_api_descriptions"}:
            raise ValueError(
                "The LLM response must contain only " "'call_api_descriptions'."
            )

        entries = result["call_api_descriptions"]
        if not isinstance(entries, list):
            raise ValueError("'call_api_descriptions' must be a JSON array.")

        if len(entries) != len(expected_commands):
            raise ValueError(
                "The Call API description count does not match the "
                "requested Command count."
            )

        descriptions: list[str] = []
        for expected_index, (expected_command, entry) in enumerate(
            zip(expected_commands, entries, strict=True),
            start=1,
        ):
            if not isinstance(entry, dict) or set(entry) != {
                "analysis_index",
                "command_name",
                "description",
            }:
                raise ValueError(
                    "Each Call API description must contain exactly "
                    "'analysis_index', 'command_name', and 'description'."
                )

            analysis_index = entry["analysis_index"]
            command_name = entry["command_name"]
            description = entry["description"]
            if analysis_index != expected_index:
                raise ValueError(
                    "Call API descriptions must preserve input order: "
                    f"expected analysis_index {expected_index}, received "
                    f"{analysis_index!r}."
                )
            if command_name != expected_command["command_name"]:
                raise ValueError(
                    "Call API descriptions must preserve input Command "
                    f"names: expected {expected_command['command_name']!r}, "
                    f"received {command_name!r}."
                )
            if not isinstance(command_name, str) or not command_name:
                raise ValueError(
                    "Each Call API description must contain a non-empty "
                    "string command_name."
                )
            if not isinstance(description, str) or not description.strip():
                raise ValueError(
                    f"Description for {command_name!r} must be a non-empty " "string."
                )
            descriptions.append(description.strip())

        return descriptions

    @staticmethod
    def _parse_json_object(
        *,
        response: str,
        response_name: str,
    ) -> dict[str, Any]:
        if not isinstance(response, str):
            raise ValueError(f"{response_name} response must be a string.")
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            try:
                result = extract_single_json_from_text(response)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{response_name} response contains invalid JSON: " f"{response!r}"
                ) from exc
        if not isinstance(result, dict):
            raise ValueError(f"{response_name} response must be an object.")
        return result

    def _get_llm_client(self) -> LLMclient:
        if self._llm_client is None:
            self._llm_client = create_llm_client()
        return self._llm_client
