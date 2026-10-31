from __future__ import annotations

from .config import AGENT_CONFIG
from .model import AgentState
from .utils import OpenAIClient
from .workflow import invoke_worker


def main(
    *,
    state: AgentState | None = None,
    llm_client: OpenAIClient | None = None,
) -> AgentState:
    if state is None:
        state = AgentState(AGENT_CONFIG)
    if llm_client is None:
        llm_client = OpenAIClient(AGENT_CONFIG["model_config"])
    return invoke_worker(
        'CreativeConceptDeveloper',
        agent_state=state,
        llm_client=llm_client,
    )


if __name__ == "__main__":
    main()
