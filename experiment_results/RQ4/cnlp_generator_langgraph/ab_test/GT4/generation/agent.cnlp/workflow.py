from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .commands import (
    abtestanalyzer__command1,
    abtestanalyzer__command2,
    abtestanalyzer__command3,
    abtestanalyzer__command4,
    abtestanalyzer__command5,
    abtestanalyzer__command6,
    abtestanalyzer__command7,
    abtestanalyzer__command8,
    abtestanalyzer__command9,
    abtestanalyzer__command10,
    abtestanalyzer__command11,
    abtestanalyzer__command12,
    abtestanalyzer__command13,
)
from .predicates import (
    predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch1_1,
    predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch2_2,
    predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch3_3,
    predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch4_4,
    predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch5_5,
)
from .model import AgentState
from .utils import OpenAIClient


class WorkflowState(TypedDict):
    agent_state: AgentState
    llm_client: OpenAIClient


COMMAND_FUNCTIONS: dict[str, Callable] = {
    'abtestanalyzer__command1': abtestanalyzer__command1,
    'abtestanalyzer__command2': abtestanalyzer__command2,
    'abtestanalyzer__command3': abtestanalyzer__command3,
    'abtestanalyzer__command4': abtestanalyzer__command4,
    'abtestanalyzer__command5': abtestanalyzer__command5,
    'abtestanalyzer__command6': abtestanalyzer__command6,
    'abtestanalyzer__command7': abtestanalyzer__command7,
    'abtestanalyzer__command8': abtestanalyzer__command8,
    'abtestanalyzer__command9': abtestanalyzer__command9,
    'abtestanalyzer__command10': abtestanalyzer__command10,
    'abtestanalyzer__command11': abtestanalyzer__command11,
    'abtestanalyzer__command12': abtestanalyzer__command12,
    'abtestanalyzer__command13': abtestanalyzer__command13,
}

PREDICATE_FUNCTIONS: dict[str, Callable] = {
    'predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch1_1': predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch1_1,
    'predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch2_2': predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch2_2,
    'predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch3_3': predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch3_3,
    'predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch4_4': predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch4_4,
    'predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch5_5': predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch5_5,
}

WORKER_GRAPH_SPECS = {
    "ABTestAnalyzer": {
        "entry": "abtestanalyzer__command1",
        "nodes": {
            "abtestanalyzer__command13": {
                "kind": "command",
                "function": "abtestanalyzer__command13"
            },
            "abtestanalyzer__command12": {
                "kind": "command",
                "function": "abtestanalyzer__command12"
            },
            "abtestanalyzer__decision_1": {
                "kind": "decision"
            },
            "abtestanalyzer__command6": {
                "kind": "command",
                "function": "abtestanalyzer__command6"
            },
            "abtestanalyzer__command7": {
                "kind": "command",
                "function": "abtestanalyzer__command7"
            },
            "abtestanalyzer__command8": {
                "kind": "command",
                "function": "abtestanalyzer__command8"
            },
            "abtestanalyzer__command9": {
                "kind": "command",
                "function": "abtestanalyzer__command9"
            },
            "abtestanalyzer__command10": {
                "kind": "command",
                "function": "abtestanalyzer__command10"
            },
            "abtestanalyzer__command11": {
                "kind": "command",
                "function": "abtestanalyzer__command11"
            },
            "abtestanalyzer__command5": {
                "kind": "command",
                "function": "abtestanalyzer__command5"
            },
            "abtestanalyzer__command4": {
                "kind": "command",
                "function": "abtestanalyzer__command4"
            },
            "abtestanalyzer__command3": {
                "kind": "command",
                "function": "abtestanalyzer__command3"
            },
            "abtestanalyzer__command2": {
                "kind": "command",
                "function": "abtestanalyzer__command2"
            },
            "abtestanalyzer__command1": {
                "kind": "command",
                "function": "abtestanalyzer__command1"
            }
        },
        "routes": {
            "abtestanalyzer__command13": {
                "kind": "direct",
                "target": "__end__"
            },
            "abtestanalyzer__command12": {
                "kind": "direct",
                "target": "abtestanalyzer__command13"
            },
            "abtestanalyzer__command6": {
                "kind": "direct",
                "target": "abtestanalyzer__command12"
            },
            "abtestanalyzer__command7": {
                "kind": "direct",
                "target": "abtestanalyzer__command12"
            },
            "abtestanalyzer__command8": {
                "kind": "direct",
                "target": "abtestanalyzer__command12"
            },
            "abtestanalyzer__command9": {
                "kind": "direct",
                "target": "abtestanalyzer__command12"
            },
            "abtestanalyzer__command10": {
                "kind": "direct",
                "target": "abtestanalyzer__command12"
            },
            "abtestanalyzer__command11": {
                "kind": "direct",
                "target": "abtestanalyzer__command12"
            },
            "abtestanalyzer__decision_1": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch1_1",
                        "target": "abtestanalyzer__command6"
                    },
                    {
                        "predicate": "predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch2_2",
                        "target": "abtestanalyzer__command7"
                    },
                    {
                        "predicate": "predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch3_3",
                        "target": "abtestanalyzer__command8"
                    },
                    {
                        "predicate": "predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch4_4",
                        "target": "abtestanalyzer__command9"
                    },
                    {
                        "predicate": "predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch5_5",
                        "target": "abtestanalyzer__command10"
                    }
                ],
                "default": "abtestanalyzer__command11"
            },
            "abtestanalyzer__command5": {
                "kind": "direct",
                "target": "abtestanalyzer__decision_1"
            },
            "abtestanalyzer__command4": {
                "kind": "direct",
                "target": "abtestanalyzer__command5"
            },
            "abtestanalyzer__command3": {
                "kind": "direct",
                "target": "abtestanalyzer__command4"
            },
            "abtestanalyzer__command2": {
                "kind": "direct",
                "target": "abtestanalyzer__command3"
            },
            "abtestanalyzer__command1": {
                "kind": "direct",
                "target": "abtestanalyzer__command2"
            }
        }
    }
}
_COMPILED_WORKER_GRAPHS: dict[str, Any] | None = None


def _command_node(command: Callable) -> Callable:
    def run(graph_state: WorkflowState) -> dict[str, object]:
        command(
            graph_state["agent_state"],
            graph_state["llm_client"],
        )
        return {}
    return run


def _decision_node(graph_state: WorkflowState) -> dict[str, object]:
    return {}


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
    builder.add_edge(START, END if entry == "__end__" else entry)
    for source, route in spec["routes"].items():
        if route["kind"] == "direct":
            target = route["target"]
            builder.add_edge(
                source,
                END if target == "__end__" else target,
            )
            continue
        destinations = {
            choice["target"] for choice in route["choices"]
        }
        destinations.add(route["default"])
        path_map = {
            destination: (
                END if destination == "__end__" else destination
            )
            for destination in destinations
        }
        builder.add_conditional_edges(
            source,
            _predicate_router(route),
            path_map=path_map,
        )
    return builder.compile(name=worker_name)


def get_worker_graphs() -> dict[str, Any]:
    global _COMPILED_WORKER_GRAPHS
    if _COMPILED_WORKER_GRAPHS is None:
        _COMPILED_WORKER_GRAPHS = {
            worker_name: _compile_worker_graph(worker_name, spec)
            for worker_name, spec in WORKER_GRAPH_SPECS.items()
        }
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
        raise ValueError(f"Unknown Worker: {worker_name!r}.") from exc
    graph.invoke(
        {"agent_state": agent_state, "llm_client": llm_client},
        {"recursion_limit": 1000},
    )
    return agent_state
