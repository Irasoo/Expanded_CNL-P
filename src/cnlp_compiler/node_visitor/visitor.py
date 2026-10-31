from __future__ import annotations

import copy
import re
from typing import Any

from ..schema.cnlp_types import CNLPDataType, CNLPTypeIR
from ..schema.node_visitor import (
    CallAPIArgumentNode,
    CallAPICommandNode,
    CallAPIResponseNode,
    CallWorkerCommandNode,
    CommandNode,
    CommandType,
    ConditionKind,
    ConditionNode,
    StaticAttributes,
    VariableNode,
    WorkerInterfaceVariable,
    WorkerNode,
    WorkflowBranch,
    WorkflowCommandStep,
    WorkflowFlow,
    WorkflowIfStep,
    WorkflowLoopStep,
    WorkflowStep,
    WorkflowStructure,
    WriteOperation,
)


_COMMAND_PATTERN = re.compile(r"^command(\d+)$")
_ALTERNATIVE_FLOW_PATTERN = re.compile(r"^alternative_flow\d+$")
_EXCEPTION_FLOW_PATTERN = re.compile(r"^exception_flow\d+$")
_IF_BLOCK_PATTERN = re.compile(r"^if_block\d+$")
_IF_BRANCH_PATTERN = re.compile(r"^if_branch(\d+)$")
_WHILE_BLOCK_PATTERN = re.compile(r"^while_block\d+$")
_FOR_BLOCK_PATTERN = re.compile(r"^for_block\d+$")


