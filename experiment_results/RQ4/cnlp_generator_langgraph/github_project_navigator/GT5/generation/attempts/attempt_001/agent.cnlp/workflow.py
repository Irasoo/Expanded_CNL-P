from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .commands import (
    projectnavigator__command1,
    projectnavigator__command2,
    projectnavigator__command3,
    projectnavigator__command4,
    projectnavigator__command5,
    projectnavigator__command6,
    projectnavigator__command7,
    projectnavigator__command8,
    projectnavigator__command9,
    projectnavigator__command10,
    projectnavigator__command11,
    projectnavigator__command12,
    projectnavigator__command13,
    projectnavigator__command14,
    projectnavigator__command15,
    projectnavigator__command16,
    projectnavigator__command17,
    projectnavigator__command18,
    projectnavigator__command19,
    projectnavigator__command20,
    projectnavigator__command21,
    projectnavigator__command22,
    issueanalyzer__command23,
    issueanalyzer__command24,
    releaseadvisor__command25,
    releaseadvisor__command26,
    releaseadvisor__command27,
    releaseadvisor__command28,
)
from .predicates import (
    predicate_workers_ProjectNavigator_main_flow_if_block1_if_branch1_1,
    predicate_workers_ProjectNavigator_main_flow_if_block2_if_branch1_2,
    predicate_workers_ProjectNavigator_main_flow_if_block3_if_branch1_3,
    predicate_workers_ProjectNavigator_main_flow_if_block4_if_branch1_4,
    predicate_workers_ProjectNavigator_main_flow_if_block5_if_branch1_5,
    predicate_workers_ProjectNavigator_main_flow_if_block6_if_branch1_6,
    predicate_workers_ProjectNavigator_main_flow_if_block7_if_branch1_7,
    predicate_workers_ProjectNavigator_alternative_flow1_8,
    predicate_workers_ProjectNavigator_alternative_flow1_while_block1_9,
    predicate_workers_ProjectNavigator_exception_flow1_10,
    predicate_workers_ReleaseAdvisor_main_flow_if_block1_if_branch1_11,
)
from .model import AgentState
from .utils import OpenAIClient


class WorkflowState(TypedDict):
    agent_state: AgentState
    llm_client: OpenAIClient


COMMAND_FUNCTIONS: dict[str, Callable] = {
    'projectnavigator__command1': projectnavigator__command1,
    'projectnavigator__command2': projectnavigator__command2,
    'projectnavigator__command3': projectnavigator__command3,
    'projectnavigator__command4': projectnavigator__command4,
    'projectnavigator__command5': projectnavigator__command5,
    'projectnavigator__command6': projectnavigator__command6,
    'projectnavigator__command7': projectnavigator__command7,
    'projectnavigator__command8': projectnavigator__command8,
    'projectnavigator__command9': projectnavigator__command9,
    'projectnavigator__command10': projectnavigator__command10,
    'projectnavigator__command11': projectnavigator__command11,
    'projectnavigator__command12': projectnavigator__command12,
    'projectnavigator__command13': projectnavigator__command13,
    'projectnavigator__command14': projectnavigator__command14,
    'projectnavigator__command15': projectnavigator__command15,
    'projectnavigator__command16': projectnavigator__command16,
    'projectnavigator__command17': projectnavigator__command17,
    'projectnavigator__command18': projectnavigator__command18,
    'projectnavigator__command19': projectnavigator__command19,
    'projectnavigator__command20': projectnavigator__command20,
    'projectnavigator__command21': projectnavigator__command21,
    'projectnavigator__command22': projectnavigator__command22,
    'issueanalyzer__command23': issueanalyzer__command23,
    'issueanalyzer__command24': issueanalyzer__command24,
    'releaseadvisor__command25': releaseadvisor__command25,
    'releaseadvisor__command26': releaseadvisor__command26,
    'releaseadvisor__command27': releaseadvisor__command27,
    'releaseadvisor__command28': releaseadvisor__command28,
}

PREDICATE_FUNCTIONS: dict[str, Callable] = {
    'predicate_workers_ProjectNavigator_main_flow_if_block1_if_branch1_1': predicate_workers_ProjectNavigator_main_flow_if_block1_if_branch1_1,
    'predicate_workers_ProjectNavigator_main_flow_if_block2_if_branch1_2': predicate_workers_ProjectNavigator_main_flow_if_block2_if_branch1_2,
    'predicate_workers_ProjectNavigator_main_flow_if_block3_if_branch1_3': predicate_workers_ProjectNavigator_main_flow_if_block3_if_branch1_3,
    'predicate_workers_ProjectNavigator_main_flow_if_block4_if_branch1_4': predicate_workers_ProjectNavigator_main_flow_if_block4_if_branch1_4,
    'predicate_workers_ProjectNavigator_main_flow_if_block5_if_branch1_5': predicate_workers_ProjectNavigator_main_flow_if_block5_if_branch1_5,
    'predicate_workers_ProjectNavigator_main_flow_if_block6_if_branch1_6': predicate_workers_ProjectNavigator_main_flow_if_block6_if_branch1_6,
    'predicate_workers_ProjectNavigator_main_flow_if_block7_if_branch1_7': predicate_workers_ProjectNavigator_main_flow_if_block7_if_branch1_7,
    'predicate_workers_ProjectNavigator_alternative_flow1_8': predicate_workers_ProjectNavigator_alternative_flow1_8,
    'predicate_workers_ProjectNavigator_alternative_flow1_while_block1_9': predicate_workers_ProjectNavigator_alternative_flow1_while_block1_9,
    'predicate_workers_ProjectNavigator_exception_flow1_10': predicate_workers_ProjectNavigator_exception_flow1_10,
    'predicate_workers_ReleaseAdvisor_main_flow_if_block1_if_branch1_11': predicate_workers_ReleaseAdvisor_main_flow_if_block1_if_branch1_11,
}

