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
from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient


def run_abtestanalyzer(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'abtestanalyzer__command1'
    while pc != '__end__':
        match pc:
            case 'abtestanalyzer__command13':
                abtestanalyzer__command13(state, llm_client)
                pc = '__end__'
                continue
            case 'abtestanalyzer__command12':
                abtestanalyzer__command12(state, llm_client)
                pc = 'abtestanalyzer__command13'
                continue
            case 'abtestanalyzer__decision_1':
                if predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch1_1(state, llm_client):
                    pc = 'abtestanalyzer__command6'
                elif predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch2_2(state, llm_client):
                    pc = 'abtestanalyzer__command7'
                elif predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch3_3(state, llm_client):
                    pc = 'abtestanalyzer__command8'
                elif predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch4_4(state, llm_client):
                    pc = 'abtestanalyzer__command9'
                elif predicate_workers_ABTestAnalyzer_main_flow_if_block1_if_branch5_5(state, llm_client):
                    pc = 'abtestanalyzer__command10'
                else:
                    pc = 'abtestanalyzer__command11'
                continue
            case 'abtestanalyzer__command6':
                abtestanalyzer__command6(state, llm_client)
                pc = 'abtestanalyzer__command12'
                continue
            case 'abtestanalyzer__command7':
                abtestanalyzer__command7(state, llm_client)
                pc = 'abtestanalyzer__command12'
                continue
            case 'abtestanalyzer__command8':
                abtestanalyzer__command8(state, llm_client)
                pc = 'abtestanalyzer__command12'
                continue
            case 'abtestanalyzer__command9':
                abtestanalyzer__command9(state, llm_client)
                pc = 'abtestanalyzer__command12'
                continue
            case 'abtestanalyzer__command10':
                abtestanalyzer__command10(state, llm_client)
                pc = 'abtestanalyzer__command12'
                continue
            case 'abtestanalyzer__command11':
                abtestanalyzer__command11(state, llm_client)
                pc = 'abtestanalyzer__command12'
                continue
            case 'abtestanalyzer__command5':
                abtestanalyzer__command5(state, llm_client)
                pc = 'abtestanalyzer__decision_1'
                continue
            case 'abtestanalyzer__command4':
                abtestanalyzer__command4(state, llm_client)
                pc = 'abtestanalyzer__command5'
                continue
            case 'abtestanalyzer__command3':
                abtestanalyzer__command3(state, llm_client)
                pc = 'abtestanalyzer__command4'
                continue
            case 'abtestanalyzer__command2':
                abtestanalyzer__command2(state, llm_client)
                pc = 'abtestanalyzer__command3'
                continue
            case 'abtestanalyzer__command1':
                abtestanalyzer__command1(state, llm_client)
                pc = 'abtestanalyzer__command2'
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
    return run_abtestanalyzer(state=state, llm_client=llm_client)


if __name__ == "__main__":
    main()
