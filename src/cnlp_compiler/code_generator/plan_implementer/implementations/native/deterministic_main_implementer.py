from __future__ import annotations

import re
from typing import Any

from .....schema import WorkflowStep, WorkflowStructure
from ...schema import GeneratedFile
from .schema import CommandFunctionNames, PredicateNamingTable


END_PC = "__end__"


class DeterministicMainImplementer:
    """Generate Native Worker control code without a compiler-time LLM."""

    def implement(
        self,
        *,
        worker_name: str,
        workflow_structure: WorkflowStructure,
        binding_table: dict[str, Any],
        command_function_names: CommandFunctionNames,
        predicate_naming_table: PredicateNamingTable,
    ) -> GeneratedFile:
        """Turn normalized structure and Flow bindings into a PC machine."""
        specification = _ControlFlowSpecBuilder(
            worker_name=worker_name,
            workflow_structure=workflow_structure,
            binding_table=binding_table,
            predicate_naming_table=predicate_naming_table,
            expected_command_names=command_function_names,
        ).build()
        content = _render_main_module(
            specification=specification,
            command_function_names=command_function_names,
            predicate_naming_table=predicate_naming_table,
        )
        compile(content, "main.py", "exec")
        return {
            "relative_path": "main.py",
            "content": content,
            "write_type": "rewrite",
        }


