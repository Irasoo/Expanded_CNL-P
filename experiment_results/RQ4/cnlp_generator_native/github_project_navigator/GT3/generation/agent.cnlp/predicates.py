from .model import AgentState
from .utils import OpenAIClient


def predicate_workers_ProjectNavigator_main_flow_if_block1_if_branch1_1(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    value = state.get_variable_value("repository_input_limit_exceeded")
    return value is False


def predicate_workers_ProjectNavigator_main_flow_if_block2_if_branch1_2(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    repository_found = state.get_variable_value("repository_found")
    return repository_found is True


def predicate_workers_ProjectNavigator_main_flow_if_block3_if_branch1_3(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    values = state.get_variable_values([
        "repository_found",
        "issue_analysis_choice",
    ])
    repository_found = values["repository_found"]
    issue_analysis_choice = values["issue_analysis_choice"]
    return repository_found is True and issue_analysis_choice == "yes"


def predicate_workers_ProjectNavigator_main_flow_if_block4_if_branch1_4(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    repository_found = state.get_variable_value("repository_found")
    return repository_found is True


def predicate_workers_ProjectNavigator_main_flow_if_block5_if_branch1_5(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    values = state.get_variable_values(["repository_found", "release_analysis_choice"])
    return (values["repository_found"] is True) and (values["release_analysis_choice"] == "yes")


def predicate_workers_ProjectNavigator_main_flow_if_block6_if_branch1_6(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    repository_found = state.get_variable_value("repository_found")
    return repository_found is True


def predicate_workers_ProjectNavigator_main_flow_if_block7_if_branch1_7(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    values = state.get_variable_values([
        "repository_input_limit_exceeded",
        "repository_found",
    ])
    return (
        values["repository_input_limit_exceeded"] is False
        and values["repository_found"] is False
    )


def predicate_workers_ProjectNavigator_alternative_flow1_8(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    input_kind = state.get_variable_value("input_kind")
    return input_kind == "unclear"


def predicate_workers_ProjectNavigator_alternative_flow1_while_block1_9(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    values = state.get_variable_values(["input_kind", "repository_input_retry_count"])
    return (values["input_kind"] == "unclear") and (values["repository_input_retry_count"] < 3)


def predicate_workers_ProjectNavigator_exception_flow1_10(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    repository_input_limit_exceeded = state.get_variable_value("repository_input_limit_exceeded")
    if isinstance(repository_input_limit_exceeded, bool):
        return repository_input_limit_exceeded is True
    return False


def predicate_workers_ReleaseAdvisor_main_flow_if_block1_if_branch1_11(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    release_request = state.get_variable_value("release_request")
    return release_request["analysis_mode"] == "overview"
