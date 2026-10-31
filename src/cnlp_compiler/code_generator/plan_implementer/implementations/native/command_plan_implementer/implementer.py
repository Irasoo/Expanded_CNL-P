from __future__ import annotations

from .....reference_code_catalog import ReferenceCodeCatalog
from ......schema import (
    CommandAnalysisPlan,
    ModelConfig,
    StaticAttributes,
    VariableNode,
    create_empty_static_attributes,
)
from ..schema import CommandImplementationResult, FunctionImplementation
from .call_api_command_implementer import CallAPICommandPlanImplementer
from .call_worker_command_implementer import CallWorkerCommandPlanImplementer
from .display_command_implementer import DisplayCommandPlanImplementer
from .general_command_implementer import GeneralCommandPlanImplementer
from .input_command_implementer import InputCommandPlanImplementer


COMMANDS_MODULE_HEADER = """\
from .model import AgentState
from .utils import OpenAIClient, display, input
"""


class CommandPlanImplementer:

    def __init__(
        self,
        *,
        input_command_implementer: (
            InputCommandPlanImplementer | None
        ) = None,
        general_command_implementer: (
            GeneralCommandPlanImplementer | None
        ) = None,
        display_command_implementer: (
            DisplayCommandPlanImplementer | None
        ) = None,
        call_api_command_implementer: (
            CallAPICommandPlanImplementer | None
        ) = None,
        call_worker_command_implementer: (
            CallWorkerCommandPlanImplementer | None
        ) = None,
    ) -> None:
        self.input_command_implementer = (
            input_command_implementer
            or InputCommandPlanImplementer()
        )
        self.general_command_implementer = (
            general_command_implementer
            or GeneralCommandPlanImplementer()
        )
        self.display_command_implementer = (
            display_command_implementer
            or DisplayCommandPlanImplementer()
        )
        self.call_api_command_implementer = (
            call_api_command_implementer
            or CallAPICommandPlanImplementer()
        )
        self.call_worker_command_implementer = (
            call_worker_command_implementer
            or CallWorkerCommandPlanImplementer()
        )

    def implement(
        self,
        *,
        command_plans: list[CommandAnalysisPlan],
        static_attributes: StaticAttributes | None = None,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
        model_config: ModelConfig,
        reference_code_catalog: ReferenceCodeCatalog,
    ) -> CommandImplementationResult:
        command_file_content = COMMANDS_MODULE_HEADER.rstrip()
        command_function_names: list[str] = []

        for command_index, command_plan in enumerate(command_plans, start=1):
            print(
                f"[Compiler][Implementation][Commands] {command_index}/"
                f"{len(command_plans)} {command_plan['command_name']} "
                f"({command_plan['command_type']}): started.",
                flush=True,
            )
            function_implementation = self._implement_command(
                command_plan=command_plan,
                static_attributes=(
                    static_attributes or create_empty_static_attributes()
                ),
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(
                    python_schema_dependency_table
                ),
                model_config=model_config,
                reference_code_catalog=reference_code_catalog,
            )
            function_name = function_implementation["function_name"]
            if function_name in command_function_names:
                raise ValueError(
                    "Generated Command function name is duplicated: "
                    f"{function_name!r}."
                )

            command_file_content += (
                "\n\n\n"
                + function_implementation["function_code"].strip()
            )
            command_function_names.append(function_name)
            print(
                f"[Compiler][Implementation][Commands] {command_index}/"
                f"{len(command_plans)} {command_plan['command_name']}: "
                "completed.",
                flush=True,
            )

        command_file_content += "\n"
        compile(command_file_content, "commands.py", "exec")

        return {
            "generated_file": {
                "relative_path": "commands.py",
                "content": command_file_content,
                "write_type": "rewrite",
            },
            "command_function_names": command_function_names,
        }

    def _implement_command(
        self,
        *,
        command_plan: CommandAnalysisPlan,
        static_attributes: StaticAttributes,
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
        model_config: ModelConfig,
        reference_code_catalog: ReferenceCodeCatalog,
    ) -> FunctionImplementation:
        command_type = command_plan["command_type"]

        if command_type == "request_input":
            return self.input_command_implementer.implement(
                command_plan=command_plan,
                static_attributes=static_attributes,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(
                    python_schema_dependency_table
                ),
                model_config=model_config,
            )
        if command_type == "general_command":
            return self.general_command_implementer.implement(
                command_plan=command_plan,
                static_attributes=static_attributes,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(
                    python_schema_dependency_table
                ),
                model_config=model_config,
            )
        if command_type == "display_message":
            return self.display_command_implementer.implement(
                command_plan=command_plan,
                static_attributes=static_attributes,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(
                    python_schema_dependency_table
                ),
                model_config=model_config,
            )
        if command_type == "call_api":
            return self.call_api_command_implementer.implement(
                command_plan=command_plan,
                static_attributes=static_attributes,
                variables=variables,
                python_schema_code_table=python_schema_code_table,
                python_schema_dependency_table=(
                    python_schema_dependency_table
                ),
                model_config=model_config,
                reference_code_catalog=reference_code_catalog,
            )
        if command_type == "call_worker":
            return self.call_worker_command_implementer.implement(
                command_plan=command_plan,
            )

        raise ValueError(
            f"Unsupported Command type: {command_type!r}."
        )