class _ControlFlowSpecBuilder:
    """Mechanically compile Workflow Structure plus FlowBinder output."""

    def __init__(
        self,
        *,
        worker_name: str,
        workflow_structure: WorkflowStructure,
        binding_table: dict[str, Any],
        predicate_naming_table: PredicateNamingTable,
        expected_command_names: CommandFunctionNames,
    ) -> None:
        self.worker_name = worker_name
        self.workflow = workflow_structure
        self.binding = binding_table
        self.predicate_table = predicate_naming_table
        self.expected_command_names = expected_command_names
        self.nodes: dict[str, dict[str, str]] = {}
        self.routes: dict[str, dict[str, Any]] = {}
        self.main_commands: dict[int, str] = {}
        self.main_decisions: dict[int, str] = {}
        self.main_decision_paths: dict[int, str] = {}

    def build(self) -> dict[str, Any]:
        self._validate_symbol_tables()
        self._index_main_targets(self.workflow["main_flow"]["steps"])
        self._validate_binding_structure()
        flow_entries = self._compile_secondary_flows()
        trigger_routes = self._build_trigger_routes(flow_entries)
        entry = self._compile_steps(
            self.workflow["main_flow"]["steps"],
            successor=END_PC,
            main_trigger_routes=trigger_routes,
        )
        self._validate_compiled_specification(entry)
        return {
            "entry": entry,
            "nodes": self.nodes,
            "routes": self.routes,
        }

    def _validate_symbol_tables(self) -> None:
        workflow_commands = [
            step["command_name"]
            for flow in _all_flows(self.workflow)
            for step in _walk_steps(flow["steps"])
            if step["step_type"] == "command"
        ]
        if (
            len(self.expected_command_names)
            != len(set(self.expected_command_names))
            or set(self.expected_command_names) != set(workflow_commands)
        ):
            raise ValueError(
                f"Worker {self.worker_name!r} Command function names do not "
                "match its Workflow Structure."
            )

        expected_predicate_paths = _collect_predicate_paths(self.workflow)
        if set(self.predicate_table) != set(expected_predicate_paths):
            missing_paths = sorted(
                set(expected_predicate_paths) - set(self.predicate_table)
            )
            extra_paths = sorted(
                set(self.predicate_table) - set(expected_predicate_paths)
            )
            raise ValueError(
                f"Worker {self.worker_name!r} Predicate naming table does not "
                "match its Workflow Structure: "
                f"missing={missing_paths}, extra={extra_paths}."
            )
        predicate_names = list(self.predicate_table.values())
        if len(predicate_names) != len(set(predicate_names)):
            raise ValueError(
                f"Worker {self.worker_name!r} Predicate function names must "
                "be unique."
            )

    def _index_main_targets(self, steps: list[WorkflowStep]) -> None:
        for step in _walk_steps(steps):
            step_type = step["step_type"]
            if step_type == "command":
                command_index = step["command_index"]
                if command_index in self.main_commands:
                    raise ValueError(
                        f"Worker {self.worker_name!r} has duplicate Main Flow "
                        f"Command index {command_index}."
                    )
                self.main_commands[command_index] = step["command_name"]
            elif step_type in {"if", "while", "for"}:
                decision_index = step["decision_index"]
                if decision_index in self.main_decisions:
                    raise ValueError(
                        f"Worker {self.worker_name!r} has duplicate Decision "
                        f"index {decision_index}."
                    )
                self.main_decisions[decision_index] = self._decision_pc(
                    decision_index
                )
                self.main_decision_paths[decision_index] = ".".join(
                    step["block_path"]
                )

    def _validate_binding_structure(self) -> None:
        expected_main_path = ".".join(
            self.workflow["main_flow"]["flow_path"]
        )
        if self.binding.get("main_flow_path") != expected_main_path:
            raise ValueError(
                f"Worker {self.worker_name!r} binding main_flow_path does "
                "not match its Workflow Structure."
            )

        raw_decision_paths = self.binding.get("decision_path_table")
        if not isinstance(raw_decision_paths, dict):
            raise ValueError(
                "Flow binding requires a decision_path_table object."
            )
        decision_paths = {
            int(index): path for index, path in raw_decision_paths.items()
        }
        if decision_paths != self.main_decision_paths:
            raise ValueError(
                f"Worker {self.worker_name!r} Decision bindings do not "
                "match its Main Flow Decisions."
            )

        self._validate_flow_binding_family(flow_key="alternative_flows")
        self._validate_flow_binding_family(flow_key="exception_flows")

    def _validate_flow_binding_family(self, *, flow_key: str) -> None:
        workflow_flows = self.workflow[flow_key]
        bindings = self.binding.get(flow_key)
        if not isinstance(bindings, list):
            raise ValueError(f"Flow binding {flow_key} must be a list.")
        expected = [
            (flow["flow_name"], ".".join(flow["flow_path"]))
            for flow in workflow_flows
        ]
        actual = [
            (binding.get("flow_name"), binding.get("flow_path"))
            for binding in bindings
        ]
        if actual != expected:
            raise ValueError(
                f"Worker {self.worker_name!r} {flow_key} bindings do not "
                "match the Workflow declaration order."
            )

    def _compile_secondary_flows(self) -> dict[str, str]:
        entries: dict[str, str] = {}
        for flow in self.workflow["exception_flows"]:
            entries[flow["flow_name"]] = self._compile_steps(
                flow["steps"],
                successor=END_PC,
                main_trigger_routes=None,
            )

        alternative_bindings = {
            binding["flow_name"]: binding
            for binding in self.binding["alternative_flows"]
        }
        for flow in self.workflow["alternative_flows"]:
            binding = alternative_bindings.get(flow["flow_name"])
            if binding is None:
                raise ValueError(
                    f"Alternative Flow {flow['flow_name']!r} has no binding."
                )
            entries[flow["flow_name"]] = self._compile_steps(
                flow["steps"],
                successor=self._resolve_go_back(binding.get("go_back_to")),
                main_trigger_routes=None,
            )
        return entries

    def _build_trigger_routes(
        self,
        flow_entries: dict[str, str],
    ) -> dict[int, list[dict[str, str]]]:
        routes: dict[int, list[dict[str, str]]] = {}
        flows = {
            flow["flow_name"]: flow for flow in _all_secondary_flows(self.workflow)
        }
        # Exception Flow has priority; declaration order is preserved inside
        # each family. Only the first satisfied Predicate is selected.
        ordered_bindings = [
            *self.binding["exception_flows"],
            *self.binding["alternative_flows"],
        ]
        for binding in ordered_bindings:
            flow_name = binding.get("flow_name")
            flow = flows.get(flow_name)
            if flow is None:
                raise ValueError(
                    f"Flow binding references unknown Flow {flow_name!r}."
                )
            predicate_path = flow["predicate_path"]
            if predicate_path is None:
                raise ValueError(
                    f"Secondary Flow {flow_name!r} requires a Predicate."
                )
            predicate_name = self._predicate_name(predicate_path)
            triggers = binding.get("trigger_is")
            if not isinstance(triggers, list) or not triggers:
                raise ValueError(
                    f"Secondary Flow {flow_name!r} requires trigger_is."
                )
            for trigger in triggers:
                if trigger.get("index_type") != "command":
                    raise ValueError(
                        "Flow trigger_is can only reference Main Flow Commands."
                    )
                command_index = trigger.get("index")
                if command_index not in self.main_commands:
                    raise ValueError(
                        "Flow trigger references unknown Main Flow Command "
                        f"{command_index!r}."
                    )
                routes.setdefault(command_index, []).append(
                    {
                        "predicate": predicate_name,
                        "target": flow_entries[flow_name],
                    }
                )
        return routes

    def _compile_steps(
        self,
        steps: list[WorkflowStep],
        *,
        successor: str,
        main_trigger_routes: dict[int, list[dict[str, str]]] | None,
    ) -> str:
        current = successor
        for step in reversed(steps):
            step_type = step["step_type"]
            if step_type == "command":
                node_name = step["command_name"]
                self._add_node(
                    node_name,
                    {"kind": "command", "function": node_name},
                )
                choices = (
                    main_trigger_routes.get(step["command_index"], [])
                    if main_trigger_routes is not None
                    else []
                )
                self._set_route(
                    node_name,
                    (
                        {
                            "kind": "predicate",
                            "choices": choices,
                            "default": current,
                        }
                        if choices
                        else {"kind": "direct", "target": current}
                    ),
                )
                current = node_name
                continue

            if step_type == "if":
                node_name = self._decision_pc(step["decision_index"])
                self._add_node(node_name, {"kind": "decision"})
                choices: list[dict[str, str]] = []
                default_target = current
                for branch in step["branches"]:
                    branch_entry = self._compile_steps(
                        branch["steps"],
                        successor=current,
                        main_trigger_routes=main_trigger_routes,
                    )
                    if branch["branch_type"] == "else":
                        default_target = branch_entry
                    else:
                        predicate_path = branch["predicate_path"]
                        if predicate_path is None:
                            raise ValueError(
                                "If/ElseIf branch requires a Predicate path."
                            )
                        choices.append(
                            {
                                "predicate": self._predicate_name(
                                    predicate_path
                                ),
                                "target": branch_entry,
                            }
                        )
                self._set_route(
                    node_name,
                    {
                        "kind": "predicate",
                        "choices": choices,
                        "default": default_target,
                    },
                )
                current = node_name
                continue

            if step_type in {"while", "for"}:
                node_name = self._decision_pc(step["decision_index"])
                self._add_node(node_name, {"kind": "decision"})
                body_entry = self._compile_steps(
                    step["body_steps"],
                    successor=node_name,
                    main_trigger_routes=main_trigger_routes,
                )
                self._set_route(
                    node_name,
                    {
                        "kind": "predicate",
                        "choices": [
                            {
                                "predicate": self._predicate_name(
                                    step["predicate_path"]
                                ),
                                "target": body_entry,
                            }
                        ],
                        "default": current,
                    },
                )
                current = node_name
                continue

            raise ValueError(
                f"Unsupported Workflow step type: {step_type!r}."
            )
        return current

    def _resolve_go_back(self, go_back_to: Any) -> str:
        if not isinstance(go_back_to, dict):
            raise ValueError("Alternative Flow requires go_back_to.")
        index_type = go_back_to.get("index_type")
        index = go_back_to.get("index")
        if index_type == "command" and index in self.main_commands:
            return self.main_commands[index]
        if index_type == "decision" and index in self.main_decisions:
            return self.main_decisions[index]
        raise ValueError(
            "Alternative Flow go_back_to references unknown "
            f"{index_type}{index}."
        )

    def _predicate_name(self, path: list[str]) -> str:
        canonical_path = ".".join(path)
        try:
            return self.predicate_table[canonical_path]
        except KeyError as exc:
            raise ValueError(
                f"No generated Predicate matches {canonical_path!r}."
            ) from exc

    def _decision_pc(self, decision_index: int) -> str:
        return f"{_python_slug(self.worker_name)}__decision_{decision_index}"

    def _add_node(self, node_name: str, specification: dict[str, str]) -> None:
        existing = self.nodes.get(node_name)
        if existing is not None and existing != specification:
            raise ValueError(
                f"PC state {node_name!r} has conflicting definitions."
            )
        self.nodes[node_name] = specification

    def _set_route(self, node_name: str, route: dict[str, Any]) -> None:
        if node_name in self.routes:
            raise ValueError(
                f"PC state {node_name!r} has multiple routing modes."
            )
        self.routes[node_name] = route

    def _validate_compiled_specification(self, entry: str) -> None:
        if entry != END_PC and entry not in self.nodes:
            raise ValueError(
                f"Worker {self.worker_name!r} entry PC does not exist."
            )
        actual_commands = [
            node["function"]
            for node in self.nodes.values()
            if node["kind"] == "command"
        ]
        if set(actual_commands) != set(self.expected_command_names):
            raise ValueError(
                f"Worker {self.worker_name!r} compiled Commands do not "
                "match its Workflow."
            )
        if set(self.routes) != set(self.nodes):
            raise ValueError(
                f"Worker {self.worker_name!r} contains PC states without routes."
            )
        for route in self.routes.values():
            targets = (
                [route["target"]]
                if route["kind"] == "direct"
                else [
                    route["default"],
                    *(choice["target"] for choice in route["choices"]),
                ]
            )
            unknown_targets = {
                target
                for target in targets
                if target != END_PC and target not in self.nodes
            }
            if unknown_targets:
                raise ValueError(
                    "PC routes reference unknown states: "
                    f"{sorted(unknown_targets)}."
                )


