from typing import Any, Literal, TypeAlias, TypedDict

from .cnlp_types import CNLPDataType
from .cnlp_variables import CNLPValueIR


CommandType: TypeAlias = Literal[
    "request_input",
    "general_command",
    "display_message",
    "call_api",
    "call_worker",
]
WriteOperation: TypeAlias = Literal["SET", "APPEND"]


class StaticAttributes(TypedDict):
    """Stable semantic context extracted from CNL-P static sections."""

    # Persona attribute name -> its natural-language definition.
    persona: dict[str, str]

    # Audience attribute name -> its natural-language definition.
    audience: dict[str, str]

    # Concept name -> its controlled natural-language definition.
    concepts: dict[str, str]

    # Constraint name -> the restriction it imposes on the Agent.
    constraints: dict[str, str]


class WorkerInterfaceVariable(TypedDict):
    """One variable declared in a Worker's INPUTS or OUTPUTS section."""

    # AgentState variable name transferred across the Worker call boundary.
    variable_name: str

    # Whether the Worker declaration marks this value as REQUIRED.
    is_required: bool


class WorkerNode(TypedDict):
    """Stable Worker metadata exposed to Planner and Implementer stages."""

    # Unique Worker symbol written in DEFINE_WORKER.
    worker_name: str

    # Natural-language responsibility written in DEFINE_WORKER.
    description: str

    # Variables accepted from a caller before this Worker starts.
    inputs: list[WorkerInterfaceVariable]

    # Variables returned to a caller after this Worker completes.
    outputs: list[WorkerInterfaceVariable]


def create_empty_static_attributes() -> StaticAttributes:
    """Create an empty context for isolated component use and tests."""
    return {
        "persona": {},
        "audience": {},
        "concepts": {},
        "constraints": {},
    }


class CommonCommandNode(TypedDict):
    """Fields shared by every Command extracted from the CNL-P AST."""

    command_name: str
    command_index: int
    required_variables: list[str]
    written_variable: str | None
    write_operation: WriteOperation | None


class DescribedCommandNode(CommonCommandNode):
    """A Command whose task description is explicitly present in CNL-P."""

    command_type: Literal[
        "request_input",
        "general_command",
        "display_message",
    ]
    description: str


class CallAPIArgumentNode(TypedDict):
    """One Call API argument extracted directly from the AST."""

    # The called API's formal parameter name.
    parameter_name: str

    # The CNL-P variable or structured-variable field passed as the argument.
    argument_name: str

    # The business description of the argument variable or structured field.
    argument_description: str | None

    # The CNL-P type IR of the argument variable or structured field.
    argument_type: CNLPDataType


class CallAPIResponseNode(TypedDict):
    """The CNL-P variable that receives one Call API response."""

    # The CNL-P variable or structured-variable field receiving the response.
    variable_name: str

    # The business description of the response variable or structured field.
    variable_description: str | None

    # The CNL-P type IR of the response variable or structured field.
    variable_type: CNLPDataType


class CallAPICommandNode(CommonCommandNode):
    """A Call API Command containing only facts present in the AST."""

    command_type: Literal["call_api"]

    # The API name written after CALL in the CNL-P source.
    api_name: str

    # The ordered mapping from API parameters to CNL-P argument variables.
    arguments: list[CallAPIArgumentNode]

    # The CNL-P variable that receives the API response, if RESPONSE is used.
    response: CallAPIResponseNode | None


class CallWorkerCommandNode(CommonCommandNode):
    """A CALL whose target resolves to another Worker in this Agent."""

    command_type: Literal["call_worker"]

    # Worker symbol resolved from the name written after CALL.
    target_worker_name: str

    # Caller variables supplied to the callee's declared INPUTS.
    arguments: list[CallAPIArgumentNode]

    # Caller variable receiving the callee's OUTPUT value, when requested.
    response: CallAPIResponseNode | None


