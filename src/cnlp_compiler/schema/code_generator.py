from typing import Literal, TypeAlias, TypedDict

from .node_visitor import (
    CallAPIArgumentNode,
    CallAPIResponseNode,
    ConditionKind,
    WriteOperation,
    WorkerInterfaceVariable,
)



class ModelConfig(TypedDict):
    model_name: str
    api_key: str
    base_url: str


class InputCommandAnalysisPlan(TypedDict):
    command_name: str
    command_index: int
    command_type: Literal["request_input"]
    description: str
    required_variables: list[str]
    request_generation: dict[str, bool]
    raw_input_processing: dict[str, bool]
    written_variable: str
    write_operation: WriteOperation | None


class GeneralCommandAnalysisPlan(TypedDict):
    command_name: str
    command_index: int
    command_type: Literal["general_command"]
    description: str
    required_variables: list[str]
    llm_based_processing: bool
    written_variable: str
    write_operation: WriteOperation | None


class DisplayCommandAnalysisPlan(TypedDict):
    command_name: str
    command_index: int
    command_type: Literal["display_message"]
    description: str
    required_variables: list[str]
    display_content_generation: dict[str, bool]
    written_variable: None
    write_operation: WriteOperation | None


class CallAPICommandAnalysisPlan(TypedDict):
    command_name: str
    command_index: int
    command_type: Literal["call_api"]

    # The API name extracted directly from the CNL-P AST.
    api_name: str

    # The ordered API parameter-to-CNL-P-variable mappings extracted from AST.
    arguments: list[CallAPIArgumentNode]

    # The variable that receives the API response, if the CALL has RESPONSE.
    response: CallAPIResponseNode | None

    # A Planner-generated summary based on the complete CNL-P source.
    description: str

    # The Catalog key of the selected reference function. None means no
    # suitable reference function was found. Source code is never stored here.
    reference_function_name: str | None

    required_variables: list[str]
    written_variable: str | None
    write_operation: WriteOperation | None


class CallWorkerCommandAnalysisPlan(TypedDict):
    """Plan for invoking another Worker through its INPUT/OUTPUT contract."""

    command_name: str
    command_index: int
    command_type: Literal["call_worker"]

    # Callee Worker symbol resolved mechanically by NodeVisitor.
    target_worker_name: str

    # Caller values mapped to formal names declared by callee INPUTS.
    arguments: list[CallAPIArgumentNode]

    # Caller variable receiving the callee result, when RESPONSE is present.
    response: CallAPIResponseNode | None

    # Callee INPUTS used to validate names and required arguments.
    target_inputs: list[WorkerInterfaceVariable]

    # Callee OUTPUTS used to define the returned value shape.
    target_outputs: list[WorkerInterfaceVariable]

    required_variables: list[str]
    written_variable: str | None
    write_operation: WriteOperation | None


CommandAnalysisPlan: TypeAlias = (
    InputCommandAnalysisPlan
    | GeneralCommandAnalysisPlan
    | DisplayCommandAnalysisPlan
    | CallAPICommandAnalysisPlan
    | CallWorkerCommandAnalysisPlan
)


class PredicateAnalysisPlan(TypedDict):
    predicate_name: str
    predicate_index: int
    owner_name: str
    condition_kind: ConditionKind

    # The complete AST key path of this condition's owner. The Planner keeps
    # it unchanged so the Implementer can build the main.py routing key.
    condition_path: list[str]

    description: str
    required_variables: list[str]
    llm_based_processing: bool


class WorkerImplementationPlan(TypedDict):
    """All semantic implementation decisions for one Worker."""

    worker_name: str
    description: str
    inputs: list[WorkerInterfaceVariable]
    outputs: list[WorkerInterfaceVariable]
    commands: list[CommandAnalysisPlan]
    predicates: list[PredicateAnalysisPlan]


class ImplementationPlan(TypedDict):
    """Agent-wide plan with an explicit entry Worker and per-Worker plans."""

    # Worker invoked by generated main.py when the Agent starts.
    entry_worker: str

    # Worker symbol -> its independently planned Commands and Predicates.
    workers: dict[str, WorkerImplementationPlan]
