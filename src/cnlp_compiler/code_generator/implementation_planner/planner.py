from __future__ import annotations

from ...schema import (
    CNLPTypeIR,
    CallAPICommandAnalysisPlan,
    CommandAnalysisPlan,
    CommandNode,
    ConditionNode,
    DisplayCommandAnalysisPlan,
    GeneralCommandAnalysisPlan,
    ImplementationPlan,
    InputCommandAnalysisPlan,
    PredicateAnalysisPlan,
    StaticAttributes,
    VariableNode,
    WorkerNode,
    create_empty_static_attributes,
)
from ..plan_implementer.type_converter import TypeConverter
from ..reference_code_catalog import ReferenceCodeCatalog
from .command_analyzer import CommandAnalyzer
from .predicate_analyzer import PredicateAnalyzer


class ImplementationPlanner:

    def __init__(
        self,
        *,
        command_analyzer: CommandAnalyzer | None = None,
        predicate_analyzer: PredicateAnalyzer | None = None,
        reference_code_catalog: ReferenceCodeCatalog | None = None,
        type_converter: TypeConverter | None = None,
    ):
        self.command_analyzer = command_analyzer or CommandAnalyzer(
            reference_code_catalog=reference_code_catalog,
        )
        self.predicate_analyzer = predicate_analyzer or PredicateAnalyzer()
        self.type_converter = type_converter or TypeConverter()

    # NodeVisitor 将每个 Worker 的定义和内部节点分开交给 Planner：
    #
    # workers = [
    #     {
    #         "worker_name": "ProjectNavigator",
    #         "description": "负责理解项目并协调其他 Worker",
    #         "inputs": [
    #             {"variable_name": "project_input", "is_required": True},
    #         ],
    #         "outputs": [
    #             {"variable_name": "project_result", "is_required": True},
    #         ],
    #     },
    # ]
    #
    # commands_by_worker = {
    #     "ProjectNavigator": [
    #         {
    #             "command_name": "command1",
    #             "command_index": 1,
    #             "command_type": "request_input",
    #             "description": "请求用户提供项目",
    #             "required_variables": [],
    #             "written_variable": "project_input",
    #             "write_operation": "SET",
    #         },
    #     ],
    # }
    # 以上展示的是 request_input；general_command/display_message 同样带
    # description，call_api 改为携带 api_name/arguments/response，
    # call_worker 改为携带 target_worker_name/arguments/response。
    #
    # conditions_by_worker = {
    #     "ProjectNavigator": [
    #         {
    #             "predicate_name": "predicate1",
    #             "predicate_index": 1,
    #             "condition_kind": "if",
    #             "owner_name": "if_branch1",
    #             "condition_path": [
    #                 "worker",
    #                 "main_flow",
    #                 "if_block1",
    #                 "if_branch1",
    #             ],
    #             "description": "用户输入是 Repository URL",
    #             "required_variables": ["project_input"],
    #         },
    #     ],
    # }
    #
    # workers 只描述 Worker 本身的名称、职责以及 INPUTS/OUTPUTS 接口；
    # 后两张表才保存各 Worker 内部的 Command 和 Condition，不是重复数据。
    def plan(
        self,
        *,
        cnlp_script: str,
        workers: list[WorkerNode],
        commands_by_worker: dict[str, list[CommandNode]],
        conditions_by_worker: dict[str, list[ConditionNode]],
        variables: list[VariableNode],
        cnlp_types: list[CNLPTypeIR] | None = None,
        static_attributes: StaticAttributes | None = None,
    ) -> ImplementationPlan:
        static_attributes = static_attributes or create_empty_static_attributes()
        if not workers:
            raise ValueError("At least one Worker is required for planning.")
        normalized_cnlp_types = cnlp_types or []
        converted_types = self.type_converter.convert_with_schema_index(
            normalized_cnlp_types
        )
        worker_lookup = {worker["worker_name"]: worker for worker in workers}
        entry_worker = self._select_entry_worker(
            workers=workers,
            commands_by_worker=commands_by_worker,
        )
        print(
            f"[Compiler][Planning] Entry Worker: {entry_worker}.",
            flush=True,
        )
        input_plans_by_command = self._planning_all_input_commands(
            commands_by_worker=commands_by_worker,
            variables=variables,
            python_schema_code_table=converted_types["schema_code_table"],
            python_schema_dependency_table=converted_types[
                "schema_dependency_table"
            ],
        )
        general_plans_by_command, display_plans_by_command = (
            self._planning_general_and_display_commands(
                commands_by_worker=commands_by_worker,
                variables=variables,
                python_schema_code_table=converted_types["schema_code_table"],
                python_schema_dependency_table=converted_types[
                    "schema_dependency_table"
                ],
            )
        )
        predicate_plans_by_condition = self._planning_all_predicates(
            conditions_by_worker=conditions_by_worker,
            variables=variables,
            python_schema_code_table=converted_types["schema_code_table"],
            python_schema_dependency_table=converted_types["schema_dependency_table"],
        )
        call_api_plans_by_command = self._planning_all_call_api_commands(
            cnlp_script=cnlp_script,
            commands_by_worker=commands_by_worker,
            cnlp_types=normalized_cnlp_types,
        )
        worker_plans = {}
        for worker_index, worker in enumerate(workers, start=1):
            worker_name = worker["worker_name"]
            worker_commands = commands_by_worker.get(worker_name, [])
            worker_conditions = conditions_by_worker.get(worker_name, [])
            print(
                f"[Compiler][Planning] Worker {worker_index}/{len(workers)} "
                f"{worker_name}: analyzing {len(worker_commands)} Command(s).",
                flush=True,
            )
            command_plans = self._planning_commands_implementation(
                cnlp_script=cnlp_script,
                commands=worker_commands,
                variables=variables,
                static_attributes=static_attributes,
                workers=worker_lookup,
                cnlp_types=normalized_cnlp_types,
                python_schema_code_table=converted_types["schema_code_table"],
                python_schema_dependency_table=converted_types[
                    "schema_dependency_table"
                ],
                input_command_plans={
                    command["command_name"]: input_plans_by_command[id(command)]
                    for command in worker_commands
                    if command["command_type"] == "request_input"
                },
                general_command_plans={
                    command["command_name"]: general_plans_by_command[id(command)]
                    for command in worker_commands
                    if command["command_type"] == "general_command"
                },
                display_command_plans={
                    command["command_name"]: display_plans_by_command[id(command)]
                    for command in worker_commands
                    if command["command_type"] == "display_message"
                },
                call_api_command_plans={
                    command["command_name"]: call_api_plans_by_command[id(command)]
                    for command in worker_commands
                    if command["command_type"] == "call_api"
                },
            )
            print(
                f"[Compiler][Planning] Worker {worker_index}/{len(workers)} "
                f"{worker_name}: assigning {len(worker_conditions)} "
                "planned judgement condition(s).",
                flush=True,
            )
            predicate_plans = [
                predicate_plans_by_condition[id(condition)]
                for condition in worker_conditions
            ]
            worker_plans[worker_name] = {
                "worker_name": worker_name,
                "description": worker["description"],
                "inputs": worker["inputs"],
                "outputs": worker["outputs"],
                "commands": command_plans,
                "predicates": predicate_plans,
            }
            print(
                f"[Compiler][Planning] Worker {worker_index}/{len(workers)} "
                f"{worker_name}: completed.",
                flush=True,
            )
        return {
            "entry_worker": entry_worker,
            "workers": worker_plans,
        }

    def _planning_commands_implementation(
        self,
        *,
        cnlp_script: str,
        commands: list[CommandNode],
        variables: list[VariableNode],
        static_attributes: StaticAttributes,
        workers: dict[str, WorkerNode],
        cnlp_types: list[CNLPTypeIR],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
        input_command_plans: dict[str, InputCommandAnalysisPlan],
        general_command_plans: dict[str, GeneralCommandAnalysisPlan],
        display_command_plans: dict[str, DisplayCommandAnalysisPlan],
        call_api_command_plans: dict[str, CallAPICommandAnalysisPlan],
    ) -> list[CommandAnalysisPlan]:
        return self.command_analyzer.analyze(
            cnlp_script=cnlp_script,
            commands=commands,
            variables=variables,
            static_attributes=static_attributes,
            workers=workers,
            cnlp_types=cnlp_types,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=python_schema_dependency_table,
            input_command_plans=input_command_plans,
            general_command_plans=general_command_plans,
            display_command_plans=display_command_plans,
            call_api_command_plans=call_api_command_plans,
        )

    def _planning_all_input_commands(
        self,
        *,
        commands_by_worker: dict[str, list[CommandNode]],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
    ) -> dict[int, InputCommandAnalysisPlan]:
        input_commands = [
            command
            for commands in commands_by_worker.values()
            for command in commands
            if command["command_type"] == "request_input"
        ]
        if input_commands:
            print(
                "[Compiler][Planning][Input] Analyzing all "
                f"{len(input_commands)} Command(s) in one request.",
                flush=True,
            )
        plans = self.command_analyzer.input_analyzer.analyze_all(
            commands=input_commands,
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=python_schema_dependency_table,
        )
        return {
            id(command): plan
            for command, plan in zip(
                input_commands,
                plans,
                strict=True,
            )
        }

    def _planning_all_call_api_commands(
        self,
        *,
        cnlp_script: str,
        commands_by_worker: dict[str, list[CommandNode]],
        cnlp_types: list[CNLPTypeIR],
    ) -> dict[int, CallAPICommandAnalysisPlan]:
        call_api_commands = [
            command
            for commands in commands_by_worker.values()
            for command in commands
            if command["command_type"] == "call_api"
        ]
        if call_api_commands:
            print(
                "[Compiler][Planning][Call API] Analyzing all "
                f"{len(call_api_commands)} Command description(s) in one "
                "request.",
                flush=True,
            )
        plans = self.command_analyzer.call_api_analyzer.analyze_all(
            cnlp_script=cnlp_script,
            commands=call_api_commands,
            cnlp_types=cnlp_types,
        )
        return {
            id(command): plan
            for command, plan in zip(
                call_api_commands,
                plans,
                strict=True,
            )
        }

    def _planning_general_and_display_commands(
        self,
        *,
        commands_by_worker: dict[str, list[CommandNode]],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
    ) -> tuple[
        dict[int, GeneralCommandAnalysisPlan],
        dict[int, DisplayCommandAnalysisPlan],
    ]:
        all_commands = [
            command for commands in commands_by_worker.values() for command in commands
        ]
        general_commands = [
            command
            for command in all_commands
            if command["command_type"] == "general_command"
        ]
        display_commands = [
            command
            for command in all_commands
            if command["command_type"] == "display_message"
        ]

        if general_commands:
            print(
                "[Compiler][Planning][General] Analyzing all "
                f"{len(general_commands)} Command(s) in one request.",
                flush=True,
            )
        general_plans = self.command_analyzer.general_analyzer.analyze_all(
            commands=general_commands,
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=python_schema_dependency_table,
        )

        if display_commands:
            print(
                "[Compiler][Planning][Display] Analyzing all "
                f"{len(display_commands)} Command(s) in one request.",
                flush=True,
            )
        display_plans = self.command_analyzer.display_analyzer.analyze_all(
            commands=display_commands,
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=python_schema_dependency_table,
        )

        return (
            {
                id(command): plan
                for command, plan in zip(
                    general_commands,
                    general_plans,
                    strict=True,
                )
            },
            {
                id(command): plan
                for command, plan in zip(
                    display_commands,
                    display_plans,
                    strict=True,
                )
            },
        )

    def _planning_all_predicates(
        self,
        *,
        conditions_by_worker: dict[str, list[ConditionNode]],
        variables: list[VariableNode],
        python_schema_code_table: dict[str, str],
        python_schema_dependency_table: dict[str, list[str]],
    ) -> dict[int, PredicateAnalysisPlan]:
        all_conditions = [
            condition
            for conditions in conditions_by_worker.values()
            for condition in conditions
        ]
        if all_conditions:
            print(
                "[Compiler][Planning][Predicates] Analyzing all "
                f"{len(all_conditions)} judgement condition(s) in one "
                "request.",
                flush=True,
            )
        predicate_plans = self.predicate_analyzer.analyze_all(
            conditions=all_conditions,
            variables=variables,
            python_schema_code_table=python_schema_code_table,
            python_schema_dependency_table=(python_schema_dependency_table),
        )
        return {
            id(condition): plan
            for condition, plan in zip(
                all_conditions,
                predicate_plans,
                strict=True,
            )
        }

    @staticmethod
    def _select_entry_worker(
        *,
        workers: list[WorkerNode],
        commands_by_worker: dict[str, list[CommandNode]],
    ) -> str:
        """Select the unique Worker not invoked by another Worker."""
        if len(workers) == 1:
            return workers[0]["worker_name"]

        called_workers = {
            command["target_worker_name"]
            for caller_name, commands in commands_by_worker.items()
            for command in commands
            if (
                command["command_type"] == "call_worker"
                and command["target_worker_name"] != caller_name
            )
        }
        candidates = [
            worker["worker_name"]
            for worker in workers
            if worker["worker_name"] not in called_workers
        ]
        if len(candidates) == 1:
            return candidates[0]
        raise ValueError(
            "The entry Worker is ambiguous. Expected exactly one Worker "
            "that is not called by another Worker, but found "
            f"{candidates or 'none'}. Controller-based entry selection is "
            "intentionally not enabled in this compiler variant."
        )
