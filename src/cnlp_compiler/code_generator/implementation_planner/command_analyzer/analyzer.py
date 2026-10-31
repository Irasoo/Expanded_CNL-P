"""
Analysis顾名思义就是独立与具体实现之外，CNL-P Agent语义级别的内容分析，在正式生成代码之前，需要知道那些抽象事物的实现情况...
也就是说，代码生成应该继续分为两个大段，如果后面的叫“实现”，那前面，也就是现在的分析阶段应该叫什么呢？？？


针对不同的command，应该要分析出不同的事物：
"""

from ....schema import (
    CNLPTypeIR,
    CallAPICommandAnalysisPlan,
    CallWorkerCommandAnalysisPlan,
    CommandAnalysisPlan,
    CommandNode,
    DisplayCommandAnalysisPlan,
    GeneralCommandAnalysisPlan,
    InputCommandAnalysisPlan,
    StaticAttributes,
    VariableNode,
    WorkerNode,
    create_empty_static_attributes,
)
from ...reference_code_catalog import ReferenceCodeCatalog
from .call_analyzer import CallAPICommandAnalyzer
from .display_analyzer import DisplayCommandAnalyzer
from .general_analyzer import GeneralCommandAnalyzer
from .input_analyzer import InputCommandAnalyzer


class CommandAnalyzer:

    def __init__(
        self,
        *,
        input_analyzer: InputCommandAnalyzer | None = None,
        general_analyzer: GeneralCommandAnalyzer | None = None,
        display_analyzer: DisplayCommandAnalyzer | None = None,
        call_api_analyzer: CallAPICommandAnalyzer | None = None,
        reference_code_catalog: ReferenceCodeCatalog | None = None,
    ):
        self.input_analyzer = input_analyzer or InputCommandAnalyzer()
        self.general_analyzer = general_analyzer or GeneralCommandAnalyzer()
        self.display_analyzer = display_analyzer or DisplayCommandAnalyzer()
        self.call_api_analyzer = call_api_analyzer or CallAPICommandAnalyzer(
            reference_code_catalog=reference_code_catalog,
        )

    def analyze(
        self,
        *,
        cnlp_script: str,
        commands: list[CommandNode],
        variables: list[VariableNode],
        static_attributes: StaticAttributes | None = None,
        workers: dict[str, WorkerNode] | None = None,
        cnlp_types: list[CNLPTypeIR] | None = None,
        python_schema_code_table: dict[str, str] | None = None,
        python_schema_dependency_table: dict[str, list[str]] | None = None,
        general_command_plans: dict[str, GeneralCommandAnalysisPlan] | None = None,
        display_command_plans: dict[str, DisplayCommandAnalysisPlan] | None = None,
        call_api_command_plans: dict[str, CallAPICommandAnalysisPlan] | None = None,
        input_command_plans: dict[str, InputCommandAnalysisPlan] | None = None,
    ) -> list[CommandAnalysisPlan]:

        # TODO: 基本上不可能出现的空的Attributes
        static_attributes = static_attributes or create_empty_static_attributes()
        # TODO：__init__里面适合做这种事情吗？
        workers = workers or {}
        if input_command_plans is None:
            input_command_plans = {
                plan["command_name"]: plan
                for plan in self.input_analyzer.analyze_all(
                    commands=[
                        command
                        for command in commands
                        if command["command_type"] == "request_input"
                    ],
                    variables=variables,
                    python_schema_code_table=python_schema_code_table,
                    python_schema_dependency_table=(
                        python_schema_dependency_table or {}
                    ),
                )
            }
        if call_api_command_plans is None:
            call_api_commands = [
                command for command in commands if command["command_type"] == "call_api"
            ]
            if call_api_commands:
                print(
                    "[Compiler][Planning][Commands] Preparing "
                    f"{len(call_api_commands)} Call API Command plan(s).",
                    flush=True,
                )
            call_api_command_plans = {
                plan["command_name"]: plan
                for plan in self.call_api_analyzer.analyze_all(
                    cnlp_script=cnlp_script,
                    commands=call_api_commands,
                    cnlp_types=cnlp_types,
                )
            }
        if general_command_plans is None:
            general_command_plans = {
                plan["command_name"]: plan
                for plan in self.general_analyzer.analyze_all(
                    commands=[
                        command
                        for command in commands
                        if command["command_type"] == "general_command"
                    ],
                    variables=variables,
                    python_schema_code_table=python_schema_code_table,
                    python_schema_dependency_table=(
                        python_schema_dependency_table or {}
                    ),
                )
            }
        if display_command_plans is None:
            display_command_plans = {
                plan["command_name"]: plan
                for plan in self.display_analyzer.analyze_all(
                    commands=[
                        command
                        for command in commands
                        if command["command_type"] == "display_message"
                    ],
                    variables=variables,
                    python_schema_code_table=python_schema_code_table,
                    python_schema_dependency_table=(
                        python_schema_dependency_table or {}
                    ),
                )
            }

        plans: list[CommandAnalysisPlan] = []
        for command_index, command in enumerate(commands, start=1):
            print(
                f"[Compiler][Planning][Commands] {command_index}/"
                f"{len(commands)} {command['command_name']} "
                f"({command['command_type']}): started.",
                flush=True,
            )
            plans.append(
                self._analyze_command(
                    command=command,
                    variables=variables,
                    static_attributes=static_attributes,
                    input_command_plans=input_command_plans,
                    call_api_plans=call_api_command_plans,
                    general_command_plans=general_command_plans,
                    display_command_plans=display_command_plans,
                    workers=workers,
                    python_schema_code_table=python_schema_code_table,
                    python_schema_dependency_table=(
                        python_schema_dependency_table or {}
                    ),
                )
            )
            print(
                f"[Compiler][Planning][Commands] {command_index}/"
                f"{len(commands)} {command['command_name']}: completed.",
                flush=True,
            )
        return plans

    def _analyze_command(
        self,
        *,
        command: CommandNode,
        variables: list[VariableNode],
        static_attributes: StaticAttributes,
        input_command_plans: dict[str, InputCommandAnalysisPlan],
        call_api_plans: dict[str, CallAPICommandAnalysisPlan],
        general_command_plans: dict[str, GeneralCommandAnalysisPlan],
        display_command_plans: dict[str, DisplayCommandAnalysisPlan],
        workers: dict[str, WorkerNode],
        python_schema_code_table: dict[str, str] | None,
        python_schema_dependency_table: dict[str, list[str]],
    ) -> CommandAnalysisPlan:
        command_type = command["command_type"]

        if command_type == "request_input":
            return input_command_plans[command["command_name"]]
        elif command_type == "general_command":
            return general_command_plans[command["command_name"]]
        elif command_type == "display_message":
            return display_command_plans[command["command_name"]]
        elif command_type == "call_api":
            return call_api_plans[command["command_name"]]
        elif command_type == "call_worker":
            return self._analyze_call_worker(
                command=command,
                workers=workers,
            )

        raise ValueError(f"Unsupported command type: {command_type}")

    @staticmethod
    def _analyze_call_worker(
        *,
        command: CommandNode,
        workers: dict[str, WorkerNode],
    ) -> CallWorkerCommandAnalysisPlan:
        target_name = command["target_worker_name"]
        target = workers.get(target_name)
        if target is None:
            raise ValueError(f"CALL target Worker {target_name!r} is not defined.")

        declared_inputs = {item["variable_name"]: item for item in target["inputs"]}
        supplied_names = {
            argument["parameter_name"] for argument in command["arguments"]
        }
        unknown_names = supplied_names - declared_inputs.keys()
        if unknown_names:
            raise ValueError(
                f"CALL {target_name} supplies undeclared Worker INPUTS: "
                f"{sorted(unknown_names)}."
            )
        missing_required = {
            name
            for name, item in declared_inputs.items()
            if item["is_required"] and name not in supplied_names
        }
        if missing_required:
            raise ValueError(
                f"CALL {target_name} is missing required Worker INPUTS: "
                f"{sorted(missing_required)}."
            )
        if command["response"] is not None and not target["outputs"]:
            raise ValueError(
                f"CALL {target_name} declares RESPONSE, but the Worker has "
                "no OUTPUTS."
            )

        return CallWorkerCommandAnalysisPlan(
            command_name=command["command_name"],
            command_index=command["command_index"],
            command_type="call_worker",
            target_worker_name=target_name,
            arguments=command["arguments"],
            response=command["response"],
            target_inputs=target["inputs"],
            target_outputs=target["outputs"],
            required_variables=command["required_variables"],
            written_variable=command["written_variable"],
            write_operation=command["write_operation"],
        )
