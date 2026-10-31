from .model import AgentState
from .utils import OpenAIClient


def predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch1_1(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    communication_type = state.get_variable_value("communication_type")
    return communication_type == "three_p"


def predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch2_2(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    communication_type = state.get_variable_value("communication_type")
    return communication_type == "newsletter"


def predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch3_3(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    communication_type = state.get_variable_value("communication_type")
    return communication_type == "faq"


def predicate_workers_InternalCommsDispatcher_exception_flow1_4(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    communication_type = state.get_variable_value("communication_type")
    return communication_type == "unknown"