WORKER_GRAPH_SPECS = {
    "ProjectNavigator": {
        "entry": "projectnavigator__command1",
        "nodes": {
            "projectnavigator__command22": {
                "kind": "command",
                "function": "projectnavigator__command22"
            },
            "projectnavigator__command21": {
                "kind": "command",
                "function": "projectnavigator__command21"
            },
            "projectnavigator__decision_8": {
                "kind": "decision"
            },
            "projectnavigator__command20": {
                "kind": "command",
                "function": "projectnavigator__command20"
            },
            "projectnavigator__command19": {
                "kind": "command",
                "function": "projectnavigator__command19"
            },
            "projectnavigator__command18": {
                "kind": "command",
                "function": "projectnavigator__command18"
            },
            "projectnavigator__decision_7": {
                "kind": "decision"
            },
            "projectnavigator__command17": {
                "kind": "command",
                "function": "projectnavigator__command17"
            },
            "projectnavigator__command16": {
                "kind": "command",
                "function": "projectnavigator__command16"
            },
            "projectnavigator__decision_6": {
                "kind": "decision"
            },
            "projectnavigator__command15": {
                "kind": "command",
                "function": "projectnavigator__command15"
            },
            "projectnavigator__decision_5": {
                "kind": "decision"
            },
            "projectnavigator__command14": {
                "kind": "command",
                "function": "projectnavigator__command14"
            },
            "projectnavigator__command13": {
                "kind": "command",
                "function": "projectnavigator__command13"
            },
            "projectnavigator__decision_4": {
                "kind": "decision"
            },
            "projectnavigator__command12": {
                "kind": "command",
                "function": "projectnavigator__command12"
            },
            "projectnavigator__decision_3": {
                "kind": "decision"
            },
            "projectnavigator__command11": {
                "kind": "command",
                "function": "projectnavigator__command11"
            },
            "projectnavigator__decision_2": {
                "kind": "decision"
            },
            "projectnavigator__command10": {
                "kind": "command",
                "function": "projectnavigator__command10"
            },
            "projectnavigator__command9": {
                "kind": "command",
                "function": "projectnavigator__command9"
            },
            "projectnavigator__command8": {
                "kind": "command",
                "function": "projectnavigator__command8"
            },
            "projectnavigator__decision_1": {
                "kind": "decision"
            },
            "projectnavigator__command7": {
                "kind": "command",
                "function": "projectnavigator__command7"
            },
            "projectnavigator__command6": {
                "kind": "command",
                "function": "projectnavigator__command6"
            },
            "projectnavigator__command5": {
                "kind": "command",
                "function": "projectnavigator__command5"
            },
            "projectnavigator__command4": {
                "kind": "command",
                "function": "projectnavigator__command4"
            },
            "projectnavigator__command3": {
                "kind": "command",
                "function": "projectnavigator__command3"
            },
            "projectnavigator__command2": {
                "kind": "command",
                "function": "projectnavigator__command2"
            },
            "projectnavigator__command1": {
                "kind": "command",
                "function": "projectnavigator__command1"
            }
        },
        "routes": {
            "projectnavigator__command22": {
                "kind": "direct",
                "target": "__end__"
            },
            "projectnavigator__command21": {
                "kind": "direct",
                "target": "projectnavigator__command22"
            },
            "projectnavigator__command20": {
                "kind": "direct",
                "target": "projectnavigator__decision_8"
            },
            "projectnavigator__command19": {
                "kind": "direct",
                "target": "projectnavigator__command20"
            },
            "projectnavigator__command18": {
                "kind": "direct",
                "target": "projectnavigator__command19"
            },
            "projectnavigator__decision_8": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_alternative_flow1_while_block1_9",
                        "target": "projectnavigator__command18"
                    }
                ],
                "default": "projectnavigator__command4"
            },
            "projectnavigator__command17": {
                "kind": "direct",
                "target": "__end__"
            },
            "projectnavigator__command16": {
                "kind": "direct",
                "target": "projectnavigator__command17"
            },
            "projectnavigator__decision_7": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block7_if_branch1_7",
                        "target": "projectnavigator__command16"
                    }
                ],
                "default": "__end__"
            },
            "projectnavigator__command15": {
                "kind": "direct",
                "target": "projectnavigator__decision_7"
            },
            "projectnavigator__decision_6": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block6_if_branch1_6",
                        "target": "projectnavigator__command15"
                    }
                ],
                "default": "projectnavigator__decision_7"
            },
            "projectnavigator__command14": {
                "kind": "direct",
                "target": "projectnavigator__decision_6"
            },
            "projectnavigator__command13": {
                "kind": "direct",
                "target": "projectnavigator__command14"
            },
            "projectnavigator__decision_5": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block5_if_branch1_5",
                        "target": "projectnavigator__command13"
                    }
                ],
                "default": "projectnavigator__decision_6"
            },
            "projectnavigator__command12": {
                "kind": "direct",
                "target": "projectnavigator__decision_5"
            },
            "projectnavigator__decision_4": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block4_if_branch1_4",
                        "target": "projectnavigator__command12"
                    }
                ],
                "default": "projectnavigator__decision_5"
            },
            "projectnavigator__command11": {
                "kind": "direct",
                "target": "projectnavigator__decision_4"
            },
            "projectnavigator__decision_3": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block3_if_branch1_3",
                        "target": "projectnavigator__command11"
                    }
                ],
                "default": "projectnavigator__decision_4"
            },
            "projectnavigator__command10": {
                "kind": "direct",
                "target": "projectnavigator__decision_3"
            },
            "projectnavigator__command9": {
                "kind": "direct",
                "target": "projectnavigator__command10"
            },
            "projectnavigator__command8": {
                "kind": "direct",
                "target": "projectnavigator__command9"
            },
            "projectnavigator__decision_2": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block2_if_branch1_2",
                        "target": "projectnavigator__command8"
                    }
                ],
                "default": "projectnavigator__decision_3"
            },
            "projectnavigator__command7": {
                "kind": "direct",
                "target": "projectnavigator__decision_2"
            },
            "projectnavigator__command6": {
                "kind": "direct",
                "target": "projectnavigator__command7"
            },
            "projectnavigator__command5": {
                "kind": "direct",
                "target": "projectnavigator__command6"
            },
            "projectnavigator__decision_1": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_main_flow_if_block1_if_branch1_1",
                        "target": "projectnavigator__command5"
                    }
                ],
                "default": "projectnavigator__decision_2"
            },
            "projectnavigator__command4": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_exception_flow1_10",
                        "target": "projectnavigator__command21"
                    }
                ],
                "default": "projectnavigator__decision_1"
            },
            "projectnavigator__command3": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ProjectNavigator_alternative_flow1_8",
                        "target": "projectnavigator__decision_8"
                    }
                ],
                "default": "projectnavigator__command4"
            },
            "projectnavigator__command2": {
                "kind": "direct",
                "target": "projectnavigator__command3"
            },
            "projectnavigator__command1": {
                "kind": "direct",
                "target": "projectnavigator__command2"
            }
        }
    },
    "IssueAnalyzer": {
        "entry": "issueanalyzer__command23",
        "nodes": {
            "issueanalyzer__command24": {
                "kind": "command",
                "function": "issueanalyzer__command24"
            },
            "issueanalyzer__command23": {
                "kind": "command",
                "function": "issueanalyzer__command23"
            }
        },
        "routes": {
            "issueanalyzer__command24": {
                "kind": "direct",
                "target": "__end__"
            },
            "issueanalyzer__command23": {
                "kind": "direct",
                "target": "issueanalyzer__command24"
            }
        }
    },
    "ReleaseAdvisor": {
        "entry": "releaseadvisor__command25",
        "nodes": {
            "releaseadvisor__decision_1": {
                "kind": "decision"
            },
            "releaseadvisor__command26": {
                "kind": "command",
                "function": "releaseadvisor__command26"
            },
            "releaseadvisor__command28": {
                "kind": "command",
                "function": "releaseadvisor__command28"
            },
            "releaseadvisor__command27": {
                "kind": "command",
                "function": "releaseadvisor__command27"
            },
            "releaseadvisor__command25": {
                "kind": "command",
                "function": "releaseadvisor__command25"
            }
        },
        "routes": {
            "releaseadvisor__command26": {
                "kind": "direct",
                "target": "__end__"
            },
            "releaseadvisor__command28": {
                "kind": "direct",
                "target": "__end__"
            },
            "releaseadvisor__command27": {
                "kind": "direct",
                "target": "releaseadvisor__command28"
            },
            "releaseadvisor__decision_1": {
                "kind": "predicate",
                "choices": [
                    {
                        "predicate": "predicate_workers_ReleaseAdvisor_main_flow_if_block1_if_branch1_11",
                        "target": "releaseadvisor__command26"
                    }
                ],
                "default": "releaseadvisor__command27"
            },
            "releaseadvisor__command25": {
                "kind": "direct",
                "target": "releaseadvisor__decision_1"
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
