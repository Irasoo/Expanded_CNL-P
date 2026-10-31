from .commands import (
    creativeconceptdeveloper__command1,
    creativeconceptdeveloper__command2,
    creativeconceptdeveloper__command3,
    creativeconceptdeveloper__command4,
    creativeconceptdeveloper__command5,
    creativeconceptdeveloper__command6,
    creativeconceptdeveloper__command7,
    creativeconceptdeveloper__command8,
    creativeconceptdeveloper__command9,
)
from .predicates import (
    predicate_workers_CreativeConceptDeveloper_main_flow_while_block1_1,
    predicate_workers_CreativeConceptDeveloper_main_flow_if_block1_if_branch1_2,
)
from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient


def run_creativeconceptdeveloper(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'creativeconceptdeveloper__command1'
    while pc != '__end__':
        match pc:
            case 'creativeconceptdeveloper__command9':
                creativeconceptdeveloper__command9(state, llm_client)
                pc = '__end__'
                continue
            case 'creativeconceptdeveloper__decision_2':
                if predicate_workers_CreativeConceptDeveloper_main_flow_if_block1_if_branch1_2(state, llm_client):
                    pc = 'creativeconceptdeveloper__command7'
                else:
                    pc = 'creativeconceptdeveloper__command8'
                continue
            case 'creativeconceptdeveloper__command7':
                creativeconceptdeveloper__command7(state, llm_client)
                pc = 'creativeconceptdeveloper__command9'
                continue
            case 'creativeconceptdeveloper__command8':
                creativeconceptdeveloper__command8(state, llm_client)
                pc = 'creativeconceptdeveloper__command9'
                continue
            case 'creativeconceptdeveloper__decision_1':
                if predicate_workers_CreativeConceptDeveloper_main_flow_while_block1_1(state, llm_client):
                    pc = 'creativeconceptdeveloper__command4'
                else:
                    pc = 'creativeconceptdeveloper__decision_2'
                continue
            case 'creativeconceptdeveloper__command6':
                creativeconceptdeveloper__command6(state, llm_client)
                pc = 'creativeconceptdeveloper__decision_1'
                continue
            case 'creativeconceptdeveloper__command5':
                creativeconceptdeveloper__command5(state, llm_client)
                pc = 'creativeconceptdeveloper__command6'
                continue
            case 'creativeconceptdeveloper__command4':
                creativeconceptdeveloper__command4(state, llm_client)
                pc = 'creativeconceptdeveloper__command5'
                continue
            case 'creativeconceptdeveloper__command3':
                creativeconceptdeveloper__command3(state, llm_client)
                pc = 'creativeconceptdeveloper__decision_1'
                continue
            case 'creativeconceptdeveloper__command2':
                creativeconceptdeveloper__command2(state, llm_client)
                pc = 'creativeconceptdeveloper__command3'
                continue
            case 'creativeconceptdeveloper__command1':
                creativeconceptdeveloper__command1(state, llm_client)
                pc = 'creativeconceptdeveloper__command2'
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
    return run_creativeconceptdeveloper(state=state, llm_client=llm_client)


if __name__ == "__main__":
    main()