CommandNode: TypeAlias = (
    DescribedCommandNode | CallAPICommandNode | CallWorkerCommandNode
)


ConditionKind = Literal[
    "if",
    "elseif",
    "while",
    "for",
    "alternative_flow",
    "exception_flow",
]


WorkflowStepType: TypeAlias = Literal["command", "if", "while", "for"]
WorkflowBranchType: TypeAlias = Literal["if", "elseif", "else"]
WorkflowFlowType: TypeAlias = Literal[
    "main_flow",
    "alternative_flow",
    "exception_flow",
]


class ConditionNode(TypedDict):
    predicate_name: str
    predicate_index: int
    condition_kind: ConditionKind
    owner_name: str

    # The complete AST key path of the structure that owns this condition.
    # It is the stable structural identity later used to connect main.py to
    # the generated Predicate function.
    condition_path: list[str]

    description: str
    required_variables: list[str]


class WorkflowCommandStep(TypedDict):
    """One Command position in the normalized Worker control structure."""

    # Discriminator used when rendering the ordered workflow.
    step_type: Literal["command"]

    # Stable Command key shared with CommandFunctionNames.
    command_name: str

    # Numeric suffix extracted from command_name.
    command_index: int

    # Complete AST path of this Command.
    command_path: list[str]


class WorkflowBranch(TypedDict):
    """One ordered branch owned by an If Decision."""

    # Whether this is the initial if, an elseif, or the final else branch.
    branch_type: WorkflowBranchType

    # Complete AST path of this branch.
    branch_path: list[str]

    # Condition path used by PredicateNamingTable; None for else.
    predicate_path: list[str] | None

    # Ordered control-flow steps executed when this branch is selected.
    steps: list["WorkflowStep"]


class WorkflowIfStep(TypedDict):
    """One If Decision and all of its ordered branches."""

    # Discriminator used when rendering the ordered workflow.
    step_type: Literal["if"]

    # Stable Decision number shared with FlowBinder go_back_to records.
    decision_index: int

    # Complete AST path of the whole If Block.
    block_path: list[str]

    # Branches in evaluation order; else, when present, is last.
    branches: list[WorkflowBranch]


class WorkflowLoopStep(TypedDict):
    """One While or For Decision and its body."""

    # Distinguishes the two supported loop structures.
    step_type: Literal["while", "for"]

    # Stable Decision number shared with FlowBinder go_back_to records.
    decision_index: int

    # Complete AST path of the whole loop block.
    block_path: list[str]

    # Condition path used by PredicateNamingTable.
    predicate_path: list[str]

    # Ordered control-flow steps executed by one loop iteration.
    body_steps: list["WorkflowStep"]


WorkflowStep: TypeAlias = (
    WorkflowCommandStep
    | WorkflowIfStep
    | WorkflowLoopStep
)


class WorkflowFlow(TypedDict):
    """One normalized Main, Alternative, or Exception Flow."""

    # Flow key from the Worker AST, such as alternative_flow1.
    flow_name: str

    # Semantic role of this Flow in Worker execution.
    flow_type: WorkflowFlowType

    # Complete AST path of this Flow.
    flow_path: list[str]

    # Flow-level condition path; only Alternative/Exception Flows use it.
    predicate_path: list[str] | None

    # Ordered control-flow steps inside this Flow.
    steps: list[WorkflowStep]


class WorkflowStructure(TypedDict):
    """Stable structural input shared by FlowBinder and MainImplementer."""

    # The unique Main Flow executed when the Worker starts.
    main_flow: WorkflowFlow

    # Alternative Flows in CNL-P declaration order.
    alternative_flows: list[WorkflowFlow]

    # Exception Flows in CNL-P declaration order.
    exception_flows: list[WorkflowFlow]


class VariableNode(TypedDict):
    variable_name: str
    description: str | None
    data_type: CNLPDataType
    default_value: CNLPValueIR | None
