from .model import AgentState
from .utils import OpenAIClient


def predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch1_1(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    value = state.get_variable_value("analysis_outcome")
    return type(value) is str and value == "significant_positive_safe"


def predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch2_2(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    analysis_outcome = state.get_variable_value("analysis_outcome")
    return analysis_outcome == "significant_positive_guardrail_concern"


def predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch3_3(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    analysis_outcome = state.get_variable_value("analysis_outcome")
    if analysis_outcome == "not_significant_positive":
        return True
    return False


def predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch4_4(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    analysis_outcome = state.get_variable_value("analysis_outcome")
    return analysis_outcome == "not_significant_flat"


def predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch5_5(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    analysis_outcome = state.get_variable_value("analysis_outcome")
    return analysis_outcome == "significant_negative"
