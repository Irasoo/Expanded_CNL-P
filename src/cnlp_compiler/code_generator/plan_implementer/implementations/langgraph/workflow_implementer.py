from __future__ import annotations

import json
import re
from typing import Any

from .....schema import WorkflowStep, WorkflowStructure
from ...schema import GeneratedFile


END_NODE = "__end__"


class WorkflowGraphImplementer:
    """Compile normalized Worker workflows into executable LangGraph code."""

    def implement(
        self,
        *,
        entry_worker: str,
        workflow_structures: dict[str, WorkflowStructure],
        binding_tables: dict[str, dict[str, Any]],
        command_names_by_worker: dict[str, list[str]],
        predicate_naming_table: dict[str, str],
    ) -> tuple[GeneratedFile, GeneratedFile, GeneratedFile]:
        specs = {
            worker_name: _WorkerGraphSpecBuilder(
                worker_name=worker_name,
                workflow_structure=workflow_structure,
                binding_table=binding_tables[worker_name],
                predicate_naming_table=predicate_naming_table,
                expected_command_names=command_names_by_worker[worker_name],
            ).build()
            for worker_name, workflow_structure in workflow_structures.items()
        }
        if entry_worker not in specs:
            raise ValueError(
                f"Entry Worker {entry_worker!r} has no LangGraph specification."
            )

        command_names = [
            command_name
            for worker_name in workflow_structures
            for command_name in command_names_by_worker[worker_name]
        ]
        predicate_names = list(predicate_naming_table.values())
        workflow_source = _render_workflow_module(
            graph_specs=specs,
            command_names=command_names,
            predicate_names=predicate_names,
        )
        main_source = _render_main_module(entry_worker)
        requirements_source = (
            "langgraph>=1.0,<2.0\n"
            "openai>=1.0\n"
            "pydantic>=2.0\n"
            "typing-extensions>=4.0\n"
        )
        compile(workflow_source, "workflow.py", "exec")
        compile(main_source, "main.py", "exec")
        return (
            {
                "relative_path": "workflow.py",
                "content": workflow_source,
                "write_type": "rewrite",
            },
            {
                "relative_path": "main.py",
                "content": main_source,
                "write_type": "rewrite",
            },
            {
                "relative_path": "requirements.txt",
                "content": requirements_source,
                "write_type": "rewrite",
            },
        )