def _render_main_module(
    *,
    specification: dict[str, Any],
    command_function_names: CommandFunctionNames,
    predicate_naming_table: PredicateNamingTable,
) -> str:
    command_import = _render_import("commands", command_function_names)
    predicate_import = _render_import(
        "predicates",
        list(predicate_naming_table.values()),
    )
    cases = []
    for pc_name, node in specification["nodes"].items():
        lines = [f"            case {pc_name!r}:"]
        if node["kind"] == "command":
            lines.append(
                f"                {node['function']}(state, llm_client)"
            )
        lines.extend(_render_route(specification["routes"][pc_name]))
        lines.append("                continue")
        cases.append("\n".join(lines))

    if not cases:
        cases.append("            case _:\n                break")
    else:
        cases.append(
            "            case _:\n"
            "                raise RuntimeError(f\"Unknown program counter: {pc!r}\")"
        )

    return f'''{command_import}
{predicate_import}
from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient


def main(
    *,
    state: AgentState | None = None,
    llm_client: OpenAIClient | None = None,
) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG["model_config"])

    pc = {specification['entry']!r}
    while pc != {END_PC!r}:
        match pc:
{chr(10).join(cases)}

    return state


if __name__ == "__main__":
    main()
'''


def _render_route(route: dict[str, Any]) -> list[str]:
    if route["kind"] == "direct":
        return [f"                pc = {route['target']!r}"]

    choices = route["choices"]
    lines: list[str] = []
    for index, choice in enumerate(choices):
        keyword = "if" if index == 0 else "elif"
        lines.append(
            f"                {keyword} "
            f"{choice['predicate']}(state, llm_client):"
        )
        lines.append(f"                    pc = {choice['target']!r}")
    if choices:
        lines.append("                else:")
        lines.append(f"                    pc = {route['default']!r}")
    else:
        lines.append(f"                pc = {route['default']!r}")
    return lines


