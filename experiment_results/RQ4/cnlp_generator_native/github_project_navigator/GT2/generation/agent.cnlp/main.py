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
from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient


def run_projectnavigator(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'projectnavigator__command1'
    while pc != '__end__':
        match pc:
            case 'projectnavigator__command22':
                projectnavigator__command22(state, llm_client)
                pc = '__end__'
                continue
            case 'projectnavigator__command21':
                projectnavigator__command21(state, llm_client)
                pc = 'projectnavigator__command22'
                continue
            case 'projectnavigator__decision_8':
                if predicate_workers_ProjectNavigator_alternative_flow1_while_block1_9(state, llm_client):
                    pc = 'projectnavigator__command18'
                else:
                    pc = 'projectnavigator__command4'
                continue
            case 'projectnavigator__command20':
                projectnavigator__command20(state, llm_client)
                pc = 'projectnavigator__decision_8'
                continue
            case 'projectnavigator__command19':
                projectnavigator__command19(state, llm_client)
                pc = 'projectnavigator__command20'
                continue
            case 'projectnavigator__command18':
                projectnavigator__command18(state, llm_client)
                pc = 'projectnavigator__command19'
                continue
            case 'projectnavigator__decision_7':
                if predicate_workers_ProjectNavigator_main_flow_if_block7_if_branch1_7(state, llm_client):
                    pc = 'projectnavigator__command16'
                else:
                    pc = '__end__'
                continue
            case 'projectnavigator__command17':
                projectnavigator__command17(state, llm_client)
                pc = '__end__'
                continue
            case 'projectnavigator__command16':
                projectnavigator__command16(state, llm_client)
                pc = 'projectnavigator__command17'
                continue
            case 'projectnavigator__decision_6':
                if predicate_workers_ProjectNavigator_main_flow_if_block6_if_branch1_6(state, llm_client):
                    pc = 'projectnavigator__command15'
                else:
                    pc = 'projectnavigator__decision_7'
                continue
            case 'projectnavigator__command15':
                projectnavigator__command15(state, llm_client)
                pc = 'projectnavigator__decision_7'
                continue
            case 'projectnavigator__decision_5':
                if predicate_workers_ProjectNavigator_main_flow_if_block5_if_branch1_5(state, llm_client):
                    pc = 'projectnavigator__command13'
                else:
                    pc = 'projectnavigator__decision_6'
                continue
            case 'projectnavigator__command14':
                projectnavigator__command14(state, llm_client)
                pc = 'projectnavigator__decision_6'
                continue
            case 'projectnavigator__command13':
                projectnavigator__command13(state, llm_client)
                pc = 'projectnavigator__command14'
                continue
            case 'projectnavigator__decision_4':
                if predicate_workers_ProjectNavigator_main_flow_if_block4_if_branch1_4(state, llm_client):
                    pc = 'projectnavigator__command12'
                else:
                    pc = 'projectnavigator__decision_5'
                continue
            case 'projectnavigator__command12':
                projectnavigator__command12(state, llm_client)
                pc = 'projectnavigator__decision_5'
                continue
            case 'projectnavigator__decision_3':
                if predicate_workers_ProjectNavigator_main_flow_if_block3_if_branch1_3(state, llm_client):
                    pc = 'projectnavigator__command11'
                else:
                    pc = 'projectnavigator__decision_4'
                continue
            case 'projectnavigator__command11':
                projectnavigator__command11(state, llm_client)
                pc = 'projectnavigator__decision_4'
                continue
            case 'projectnavigator__decision_2':
                if predicate_workers_ProjectNavigator_main_flow_if_block2_if_branch1_2(state, llm_client):
                    pc = 'projectnavigator__command8'
                else:
                    pc = 'projectnavigator__decision_3'
                continue
            case 'projectnavigator__command10':
                projectnavigator__command10(state, llm_client)
                pc = 'projectnavigator__decision_3'
                continue
            case 'projectnavigator__command9':
                projectnavigator__command9(state, llm_client)
                pc = 'projectnavigator__command10'
                continue
            case 'projectnavigator__command8':
                projectnavigator__command8(state, llm_client)
                pc = 'projectnavigator__command9'
                continue
            case 'projectnavigator__decision_1':
                if predicate_workers_ProjectNavigator_main_flow_if_block1_if_branch1_1(state, llm_client):
                    pc = 'projectnavigator__command5'
                else:
                    pc = 'projectnavigator__decision_2'
                continue
            case 'projectnavigator__command7':
                projectnavigator__command7(state, llm_client)
                pc = 'projectnavigator__decision_2'
                continue
            case 'projectnavigator__command6':
                projectnavigator__command6(state, llm_client)
                pc = 'projectnavigator__command7'
                continue
            case 'projectnavigator__command5':
                projectnavigator__command5(state, llm_client)
                pc = 'projectnavigator__command6'
                continue
            case 'projectnavigator__command4':
                projectnavigator__command4(state, llm_client)
                if predicate_workers_ProjectNavigator_exception_flow1_10(state, llm_client):
                    pc = 'projectnavigator__command21'
                else:
                    pc = 'projectnavigator__decision_1'
                continue
            case 'projectnavigator__command3':
                projectnavigator__command3(state, llm_client)
                if predicate_workers_ProjectNavigator_alternative_flow1_8(state, llm_client):
                    pc = 'projectnavigator__decision_8'
                else:
                    pc = 'projectnavigator__command4'
                continue
            case 'projectnavigator__command2':
                projectnavigator__command2(state, llm_client)
                pc = 'projectnavigator__command3'
                continue
            case 'projectnavigator__command1':
                projectnavigator__command1(state, llm_client)
                pc = 'projectnavigator__command2'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state
def run_issueanalyzer(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'issueanalyzer__command23'
    while pc != '__end__':
        match pc:
            case 'issueanalyzer__command24':
                issueanalyzer__command24(state, llm_client)
                pc = '__end__'
                continue
            case 'issueanalyzer__command23':
                issueanalyzer__command23(state, llm_client)
                pc = 'issueanalyzer__command24'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state
def run_releaseadvisor(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'releaseadvisor__command25'
    while pc != '__end__':
        match pc:
            case 'releaseadvisor__decision_1':
                if predicate_workers_ReleaseAdvisor_main_flow_if_block1_if_branch1_11(state, llm_client):
                    pc = 'releaseadvisor__command26'
                else:
                    pc = 'releaseadvisor__command27'
                continue
            case 'releaseadvisor__command26':
                releaseadvisor__command26(state, llm_client)
                pc = '__end__'
                continue
            case 'releaseadvisor__command28':
                releaseadvisor__command28(state, llm_client)
                pc = '__end__'
                continue
            case 'releaseadvisor__command27':
                releaseadvisor__command27(state, llm_client)
                pc = 'releaseadvisor__command28'
                continue
            case 'releaseadvisor__command25':
                releaseadvisor__command25(state, llm_client)
                pc = 'releaseadvisor__decision_1'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state


def main(
    *,
    state: AgentState | None = None,
    llm_client: OpenAIClient | None = None,
) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG["model_config"])
    return run_projectnavigator(state=state, llm_client=llm_client)


if __name__ == "__main__":
    main()
