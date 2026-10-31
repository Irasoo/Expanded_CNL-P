from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .type_system import type_name_from_cnlp


_COMMAND = re.compile(r"^command\d+$")
_IF_BLOCK = re.compile(r"^if_block\d+$")
_LOOP_BLOCK = re.compile(r"^(?:while|for)_block\d+$")
_FLOW = re.compile(r"^(?:main_flow|alternative_flow\d+|exception_flow\d+)$")
_EXAMPLE_COMMAND = re.compile(r"^COMMAND-(\d+)$", re.IGNORECASE)


def format_path(path: tuple[str, ...]) -> str:
    return ".".join(path)


@dataclass(frozen=True)
class VariableReference:
    name: str
    path: tuple[str, ...]
    worker_name: str | None = None
    command_name: str | None = None


@dataclass(frozen=True)
class CallArgument:
    parameter_name: str
    variable_name: str | None


@dataclass(frozen=True)
class CommandFact:
    name: str
    path: tuple[str, ...]
    worker_name: str
    command_type: str
    reads: tuple[VariableReference, ...]
    write_name: str | None
    write_type_name: str | None
    write_is_declaration: bool
    api_name: str | None
    arguments: tuple[CallArgument, ...]
    has_response: bool


@dataclass(frozen=True)
class SequenceFact:
    elements: tuple[Any, ...]


@dataclass(frozen=True)
class BranchFact:
    condition_reads: tuple[VariableReference, ...]
    body: SequenceFact
    path: tuple[str, ...]


@dataclass(frozen=True)
class IfFact:
    branches: tuple[BranchFact, ...]
    path: tuple[str, ...]


@dataclass(frozen=True)
class LoopFact:
    condition_reads: tuple[VariableReference, ...]
    body: SequenceFact
    path: tuple[str, ...]


@dataclass(frozen=True)
class ExampleFact:
    name: str
    kind: str
    path: tuple[str, ...]
    worker_name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    execution_path: tuple[str, ...]


@dataclass(frozen=True)
class SemanticFacts:
    ast: dict[str, Any]
    declared_variables: dict[str, str | None]
    local_types: dict[str, Any]
    persona_references: tuple[VariableReference, ...]
    constraint_references: tuple[VariableReference, ...]
    commands: tuple[CommandFact, ...]
    worker_flows: dict[str, SequenceFact]
    worker_inputs: dict[str, frozenset[str]]
    worker_required_inputs: dict[str, frozenset[str]]
    worker_outputs: dict[str, frozenset[str]]
    examples: tuple[ExampleFact, ...]