def _render_import(module_name: str, names: list[str]) -> str:
    if not names:
        return ""
    lines = [f"from .{module_name} import ("]
    lines.extend(f"    {name}," for name in names)
    lines.append(")")
    return "\n".join(lines)


def _all_flows(workflow: WorkflowStructure):
    yield workflow["main_flow"]
    yield from workflow["alternative_flows"]
    yield from workflow["exception_flows"]


def _all_secondary_flows(workflow: WorkflowStructure):
    yield from workflow["exception_flows"]
    yield from workflow["alternative_flows"]


def _walk_steps(steps: list[WorkflowStep]):
    for step in steps:
        yield step
        if step["step_type"] == "if":
            for branch in step["branches"]:
                yield from _walk_steps(branch["steps"])
        elif step["step_type"] in {"while", "for"}:
            yield from _walk_steps(step["body_steps"])


def _collect_predicate_paths(workflow: WorkflowStructure) -> list[str]:
    paths: list[str] = []
    for flow in _all_flows(workflow):
        if flow["predicate_path"] is not None:
            paths.append(".".join(flow["predicate_path"]))
        for step in _walk_steps(flow["steps"]):
            if step["step_type"] == "if":
                for branch in step["branches"]:
                    if branch["predicate_path"] is not None:
                        paths.append(".".join(branch["predicate_path"]))
            elif step["step_type"] in {"while", "for"}:
                paths.append(".".join(step["predicate_path"]))
    return paths


def _python_slug(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    if not slug:
        raise ValueError(f"Worker name cannot form a Python name: {name!r}.")
    return f"w_{slug}" if slug[0].isdigit() else slug
