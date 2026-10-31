from .commands import (
    internalcommsdispatcher__command1,
    internalcommsdispatcher__command2,
    internalcommsdispatcher__command3,
    internalcommsdispatcher__command4,
    internalcommsdispatcher__command5,
    internalcommsdispatcher__command6,
    threepwriter__command7,
    threepwriter__command8,
    threepwriter__command9,
    threepwriter__command10,
    newsletterwriter__command11,
    newsletterwriter__command12,
    newsletterwriter__command13,
    faqwriter__command14,
    faqwriter__command15,
    faqwriter__command16,
    generalcommswriter__command17,
    generalcommswriter__command18,
    generalcommswriter__command19,
    generalcommswriter__command20,
)
from .predicates import (
    predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch1_1,
    predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch2_2,
    predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch3_3,
    predicate_workers_InternalCommsDispatcher_exception_flow1_4,
)
from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient


def run_internalcommsdispatcher(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'internalcommsdispatcher__command1'
    while pc != '__end__':
        match pc:
            case 'internalcommsdispatcher__command6':
                internalcommsdispatcher__command6(state, llm_client)
                pc = '__end__'
                continue
            case 'internalcommsdispatcher__decision_1':
                if predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch1_1(state, llm_client):
                    pc = 'internalcommsdispatcher__command2'
                elif predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch2_2(state, llm_client):
                    pc = 'internalcommsdispatcher__command3'
                elif predicate_workers_InternalCommsDispatcher_main_flow_if_block1_if_branch3_3(state, llm_client):
                    pc = 'internalcommsdispatcher__command4'
                else:
                    pc = 'internalcommsdispatcher__command5'
                continue
            case 'internalcommsdispatcher__command2':
                internalcommsdispatcher__command2(state, llm_client)
                pc = '__end__'
                continue
            case 'internalcommsdispatcher__command3':
                internalcommsdispatcher__command3(state, llm_client)
                pc = '__end__'
                continue
            case 'internalcommsdispatcher__command4':
                internalcommsdispatcher__command4(state, llm_client)
                pc = '__end__'
                continue
            case 'internalcommsdispatcher__command5':
                internalcommsdispatcher__command5(state, llm_client)
                pc = '__end__'
                continue
            case 'internalcommsdispatcher__command1':
                internalcommsdispatcher__command1(state, llm_client)
                if predicate_workers_InternalCommsDispatcher_exception_flow1_4(state, llm_client):
                    pc = 'internalcommsdispatcher__command6'
                else:
                    pc = 'internalcommsdispatcher__decision_1'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state
def run_threepwriter(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'threepwriter__command7'
    while pc != '__end__':
        match pc:
            case 'threepwriter__command10':
                threepwriter__command10(state, llm_client)
                pc = '__end__'
                continue
            case 'threepwriter__command9':
                threepwriter__command9(state, llm_client)
                pc = 'threepwriter__command10'
                continue
            case 'threepwriter__command8':
                threepwriter__command8(state, llm_client)
                pc = 'threepwriter__command9'
                continue
            case 'threepwriter__command7':
                threepwriter__command7(state, llm_client)
                pc = 'threepwriter__command8'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state
def run_newsletterwriter(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'newsletterwriter__command11'
    while pc != '__end__':
        match pc:
            case 'newsletterwriter__command13':
                newsletterwriter__command13(state, llm_client)
                pc = '__end__'
                continue
            case 'newsletterwriter__command12':
                newsletterwriter__command12(state, llm_client)
                pc = 'newsletterwriter__command13'
                continue
            case 'newsletterwriter__command11':
                newsletterwriter__command11(state, llm_client)
                pc = 'newsletterwriter__command12'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state
def run_faqwriter(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'faqwriter__command14'
    while pc != '__end__':
        match pc:
            case 'faqwriter__command16':
                faqwriter__command16(state, llm_client)
                pc = '__end__'
                continue
            case 'faqwriter__command15':
                faqwriter__command15(state, llm_client)
                pc = 'faqwriter__command16'
                continue
            case 'faqwriter__command14':
                faqwriter__command14(state, llm_client)
                pc = 'faqwriter__command15'
                continue
            case _:
                raise RuntimeError(f'Unknown program counter: {pc!r}')
    return state
def run_generalcommswriter(*, state: AgentState | None=None, llm_client: OpenAIClient | None=None) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG['model_config'])
    pc = 'generalcommswriter__command17'
    while pc != '__end__':
        match pc:
            case 'generalcommswriter__command20':
                generalcommswriter__command20(state, llm_client)
                pc = '__end__'
                continue
            case 'generalcommswriter__command19':
                generalcommswriter__command19(state, llm_client)
                pc = 'generalcommswriter__command20'
                continue
            case 'generalcommswriter__command18':
                generalcommswriter__command18(state, llm_client)
                pc = 'generalcommswriter__command19'
                continue
            case 'generalcommswriter__command17':
                generalcommswriter__command17(state, llm_client)
                pc = 'generalcommswriter__command18'
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
    return run_internalcommsdispatcher(state=state, llm_client=llm_client)


if __name__ == "__main__":
    main()