class _WorkerGraphSpecBuilder:
    def __init__(
        self,
        *,
        worker_name: str,
        workflow_structure: WorkflowStructure,
        binding_table: dict[str, Any],
        predicate_naming_table: dict[str, str],
        expected_command_names: list[str],
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
        self._index_main_targets(self.workflow["main_flow"]["steps"])
        self._validate_binding_structure()
        flow_entries = self._compile_secondary_flows()
        trigger_routes = self._build_trigger_routes(flow_entries)
        entry = self._compile_steps(
            self.workflow["main_flow"]["steps"],
            successor=END_NODE,
            main_trigger_routes=trigger_routes,
        )
        self._validate(entry)
        return {
            "entry": entry,
            "nodes": self.nodes,
            "routes": self.routes,
        }

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
                self.main_decisions[decision_index] = self._decision_node_name(
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
            int(index): path
            for index, path in raw_decision_paths.items()
        }
        if decision_paths != self.main_decision_paths:
            raise ValueError(
                f"Worker {self.worker_name!r} Decision bindings do not "
                "match its Main Flow Decisions."
            )

        self._validate_flow_binding_family(
            flow_key="alternative_flows",
        )
        self._validate_flow_binding_family(
            flow_key="exception_flows",
        )

    def _validate_flow_binding_family(self, *, flow_key: str) -> None:
        workflow_flows = self.workflow[flow_key]
        bindings = self.binding.get(flow_key)
        if not isinstance(bindings, list):
            raise ValueError(f"Flow binding {flow_key} must be a list.")
        expected = {
            flow["flow_name"]: ".".join(flow["flow_path"])
            for flow in workflow_flows
        }
        actual = {
            binding.get("flow_name"): binding.get("flow_path")
            for binding in bindings
        }
        if actual != expected:
            raise ValueError(
                f"Worker {self.worker_name!r} {flow_key} bindings do not "
                "match its Workflow Structure."
            )

    def _compile_secondary_flows(self) -> dict[str, str]:
        entries: dict[str, str] = {}
        for flow in self.workflow["exception_flows"]:
            entries[flow["flow_name"]] = self._compile_steps(
                flow["steps"],
                successor=END_NODE,
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
            successor = self._resolve_go_back(binding["go_back_to"])
            entries[flow["flow_name"]] = self._compile_steps(
                flow["steps"],
                successor=successor,
                main_trigger_routes=None,
            )
        return entries

    def _build_trigger_routes(
        self,
        flow_entries: dict[str, str],
    ) -> dict[int, list[dict[str, str]]]:
        routes: dict[int, list[dict[str, str]]] = {}
        flows = {
            flow["flow_name"]: flow
            for flow in [
                *self.workflow["exception_flows"],
                *self.workflow["alternative_flows"],
            ]
        }
        ordered_bindings = [
            *self.binding["exception_flows"],
            *self.binding["alternative_flows"],
        ]
        for binding in ordered_bindings:
            flow_name = binding["flow_name"]
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
            target = flow_entries[flow_name]
            for trigger in binding["trigger_is"]:
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
                        "target": target,
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
                if choices:
                    self._set_route(
                        node_name,
                        {
                            "kind": "predicate",
                            "choices": choices,
                            "default": current,
                        },
                    )
                else:
                    self._set_route(
                        node_name,
                        {"kind": "direct", "target": current},
                    )
                current = node_name
                continue

            if step_type == "if":
                node_name = self._decision_node_name(
                    step["decision_index"]
                )
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
                node_name = self._decision_node_name(
                    step["decision_index"]
                )
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

    def _resolve_go_back(self, go_back_to: dict[str, Any]) -> str:
        index_type = go_back_to.get("index_type")
        index = go_back_to.get("index")
        if index_type == "command" and index in self.main_commands:
            return self.main_commands[index]
        if index_type == "decision" and index in self.main_decisions:
            return self.main_decisions[index]
        raise ValueError(
            f"Alternative Flow go_back_to references unknown "
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

    def _decision_node_name(self, decision_index: int) -> str:
        return f"{_python_slug(self.worker_name)}__decision_{decision_index}"

    def _add_node(self, node_name: str, specification: dict[str, str]) -> None:
        existing = self.nodes.get(node_name)
        if existing is not None and existing != specification:
            raise ValueError(
                f"LangGraph node {node_name!r} has conflicting definitions."
            )
        self.nodes[node_name] = specification

    def _set_route(self, node_name: str, route: dict[str, Any]) -> None:
        if node_name in self.routes:
            raise ValueError(
                f"LangGraph node {node_name!r} has multiple routing modes."
            )
        self.routes[node_name] = route

    def _validate(self, entry: str) -> None:
        if entry != END_NODE and entry not in self.nodes:
            raise ValueError(
                f"Worker {self.worker_name!r} entry node does not exist."
            )
        actual_commands = {
            node["function"]
            for node in self.nodes.values()
            if node["kind"] == "command"
        }
        if actual_commands != set(self.expected_command_names):
            raise ValueError(
                f"Worker {self.worker_name!r} Command functions do not match "
                f"its Workflow: functions={sorted(self.expected_command_names)}, "
                f"workflow={sorted(actual_commands)}."
            )
        if set(self.routes) != set(self.nodes):
            raise ValueError(
                f"Worker {self.worker_name!r} contains nodes without routes."
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
                if target != END_NODE and target not in self.nodes
            }
            if unknown_targets:
                raise ValueError(
                    f"LangGraph routes reference unknown nodes: "
                    f"{sorted(unknown_targets)}."
                )


def _walk_steps(steps: list[WorkflowStep]):
    for step in steps:
        yield step
        if step["step_type"] == "if":
            for branch in step["branches"]:
                yield from _walk_steps(branch["steps"])
        elif step["step_type"] in {"while", "for"}:
            yield from _walk_steps(step["body_steps"])


def _render_workflow_module(
    *,
    graph_specs: dict[str, dict[str, Any]],
    command_names: list[str],
    predicate_names: list[str],
) -> str:
    command_import = _render_import("commands", command_names)
    predicate_import = _render_import("predicates", predicate_names)
    command_table = _render_function_table("COMMAND_FUNCTIONS", command_names)
    predicate_table = _render_function_table(
        "PREDICATE_FUNCTIONS",
        predicate_names,
    )
    specs_json = json.dumps(graph_specs, ensure_ascii=False, indent=4)
    return f'''from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

{command_import}
{predicate_import}
from .model import AgentState
from .utils import OpenAIClient


class WorkflowState(TypedDict):
    agent_state: AgentState
    llm_client: OpenAIClient


{command_table}

{predicate_table}

WORKER_GRAPH_SPECS = {specs_json}
_COMPILED_WORKER_GRAPHS: dict[str, Any] | None = None


def _command_node(command: Callable) -> Callable:
    def run(graph_state: WorkflowState) -> dict[str, object]:
        command(
            graph_state["agent_state"],
            graph_state["llm_client"],
        )
        return {{}}
    return run


def _decision_node(graph_state: WorkflowState) -> dict[str, object]:
    return {{}}


def _predicate_router(route: dict[str, Any]) -> Callable:
    def choose(graph_state: WorkflowState) -> str:
        for choice in route["choices"]:
            predicate = PREDICATE_FUNCTIONS[choice["predicate"]]
            if predicate(
                graph_state["agent_state"],
                graph_state["llm_client"],
            ):
                return choice["target"]
        return route["default"]
    return choose


def _compile_worker_graph(worker_name: str, spec: dict[str, Any]):
    builder = StateGraph(WorkflowState)
    for node_name, node_spec in spec["nodes"].items():
        if node_spec["kind"] == "command":
            node = _command_node(
                COMMAND_FUNCTIONS[node_spec["function"]]
            )
        else:
            node = _decision_node
        builder.add_node(node_name, node)

    entry = spec["entry"]
    builder.add_edge(START, END if entry == "{END_NODE}" else entry)
    for source, route in spec["routes"].items():
        if route["kind"] == "direct":
            target = route["target"]
            builder.add_edge(
                source,
                END if target == "{END_NODE}" else target,
            )
            continue
        destinations = {{
            choice["target"] for choice in route["choices"]
        }}
        destinations.add(route["default"])
        path_map = {{
            destination: (
                END if destination == "{END_NODE}" else destination
            )
            for destination in destinations
        }}
        builder.add_conditional_edges(
            source,
            _predicate_router(route),
            path_map=path_map,
        )
    return builder.compile(name=worker_name)


def get_worker_graphs() -> dict[str, Any]:
    global _COMPILED_WORKER_GRAPHS
    if _COMPILED_WORKER_GRAPHS is None:
        _COMPILED_WORKER_GRAPHS = {{
            worker_name: _compile_worker_graph(worker_name, spec)
            for worker_name, spec in WORKER_GRAPH_SPECS.items()
        }}
    return _COMPILED_WORKER_GRAPHS


def invoke_worker(
    worker_name: str,
    *,
    agent_state: AgentState,
    llm_client: OpenAIClient,
) -> AgentState:
    try:
        graph = get_worker_graphs()[worker_name]
    except KeyError as exc:
        raise ValueError(f"Unknown Worker: {{worker_name!r}}.") from exc
    graph.invoke(
        {{"agent_state": agent_state, "llm_client": llm_client}},
        {{"recursion_limit": 1000}},
    )
    return agent_state
'''


def _render_main_module(entry_worker: str) -> str:
    return f'''from __future__ import annotations

from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient
from .workflow import invoke_worker


def main(
    *,
    state: AgentState | None = None,
    llm_client: OpenAIClient | None = None,
) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG["model_config"])
    return invoke_worker(
        {entry_worker!r},
        agent_state=state,
        llm_client=llm_client,
    )


if __name__ == "__main__":
    main()
'''


def _render_import(module_name: str, names: list[str]) -> str:
    if not names:
        return ""
    lines = [f"from .{module_name} import ("]
    lines.extend(f"    {name}," for name in names)
    lines.append(")")
    return "\n".join(lines)


def _render_function_table(table_name: str, names: list[str]) -> str:
    lines = [f"{table_name}: dict[str, Callable] = {{"]
    lines.extend(f"    {name!r}: {name}," for name in names)
    lines.append("}")
    return "\n".join(lines)


def _python_slug(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    if not slug:
        raise ValueError(f"Worker name cannot form a Python name: {name!r}.")
    return f"w_{slug}" if slug[0].isdigit() else slug
