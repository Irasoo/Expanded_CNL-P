from .model import AgentState
from .utils import OpenAIClient


def predicate_workers_CreativeConceptDeveloper_main_flow_while_block1_1(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    values = state.get_variable_values(["evaluation_result", "refinement_count"])
    evaluation_result = values["evaluation_result"]
    refinement_count = values["refinement_count"]

    if evaluation_result["overall_score"] < 8.0 and refinement_count < 2:
        return True
    return False


def predicate_workers_CreativeConceptDeveloper_main_flow_if_block1_if_branch1_2(
    state: AgentState,
    llm_client: OpenAIClient,
) -> bool:
    evaluation_result = state.get_variable_value("evaluation_result")
    return evaluation_result["overall_score"] >= 8.0