class NodeVisitor:
    """Read-only queries over a reconstructed CNL-P AST."""

    @staticmethod
    def find_static_attributes(
        cnlp_ast: dict[str, Any],
    ) -> StaticAttributes:
        """Return normalized Persona, Audience, Concepts, and Constraints.

        The returned interface deliberately unwraps the parser's nested
        ``description`` objects. Planner and Implementer code therefore does
        not depend on the current physical AST representation.
        """
        NodeVisitor._require_ast(cnlp_ast)
        return {
            "persona": NodeVisitor._static_attribute_section(
                cnlp_ast,
                "persona",
            ),
            "audience": NodeVisitor._static_attribute_section(
                cnlp_ast,
                "audience",
            ),
            "concepts": NodeVisitor._static_attribute_section(
                cnlp_ast,
                "concepts",
            ),
            "constraints": NodeVisitor._static_attribute_section(
                cnlp_ast,
                "constraints",
            ),
        }

    @staticmethod
    def find_all_workers(
        cnlp_ast: dict[str, Any],
    ) -> list[WorkerNode]:
        """Return ordered Worker definitions with normalized I/O contracts."""
        NodeVisitor._require_ast(cnlp_ast)
        workers = cnlp_ast.get("workers")
        if workers is None:
            legacy_worker = NodeVisitor._optional_mapping(cnlp_ast, "worker")
            if legacy_worker is None:
                return []
            fallback_name = legacy_worker.get("worker_name", "worker")
            workers = {fallback_name: legacy_worker}
        if not isinstance(workers, dict):
            raise TypeError("AST section 'workers' must be an object.")

        results: list[WorkerNode] = []
        for worker_name, worker_ast in workers.items():
            if not isinstance(worker_name, str) or not worker_name:
                raise ValueError("Every Worker must have a non-empty name.")
            if not isinstance(worker_ast, dict):
                raise TypeError(
                    f"Worker {worker_name!r} must be represented as an object."
                )
            description = worker_ast.get("description", "")
            if not isinstance(description, str):
                raise TypeError(
                    f"Worker {worker_name!r} description must be a string."
                )
            results.append(
                WorkerNode(
                    worker_name=worker_name,
                    description=description,
                    inputs=NodeVisitor._worker_interface_variables(
                        worker_ast.get("input"),
                        section_name="INPUTS",
                        worker_name=worker_name,
                    ),
                    outputs=NodeVisitor._worker_interface_variables(
                        worker_ast.get("output"),
                        section_name="OUTPUTS",
                        worker_name=worker_name,
                    ),
                )
            )
        return results

    @staticmethod
    def find_commands_by_worker(
        cnlp_ast: dict[str, Any],
    ) -> dict[str, list[CommandNode]]:
        """Extract Commands per Worker while preserving local Command names."""
        worker_names = NodeVisitor._worker_names(cnlp_ast)
        worker_symbols = set(worker_names)
        result: dict[str, list[CommandNode]] = {}
        for worker_name in worker_names:
            commands = NodeVisitor.find_all_commands(
                NodeVisitor._worker_projection(cnlp_ast, worker_name)
            )
            resolved_commands: list[CommandNode] = []
            for command in commands:
                if (
                    command["command_type"] == "call_api"
                    and command["api_name"] in worker_symbols
                ):
                    resolved_commands.append(
                        CallWorkerCommandNode(
                            command_name=command["command_name"],
                            command_index=command["command_index"],
                            command_type="call_worker",
                            target_worker_name=command["api_name"],
                            arguments=command["arguments"],
                            response=command["response"],
                            required_variables=command[
                                "required_variables"
                            ],
                            written_variable=command["written_variable"],
                            write_operation=command["write_operation"],
                        )
                    )
                else:
                    resolved_commands.append(command)
            result[worker_name] = resolved_commands
        return result

    @staticmethod
    def find_conditions_by_worker(
        cnlp_ast: dict[str, Any],
    ) -> dict[str, list[ConditionNode]]:
        """Extract Predicate inputs independently for every Worker."""
        return {
            worker_name: NodeVisitor.find_all_conditions(
                NodeVisitor._worker_projection(cnlp_ast, worker_name)
            )
            for worker_name in NodeVisitor._worker_names(cnlp_ast)
        }

    @staticmethod
    def find_workflow_structures(
        cnlp_ast: dict[str, Any],
    ) -> dict[str, WorkflowStructure]:
        """Extract one normalized control structure for each Worker."""
        return {
            worker_name: NodeVisitor.find_workflow_structure(
                NodeVisitor._worker_projection(cnlp_ast, worker_name)
            )
            for worker_name in NodeVisitor._worker_names(cnlp_ast)
        }

    @staticmethod
    def _worker_interface_variables(
        raw_section: Any,
        *,
        section_name: str,
        worker_name: str,
    ) -> list[WorkerInterfaceVariable]:
        if raw_section is None:
            return []
        if not isinstance(raw_section, dict):
            raise TypeError(
                f"Worker {worker_name!r} {section_name} must be an object."
            )
        results: list[WorkerInterfaceVariable] = []
        for reference in raw_section.values():
            if not isinstance(reference, dict):
                raise TypeError(
                    f"Worker {worker_name!r} {section_name} contains an "
                    "invalid variable reference."
                )
            variable_name = reference.get("var_name")
            if not isinstance(variable_name, str) or not variable_name:
                raise ValueError(
                    f"Worker {worker_name!r} {section_name} contains a "
                    "reference without a variable name."
                )
            results.append(
                WorkerInterfaceVariable(
                    variable_name=variable_name,
                    is_required=bool(reference.get("is_required", False)),
                )
            )
        return results

    @staticmethod
    def _worker_names(cnlp_ast: dict[str, Any]) -> list[str]:
        return [
            worker["worker_name"]
            for worker in NodeVisitor.find_all_workers(cnlp_ast)
        ]

    @staticmethod
    def _worker_projection(
        cnlp_ast: dict[str, Any],
        worker_name: str,
    ) -> dict[str, Any]:
        workers = cnlp_ast.get("workers")
        if isinstance(workers, dict):
            worker_ast = workers.get(worker_name)
        else:
            worker_ast = cnlp_ast.get("worker")
        if not isinstance(worker_ast, dict):
            raise KeyError(f"Unknown Worker: {worker_name!r}.")
        projection = {
            key: value
            for key, value in cnlp_ast.items()
            if key not in {"worker", "workers"}
        }
        projection["worker"] = worker_ast
        return projection

    @staticmethod
    def _static_attribute_section(
        cnlp_ast: dict[str, Any],
        section_name: str,
    ) -> dict[str, str]:
        section = NodeVisitor._optional_mapping(cnlp_ast, section_name)
        if section is None:
            return {}

        normalized: dict[str, str] = {}
        for attribute_name, attribute_value in section.items():
            if not isinstance(attribute_name, str):
                raise TypeError(
                    f"AST section '{section_name}' contains a non-string "
                    "attribute name."
                )
            if not isinstance(attribute_value, dict):
                raise TypeError(
                    f"Static attribute '{section_name}.{attribute_name}' "
                    "must be represented as an object."
                )
            description = attribute_value.get("description")
            if not isinstance(description, str):
                raise TypeError(
                    f"Static attribute '{section_name}.{attribute_name}' "
                    "must contain a string description."
                )

            description = description.strip()
            redundant_prefix = re.compile(
                rf"^{re.escape(attribute_name)}\s*:\s*",
                flags=re.IGNORECASE,
            )
            normalized[attribute_name] = redundant_prefix.sub(
                "",
                description,
                count=1,
            )
        return normalized

    @staticmethod
    def find_all_commands(cnlp_ast: dict[str, Any]) -> list[CommandNode]:
        NodeVisitor._require_ast(cnlp_ast)
        worker = NodeVisitor._optional_mapping(cnlp_ast, "worker")
        if worker is None:
            return []

        variable_lookup = {
            variable["variable_name"]: variable
            for variable in NodeVisitor.find_all_variables(cnlp_ast)
        }
        type_contents = NodeVisitor._type_contents(cnlp_ast)

        commands: list[CommandNode] = []

        def visit(value: Any, path: tuple[str, ...]) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = (*path, key)
                    command_match = _COMMAND_PATTERN.fullmatch(key)

                    if command_match and isinstance(child, dict):
                        raw_command_type = child.get("type")
                        if raw_command_type not in {
                            "request_input",
                            "general_command",
                            "display_message",
                            "call_api",
                        }:
                            raise ValueError(
                                f"Command at '{NodeVisitor._format_path(child_path)}' "
                                f"has an unsupported type: {raw_command_type!r}."
                            )

                        command_type: CommandType = raw_command_type
                        common_fields = {
                            "command_name": key,
                            "command_index": int(command_match.group(1)),
                            "required_variables": (
                                NodeVisitor._command_required_variables(
                                    command_type=command_type,
                                    command=child,
                                )
                            ),
                            "written_variable": (
                                NodeVisitor._command_written_variable(
                                    command_type=command_type,
                                    command=child,
                                )
                            ),
                            "write_operation": (
                                NodeVisitor._command_write_operation(
                                    command_type=command_type,
                                    command=child,
                                )
                            ),
                        }

                        if command_type == "call_api":
                            commands.append(
                                CallAPICommandNode(
                                    **common_fields,
                                    command_type="call_api",
                                    api_name=NodeVisitor._call_api_name(child),
                                    arguments=NodeVisitor._call_api_arguments(
                                        child,
                                        variable_lookup=variable_lookup,
                                        type_contents=type_contents,
                                    ),
                                    response=NodeVisitor._call_api_response(
                                        child,
                                        variable_lookup=variable_lookup,
                                        type_contents=type_contents,
                                    ),
                                )
                            )
                        else:
                            commands.append({
                                **common_fields,
                                "command_type": command_type,
                                "description": NodeVisitor._command_description(
                                    command_type=command_type,
                                    command=child,
                                ),
                            })
                        continue

                    visit(child, child_path)

            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, (*path, f"[{index}]"))

        visit(worker, ("worker",))
        return commands

    @staticmethod
    def _command_description(
        *,
        command_type: CommandType,
        command: dict[str, Any],
    ) -> str:
        description_with_reference = command.get("description_with_reference")
        if not isinstance(description_with_reference, dict):
            raise ValueError(
                f"{command_type} does not contain 'description_with_reference'."
            )

        return NodeVisitor._render_description_with_references(
            description_with_reference,
            source_name=command_type,
        )

    @staticmethod
    def _condition_description(condition: dict[str, Any]) -> str:
        return NodeVisitor._render_description_with_references(
            condition,
            source_name="condition",
        )

    @staticmethod
    def _render_description_with_references(
        description_with_references: dict[str, Any],
        *,
        source_name: str,
    ) -> str:
        description = description_with_references.get("description")
        if not isinstance(description, str):
            raise ValueError(
                f"{source_name} does not contain a string description."
            )

        def replace_reference(match: re.Match[str]) -> str:
            reference_name = f"reference{match.group(1)}"
            reference = description_with_references.get(reference_name)
            if not isinstance(reference, dict):
                raise ValueError(
                    f"Description refers to missing '{reference_name}'."
                )

            var_name = reference.get("var_name")
            if not isinstance(var_name, str):
                raise ValueError(
                    f"'{reference_name}' does not contain a variable name."
                )
            return f" variable: `{var_name}` "

        rendered = re.sub(
            r"<reference(\d+)>",
            replace_reference,
            description,
        )
        return NodeVisitor._normalize_description(rendered)

    @staticmethod
    def _call_api_name(command: dict[str, Any]) -> str:
        api_name = command.get("api_name")
        if not isinstance(api_name, str) or not api_name.strip():
            raise ValueError("call_api does not contain a string 'api_name'.")
        return api_name

    @staticmethod
    def _call_api_arguments(
        command: dict[str, Any],
        *,
        variable_lookup: dict[str, VariableNode],
        type_contents: dict[str, CNLPDataType],
    ) -> list[CallAPIArgumentNode]:
        parameters = command.get("paras")
        if parameters is None:
            return []
        if not isinstance(parameters, dict):
            raise ValueError("call_api 'paras' must be an object.")

        arguments: list[CallAPIArgumentNode] = []
        for parameter_name, parameter in parameters.items():
            if not isinstance(parameter, dict):
                raise ValueError(
                    f"API parameter '{parameter_name}' must be an object."
                )

            argument_name = parameter.get("reference")
            if (
                parameter.get("type") != "reference"
                or not isinstance(argument_name, str)
                or not argument_name
            ):
                raise ValueError(
                    f"API parameter '{parameter_name}' must reference a "
                    "CNL-P variable."
                )

            resolved = NodeVisitor._resolve_variable_reference(
                argument_name,
                variable_lookup=variable_lookup,
                type_contents=type_contents,
            )
            arguments.append(
                CallAPIArgumentNode(
                    parameter_name=parameter_name,
                    argument_name=argument_name,
                    argument_description=resolved["description"],
                    argument_type=resolved["data_type"],
                )
            )

        return arguments

    @staticmethod
    def _call_api_response(
        command: dict[str, Any],
        *,
        variable_lookup: dict[str, VariableNode],
        type_contents: dict[str, CNLPDataType],
    ) -> CallAPIResponseNode | None:
        response = command.get("response")
        if response is None:
            return None
        if not isinstance(response, dict):
            raise ValueError("call_api 'response' must be an object.")

        reference = response.get("reference")
        if not isinstance(reference, dict):
            raise ValueError(
                "call_api response must contain a variable reference."
            )
        variable_name = reference.get("var_name")
        if not isinstance(variable_name, str) or not variable_name:
            raise ValueError(
                "call_api response must contain a non-empty variable name."
            )

        resolved = NodeVisitor._resolve_variable_reference(
            variable_name,
            variable_lookup=variable_lookup,
            type_contents=type_contents,
        )
        return CallAPIResponseNode(
            variable_name=variable_name,
            variable_description=resolved["description"],
            variable_type=resolved["data_type"],
        )

    @staticmethod
    def _resolve_variable_reference(
        variable_reference: str,
        *,
        variable_lookup: dict[str, VariableNode],
        type_contents: dict[str, CNLPDataType],
    ) -> dict[str, str | None | CNLPDataType]:
        """Resolve a CNL-P variable or structured field without LLM use."""
        path = variable_reference.split(".")
        variable_name = path[0]
        try:
            variable = variable_lookup[variable_name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown CNL-P variable reference: {variable_reference!r}."
            ) from exc

        description = variable["description"]
        data_type = copy.deepcopy(variable["data_type"])
        for field_name in path[1:]:
            field = NodeVisitor._find_struct_field(
                data_type=data_type,
                field_name=field_name,
                type_contents=type_contents,
                variable_reference=variable_reference,
            )
            description = field.get("field_comment")
            data_type = copy.deepcopy(field["field_content"])

        return {
            "description": description,
            "data_type": data_type,
        }

    @staticmethod
    def _find_struct_field(
        *,
        data_type: CNLPDataType,
        field_name: str,
        type_contents: dict[str, CNLPDataType],
        variable_reference: str,
    ) -> dict[str, Any]:
        fields: list[dict[str, Any]] | None = None
        if isinstance(data_type, list):
            fields = data_type
        elif isinstance(data_type, dict):
            declared_type_name = data_type.get("declared_type_name")
            if isinstance(declared_type_name, str):
                fields = type_contents.get(declared_type_name)

        if not isinstance(fields, list):
            raise ValueError(
                f"CNL-P reference {variable_reference!r} accesses field "
                f"{field_name!r} on a non-struct type."
            )

        for field in fields:
            if isinstance(field, dict) and field.get("field_name") == field_name:
                if "field_content" not in field:
                    raise ValueError(
                        f"CNL-P struct field {field_name!r} does not "
                        "contain field_content."
                    )
                return field

        raise ValueError(
            f"CNL-P reference {variable_reference!r} has no field "
            f"{field_name!r}."
        )

    @staticmethod
    def _type_contents(
        cnlp_ast: dict[str, Any],
    ) -> dict[str, CNLPDataType]:
        return {
            cnlp_type["type_name"]: copy.deepcopy(cnlp_type["type_content"])
            for cnlp_type in NodeVisitor.find_all_types(cnlp_ast)
        }

    @staticmethod
    def _normalize_description(description: str) -> str:
        description = re.sub(r"\s+", " ", description).strip()
        return re.sub(r"\s+([,.;!?])", r"\1", description)

    @staticmethod
    def _command_required_variables(
        *,
        command_type: CommandType,
        command: dict[str, Any],
    ) -> list[str]:
        if command_type == "call_api":
            source = command.get("paras")
        else:
            source = command.get("description_with_reference")

        return NodeVisitor._find_referenced_variables(source)

    @staticmethod
    def _command_written_variable(
        *,
        command_type: CommandType,
        command: dict[str, Any],
    ) -> str | None:
        if command_type == "request_input":
            target = command.get("value")
        elif command_type == "general_command":
            target = command.get("result")
        elif command_type == "call_api":
            target = command.get("response")
        else:
            return None

        referenced_variables = NodeVisitor._find_referenced_variables(target)
        if not referenced_variables:
            return None
        if len(referenced_variables) != 1:
            raise ValueError(
                f"{command_type} must write exactly one variable; received "
                f"{referenced_variables!r}."
            )
        return referenced_variables[0]

    @staticmethod
    def _command_write_operation(
        *,
        command_type: CommandType,
        command: dict[str, Any],
    ) -> WriteOperation | None:
        if command_type == "request_input":
            target = command.get("value")
        elif command_type == "general_command":
            target = command.get("result")
        elif command_type == "call_api":
            target = command.get("response")
        else:
            return None

        if target is None:
            return None
        if not isinstance(target, dict):
            raise ValueError(
                f"{command_type} write target must be an object."
            )

        operation = target.get("operation")
        if operation not in {"SET", "APPEND"}:
            raise ValueError(
                f"{command_type} has an unsupported write operation: "
                f"{operation!r}."
            )
        return operation

    @staticmethod
    def _find_referenced_variables(value: Any) -> list[str]:
        variables: list[str] = []

        def add(variable_reference: str) -> None:
            variable_name = variable_reference.split(".", 1)[0]
            if variable_name and variable_name not in variables:
                variables.append(variable_name)

        def visit(current: Any) -> None:
            if isinstance(current, dict):
                var_name = current.get("var_name")
                if isinstance(var_name, str):
                    add(var_name)

                if (
                    current.get("type") == "reference"
                    and isinstance(current.get("reference"), str)
                ):
                    add(current["reference"])

                for child in current.values():
                    visit(child)
            elif isinstance(current, list):
                for child in current:
                    visit(child)

        visit(value)
        return variables

    @staticmethod
    def find_all_conditions(cnlp_ast: dict[str, Any]) -> list[ConditionNode]:
        NodeVisitor._require_ast(cnlp_ast)
        worker = NodeVisitor._optional_mapping(cnlp_ast, "worker")
        if worker is None:
            return []

        conditions: list[ConditionNode] = []

        def add_condition(
            *,
            owner_name: str,
            condition_kind: ConditionKind,
            owner: dict[str, Any],
            owner_path: tuple[str, ...],
        ) -> None:
            condition = owner.get("condition")
            if not isinstance(condition, dict):
                return

            predicate_index = len(conditions) + 1
            conditions.append(
                ConditionNode(
                    predicate_name=f"predicate{predicate_index}",
                    predicate_index=predicate_index,
                    condition_kind=condition_kind,
                    owner_name=owner_name,
                    condition_path=list(owner_path),
                    description=NodeVisitor._condition_description(condition),
                    required_variables=NodeVisitor._find_referenced_variables(
                        condition
                    ),
                )
            )

        def visit(value: Any, path: tuple[str, ...]) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = (*path, key)

                    if not isinstance(child, dict):
                        visit(child, child_path)
                        continue

                    if _ALTERNATIVE_FLOW_PATTERN.fullmatch(key):
                        add_condition(
                            owner_name=key,
                            condition_kind="alternative_flow",
                            owner=child,
                            owner_path=child_path,
                        )
                        visit_without_condition(child, child_path)
                        continue

                    if _EXCEPTION_FLOW_PATTERN.fullmatch(key):
                        add_condition(
                            owner_name=key,
                            condition_kind="exception_flow",
                            owner=child,
                            owner_path=child_path,
                        )
                        visit_without_condition(child, child_path)
                        continue

                    if _IF_BLOCK_PATTERN.fullmatch(key):
                        visit_if_block(child, child_path)
                        continue

                    if _WHILE_BLOCK_PATTERN.fullmatch(key):
                        add_condition(
                            owner_name=key,
                            condition_kind="while",
                            owner=child,
                            owner_path=child_path,
                        )
                        visit_without_condition(child, child_path)
                        continue

                    if _FOR_BLOCK_PATTERN.fullmatch(key):
                        add_condition(
                            owner_name=key,
                            condition_kind="for",
                            owner=child,
                            owner_path=child_path,
                        )
                        visit_without_condition(child, child_path)
                        continue

                    visit(child, child_path)

            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, (*path, f"[{index}]"))

        def visit_without_condition(
            owner: dict[str, Any],
            owner_path: tuple[str, ...],
        ) -> None:
            for key, child in owner.items():
                if key == "condition":
                    continue
                # Preserve the child key so ``visit`` can classify an
                # immediately nested If/While/For block. Passing only the
                # child value loses the block identity and previously omitted
                # predicates such as Alternative Flow -> While.
                visit({key: child}, owner_path)

        def visit_if_block(
            if_block: dict[str, Any],
            if_block_path: tuple[str, ...],
        ) -> None:
            for branch_name, branch in if_block.items():
                branch_match = _IF_BRANCH_PATTERN.fullmatch(branch_name)
                branch_path = (*if_block_path, branch_name)

                if branch_match and isinstance(branch, dict):
                    branch_number = int(branch_match.group(1))
                    add_condition(
                        owner_name=branch_name,
                        condition_kind="if" if branch_number == 1 else "elseif",
                        owner=branch,
                        owner_path=branch_path,
                    )
                    visit_without_condition(branch, branch_path)
                    continue

                visit(branch, branch_path)

        visit(worker, ("worker",))
        return conditions

    @staticmethod
    def find_workflow_structure(
        cnlp_ast: dict[str, Any],
    ) -> WorkflowStructure:
        """
        Extract the ordered Worker control structure without semantic planning.

        Decision indices already present in the AST are preserved. Missing
        indices are assigned mechanically in structural traversal order.
        """
        NodeVisitor._require_ast(cnlp_ast)
        worker = NodeVisitor._optional_mapping(cnlp_ast, "worker")
        if worker is None:
            raise ValueError(
                "A Worker AST is required to extract workflow structure."
            )
        # Workflow extraction needs normalized Decision identities, but the
        # normalizer itself belongs to FlowBinder rather than this query API.
        from ..flow_binder.decision_indexer import (
            build_decision_indexed_worker_ast,
        )

        worker = build_decision_indexed_worker_ast(worker)

        used_decision_indices: set[int] = set()
        next_decision_index = 1

        def reserve_decision_index(block: dict[str, Any]) -> int:
            nonlocal next_decision_index

            raw_index = block.get("decision_index")
            if raw_index is None:
                while next_decision_index in used_decision_indices:
                    next_decision_index += 1
                decision_index = next_decision_index
                next_decision_index += 1
            else:
                decision_index = NodeVisitor._coerce_decision_index(
                    raw_index
                )

            if decision_index in used_decision_indices:
                raise ValueError(
                    f"Duplicate decision_index: {decision_index}."
                )
            used_decision_indices.add(decision_index)
            return decision_index

        def extract_steps(
            container: dict[str, Any],
            container_path: tuple[str, ...],
        ) -> list[WorkflowStep]:
            steps: list[WorkflowStep] = []

            for key, child in container.items():
                child_path = (*container_path, key)
                command_match = _COMMAND_PATTERN.fullmatch(key)
                if command_match:
                    if not isinstance(child, dict):
                        raise TypeError(
                            f"Command at "
                            f"'{NodeVisitor._format_path(child_path)}' "
                            "must be represented as an object."
                        )
                    steps.append(
                        WorkflowCommandStep(
                            step_type="command",
                            command_name=key,
                            command_index=int(command_match.group(1)),
                            command_path=list(child_path),
                        )
                    )
                    continue

                if not isinstance(child, dict):
                    continue

                if _IF_BLOCK_PATTERN.fullmatch(key):
                    steps.append(
                        extract_if_step(child, child_path)
                    )
                    continue

                if _WHILE_BLOCK_PATTERN.fullmatch(key):
                    steps.append(
                        extract_loop_step(
                            child,
                            child_path,
                            step_type="while",
                        )
                    )
                    continue

                if _FOR_BLOCK_PATTERN.fullmatch(key):
                    steps.append(
                        extract_loop_step(
                            child,
                            child_path,
                            step_type="for",
                        )
                    )
                    continue

                steps.extend(extract_steps(child, child_path))

            return steps

        def extract_if_step(
            if_block: dict[str, Any],
            block_path: tuple[str, ...],
        ) -> WorkflowIfStep:
            decision_index = reserve_decision_index(if_block)
            indexed_branches: list[
                tuple[int, str, dict[str, Any]]
            ] = []
            else_branch: tuple[str, dict[str, Any]] | None = None

            for branch_name, branch in if_block.items():
                if branch_name == "decision_index":
                    continue
                branch_match = _IF_BRANCH_PATTERN.fullmatch(branch_name)
                if branch_match:
                    if not isinstance(branch, dict):
                        raise TypeError(
                            f"If branch {branch_name!r} must be an object."
                        )
                    indexed_branches.append(
                        (
                            int(branch_match.group(1)),
                            branch_name,
                            branch,
                        )
                    )
                    continue
                if branch_name == "else_branch":
                    if not isinstance(branch, dict):
                        raise TypeError(
                            "else_branch must be represented as an object."
                        )
                    else_branch = (branch_name, branch)

            indexed_branches.sort(key=lambda item: item[0])
            if (
                not indexed_branches
                or indexed_branches[0][0] != 1
            ):
                raise ValueError(
                    f"If Block '{NodeVisitor._format_path(block_path)}' "
                    "must contain if_branch1."
                )

            branches: list[WorkflowBranch] = []
            for branch_index, branch_name, branch in indexed_branches:
                branch_path = (*block_path, branch_name)
                if not isinstance(branch.get("condition"), dict):
                    raise ValueError(
                        f"If branch "
                        f"'{NodeVisitor._format_path(branch_path)}' "
                        "must contain a condition."
                    )
                branches.append(
                    WorkflowBranch(
                        branch_type=(
                            "if" if branch_index == 1 else "elseif"
                        ),
                        branch_path=list(branch_path),
                        predicate_path=list(branch_path),
                        steps=extract_steps(branch, branch_path),
                    )
                )

            if else_branch is not None:
                branch_name, branch = else_branch
                branch_path = (*block_path, branch_name)
                branches.append(
                    WorkflowBranch(
                        branch_type="else",
                        branch_path=list(branch_path),
                        predicate_path=None,
                        steps=extract_steps(branch, branch_path),
                    )
                )

            return WorkflowIfStep(
                step_type="if",
                decision_index=decision_index,
                block_path=list(block_path),
                branches=branches,
            )

        def extract_loop_step(
            loop_block: dict[str, Any],
            block_path: tuple[str, ...],
            *,
            step_type: str,
        ) -> WorkflowLoopStep:
            if not isinstance(loop_block.get("condition"), dict):
                raise ValueError(
                    f"Loop Block '{NodeVisitor._format_path(block_path)}' "
                    "must contain a condition."
                )
            if step_type not in {"while", "for"}:
                raise ValueError(
                    f"Unsupported workflow loop type: {step_type!r}."
                )

            return WorkflowLoopStep(
                step_type=step_type,
                decision_index=reserve_decision_index(loop_block),
                block_path=list(block_path),
                predicate_path=list(block_path),
                body_steps=extract_steps(loop_block, block_path),
            )

        def find_flows(
            value: Any,
            path: tuple[str, ...],
        ) -> tuple[
            list[tuple[str, dict[str, Any], tuple[str, ...]]],
            list[tuple[str, dict[str, Any], tuple[str, ...]]],
            list[tuple[str, dict[str, Any], tuple[str, ...]]],
        ]:
            main_flows: list[
                tuple[str, dict[str, Any], tuple[str, ...]]
            ] = []
            alternative_flows: list[
                tuple[str, dict[str, Any], tuple[str, ...]]
            ] = []
            exception_flows: list[
                tuple[str, dict[str, Any], tuple[str, ...]]
            ] = []

            if not isinstance(value, dict):
                return main_flows, alternative_flows, exception_flows

            for key, child in value.items():
                child_path = (*path, key)
                if not isinstance(child, dict):
                    continue
                flow_record = (key, child, child_path)

                if key == "main_flow":
                    main_flows.append(flow_record)
                    continue
                if _ALTERNATIVE_FLOW_PATTERN.fullmatch(key):
                    alternative_flows.append(flow_record)
                    continue
                if _EXCEPTION_FLOW_PATTERN.fullmatch(key):
                    exception_flows.append(flow_record)
                    continue

                nested = find_flows(child, child_path)
                main_flows.extend(nested[0])
                alternative_flows.extend(nested[1])
                exception_flows.extend(nested[2])

            return main_flows, alternative_flows, exception_flows

        main_flows, alternative_flows, exception_flows = find_flows(
            worker,
            ("worker",),
        )
        if len(main_flows) != 1:
            raise ValueError(
                "Worker workflow structure requires exactly one main_flow; "
                f"found {len(main_flows)}."
            )

        def make_flow(
            record: tuple[str, dict[str, Any], tuple[str, ...]],
            *,
            flow_type: str,
        ) -> WorkflowFlow:
            flow_name, flow, flow_path = record
            if flow_type not in {
                "main_flow",
                "alternative_flow",
                "exception_flow",
            }:
                raise ValueError(
                    f"Unsupported workflow flow type: {flow_type!r}."
                )
            predicate_path = (
                None
                if flow_type == "main_flow"
                else list(flow_path)
            )
            if (
                predicate_path is not None
                and not isinstance(flow.get("condition"), dict)
            ):
                raise ValueError(
                    f"Flow '{NodeVisitor._format_path(flow_path)}' "
                    "must contain a condition."
                )

            return WorkflowFlow(
                flow_name=flow_name,
                flow_type=flow_type,
                flow_path=list(flow_path),
                predicate_path=predicate_path,
                steps=extract_steps(flow, flow_path),
            )

        return WorkflowStructure(
            main_flow=make_flow(
                main_flows[0],
                flow_type="main_flow",
            ),
            alternative_flows=[
                make_flow(record, flow_type="alternative_flow")
                for record in alternative_flows
            ],
            exception_flows=[
                make_flow(record, flow_type="exception_flow")
                for record in exception_flows
            ],
        )

    @staticmethod
    def find_all_variables(cnlp_ast: dict[str, Any]) -> list[VariableNode]:
        NodeVisitor._require_ast(cnlp_ast)
        variables = NodeVisitor._optional_mapping(cnlp_ast, "variables")
        if variables is None:
            return []

        results: list[VariableNode] = []
        for variable_name, variable in variables.items():
            if not isinstance(variable, dict):
                raise TypeError(
                    f"Variable '{variable_name}' must be represented as an object."
                )

            # TODO(planner-declared-types): Resolve a data_type containing only
            # {"declared_type_name": "..."} into its complete declared type
            # definition, or attach an equivalent normalized type registry to
            # the planner input. This resolution must remain in NodeVisitor so
            # command and predicate analyzers never need to inspect the AST.
            results.append(
                VariableNode(
                    variable_name=variable.get("variable_name", variable_name),
                    description=copy.deepcopy(variable.get("description")),
                    data_type=copy.deepcopy(variable.get("data_type")),
                    default_value=copy.deepcopy(variable.get("default_value")),
                )
            )

        return results

    @staticmethod
    def find_all_types(cnlp_ast: dict[str, Any]) -> list[CNLPTypeIR]:
        """Return normalized copies of the type declarations in source order."""
        NodeVisitor._require_ast(cnlp_ast)
        types = NodeVisitor._optional_mapping(cnlp_ast, "types")
        if types is None:
            return []

        results: list[CNLPTypeIR] = []
        for declared_name, type_ir in types.items():
            if not isinstance(type_ir, dict):
                raise TypeError(
                    f"Type '{declared_name}' must be represented as an object."
                )

            type_name = type_ir.get("type_name", declared_name)
            if not isinstance(type_name, str) or not type_name:
                raise TypeError(
                    f"Type '{declared_name}' must contain a non-empty type name."
                )
            if type_name != declared_name:
                raise ValueError(
                    f"Type section key '{declared_name}' does not match "
                    f"its type_name '{type_name}'."
                )
            if "type_content" not in type_ir:
                raise ValueError(
                    f"Type '{declared_name}' does not contain 'type_content'."
                )

            type_comment = type_ir.get("type_comment")
            if type_comment is not None and not isinstance(type_comment, str):
                raise TypeError(
                    f"Type '{declared_name}' comment must be a string or None."
                )

            results.append(
                CNLPTypeIR(
                    type_name=type_name,
                    type_comment=copy.deepcopy(type_comment),
                    type_content=copy.deepcopy(type_ir["type_content"]),
                )
            )

        return results

    @staticmethod
    def _require_ast(cnlp_ast: dict[str, Any]) -> None:
        if not isinstance(cnlp_ast, dict):
            raise TypeError("cnlp_ast must be a dictionary.")

    @staticmethod
    def _coerce_decision_index(value: Any) -> int:
        if isinstance(value, bool):
            raise ValueError(
                "Boolean values cannot be used as decision_index."
            )
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str):
            match = re.search(r"(\d+)$", value.strip())
            if match and int(match.group(1)) > 0:
                return int(match.group(1))
        raise ValueError(f"Invalid decision_index value: {value!r}.")

    @staticmethod
    def _optional_mapping(
        cnlp_ast: dict[str, Any],
        section_name: str,
    ) -> dict[str, Any] | None:
        section = cnlp_ast.get(section_name)
        if section is None:
            return None
        if not isinstance(section, dict):
            raise TypeError(
                f"AST section '{section_name}' must be represented as an object."
            )
        return section

    @staticmethod
    def _format_path(path: tuple[str, ...]) -> str:
        result = ""
        for segment in path:
            if segment.startswith("["):
                result += segment
            else:
                result = f"{result}.{segment}" if result else segment
        return result