class SemanticFactCollector:
    """Read the TOSEM AST once and expose facts; it makes no judgments."""

    def collect(self, ast: dict[str, Any]) -> SemanticFacts:
        if not isinstance(ast, dict):
            raise TypeError("cnlp_ast must be a dictionary.")

        declared_variables: dict[str, str | None] = {}
        variables = ast.get("variables")
        if isinstance(variables, dict):
            for section_name, payload in variables.items():
                if not isinstance(section_name, str) or not isinstance(payload, dict):
                    continue
                name = payload.get("variable_name", section_name)
                if isinstance(name, str):
                    declared_variables[name] = type_name_from_cnlp(payload.get("data_type"))

        local_types: dict[str, Any] = {}
        raw_types = ast.get("types")
        if isinstance(raw_types, dict):
            for section_name, payload in raw_types.items():
                if not isinstance(section_name, str) or not isinstance(payload, dict):
                    continue
                name = payload.get("type_name", section_name)
                content = payload.get("type_content")
                if isinstance(name, str) and isinstance(content, (dict, list)):
                    local_types[name] = content

        commands: list[CommandFact] = []
        worker_flows: dict[str, SequenceFact] = {}
        worker_inputs: dict[str, frozenset[str]] = {}
        worker_required_inputs: dict[str, frozenset[str]] = {}
        worker_outputs: dict[str, frozenset[str]] = {}
        examples: list[ExampleFact] = []
        workers = ast.get("workers")
        if isinstance(workers, dict):
            worker_symbols = frozenset(
                worker_name
                for worker_name, worker in workers.items()
                if isinstance(worker_name, str) and isinstance(worker, dict)
            )
            for worker_name, worker in workers.items():
                if not isinstance(worker_name, str) or not isinstance(worker, dict):
                    continue
                worker_inputs[worker_name] = self._worker_interface_names(
                    worker.get("input")
                )
                worker_required_inputs[worker_name] = (
                    self._worker_required_interface_names(worker.get("input"))
                )
                worker_outputs[worker_name] = self._worker_interface_names(
                    worker.get("output")
                )
                examples.extend(self._examples(worker_name, worker.get("example")))
                main_flow = worker.get("main_flow")
                if isinstance(main_flow, dict):
                    worker_flows[worker_name] = self._sequence(
                        main_flow,
                        path=("workers", worker_name, "main_flow"),
                        worker_name=worker_name,
                        worker_symbols=worker_symbols,
                        commands=commands,
                    )

        return SemanticFacts(
            ast=ast,
            declared_variables=declared_variables,
            local_types=local_types,
            persona_references=self._references(ast.get("persona"), ("persona",)),
            constraint_references=self._references(ast.get("constraints"), ("constraints",)),
            commands=tuple(commands),
            worker_flows=worker_flows,
            worker_inputs=worker_inputs,
            worker_required_inputs=worker_required_inputs,
            worker_outputs=worker_outputs,
            examples=tuple(examples),
        )

    @staticmethod
    def _worker_interface_names(value: Any) -> frozenset[str]:
        names: set[str] = set()
        if isinstance(value, dict):
            for reference in value.values():
                if not isinstance(reference, dict):
                    continue
                name = reference.get("var_name")
                if isinstance(name, str):
                    names.add(name)
        return frozenset(names)

    @staticmethod
    def _worker_required_interface_names(value: Any) -> frozenset[str]:
        names: set[str] = set()
        if isinstance(value, dict):
            for reference in value.values():
                if not isinstance(reference, dict):
                    continue
                name = reference.get("var_name")
                if isinstance(name, str) and reference.get("is_required") is True:
                    names.add(name)
        return frozenset(names)

    @staticmethod
    def _examples(worker_name: str, value: Any) -> list[ExampleFact]:
        examples: list[ExampleFact] = []
        if not isinstance(value, dict):
            return examples
        for name, payload in value.items():
            if not isinstance(name, str) or not isinstance(payload, dict):
                continue
            if name.startswith("expect_worker_behavior"):
                kind = "expected"
                output_key = "expected-output"
            elif name.startswith("defect_worker_behavior"):
                kind = "defect"
                output_key = "defect-outputs"
            else:
                continue
            inputs = payload.get("inputs")
            outputs = payload.get(output_key)
            raw_execution_path = payload.get("execution-path")
            if not isinstance(inputs, dict):
                inputs = {}
            if not isinstance(outputs, dict):
                outputs = {}
            execution_path: list[str] = []
            if isinstance(raw_execution_path, list):
                for command in raw_execution_path:
                    if not isinstance(command, str):
                        continue
                    match = _EXAMPLE_COMMAND.fullmatch(command.strip())
                    if match:
                        execution_path.append(f"command{int(match.group(1))}")
            examples.append(
                ExampleFact(
                    name=name,
                    kind=kind,
                    path=("workers", worker_name, "example", name),
                    worker_name=worker_name,
                    inputs=dict(inputs),
                    outputs=dict(outputs),
                    execution_path=tuple(execution_path),
                )
            )
        return examples

    def _sequence(
        self,
        mapping: dict[str, Any],
        *,
        path: tuple[str, ...],
        worker_name: str,
        worker_symbols: frozenset[str],
        commands: list[CommandFact],
    ) -> SequenceFact:
        elements: list[Any] = []
        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            child_path = (*path, key)
            if _COMMAND.fullmatch(key):
                command = self._command(
                    key,
                    value,
                    path=child_path,
                    worker_name=worker_name,
                    worker_symbols=worker_symbols,
                )
                commands.append(command)
                elements.append(command)
            elif _IF_BLOCK.fullmatch(key):
                branches: list[BranchFact] = []
                for branch_name, branch in value.items():
                    if not isinstance(branch_name, str) or not isinstance(branch, dict):
                        continue
                    branch_path = (*child_path, branch_name)
                    branches.append(
                        BranchFact(
                            condition_reads=self._references(
                                branch.get("condition"),
                                (*branch_path, "condition"),
                                worker_name=worker_name,
                            ),
                            body=self._sequence(
                                branch,
                                path=branch_path,
                                worker_name=worker_name,
                                worker_symbols=worker_symbols,
                                commands=commands,
                            ),
                            path=branch_path,
                        )
                    )
                elements.append(IfFact(branches=tuple(branches), path=child_path))
            elif _LOOP_BLOCK.fullmatch(key):
                elements.append(
                    LoopFact(
                        condition_reads=self._references(
                            value.get("condition"),
                            (*child_path, "condition"),
                            worker_name=worker_name,
                        ),
                        body=self._sequence(
                            value,
                            path=child_path,
                            worker_name=worker_name,
                            worker_symbols=worker_symbols,
                            commands=commands,
                        ),
                        path=child_path,
                    )
                )
            elif _FLOW.fullmatch(key):
                elements.extend(
                    self._sequence(
                        value,
                        path=child_path,
                        worker_name=worker_name,
                        worker_symbols=worker_symbols,
                        commands=commands,
                    ).elements
                )
            elif key.startswith(("sequential_block", "if_branch")):
                elements.extend(
                    self._sequence(
                        value,
                        path=child_path,
                        worker_name=worker_name,
                        worker_symbols=worker_symbols,
                        commands=commands,
                    ).elements
                )
        return SequenceFact(elements=tuple(elements))

    def _command(
        self,
        name: str,
        command: dict[str, Any],
        *,
        path: tuple[str, ...],
        worker_name: str,
        worker_symbols: frozenset[str],
    ) -> CommandFact:
        command_type = command.get("type")
        if not isinstance(command_type, str):
            command_type = "unknown"

        raw_api_name = command.get("api_name")
        if (
            command_type == "call_api"
            and isinstance(raw_api_name, str)
            and raw_api_name in worker_symbols
        ):
            command_type = "call_worker"

        if command_type in {"call_api", "call_worker"}:
            reads = self._references(
                command.get("paras"),
                (*path, "paras"),
                worker_name=worker_name,
                command_name=name,
            )
        else:
            reads = self._references(
                command.get("description_with_reference"),
                (*path, "description_with_reference"),
                worker_name=worker_name,
                command_name=name,
            )

        target_key = {
            "request_input": "value",
            "general_command": "result",
            "call_api": "response",
            "call_worker": "response",
        }.get(command_type)
        target = command.get(target_key) if target_key else None
        write_name = None
        write_type_name = None
        write_is_declaration = False
        if isinstance(target, dict):
            direct_name = target.get("var_name")
            direct_type = target.get("var_type")
            reference = target.get("reference")
            if isinstance(direct_name, str):
                write_name = direct_name
                write_type_name = direct_type if isinstance(direct_type, str) else None
                write_is_declaration = True
            elif isinstance(reference, dict):
                referenced_name = reference.get("var_name")
                if isinstance(referenced_name, str):
                    write_name = referenced_name

        arguments: list[CallArgument] = []
        raw_arguments = command.get("paras")
        if isinstance(raw_arguments, dict):
            for parameter_name, argument in raw_arguments.items():
                if not isinstance(parameter_name, str):
                    continue
                variable_name = None
                if isinstance(argument, dict) and argument.get("type") == "reference":
                    reference = argument.get("reference")
                    if isinstance(reference, str):
                        variable_name = reference.split(".", 1)[0]
                arguments.append(CallArgument(parameter_name, variable_name))

        return CommandFact(
            name=name,
            path=path,
            worker_name=worker_name,
            command_type=command_type,
            reads=reads,
            write_name=(write_name if isinstance(write_name, str) else None),
            write_type_name=(write_type_name if isinstance(write_type_name, str) else None),
            write_is_declaration=write_is_declaration,
            api_name=(raw_api_name if isinstance(raw_api_name, str) else None),
            arguments=tuple(arguments),
            has_response=isinstance(command.get("response"), dict),
        )

    def _references(
        self,
        value: Any,
        path: tuple[str, ...],
        *,
        worker_name: str | None = None,
        command_name: str | None = None,
    ) -> tuple[VariableReference, ...]:
        found: list[VariableReference] = []

        def visit(current: Any, current_path: tuple[str, ...]) -> None:
            if isinstance(current, dict):
                if current.get("type") == "reference" and isinstance(current.get("reference"), str):
                    found.append(
                        VariableReference(
                            name=current["reference"].split(".", 1)[0],
                            path=current_path,
                            worker_name=worker_name,
                            command_name=command_name,
                        )
                    )
                elif isinstance(current.get("var_name"), str):
                    found.append(
                        VariableReference(
                            name=current["var_name"].split(".", 1)[0],
                            path=current_path,
                            worker_name=worker_name,
                            command_name=command_name,
                        )
                    )
                for key, child in current.items():
                    visit(child, (*current_path, str(key)))
            elif isinstance(current, list):
                for index, child in enumerate(current):
                    visit(child, (*current_path, f"[{index}]"))

        visit(value, path)
        unique: list[VariableReference] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for reference in found:
            key = (reference.name, reference.path)
            if key not in seen:
                seen.add(key)
                unique.append(reference)
        return tuple(unique)


__all__ = [
    "BranchFact",
    "CallArgument",
    "CommandFact",
    "ExampleFact",
    "IfFact",
    "LoopFact",
    "SemanticFactCollector",
    "SemanticFacts",
    "SequenceFact",
    "VariableReference",
    "format_path",
]
